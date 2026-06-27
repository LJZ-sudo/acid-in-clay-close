# -*- coding: utf-8 -*-
"""R²-Memory 数据模型（ESAS-OS 2.0 / §10.2）。

角色隔离 + 可撤销 + 多轮记忆的最小可信类型:
  - Role            四类科学角色(测量/分析/优化/审稿),决定读投影与写权限;
  - Use             记忆项的用途枚举(训练标签/迁移参照/主张支持/...),来源域守卫的抓手;
  - MemoryItem      带 allowed/forbidden 用途、可见/可写角色、主张等级、状态、来源域;
  - RoundState      单 Agent 多轮的结构化交接(目标/已知/未决/下一步),取代裸文本上下文。
不替换 SQLite 证据图/`history_bridge`,旁挂互补(见 store.py)。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

# ---- 写入门裁决 / 记忆项状态 -------------------------------------------------
PROPOSED = "PROPOSED"
ACTIVE = "ACTIVE"
CONTESTED = "CONTESTED"
REJECTED = "REJECTED"
INVALID = "INVALID"

# 写门返回
ACCEPT = "ACCEPT"
REBASE_REQUIRED = "REBASE_REQUIRED"
DENY = "DENY"


class Role:
    MEASUREMENT = "measurement"
    ANALYSIS = "analysis"
    OPTIMIZATION = "optimization"
    REVIEW = "review"
    ALL = (MEASUREMENT, ANALYSIS, OPTIMIZATION, REVIEW)


class Use:
    """记忆项用途。来源域守卫的关键:同一条记忆对不同用途的合法性不同。"""
    TRAINING_LABEL = "training_label"          # 直接作 BO 训练标签(最强,跨域最危险)
    TRANSFER_REFERENCE = "transfer_reference"  # 迁移参照(只读启发,绝不作标签)
    CLAIM_SUPPORT = "claim_support"            # 进主张支持集
    PROMPT_CONTEXT = "prompt_context"          # 仅作 LLM 上下文
    DIAGNOSIS = "diagnosis"                    # 故障/异常诊断参考
    ALL = (TRAINING_LABEL, TRANSFER_REFERENCE, CLAIM_SUPPORT, PROMPT_CONTEXT, DIAGNOSIS)


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


@dataclass
class MemoryItem:
    item_id: str
    content: Dict[str, Any]
    author_role: str
    domain: str                                   # 来源域,如 acid_in_clay / biopolymer_clay
    allowed_uses: Set[str] = field(default_factory=set)
    forbidden_uses: Set[str] = field(default_factory=set)
    visible_to: Set[str] = field(default_factory=lambda: set(Role.ALL))
    writable_by: Set[str] = field(default_factory=set)
    claim_level: str = "C0"
    is_counterevidence: bool = False
    conditions: Set[str] = field(default_factory=set)   # 适用条件(批次/湿度/分支...)
    topic: Optional[str] = None                   # 同 topic 的 support/refute 并存 → CONTESTED
    polarity: str = "support"                     # support | refute
    status: str = PROPOSED
    based_on_version: int = 0                     # 写入时所基于的记忆版本(stale 检测)
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    def effective_uses(self) -> Set[str]:
        """净用途 = allowed − forbidden(forbidden 永远优先,杜绝自相矛盾放行)。"""
        return set(self.allowed_uses) - set(self.forbidden_uses)

    def allows(self, use: str) -> bool:
        return use in self.effective_uses()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_id": self.item_id, "author_role": self.author_role, "domain": self.domain,
            "allowed_uses": sorted(self.allowed_uses), "forbidden_uses": sorted(self.forbidden_uses),
            "visible_to": sorted(self.visible_to), "writable_by": sorted(self.writable_by),
            "claim_level": self.claim_level, "is_counterevidence": self.is_counterevidence,
            "conditions": sorted(self.conditions), "topic": self.topic, "polarity": self.polarity,
            "status": self.status, "based_on_version": self.based_on_version,
            "created_at": self.created_at, "updated_at": self.updated_at,
            "content": self.content,
        }


@dataclass
class RoundState:
    """单 Agent 多轮的结构化交接;取代"把上一轮整段文本塞回去"。"""
    round_id: int
    goal: str
    actor_role: str
    known: List[str] = field(default_factory=list)
    pending: List[str] = field(default_factory=list)
    next_step: str = ""
    resolved: List[str] = field(default_factory=list)   # 本轮解决了上一轮哪些 pending
    created_at: str = field(default_factory=_now)

    def handoff(self) -> Dict[str, Any]:
        return {
            "round_id": self.round_id, "goal": self.goal, "actor_role": self.actor_role,
            "known": list(self.known), "pending": list(self.pending),
            "next_step": self.next_step, "resolved": list(self.resolved),
        }


@dataclass
class WriteDecision:
    decision: str                                 # ACCEPT | REBASE_REQUIRED | DENY
    item_id: Optional[str] = None
    status: Optional[str] = None                  # 落库后的状态(ACTIVE/CONTESTED)
    reasons: List[str] = field(default_factory=list)

    def accepted(self) -> bool:
        return self.decision == ACCEPT
