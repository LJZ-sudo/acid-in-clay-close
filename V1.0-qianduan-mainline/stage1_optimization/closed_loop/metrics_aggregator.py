"""聚合所有 round_NNN_*.json + history_db 生成 closed_loop_metrics.json (P-Stage1-B)。

closed_loop_validity 规则：
    - 任意一轮 source_mode == "real"  → "prospective_real"
    - 否则若任意一轮 source_mode == "virtual_oracle" → "virtual_oracle_only"
    - 否则                                                 → "retrospective_replay"

best_initial_*  = history 中前 n_initial_points 轮的最优值
best_final_*    = history 中所有轮的最优值
"""

from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROUND_DIR_NAME = "closed_loop_rounds"
SUGGESTION_RE = re.compile(r"^round_(\d{3,})_suggestion\.json$")
STAGE0_RE = re.compile(r"^round_(\d{3,})_stage0_result\.json$")


def _read_json(p: Path) -> Optional[dict]:
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _classify_validity(source_modes: List[str]) -> str:
    if any(m == "real" for m in source_modes):
        return "prospective_real"
    if any(m == "virtual_oracle" for m in source_modes):
        return "virtual_oracle_only"
    return "retrospective_replay"


def _safe_max_min(values: List[float], goal: str) -> Optional[float]:
    if not values:
        return None
    return max(values) if goal == "maximize" else min(values)


def _is_finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not (
        isinstance(value, float) and math.isnan(value)
    )


def _is_bo_suggestion(suggestion: Dict[str, Any]) -> bool:
    """Return True when a round used a trained BO model rather than cold-start.

    Older round files may store `optimization_mode`; current files store
    `cold_start`. Support both so metrics do not undercount real BO suggestions.
    """
    provenance = suggestion.get("bo_provenance") or {}
    mode = provenance.get("optimization_mode")
    if mode is not None:
        return str(mode) != "cold_start"
    if "cold_start" in provenance:
        return provenance.get("cold_start") is False
    n_train = provenance.get("n_train_points") or provenance.get("history_count")
    threshold = provenance.get("cold_start_threshold")
    if _is_finite_number(n_train) and _is_finite_number(threshold):
        return float(n_train) >= float(threshold)
    return False


def _is_llm_adjusted(suggestion: Dict[str, Any]) -> bool:
    delta = suggestion.get("optimizer_vs_llm_delta") or {}
    if delta.get("adjusted") is True:
        return True
    parameters = delta.get("parameters") or {}
    return any(
        isinstance(v, dict) and v.get("status") == "adjusted"
        for v in parameters.values()
    )


def _best_trial_pair(
    pairs: List[tuple[Dict[str, Any], float]],
    goal: str,
) -> Optional[tuple[Dict[str, Any], float]]:
    if not pairs:
        return None
    if goal == "maximize":
        return max(pairs, key=lambda item: item[1])
    return min(pairs, key=lambda item: item[1])


