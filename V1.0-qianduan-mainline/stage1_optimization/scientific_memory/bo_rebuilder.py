# -*- coding: utf-8 -*-
"""失效 → BO 训练视图重建 + 决策影响报告（WP3-c / E-Mem 核心闭环）。

GPT-3 指出最关键缺口:失效只改了主张图,但 BO 的 history/GP 可能仍被污染。本模块补齐:
  证据失效 → 重建 **CommittedObservationView**(只含仍有效/已提交的观测)→ 重算 best trial →
  产出 **DecisionImpactReport**(移除了哪些观测、best 是否变化、哪些历史推荐受影响)。
并提供 **WP2 桥接** `apply_revocation_impact`:Skill 撤销 → 失效其产出证据 → 重建视图 →
把 RevocationImpactRequest 标 downstream_propagation_done=True。

诚实边界:本模块重建的是 **BO 的训练输入(committed view)+ 影响报告**;真正的 GP 重训由
优化器消费新视图执行(本模块给出新视图与确定性的 best,不在此重训 GP)。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from .claim_graph import ClaimGraph
from .invalidation_engine import InvalidationEngine


@dataclass
class Observation:
    evidence_id: str
    parameters: Dict[str, Any]
    objective_value: float
    objective_id: str


@dataclass
class CommittedObservationView:
    version: int
    objective_id: str
    observations: List[Observation]
    built_at: str = field(default_factory=lambda: datetime.now(timezone.utc).astimezone().isoformat())

    def best(self) -> Optional[Observation]:
        if not self.observations:
            return None
        return max(self.observations, key=lambda o: o.objective_value)

    def evidence_ids(self) -> List[str]:
        return [o.evidence_id for o in self.observations]


@dataclass
class DecisionImpactReport:
    view_version_before: int
    view_version_after: int
    objective_id: str
    removed_evidence_ids: List[str]
    n_before: int
    n_after: int
    best_evidence_before: Optional[str]
    best_evidence_after: Optional[str]
    best_changed: bool
    recommendations_affected: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "view_version_before": self.view_version_before,
            "view_version_after": self.view_version_after,
            "objective_id": self.objective_id,
            "removed_evidence_ids": list(self.removed_evidence_ids),
            "n_before": self.n_before, "n_after": self.n_after,
            "best_evidence_before": self.best_evidence_before,
            "best_evidence_after": self.best_evidence_after,
            "best_changed": self.best_changed,
            "recommendations_affected": list(self.recommendations_affected),
        }


def build_committed_view(
    graph: ClaimGraph,
    observations: List[Observation],
    objective_id: str,
    version: int = 1,
) -> CommittedObservationView:
    """只保留证据仍 valid 的观测(失效/未提交证据绝不进训练视图)。"""
    kept = [o for o in observations if graph.is_valid(o.evidence_id)]
    return CommittedObservationView(version=version, objective_id=objective_id, observations=kept)


def rebuild_after_invalidation(
    graph: ClaimGraph,
    all_observations: List[Observation],
    objective_id: str,
    prev_view: CommittedObservationView,
    recommendations: Optional[Dict[str, List[str]]] = None,
) -> Tuple[CommittedObservationView, DecisionImpactReport]:
    """据当前图有效性重建视图,并对比 prev_view 产出决策影响报告。

    recommendations: 可选 {rec_id: [evidence_id,...]} —— 历史推荐依赖哪些证据;
    依赖到已移除证据的推荐记为 affected。
    """
    new_view = build_committed_view(graph, all_observations, objective_id,
                                    version=prev_view.version + 1)
    before_ids = set(prev_view.evidence_ids())
    after_ids = set(new_view.evidence_ids())
    removed = sorted(before_ids - after_ids)

    best_b = prev_view.best()
    best_a = new_view.best()
    best_b_id = best_b.evidence_id if best_b else None
    best_a_id = best_a.evidence_id if best_a else None

    affected_recs: List[str] = []
    for rec_id, ev_ids in (recommendations or {}).items():
        if any(e in removed for e in ev_ids):
            affected_recs.append(rec_id)

    report = DecisionImpactReport(
        view_version_before=prev_view.version, view_version_after=new_view.version,
        objective_id=objective_id, removed_evidence_ids=removed,
        n_before=len(prev_view.observations), n_after=len(new_view.observations),
        best_evidence_before=best_b_id, best_evidence_after=best_a_id,
        best_changed=(best_b_id != best_a_id),
        recommendations_affected=sorted(affected_recs))
    return new_view, report


def apply_revocation_impact(
    graph: ClaimGraph,
    revocation_request: Any,                 # scientific_skills.revocation.RevocationImpactRequest
    all_observations: List[Observation],
    objective_id: str,
    prev_view: CommittedObservationView,
    recommendations: Optional[Dict[str, List[str]]] = None,
) -> Tuple[CommittedObservationView, DecisionImpactReport]:
    """WP2→WP3 桥接:Skill 撤销 → 失效其产出证据 → 重建 BO 视图 → 标已传播。"""
    affected = list(getattr(revocation_request, "affected_evidence_ids", []) or [])
    if affected:
        InvalidationEngine(graph).mark_invalid(
            affected, reason=f"skill_revoked:{getattr(revocation_request, 'skill_id', '?')}")
    new_view, report = rebuild_after_invalidation(
        graph, all_observations, objective_id, prev_view, recommendations)
    # 标记下游传播已完成(WP2 撤销请求由 E-Mem 接管完成)
    try:
        revocation_request.downstream_propagation_done = True
    except Exception:
        pass
    return new_view, report
