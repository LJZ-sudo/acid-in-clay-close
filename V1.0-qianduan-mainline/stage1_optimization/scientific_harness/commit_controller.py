# -*- coding: utf-8 -*-
"""科学提交控制器（M5-A 核心）。

三道闸:物理提交 C_P → 计量提交 C_M → 认知提交 C_E。
强制不变量:`¬C_E ⇒ 不入 {BO, 主张, 长期记忆}`;超时先核对、禁盲目重试。
C_M/C_E 复用 M1-4 evidence_admission(依赖注入,可测);C_M 额外叠加物理计量前置
(温度平衡 / 校准有效,这些是 analysis 层 admission 不知道的硬件计量条件)。
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .commits import PhysicalCommit, MetrologicalCommit, EpistemicCommit
from .event_store import EventStore
from .reconciler import reconcile

# 复用 M1-4 证据准入作 C_M/C_E 核心
_ANALYSIS_DIR = Path(__file__).resolve().parents[2] / "stage0_measurement" / "modules" / "analysis"
if str(_ANALYSIS_DIR) not in sys.path:
    sys.path.insert(0, str(_ANALYSIS_DIR))


def _default_admissibility(**kwargs):
    import evidence_admission as EA
    return EA.assess_admissibility(**kwargs)


_ADM_TO_CE = {
    "PRIMARY": EpistemicCommit.PRIMARY_EVIDENCE,
    "SENSITIVITY_ONLY": EpistemicCommit.SENSITIVITY_ONLY,
    "DIAGNOSTIC_ONLY": EpistemicCommit.DIAGNOSTIC_ONLY,
    "REJECTED": EpistemicCommit.REJECTED,
}


@dataclass
class CommitResult:
    command_id: str
    physical_commit: str
    metrological_commit: str
    epistemic_commit: str
    entered_bo: bool
    blind_retry_count: int
    reconciled: bool
    reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "command_id": self.command_id,
            "physical_commit": self.physical_commit,
            "metrological_commit": self.metrological_commit,
            "epistemic_commit": self.epistemic_commit,
            "entered_bo": self.entered_bo,
            "blind_retry_count": self.blind_retry_count,
            "reconciled": self.reconciled,
            "reasons": self.reasons,
        }


class CommitController:
    def __init__(self, event_store: Optional[EventStore] = None,
                 admissibility_fn: Optional[Callable[..., Any]] = None):
        self.store = event_store or EventStore()
        self.admissibility_fn = admissibility_fn or _default_admissibility

    def process(self, command_id: str, instrument: Any, measurement: Dict[str, Any]) -> CommitResult:
        reasons: List[str] = []
        blind_retry = 0
        reconciled = False

        # ---- C_P 物理提交 ----
        dispatch = instrument.dispatch(command_id)
        self.store.append("dispatch", {"command_id": command_id, "timed_out": dispatch.timed_out})
        if dispatch.timed_out:
            # 不变量:超时先核对、禁盲目重试
            rec = reconcile(command_id, instrument, instrument.sample_id)
            reconciled = True
            blind_retry = 0  # 本控制器在 reconcile 前从不重试
            c_p = rec.physical_status
            reasons += rec.reasons
            self.store.append("reconcile", {"command_id": command_id,
                                            "physical_status": c_p, "reasons": rec.reasons})
        else:
            file_ok = bool(instrument.query_output_file(command_id))
            c_p = PhysicalCommit.EFFECT_OBSERVED if file_ok else PhysicalCommit.PARTIAL
        self.store.append("physical_commit", {"command_id": command_id, "status": c_p})

        # ---- C_M 计量提交 ----
        if not PhysicalCommit.is_committed(c_p):
            c_m = MetrologicalCommit.INVALID
            reasons.append("C_P_not_committed")
        elif not getattr(instrument, "temp_equilibrated", True):
            c_m = MetrologicalCommit.INVALID
            reasons.append("temperature_not_equilibrated")
        elif not getattr(instrument, "calibration_valid", True):
            c_m = MetrologicalCommit.INVALID
            reasons.append("calibration_expired")
        else:
            adm = self.admissibility_fn(
                qa_failed=measurement.get("qa_failed", False),
                kk_mu_median=measurement.get("kk_mu_median"),
                rb_method_spread_dex=measurement.get("rb_method_spread_dex"),
                uncertainty_status=measurement.get("uncertainty_status", "PARTIAL"),
            )
            if adm.qa_status == "FAIL" or adm.kk_status == "FAIL":
                c_m = MetrologicalCommit.INVALID
            elif adm.kk_status == "WARN":
                c_m = MetrologicalCommit.CONDITIONAL
            else:
                c_m = MetrologicalCommit.VALID
            reasons += [f"adm:{r}" for r in adm.reason_codes]
        self.store.append("metrological_commit", {"command_id": command_id, "status": c_m})

        # ---- C_E 认知提交(需 C_P∧C_M)----
        if not PhysicalCommit.is_committed(c_p) or not MetrologicalCommit.is_committed(c_m):
            c_e = EpistemicCommit.REJECTED if c_m == MetrologicalCommit.INVALID else EpistemicCommit.DIAGNOSTIC_ONLY
        else:
            adm = self.admissibility_fn(
                qa_failed=measurement.get("qa_failed", False),
                kk_mu_median=measurement.get("kk_mu_median"),
                rb_method_spread_dex=measurement.get("rb_method_spread_dex"),
                uncertainty_status=measurement.get("uncertainty_status", "PARTIAL"),
            )
            c_e = _ADM_TO_CE.get(adm.scientific_admissibility, EpistemicCommit.REJECTED)
        self.store.append("epistemic_commit", {"command_id": command_id, "status": c_e})

        # ---- 不变量:¬C_E ⇒ 不入 BO ----
        entered_bo = EpistemicCommit.is_committed(c_e)
        self.store.append("bo_admission", {"command_id": command_id, "entered_bo": entered_bo})

        return CommitResult(
            command_id=command_id, physical_commit=c_p, metrological_commit=c_m,
            epistemic_commit=c_e, entered_bo=entered_bo, blind_retry_count=blind_retry,
            reconciled=reconciled, reasons=reasons)
