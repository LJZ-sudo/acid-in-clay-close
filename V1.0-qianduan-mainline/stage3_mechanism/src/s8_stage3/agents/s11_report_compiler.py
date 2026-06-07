from __future__ import annotations

from pathlib import Path

from s8_stage3.config.prompt_registry import load_prompt
from s8_stage3.contracts.evidence import EvidenceBundle
from s8_stage3.contracts.material import MaterialFamilySet, MaterialInstanceSet
from s8_stage3.contracts.mechanism import MechanismArbitrationResult
from s8_stage3.contracts.ranking import RankingResult
from s8_stage3.contracts.report import AuditTrail, ReportSection, Stage3Report
from s8_stage3.io.writers import write_json, write_markdown
from s8_stage3.llm.prompt_packing import pack_for_s11


def _normalize_s11_result(raw: dict) -> dict:
    return dict(raw or {})


def _fallback_report(
    evidence: EvidenceBundle,
    arbitration: MechanismArbitrationResult,
    family_set: MaterialFamilySet,
    instance_set: MaterialInstanceSet,
    ranking: RankingResult,
) -> Stage3Report:
    sections = [
        ReportSection(
            section_id="S1",
            title="Evidence Summary",
            content=f"{len(evidence.evidence_cards)} evidence cards constrain the mechanism reasoning.",
        ),
        ReportSection(
            section_id="S2",
            title="Selected Mechanism",
            content=(
                f"{arbitration.mechanism_card.mechanism_label}: "
                f"{arbitration.mechanism_card.justification}"
            ),
        ),
        ReportSection(
            section_id="S3",
            title="Candidate Ranking",
            content=f"{len(ranking.ranked_candidates)} material instances ranked for transfer validation.",
        ),
    ]
    top = [
        {
            "rank": cand.rank,
            "name": cand.instance_name,
            "score": cand.total_score,
            "literature_support_card_ids": cand.literature_support_card_ids,
        }
        for cand in ranking.ranked_candidates[:5]
    ]
    return Stage3Report(
        sections=sections,
        top_candidates_summary=top,
        audit_trail=[
            AuditTrail(step_id="s03", status="completed", notes=f"{len(evidence.evidence_cards)} cards"),
            AuditTrail(step_id="s06", status="completed", notes=arbitration.mechanism_card.selected_hypothesis_id),
            AuditTrail(step_id="s09", status="completed", notes=f"{len(instance_set.instances)} instances"),
            AuditTrail(step_id="s10", status="completed", notes=f"{len(ranking.ranked_candidates)} ranked"),
        ],
    )


def _render_markdown(report: Stage3Report) -> str:
    lines = [f"# {report.title}", ""]
    for section in report.sections:
        lines.append(f"## {section.title}")
        lines.append(section.content)
        lines.append("")
    if report.top_candidates_summary:
        lines.append("## Top Candidates")
        for row in report.top_candidates_summary:
            lines.append(f"- Rank {row.get('rank')}: {row.get('name')} (score={row.get('score')})")
        lines.append("")
    lines.append(f"> {report.eis_disclaimer}")
    return "\n".join(lines) + "\n"


def run_s11(
    evidence: EvidenceBundle,
    arbitration: MechanismArbitrationResult,
    family_set: MaterialFamilySet,
    instance_set: MaterialInstanceSet,
    ranking: RankingResult,
    gateway,
    output_dir: Path,
    *,
    settings=None,
) -> Stage3Report:
    state = {
        "evidence_bundle": evidence.model_dump(mode="json"),
        "mechanism_card": arbitration.mechanism_card.model_dump(mode="json"),
        "material_families": family_set.model_dump(mode="json"),
        "material_instances": instance_set.model_dump(mode="json"),
        "ranked_candidates": [c.model_dump(mode="json") for c in ranking.ranked_candidates],
    }
    deterministic = bool(getattr(settings, "s11_deterministic_report", False))
    gateway_is_mock = bool(getattr(gateway, "is_mock", False))
    if deterministic and not gateway_is_mock:
        report = _fallback_report(evidence, arbitration, family_set, instance_set, ranking)
    else:
        try:
            raw = gateway.chat_json(
                [
                    {"role": "system", "content": load_prompt("s11_report_compiler")},
                    {"role": "user", "content": pack_for_s11(state)},
                ],
                step="s11_report_compiler",
                output_schema=Stage3Report,
            )
            report = Stage3Report.model_validate(_normalize_s11_result(raw))
        except Exception:
            report = _fallback_report(evidence, arbitration, family_set, instance_set, ranking)

    write_json(
        output_dir / "10_reports" / "report_generation_audit.json",
        {
            "generation_mode": (
                "deterministic_fallback_report"
                if deterministic and not gateway_is_mock
                else "llm_report_with_exception_fallback"
            ),
            "n_sections": len(report.sections),
            "n_top_candidates": len(report.top_candidates_summary),
        },
    )
    write_json(output_dir / "10_reports" / "stage3_report.json", report)
    write_markdown(output_dir / "10_reports" / "stage3_report.md", _render_markdown(report))
    return report
