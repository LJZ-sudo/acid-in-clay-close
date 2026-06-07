from __future__ import annotations

import json
import logging
from pathlib import Path

from s8_stage3.config.prompt_registry import load_prompt
from s8_stage3.contracts.literature import LiteratureSurvey
from s8_stage3.contracts.material import MaterialInstanceSet
from s8_stage3.contracts.mechanism import MechanismArbitrationResult
from s8_stage3.contracts.ranking import RankedCandidate, RankingCriterion, RankingResult
from s8_stage3.io.writers import write_json
from s8_stage3.llm.prompt_packing import pack_for_s10
from s8_stage3.scoring.candidate_audit import audit_candidates
from s8_stage3.scoring.material_score import compute_weighted_score, validate_ranking_consistency
from s8_stage3.scoring.sensitivity import rank_sensitivity_summary

logger = logging.getLogger(__name__)


def _normalize_s10_result(raw: dict) -> dict:
    data = dict(raw or {})
    if "ranked_candidates" not in data:
        for alias in ("rankings", "candidates", "top_candidates"):
            if alias in data:
                data["ranked_candidates"] = data.pop(alias)
                break
    return data


def _inherit_instance_metadata(result: RankingResult, instances: MaterialInstanceSet) -> None:
    by_id = {inst.instance_id: inst for inst in instances.instances}
    for candidate in result.ranked_candidates:
        inst = by_id.get(candidate.instance_id)
        if inst is None:
            continue
        candidate.combination_novelty = inst.combination_novelty
        candidate.literature_support_card_ids = list(inst.literature_support_card_ids)
        candidate.novelty_rationale = inst.novelty_rationale
        if not candidate.instance_name:
            candidate.instance_name = inst.instance_name


def _emit_deterministic_audit(
    result: RankingResult,
    instances: MaterialInstanceSet,
    output_dir: Path,
) -> None:
    warnings = validate_ranking_consistency(result.ranked_candidates)
    recomputed = [
        {
            "instance_id": cand.instance_id,
            "rank": cand.rank,
            "llm_total_score": cand.total_score,
            "weighted_score_from_criteria": compute_weighted_score(cand),
        }
        for cand in result.ranked_candidates
    ]
    rows, reranked = audit_candidates(
        [inst.model_dump(mode="json") for inst in instances.instances],
        result.model_dump(mode="json"),
        output_dir,
        source_term_ok=True,
    )
    write_json(
        output_dir / "09_ranking" / "score_override_log.json",
        {"ranking_consistency_warnings": warnings, "recomputed": recomputed},
    )
    write_json(
        output_dir / "09_ranking" / "candidate_audit.json",
        {
            "n_candidates": len(rows),
            "source_term_audit_ok": True,
            "rows": rows,
        },
    )
    write_json(output_dir / "09_ranking" / "deterministic_reranked_top_list.json", {"ranked_candidates": reranked})


def _emit_ranking_robustness_v2(output_dir: Path) -> None:
    try:
        from s8_stage3.scoring.ranking_robustness_v2 import run_ranking_robustness_v2

        run_ranking_robustness_v2(output_dir=output_dir, n_seeds=200, plot=False)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[S10] ranking_robustness_v2 skipped: %s", exc)


def _build_manual_review_queue(result: RankingResult, survey: LiteratureSurvey) -> dict:
    used_card_ids = set()
    for candidate in result.ranked_candidates[:3]:
        used_card_ids.update(candidate.literature_support_card_ids)

    items: list[dict] = []
    for card in survey.cards:
        if used_card_ids and card.card_id not in used_card_ids:
            continue
        for claim in card.component_descriptor_claims:
            if claim.human_review_status != "pending":
                continue
            items.append(
                {
                    "card_id": card.card_id,
                    "title": card.title,
                    "component": claim.component,
                    "descriptor_ids": claim.descriptor_ids,
                    "quantitative_anchor": claim.quantitative_anchor,
                    "claim_text": claim.claim_text,
                    "confidence": claim.confidence,
                    "human_review_status": claim.human_review_status,
                    "reviewer": claim.reviewer,
                    "review_notes": claim.review_notes,
                    "reason": "Claim is linked to literature cards used by Top-3 ranked candidates.",
                }
            )
    return {"review_scope": "top3_literature_support_claims", "n_items": len(items), "items": items}


