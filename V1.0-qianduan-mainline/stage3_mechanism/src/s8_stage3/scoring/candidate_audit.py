"""P-Stage3-G: 确定性候选审计模块。

LLM 只负责给出 candidate 解释和定性理由；最终 score 由 candidate_audit +
discovery_score 以代码方式决定。S10 在 LLM 排序后调用 `audit_candidates()`，
把每个 candidate 的 deterministic sub-scores 计算出来并产出 override 日志。
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


_NOVELTY_BASE = {
    "novel_combination": 0.85,
    "close_variant": 0.55,
    "exact_match": 0.25,
}

_COMPONENT_TOKEN_STOPWORDS = {
    "and", "or", "the", "with", "for", "from", "via", "in", "of",
    "component", "components", "matrix", "host", "network", "membrane",
    "composite", "placeholder", "source", "class", "eg", "e", "g",
}


def _clamp(v: float) -> float:
    return max(0.0, min(1.0, float(v or 0.0)))


def _load_json_safe(p: Path) -> Optional[dict]:
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        logger.warning("[CandidateAudit] failed to load %s: %s", p, e)
        return None


def _descriptor_claim_index(
    claim_pool: Optional[dict],
) -> dict[str, set[str]]:
    """返回 descriptor_id -> 支持它的 card_id 集合。"""
    index: dict[str, set[str]] = {}
    if not claim_pool:
        return index
    for entry in claim_pool.get("claims") or []:
        card_id = entry.get("card_id")
        if not card_id:
            continue
        for did in entry.get("descriptor_ids") or []:
            index.setdefault(did, set()).add(card_id)
    return index


def _component_tokens(value: str) -> set[str]:
    raw = re.findall(r"[a-z0-9]+", (value or "").lower())
    tokens = {
        t for t in raw
        if len(t) >= 2 and t not in _COMPONENT_TOKEN_STOPWORDS
    }
    joined = " ".join(tokens)
    if {"poly", "vinyl", "alcohol"}.issubset(tokens) or "polyvinyl" in tokens:
        tokens.add("pva")
    if {"phosphoric", "acid"}.issubset(tokens):
        tokens.add("h3po4")
    if "palygorskite" in tokens:
        tokens.add("attapulgite")
    return tokens


def _component_matches(candidate_component: str, claim_component: str) -> bool:
    cand = (candidate_component or "").strip().lower()
    claim = (claim_component or "").strip().lower()
    if not cand or not claim:
        return False
    if len(claim) >= 4 and claim in cand:
        return True
    if len(cand) >= 4 and cand in claim:
        return True
    return bool(_component_tokens(cand) & _component_tokens(claim))


def _confidence_value(value: str) -> float:
    return {
        "supported": 1.0,
        "hint": 0.65,
        "disputed": 0.2,
    }.get(str(value or "").strip().lower(), 0.75)


def _claim_descriptor_ids(entry: dict) -> set[str]:
    dids = entry.get("descriptor_ids")
    if dids is None:
        dids = entry.get("descriptor_id")
    if dids is None:
        return set()
    if isinstance(dids, str):
        return {dids.strip()} if dids.strip() else set()
    return {str(d).strip() for d in dids if str(d).strip()}


def _element_descriptor_support(
    inst_dump: dict,
    claim_pool: Optional[dict],
) -> dict:
    """Audit each claimed (component, descriptor) pair against S08 claim_pool.

    A pair is supported only when a claim has the same descriptor id and a
    component-level match.  If the candidate cites analog_paper_ids, the support
    must also come from one of those cited cards.  This prevents a candidate from
    citing a paper that supports the descriptor for a different component.
    """
    claims = (claim_pool or {}).get("claims") or []
    pair_rows: list[dict] = []

    for ev in inst_dump.get("element_evidence") or []:
        component = str(ev.get("component") or "").strip()
        cited_ids = {str(pid).strip() for pid in (ev.get("analog_paper_ids") or []) if str(pid).strip()}
        for did in ev.get("descriptor_satisfied") or []:
            descriptor_id = str(did).strip()
            if not descriptor_id:
                continue
            support_card_ids: list[str] = []
            support_components: list[str] = []
            support_confidences: list[float] = []
            support_quantitative_anchors: list[str] = []
            for claim in claims:
                card_id = str(claim.get("card_id") or "").strip()
                if descriptor_id not in _claim_descriptor_ids(claim):
                    continue
                if cited_ids and card_id not in cited_ids:
                    continue
                if not _component_matches(component, str(claim.get("component") or "")):
                    continue
                if card_id:
                    support_card_ids.append(card_id)
                support_components.append(str(claim.get("component") or ""))
                support_confidences.append(_confidence_value(str(claim.get("confidence") or "")))
                anchor = str(claim.get("quantitative_anchor") or "").strip()
                if anchor:
                    support_quantitative_anchors.append(anchor)
            pair_rows.append({
                "component": component,
                "descriptor_id": descriptor_id,
                "cited_card_ids": sorted(cited_ids),
                "supported": bool(support_card_ids or support_components),
                "support_card_ids": sorted(set(support_card_ids)),
                "support_components": sorted(set(support_components)),
                "support_confidence_max": max(support_confidences) if support_confidences else 0.0,
                "has_quantitative_anchor": bool(support_quantitative_anchors),
            })

    n_pairs = len(pair_rows)
    n_supported = sum(1 for row in pair_rows if row["supported"])
    return {
        "coverage": (n_supported / n_pairs) if n_pairs else 0.0,
        "n_pairs": n_pairs,
        "n_supported_pairs": n_supported,
        "pairs": pair_rows,
        "unsupported_pairs": [row for row in pair_rows if not row["supported"]],
    }


def _bound_prospective_instance_ids(validation_binding: Optional[dict]) -> set[str]:
    """Instance ids that have at least one BOUND, PROSPECTIVE validation record.

    Tier2 (2026-06-01, issue 1): derives a deterministic prospective-status signal
    from the S13 validation-binding report. An instance counts as prospectively
    validated only if a real experimental record is bound to it with
    ``validation_timing == "prospective"``. No fabrication: if no binding report
    is supplied, the set is empty and ``prospective_status_score`` stays 0.0
    (i.e. identical to the pre-Tier2 / frozen behavior).
    """
    if not validation_binding:
        return set()
    ids: set[str] = set()
    for rec in validation_binding.get("records") or []:
        iid = str(rec.get("instance_id") or "").strip()
        timing = str(rec.get("validation_timing") or "").strip().lower()
        bound = rec.get("bound", True)  # records listed are bound unless flagged
        if iid and timing == "prospective" and bound:
            ids.add(iid)
    return ids


def _candidate_descriptor_ids(inst_dump: dict) -> set[str]:
    ids: set[str] = set()
    for ev in inst_dump.get("element_evidence") or []:
        for did in ev.get("descriptor_satisfied") or []:
            if did:
                ids.add(str(did).strip())
    return ids


def _risk_score(inst_dump: dict) -> float:
    """越高越坏 → 最终分数需要减。"""
    flags = " ".join(inst_dump.get("risk_flags") or []).lower()
    risk = 0.0
    for pattern, delta in [
        ("free acid leakage", 0.25),
        ("acid leach", 0.10),
        ("leaching", 0.10),
        ("bulk water freez", 0.25),
        ("water content", 0.20),
        ("mechanical fragil", 0.15),
        ("mechanical strength", 0.15),
        ("acid loss", 0.2),
        ("crystallis", 0.1),
        ("overfilling", 0.1),
        ("dispersion", 0.06),
        ("reproducibility", 0.04),
        ("swelling", 0.10),
        ("percolation", 0.07),
        ("optimisation", 0.05),
        ("optimization", 0.05),
        ("loading", 0.05),
        ("plasticise", 0.12),
        ("plasticize", 0.12),
        ("brittle", 0.15),
        ("brittleness", 0.15),
        ("oxide", 0.12),
        ("agglomeration", 0.22),
        ("block conduction", 0.20),
        ("acid-base", 0.12),
        ("screening", 0.04),
    ]:
        if pattern in flags:
            risk += delta
    return min(risk, 1.0)


def _citation_validity(inst_dump: dict, valid_card_ids: set[str]) -> tuple[float, list[str]]:
    """candidate 引用的 paper_id 必须都在 S08 pool 中。"""
    cited: list[str] = []
    for ev in inst_dump.get("element_evidence") or []:
        for pid in ev.get("analog_paper_ids") or []:
            if pid:
                cited.append(pid)
    for pid in inst_dump.get("literature_support_card_ids") or []:
        if pid:
            cited.append(pid)
    cited = list({c for c in cited if c})
    if not cited:
        return 0.5, []
    bad = [c for c in cited if c not in valid_card_ids]
    ok = len(cited) - len(bad)
    return (ok / len(cited)) if cited else 0.0, bad


def _text_bag(inst_dump: dict) -> str:
    parts: list[str] = []
    for key in ("instance_name", "composition_description", "novelty_rationale"):
        parts.append(str(inst_dump.get(key) or ""))
    parts.extend(str(x) for x in inst_dump.get("components") or [])
    parts.extend(str(x) for x in inst_dump.get("expected_properties") or [])
    parts.extend(str(x) for x in inst_dump.get("risk_flags") or [])
    for ev in inst_dump.get("element_evidence") or []:
        parts.append(str(ev.get("component") or ""))
        parts.append(str(ev.get("role_in_formulation") or ""))
        parts.append(str(ev.get("analog_reason") or ""))
    return " ".join(parts).lower()


def _has_any(text: str, patterns: list[str]) -> bool:
    return any(p in text for p in patterns)


def _formulation_role_scores(inst_dump: dict) -> dict[str, float]:
    text = _text_bag(inst_dump)
    return {
        "biopolymer_host": 1.0 if _has_any(text, ["starch", "chitosan", "cellulose", "biopolymer", "lotus", "lrs"]) else 0.0,
        "film_matrix": 1.0 if _has_any(text, ["pva", "poly(vinyl alcohol)", "film", "membrane", "matrix", "hydrogel"]) else 0.0,
        "clay_confinement": 1.0 if _has_any(text, ["attapulgite", "montmorillonite", "mmt", "halloysite", "hnt", "clay", "nanotube", "1-d", "1d"]) else 0.0,
        "acid_carrier": 1.0 if _has_any(text, ["h3po4", "phosphoric", " acid", "proton"]) else 0.0,
    }


def _formulation_completeness(inst_dump: dict) -> float:
    roles = _formulation_role_scores(inst_dump)
    return sum(roles.values()) / len(roles)


def _evidence_quality_score(pair_support: dict) -> float:
    pairs = pair_support.get("pairs") or []
    if not pairs:
        return 0.0
    supported = [p for p in pairs if p.get("supported")]
    if not supported:
        return 0.0
    per_pair = []
    unique_cards: set[str] = set()
    for row in supported:
        for cid in row.get("support_card_ids") or []:
            unique_cards.add(str(cid))
        conf = float(row.get("support_confidence_max") or 0.0)
        quant_bonus = 0.10 if row.get("has_quantitative_anchor") else 0.0
        per_pair.append(_clamp(conf + quant_bonus))
    avg_pair = sum(per_pair) / len(pairs)
    diversity_bonus = min(0.15, 0.035 * len(unique_cards))
    pair_count_bonus = min(0.10, 0.02 * len(supported))
    return _clamp(avg_pair + diversity_bonus + pair_count_bonus)


def _mechanism_fit_score(inst_dump: dict, cand_descs: set[str], descriptor_claim_coverage: float) -> float:
    roles = _formulation_completeness(inst_dump)
    core = 0.0
    if "D1" in cand_descs:
        core += 0.35
    if "D4" in cand_descs:
        core += 0.35
    bonus = 0.0
    if cand_descs & {"D3", "D5", "D6"}:
        bonus += 0.20
    if len(cand_descs) >= 3:
        bonus += 0.10
    return _clamp(0.45 * descriptor_claim_coverage + 0.35 * roles + 0.20 * _clamp(core + bonus))


def _low_temperature_plausibility(inst_dump: dict) -> float:
    text = _text_bag(inst_dump)
    score = 0.25
    if _has_any(text, ["cold", "low-temperature", "low temperature", "253", "193"]):
        score += 0.20
    if _has_any(text, ["bound-water", "bound water", "retained", "retention", "confined", "confinement"]):
        score += 0.20
    if _has_any(text, ["attapulgite", "halloysite", "nanotube", "1-d", "1d", "clay", "mmt"]):
        score += 0.15
    if _has_any(text, ["pva", "starch", "chitosan", "hydrogen-bond", "h-bond"]):
        score += 0.15
    if _has_any(text, ["glycerol", "anti-freeze", "antifreeze"]):
        score += 0.10
    if _has_any(text, ["water content may dominate", "bulk water", "freezing behaviour"]):
        score -= 0.20
    return _clamp(score)


def _processability_score(inst_dump: dict) -> float:
    text = _text_bag(inst_dump)
    score = 0.55
    if _has_any(text, ["film", "membrane", "water-processable", "water processable", "solution-cast", "cast"]):
        score += 0.20
    if _has_any(text, ["pva", "starch", "chitosan"]):
        score += 0.15
    if _has_any(text, ["dispersion", "agglomeration", "brittle", "brittleness", "mechanical strength", "swelling"]):
        score -= 0.20
    if _has_any(text, ["high acid fraction", "plasticise", "plasticize"]):
        score -= 0.10
    return _clamp(score)


def audit_candidates(
    instance_dumps: list[dict],
    ranking_dump: dict,
    output_dir: Path,
    *,
    source_term_ok: bool = True,
    discovery_mode: str = "broad_literature_pool_selection",
    registry_run_id: str = "",
    validation_binding: Optional[dict] = None,
) -> tuple[list[dict], list[dict]]:
    """为每个候选计算 deterministic score。

    Args:
        validation_binding: optional S13 validation-binding report. When supplied,
            candidates whose ``instance_id`` has a bound prospective validation get
            ``prospective_status_score = 1.0``; otherwise 0.0. Default ``None`` keeps
            the pre-Tier2 / frozen behavior (every candidate scores 0.0), so the live
            S10 pipeline run is byte-for-byte unchanged unless a binding is passed in.

    Returns:
        (audit_rows, reranked_candidates) —— 后者已按 deterministic_total_score 排序。
    """
    out_sub = output_dir / "06_literature_materials"
    prospective_instance_ids = _bound_prospective_instance_ids(validation_binding)
    claim_pool = _load_json_safe(out_sub / "descriptor_claim_pool.json")
    pool_balance = _load_json_safe(out_sub / "material_pool_balance.json")
    coverage_summary = _load_json_safe(out_sub / "claim_coverage_summary.json")

    descriptor_idx = _descriptor_claim_index(claim_pool)

    survey_path = out_sub / "literature_cards_materials.json"
    survey = _load_json_safe(survey_path) or {}
    valid_card_ids = {c.get("card_id") for c in survey.get("cards", []) if c.get("card_id")}

    inst_by_id = {i.get("instance_id"): i for i in instance_dumps}
    audit_rows: list[dict] = []
    for cand in ranking_dump.get("ranked_candidates") or []:
        iid = cand.get("instance_id")
        inst = inst_by_id.get(iid, {})
        llm_total = float(cand.get("total_score") or 0.0)
        nov = cand.get("combination_novelty") or inst.get("combination_novelty") or "novel_combination"

        # 1. descriptor_claim_coverage: component-level pair support, not only
        # descriptor-level global support.
        cand_descs = _candidate_descriptor_ids(inst)
        pair_support = _element_descriptor_support(inst, claim_pool)
        descriptor_claim_coverage = pair_support["coverage"]

        # 2. citation_validity
        citation_validity, bad_ids = _citation_validity(inst, valid_card_ids)

        # 3. combination_novelty deterministic mapping
        novelty_score = _NOVELTY_BASE.get(nov, 0.5)

        # 4. term_leakage_penalty
        term_leakage_penalty = 0.0 if source_term_ok else 0.3

        # 5. risk score
        risk = _risk_score(inst)

        # 6. prospective status score
        # Tier2 (2026-06-01, issue 1): now derived from the S13 validation-binding
        # report when one is supplied. A candidate scores 1.0 only if its
        # instance_id has a BOUND prospective experimental validation; otherwise
        # 0.0. When ``validation_binding`` is None (the default, e.g. the live S10
        # pass that runs BEFORE S13 exists) the set is empty and every candidate
        # still scores 0.0 — preserving the frozen ranking exactly. The re-run
        # driver feeds the frozen S13 binding back in to test ranking stability
        # (see codex/remediation_tier2/).
        has_prospective = iid in prospective_instance_ids
        prospective_status_score = 1.0 if has_prospective else 0.0

        # 汇总 deterministic_total_score
        audit_gate_score = (
            0.35 * descriptor_claim_coverage
            + 0.15 * citation_validity
            + 0.35 * novelty_score
            + 0.15 * (1.0 - risk)
        )
        audit_gate_score = _clamp(audit_gate_score - term_leakage_penalty + 0.05 * prospective_status_score)

        evidence_quality = _evidence_quality_score(pair_support)
        formulation_completeness = _formulation_completeness(inst)
        mechanism_fit = _mechanism_fit_score(inst, cand_descs, descriptor_claim_coverage)
        low_temperature_plausibility = _low_temperature_plausibility(inst)
        processability = _processability_score(inst)
        material_priority_score = _clamp(
            0.20 * mechanism_fit
            + 0.18 * evidence_quality
            + 0.18 * formulation_completeness
            + 0.14 * low_temperature_plausibility
            + 0.11 * processability
            + 0.05 * novelty_score
            + 0.04 * citation_validity
            + 0.10 * (1.0 - risk)
            - term_leakage_penalty
            + 0.05 * prospective_status_score
        )

        audit_rows.append({
            "instance_id": iid,
            "instance_name": cand.get("instance_name"),
            "llm_total_score": round(llm_total, 4),
            "deterministic_total_score": round(material_priority_score, 4),
            "delta_llm_vs_deterministic": round(material_priority_score - llm_total, 4),
            "audit_gate_score": round(audit_gate_score, 4),
            "material_priority_score": round(material_priority_score, 4),
            "mechanism_fit_score": round(mechanism_fit, 4),
            "evidence_quality_score": round(evidence_quality, 4),
            "formulation_completeness_score": round(formulation_completeness, 4),
            "low_temperature_plausibility_score": round(low_temperature_plausibility, 4),
            "processability_score": round(processability, 4),
            "descriptor_claim_coverage": round(descriptor_claim_coverage, 4),
            "citation_validity": round(citation_validity, 4),
            "combination_novelty": nov,
            "novelty_score": round(novelty_score, 4),
            "term_leakage_penalty": round(term_leakage_penalty, 4),
            "prospective_status_score": round(prospective_status_score, 4),
            "has_prospective_validation": bool(has_prospective),
            "risk_score": round(risk, 4),
            "bad_cited_paper_ids": bad_ids,
            "candidate_descriptor_ids": sorted(cand_descs),
            "n_candidate_descriptors": len(cand_descs),
            "n_descriptors_with_pool_support": sum(
                1 for d in cand_descs if descriptor_idx.get(d)
            ),
            "n_element_descriptor_pairs": pair_support["n_pairs"],
            "n_supported_element_descriptor_pairs": pair_support["n_supported_pairs"],
            "unsupported_element_descriptor_pairs": pair_support["unsupported_pairs"],
            "origin": inst.get("origin", "llm_selected_from_broad_pool"),
            "source_mode": inst.get("source_mode", discovery_mode),
        })

    reranked = sorted(
        audit_rows, key=lambda r: r["deterministic_total_score"], reverse=True
    )
    for i, row in enumerate(reranked, start=1):
        row["deterministic_rank"] = i
    for row in audit_rows:
        row["deterministic_rank"] = next(
            r["deterministic_rank"] for r in reranked if r["instance_id"] == row["instance_id"]
        )

    return audit_rows, reranked
