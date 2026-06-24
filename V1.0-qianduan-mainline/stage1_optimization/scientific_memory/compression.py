# -*- coding: utf-8 -*-
"""证据保真压缩 + 压缩证书（WP3-d / E-Mem）。

GPT-3/TierMem:压缩目标不是最短摘要,而是**固定预算下最小化科学失真**。关键字段
(适用条件、反证、可推翻条件、主张等级、来源)设为**零损失约束**。摘要只有在通过验证后
才发 CompressionCertificate;任一约束破坏 → 拒绝该摘要(降级或回溯原始证据)。

验证(docx §5.6):
  claim_level(summary) ≤ claim_level(source)   # 主张不增强
  critical_conditions_lost == 0                # 条件零损失
  counterevidence_lost == 0                    # 反证零损失
  provenance_recoverable == True               # 来源可恢复(摘要指回 source_node_ids)
  action_divergence == 0                       # 决策不变(可选 decision_probe 回放)
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

_C_ORDER = ["C0", "C1", "C2", "C3", "C4", "C5"]


@dataclass
class MemoryState:
    """压缩前/后的记忆状态(用于验证关键字段是否保真)。"""
    claim_levels: Dict[str, str] = field(default_factory=dict)   # claim_id -> C-level
    conditions: Set[str] = field(default_factory=set)            # 适用条件(batch/branch/humidity/...)
    counterevidence: Set[str] = field(default_factory=set)       # 反证根 id
    source_node_ids: List[str] = field(default_factory=list)

    def max_level(self) -> str:
        if not self.claim_levels:
            return "C0"
        return max(self.claim_levels.values(), key=lambda c: _C_ORDER.index(c))


@dataclass
class CompressionCertificate:
    compression_id: str
    source_node_ids: List[str]
    preserved_counterevidence: List[str]
    preserved_conditions: List[str]
    claim_level_before: str
    claim_level_after: str
    action_divergence: float
    raw_recovery_pointer: Optional[str]
    ok: bool
    reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "compression_id": self.compression_id,
            "source_node_ids": list(self.source_node_ids),
            "preserved_counterevidence": list(self.preserved_counterevidence),
            "preserved_conditions": list(self.preserved_conditions),
            "claim_level_before": self.claim_level_before,
            "claim_level_after": self.claim_level_after,
            "action_divergence": self.action_divergence,
            "raw_recovery_pointer": self.raw_recovery_pointer,
            "ok": self.ok, "reasons": self.reasons,
        }


def compress_and_verify(
    source: MemoryState,
    summary: MemoryState,
    *,
    decision_probe: Optional[Callable[[MemoryState], Any]] = None,
    raw_recovery_pointer: Optional[str] = None,
) -> Tuple[bool, CompressionCertificate]:
    """验证摘要是否保真;通过才发证(ok=True)。任何关键字段失真 → ok=False。"""
    reasons: List[str] = []

    lvl_before = source.max_level()
    lvl_after = summary.max_level()
    amplified = _C_ORDER.index(lvl_after) > _C_ORDER.index(lvl_before)
    if amplified:
        reasons.append(f"CLAIM_LEVEL_AMPLIFIED:{lvl_before}->{lvl_after}")

    conditions_lost = source.conditions - summary.conditions
    if conditions_lost:
        reasons.append(f"CRITICAL_CONDITIONS_LOST:{sorted(conditions_lost)}")

    counter_lost = source.counterevidence - summary.counterevidence
    if counter_lost:
        reasons.append(f"COUNTEREVIDENCE_LOST:{sorted(counter_lost)}")

    provenance_recoverable = bool(summary.source_node_ids) and \
        set(summary.source_node_ids).issubset(set(source.source_node_ids))
    if not provenance_recoverable:
        reasons.append("PROVENANCE_NOT_RECOVERABLE")

    action_divergence = 0.0
    if decision_probe is not None:
        a_src = decision_probe(source)
        a_sum = decision_probe(summary)
        if a_src != a_sum:
            action_divergence = 1.0
            reasons.append(f"ACTION_DIVERGENCE:{a_src}!={a_sum}")

    ok = (not amplified) and (not conditions_lost) and (not counter_lost) \
        and provenance_recoverable and action_divergence == 0.0

    cert = CompressionCertificate(
        compression_id=f"CMP-{uuid.uuid4().hex[:8]}",
        source_node_ids=list(summary.source_node_ids),
        preserved_counterevidence=sorted(summary.counterevidence),
        preserved_conditions=sorted(summary.conditions),
        claim_level_before=lvl_before, claim_level_after=lvl_after,
        action_divergence=action_divergence,
        raw_recovery_pointer=raw_recovery_pointer,
        ok=ok, reasons=reasons or ["OK"])
    return ok, cert