def _deterministic_seed_ranking(instances: MaterialInstanceSet) -> RankingResult:
    candidates: list[RankedCandidate] = []
    for rank, inst in enumerate(instances.instances, start=1):
        candidates.append(
            RankedCandidate(
                rank=rank,
                instance_id=inst.instance_id,
                instance_name=inst.instance_name,
                total_score=0.0,
                criteria_scores=[],
                ranking_rationale="Provisional candidate for deterministic audit scoring.",
                combination_novelty=inst.combination_novelty,
                literature_support_card_ids=list(inst.literature_support_card_ids),
                novelty_rationale=inst.novelty_rationale,
                risk_summary="; ".join(inst.risk_flags),
            )
        )
    return RankingResult(
        ranked_candidates=candidates,
        ranking_notes="Provisional ranking used only to compute deterministic candidate audit scores.",
    )


def _criterion(name: str, score: float, weight: float, rationale: str) -> RankingCriterion:
    return RankingCriterion(
        criterion_name=name,
        score=max(0.0, min(1.0, float(score or 0.0))),
        weight=weight,
        rationale=rationale,
    )


def _build_deterministic_ranking(
    instance_set: MaterialInstanceSet,
    output_dir: Path,
) -> RankingResult:
    """Rank candidates with the same auditable score components used by S14."""
    seed = _deterministic_seed_ranking(instance_set)
    rows, reranked = audit_candidates(
        [inst.model_dump(mode="json") for inst in instance_set.instances],
        seed.model_dump(mode="json"),
        output_dir,
        source_term_ok=True,
    )
    rows_by_id = {row["instance_id"]: row for row in rows}
    by_id = {inst.instance_id: inst for inst in instance_set.instances}

    candidates: list[RankedCandidate] = []
    for rank, row in enumerate(reranked, start=1):
        inst = by_id.get(row["instance_id"])
        if inst is None:
            continue
        risk_score = float(row.get("risk_score") or 0.0)
        criteria = [
            _criterion(
                "mechanism_fit",
                row.get("mechanism_fit_score", row.get("descriptor_claim_coverage", 0.0)),
                0.20,
                "Transfer mechanism fit from critical descriptors and role coverage.",
            ),
            _criterion(
                "evidence_quality",
                row.get("evidence_quality_score", row.get("descriptor_claim_coverage", 0.0)),
                0.18,
                "Claim confidence, quantitative anchors, support-card diversity, and pair count.",
            ),
            _criterion(
                "formulation_completeness",
                row.get("formulation_completeness_score", 0.0),
                0.18,
                "Presence of biopolymer host, film matrix, clay confinement, and acid carrier roles.",
            ),
            _criterion(
                "low_temperature_plausibility",
                row.get("low_temperature_plausibility_score", 0.0),
                0.14,
                "Cold-window plausibility from retention, confinement, clay, and H-bond motifs.",
            ),
            _criterion(
                "processability",
                row.get("processability_score", 0.0),
                0.11,
                "Film-forming and water-processable route with penalties for dispersion or brittleness.",
            ),
            _criterion(
                "novelty",
                row.get("novelty_score", 0.0),
                0.05,
                f"Deterministic novelty mapping for {row.get('combination_novelty')}.",
            ),
            _criterion(
                "citation_validity",
                row.get("citation_validity", 0.0),
                0.04,
                "Cited literature card ids are present in the S08 material pool.",
            ),
            _criterion(
                "risk_control",
                1.0 - risk_score,
                0.10,
                "Inverse risk score; risk enters the final priority score as a penalty.",
            ),
        ]
        candidates.append(
            RankedCandidate(
                rank=rank,
                instance_id=inst.instance_id,
                instance_name=inst.instance_name,
                total_score=float(row.get("deterministic_total_score") or 0.0),
                criteria_scores=criteria,
                ranking_rationale=(
                    "Deterministic S10 material-priority ranking from mechanism fit, "
                    "evidence quality, formulation completeness, low-temperature plausibility, "
                    "processability, novelty, citation validity, and risk penalties."
                ),
                combination_novelty=inst.combination_novelty,
                literature_support_card_ids=list(inst.literature_support_card_ids),
                novelty_rationale=inst.novelty_rationale,
                risk_summary="; ".join(inst.risk_flags) or "No explicit risk flags.",
            )
        )

    missing = sorted(set(by_id) - set(rows_by_id))
    notes = (
        "Deterministic ranking: total_score equals candidate_audit material_priority_score. "
        "Audit gate fields remain in candidate_audit for claim-boundary checks."
    )
    if missing:
        notes += f" Missing audit rows for: {', '.join(missing)}."
    return RankingResult(ranked_candidates=candidates, ranking_notes=notes)


