"""C4: Stage3 -> Stage1 campaign seed auto-writeback.

LEGACY / OPTIONAL (Tier1 note 2026-06-01):
    This module is NOT part of the canonical Stage3 S01->S14 pipeline and is
    not imported by ``orchestrator/pipeline.py`` or ``agents/__init__.py``.
    It is an optional V1->V2 bridge that converts a frozen Stage3 top-list
    into Stage1 BO campaign seeds. It is only invoked manually (e.g. the
    archived ``code/stage0_processing/archive/.../_run_s09b.py`` helper) and
    has no effect on the frozen Stage3 outputs / three_pillars evidence.

    KNOWN CAVEAT (do NOT use blindly): ``_DEFAULT_PARAMETERS`` below still
    mirrors the S8 sepiolite space (N in [2.5, 7.006]). That range does NOT
    match the current attapulgite AiCE campaign (N ~ [0.5, 1.3]). Before this
    bridge is wired into a real V2 campaign, the parameter space must be made
    campaign-aware. Fixing the parameter space is deferred to the V1/V2
    reconciliation work (Tier 2/3); Tier 1 only documents it to prevent misuse.

Reads
    <output_dir>/09_ranking/deterministic_reranked_top_list.json
    <output_dir>/09_ranking/ranking_robustness_v2.json    (optional)
    <output_dir>/08_material_instances/material_instances.json

and emits, for each of the top-N candidates, a Stage1-compatible
``campaign_seed.json`` plus a manifest, into:

    <output_dir>/14_campaign_seeds/<instance_id>_campaign_seed.json
    <output_dir>/14_campaign_seeds/manifest.json

The campaign seed schema is the **same** dict shape consumed by
``stage1_optimization/canonical_input/campaign_parser.py::CampaignConfig``
(campaign_name / domain_knowledge / objective / parameters), with three
non-breaking additions used only by the seed writer:

    "stage3_provenance" : { instance_id, family_id, components,
                            descriptor_claim_coverage, novelty,
                            literature_card_ids, robustness_top1_freq, ... }
    "seed_points"        : [ { "R": float, "N": float, "rationale": str } ]
    "material_system"    : str (clay/biopolymer label, human-readable)

Stage1's existing ``CampaignConfig`` ignores unknown keys (it only validates
required ones), so seeds can be fed directly without modifying Stage1.

This agent is intentionally pure / deterministic and does not call an LLM;
it just carries the Stage3 reasoning artifacts into Stage1's input slot.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


# Default AiCE parameter space (originally mirrored the S8 sepiolite campaign
# space; that campaign config has since been migrated to
# three_pillars/pillar1_transfer_agent/s8_acid_in_clay_mother_system/
# s8_sepiolite_campaign_config.json). We reuse it as the baseline shape; the
# domain_knowledge string and material_system are rewritten per-candidate.
_DEFAULT_PARAMETERS: dict[str, dict[str, Any]] = {
    "R": {
        "type": "continuous",
        "low": 0.0,
        "high": 1.041,
        "desc": "Acid/water molar ratio R = n(H3PO4)/n(H2O); controls H-bond donor:acceptor ratio.",
    },
    "N": {
        "type": "continuous",
        "low": 2.5,
        "high": 7.006,
        "desc": "Liquid/solid mass ratio N; controls acid loading inside confined pores.",
    },
}

_DEFAULT_OBJECTIVE: dict[str, Any] = {
    "target": "combined_score",
    "goal": "maximize",
    "formula": "math.log10(conductivity_room_temp_S_cm) - 3.0 * ea_high_temp_eV",
}


def _slug(name: str) -> str:
    out = []
    for ch in name.strip().lower():
        if ch.isalnum():
            out.append(ch)
        elif ch in (" ", "/", "+", "-", "_"):
            out.append("_")
    s = "".join(out).strip("_")
    while "__" in s:
        s = s.replace("__", "_")
    return s or "candidate"


def _safe_load(p: Path) -> Optional[dict]:
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        logger.warning("[s09b] failed to load %s: %s", p, e)
        return None


def _index_instances(instances: list[dict]) -> dict[str, dict]:
    return {i.get("instance_id"): i for i in instances if i.get("instance_id")}


def _index_robustness(robust: Optional[dict]) -> dict[str, dict]:
    if not robust:
        return {}
    out: dict[str, dict] = {}
    for r in robust.get("per_candidate") or []:
        iid = r.get("instance_id")
        if iid:
            out[iid] = r
    return out


def _build_domain_knowledge(
    *, instance: dict, ranking_row: dict, robustness_row: Optional[dict]
) -> str:
    """Carry Stage3 reasoning provenance into the domain_knowledge string
    that Stage1's planner_prompts will read."""
    name = instance.get("instance_name", ranking_row.get("instance_name", ""))
    components = instance.get("components") or []
    novelty = ranking_row.get("combination_novelty") or instance.get("combination_novelty")
    expected = instance.get("expected_properties") or []
    rationale = (instance.get("novelty_rationale") or "").strip()

    nov_line = f"Combination novelty: {novelty}." if novelty else ""
    exp_line = ("Stage3-expected envelope: " + "; ".join(expected) + ".") if expected else ""
    rob_line = ""
    if robustness_row:
        rob_line = (
            f"Stage3 ranking robustness (200-seed weight+score perturbation): "
            f"top1_freq={robustness_row.get('top1_freq')}, "
            f"top3_freq={robustness_row.get('top3_freq')}, "
            f"mean_rank={robustness_row.get('mean_rank')}, "
            f"std_rank={robustness_row.get('std_rank')}."
        )

    parts = [
        "[Stage3 -> Stage1 campaign seed]",
        f"Material system: {name}",
        f"Components: {', '.join(components) if components else '(unspecified)'}",
        nov_line,
        exp_line,
        rob_line,
        "Stage3 novelty rationale:",
        rationale,
        "",
        "Stage1 task: optimise R (acid/water molar ratio) and N (liquid/solid mass "
        "ratio) for this composition. The seed_points field carries Stage3-derived "
        "starting recipes; treat them as cold-start anchors, not as ground truth.",
    ]
    return "\n".join([p for p in parts if p])


