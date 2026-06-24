# -*- coding: utf-8 -*-
"""Scientific Skill 合同与证书（M5-C）。"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


class Lifecycle:
    DRAFT = "DRAFT"
    SIMULATION_VALIDATED = "SIMULATION_VALIDATED"
    SHADOW = "SHADOW"
    CANARY = "CANARY"
    VALIDATED = "VALIDATED"
    DEGRADED = "DEGRADED"          # 成功率/QC 漂移 → 限制用途,需重新验证
    SUSPENDED = "SUSPENDED"        # 固件/代码漂移 → 暂停新事务,需重新认证
    REVOKED = "REVOKED"            # 证书撤销 → 历史影响须重评
    DEPRECATED = "DEPRECATED"
    # 只有 VALIDATED 允许进入控制面自动执行(DEGRADED/SUSPENDED/REVOKED 一律不许)
    CONTROL_PLANE_ALLOWED = frozenset({VALIDATED})


@dataclass
class ScientificSkillContract:
    skill_id: str
    version: str
    input_schema: Dict[str, Any] = field(default_factory=dict)
    output_schema: Dict[str, Any] = field(default_factory=dict)
    applicability_domain: Dict[str, Any] = field(default_factory=dict)   # 如 {R:[0,1.04], N:[0.5,1.3]}
    preconditions: List[str] = field(default_factory=list)               # 能力 token(消费)
    postconditions: List[str] = field(default_factory=list)              # 能力 token(产出)
    physical_side_effects: List[str] = field(default_factory=list)
    failure_modes: List[str] = field(default_factory=list)
    validators: List[str] = field(default_factory=list)
    required_evidence_level: str = "PRIMARY"
    autonomy_level: str = "ADVISORY"   # ADVISORY | SHADOW | CANARY | AUTONOMOUS

    @property
    def contract_hash(self) -> str:
        payload = json.dumps({
            "skill_id": self.skill_id, "version": self.version,
            "input_schema": self.input_schema, "output_schema": self.output_schema,
            "applicability_domain": self.applicability_domain,
            "preconditions": sorted(self.preconditions),
            "postconditions": sorted(self.postconditions),
            "validators": sorted(self.validators),
            "required_evidence_level": self.required_evidence_level,
        }, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def in_domain(self, context: Dict[str, Any]) -> bool:
        """context 是否落在适用域(数值参数检查区间;缺项视为不约束)。"""
        for key, dom in self.applicability_domain.items():
            if key not in context:
                return False
            v = context[key]
            if isinstance(dom, (list, tuple)) and len(dom) == 2 and all(isinstance(d, (int, float)) for d in dom):
                if not (dom[0] <= v <= dom[1]):
                    return False
            elif isinstance(dom, (list, tuple)):
                if v not in dom:
                    return False
        return True


@dataclass
class SkillCertificate:
    skill_id: str
    version: str
    applicability_domain: Dict[str, Any]
    validators_passed: List[str]
    risk_estimate: float
    risk_upper_bound: float
    contract_hash: str
    code_hash: str
    lifecycle_state: str
    expiry: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
