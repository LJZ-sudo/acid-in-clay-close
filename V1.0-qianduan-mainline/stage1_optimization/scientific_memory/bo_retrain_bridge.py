# -*- coding: utf-8 -*-
"""失效 → BO 真正重训回灌（WP5 / P1 闭环最后一步）。

WP3 `bo_rebuilder` 把失效传到"训练视图",但 GP 还没在新集上重新拟合。本模块补齐最后一步:
  证据失效(证据图)→ CommittedMemoryView 只暴露仍有效的 trial → 真实优化器
  `build_noise_aware_optimizer(...).suggest_next()` 在**更小的 committed 集上重新拟合 GP** →
  给出新建议。从而"失效→BO"闭到 GP 重训,而不仅是改训练集。

CommittedMemoryView 实现 memory_manager 协议(get_history),优化器 `_extract` 直接消费;
失效证据**绝不**出现在 get_history 返回里(无泄漏)。不改写优化器/冻结闭环。
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from .claim_graph import ClaimGraph
from .history_bridge import evidence_id_for_trial


class CommittedMemoryView:
    """只读 memory_manager 适配器:仅暴露证据仍 valid 的 trial(committed)。

    与 campaign_memory.MemoryManager 的 get_history() 同接口,可直接喂给优化器。
    """

    def __init__(self, trials: List[Dict[str, Any]], graph: ClaimGraph,
                 evidence_id_fn: Optional[Callable[[Dict[str, Any]], str]] = None):
        self._trials = list(trials)
        self._graph = graph
        self._eid = evidence_id_fn or evidence_id_for_trial

    def get_history(self) -> List[Dict[str, Any]]:
        return [t for t in self._trials if self._graph.is_valid(self._eid(t))]

    def committed_evidence_ids(self) -> List[str]:
        return [self._eid(t) for t in self.get_history()]


def rebuild_and_resuggest(
    graph: ClaimGraph,
    trials: List[Dict[str, Any]],
    parameter_space: Any,
    objectives: Any,
    *,
    backend: str = "noise_aware_skopt",
    cold_start_threshold: int = 5,
    seed: int = 7,
    evidence_id_fn: Optional[Callable[[Dict[str, Any]], str]] = None,
) -> Dict[str, Any]:
    """在当前 committed 证据集上重训优化器并给出新建议。

    返回 {n_committed, n_train_points, mode, suggestion, backend}。
    n_train_points 来自优化器 provenance —— 失效后它会**变小**,证明 GP 在更小集上重拟合。
    """
    import sys
    from pathlib import Path
    stage1 = Path(__file__).resolve().parents[1]
    if str(stage1) not in sys.path:
        sys.path.insert(0, str(stage1))
    from optimizers.botorch_mobo_v2 import build_noise_aware_optimizer

    shim = CommittedMemoryView(trials, graph, evidence_id_fn)
    opt = build_noise_aware_optimizer(
        backend, parameter_space, shim, objectives=objectives,
        cold_start_threshold=cold_start_threshold, random_state=seed)
    suggestion = opt.suggest_next()
    prov = opt.get_provenance()
    return {
        "n_committed": len(shim.get_history()),
        "n_train_points": prov.get("n_train_points"),
        "mode": prov.get("mode"),
        "backend": prov.get("backend", backend),
        "suggestion": suggestion,
    }
