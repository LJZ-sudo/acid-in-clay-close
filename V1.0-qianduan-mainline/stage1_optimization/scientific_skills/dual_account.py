# -*- coding: utf-8 -*-
"""双账户认知博弈（M5-C）。

认知账户(Epistemic):用严格适当评分(Brier/log-loss)度量预测校准 + 更新信誉。
执行账户(Execution / RiskClearing):执行权由独立风险清算决定,**不读 agent 的自报置信度**
→ Agent 不能因"更自信"直接获得更多执行权(机制设计核心)。
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List


class EpistemicAccount:
    """严格适当评分(Brier/log-loss):真实概率是期望得分最优报告。"""

    def __init__(self, eta: float = 0.5):
        self.eta = eta
        self._brier: Dict[str, List[float]] = {}
        self._logloss: Dict[str, List[float]] = {}
        self._weight: Dict[str, float] = {}

    def record(self, agent: str, predicted_prob: float, outcome: int) -> None:
        p = min(max(float(predicted_prob), 1e-6), 1 - 1e-6)
        y = int(outcome)
        brier = (p - y) ** 2
        logloss = -(y * math.log(p) + (1 - y) * math.log(1 - p))
        self._brier.setdefault(agent, []).append(brier)
        self._logloss.setdefault(agent, []).append(logloss)
        w = self._weight.get(agent, 1.0)
        self._weight[agent] = w * math.exp(-self.eta * brier)

    def brier(self, agent: str) -> float:
        xs = self._brier.get(agent, [])
        return sum(xs) / len(xs) if xs else float("nan")

    def logloss(self, agent: str) -> float:
        xs = self._logloss.get(agent, [])
        return sum(xs) / len(xs) if xs else float("nan")

    def reputation(self, agent: str) -> float:
        return self._weight.get(agent, 1.0)


@dataclass
class RiskClearing:
    """执行账户:执行权由风险清算决定,与自报置信度无关。"""
    r_max: float = 0.2

    def act(self, *, cert_valid: bool, in_domain: bool,
            risk_estimate: float, uncertainty: float,
            claimed_confidence: float = None) -> bool:
        # claimed_confidence 被**有意忽略** —— 防止"越自信越能执行"。
        if not cert_valid or not in_domain:
            return False
        return (risk_estimate + uncertainty) <= self.r_max

    def authority_depends_on_confidence(self) -> bool:
        """机制自证:执行权是否依赖自报置信度 → 恒 False(双账户分离)。"""
        base = self.act(cert_valid=True, in_domain=True, risk_estimate=0.05,
                        uncertainty=0.02, claimed_confidence=0.50)
        hyped = self.act(cert_valid=True, in_domain=True, risk_estimate=0.05,
                         uncertainty=0.02, claimed_confidence=0.999)
        return base != hyped


# 别名:RiskClearing 即"执行账户"
ExecutionAccount = RiskClearing