def _manual_review_queue_path(output_dir: Path) -> Path:
    stage3_root = Path(__file__).resolve().parents[3]
    if output_dir.resolve().is_relative_to(stage3_root.resolve()):
        return stage3_root / "literature_workspace" / "08_manual_review" / "s10_top3_claim_review_queue.json"
    return output_dir / "09_ranking" / "s10_top3_claim_review_queue.json"


def run_s10(
    instance_set: MaterialInstanceSet,
    arbitration: MechanismArbitrationResult,
    material_literature: LiteratureSurvey,
    gateway,
    output_dir: Path,
    *,
    system_context=None,
    settings=None,
) -> RankingResult:
    deterministic = bool(getattr(settings, "s10_deterministic_from_audit", False))
    gateway_is_mock = bool(getattr(gateway, "is_mock", False))
    if deterministic and not gateway_is_mock:
        result = _build_deterministic_ranking(instance_set, output_dir)
        write_json(
            output_dir / "09_ranking" / "ranking_generation_audit.json",
            {
                "generation_mode": "deterministic_from_candidate_audit",
                "audit_ok": bool(result.ranked_candidates),
                "n_instances": len(instance_set.instances),
                "n_ranked_candidates": len(result.ranked_candidates),
            },
        )
    else:
        packed = pack_for_s10(
            [inst.model_dump(mode="json") for inst in instance_set.instances],
            arbitration.mechanism_card.model_dump(mode="json"),
            material_literature.model_dump(mode="json"),
            system_context.model_dump(mode="json") if system_context else None,
        )
        raw = gateway.chat_json(
            [
                {"role": "system", "content": load_prompt("s10_instance_ranker")},
                {"role": "user", "content": packed},
            ],
            step="s10_instance_ranker",
            output_schema=RankingResult,
        )
        result = RankingResult.model_validate(_normalize_s10_result(raw))
        result.ranked_candidates.sort(key=lambda item: item.rank)
        _inherit_instance_metadata(result, instance_set)
        write_json(
            output_dir / "09_ranking" / "ranking_generation_audit.json",
            {
                "generation_mode": "llm_ranker",
                "audit_ok": bool(result.ranked_candidates),
                "n_instances": len(instance_set.instances),
                "n_ranked_candidates": len(result.ranked_candidates),
            },
        )

    write_json(output_dir / "09_ranking" / "ranked_top_list.json", result)
    write_json(output_dir / "09_ranking" / "ranking_robustness.json", rank_sensitivity_summary(result.ranked_candidates))
    write_json(_manual_review_queue_path(output_dir), _build_manual_review_queue(result, material_literature))
    _emit_deterministic_audit(result, instance_set, output_dir)
    _emit_ranking_robustness_v2(output_dir)
    return result
