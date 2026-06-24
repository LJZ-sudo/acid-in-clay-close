# -*- coding: utf-8 -*-
"""证据超图 + 四值逻辑（M5-B 核心)。

四值逻辑(容矛盾):对主张 c,(s,r) = (是否存在全有效支持集, 是否存在全有效反驳集):
  (0,0)=UNKNOWN  (1,0)=SUPPORTED  (0,1)=REFUTED  (1,1)=CONTESTED
**禁止"最后写入者胜出"**:正反并存保留 CONTESTED。

最小支持集:同一 support_set_id 的若干 (evidence→claim) 边构成一个支持集;
主张被支持 ⇔ 存在某支持集,其全部证据仍 valid(独立支持链 → 删一条不塌)。
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from . import schema


class NodeType:
    EVIDENCE = "EVIDENCE"
    CLAIM = "CLAIM"
    PARAMETER = "PARAMETER"


class EdgeType:
    SUPPORTS = "supports"
    REFUTES = "refutes"
    DEPENDS_ON = "depends_on"
    INVALIDATES = "invalidates"
    DERIVED_FROM = "derived_from"


class ClaimStatus:
    UNKNOWN = "UNKNOWN"
    SUPPORTED = "SUPPORTED"
    REFUTED = "REFUTED"
    CONTESTED = "CONTESTED"


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def _four_valued(s: int, r: int) -> str:
    return {(0, 0): ClaimStatus.UNKNOWN, (1, 0): ClaimStatus.SUPPORTED,
            (0, 1): ClaimStatus.REFUTED, (1, 1): ClaimStatus.CONTESTED}[(int(bool(s)), int(bool(r)))]


class ClaimGraph:
    def __init__(self, db_path: Union[str, Path] = ":memory:"):
        self.conn = schema.connect(db_path)

    def close(self) -> None:
        self.conn.close()

    # ---------- 构图 ---------- #
    def add_node(self, node_id: str, node_type: str, label: str = "",
                 valid: bool = True, meta: Optional[Dict[str, Any]] = None) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO nodes(id,node_type,label,valid,created_at,meta) VALUES (?,?,?,?,?,?)",
            (node_id, node_type, label, 1 if valid else 0, _now(),
             json.dumps(meta or {}, ensure_ascii=False)))
        if node_type == NodeType.CLAIM:
            self.conn.execute(
                "INSERT OR IGNORE INTO claim_status(claim_id,support,refute,status,affected,updated_at) "
                "VALUES (?,?,?,?,?,?)", (node_id, 0, 0, ClaimStatus.UNKNOWN, 0, _now()))
        self.conn.commit()

    def add_edge(self, src: str, dst: str, edge_type: str,
                 support_set_id: Optional[str] = None, meta: Optional[Dict[str, Any]] = None) -> None:
        self.conn.execute(
            "INSERT INTO edges(src,dst,edge_type,support_set_id,meta) VALUES (?,?,?,?,?)",
            (src, dst, edge_type, support_set_id, json.dumps(meta or {}, ensure_ascii=False)))
        self.conn.commit()

    def add_support(self, evidence_ids: List[str], claim_id: str, set_id: str) -> None:
        """加一个最小支持集(若干证据共同支持 claim)。"""
        for e in evidence_ids:
            self.add_edge(e, claim_id, EdgeType.SUPPORTS, support_set_id=set_id)

    def add_refute(self, evidence_ids: List[str], claim_id: str, set_id: str) -> None:
        for e in evidence_ids:
            self.add_edge(e, claim_id, EdgeType.REFUTES, support_set_id=set_id)

    def add_dependency(self, claim_id: str, depends_on_claim_id: str) -> None:
        self.add_edge(claim_id, depends_on_claim_id, EdgeType.DEPENDS_ON)

    # ---------- 查询(无泄漏) ---------- #
    def is_valid(self, node_id: str) -> bool:
        row = self.conn.execute("SELECT valid FROM nodes WHERE id=?", (node_id,)).fetchone()
        return bool(row and row["valid"] == 1)

    def valid_evidence(self) -> List[str]:
        """只返回 valid=1 的证据 —— 失效证据绝不出现(无泄漏)。"""
        rows = self.conn.execute(
            "SELECT id FROM nodes WHERE node_type=? AND valid=1", (NodeType.EVIDENCE,)).fetchall()
        return [r["id"] for r in rows]

    def all_claims(self) -> List[str]:
        rows = self.conn.execute("SELECT id FROM nodes WHERE node_type=?", (NodeType.CLAIM,)).fetchall()
        return [r["id"] for r in rows]

    def _sets(self, claim_id: str, edge_type: str) -> Dict[str, List[str]]:
        rows = self.conn.execute(
            "SELECT src, support_set_id FROM edges WHERE dst=? AND edge_type=?",
            (claim_id, edge_type)).fetchall()
        sets: Dict[str, List[str]] = {}
        for r in rows:
            sets.setdefault(r["support_set_id"] or "_default", []).append(r["src"])
        return sets

    def support_sets(self, claim_id: str) -> Dict[str, List[str]]:
        return self._sets(claim_id, EdgeType.SUPPORTS)

    def refute_sets(self, claim_id: str) -> Dict[str, List[str]]:
        return self._sets(claim_id, EdgeType.REFUTES)

    def _has_all_valid_set(self, sets: Dict[str, List[str]]) -> bool:
        for members in sets.values():
            if members and all(self.is_valid(m) for m in members):
                return True
        return False

    def surviving_support_sets(self, claim_id: str) -> List[str]:
        """返回当前仍全有效的支持集 id(独立支持链)。"""
        return [sid for sid, members in self.support_sets(claim_id).items()
                if members and all(self.is_valid(m) for m in members)]

    def compute_status(self, claim_id: str) -> Tuple[int, int, str]:
        s = 1 if self._has_all_valid_set(self.support_sets(claim_id)) else 0
        r = 1 if self._has_all_valid_set(self.refute_sets(claim_id)) else 0
        return s, r, _four_valued(s, r)

    def get_status(self, claim_id: str) -> str:
        row = self.conn.execute(
            "SELECT status FROM claim_status WHERE claim_id=?", (claim_id,)).fetchone()
        return row["status"] if row else ClaimStatus.UNKNOWN

    def is_affected(self, claim_id: str) -> bool:
        row = self.conn.execute(
            "SELECT affected FROM claim_status WHERE claim_id=?", (claim_id,)).fetchone()
        return bool(row and row["affected"] == 1)

    def dependents_of(self, claim_id: str) -> List[str]:
        """返回 depends_on 该 claim 的下游 claim(A depends_on claim ⇒ A 受影响)。"""
        rows = self.conn.execute(
            "SELECT src FROM edges WHERE dst=? AND edge_type=?",
            (claim_id, EdgeType.DEPENDS_ON)).fetchall()
        return [r["src"] for r in rows]

    # ---------- 状态落盘 + 版本 ---------- #
    def _write_status(self, claim_id: str, s: int, r: int, status: str,
                      affected: int, cause: str) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO claim_status(claim_id,support,refute,status,affected,updated_at) "
            "VALUES (?,?,?,?,?,?)", (claim_id, s, r, status, affected, _now()))
        self.conn.execute(
            "INSERT INTO claim_versions(claim_id,support,refute,status,affected,at,cause) "
            "VALUES (?,?,?,?,?,?,?)", (claim_id, s, r, status, affected, _now(), cause))
        self.conn.commit()

    def recompute_all(self, cause: str = "recompute") -> Dict[str, Dict[str, Any]]:
        """重算所有主张四值状态 + 标 AFFECTED。返回 {claim: {old,new,changed,affected}}。"""
        prev = {c: self.get_status(c) for c in self.all_claims()}
        # 1) 先按证据有效性重算每个主张
        new_status: Dict[str, Tuple[int, int, str]] = {}
        for c in self.all_claims():
            new_status[c] = self.compute_status(c)
        changed = {c for c in new_status if new_status[c][2] != prev.get(c, ClaimStatus.UNKNOWN)}
        # 2) depends_on 传播:依赖了"状态变化的主张"的下游 → AFFECTED
        affected: Dict[str, bool] = {c: False for c in self.all_claims()}
        for c in self.all_claims():
            for dep in self._depends_on_targets(c):
                if dep in changed:
                    affected[c] = True
        # 3) 落盘
        report: Dict[str, Dict[str, Any]] = {}
        for c in self.all_claims():
            s, r, st = new_status[c]
            self._write_status(c, s, r, st, 1 if affected[c] else 0, cause)
            report[c] = {"old": prev.get(c, ClaimStatus.UNKNOWN), "new": st,
                         "changed": c in changed, "affected": affected[c]}
        return report

    def _depends_on_targets(self, claim_id: str) -> List[str]:
        rows = self.conn.execute(
            "SELECT dst FROM edges WHERE src=? AND edge_type=?",
            (claim_id, EdgeType.DEPENDS_ON)).fetchall()
        return [r["dst"] for r in rows]
