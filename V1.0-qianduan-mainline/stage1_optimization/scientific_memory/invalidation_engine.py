# -*- coding: utf-8 -*-
"""失效传播引擎（M5-B）。

证据失效 → 删依赖路径(置 valid=0,有效检索不再返回)→ 下游主张按四值逻辑自动重算 →
独立支持链存活 → 旧决策(depends_on)标 AFFECTED。并计算三项验收指标。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .claim_graph import ClaimGraph, EdgeType, NodeType


@dataclass
class InvalidationReport:
    invalidated_evidence: List[str]
    claim_status_before: Dict[str, str]
    claim_status_after: Dict[str, str]
    downgraded_claims: List[str]
    affected_claims: List[str]
    surviving_independent_support: List[str]
    metrics: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "invalidated_evidence": self.invalidated_evidence,
            "claim_status_before": self.claim_status_before,
            "claim_status_after": self.claim_status_after,
            "downgraded_claims": self.downgraded_claims,
            "affected_claims": self.affected_claims,
            "surviving_independent_support": self.surviving_independent_support,
            "metrics": self.metrics,
        }


class InvalidationEngine:
    def __init__(self, graph: ClaimGraph):
        self.g = graph

    def _claims_touching(self, evidence_id: str) -> List[str]:
        """所有支持/反驳集里包含该证据的主张(直接受影响候选)。"""
        rows = self.g.conn.execute(
            "SELECT DISTINCT dst FROM edges WHERE src=? AND edge_type IN (?,?)",
            (evidence_id, EdgeType.SUPPORTS, EdgeType.REFUTES)).fetchall()
        return [r["dst"] for r in rows]

    def mark_invalid(self, evidence_ids: List[str], reason: str = "") -> InvalidationReport:
        # 0) 重算基线(确保 before 是最新四值)
        self.g.recompute_all(cause="baseline_before_invalidation")
        before = {c: self.g.get_status(c) for c in self.g.all_claims()}

        # 1) 置失效 + 记事件(失效证据从此不进有效检索)
        for e in evidence_ids:
            self.g.conn.execute("UPDATE nodes SET valid=0 WHERE id=? AND node_type=?",
                                (e, NodeType.EVIDENCE))
            self.g.conn.execute(
                "INSERT INTO invalidation_events(evidence_id,reason,at) VALUES (?,?,?)",
                (e, reason, datetime.now(timezone.utc).astimezone().isoformat()))
        self.g.conn.commit()

        # 2) 失效传播:重算全部主张四值 + AFFECTED
        report = self.g.recompute_all(cause=f"invalidation:{reason}")
        after = {c: self.g.get_status(c) for c in self.g.all_claims()}

        downgraded = [c for c in self.g.all_claims()
                      if _rank(after[c]) < _rank(before[c]) or
                      (before[c] == "SUPPORTED" and after[c] in ("CONTESTED", "REFUTED", "UNKNOWN"))]
        affected = [c for c in self.g.all_claims() if self.g.is_affected(c)]
        surviving = [c for c in self.g.all_claims()
                     if after[c] == "SUPPORTED" and self.g.surviving_support_sets(c)]

        metrics = self._acceptance_metrics(evidence_ids, before, after)
        return InvalidationReport(
            invalidated_evidence=list(evidence_ids),
            claim_status_before=before, claim_status_after=after,
            downgraded_claims=downgraded, affected_claims=affected,
            surviving_independent_support=surviving, metrics=metrics)

    def _acceptance_metrics(self, evidence_ids, before, after) -> Dict[str, float]:
        # ① 失效证据被有效检索率 = 0
        valid_now = set(self.g.valid_evidence())
        leaked = [e for e in evidence_ids if e in valid_now]
        invalidated_retrieval_rate = len(leaked) / max(len(evidence_ids), 1)

        # ② 下游主张自动重算率:所有"支持/反驳集触及失效证据"的主张是否都被重算
        touched = set()
        for e in evidence_ids:
            touched.update(self._claims_touching(e))
        # 重算 = claim_versions 里有本轮 invalidation cause 的记录
        recomputed = set()
        for c in touched:
            row = self.g.conn.execute(
                "SELECT cause FROM claim_versions WHERE claim_id=? ORDER BY id DESC LIMIT 1",
                (c,)).fetchone()
            if row and str(row["cause"]).startswith("invalidation:"):
                recomputed.add(c)
        recompute_rate = len(recomputed) / max(len(touched), 1)

        # ③ 独立支持链存活率:失效前 SUPPORTED 且仍有全有效独立支持集的主张,失效后是否仍 SUPPORTED
        had_independent = []
        for c in self.g.all_claims():
            if before.get(c) == "SUPPORTED" and self.g.surviving_support_sets(c):
                had_independent.append(c)
        survived = [c for c in had_independent if after.get(c) == "SUPPORTED"]
        preservation_rate = (len(survived) / len(had_independent)) if had_independent else 1.0

        return {
            "invalidated_evidence_retrieval_rate": round(invalidated_retrieval_rate, 6),
            "downstream_claim_recomputation_rate": round(recompute_rate, 6),
            "independent_support_preservation_rate": round(preservation_rate, 6),
            "n_evidence_invalidated": len(evidence_ids),
            "n_claims_touched": len(touched),
            "n_claims_with_independent_support": len(had_independent),
        }


def _rank(status: str) -> int:
    """SUPPORTED 最强 → REFUTED/UNKNOWN 弱;用于判定"降级"。"""
    return {"SUPPORTED": 3, "CONTESTED": 2, "UNKNOWN": 1, "REFUTED": 0}.get(status, 1)