def _seed_points_for_instance(instance: dict) -> list[dict]:
    """Heuristic cold-start seeds. Stage3 doesn't predict R/N numerically, so
    we anchor at the design space midpoint plus one diversification point.
    Rationale string makes the heuristic auditable."""
    R_mid = round((_DEFAULT_PARAMETERS["R"]["low"] + _DEFAULT_PARAMETERS["R"]["high"]) / 2, 3)
    N_mid = round((_DEFAULT_PARAMETERS["N"]["low"] + _DEFAULT_PARAMETERS["N"]["high"]) / 2, 3)
    R_lo = round(_DEFAULT_PARAMETERS["R"]["low"] + 0.20 * (_DEFAULT_PARAMETERS["R"]["high"] - _DEFAULT_PARAMETERS["R"]["low"]), 3)
    N_lo = round(_DEFAULT_PARAMETERS["N"]["low"] + 0.20 * (_DEFAULT_PARAMETERS["N"]["high"] - _DEFAULT_PARAMETERS["N"]["low"]), 3)
    return [
        {
            "R": R_mid,
            "N": N_mid,
            "rationale": (
                "Design-space midpoint cold start. No Stage3 numerical R/N prior; "
                "let BO acquisition explore from the centroid."
            ),
        },
        {
            "R": R_lo,
            "N": N_lo,
            "rationale": (
                "Strong-confinement / low-acid corner. Per Stage3 mechanism card, "
                "low-N keeps acid inside nanopores and minimises low-T Ea risk."
            ),
        },
    ]


def _build_seed_for_candidate(
    *,
    instance: dict,
    ranking_row: dict,
    robustness_row: Optional[dict],
    discovery_mode: str,
) -> dict:
    iid = ranking_row.get("instance_id") or instance.get("instance_id")
    name = ranking_row.get("instance_name") or instance.get("instance_name") or iid
    campaign_name = f"Stage3Seed_{iid}_{_slug(name)}"

    return {
        "campaign_name": campaign_name,
        "material_system": name,
        "domain_knowledge": _build_domain_knowledge(
            instance=instance, ranking_row=ranking_row, robustness_row=robustness_row
        ),
        "objective": dict(_DEFAULT_OBJECTIVE),
        "parameters": {k: dict(v) for k, v in _DEFAULT_PARAMETERS.items()},
        "seed_points": _seed_points_for_instance(instance),
        "stage3_provenance": {
            "instance_id": iid,
            "family_id": instance.get("family_id"),
            "components": instance.get("components"),
            "combination_novelty": ranking_row.get("combination_novelty")
            or instance.get("combination_novelty"),
            "literature_support_card_ids": instance.get("literature_support_card_ids") or [],
            "design_principle_ids": instance.get("design_principle_ids") or [],
            "deterministic_rank": ranking_row.get("deterministic_rank"),
            "deterministic_total_score": ranking_row.get("deterministic_total_score"),
            "llm_total_score": ranking_row.get("llm_total_score"),
            "descriptor_claim_coverage": ranking_row.get("descriptor_claim_coverage"),
            "citation_validity": ranking_row.get("citation_validity"),
            "term_leakage_penalty": ranking_row.get("term_leakage_penalty"),
            "robustness_top1_freq": (robustness_row or {}).get("top1_freq"),
            "robustness_top3_freq": (robustness_row or {}).get("top3_freq"),
            "robustness_mean_rank": (robustness_row or {}).get("mean_rank"),
            "robustness_std_rank": (robustness_row or {}).get("std_rank"),
            "discovery_mode": discovery_mode,
            "origin": instance.get("origin", "llm_selected_from_broad_pool"),
        },
    }


