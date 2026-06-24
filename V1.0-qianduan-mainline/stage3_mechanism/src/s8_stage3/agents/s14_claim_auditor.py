"""S14 Claim Auditor / Claim Ladder (P-Stage3-J)。

根据：
    - settings.discovery_mode / final_audit
    - <current output_dir>/source_term_audit.json（P-Stage3-C）
    - <current output_dir>/11_candidate_registry/prospective_candidates.json（S12）
    - <current output_dir>/12_validation_binding/validation_binding_report.json（S13）
    - Stage1 closed_loop_metrics.json（Stage1 P-Stage1-C）

自动生成可写 claim ladder，并标出 publication_blockers / recommended_wording。

纯确定性、不调用 LLM。
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from s8_stage3.contracts.claim_audit import (
    ClaimAuditReport,
    ClaimLadderItem,
)
from s8_stage3.contracts.discovery import (
    ALLOWED_CLAIM_BY_MODE,
    CLAIM_STRENGTH_BY_MODE,
)
from s8_stage3.io.writers import write_json, write_markdown
from s8_stage3.preprocess.eis_guardrails import check_eis_absolute_claims

logger = logging.getLogger(__name__)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha256_or_missing(p: Path) -> str:
    try:
        return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else "missing"
    except Exception:  # noqa: BLE001
        return "error"


def _locate_closed_loop_metrics() -> Optional[Path]:
    """尝试定位 Stage1 closed_loop_metrics.json。"""
    stage3_root = Path(__file__).parent.parent.parent.parent
    candidates = [
        # Prefer campaign-aware prospective real metrics over the legacy root file.
        stage3_root.parent / "stage1_optimization" / "output" / "attapulgite_aice" / "closed_loop_metrics.json",
        stage3_root.parent / "stage1_optimization" / "output" / "closed_loop_metrics.json",
        stage3_root.parent / "stage1_optimization" / "outputs" / "closed_loop_metrics.json",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def _load_json(p: Optional[Path]) -> Optional[dict]:
    if p is None or not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        logger.warning("[S14] Failed to load %s: %s", p, e)
        return None


def _rel_output_path(output_dir: Path, path: Path) -> str:
    try:
        return str(path.relative_to(output_dir)).replace("\\", "/")
    except ValueError:
        return str(path)


def _ranking_robustness_gate(output_dir: Path) -> dict:
    path = output_dir / "09_ranking" / "ranking_robustness_v2.json"
    data = _load_json(path) or {}
    if not data:
        return {
            "path": path,
            "present": False,
            "status": "missing",
            "stability_class": "missing",
            "top1_stability_rate": None,
            "top3_jaccard_mean": None,
            "recommended_wording_hint": (
                "Ranking robustness was not available; avoid single-winner claims."
            ),
            "claim_ok": False,
            "single_winner_ok": False,
        }
    status = str(data.get("status") or "ok")
    stability_class = str(data.get("stability_class") or "unstable")
    top1 = data.get("top1_stability_rate")
    top3 = data.get("top3_jaccard_mean")
    try:
        top1_f = float(top1)
    except (TypeError, ValueError):
        top1_f = None
    try:
        top3_f = float(top3)
    except (TypeError, ValueError):
        top3_f = None
    claim_ok = (
        status == "ok"
        and stability_class in {"stable", "moderately_stable"}
        and (top3_f is None or top3_f >= 0.6)
    )
    single_winner_ok = (
        claim_ok
        and stability_class == "stable"
        and top1_f is not None
        and top1_f >= 0.7
        and top3_f is not None
        and top3_f >= 0.8
    )
    return {
        "path": path,
        "present": True,
        "status": status,
        "stability_class": stability_class,
        "top1_stability_rate": top1_f,
        "top3_jaccard_mean": top3_f,
        "recommended_wording_hint": data.get("recommended_wording_hint") or "",
        "claim_ok": claim_ok,
        "single_winner_ok": single_winner_ok,
    }


# --- C0–C5 + four-state alignment (additive 2026-06-21; see THREE_INNOVATIONS §8).
#     Pure derivation from already-decided fields. NEVER mutates is_supported,
#     caveats, publication_blockers, or recommended_wording. ---
_CLEVEL_BY_CLAIM = {
    "closed_loop_source_system": "C1",   # single (mother) system measurement/optimisation fact
    "retrospective_validation": "C2",    # cross-batch relative consistency
    "llm_transfer_candidate": "C2",      # cross-system transfer (select/recombine level)
    "prospective_validation": "C3",      # frozen-then-measured empirical validation
    "mechanism_consistency": "C4",       # 首选命名(M2-5/G6):机理一致/相容(封顶;保留替代解释)
    "mechanism_discovery": "C4",         # DEPRECATED 别名:命名暗示超额,仍映射 C4 以向后兼容
    "unsupported": "C0",
}
_C_ORDER = ["C0", "C1", "C2", "C3", "C4", "C5"]
_C4_CAP = "C4"  # EIS transport-only must never auto-emit C5 (structure/causal)


def _assign_c_level_and_status(item: ClaimLadderItem, applicability_domain: str) -> None:
    """Fill the additive C0–C5 / four-state fields on a ladder item, in place.

    Hard cap at C4 for EIS-only evidence. 'refuted' is intentionally NOT assigned
    here (no explicit falsification signal in this deterministic auditor; it is
    reserved for the P3 critic). Unsupported -> invalid; supported -> supported;
    otherwise inconclusive (valid but insufficient / unidentifiable).
    """
    base = _CLEVEL_BY_CLAIM.get(item.claim_level, "C1")
    if _C_ORDER.index(base) > _C_ORDER.index(_C4_CAP):
        base = _C4_CAP
    item.claim_level_c = base  # type: ignore[assignment]
    if item.claim_level == "unsupported":
        item.status = "invalid"
    elif item.is_supported:
        item.status = "supported"
    else:
        item.status = "inconclusive"
    item.falsifier = item.forbidden_overclaim or ""
    item.applicability_domain = applicability_domain


def run_s14(
    output_dir: Path,
    settings,
    *,
    registry_path: Optional[Path] = None,
    binding_path: Optional[Path] = None,
    source_audit_path: Optional[Path] = None,
    closed_loop_metrics_path: Optional[Path] = None,
    strict_eis_guardrail: Optional[bool] = None,
) -> ClaimAuditReport:
    """装配 claim ladder。所有输入文件缺失时仍返回可读报告，仅 is_supported=False。

    Tier2 (2026-06-01, issue 3-cont): a deterministic EIS-overclaim guardrail now
    scans the assembled claim ladder + recommended wording for absolute EIS
    phrasing ("EIS proves/confirms/...", "等效电路已确定", ...) using the formerly
    unwired ``eis_guardrails.check_eis_absolute_claims``. By default it is ADVISORY
    (findings are logged + recorded in inputs_digest, no new blocker), so the frozen
    publication_blockers=[] is preserved. When ``strict_eis_guardrail`` is True (param,
    or settings.strict_eis_guardrail, or env STAGE3_STRICT_EIS_GUARDRAIL=1) any finding
    becomes a publication blocker. Run strict into a NEW dir, never over frozen.
    """
    output_dir = Path(output_dir)
    registry_path = registry_path or (
        output_dir / "11_candidate_registry" / "prospective_candidates.json"
    )
    binding_path = binding_path or (
        output_dir / "12_validation_binding" / "validation_binding_report.json"
    )
    stage3_root = Path(__file__).parent.parent.parent.parent
    if source_audit_path is None:
        audit_candidates = [
            output_dir / "source_term_audit.json",
            stage3_root / "audit" / "source_term_audit.json",
        ]
        source_audit_path = next(
            (p for p in audit_candidates if p.exists()), audit_candidates[0]
        )
    closed_loop_metrics_path = (
        closed_loop_metrics_path or _locate_closed_loop_metrics()
    )

    registry = _load_json(registry_path)
    binding = _load_json(binding_path)
    source_audit = _load_json(source_audit_path)
    closed_loop = _load_json(closed_loop_metrics_path)
    candidate_audit_path = output_dir / "09_ranking" / "candidate_audit.json"
    candidate_audit = _load_json(candidate_audit_path)
    robustness = _ranking_robustness_gate(output_dir)

    discovery_mode = str(getattr(settings, "discovery_mode", "broad_literature_pool_selection"))
    final_audit = bool(getattr(settings, "final_audit", False))
    claim_strength = CLAIM_STRENGTH_BY_MODE.get(discovery_mode, "moderate")
    allowed_mode_claim = ALLOWED_CLAIM_BY_MODE.get(discovery_mode, "")

    ladder: list[ClaimLadderItem] = []
    blockers: list[str] = []
    wording: list[str] = []

    # === L1: closed_loop_source_system ===
    cl_validity = (closed_loop or {}).get("closed_loop_validity", "")
    n_rounds = int((closed_loop or {}).get("n_closed_loop_rounds", 0) or 0)
    cl_supported = cl_validity == "prospective_real" and n_rounds >= 3
    cl_metrics_label = (
        str(closed_loop_metrics_path)
        if closed_loop_metrics_path
        else "missing"
    )
    if cl_supported:
        cl_status = (
            f"closed_loop_validity={cl_validity}, n_rounds={n_rounds}, "
            f"metrics={cl_metrics_label} -> supported."
        )
        cl_allowed = (
            "Acid-in-clay is the closed-loop mother system and underwent prospective "
            "BO-driven optimisation over multiple real rounds."
        )
    else:
        cl_status = (
            f"closed_loop_validity={cl_validity or 'missing'}, n_rounds={n_rounds}. "
            f"metrics={cl_metrics_label}. Not yet a prospective real closed loop; "
            "retrospective / virtual / replay."
        )
        cl_allowed = (
            "Acid-in-clay data were used as the mother-system evidence base; full "
            "prospective closed-loop optimisation is ongoing."
        )
        wording.append(
            "Avoid claiming 'closed-loop optimisation' in the abstract until Stage1 "
            "produces closed_loop_validity=prospective_real with >= 3 real rounds."
        )
    ladder.append(
        ClaimLadderItem(
            claim_level="closed_loop_source_system",
            allowed_claim=cl_allowed,
            required_evidence=[
                "stage1_optimization/output/attapulgite_aice/closed_loop_metrics.json with "
                "closed_loop_validity=prospective_real and n_closed_loop_rounds>=3"
            ],
            current_evidence_status=cl_status,
            forbidden_overclaim=(
                "Do not call retrospective_replay or virtual_oracle runs a "
                "'closed-loop optimisation'."
            ),
            caveats=(
                ["Current Stage1 metrics show retrospective/virtual mode."]
                if not cl_supported
                else []
            ),
            is_supported=cl_supported,
        )
    )

    # === L2: mechanism_discovery ===
    mech_card_candidates = [
        output_dir / "04_mechanism" / "mechanism_card.json",
        output_dir / "04_mechanism_card" / "mechanism_card.json",
        output_dir / "03_mechanism_arbitration" / "mechanism_card.json",
    ]
    mech_card_path = next((p for p in mech_card_candidates if p.exists()), mech_card_candidates[0])
    evidence_cards_path = output_dir / "01_evidence" / "evidence_cards.json"
    evidence_cards_data = _load_json(evidence_cards_path)
    evidence_cards = (evidence_cards_data or {}).get("evidence_cards") or []
    v2_evidence_card_count = sum(
        1 for card in evidence_cards
        if str(card.get("card_id") or "").startswith("V2-E")
        or bool((card.get("support_metrics") or {}).get("v2_evidence_id"))
    )
    mech_supported = mech_card_path.exists() and (
        v2_evidence_card_count > 0 or not final_audit
    )
    mech_evidence_ref = _rel_output_path(output_dir, mech_card_path)
    evidence_cards_ref = _rel_output_path(output_dir, evidence_cards_path)
    ladder.append(
        ClaimLadderItem(
            claim_level="mechanism_discovery",
            allowed_claim=(
                "LLM-generated mechanism hypotheses, constrained by Stage2 evidence "
                "(V2 seed), yielded a winning mechanism describing confined vs bulk "
                "proton populations and an overfilling crossover."
            ),
            required_evidence=[
                mech_evidence_ref,
                f"{evidence_cards_ref} containing EvidenceUnitV2-derived cards",
            ],
            current_evidence_status=(
                f"mechanism_card={'present' if mech_card_path.exists() else 'missing'}, "
                f"v2_evidence_cards={v2_evidence_card_count}."
            ),
            forbidden_overclaim=(
                "Do not say 'LLM proved the mechanism'. LLMs generate and arbitrate "
                "hypotheses; proof requires experiment + statistics."
            ),
            caveats=["Mechanism claim must always be hedged as 'hypothesised/supported'."],
            is_supported=mech_supported,
        )
    )

    # === L3: llm_transfer_candidate ===
    n_candidates = int((registry or {}).get("n_candidates", 0) or 0)
    candidate_audit_rows = []
    if isinstance(candidate_audit, dict):
        candidate_audit_rows = candidate_audit.get("rows") or []
        if n_candidates <= 0:
            n_candidates = int(candidate_audit.get("n_candidates", 0) or 0)
    bad_citation_candidates = [
        str(row.get("instance_id"))
        for row in candidate_audit_rows
        if row.get("bad_cited_paper_ids")
    ]
    low_coverage_candidates = [
        str(row.get("instance_id"))
        for row in candidate_audit_rows
        if float(row.get("descriptor_claim_coverage") or 0.0) < 0.5
        or int(row.get("n_element_descriptor_pairs") or 0) <= 0
    ]
    candidate_audit_quality_ok = (
        bool(candidate_audit_rows)
        and not bad_citation_candidates
        and not low_coverage_candidates
    )
    source_term_audit_ok = True
    source_term_audit_source = "default_true_no_audit_file"
    if isinstance(candidate_audit, dict) and "source_term_audit_ok" in candidate_audit:
        source_term_audit_ok = bool(candidate_audit.get("source_term_audit_ok"))
        source_term_audit_source = "09_ranking/candidate_audit.json"
    elif source_audit:
        source_term_audit_source = "source_term_audit.json"
        groups = {}
        if isinstance(source_audit, dict):
            if isinstance(source_audit.get("groups"), dict):
                groups = source_audit["groups"]
            else:
                groups = {
                    k: v
                    for k, v in source_audit.items()
                    if isinstance(v, dict)
                    and ("violations" in v or "n_hits_total" in v or "hits" in v)
                }
        for _gname, gdata in (groups or {}).items():
            if not isinstance(gdata, dict):
                continue
            violations = gdata.get("violations") or []
            if violations:
                source_term_audit_ok = False
                break
    transfer_supported = (
        n_candidates > 0
        and candidate_audit_quality_ok
        and (source_term_audit_ok or claim_strength != "strong")
        and (robustness["claim_ok"] or not final_audit)
    )
    registry_ref = _rel_output_path(output_dir, registry_path)
    candidate_audit_ref = _rel_output_path(output_dir, candidate_audit_path)
    source_audit_ref = _rel_output_path(output_dir, source_audit_path)
    robustness_ref = _rel_output_path(output_dir, robustness["path"])
    transfer_caveats = (
        [
            "Final-audit=True disables LLM cache; claim strength is tied to "
            "discovery_mode."
        ]
        if final_audit
        else [
            "final_audit=False — cached LLM responses may have been reused; "
            "do not make final publication claims from this run."
        ]
    )
    if not source_term_audit_ok:
        transfer_caveats.append(
            "source-term audit is not clean; keep wording at the registered "
            "discovery_mode level and do not claim blind or independent discovery."
        )
    if not candidate_audit_quality_ok:
        transfer_caveats.append(
            "candidate_audit is missing or weak: every supported transfer claim "
            "needs clean citation ids and descriptor_claim_coverage >= 0.5."
        )
    if not robustness["claim_ok"]:
        transfer_caveats.append(
            "ranking robustness is insufficient for strong or single-winner claims; "
            + str(robustness["recommended_wording_hint"])
        )
    ladder.append(
        ClaimLadderItem(
            claim_level="llm_transfer_candidate",
            allowed_claim=allowed_mode_claim
            or (
                "LLM transferred acid-in-clay-derived design principles to "
                "biopolymer–clay–H3PO4 candidate materials."
            ),
            required_evidence=[
                registry_ref,
                f"{candidate_audit_ref} and {source_audit_ref} with discovery-mode "
                "consistent source-term status",
                f"{robustness_ref} with stable or moderately_stable ranking robustness",
            ],
            current_evidence_status=(
                f"discovery_mode={discovery_mode}, claim_strength={claim_strength}, "
                f"n_candidates={n_candidates}, source_term_audit_ok={source_term_audit_ok} "
                f"(source={source_term_audit_source}), "
                f"candidate_audit_quality_ok={candidate_audit_quality_ok}, "
                f"ranking_stability_class={robustness['stability_class']}, "
                f"top1_stability={robustness['top1_stability_rate']}, "
                f"top3_jaccard={robustness['top3_jaccard_mean']}, "
                f"bad_citation_candidates={bad_citation_candidates}, "
                f"low_coverage_candidates={low_coverage_candidates}."
            ),
            forbidden_overclaim=(
                "Do not escalate beyond the discovery_mode allowance. "
                "broad_literature_pool_selection → 'selected / recombined', NOT "
                "'independently discovered'."
            ),
            caveats=transfer_caveats,
            is_supported=transfer_supported,
        )
    )

    # === L4 vs L5: prospective vs retrospective validation ===
    links = (binding or {}).get("candidate_links") or []
    n_pros = sum(
        1 for l in links if l.get("claim_eligibility") == "prospective_validation"
    )
    n_retro = sum(
        1 for l in links if l.get("claim_eligibility") == "retrospective_validation"
    )
    n_mixed = sum(
        1 for l in links if l.get("claim_eligibility") == "mixed_validation"
    )

    pros_supported = n_pros > 0
    ladder.append(
        ClaimLadderItem(
            claim_level="prospective_validation",
            allowed_claim=(
                "LLM-ranked candidates were frozen before experiment and "
                "subsequently validated by wide-temperature EIS measurements."
            ),
            required_evidence=[
                "validation_binding_report.json with >=1 link classified as "
                "prospective_validation",
                "validation_timing=prospective and validation date > "
                "registry.preregistered_at",
            ],
            current_evidence_status=(
                f"n_prospective_links={n_pros}, n_mixed_links={n_mixed}, "
                f"n_retrospective_links={n_retro}."
            ),
            forbidden_overclaim=(
                "If experiments preceded registry.preregistered_at, call it "
                "'retrospective validation' only."
            ),
            caveats=(
                ["No prospective validation yet; only retrospective/no bindings."]
                if not pros_supported
                else []
            ),
            is_supported=pros_supported,
        )
    )

    retro_supported = n_retro > 0 or n_mixed > 0
    ladder.append(
        ClaimLadderItem(
            claim_level="retrospective_validation",
            allowed_claim=(
                "The biopolymer / PVA / 1D-clay / H3PO4 motif predicted by the "
                "evidence-constrained LLM pipeline is consistent with prior "
                "experimental measurements on the three biopolymer systems "
                "(lotus / corn starch / chitosan)."
            ),
            required_evidence=[
                "validation_binding_report.json with >=1 link classified as "
                "retrospective_validation or mixed_validation",
            ],
            current_evidence_status=(
                f"n_retrospective_links={n_retro}, n_mixed_links={n_mixed}."
            ),
            forbidden_overclaim=(
                "Do not present retrospective_validation as 'prospective discovery'."
            ),
            caveats=[
                "If any experiment time > registry.preregistered_at, prefer "
                "prospective_validation for that specific candidate."
            ],
            is_supported=retro_supported,
        )
    )

    # === L0: unsupported / publication_blocker stubs ===
    if final_audit and not source_term_audit_ok:
        blockers.append(
            "source_term_audit reports violations while final_audit=True. "
            "Fix leakage before publication run."
        )
    if final_audit and discovery_mode == "blind_transfer" and not source_term_audit_ok:
        blockers.append(
            "Cannot make blind_transfer claim with any pre-S09 leakage. "
            "Switch discovery_mode to broad_literature_pool_selection or "
            "eliminate leakage."
        )
    if final_audit and mech_card_path.exists() and v2_evidence_card_count <= 0:
        blockers.append(
            "mechanism_card exists but S03 evidence_cards contain no V2-derived "
            "EvidenceUnit cards. Re-run Stage2/Stage3 strict real mode before "
            "publication claims."
        )
    if final_audit and not candidate_audit_quality_ok:
        blockers.append(
            "candidate_audit is not publication-clean. Resolve bad citations and "
            "raise descriptor_claim_coverage >= 0.5 for ranked candidates before "
            "claiming transfer candidates."
        )
    if final_audit and not robustness["claim_ok"]:
        blockers.append(
            "ranking_robustness_v2 is missing or unstable. Do not make strong "
            "single-winner transfer-candidate claims until robustness is stable."
        )
    if not registry:
        blockers.append("Prospective candidate registry missing. Run S12 before S14.")
    if not binding:
        wording.append(
            "Validation binding report is missing or empty; claim_ladder prospective/"
            "retrospective layers remain unsupported."
        )

    wording.append(
        f"Core claim wording tied to discovery_mode={discovery_mode}: "
        f'"{allowed_mode_claim}"'
    )
    if robustness["recommended_wording_hint"]:
        wording.append(
            "Ranking robustness wording gate: "
            + str(robustness["recommended_wording_hint"])
        )
    if not pros_supported and retro_supported:
        wording.append(
            "Use 'evidence-constrained LLM transfer discovery, retrospectively "
            "validated on three biopolymer/PVA/1D-clay/H3PO4 systems' in abstract."
        )

    # === Tier2 EIS-overclaim guardrail (deterministic) ===
    if strict_eis_guardrail is None:
        import os as _os
        strict_eis_guardrail = bool(
            getattr(settings, "strict_eis_guardrail", False)
        ) or _os.getenv("STAGE3_STRICT_EIS_GUARDRAIL", "").strip() in {"1", "true", "True"}
    _guard_text_parts: list[str] = list(wording)
    for _it in ladder:
        _guard_text_parts.append(_it.current_evidence_status or "")
        _guard_text_parts.append(_it.allowed_claim or "")
        _guard_text_parts.extend(_it.caveats or [])
    eis_overclaim_findings = check_eis_absolute_claims("\n".join(_guard_text_parts))
    if eis_overclaim_findings:
        if strict_eis_guardrail:
            for _f in eis_overclaim_findings:
                blockers.append(f"EIS_OVERCLAIM(strict): {_f}")
            logger.warning(
                "[S14] EIS overclaim guardrail (STRICT): %d finding(s) promoted to blockers.",
                len(eis_overclaim_findings),
            )
        else:
            logger.warning(
                "[S14] EIS overclaim guardrail (advisory): %d finding(s) detected; "
                "not blocking (set strict to enforce). First: %s",
                len(eis_overclaim_findings),
                eis_overclaim_findings[0],
            )

    # === C0–C5 + four-state alignment (additive; does not change blockers/wording) ===
    _applicability = (
        f"EIS transport-only; biopolymer/clay/H3PO4 transfer; discovery_mode={discovery_mode}"
    )
    for _it in ladder:
        _assign_c_level_and_status(_it, _applicability)

    report = ClaimAuditReport(
        run_id=(registry or {}).get("run_id", "") if isinstance(registry, dict) else "",
        discovery_mode=discovery_mode,
        final_audit=final_audit,
        claim_ladder=ladder,
        publication_blockers=blockers,
        recommended_wording=wording,
        inputs_digest={
            "eis_overclaim_findings_count": str(len(eis_overclaim_findings)),
            "eis_overclaim_strict": "1" if strict_eis_guardrail else "0",
            "source_term_audit.json": _sha256_or_missing(source_audit_path),
            "candidate_audit.json": _sha256_or_missing(candidate_audit_path),
            "ranking_robustness_v2.json": _sha256_or_missing(robustness["path"]),
            "evidence_cards.json": _sha256_or_missing(evidence_cards_path),
            "prospective_candidates.json": _sha256_or_missing(registry_path),
            "validation_binding_report.json": _sha256_or_missing(binding_path),
            "closed_loop_metrics.json": (
                _sha256_or_missing(closed_loop_metrics_path)
                if closed_loop_metrics_path
                else "missing"
            ),
            "closed_loop_metrics_path": (
                str(closed_loop_metrics_path)
                if closed_loop_metrics_path
                else "missing"
            ),
            "audit_built_at": _utcnow_iso(),
        },
    )

    out_path = output_dir / "13_claim_audit" / "claim_audit_report.json"
    write_json(out_path, report)
    md_path = output_dir / "13_claim_audit" / "claim_audit_report.md"
    write_markdown(md_path, _render_markdown(report))

    logger.info(
        "[S14] Claim ladder built: %d layers, %d blockers, discovery_mode=%s.",
        len(ladder),
        len(blockers),
        discovery_mode,
    )
    for item in ladder:
        logger.info(
            "  [%s] supported=%s — %s",
            item.claim_level,
            item.is_supported,
            item.current_evidence_status,
        )
    return report


def _render_markdown(report: ClaimAuditReport) -> str:
    lines: list[str] = []
    lines.append(f"# Stage3 Claim Audit Report\n")
    lines.append(f"- **run_id**: `{report.run_id}`")
    lines.append(f"- **discovery_mode**: `{report.discovery_mode}`")
    lines.append(f"- **final_audit**: `{report.final_audit}`")
    lines.append("")
    lines.append("## Claim Ladder\n")
    for item in report.claim_ladder:
        mark = "PASS" if item.is_supported else "TODO"
        c_tag = f" · {item.claim_level_c}/{item.status}" if item.claim_level_c else ""
        lines.append(f"### [{mark}{c_tag}] `{item.claim_level}`\n")
        lines.append(f"**Allowed claim**: {item.allowed_claim}\n")
        lines.append(f"- current status: {item.current_evidence_status}")
        lines.append("- required evidence:")
        for r in item.required_evidence:
            lines.append(f"  - {r}")
        lines.append(f"- forbidden overclaim: {item.forbidden_overclaim}")
        if item.caveats:
            lines.append("- caveats:")
            for c in item.caveats:
                lines.append(f"  - {c}")
        lines.append("")

    if report.publication_blockers:
        lines.append("## Publication Blockers\n")
        for b in report.publication_blockers:
            lines.append(f"- **BLOCKER**: {b}")
        lines.append("")

    if report.recommended_wording:
        lines.append("## Recommended Wording\n")
        for w in report.recommended_wording:
            lines.append(f"- {w}")
        lines.append("")

    lines.append("## Inputs Digest\n")
    for k, v in report.inputs_digest.items():
        short = v if len(v) <= 20 else v[:16] + "..."
        lines.append(f"- `{k}`: {short}")
    return "\n".join(lines) + "\n"
