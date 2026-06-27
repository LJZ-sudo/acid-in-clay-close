# -*- coding: utf-8 -*-
"""Rb-ACT 数据模型（ESAS-OS 2.0 / PC-Skills v2）。

Rb-ACT = **A**ctive, **C**alibrated, **T**eachable bulk-resistance skill。
它**不替代、不改写** `rb_fitting.py`（legacy 永不覆盖），而是在既有
`fit_all_rb_methods()`（并行四法 + 可信集 + 集成）之上加一层**决策**:

  四法证据 → Rb 后验(点估 + 95% 区间 + 两类不确定度分解)
           → 弃权(ABSTAIN)判定（不确定就拒绝给值，附原因码）
           → 主动测量建议（扩频 / 加测温点 / 换夹具 / 重测）
           → 喂给 SciTX C_M 的准入信号（rb_method_spread_dex 等）

诚实边界:这里的"数据质量不确定度"是**分析置信度启发式**（频率窗、过零点、谷底
位置、噪声粗糙度），**不是臆造的材料学阈值**;它只用于(a)膨胀报告区间、(b)触发补测
建议、(c)决定是否弃权——绝不直接产生新的材料数值主张。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ---- 决策枚举 -----------------------------------------------------------------
REPORT = "REPORT"                       # 可信，给点估 + 区间
REPORT_CONDITIONAL = "REPORT_CONDITIONAL"  # 给值但降级（兜底/边界/中等不确定）
ABSTAIN = "ABSTAIN"                     # 拒绝给值（方法严重分歧或数据不足）

# ---- 主动测量动作枚举 ---------------------------------------------------------
EXTEND_FREQ_HIGH = "EXTEND_FREQ_HIGH"   # 高频端未见实轴截距 → 向上扩频
EXTEND_FREQ_LOW = "EXTEND_FREQ_LOW"     # 低频端未平台 → 向下扩频
CHANGE_FIXTURE = "CHANGE_FIXTURE"       # 高频寄生电感 → 检查夹具/接线
REMEASURE = "REMEASURE"                 # 噪声过大 → 重测/增积分
ADD_TEMP_POINT = "ADD_TEMP_POINT"       # 温度序列稀疏/断点附近 → 加测温点


@dataclass
class RbPosterior:
    """对数域贝叶斯模型平均(BMA)得到的 Rb 后验。"""
    rb_ohm: Optional[float]
    log10_rb: Optional[float]
    ci95_low_ohm: Optional[float]
    ci95_high_ohm: Optional[float]
    sigma_log10_total: float            # 总不确定度（dex）
    u_method_dex: float                 # 方法间分歧分量（可信集 log10 标准差）
    u_data_dex: float                   # 数据质量分量（分析置信度启发式）
    n_applicable: int
    n_credible: int
    weights: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rb_ohm": self.rb_ohm,
            "log10_rb": self.log10_rb,
            "ci95_low_ohm": self.ci95_low_ohm,
            "ci95_high_ohm": self.ci95_high_ohm,
            "sigma_log10_total": self.sigma_log10_total,
            "u_method_dex": self.u_method_dex,
            "u_data_dex": self.u_data_dex,
            "n_applicable": self.n_applicable,
            "n_credible": self.n_credible,
            "weights": dict(self.weights),
        }


@dataclass
class ActiveRequest:
    """一条主动测量建议（agent 可据此扩展动作空间，对接 C³-Harness）。"""
    action: str
    reason: str
    detail: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"action": self.action, "reason": self.reason, "detail": self.detail}


@dataclass
class RbActResult:
    decision: str                        # REPORT | REPORT_CONDITIONAL | ABSTAIN
    posterior: RbPosterior
    legacy_rb_ohm: Optional[float]
    legacy_method: Optional[str]
    abstain_reasons: List[str] = field(default_factory=list)
    active_requests: List[ActiveRequest] = field(default_factory=list)
    features: Dict[str, Any] = field(default_factory=dict)
    admission_signals: Dict[str, Any] = field(default_factory=dict)
    delta: Dict[str, Any] = field(default_factory=dict)
    temperature_K: Optional[float] = None

    def reported(self) -> bool:
        return self.decision in (REPORT, REPORT_CONDITIONAL)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision": self.decision,
            "temperature_K": self.temperature_K,
            "posterior": self.posterior.to_dict(),
            "legacy_rb_ohm": self.legacy_rb_ohm,
            "legacy_method": self.legacy_method,
            "abstain_reasons": list(self.abstain_reasons),
            "active_requests": [a.to_dict() for a in self.active_requests],
            "features": dict(self.features),
            "admission_signals": dict(self.admission_signals),
            "delta": dict(self.delta),
        }