def build_closed_loop_metrics(
    output_dir: Path,
    history_db_path: Optional[Path] = None,
    n_initial_points: int = 3,
    objective_target: str = "combined_score",
    objective_goal: str = "maximize",
    campaign_name: Optional[str] = None,
    campaign_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """读取 closed_loop_rounds/ + history_db.json，写出 closed_loop_metrics.json。"""

    output_dir = Path(output_dir)
    rounds_dir = output_dir / ROUND_DIR_NAME

    suggestion_files = sorted(rounds_dir.glob("round_*_suggestion.json")) if rounds_dir.exists() else []
    stage0_files = sorted(rounds_dir.glob("round_*_stage0_result.json")) if rounds_dir.exists() else []

    suggestions = [s for s in (_read_json(p) for p in suggestion_files) if s]
    stage0_records = [s for s in (_read_json(p) for p in stage0_files) if s]

    source_modes = [s.get("source_mode", "replay") for s in suggestions]
    validity = _classify_validity(source_modes)

    bo_count = sum(1 for s in suggestions if _is_bo_suggestion(s))
    llm_adjusted_count = sum(1 for s in suggestions if _is_llm_adjusted(s))

    # history-based metrics
    history_db_path = (
        Path(history_db_path)
        if history_db_path
        else Path(__file__).resolve().parent.parent / "campaign_memory" / "history_db_attapulgite.json"
    )
    history_data = _read_json(history_db_path) or {}
    trials: List[Dict[str, Any]] = list(history_data.get("trials") or [])
    if campaign_name is None:
        campaign_name = history_data.get("campaign_name")

    valid_objective_pairs: List[tuple[Dict[str, Any], float]] = []
    for t in trials:
        v = (t.get("objectives") or {}).get(objective_target)
        if _is_finite_number(v):
            valid_objective_pairs.append((t, float(v)))

    initial_pairs = valid_objective_pairs[:n_initial_points]
    best_initial_pair = _best_trial_pair(initial_pairs, objective_goal)
    best_final_pair = _best_trial_pair(valid_objective_pairs, objective_goal)
    best_initial = best_initial_pair[1] if best_initial_pair else None
    best_final = best_final_pair[1] if best_final_pair else None

    abs_improvement: Optional[float] = None
    if best_initial is not None and best_final is not None:
        abs_improvement = (
            best_final - best_initial if objective_goal == "maximize" else best_initial - best_final
        )

    # find best trial parameters
    best_R = best_N = None
    best_sigma_initial = best_sigma_final = None
    if best_final_pair:
        best_trial = best_final_pair[0]
        params = best_trial.get("parameters") or {}
        best_R = params.get("R")
        best_N = params.get("N")
        best_sigma_final = (best_trial.get("objectives") or {}).get("conductivity_room_temp_S_cm")
    if best_initial_pair:
        best_sigma_initial = (
            (best_initial_pair[0].get("objectives") or {}).get("conductivity_room_temp_S_cm")
        )

    suggestion_hashes = {
        s.get("suggestion_hash") for s in suggestions if s.get("suggestion_hash")
    }
    measured_after_hashes = [
        r.get("measured_after_suggestion_hash")
        for r in stage0_records
        if r.get("measured_after_suggestion_hash")
    ]
    n_suggestions_measured = sum(1 for h in measured_after_hashes if h in suggestion_hashes)
    geometry_repairs = []
    for t in trials:
        meta = t.get("metadata") or {}
        repair = meta.get("thickness_repair") or {}
        if repair.get("applied"):
            geometry_repairs.append(
                {
                    "trial_id": t.get("trial_id"),
                    "sample_id": meta.get("sample_id"),
                    "fallback_thickness_used": repair.get("fallback_thickness_used"),
                    "real_thickness_cm": repair.get("real_thickness_cm") or meta.get("thickness_cm"),
                    "factor": repair.get("factor"),
                    "note": repair.get("note"),
                }
            )

    metrics: Dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "campaign_name": campaign_name,
        "source_tag": (campaign_config or {}).get("source_tag"),
        "source_system": (campaign_config or {}).get("source_tag") or campaign_name,
        "metrics_schema_version": "0.2.0",
        "history_db_path": str(history_db_path),
        "output_dir": str(output_dir),
        "objective_target": objective_target,
        "objective_goal": objective_goal,
        "source_mode_distribution": {
            mode: source_modes.count(mode) for mode in sorted(set(source_modes))
        },
        "n_closed_loop_rounds": len(suggestions),
        "n_initial_points": min(n_initial_points, len(valid_objective_pairs)),
        "n_bo_suggestions": bo_count,
        "n_suggestions_generated": len(suggestions),
        "n_suggestions_measured": n_suggestions_measured,
        "n_llm_adjusted_suggestions": llm_adjusted_count,
        "n_history_trials": len(trials),
        "best_initial_score": best_initial,
        "best_final_score": best_final,
        "absolute_improvement": abs_improvement,
        "best_initial_sigma_299K_S_cm": best_sigma_initial,
        "best_final_sigma_299K_S_cm": best_sigma_final,
        "best_candidate_R": best_R,
        "best_candidate_N": best_N,
        "geometry_repair_count": len(geometry_repairs),
        "geometry_repairs": geometry_repairs,
        "human_intervention_level": (
            "manual sample preparation; algorithmic next-point selection; automated EIS analysis"
        ),
        "closed_loop_validity": validity,
        "limitations": _build_limitations(validity, len(suggestions), bo_count, len(trials)),
        "rounds_index": [
            {
                "round_id": s.get("round_id"),
                "source_mode": s.get("source_mode"),
                "source_tag": s.get("source_tag"),
                "suggestion_hash": s.get("suggestion_hash"),
                "created_at": s.get("created_at"),
            }
            for s in suggestions
        ],
        "stage0_records_index": [
            {
                "round_id": r.get("round_id"),
                "sample_id": r.get("sample_id"),
                "parser_mode": r.get("parser_mode"),
                "measured_after_suggestion_hash": r.get("measured_after_suggestion_hash"),
            }
            for r in stage0_records
        ],
    }
    if geometry_repairs:
        metrics["limitations"].append(
            f"{len(geometry_repairs)} history trial(s) used explicit thickness repairs; "
            "paper figures should reference the geometry repair supplement."
        )

    # Termination v3 snapshot (best-effort; never fail aggregation if criteria missing)
    if campaign_config is not None:
        try:
            from .termination_evaluator import evaluate_termination
            metrics["termination_status"] = evaluate_termination(
                campaign_config=campaign_config,
                history=history_data or {"trials": trials},
                output_dir=output_dir,
            )
        except Exception as exc:  # pragma: no cover - defensive
            metrics["termination_status"] = {"error": f"evaluate_termination failed: {exc}"}

    metrics_path = output_dir / "closed_loop_metrics.json"
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = metrics_path.with_suffix(metrics_path.suffix + ".tmp")
    tmp_path.write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    tmp_path.replace(metrics_path)
    return metrics


def _build_limitations(validity: str, n_rounds: int, bo_count: int, n_trials: int) -> List[str]:
    out: List[str] = []
    if validity == "retrospective_replay":
        out.append(
            "closed_loop_validity=retrospective_replay: all rounds are historical replay; "
            "cannot be reported as prospective closed-loop optimization."
        )
    elif validity == "virtual_oracle_only":
        out.append(
            "closed_loop_validity=virtual_oracle_only: all rounds use virtual oracle simulation, "
            "not real synthesis + EIS measurement."
        )
    if n_rounds < 3:
        out.append(f"Only {n_rounds} closed-loop round(s) recorded; underpowered for trend claims.")
    if bo_count == 0 and n_rounds > 0:
        out.append("No round used Bayesian-optimizer suggestion (all in cold-start mode).")
    if n_trials < 5:
        out.append(f"history_db has only {n_trials} trials; statistical conclusions are tentative.")
    return out
