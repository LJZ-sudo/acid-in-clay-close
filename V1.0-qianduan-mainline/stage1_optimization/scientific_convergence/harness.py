# -*- coding: utf-8 -*-
"""C³-Harness shadow 层（ESAS-OS 2.0 / §10.5）。

**shadow 于 `termination_evaluator.evaluate_termination` 之上,绝不改写它**:
  legacy 给 verdict → 本层把 progress/convergence 投影成 `ConvergenceState`,
  叠加 Rb-ACT 计量不确定度 / 复现地板 / 主张稳定度 → 动作组合 + `ConvergenceCertificate`。
只记录、不夺权(对齐 §10.7:默认 shadow,关掉即恢复 legacy)。
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from .models import Action, ConvergenceState, ConvergenceCertificate
from .policy import recommend, UtilityWeights


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


def build_state_from_termination(
    termination: Dict[str, Any],
    *,
    metrological_uncertainty_dex: float = 0.0,
    metro_fail_dex: float = 0.30,
    repro_replicates_have: Optional[int] = None,
    repro_replicates_required: int = 3,
    claim_stability: float = 1.0,
    bo_std_ref: float = 0.10,
    score_min: Optional[float] = None,
    rb_act_active_requests: Optional[List[str]] = None,
) -> ConvergenceState:
    """把 legacy termination 结构 + 外部证据质量投影成五类不确定度。

    - metrological_uncertainty_dex: 来自 Rb-ACT 后验 σ(dex),/metro_fail_dex 归一;
    - repro_replicates_have/required: 复现地板需要的独立片数(between-specimen 0.252 dex 需 ≥3);
    - claim_stability∈[0,1]: 来自 claim_graph(1=全 SUPPORTED 无 AFFECTED);
    - bo_std/performance_gap: 从 termination.convergence / progress 读。
    """
    conv = termination.get("convergence") or {}
    progress = termination.get("progress") or {}
    budget = termination.get("budget") or {}

    # BO 后验 std:取 convergence 的 predicted_std 规则值
    bo_std = 0.0
    for r in conv.get("rules") or []:
        if r.get("id") == "predicted_std":
            val = (r.get("value") or {})
            ms = val.get("max_std")
            if isinstance(ms, (int, float)):
                bo_std = float(ms)
    # 性能差距:progress 的 combined_score gap(>0 表示还差),按 score_min 归一
    gaps = progress.get("performance_gap_to_threshold") or {}
    gap_raw = gaps.get("combined_score")
    if isinstance(gap_raw, (int, float)) and gap_raw > 0:
        denom = abs(score_min) if (score_min not in (None, 0)) else max(abs(gap_raw), 1.0)
        perf_gap = _clip01(float(gap_raw) / denom)
    else:
        perf_gap = 0.0

    repro_unmet = 0.0
    if repro_replicates_have is not None and repro_replicates_required > 0:
        repro_unmet = _clip01((repro_replicates_required - repro_replicates_have)
                              / repro_replicates_required)

    reqs = set(rb_act_active_requests or [])
    notes = {
        "extend_freq_requested": any("EXTEND_FREQ" in s for s in reqs),
        "add_temp_requested": any("ADD_TEMP" in s for s in reqs),
        "rb_act_active_requests": sorted(reqs),
        "legacy_progress_best_score": progress.get("best_score"),
    }

    return ConvergenceState(
        performance_gap=perf_gap,
        bo_posterior_std=_clip01(bo_std / bo_std_ref if bo_std_ref > 0 else 0.0),
        metrological_uncertainty=_clip01(
            metrological_uncertainty_dex / metro_fail_dex if metro_fail_dex > 0 else 0.0),
        reproducibility_unmet=repro_unmet,
        claim_instability=_clip01(1.0 - claim_stability),
        anomaly=1.0 if (termination.get("anomaly") or {}).get("triggered") else 0.0,
        legacy_verdict=str(termination.get("verdict") or "continue"),
        legacy_triggered_by=list(termination.get("triggered_by") or []),
        budget_exhausted=bool(budget.get("triggered")) and budget.get("status") == "exhausted",
        notes=notes,
    )


def certify(state: ConvergenceState,
            weights: UtilityWeights = UtilityWeights()) -> ConvergenceCertificate:
    """据状态算动作组合 + 出收敛证书(含单调一致性裁决)。"""
    portfolio = recommend(state, weights)
    recommended = portfolio[0].action
    legacy_stop = state.legacy_allows_end()
    c3_stop = (recommended == Action.STOP)
    # 单调不变量:c3_stop ⇒ legacy_stop(recommend 已保证不更早停)
    consistent = (not c3_stop) or legacy_stop

    if c3_stop and legacy_stop:
        delta = "agree_stop"
    elif (not c3_stop) and (not legacy_stop):
        delta = "agree_continue"
    elif (not c3_stop) and legacy_stop:
        delta = "c3_defers_stop"        # ★ C³ 的价值:legacy 想停,但证据不足 → 推迟
    else:
        delta = "INCONSISTENT"          # 理论上不应出现(被单调约束排除)

    reasons: List[str] = []
    if delta == "c3_defers_stop":
        if state.metrological_uncertainty > 0.33:
            reasons.append(f"metrological_uncertainty_high={state.metrological_uncertainty:.2f}→{recommended}")
        if state.reproducibility_unmet > 0:
            reasons.append(f"reproducibility_floor_unmet={state.reproducibility_unmet:.2f}")
        if state.claim_instability > 0:
            reasons.append(f"claim_unstable={state.claim_instability:.2f}")
    elif delta == "agree_stop":
        reasons.append("all_uncertainties_resolved")
    else:
        reasons.append(f"explore:{recommended}")

    return ConvergenceCertificate(
        certificate_id=f"C3-{uuid.uuid4().hex[:8]}",
        state=state, portfolio=portfolio, recommended_action=recommended,
        c3_stop=c3_stop, legacy_stop=legacy_stop, consistent_with_legacy=consistent,
        delta_vs_legacy=delta, reasons=reasons or ["ok"])


def shadow_convergence(
    termination: Dict[str, Any],
    *,
    weights: UtilityWeights = UtilityWeights(),
    **state_kwargs: Any,
) -> ConvergenceCertificate:
    """一步到位:legacy termination(+证据质量)→ 收敛证书。shadow,不改 legacy verdict。"""
    state = build_state_from_termination(termination, **state_kwargs)
    return certify(state, weights)
