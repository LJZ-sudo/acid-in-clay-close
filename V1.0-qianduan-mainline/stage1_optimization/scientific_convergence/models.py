# -*- coding: utf-8 -*-
"""C³-Harness 数据模型（ESAS-OS 2.0 / §10.5）。

把"收敛=几条阈值触发"升级为"**收敛状态 + 动作组合**":
  - `ConvergenceState`  统一五类不确定度(性能差距 / BO 后验 std / 计量不确定度(Rb-ACT)/
                        复现地板 / 主张稳定度)+ legacy verdict 投影;
  - `Action`            候选动作枚举(不止"新配方");
  - `ActionUtility`     单动作的信息价值效用分解(E[ΔHV]/VoI/cost/risk → U);
  - `ConvergenceCertificate` 可审计:在何种不确定度下、依据什么、建议何动作、是否与 legacy 一致。
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class Action:
    STOP = "STOP"                       # 宣告收敛/结束
    REPLICATE = "REPLICATE"             # 同配方复测新片(降复现地板风险)
    REMEASURE = "REMEASURE"             # 同片重测(降计量不确定度)
    EXTEND_FREQ = "EXTEND_FREQ"         # 扩频(补高/低频锚点)
    ADD_TEMP = "ADD_TEMP"               # 加测温点(稳断点/Arrhenius)
    DIAGNOSE = "DIAGNOSE"               # 故障诊断(异常触发时)
    NEW_FORMULATION = "NEW_FORMULATION" # 探索新配方
    CONTINUE = "CONTINUE"               # 低承诺默认:再走一轮
    ALL = (STOP, REPLICATE, REMEASURE, EXTEND_FREQ, ADD_TEMP, DIAGNOSE,
           NEW_FORMULATION, CONTINUE)


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


@dataclass
class ConvergenceState:
    """五类不确定度统一在 [0,1] 归一(0=已解决,1=最不确定),外加 legacy 投影。"""
    performance_gap: float = 0.0        # 距性能目标还差多少(归一;0=达标)
    bo_posterior_std: float = 0.0       # BO 后验不确定度(归一;高=仍有探索空间)
    metrological_uncertainty: float = 0.0  # 计量不确定度(来自 Rb-ACT u_total_dex 归一)
    reproducibility_unmet: float = 0.0  # 复现地板未满足程度(缺的独立片占比)
    claim_instability: float = 0.0      # 主张不稳定度(1−claim_stability)
    anomaly: float = 0.0                # 异常信号(safety/stage0/boundary)
    legacy_verdict: str = "continue"
    legacy_triggered_by: List[str] = field(default_factory=list)
    budget_exhausted: bool = False
    notes: Dict[str, Any] = field(default_factory=dict)

    def legacy_allows_end(self) -> bool:
        return self.legacy_verdict in ("loop_can_end", "loop_must_end_budget") or self.budget_exhausted

    def unresolved(self) -> float:
        """阻止"安心停止"的最大未解决不确定度(任一高 → 不该宣收敛)。"""
        return max(self.metrological_uncertainty, self.reproducibility_unmet,
                   self.claim_instability)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "performance_gap": self.performance_gap,
            "bo_posterior_std": self.bo_posterior_std,
            "metrological_uncertainty": self.metrological_uncertainty,
            "reproducibility_unmet": self.reproducibility_unmet,
            "claim_instability": self.claim_instability,
            "anomaly": self.anomaly,
            "unresolved": self.unresolved(),
            "legacy_verdict": self.legacy_verdict,
            "legacy_triggered_by": list(self.legacy_triggered_by),
            "budget_exhausted": self.budget_exhausted,
            "notes": dict(self.notes),
        }


@dataclass
class ActionUtility:
    action: str
    expected_delta_hv: float            # E[ΔHV] 预期超体积增益(探索价值)
    value_of_information: float         # VoI 解决不确定度的价值
    cost: float
    risk: float
    utility: float

    def to_dict(self) -> Dict[str, Any]:
        return {"action": self.action, "expected_delta_hv": round(self.expected_delta_hv, 4),
                "value_of_information": round(self.value_of_information, 4),
                "cost": round(self.cost, 4), "risk": round(self.risk, 4),
                "utility": round(self.utility, 4)}


@dataclass
class ConvergenceCertificate:
    certificate_id: str
    state: ConvergenceState
    portfolio: List[ActionUtility]      # 按 utility 降序
    recommended_action: str
    c3_stop: bool                       # C³ 是否建议停(单调 ⊆ legacy 停)
    legacy_stop: bool
    consistent_with_legacy: bool        # C³ 绝不比 legacy 更早停 → 永不矛盾
    delta_vs_legacy: str                # "agree_stop"|"agree_continue"|"c3_defers_stop"
    reasons: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=_now)

    def top_actions(self, k: int = 3) -> List[str]:
        return [u.action for u in self.portfolio[:k]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "certificate_id": self.certificate_id,
            "state": self.state.to_dict(),
            "portfolio": [u.to_dict() for u in self.portfolio],
            "recommended_action": self.recommended_action,
            "c3_stop": self.c3_stop, "legacy_stop": self.legacy_stop,
            "consistent_with_legacy": self.consistent_with_legacy,
            "delta_vs_legacy": self.delta_vs_legacy,
            "reasons": list(self.reasons), "created_at": self.created_at,
        }
