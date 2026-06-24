# -*- coding: utf-8 -*-
"""自主动作单一受控入口（WP4 Cutover / SciTX）。

GPT-3 + P0-5 审计指出:自主路径 `/api/agent` 直连 `hw.enqueue_command(...)`,绕过 SciTX。
本模块提供**唯一受控入口** ActionGate:自主路径不再直接调硬件,而是提交 ActionProposal,
由 gate 按策略 + 模式裁决:
  - shadow  : 记录提案与裁决,**仍照常下发**(行为与 legacy 完全一致;只观察)。
  - canary  : 仅放行 allowlist 内低风险命令,其余需人工。
  - enforce : 只有策略放行才下发;allowlist 外命令 **BLOCKED**(取得系统权威性)。
人工 override(source=operator)产生 HumanOverrideEvent,不计入自主覆盖率。
不变量(对齐 docx §3.2 不变量 1/2):Agent 不直接碰 enqueue_command;override 与自主隔离并留痕。
"""
from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

# 当前自主路径允许的控制命令(与 backend agent 决策环一致)
ALLOWED_AUTONOMOUS_COMMANDS = frozenset({"TRIGGER_FINE_SCAN", "BACKTRACK", "RE_MEASURE"})

# 模式
SHADOW = "shadow"
CANARY = "canary"
ENFORCE = "enforce"

# 裁决
DISPATCHED = "DISPATCHED"
SHADOW_DISPATCHED = "SHADOW_DISPATCHED"
BLOCKED = "BLOCKED"
OVERRIDE_DISPATCHED = "OVERRIDE_DISPATCHED"


def resolve_mode(explicit: Optional[str] = None) -> str:
    """模式优先级:显式参数 > 环境变量 SCITX_HARNESS_MODE > 默认 shadow。"""
    m = (explicit or os.environ.get("SCITX_HARNESS_MODE") or SHADOW).strip().lower()
    return m if m in (SHADOW, CANARY, ENFORCE) else SHADOW


@dataclass
class ActionProposal:
    command: str
    params: Optional[Dict[str, Any]] = None
    source: str = "autonomous"            # autonomous | operator
    rationale: str = ""
    operator: Optional[str] = None        # operator override 时填
    proposal_id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass
class GateDecision:
    proposal_id: str
    command: str
    mode: str
    decision: str                          # DISPATCHED | SHADOW_DISPATCHED | BLOCKED | OVERRIDE_DISPATCHED
    dispatched: bool
    reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "proposal_id": self.proposal_id, "command": self.command, "mode": self.mode,
            "decision": self.decision, "dispatched": self.dispatched, "reasons": self.reasons,
        }


class ActionGate:
    """自主硬件命令的唯一受控入口。enqueue_fn 为注入的真实下发函数(如 hw.enqueue_command)。"""

    def __init__(
        self,
        enqueue_fn: Callable[..., Any],
        mode: Optional[str] = None,
        event_store: Any = None,
        allowed: Optional[frozenset] = None,
    ):
        self._enqueue = enqueue_fn
        self.mode = resolve_mode(mode)
        self.store = event_store
        self.allowed = allowed if allowed is not None else ALLOWED_AUTONOMOUS_COMMANDS

    def _record(self, kind: str, payload: Dict[str, Any]) -> None:
        if self.store is not None:
            try:
                self.store.append(kind, payload)
            except Exception:
                pass

    def submit(self, proposal: ActionProposal) -> GateDecision:
        policy_ok = proposal.command in self.allowed
        reasons: List[str] = [f"policy_ok={policy_ok}", f"source={proposal.source}"]

        # 人工 override:隔离 + 留痕(不计入自主覆盖率)
        if proposal.source == "operator":
            self._record("human_override", {"proposal_id": proposal.proposal_id,
                                            "command": proposal.command, "operator": proposal.operator,
                                            "at": datetime.now(timezone.utc).astimezone().isoformat()})
            dispatched = self._dispatch(proposal)
            return GateDecision(proposal.proposal_id, proposal.command, self.mode,
                                OVERRIDE_DISPATCHED, dispatched, reasons + ["human_override"])

        self._record("action_proposal", {"proposal_id": proposal.proposal_id,
                                          "command": proposal.command, "mode": self.mode,
                                          "policy_ok": policy_ok})

        if self.mode == SHADOW:
            # 只观察:照常下发(与 legacy 一致),记录"若 enforce 会怎样"
            dispatched = self._dispatch(proposal)
            return GateDecision(proposal.proposal_id, proposal.command, self.mode,
                                SHADOW_DISPATCHED, dispatched,
                                reasons + [f"would_block_in_enforce={not policy_ok}"])

        # canary / enforce:策略放行才下发
        if policy_ok:
            dispatched = self._dispatch(proposal)
            return GateDecision(proposal.proposal_id, proposal.command, self.mode,
                                DISPATCHED, dispatched, reasons)
        # 策略不放行 → 阻断(取得权威性)
        self._record("blocked", {"proposal_id": proposal.proposal_id, "command": proposal.command,
                                 "mode": self.mode})
        return GateDecision(proposal.proposal_id, proposal.command, self.mode,
                            BLOCKED, False, reasons + ["blocked_by_policy"])

    def _dispatch(self, proposal: ActionProposal) -> bool:
        if proposal.params is not None:
            self._enqueue(proposal.command, proposal.params)
        else:
            self._enqueue(proposal.command)
        return True
