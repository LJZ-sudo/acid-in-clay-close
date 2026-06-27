# -*- coding: utf-8 -*-
"""R²-Memory 存储与治理（ESAS-OS 2.0 / §10.2）。

`AgentMemory`:角色隔离 / 可撤销 / 多轮的记忆层,旁挂在 SQLite 证据图之外。
分层(对齐 GPT-4 §R²):
  - **L0 不可变事件层**:append-only `_events`,任何变更只追加不改写 → `version()` = 事件数;
  - **L1 活动项**:`_items`(PROPOSED/ACTIVE/CONTESTED/REJECTED/INVALID);
  - **L3 角色上下文**:`read(role, use)` 给出经治理的角色投影 + 多轮 `RoundState`。

治理三闸(写入门 `propose`):
  1. **写权限**:author ∉ item.writable_by → DENY;
  2. **用途自洽 + 来源域守卫**:allowed∩forbidden≠∅ → DENY;`assert_use` 拦截 forbidden(如 S8 作 training_label);
  3. **stale 写**:based_on_version < 当前 version → REBASE_REQUIRED(乐观并发,旧版本写入被拒)。
通过后:同 topic 反极性 ACTIVE 已存在 → 双方 CONTESTED(禁"最后写入者胜出");否则 ACTIVE。

**决策回放**:`verify_compression(probe)` 复用 `compression.compress_and_verify`,验证压缩前后
top-1 动作 + 主张等级一致(决策保持性)。
"""
from __future__ import annotations

import uuid
from typing import Any, Callable, Dict, List, Optional, Set

from .models import (
    MemoryItem, RoundState, WriteDecision, Role, Use,
    PROPOSED, ACTIVE, CONTESTED, REJECTED, INVALID,
    ACCEPT, REBASE_REQUIRED, DENY, _now,
)
from ..compression import MemoryState, compress_and_verify, CompressionCertificate


class UsageViolation(PermissionError):
    """显式企图把记忆项用于其 forbidden_uses(如跨域训练标签)。"""


