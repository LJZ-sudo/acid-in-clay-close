# -*- coding: utf-8 -*-
"""Skill 注册表 + 生命周期 + 控制面准入 + 组合兼容（M5-C）。"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple

from .contracts import ScientificSkillContract, SkillCertificate, Lifecycle


class SkillRegistry:
    def __init__(self):
        self._contracts: Dict[str, ScientificSkillContract] = {}
        self._state: Dict[str, str] = {}
        self._cert: Dict[str, SkillCertificate] = {}

    def register(self, contract: ScientificSkillContract,
                 state: str = Lifecycle.DRAFT) -> None:
        self._contracts[contract.skill_id] = contract
        self._state[contract.skill_id] = state

    def get(self, skill_id: str) -> ScientificSkillContract:
        return self._contracts[skill_id]

    def state(self, skill_id: str) -> str:
        return self._state.get(skill_id, "UNKNOWN")

    def certify(self, skill_id: str, validator_results: Dict[str, bool],
                risk_estimate: float, risk_upper_bound: float,
                code_hash: str = "") -> Tuple[bool, Optional[SkillCertificate]]:
        """所有 validator 通过 → 颁发证书 + 置 VALIDATED;否则保持原状态。"""
        c = self._contracts[skill_id]
        passed = [v for v, ok in validator_results.items() if ok]
        all_ok = len(passed) == len(c.validators) and all(validator_results.get(v, False) for v in c.validators)
        if not all_ok:
            return False, None
        cert = SkillCertificate(
            skill_id=skill_id, version=c.version,
            applicability_domain=c.applicability_domain,
            validators_passed=passed,
            risk_estimate=risk_estimate, risk_upper_bound=risk_upper_bound,
            contract_hash=c.contract_hash, code_hash=code_hash,
            lifecycle_state=Lifecycle.VALIDATED,
        )
        self._cert[skill_id] = cert
        self._state[skill_id] = Lifecycle.VALIDATED
        return True, cert

    def certificate(self, skill_id: str) -> Optional[SkillCertificate]:
        return self._cert.get(skill_id)

    # ---------- 漂移降级 / 撤销(WP2-e) ---------- #
    def degrade(self, skill_id: str, reason: str = "") -> None:
        """成功率/QC 漂移 → 置 DEGRADED(退出控制面,但保留证书供审计)。"""
        if skill_id in self._contracts:
            self._state[skill_id] = Lifecycle.DEGRADED

    def suspend(self, skill_id: str, reason: str = "") -> None:
        """固件/代码漂移 → 置 SUSPENDED,**作废证书**(必须重新认证才能再执行)。"""
        if skill_id in self._contracts:
            self._state[skill_id] = Lifecycle.SUSPENDED
            self._cert.pop(skill_id, None)

    def revoke(self, skill_id: str, reason: str = "") -> None:
        """撤销 → 置 REVOKED,作废证书;历史影响由 revocation.py + E-Mem(WP3)重评。"""
        if skill_id in self._contracts:
            self._state[skill_id] = Lifecycle.REVOKED
            self._cert.pop(skill_id, None)

    # ---------- 控制面准入(只许 VALIDATED + 域内) ---------- #
    def can_execute(self, skill_id: str, context: Dict[str, Any]) -> Tuple[bool, str]:
        if skill_id not in self._contracts:
            return False, "unknown_skill"
        if self._state.get(skill_id) not in Lifecycle.CONTROL_PLANE_ALLOWED:
            return False, f"not_validated(state={self._state.get(skill_id)})"
        if skill_id not in self._cert:
            return False, "no_certificate"
        if not self._contracts[skill_id].in_domain(context):
            return False, "out_of_certified_domain"
        return True, "ok"

    # ---------- 组合兼容:post(S_i) ⊨ pre(S_{i+1}) ---------- #
    def check_composition(
        self, chain: List[str], provided: Optional[set] = None,
    ) -> Tuple[bool, List[Dict[str, Any]]]:
        """链中每相邻对:上游 postconditions 必须覆盖下游 preconditions。

        provided: 开局即由系统/上下文满足的**环境前置**(如 calibration_valid /
        instrument_reserved)——它们不是上游 Skill 的产出 token,故作为初始 available 注入,
        避免把环境前置误报为"缺失"。默认空(向后兼容)。
        """
        details = []
        ok_all = True
        available: set = set(provided or set())
        for sid in chain:
            c = self._contracts[sid]
            missing = [p for p in c.preconditions if p not in available]
            step_ok = (len(missing) == 0)
            details.append({"skill": sid, "missing_preconditions": missing, "ok": step_ok})
            if not step_ok:
                ok_all = False
            available.update(c.postconditions)
        return ok_all, details