def run_s09b(
    *,
    output_dir: Path,
    top_n: int = 5,
    discovery_mode: str = "broad_literature_pool_selection",
) -> dict:
    """Generate Stage1 campaign seeds for the top-N Stage3 candidates.

    Returns the manifest dict (also written to JSON).
    """
    ranking = _safe_load(output_dir / "09_ranking" / "deterministic_reranked_top_list.json")
    if ranking is None:
        # Fallback to LLM ranking if deterministic rerank wasn't produced.
        ranking = _safe_load(output_dir / "09_ranking" / "ranked_top_list.json")
    if ranking is None:
        raise FileNotFoundError("No ranking file found in 09_ranking/.")

    instances_doc = _safe_load(output_dir / "08_material_instances" / "material_instances.json")
    if instances_doc is None:
        raise FileNotFoundError("material_instances.json not found.")

    robustness = _safe_load(output_dir / "09_ranking" / "ranking_robustness_v2.json")

    inst_index = _index_instances(instances_doc.get("instances") or [])
    rob_index = _index_robustness(robustness)

    ranked_rows = ranking.get("ranked") or ranking.get("ranked_candidates") or []
    rank_key = "deterministic_rank" if "deterministic_rank" in (ranked_rows[0] if ranked_rows else {}) else "rank"
    ranked_rows_sorted = sorted(ranked_rows, key=lambda r: r.get(rank_key, 999))[:top_n]

    out_root = output_dir / "14_campaign_seeds"
    out_root.mkdir(parents=True, exist_ok=True)

    seed_records: list[dict] = []
    for row in ranked_rows_sorted:
        iid = row.get("instance_id")
        inst = inst_index.get(iid)
        if inst is None:
            logger.warning("[s09b] instance_id=%s not in material_instances.json; skipping", iid)
            continue
        seed = _build_seed_for_candidate(
            instance=inst,
            ranking_row=row,
            robustness_row=rob_index.get(iid),
            discovery_mode=discovery_mode,
        )
        fname = f"{iid}_{_slug(seed['material_system'])}_campaign_seed.json"
        fpath = out_root / fname
        fpath.write_text(json.dumps(seed, ensure_ascii=False, indent=2), encoding="utf-8")
        seed_records.append(
            {
                "instance_id": iid,
                "deterministic_rank": row.get(rank_key),
                "deterministic_total_score": row.get("deterministic_total_score"),
                "material_system": seed["material_system"],
                "campaign_name": seed["campaign_name"],
                "seed_path": str(fpath.relative_to(output_dir.parent.parent)).replace("\\", "/"),
                "n_seed_points": len(seed["seed_points"]),
                "robustness_top1_freq": (rob_index.get(iid) or {}).get("top1_freq"),
            }
        )

    manifest = {
        "step_id": "s09b_top_list_to_campaign_seed",
        "n_candidates": len(seed_records),
        "top_n_requested": top_n,
        "discovery_mode": discovery_mode,
        "ranking_source": (
            "deterministic_reranked_top_list.json"
            if (output_dir / "09_ranking" / "deterministic_reranked_top_list.json").exists()
            else "ranked_top_list.json"
        ),
        "robustness_source": (
            "ranking_robustness_v2.json"
            if (output_dir / "09_ranking" / "ranking_robustness_v2.json").exists()
            else None
        ),
        "stage1_compatibility": {
            "validated_against": "stage1_optimization/canonical_input/campaign_parser.py::CampaignConfig",
            "required_fields_present": ["campaign_name", "objective", "parameters"],
            "extra_fields_carried": ["material_system", "seed_points", "stage3_provenance"],
            "note": "CampaignConfig ignores unknown top-level keys; seed_points is "
            "consumed by Stage1's BO cold-start when the seeds_loader is enabled.",
        },
        "seeds": seed_records,
    }
    (out_root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    logger.info("[s09b] wrote %d campaign seeds to %s", len(seed_records), out_root)
    return manifest

