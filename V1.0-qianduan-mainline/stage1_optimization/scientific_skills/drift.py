# -*- coding: utf-8 -*-
"""Skill 漂移检测（WP2-e / PC-Skills）。

固件/代码变化 → 证书失效(SUSPEND,须重认证);认证域内成功率/QC 通过率显著下降 → DEGRADE。
纯函数,输出建议动作(由调用方/runtime 执行 registry.suspend/degrade)。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


class DriftAction:
    NONE = "NONE"
    DEGRADE = "DEGRADE"
    SUSPEND = "SUSPEND"


@dataclass
class DriftAssessment:
    drifted: bool
    action: str                  # NONE | DEGRADE | SUSPEND
    kinds: List[str] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)


def detect_drift(
    *,
    baseline_code_hash: Optional[str] = None,
    current_code_hash: Optional[str] = None,
    baseline_firmware: Optional[str] = None,
    current_firmware: Optional[str] = None,
    baseline_success_rate: Optional[float] = None,
    current_success_rate: Optional[float] = None,
    success_drop_tolerance: float = 0.1,
) -> DriftAssessment:
    """检测代码/固件/成功率漂移。代码或固件变 → SUSPEND(最严);仅成功率掉 → DEGRADE。"""
    kinds: List[str] = []
    reasons: List[str] = []
    suspend = False
    degrade = False

    if baseline_code_hash is not None and current_code_hash is not None \
            and baseline_code_hash != current_code_hash:
        suspend = True
        kinds.append("code_hash_changed")
        reasons.append(f"code_hash {baseline_code_hash[:8]}→{current_code_hash[:8]}")

    if baseline_firmware is not None and current_firmware is not None \
            and baseline_firmware != current_firmware:
        suspend = True
        kinds.append("firmware_changed")
        reasons.append(f"firmware {baseline_firmware}→{current_firmware}")

    if baseline_success_rate is not None and current_success_rate is not None:
        drop = baseline_success_rate - current_success_rate
        if drop > success_drop_tolerance:
            degrade = True
            kinds.append("success_rate_drop")
            reasons.append(f"success_rate {baseline_success_rate:.3f}→{current_success_rate:.3f} "
                           f"(drop {drop:.3f} > tol {success_drop_tolerance})")

    if suspend:
        return DriftAssessment(True, DriftAction.SUSPEND, kinds, reasons)
    if degrade:
        return DriftAssessment(True, DriftAction.DEGRADE, kinds, reasons)
    return DriftAssessment(False, DriftAction.NONE, kinds, ["no_drift"])
