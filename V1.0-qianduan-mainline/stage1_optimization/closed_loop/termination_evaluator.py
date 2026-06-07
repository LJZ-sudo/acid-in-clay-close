"""termination_evaluator.py — 闭环终止判据 v3 评估器。

输入：
    * campaign_config 里的 termination_criteria 块（阈值）
    * history_db 的 trials[] 列表（性能 / 预算）
    * (可选) closed_loop_rounds/*_suggestion.json（推荐位移、predicted_std）
    * (可选) Stage0 后处理的 safety_box 连续失败计数

输出：四象限触发结构，可直接序列化进 closed_loop_metrics.json
    或者 GET /api/campaigns/{name}/termination 端点返回给前端。

设计原则：
    1. 纯函数 + 全部条件可独立 inspect，每条判据返回当前值 / 阈值 / 触发标志；
    2. 阈值缺失 → 该条 status=`unknown`，不会误触发；
    3. Tier2 起 BO predicted_std 已由 optimizer 持久化进 round_*_suggestion.json
       的 bo_provenance —— `convergence` 的 B3(std) 与 `anomaly` 的 D3(stage0 fail)
       现在都能在有数据时真正触发；无数据时仍 ok=False，不会误触发；
    4. 全部用 (R, N) 归一化空间算距离/位移，避免 R∈[0,1] 与 N∈[0.5,1.3] 量纲不同导致误判。
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


_ROUND_RE = re.compile(r"^round_(\d{3,})_suggestion\.json$")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_float(v: Any) -> Optional[float]:
    try:
        f = float(v)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except (TypeError, ValueError):
        return None


def _normalize_point(params: Dict[str, Any], bounds: Dict[str, Tuple[float, float]]) -> Optional[List[float]]:
    """Map a parameter dict to [0,1]^d using bounds (skips param if missing)."""
    out: List[float] = []
    for k, (lo, hi) in bounds.items():
        v = _safe_float(params.get(k))
        if v is None or hi <= lo:
            return None
        out.append((v - lo) / (hi - lo))
    return out


def _l2(a: List[float], b: List[float]) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def _extract_bounds(campaign_config: Dict[str, Any]) -> Dict[str, Tuple[float, float]]:
    out: Dict[str, Tuple[float, float]] = {}
    for k, v in (campaign_config.get("parameters") or {}).items():
        lo = _safe_float(v.get("low"))
        hi = _safe_float(v.get("high"))
        if lo is not None and hi is not None:
            out[k] = (lo, hi)
    return out


def _read_round_suggestions(rounds_dir: Path) -> List[Dict[str, Any]]:
    if not rounds_dir.exists():
        return []
    items: List[Tuple[int, Dict[str, Any]]] = []
    for p in rounds_dir.glob("round_*_suggestion.json"):
        m = _ROUND_RE.match(p.name)
        if not m:
            continue
        try:
            payload = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        items.append((int(m.group(1)), payload))
    items.sort(key=lambda x: x[0])
    return [s for _, s in items]


_STAGE0_RESULT_RE = re.compile(r"^round_(\d{3,})_stage0_result\.json$")
_STAGE0_FAIL_TOKEN_RE = re.compile(r"fail|invalid|reject|not_ready|error|missing", re.IGNORECASE)


def _read_round_stage0_results(rounds_dir: Path) -> List[Dict[str, Any]]:
    """Read round_*_stage0_result.json in round order (Tier2 D3 input)."""
    if not rounds_dir.exists():
        return []
    items: List[Tuple[int, Dict[str, Any]]] = []
    for p in rounds_dir.glob("round_*_stage0_result.json"):
        m = _STAGE0_RESULT_RE.match(p.name)
        if not m:
            continue
        try:
            payload = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        items.append((int(m.group(1)), payload))
    items.sort(key=lambda x: x[0])
    return [s for _, s in items]


def _stage0_round_failed(stage0_result: Dict[str, Any]) -> bool:
    """Decide whether a persisted stage0 round result counts as a failure.

    Tier2 (issue 6 / D3): a round is a stage0 failure when it explicitly says so
    (``stage0_ok``/``objective_ready`` False) or carries a failure-flavoured
    validity flag. Empty/valid results are NOT counted as failures.
    """
    if stage0_result.get("stage0_ok") is False:
        return True
    if stage0_result.get("objective_ready") is False:
        return True
    for flag in stage0_result.get("validity_flags") or []:
        if _STAGE0_FAIL_TOKEN_RE.search(str(flag)):
            return True
    return False


# ---------------------------------------------------------------------------
# Quadrant evaluators
# ---------------------------------------------------------------------------

def _eval_performance(
    trials: List[Dict[str, Any]],
    perf: Dict[str, Any],
    bounds: Dict[str, Tuple[float, float]],
) -> Dict[str, Any]:
    """A 类：性能目标 — 4 条全部满足 + 重复 N 个去重配方。"""
    if not perf:
        return {"status": "unknown", "triggered": False, "reason": "no performance_target in campaign"}

    sigma_min = _safe_float(perf.get("sigma_rt_min_S_cm"))
    ea_high_max = _safe_float(perf.get("ea_high_max_eV"))
    ea_low_excess_max = _safe_float(perf.get("ea_low_excess_max_eV"))
    score_min = _safe_float(perf.get("combined_score_min"))
    n_required = int(perf.get("consecutive_distinct_recipes_required") or 2)
    min_distance = float(perf.get("distinct_recipe_min_distance") or 0.05)

    qualifying: List[Dict[str, Any]] = []
    for t in trials:
        obj = t.get("objectives") or {}
        sigma = _safe_float(obj.get("conductivity_room_temp_S_cm"))
        ea_h = _safe_float(obj.get("ea_high_temp_eV"))
        ea_lex = _safe_float(obj.get("ea_low_excess_eV"))
        score = _safe_float(obj.get("combined_score"))
        # ea_low_excess 派生：若不存在则现算（兼容旧 trial）
        if ea_lex is None and ea_h is not None:
            ea_low = _safe_float(obj.get("ea_low_temp_eV"))
            if ea_low is not None:
                v = ea_low - 1.5 * ea_h
                ea_lex = max(0.0, v)
        passed = True
        per_check: Dict[str, Any] = {}
        for label, value, limit, op in [
            ("sigma_rt", sigma, sigma_min, "ge"),
            ("ea_high", ea_h, ea_high_max, "le"),
            ("ea_low_excess", ea_lex, ea_low_excess_max, "le"),
            ("combined_score", score, score_min, "ge"),
        ]:
            if value is None or limit is None:
                per_check[label] = {"value": value, "limit": limit, "ok": None}
                passed = False
                continue
            ok = (value >= limit) if op == "ge" else (value <= limit)
            per_check[label] = {"value": value, "limit": limit, "ok": ok}
            if not ok:
                passed = False
        if passed:
            qualifying.append({
                "trial_id": t.get("trial_id"),
                "sample_id": (t.get("metadata") or {}).get("sample_id"),
                "parameters": t.get("parameters") or {},
                "checks": per_check,
            })

    # 求"距离 >= min_distance"的去重配方计数
    distinct_count = 0
    chosen: List[List[float]] = []
    for q in qualifying:
        pt = _normalize_point(q["parameters"], bounds)
        if pt is None:
            continue
        if not chosen or all(_l2(pt, c) >= min_distance for c in chosen):
            chosen.append(pt)
            distinct_count += 1

    # 历史最优 trial 当前各指标值（便于"接近但未达"提示）
    best_trial: Optional[Dict[str, Any]] = None
    best_score = None
    for t in trials:
        s = _safe_float((t.get("objectives") or {}).get("combined_score"))
        if s is None:
            continue
        if best_score is None or s > best_score:
            best_score = s
            best_trial = t

    current_best_metrics: Dict[str, Any] = {}
    if best_trial:
        obj = best_trial.get("objectives") or {}
        current_best_metrics = {
            "trial_id": best_trial.get("trial_id"),
            "sigma_rt": _safe_float(obj.get("conductivity_room_temp_S_cm")),
            "ea_high": _safe_float(obj.get("ea_high_temp_eV")),
            "ea_low_excess": _safe_float(obj.get("ea_low_excess_eV")),
            "combined_score": _safe_float(obj.get("combined_score")),
        }

    triggered = distinct_count >= n_required
    return {
        "status": "ok" if triggered else "pending",
        "triggered": triggered,
        "thresholds": {
            "sigma_rt_min_S_cm": sigma_min,
            "ea_high_max_eV": ea_high_max,
            "ea_low_excess_max_eV": ea_low_excess_max,
            "combined_score_min": score_min,
            "consecutive_distinct_recipes_required": n_required,
            "distinct_recipe_min_distance": min_distance,
        },
        "qualifying_trials": qualifying,
        "n_qualifying_total": len(qualifying),
        "n_qualifying_distinct": distinct_count,
        "current_best": current_best_metrics,
    }


def _eval_convergence(
    trials: List[Dict[str, Any]],
    rounds: List[Dict[str, Any]],
    conv: Dict[str, Any],
    bounds: Dict[str, Tuple[float, float]],
) -> Dict[str, Any]:
    """B 类：BO 收敛 — plateau + 推荐位移 + (可选) GP std。"""
    if not conv:
        return {"status": "unknown", "triggered": False, "rules": [], "reason": "no convergence in campaign"}

    plateau_window = int(conv.get("best_score_plateau_window") or 5)
    plateau_min_delta = float(conv.get("best_score_min_delta") or 0.10)
    shift_window = int(conv.get("recommendation_shift_window") or 3)
    shift_max_l2 = float(conv.get("recommendation_shift_max_l2") or 0.05)
    std_max = _safe_float(conv.get("predicted_std_max"))
    required_to_trigger = int(conv.get("rules_required_to_trigger") or 2)

    rules: List[Dict[str, Any]] = []

    # Rule B1: best_score plateau —— 看最近 plateau_window 个新样本是否把 best 推高 >= delta
    scores = [_safe_float((t.get("objectives") or {}).get("combined_score")) for t in trials]
    scores = [s for s in scores if s is not None]
    plateau_rule: Dict[str, Any] = {
        "id": "best_score_plateau",
        "label": f"最近 {plateau_window} 个样本未将 best_score 提升 ≥ {plateau_min_delta}",
        "ok": False,
        "value": None,
        "threshold": {"window": plateau_window, "min_delta": plateau_min_delta},
    }
    if len(scores) > plateau_window:
        best_before = max(scores[:-plateau_window])
        best_after = max(scores)
        gain = best_after - best_before
        plateau_rule.update({
            "value": {"best_before_window": best_before, "best_after_window": best_after, "gain": gain},
            "ok": gain < plateau_min_delta,
        })
    elif len(scores) >= 2:
        plateau_rule.update({
            "value": {"n_scores": len(scores), "needed": plateau_window + 1},
            "ok": False,
        })
    rules.append(plateau_rule)

    # Rule B2: 推荐位移 —— 最近 shift_window 个 BO 推荐的归一化 L2 位移 max <= shift_max
    bo_points: List[List[float]] = []
    for r in rounds:
        opt = r.get("optimizer_suggestion") or {}
        pt = _normalize_point(opt, bounds)
        if pt is not None:
            bo_points.append(pt)
    shift_rule: Dict[str, Any] = {
        "id": "recommendation_shift",
        "label": f"最近 {shift_window} 次 BO 推荐的归一化 L2 位移 ≤ {shift_max_l2}",
        "ok": False,
        "value": None,
        "threshold": {"window": shift_window, "max_l2": shift_max_l2},
    }
    if len(bo_points) >= shift_window + 1:
        recent = bo_points[-(shift_window + 1):]
        shifts = [_l2(recent[i], recent[i - 1]) for i in range(1, len(recent))]
        max_shift = max(shifts)
        shift_rule.update({
            "value": {"shifts": shifts, "max_shift": max_shift},
            "ok": max_shift <= shift_max_l2,
        })
    else:
        shift_rule.update({
            "value": {"n_bo_points": len(bo_points), "needed": shift_window + 1},
            "ok": False,
        })
    rules.append(shift_rule)

    # Rule B3 (optional): GP predicted_std
    # Tier2 (issue 6, 2026-06-01): now LIVE on the producer side too. The optimizer
    # (BayesianOptimizer.get_provenance) persists predicted_std for the last
    # suggestion into closed_loop_rounds/round_*_suggestion.json -> bo_provenance.
    # This rule becomes `ok=True` only when `predicted_std_max` is configured AND
    # enough recent rounds carry a numeric predicted_std (cold-start rounds have
    # none, so it cannot false-trigger early).
    std_rule: Dict[str, Any] = {
        "id": "predicted_std",
        "label": f"最近 {shift_window} 次 BO 推荐 GP 不确定度 std ≤ {std_max}",
        "ok": False,
        "value": None,
        "threshold": {"window": shift_window, "max_std": std_max},
    }
    if std_max is not None:
        recent_std: List[float] = []
        for r in rounds[-shift_window:]:
            prov = (r.get("bo_provenance") or {})
            s = _safe_float(prov.get("predicted_std"))
            if s is not None:
                recent_std.append(s)
        if len(recent_std) >= shift_window:
            std_rule.update({
                "value": {"recent_std": recent_std, "max_std": max(recent_std)},
                "ok": max(recent_std) <= std_max,
            })
        else:
            std_rule.update({
                "value": {"available": len(recent_std), "needed": shift_window, "note": "predicted_std 尚未在 round_*_suggestion.json 持久化"},
                "ok": False,
            })
    else:
        std_rule["value"] = {"note": "未配置 predicted_std_max；跳过该项"}

    rules.append(std_rule)

    n_ok = sum(1 for r in rules if r.get("ok") is True)
    triggered = n_ok >= required_to_trigger

    return {
        "status": "ok" if triggered else "pending",
        "triggered": triggered,
        "rules": rules,
        "n_ok": n_ok,
        "required_to_trigger": required_to_trigger,
    }


def _eval_budget(trials: List[Dict[str, Any]], budget: Dict[str, Any]) -> Dict[str, Any]:
    if not budget:
        return {"status": "unknown", "triggered": False}
    max_total = int(budget.get("max_total_trials") or 20)
    n_total = len(trials)
    triggered = n_total >= max_total
    return {
        "status": "exhausted" if triggered else "ok",
        "triggered": triggered,
        "n_total_trials": n_total,
        "max_total_trials": max_total,
        "remaining": max(0, max_total - n_total),
    }


def _eval_anomaly(
    trials: List[Dict[str, Any]],
    rounds: List[Dict[str, Any]],
    anomaly: Dict[str, Any],
    bounds: Dict[str, Tuple[float, float]],
    stage0_results: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    if not anomaly:
        return {"status": "unknown", "triggered": False, "rules": []}
    stage0_results = stage0_results or []

    safety_fail_max = int(anomaly.get("safety_box_consecutive_fail") or 2)
    stage0_fail_max = int(anomaly.get("stage0_consecutive_fail") or 3)
    boundary_max = int(anomaly.get("boundary_hugging_consecutive") or 2)
    boundary_eps = float(anomaly.get("boundary_proximity_normalized") or 0.02)

    rules: List[Dict[str, Any]] = []

    # Rule D1: safety_box 连续 false
    safety_fail_streak = 0
    max_streak = 0
    for r in rounds:
        sb = r.get("safety_box") or {}
        if sb.get("passed") is False:
            safety_fail_streak += 1
            max_streak = max(max_streak, safety_fail_streak)
        else:
            safety_fail_streak = 0
    rules.append({
        "id": "safety_box_consecutive_fail",
        "label": f"safety_box 连续未通过 ≥ {safety_fail_max} 轮",
        "ok": max_streak >= safety_fail_max,
        "value": {"current_streak": safety_fail_streak, "max_streak": max_streak},
        "threshold": safety_fail_max,
    })

    # Rule D2: boundary hugging —— 最近 N 个 BO 推荐贴域边
    bo_pts: List[List[float]] = []
    for r in rounds:
        opt = r.get("optimizer_suggestion") or {}
        pt = _normalize_point(opt, bounds)
        if pt is not None:
            bo_pts.append(pt)
    boundary_streak = 0
    for pt in bo_pts[-boundary_max:]:
        if any((x <= boundary_eps or x >= 1 - boundary_eps) for x in pt):
            boundary_streak += 1
        else:
            boundary_streak = 0
    rules.append({
        "id": "boundary_hugging",
        "label": f"最近 {boundary_max} 次 BO 推荐贴域边界（归一化距离 ≤ {boundary_eps}）",
        "ok": boundary_streak >= boundary_max and len(bo_pts) >= boundary_max,
        "value": {"current_streak": boundary_streak, "n_bo_points": len(bo_pts)},
        "threshold": boundary_max,
    })

    # Rule D3: stage0 连续失败
    # Tier2 (issue 6, 2026-06-01): now LIVE. Computes the trailing consecutive
    # stage0-failure streak from persisted round_*_stage0_result.json. When no
    # stage0 results are persisted the streak is 0 -> ok=False (still cannot
    # false-trigger), preserving the inert behavior in the no-data case.
    stage0_fail_streak = 0
    stage0_max_streak = 0
    for sr in stage0_results:
        if _stage0_round_failed(sr):
            stage0_fail_streak += 1
            stage0_max_streak = max(stage0_max_streak, stage0_fail_streak)
        else:
            stage0_fail_streak = 0
    rules.append({
        "id": "stage0_consecutive_fail",
        "label": f"Stage0 连续失败 ≥ {stage0_fail_max} 轮",
        "ok": stage0_max_streak >= stage0_fail_max and len(stage0_results) >= stage0_fail_max,
        "value": {
            "current_streak": stage0_fail_streak,
            "max_streak": stage0_max_streak,
            "n_stage0_results": len(stage0_results),
        },
        "threshold": stage0_fail_max,
    })

    triggered = any(r["ok"] for r in rules)
    return {
        "status": "alert" if triggered else "ok",
        "triggered": triggered,
        "rules": rules,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def evaluate_termination(
    campaign_config: Dict[str, Any],
    history: Dict[str, Any],
    output_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """主入口：给定 campaign_config + history_db，返回 termination_status v3 结构。

    A/B/C/D 任意一个 `triggered=True` 即视为闭环可结束（前端做最终展示）。
    """
    criteria = campaign_config.get("termination_criteria") or {}
    bounds = _extract_bounds(campaign_config)
    trials = list(history.get("trials") or [])

    rounds: List[Dict[str, Any]] = []
    stage0_results: List[Dict[str, Any]] = []
    if output_dir is not None:
        rounds = _read_round_suggestions(Path(output_dir) / "closed_loop_rounds")
        stage0_results = _read_round_stage0_results(Path(output_dir) / "closed_loop_rounds")

    perf = _eval_performance(trials, criteria.get("performance_target") or {}, bounds)
    conv = _eval_convergence(trials, rounds, criteria.get("convergence") or {}, bounds)
    budget = _eval_budget(trials, criteria.get("budget") or {})
    anomaly = _eval_anomaly(trials, rounds, criteria.get("anomaly") or {}, bounds, stage0_results)

    any_triggered = bool(perf.get("triggered") or conv.get("triggered") or budget.get("triggered") or anomaly.get("triggered"))
    triggered_by: List[str] = []
    if perf.get("triggered"):
        triggered_by.append("performance_target")
    if conv.get("triggered"):
        triggered_by.append("convergence")
    if budget.get("triggered"):
        triggered_by.append("budget")
    if anomaly.get("triggered"):
        triggered_by.append("anomaly")

    if any_triggered:
        verdict = "loop_can_end"
    elif budget.get("remaining") == 0:
        verdict = "loop_must_end_budget"
    else:
        verdict = "continue"

    # ---- Progress 摘要：让 UI 即使没触发也能直观看到 BO 在变 ----
    recent_n = 3
    recent_trials_summary: List[Dict[str, Any]] = []
    best_score_so_far: Optional[float] = None
    best_trial_id: Optional[Any] = None
    best_seen_at: Optional[int] = None  # 在 trials 列表的索引（0-based）
    score_trajectory: List[Optional[float]] = []
    for idx, t in enumerate(trials):
        obj = t.get("objectives") or {}
        params = t.get("parameters") or {}
        score = _safe_float(obj.get("combined_score"))
        score_trajectory.append(score)
        if score is not None and (best_score_so_far is None or score > best_score_so_far):
            best_score_so_far = score
            best_trial_id = t.get("trial_id")
            best_seen_at = idx
    for t in trials[-recent_n:]:
        obj = t.get("objectives") or {}
        params = t.get("parameters") or {}
        recent_trials_summary.append({
            "trial_id": t.get("trial_id"),
            "sample_id": (t.get("metadata") or {}).get("sample_id"),
            "R": _safe_float(params.get("R")),
            "N": _safe_float(params.get("N")),
            "sigma_rt": _safe_float(obj.get("conductivity_room_temp_S_cm")),
            "ea_high": _safe_float(obj.get("ea_high_temp_eV")),
            "ea_low_excess": _safe_float(obj.get("ea_low_excess_eV")),
            "combined_score": _safe_float(obj.get("combined_score")),
        })
    trials_since_best: Optional[int] = None
    if best_seen_at is not None:
        trials_since_best = len(trials) - 1 - best_seen_at

    # 离 A 类阈值还差多少（用 best trial 计算）
    perf_th = (criteria.get("performance_target") or {})
    gaps: Dict[str, Any] = {}
    best_obj = (
        trials[best_seen_at].get("objectives") if best_seen_at is not None else {}
    ) or {}
    if perf_th:
        sigma = _safe_float(best_obj.get("conductivity_room_temp_S_cm"))
        ea_h = _safe_float(best_obj.get("ea_high_temp_eV"))
        ea_lex = _safe_float(best_obj.get("ea_low_excess_eV"))
        if ea_lex is None and ea_h is not None:
            ea_low = _safe_float(best_obj.get("ea_low_temp_eV"))
            if ea_low is not None:
                ea_lex = max(0.0, ea_low - 1.5 * ea_h)
        score_v = _safe_float(best_obj.get("combined_score"))
        if sigma is not None and perf_th.get("sigma_rt_min_S_cm") is not None:
            gaps["sigma_rt"] = perf_th["sigma_rt_min_S_cm"] - sigma  # >0 表示还差多少
        if ea_h is not None and perf_th.get("ea_high_max_eV") is not None:
            gaps["ea_high"] = ea_h - perf_th["ea_high_max_eV"]  # >0 表示超阈值多少
        if ea_lex is not None and perf_th.get("ea_low_excess_max_eV") is not None:
            gaps["ea_low_excess"] = ea_lex - perf_th["ea_low_excess_max_eV"]
        if score_v is not None and perf_th.get("combined_score_min") is not None:
            gaps["combined_score"] = perf_th["combined_score_min"] - score_v

    progress = {
        "best_trial_id": best_trial_id,
        "best_score": best_score_so_far,
        "trials_since_best_updated": trials_since_best,
        "score_trajectory": score_trajectory,
        "recent_trials": recent_trials_summary,
        "performance_gap_to_threshold": gaps,
    }

    return {
        "version": criteria.get("version") or "v3",
        "rationale": criteria.get("rationale"),
        "verdict": verdict,
        "triggered_by": triggered_by,
        "performance": perf,
        "convergence": conv,
        "budget": budget,
        "anomaly": anomaly,
        "n_history_trials": len(trials),
        "n_closed_loop_rounds": len(rounds),
        "progress": progress,
    }


__all__ = ["evaluate_termination"]
