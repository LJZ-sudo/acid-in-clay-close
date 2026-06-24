# -*- coding: utf-8 -*-
"""图版本快照 + 乐观并发写门（WP3-a / E-Mem）。

多 Agent 并发写记忆时,防"基于过期图版本写入"与"用已失效证据写入":
  - 快照捕获 evidence_graph_version(失效事件数)+ claim_graph_version(主张版本数)+
    当时的有效证据集 + 主张状态。
  - 写门 validate_write:基于的版本落后于当前 → REBASE_REQUIRED;用到任何当前失效证据 → REJECTED;
    否则 ACCEPT。LLM 只能写 Proposed/Quarantined,不能直接改 Active Fact(由调用方按本门裁决)。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .claim_graph import ClaimGraph

ACCEPT = "ACCEPT"
REBASE_REQUIRED = "REBASE_REQUIRED"
REJECTED = "REJECTED"


@dataclass
class GraphSnapshot:
    evidence_graph_version: int       # = 失效事件总数(每次失效 +)
    claim_graph_version: int          # = claim_versions 行数(每次重算 +)
    valid_evidence_ids: List[str]
    claim_status: Dict[str, str]
    captured_at: str = field(default_factory=lambda: datetime.now(timezone.utc).astimezone().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evidence_graph_version": self.evidence_graph_version,
            "claim_graph_version": self.claim_graph_version,
            "valid_evidence_ids": list(self.valid_evidence_ids),
            "claim_status": dict(self.claim_status),
            "captured_at": self.captured_at,
        }


@dataclass
class WriteGateResult:
    decision: str                     # ACCEPT | REBASE_REQUIRED | REJECTED
    reasons: List[str] = field(default_factory=list)

    def accepted(self) -> bool:
        return self.decision == ACCEPT


def _evidence_version(graph: ClaimGraph) -> int:
    row = graph.conn.execute("SELECT COUNT(*) AS n FROM invalidation_events").fetchone()
    return int(row["n"]) if row else 0


def _claim_version(graph: ClaimGraph) -> int:
    row = graph.conn.execute("SELECT COUNT(*) AS n FROM claim_versions").fetchone()
    return int(row["n"]) if row else 0


def take_snapshot(graph: ClaimGraph) -> GraphSnapshot:
    return GraphSnapshot(
        evidence_graph_version=_evidence_version(graph),
        claim_graph_version=_claim_version(graph),
        valid_evidence_ids=graph.valid_evidence(),
        claim_status={c: graph.get_status(c) for c in graph.all_claims()},
    )


def validate_write(
    graph: ClaimGraph,
    snapshot: GraphSnapshot,
    used_evidence_ids: List[str],
) -> WriteGateResult:
    """乐观并发写门:基于 snapshot 的写入是否仍可接受。"""
    reasons: List[str] = []
    # 1) 用到当前失效证据 → 直接 REJECTED(最严)
    invalid_used = [e for e in used_evidence_ids if not graph.is_valid(e)]
    if invalid_used:
        return WriteGateResult(REJECTED, [f"used_invalid_evidence:{invalid_used}"])
    # 2) 证据图版本落后(快照后又发生过失效)→ 需 rebase
    cur_ev = _evidence_version(graph)
    if cur_ev > snapshot.evidence_graph_version:
        return WriteGateResult(
            REBASE_REQUIRED,
            [f"stale_evidence_version:snapshot={snapshot.evidence_graph_version}<current={cur_ev}"])
    return WriteGateResult(ACCEPT, ["ok"])
