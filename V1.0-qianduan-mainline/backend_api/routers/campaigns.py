# -*- coding: utf-8 -*-
"""Campaign-centric routes — read-only thin wrappers over Stage1 JSON files.

These power the Campaign Dashboard (paper §6.1 / frontend_redesign §3.1) by
exposing the four Stage1 evidence sources as REST endpoints:

  - campaigns/<name>.json                 -> campaign meta (goal, bounds, knowledge)
  - campaign storage.history_db           -> trials[]
  - campaign storage.output_dir/next_experiment_recipe.json
                                           -> the LLM-vs-BO recommendation card
  - campaign storage.output_dir/closed_loop_metrics.json
                                           -> campaign health bar

The router never mutates Stage1 state; the closed-loop runner is the only
writer. This keeps the UI layer faithful to the on-disk source of truth and
makes every dashboard pixel reproducible.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

router = APIRouter()
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
STAGE1_DIR = PROJECT_ROOT / "stage1_optimization"

_CAMPAIGNS_DIR = STAGE1_DIR / "campaigns"
_MEMORY_DIR = STAGE1_DIR / "campaign_memory"
_OUTPUT_DIR = STAGE1_DIR / "output"

# Campaign names live in JSON files under campaigns/. Allow only filename-safe
# tokens (letters / digits / underscore / hyphen / dot). The campaign_name field
# inside the JSON itself can be richer, but the URL identifier is the slug.
_NAME_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


def _safe_name(name: str) -> str:
    if not name or not _NAME_RE.match(name):
        raise HTTPException(400, "Invalid campaign name")
    return name


def _load_json(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to parse %s: %s", path, exc)
        return None


def _list_campaign_files() -> List[Path]:
    if not _CAMPAIGNS_DIR.exists():
        return []
    return sorted(p for p in _CAMPAIGNS_DIR.glob("*.json") if p.is_file())


def _resolve_campaign_path(name: str) -> Path:
    name = _safe_name(name)
    candidate = (_CAMPAIGNS_DIR / f"{name}.json").resolve()
    try:
        if not candidate.is_relative_to(_CAMPAIGNS_DIR.resolve()):
            raise HTTPException(400, "Path traversal rejected")
    except ValueError:
        raise HTTPException(400, "Path traversal rejected")
    if not candidate.exists():
        raise HTTPException(404, f"Campaign {name} not found")
    return candidate


def _campaign_meta_summary(meta: Dict[str, Any]) -> Dict[str, Any]:
    """Trim the on-disk campaign config to a UI-friendly shape."""
    objective = meta.get("objective") or {}
    parameters = meta.get("parameters") or {}
    bounds = {
        k: {"low": v.get("low"), "high": v.get("high"), "type": v.get("type"), "desc": v.get("desc")}
        for k, v in parameters.items()
        if isinstance(v, dict)
    }
    return {
        "campaign_name": meta.get("campaign_name"),
        "objective": {
            "target": objective.get("target"),
            "goal": objective.get("goal"),
            "formula": objective.get("formula"),
        },
        "bounds": bounds,
        "parameter_names": list(bounds.keys()),
        "domain_knowledge": meta.get("domain_knowledge"),
        "storage": meta.get("storage") or {},
    }


def _resolve_storage_path(raw: Optional[str], default: Path, base: Path = STAGE1_DIR) -> Path:
    """Resolve campaign-scoped storage paths while rejecting traversal."""
    if not raw:
        return default
    path = Path(raw)
    candidate = path if path.is_absolute() else base / path
    candidate = candidate.resolve()
    try:
        if not candidate.is_relative_to(base.resolve()):
            raise HTTPException(400, "Campaign storage path traversal rejected")
    except ValueError:
        raise HTTPException(400, "Campaign storage path traversal rejected")
    return candidate


def _campaign_storage(name: str) -> Dict[str, Path]:
    """Return history/output paths for a campaign, falling back to legacy S8 paths."""
    path = _resolve_campaign_path(name)
    meta = _load_json(path) or {}
    storage = meta.get("storage") or {}
    output_dir = _resolve_storage_path(
        storage.get("output_dir"),
        _OUTPUT_DIR,
    )
    history_db = _resolve_storage_path(
        storage.get("history_db"),
        _MEMORY_DIR / "history_db_attapulgite.json",
    )
    return {
        "history_db": history_db,
        "output_dir": output_dir,
        "next_recipe": output_dir / "next_experiment_recipe.json",
        "metrics": output_dir / "closed_loop_metrics.json",
    }


def _same_resolved_path(left: Optional[str], right: Path) -> bool:
    if not left:
        return False
    try:
        return Path(left).resolve() == right.resolve()
    except Exception:  # noqa: BLE001
        return False


def _next_recipe_schema_diagnostics(
    recipe: Dict[str, Any],
    paths: Dict[str, Path],
) -> Dict[str, Any]:
    """Validate the current Stage1 recommendation wrapper without mutating it."""
    warnings: List[str] = []
    required_root_keys = [
        "schema_version",
        "artifact_type",
        "created_at",
        "campaign_name",
        "campaign_config",
        "source_mode",
        "source_tag",
        "history_db",
        "input_bundle_hash",
        "recipe",
        "optimizer_suggestion",
        "optimizer_vs_llm_delta",
        "safety_box",
    ]
    missing = [k for k in required_root_keys if k not in recipe]
    if missing:
        warnings.append(f"missing_root_fields:{','.join(missing)}")
    schema_version = recipe.get("schema_version")
    artifact_type = recipe.get("artifact_type")
    if schema_version != "0.2.0":
        warnings.append(f"unexpected_schema_version:{schema_version or 'missing'}")
    if artifact_type != "stage1_next_experiment_recipe":
        warnings.append(f"unexpected_artifact_type:{artifact_type or 'missing'}")
    if not isinstance(recipe.get("recipe"), dict):
        warnings.append("recipe_payload_not_object")
    else:
        rec = recipe.get("recipe") or {}
        params = rec.get("recommended_parameters") or {}
        if params.get("R") is None or params.get("N") is None:
            warnings.append("recommended_parameters_missing_R_or_N")
    if not isinstance(recipe.get("optimizer_suggestion"), dict):
        warnings.append("optimizer_suggestion_not_object")
    history_db = recipe.get("history_db")
    if history_db and not _same_resolved_path(str(history_db), paths["history_db"]):
        warnings.append(
            "history_db_path_mismatch:"
            f"recipe={history_db};campaign={paths['history_db']}"
        )
    return {
        "schema_valid": not warnings,
        "schema_warnings": warnings,
        "schema_version": schema_version,
        "artifact_type": artifact_type,
    }


def _trials_payload(history: Dict[str, Any]) -> Dict[str, Any]:
    trials = history.get("trials") or []
    # Compute Pareto front on (sigma_RT max, ea_low_temp_eV min) for the dashboard.
    pareto_ids: List[int] = []
    pts: List[tuple[int, float, float]] = []
    for t in trials:
        obj = t.get("objectives") or {}
        sigma = obj.get("conductivity_room_temp_S_cm")
        ea_low = obj.get("ea_low_temp_eV")
        if sigma is None or ea_low is None:
            continue
        try:
            pts.append((int(t.get("trial_id")), float(sigma), float(ea_low)))
        except (TypeError, ValueError):
            continue
    for i, (tid, s_i, e_i) in enumerate(pts):
        dominated = False
        for j, (_, s_j, e_j) in enumerate(pts):
            if j == i:
                continue
            # j dominates i if it is at least as good on both axes and strictly better on one.
            if s_j >= s_i and e_j <= e_i and (s_j > s_i or e_j < e_i):
                dominated = True
                break
        if not dominated:
            pareto_ids.append(tid)
    return {
        "campaign_name": history.get("campaign_name"),
        "n_trials": len(trials),
        "trials": trials,
        "pareto_trial_ids": pareto_ids,
    }


def _health_payload(metrics: Dict[str, Any], history: Dict[str, Any]) -> Dict[str, Any]:
    """Build the /campaigns/{name}/health payload.

    *Live history is the source of truth.* ``closed_loop_metrics.json`` is just
    a cache produced by the **previous** ``run_optimization_loop.py`` run, so
    when history has been edited / rebuilt out-of-band (e.g. manual ingestion
    of cold-start trials), the cached numbers (best score, best R/N, trial
    count) can drift wildly from reality.

    Strategy:
    * If ``metrics.n_history_trials`` mismatches ``len(history.trials)``, mark
      the cached metrics as **stale** and ignore all numeric fields that the
      live history can recompute (best score, best R/N, σ_RT@best).
    * Always recompute ``best_score_overall`` + ``best_candidate_R/N`` +
      ``best_final_sigma_299K_S_cm`` from the actual trial list when possible.
    * Closed-loop rounds count + validity + limitations stay from metrics
      because they describe meta-info no history alone can reconstruct, but
      are flagged as stale in the response so the UI can warn.
    """
    trials = history.get("trials") or []
    n_trials = len(trials)
    scores = [
        (t.get("objectives") or {}).get("combined_score")
        for t in trials
        if (t.get("objectives") or {}).get("combined_score") is not None
    ]
    best_score = max(scores) if scores else None
    last_5_std = None
    if len(scores) >= 5:
        last5 = scores[-5:]
        m = sum(last5) / 5.0
        last_5_std = (sum((s - m) ** 2 for s in last5) / 5.0) ** 0.5

    # Identify the live "best" trial (R/N/σ) from history rather than the
    # cached metrics — this is what powers the "best R / N" card.
    best_trial = None
    if scores and trials:
        best_value = best_score
        for t in trials:
            obj = t.get("objectives") or {}
            if obj.get("combined_score") == best_value:
                best_trial = t
                break
    live_best_R = (best_trial or {}).get("parameters", {}).get("R") if best_trial else None
    live_best_N = (best_trial or {}).get("parameters", {}).get("N") if best_trial else None
    live_best_sigma = (
        (best_trial or {}).get("objectives", {}).get("conductivity_room_temp_S_cm")
        if best_trial
        else None
    )

    cached_n_trials = metrics.get("n_history_trials")
    stale = bool(metrics) and cached_n_trials is not None and cached_n_trials != n_trials
    limitations = list(metrics.get("limitations") or [])
    if stale:
        limitations.insert(
            0,
            (
                f"⚠️ closed_loop_metrics.json 缓存与 history_db 不一致 "
                f"(cached n_history_trials={cached_n_trials}, live={n_trials})。"
                "已在响应中以 history 为准；下次 run_optimization_loop.py 会覆盖缓存。"
            ),
        )

    def _pick(metrics_value, live_value):
        """If cache is stale, drop the cached numeric and prefer live."""
        if stale:
            return live_value
        return metrics_value if metrics_value is not None else live_value

    return {
        "campaign_name": metrics.get("campaign_name") or history.get("campaign_name"),
        "n_history_trials": n_trials,
        "n_closed_loop_rounds": metrics.get("n_closed_loop_rounds") if not stale else 0,
        "best_initial_score": metrics.get("best_initial_score") if not stale else None,
        "best_final_score": _pick(metrics.get("best_final_score"), best_score),
        "absolute_improvement": metrics.get("absolute_improvement") if not stale else None,
        "best_initial_sigma_299K_S_cm": metrics.get("best_initial_sigma_299K_S_cm") if not stale else None,
        "best_final_sigma_299K_S_cm": _pick(metrics.get("best_final_sigma_299K_S_cm"), live_best_sigma),
        "best_candidate_R": _pick(metrics.get("best_candidate_R"), live_best_R),
        "best_candidate_N": _pick(metrics.get("best_candidate_N"), live_best_N),
        "closed_loop_validity": metrics.get("closed_loop_validity"),
        "human_intervention_level": metrics.get("human_intervention_level"),
        "limitations": limitations,
        "last_5_score_std": last_5_std,
        "best_score_overall": best_score,
        "generated_at": metrics.get("generated_at"),
        "metrics_stale": stale,
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


class CampaignListResponse(BaseModel):
    campaigns: List[Dict[str, Any]]
    total: int


@router.get("", response_model=CampaignListResponse)
def list_campaigns(limit: int = Query(50, ge=1, le=500)):
    """List all known campaigns by slug + display name."""
    rows: List[Dict[str, Any]] = []
    for p in _list_campaign_files():
        meta = _load_json(p) or {}
        rows.append(
            {
                "slug": p.stem,
                "campaign_name": meta.get("campaign_name") or p.stem,
                "objective_target": (meta.get("objective") or {}).get("target"),
                "objective_goal": (meta.get("objective") or {}).get("goal"),
                "parameters": list((meta.get("parameters") or {}).keys()),
            }
        )
    return CampaignListResponse(campaigns=rows[:limit], total=len(rows))


@router.get("/{name}")
def get_campaign(name: str):
    """Campaign meta — goal formula, bounds, domain knowledge."""
    path = _resolve_campaign_path(name)
    meta = _load_json(path)
    if meta is None:
        raise HTTPException(500, f"Campaign {name} unreadable")
    return _campaign_meta_summary(meta)


@router.get("/{name}/trials")
def get_trials(name: str):
    """Historical trials list + Pareto subset for the dashboard scatter."""
    paths = _campaign_storage(name)
    history = _load_json(paths["history_db"])
    if history is None:
        return {"campaign_name": name, "n_trials": 0, "trials": [], "pareto_trial_ids": []}
    return _trials_payload(history)


@router.get("/{name}/next-recipe")
def get_next_recipe(name: str):
    """The LLM-vs-BO Recipe Card payload — pass-through plus a small safety wrapper."""
    paths = _campaign_storage(name)
    recipe = _load_json(paths["next_recipe"])
    if recipe is None:
        raise HTTPException(404, f"{paths['next_recipe'].name} not generated yet")
    diagnostics = _next_recipe_schema_diagnostics(recipe, paths)
    return {
        "requested_campaign": name,
        "recipe": recipe,
        **diagnostics,
        "history_db": str(paths["history_db"]),
        "output_dir": str(paths["output_dir"]),
        "next_recipe_path": str(paths["next_recipe"]),
    }


@router.get("/{name}/health")
def get_health(name: str):
    """Closed-loop health bar payload (best score, convergence, limitations)."""
    paths = _campaign_storage(name)
    metrics = _load_json(paths["metrics"]) or {}
    history = _load_json(paths["history_db"]) or {}
    return _health_payload(metrics, history)


@router.get("/{name}/termination")
def get_termination(name: str):
    """Termination v3 evaluation — A/B/C/D quadrants live from history + rounds.

    不依赖 closed_loop_metrics.json 缓存，每次调用即时计算，确保前端面板与
    history_db / closed_loop_rounds 实时一致。
    """
    path = _resolve_campaign_path(name)
    meta = _load_json(path) or {}
    paths = _campaign_storage(name)
    history = _load_json(paths["history_db"]) or {"trials": []}

    try:
        from stage1_optimization.closed_loop import evaluate_termination
    except ImportError:
        import sys
        sys.path.insert(0, str(STAGE1_DIR))
        from closed_loop import evaluate_termination  # type: ignore

    payload = evaluate_termination(
        campaign_config=meta,
        history=history,
        output_dir=paths["output_dir"],
    )
    payload["campaign_name"] = meta.get("campaign_name") or name
    payload["slug"] = name
    return payload


@router.get("/{name}/stage1-readiness")
def get_stage1_readiness(name: str, cold_start_threshold: int = Query(5, ge=1, le=50)):
    """Stage1 BO readiness panel for the experiment-control UI.

    Tells the frontend whether enough distinct (R, N) recipes have been
    accumulated to leave the cold-start regime and run a real GP+EI round.
    Mirrors ``MemoryManager.count_distinct_parameter_sets`` (round to 3 dp).
    """
    path = _resolve_campaign_path(name)
    meta = _load_json(path) or {}
    paths = _campaign_storage(name)
    history = _load_json(paths["history_db"]) or {"trials": []}
    trials = history.get("trials") or []

    param_keys = list((meta.get("parameters") or {}).keys())
    seen: set = set()
    for t in trials:
        params = t.get("parameters") or {}
        try:
            key = tuple(round(float(params[k]), 3) for k in param_keys)
        except (KeyError, TypeError, ValueError):
            continue
        seen.add(key)
    n_distinct = len(seen)
    next_mode = "bayesian" if n_distinct >= cold_start_threshold else "cold_start"
    return {
        "campaign_name": meta.get("campaign_name") or name,
        "slug": name,
        "parameters": param_keys,
        "n_trials_total": len(trials),
        "n_distinct_recipes": n_distinct,
        "cold_start_threshold": cold_start_threshold,
        "next_mode": next_mode,
        "stage1_ready": next_mode == "bayesian",
        "history_db": str(paths["history_db"]),
        "output_dir": str(paths["output_dir"]),
    }
