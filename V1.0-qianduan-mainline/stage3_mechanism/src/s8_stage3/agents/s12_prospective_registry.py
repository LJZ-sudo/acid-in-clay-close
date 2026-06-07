from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from s8_stage3.config.prompt_registry import prompt_manifest
from s8_stage3.contracts.discovery import ALLOWED_CLAIM_BY_MODE, FORBIDDEN_CLAIM_BY_MODE
from s8_stage3.contracts.material import MaterialInstanceSet
from s8_stage3.contracts.prospective import ProspectiveCandidate, ProspectiveCandidateRegistry
from s8_stage3.contracts.ranking import RankingResult
from s8_stage3.io.writers import write_json


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _short_run_id(seed: str) -> str:
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:10]


def _stable_run_seed(
    discovery_mode: str,
    ranking: "RankingResult",
    instance_set: "MaterialInstanceSet",
    top_n: int,
) -> str:
    """Content-addressed seed for a reproducible run_id (Tier2, instance-id drift).

    Built ONLY from stable candidate content (discovery_mode + the ranked
    instance_ids/names + their components), never from wall-clock time or the
    output directory path. Re-running the same candidates into a different dir at
    a different time therefore yields the SAME run_id / candidate_id, so the frozen
    registry, the S13 validation binding, and any re-run stay aligned.
    """
    inst_by_id = {inst.instance_id: inst for inst in instance_set.instances}
    rows = []
    for ranked in ranking.ranked_candidates[: max(0, top_n)]:
        inst = inst_by_id.get(ranked.instance_id)
        rows.append({
            "instance_id": ranked.instance_id,
            "instance_name": ranked.instance_name,
            "components": sorted(list(inst.components)) if inst else [],
        })
    payload = json.dumps(
        {"discovery_mode": discovery_mode, "top_n": top_n, "candidates": rows},
        sort_keys=True,
        ensure_ascii=False,
    )
    return payload


def _collect_output_hashes(output_dir: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for path in sorted(output_dir.rglob("*.json")):
        try:
            rel = str(path.relative_to(output_dir)).replace("\\", "/")
            hashes[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
        except Exception:
            continue
    return hashes


def _registry_hash(candidates: list[ProspectiveCandidate]) -> str:
    payload = json.dumps([c.model_dump(mode="json") for c in candidates], sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def run_s12(
    ranking: RankingResult,
    instance_set: MaterialInstanceSet,
    output_dir: Path,
    settings,
    *,
    top_n: int = 5,
    force_reset: bool = False,
    stable_run_id: Optional[bool] = None,
) -> ProspectiveCandidateRegistry:
    registry_path = output_dir / "11_candidate_registry" / "prospective_candidates.json"
    if registry_path.exists() and not force_reset:
        return ProspectiveCandidateRegistry.model_validate(json.loads(registry_path.read_text(encoding="utf-8")))
    if registry_path.exists() and force_reset:
        backup = registry_path.with_suffix(f".backup_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json")
        shutil.copy2(registry_path, backup)

    timestamp = _utcnow_iso()
    discovery_mode = str(getattr(settings, "discovery_mode", "broad_literature_pool_selection"))

    # Tier2 (instance-id drift): opt-in content-addressed run_id. Default keeps the
    # legacy path+time-seeded id so the frozen registry/run_id is unchanged; when
    # enabled (param / settings.stable_run_id / env STAGE3_STABLE_RUN_ID=1) the
    # run_id (and thus candidate_id) is reproducible across runs and directories.
    if stable_run_id is None:
        import os as _os
        stable_run_id = bool(getattr(settings, "stable_run_id", False)) or _os.getenv(
            "STAGE3_STABLE_RUN_ID", ""
        ).strip() in {"1", "true", "True"}
    if stable_run_id:
        run_id = "stage3-" + _short_run_id(
            _stable_run_seed(discovery_mode, ranking, instance_set, top_n)
        )
    else:
        run_id = "stage3-" + _short_run_id(str(output_dir.resolve()) + timestamp)
    instance_by_id = {inst.instance_id: inst for inst in instance_set.instances}
    output_hashes = _collect_output_hashes(output_dir)
    prompt_hashes = {
        row["name"]: row["sha256"]
        for row in prompt_manifest()
        if row.get("name") in {"s09_family_generator", "s10_instance_ranker"}
    }
    snapshot = {
        "llm_mode": str(getattr(settings, "llm_mode", "")),
        "model_tier": str(getattr(settings, "model_tier", "")),
        "discovery_mode": discovery_mode,
        "final_audit": str(getattr(settings, "final_audit", False)),
        "enable_cache": str(getattr(settings, "enable_cache", "")),
    }

    candidates: list[ProspectiveCandidate] = []
    for idx, ranked in enumerate(ranking.ranked_candidates[: max(0, top_n)], start=1):
        inst = instance_by_id.get(ranked.instance_id)
        candidates.append(
            ProspectiveCandidate(
                candidate_id=f"PC-{run_id[-10:]}-{idx}",
                instance_id=ranked.instance_id,
                instance_name=ranked.instance_name,
                origin=(getattr(inst, "origin", "") if inst else "") or "llm_selected_from_broad_pool",
                discovery_mode=discovery_mode,
                rank_before_experiment=ranked.rank,
                score_before_experiment=ranked.total_score,
                combination_novelty=ranked.combination_novelty,
                components=list(inst.components) if inst else [],
                composition_description=inst.composition_description if inst else "",
                design_principle_ids=list(inst.design_principle_ids) if inst else [],
                descriptor_ids=sorted(
                    {
                        str(did)
                        for ev in (inst.element_evidence if inst else [])
                        for did in ev.descriptor_satisfied
                    }
                ),
                evidence_card_ids=[],
                literature_card_ids=list(ranked.literature_support_card_ids),
                source_run_id=run_id,
                preregistered_at=timestamp,
                prompt_hashes=prompt_hashes,
                input_hashes={},
                output_hashes=output_hashes,
                settings_snapshot=snapshot,
                allowed_claim=ALLOWED_CLAIM_BY_MODE.get(discovery_mode, ""),
                forbidden_claim=FORBIDDEN_CLAIM_BY_MODE.get(discovery_mode, ""),
            )
        )

    registry = ProspectiveCandidateRegistry(
        run_id=run_id,
        preregistered_at=timestamp,
        discovery_mode=discovery_mode,
        top_n=top_n,
        n_candidates=len(candidates),
        candidates=candidates,
        registry_hash=_registry_hash(candidates),
        notes="Frozen prospective registry. S13 writes append-only validation links separately.",
    )
    write_json(registry_path, registry)
    return registry
