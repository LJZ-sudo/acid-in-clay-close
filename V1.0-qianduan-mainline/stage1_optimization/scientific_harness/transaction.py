# -*- coding: utf-8 -*-
"""证据事务编排（WP1-d / SciTX 2.0 核心）。

把 WP1-a(C_M 按用途)、WP1-b(C_E 绑定主张)、WP1-c(三类 ID + 多见证 C_P)缝成一条
**唯一权威流**:
  尝试(ExecutionAttempt) → 多见证 → 物理作用 C_P → 计量准入 C_M(用途) → 证据准入 C_E(主张)
  → 是否进入 BO。
强制不变量(对齐 docx §3.2):
  ① 超时先核对、禁盲目重试(blind_retry 恒 0);
  ② ¬C_P(confirmed) ⇒ C_M/C_E 全 REJECT;
  ③ ¬C_E(UPDATE_BO) ⇒ 不入 BO;
  ④ 每次事务有不同的 transaction_id / attempt_id / physical_effect_id / evidence_id。

不替代 Stage0 科学算法,也不直接控制仪器(仪器经依赖注入,可为真机适配层或 fault_injection 模拟器)。
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .commits import PhysicalCommit
from .event_store import EventStore
from .witness import ExecutionAttempt, infer_physical_effect, witnesses_from_instrument
from .admission import (
    IntendedUse, assess_use, assess_claim_admission, UseAdmission, ClaimAdmission,
)


@dataclass
class ClaimRequest:
    claim_id: str
    intended_use: str
    requested_level: str


@dataclass
class TransactionResult:
    transaction_id: str
    command_id: str
    attempt_id: str
    physical_effect_id: str
    c_p: str                                 # PhysicalCommit 状态
    physical_occurred: str                   # confirmed | not_occurred | possible | unknown
    use_admissions: Dict[str, Dict[str, Any]]   # C_M(use)
    claim_admissions: List[Dict[str, Any]]      # C_E(claim)
    evidence_id: Optional[str]               # 仅在可提交时生成
    entered_bo: bool
    blind_retry_count: int
    reconciled: bool
    reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "transaction_id": self.transaction_id,
            "command_id": self.command_id,
            "attempt_id": self.attempt_id,
            "physical_effect_id": self.physical_effect_id,
            "c_p": self.c_p,
            "physical_occurred": self.physical_occurred,
            "use_admissions": self.use_admissions,
            "claim_admissions": self.claim_admissions,
            "evidence_id": self.evidence_id,
            "entered_bo": self.entered_bo,
            "blind_retry_count": self.blind_retry_count,
            "reconciled": self.reconciled,
            "reasons": self.reasons,
        }


class EvidenceTransaction:
    """一次"意图→物理执行→证据提交"的事务。process() 返回 TransactionResult。"""

    def __init__(self, event_store: Optional[EventStore] = None):
        self.store = event_store or EventStore()

    def process(
        self,
        *,
        command_id: str,
        command: str,
        instrument: Any,
        measurement_signals: Dict[str, Any],
        intended_uses: Optional[List[str]] = None,
        target_claims: Optional[List[ClaimRequest]] = None,
        expected_sample_id: Optional[str] = None,
    ) -> TransactionResult:
        txn_id = str(uuid.uuid4())
        intended_uses = intended_uses or list(IntendedUse.ALL)
        target_claims = target_claims or []
        reasons: List[str] = []

        # ---- 1) 软件尝试 ----
        dispatch = instrument.dispatch(command_id)
        ack = bool(getattr(dispatch, "ack_received", not getattr(dispatch, "timed_out", False)))
        timed_out = bool(getattr(dispatch, "timed_out", False))
        attempt = ExecutionAttempt.make(command_id, command=command, ack_received=ack, timed_out=timed_out)
        self.store.append("attempt", {"transaction_id": txn_id, "attempt_id": attempt.attempt_id,
                                       "timed_out": timed_out})
        reconciled = timed_out          # 超时即进入"先核对"语义(下面用见证核对,不重试)
        blind_retry = 0                 # 不变量①:核对前绝不重试

        # ---- 2) 多见证 → 物理作用 C_P(不变量②的依据)----
        witnesses = witnesses_from_instrument(instrument, command_id, ack_received=ack)
        effect = infer_physical_effect(command_id, witnesses, expected_sample_id=expected_sample_id)
        c_p = effect.to_commit_status()
        self.store.append("physical_effect", {"transaction_id": txn_id, **effect.to_dict()})

        # ---- 3) C_M(用途)----  仅当物理确认才评计量;否则全 REJECT
        use_adm: Dict[str, UseAdmission] = {}
        physically_confirmed = (effect.occurred == "confirmed")
        if not physically_confirmed:
            reasons.append(f"C_P_not_confirmed:{effect.occurred}")
            from .admission import REJECT
            for u in intended_uses:
                use_adm[u] = UseAdmission(u, REJECT, "C0", ["C_P_NOT_CONFIRMED"])
        else:
            for u in intended_uses:
                use_adm[u] = assess_use(u, measurement_signals)
        self.store.append("metrological_commit",
                          {"transaction_id": txn_id, "uses": {u: a.status for u, a in use_adm.items()}})

        # ---- 4) C_E(主张)----
        claim_adm: List[ClaimAdmission] = []
        for cr in target_claims:
            if not physically_confirmed:
                from .admission import REJECT
                claim_adm.append(ClaimAdmission(
                    evidence_id="", claim_id=cr.claim_id, intended_use=cr.intended_use,
                    requested_level=cr.requested_level, cm_status=REJECT, ce_status=REJECT,
                    granted_level="C0", reason_codes=["C_P_NOT_CONFIRMED"]))
            else:
                claim_adm.append(assess_claim_admission(
                    evidence_id=f"E-{txn_id[:8]}", claim_id=cr.claim_id,
                    intended_use=cr.intended_use, requested_level=cr.requested_level,
                    signals=measurement_signals))
        self.store.append("epistemic_commit",
                          {"transaction_id": txn_id,
                           "claims": [{"claim_id": c.claim_id, "ce": c.ce_status,
                                       "granted": c.granted_level} for c in claim_adm]})

        # ---- 5) 是否进入 BO(不变量③:¬C_E(UPDATE_BO) ⇒ 不入)----
        bo_use = use_adm.get(IntendedUse.UPDATE_BO)
        entered_bo = bool(physically_confirmed and bo_use is not None and bo_use.admitted())
        evidence_id = f"E-{txn_id[:8]}" if physically_confirmed else None
        self.store.append("bo_admission", {"transaction_id": txn_id, "entered_bo": entered_bo,
                                           "evidence_id": evidence_id})

        return TransactionResult(
            transaction_id=txn_id, command_id=command_id, attempt_id=attempt.attempt_id,
            physical_effect_id=effect.physical_effect_id, c_p=c_p,
            physical_occurred=effect.occurred,
            use_admissions={u: a.to_dict() for u, a in use_adm.items()},
            claim_admissions=[c.to_dict() for c in claim_adm],
            evidence_id=evidence_id, entered_bo=entered_bo,
            blind_retry_count=blind_retry, reconciled=reconciled,
            reasons=reasons + effect.reasons)