class AgentMemory:
    def __init__(self) -> None:
        self._items: Dict[str, MemoryItem] = {}
        self._events: List[Dict[str, Any]] = []          # L0 不可变事件层
        self._rounds: List[RoundState] = []

    # ---------- L0 事件层 ---------- #
    def _emit(self, kind: str, **payload: Any) -> None:
        self._events.append({"seq": len(self._events) + 1, "kind": kind,
                             "at": _now(), **payload})

    def version(self) -> int:
        """记忆版本 = L0 事件数(每次提交型变更 +1);stale 写检测的基准。"""
        return len(self._events)

    def events(self) -> List[Dict[str, Any]]:
        return [dict(e) for e in self._events]           # 只读副本

    # ---------- 写入门 ---------- #
    def propose(self, item: MemoryItem) -> WriteDecision:
        # 1) 写权限
        if item.writable_by and item.author_role not in item.writable_by:
            return WriteDecision(DENY, item.item_id, None,
                                 [f"ROLE_CANNOT_WRITE:{item.author_role}"])
        # 2) 用途自洽(forbidden 与 allowed 冲突 → 拒)
        conflict = set(item.allowed_uses) & set(item.forbidden_uses)
        if conflict:
            return WriteDecision(DENY, item.item_id, None,
                                 [f"USE_POLICY_CONTRADICTION:{sorted(conflict)}"])
        # 3) stale 写(乐观并发):基于过期版本 → 需 rebase
        if item.based_on_version < self.version():
            return WriteDecision(REBASE_REQUIRED, item.item_id, None,
                                 [f"STALE_WRITE:based={item.based_on_version}<cur={self.version()}"])
        # 通过 → 落库;同 topic 反极性 → CONTESTED(不覆盖)
        status = ACTIVE
        reasons = ["ok"]
        if item.topic is not None:
            for other in self._items.values():
                if (other.topic == item.topic and other.status in (ACTIVE, CONTESTED)
                        and other.polarity != item.polarity):
                    status = CONTESTED
                    other.status = CONTESTED
                    other.updated_at = _now()
                    self._emit("contest", item_id=other.item_id, by=item.item_id, topic=item.topic)
                    reasons = [f"CONTESTED_WITH:{other.item_id}"]
        item.status = status
        item.updated_at = _now()
        self._items[item.item_id] = item
        self._emit("write", item_id=item.item_id, status=status, role=item.author_role,
                   domain=item.domain, topic=item.topic)
        return WriteDecision(ACCEPT, item.item_id, status, reasons)

    # ---------- 用途守卫 ---------- #
    def assert_use(self, item_id: str, use: str) -> None:
        """显式用途校验:违反 forbidden / 不在 allowed → 抛 UsageViolation(拦截率应=100%)。"""
        item = self._items.get(item_id)
        if item is None:
            raise UsageViolation(f"NO_SUCH_ITEM:{item_id}")
        if use in item.forbidden_uses:
            raise UsageViolation(f"FORBIDDEN_USE:{item_id}:{use}")
        if not item.allows(use):
            raise UsageViolation(f"USE_NOT_ALLOWED:{item_id}:{use}")

    def can_use(self, item_id: str, use: str) -> bool:
        try:
            self.assert_use(item_id, use)
            return True
        except UsageViolation:
            return False

    # ---------- L3 角色投影 ---------- #
    def read(self, role: str, use: Optional[str] = None,
             domain: Optional[str] = None,
             include_contested: bool = True) -> List[MemoryItem]:
        """角色经治理的读投影:仅 visible_to∋role、状态有效、(可选)用途合法且同域的项。"""
        out: List[MemoryItem] = []
        ok_status = {ACTIVE, CONTESTED} if include_contested else {ACTIVE}
        for it in self._items.values():
            if it.status not in ok_status:
                continue
            if role not in it.visible_to:
                continue
            if domain is not None and it.domain != domain:
                continue
            if use is not None and not it.allows(use):
                continue
            out.append(it)
        return sorted(out, key=lambda x: x.created_at)

    def training_labels_for(self, domain: str) -> List[MemoryItem]:
        """优化角色取某域可作训练标签的记忆 —— 跨域 transfer_reference 在此天然被排除。"""
        return [it for it in self.read(Role.OPTIMIZATION, use=Use.TRAINING_LABEL)
                if it.domain == domain]

    # ---------- 撤销 / 失效 ---------- #
    def invalidate(self, item_id: str, reason: str = "") -> bool:
        it = self._items.get(item_id)
        if it is None or it.status == INVALID:
            return False
        it.status = INVALID
        it.updated_at = _now()
        self._emit("invalidate", item_id=item_id, reason=reason)
        return True

    # ---------- 多轮 RoundState ---------- #
    def push_round(self, rs: RoundState) -> None:
        self._rounds.append(rs)
        self._emit("round", round_id=rs.round_id, role=rs.actor_role, goal=rs.goal)

    def rounds(self) -> List[RoundState]:
        return list(self._rounds)

    def round_continuity(self) -> Dict[str, Any]:
        """多轮一致性:目标无漂移(除非显式改写)+ 每个 pending 最终被 resolved 或显式继承。
        返回 {goal_stable, unresolved_pending, ok}。"""
        if not self._rounds:
            return {"goal_stable": True, "unresolved_pending": [], "ok": True}
        goals = {r.goal for r in self._rounds}
        goal_stable = len(goals) == 1
        carried: Set[str] = set()
        for r in self._rounds:
            carried |= set(r.pending)
        resolved: Set[str] = set()
        for r in self._rounds:
            resolved |= set(r.resolved)
        # 仍挂起 = 出现过但既未 resolved 也未被后续轮重新 pending(最后一轮的 pending 允许存活)
        last_pending = set(self._rounds[-1].pending)
        unresolved = sorted((carried - resolved) - last_pending)
        return {"goal_stable": goal_stable, "unresolved_pending": unresolved,
                "ok": goal_stable and not unresolved}

    # ---------- 决策回放(压缩保持性) ---------- #
    def _state_from_items(self, items: List[MemoryItem]) -> MemoryState:
        st = MemoryState()
        for it in items:
            st.claim_levels[it.item_id] = it.claim_level
            st.conditions |= set(it.conditions)
            if it.is_counterevidence:
                st.counterevidence.add(it.item_id)
            st.source_node_ids.append(it.item_id)
        return st

    def verify_compression(
        self,
        keep_item_ids: List[str],
        *,
        decision_probe: Optional[Callable[[MemoryState], Any]] = None,
    ) -> CompressionCertificate:
        """把"保留 keep_item_ids"当作一次压缩,验证 top-1 动作 + 主张等级 + 条件/反证保真。
        decision_probe(MemoryState)->action 用于 top-1 动作一致性回放。"""
        active = [it for it in self._items.values() if it.status in (ACTIVE, CONTESTED)]
        source = self._state_from_items(active)
        keep = [self._items[i] for i in keep_item_ids if i in self._items]
        summary = self._state_from_items(keep)
        ok, cert = compress_and_verify(source, summary, decision_probe=decision_probe,
                                       raw_recovery_pointer="agent_memory.events")
        self._emit("compression_verify", compression_id=cert.compression_id, ok=ok)
        return cert
