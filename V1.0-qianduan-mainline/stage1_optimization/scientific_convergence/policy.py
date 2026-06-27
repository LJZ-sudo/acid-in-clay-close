# -*- coding: utf-8 -*-
"""C³-Harness 信息价值策略（ESAS-OS 2.0 / §10.5）。

效用 `U(a) = E[ΔHV] + λ·VoI − β·cost − γ·risk`(第一版:确定性候选 + 概率效用,不上 POMDP)。
核心不变量(本策略保证):**C³ 的"停"单调 ⊆ legacy 的"停"** —— C³ 只会在证据不足时
*推迟* legacy 的停止,绝不比 legacy 更早停 → 永不引入新的错误提前停止。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from .models import Action, ActionUtility, ConvergenceState


@dataclass
class UtilityWeights:
    lambda_voi: float = 1.0
    beta_cost: float = 0.3
    gamma_risk: float = 1.0
    stop_base_reward: float = 0.15      # 停止节省成本的基线收益
    continue_base: float = 0.05         # 低承诺默认动作的微小效用
    resolved_eps: float = 0.15          # 死区:归一不确定度 < eps 视为已解决(不值得再投动作)


def _db(x: float, eps: float) -> float:
    """死区:低于 eps 的(归一)不确定度按已解决处理,避免为可忽略残差反复 REMEASURE。"""
    return x if x >= eps else 0.0


# 各动作的名义成本(归一;真机/样品越贵越大)
_COST = {
    Action.STOP: 0.0, Action.CONTINUE: 0.05, Action.REMEASURE: 0.10,
    Action.EXTEND_FREQ: 0.15, Action.ADD_TEMP: 0.20, Action.DIAGNOSE: 0.10,
    Action.REPLICATE: 0.30, Action.NEW_FORMULATION: 0.20,
}


def _u(action: str, edhv: float, voi: float, cost: float, risk: float,
       w: UtilityWeights) -> ActionUtility:
    util = edhv + w.lambda_voi * voi - w.beta_cost * cost - w.gamma_risk * risk
    return ActionUtility(action, edhv, voi, cost, risk, util)


def score_actions(state: ConvergenceState,
                  weights: UtilityWeights = UtilityWeights()) -> List[ActionUtility]:
    """对每个候选动作算 U(a)。纯函数、可复算。死区内的残余不确定度按已解决处理。"""
    w = weights
    eps = w.resolved_eps
    mu = _db(state.metrological_uncertainty, eps)   # 计量(死区后)
    ru = _db(state.reproducibility_unmet, eps)      # 复现地板(死区后)
    ci = _db(state.claim_instability, eps)          # 主张不稳(死区后)
    an = _db(state.anomaly, eps)                    # 异常(死区后)
    gap = _db(max(0.0, state.performance_gap), eps)
    std = max(0.0, state.bo_posterior_std)
    unresolved = max(mu, ru, ci)
    has_freq_anchor_gap = bool(state.notes.get("extend_freq_requested"))
    has_temp_gap = bool(state.notes.get("add_temp_requested"))

    out: List[ActionUtility] = []

    # STOP:无探索价值;风险 = 未解决不确定度 + 仍未达标的性能差距
    out.append(ActionUtility(Action.STOP, 0.0, 0.0, _COST[Action.STOP],
                             risk=unresolved + gap,
                             utility=w.stop_base_reward - w.gamma_risk * (unresolved + gap)))

    # REMEASURE:VoI = 计量不确定度(同片重测最直接降它)
    out.append(_u(Action.REMEASURE, 0.0, mu, _COST[Action.REMEASURE], 0.0, w))

    # REPLICATE:VoI = 复现地板未满足程度(+顺带稳主张)
    out.append(_u(Action.REPLICATE, 0.0, ru + 0.3 * ci, _COST[Action.REPLICATE], 0.0, w))

    # EXTEND_FREQ:仅当 Rb-ACT 提扩频建议时才有高 VoI(补锚点降计量不确定度)
    out.append(_u(Action.EXTEND_FREQ, 0.0, (0.8 * mu if has_freq_anchor_gap else 0.0),
                  _COST[Action.EXTEND_FREQ], 0.0, w))

    # ADD_TEMP:仅当需要稳断点时才有高 VoI
    out.append(_u(Action.ADD_TEMP, 0.0, (0.7 * ci if has_temp_gap else 0.0),
                  _COST[Action.ADD_TEMP], 0.0, w))

    # DIAGNOSE:VoI = 异常信号
    out.append(_u(Action.DIAGNOSE, 0.0, an, _COST[Action.DIAGNOSE], 0.0, w))

    # NEW_FORMULATION:E[ΔHV] = 性能差距 × (探索空间);风险 = 在不可靠测量上探索
    edhv = gap * (0.5 + 0.5 * std)
    out.append(_u(Action.NEW_FORMULATION, edhv, 0.0, _COST[Action.NEW_FORMULATION],
                  risk=0.5 * unresolved, w=w))

    # CONTINUE:低承诺默认
    out.append(ActionUtility(Action.CONTINUE, 0.0, 0.0, _COST[Action.CONTINUE],
                             0.0, w.continue_base - w.beta_cost * _COST[Action.CONTINUE]))

    out.sort(key=lambda u: u.utility, reverse=True)
    return out


def recommend(state: ConvergenceState,
              weights: UtilityWeights = UtilityWeights()) -> List[ActionUtility]:
    """返回按效用降序的动作组合;施加两条硬约束:
       (i) 预算耗尽 = 硬停门 → STOP 置顶(C³ 不得推迟硬预算门);
       (ii) 单调约束:legacy 不允许结束时,C³ 绝不把 STOP 当首选(永不更早停)。"""
    portfolio = score_actions(state, weights)
    # (i) 硬预算门:物理上不能再做实验 → 必须 STOP
    if state.budget_exhausted:
        return [u for u in portfolio if u.action == Action.STOP] + \
               [u for u in portfolio if u.action != Action.STOP]
    # (ii) 单调约束:legacy 还要继续时,STOP 不得居首
    if portfolio[0].action == Action.STOP and not state.legacy_allows_end():
        portfolio = [u for u in portfolio if u.action != Action.STOP] + \
                    [u for u in portfolio if u.action == Action.STOP]
    return portfolio
