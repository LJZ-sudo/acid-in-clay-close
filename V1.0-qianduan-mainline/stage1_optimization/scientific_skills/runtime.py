# -*- coding: utf-8 -*-
"""Skill 运行时:执行前检查 + 双账户 gate + Evidence Bundle（WP2-d / WP2-f）。

执行决策(docx §6.5):仅当 证书有效 ∧ 状态/参数在认证包络内 ∧ 风险清算通过 才允许自动执行;
否则按严重度降级为 simulate/shadow/human_approval/reject。
**双账户(WP2-f)**:执行权由 RiskClearing 决定,**有意忽略 agent 自报置信度**——
Agent 不能因"更自信"获得更多执行权。每次执行产出 EvidenceBundle(可挂到 SciTX 事务)。
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .registry import SkillRegistry
from .dual_account import RiskClearing


# 执行决策
ALLOW = "ALLOW"
SHADOW = "SHADOW"
HUMAN_APPROVAL = "HUMAN_APPROVAL"
REJECT = "REJECT"


@dataclass
class ExecutionDecision:
    skill_id: str
    decision: str                # ALLOW | SHADOW | HUMAN_APPROVAL | REJECT
    reasons: List[str] = field(default_factory=list)

    def allowed(self) -> bool:
        return self.decision == ALLOW


@dataclass
class EvidenceBundle:
    skill_id: str
    version: str
    bundle_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).astimezone().isoformat())
    certificate_id: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)
    witnesses: List[str] = field(default_factory=list)
    outputs: Dict[str, Any] = field(default_factory=dict)
    transaction_id: Optional[str] = None
    decision: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "skill_id": self.skill_id, "version": self.version, "bundle_id": self.bundle_id,
            "created_at": self.created_at, "certificate_id": self.certificate_id,
            "context": self.context, "witnesses": list(self.witnesses),
            "outputs": self.outputs, "transaction_id": self.transaction_id,
            "decision": self.decision,
        }


def decide_execution(
    registry: SkillRegistry,
    skill_id: str,
    context: Dict[str, Any],
    *,
    risk_clearing: Optional[RiskClearing] = None,
    uncertainty: float = 0.0,
    claimed_confidence: Optional[float] = None,   # 故意接收但忽略(双账户分离)
) -> ExecutionDecision:
    """执行前决策。证书/状态/域 + 风险清算共同决定;忽略自报置信度。"""
    risk_clearing = risk_clearing or RiskClearing()
    reasons: List[str] = []

    can, why = registry.can_execute(skill_id, context)
    if not can:
        # 未认证/超域:若处于 SHADOW 生命周期则可 shadow 观察,否则拒
        if registry.state(skill_id) == "SHADOW":
            return ExecutionDecision(skill_id, SHADOW, [f"not_executable:{why}", "lifecycle_shadow"])
        return ExecutionDecision(skill_id, REJECT, [f"not_executable:{why}"])

    cert = registry.certificate(skill_id)
    risk_est = cert.risk_estimate if cert else 1.0
    cleared = risk_clearing.act(
        cert_valid=True, in_domain=True,
        risk_estimate=risk_est, uncertainty=uncertainty,
        claimed_confidence=claimed_confidence,     # 被 RiskClearing 忽略
    )
    if not cleared:
        reasons.append(f"risk_clearing_failed(risk={risk_est}+unc={uncertainty}>r_max={risk_clearing.r_max})")
        return ExecutionDecision(skill_id, HUMAN_APPROVAL, reasons)
    return ExecutionDecision(skill_id, ALLOW, ["ok"])


def build_evidence_bundle(
    registry: SkillRegistry,
    skill_id: str,
    *,
    context: Dict[str, Any],
    outputs: Dict[str, Any],
    witnesses: Optional[List[str]] = None,
    transaction_id: Optional[str] = None,
    decision: Optional[str] = None,
) -> EvidenceBundle:
    """执行后构造 Evidence Bundle(绑定证书 + 见证 + 输出 + 事务)。"""
    contract = registry.get(skill_id)
    cert = registry.certificate(skill_id)
    return EvidenceBundle(
        skill_id=skill_id, version=contract.version,
        certificate_id=(cert.contract_hash[:16] if cert else None),
        context=dict(context), witnesses=list(witnesses or []),
        outputs=dict(outputs), transaction_id=transaction_id, decision=decision,
    )


def check_chain_executable(
    registry: SkillRegistry, chain: List[str], context: Dict[str, Any],
    provided: Optional[set] = None,
) -> Dict[str, Any]:
    """链级前置:组合 post⊨pre(provided=环境前置) + 每个 Skill 可执行(证书+域)。"""
    comp_ok, comp_detail = registry.check_composition(chain, provided=provided)
    exec_detail = []
    exec_ok = True
    for sid in chain:
        can, why = registry.can_execute(sid, context)
        exec_detail.append({"skill": sid, "can_execute": can, "why": why})
        if not can:
            exec_ok = False
    return {"composition_ok": comp_ok, "composition": comp_detail,
            "all_executable": exec_ok, "executable": exec_detail,
            "ok": bool(comp_ok and exec_ok)}
