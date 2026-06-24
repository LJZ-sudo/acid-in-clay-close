# -*- coding: utf-8 -*-
"""Skill 撤销 + 历史影响查询请求（WP2-e / PC-Skills）。

撤销一个 Skill 版本时:① 置 REVOKED、作废证书(registry.revoke);② 产出一个
**历史影响查询请求** RevocationImpactRequest —— 列出"该 Skill 版本产出过哪些证据/决策需重评"。
真正的失效传播(沿证据超图重算主张、重建 BO)由 E-Mem(WP3)消费本请求执行;
本模块只负责"撤销 + 生成可被 E-Mem 接管的影响请求",不在此假装已重建 BO。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .registry import SkillRegistry


@dataclass
class RevocationImpactRequest:
    skill_id: str
    version: str
    reason: str
    revoked_at: str = field(default_factory=lambda: datetime.now(timezone.utc).astimezone().isoformat())
    affected_evidence_ids: List[str] = field(default_factory=list)
    # E-Mem(WP3)接入前,该请求是"待处理":downstream_propagation_done=False
    downstream_propagation_done: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "skill_id": self.skill_id, "version": self.version, "reason": self.reason,
            "revoked_at": self.revoked_at, "affected_evidence_ids": list(self.affected_evidence_ids),
            "downstream_propagation_done": self.downstream_propagation_done,
        }


def revoke_skill(
    registry: SkillRegistry,
    skill_id: str,
    reason: str,
    *,
    evidence_index: Optional[Dict[str, List[str]]] = None,
) -> RevocationImpactRequest:
    """撤销 Skill 并生成历史影响请求。

    evidence_index: 可选 {skill_id: [evidence_id,...]} —— 哪些证据由该 Skill 产出(由
    EvidenceBundle/事务账本维护)。E-Mem 未接入时该列表可空,请求仍记录 downstream 未传播。
    """
    contract = registry.get(skill_id)
    registry.revoke(skill_id, reason=reason)
    affected = list((evidence_index or {}).get(skill_id, []))
    return RevocationImpactRequest(
        skill_id=skill_id, version=contract.version, reason=reason,
        affected_evidence_ids=affected, downstream_propagation_done=False)
