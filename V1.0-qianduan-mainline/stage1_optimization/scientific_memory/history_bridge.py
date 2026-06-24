# -*- coding: utf-8 -*-
"""history_db → CommittedObservationView 物化桥（WP5 / 测量-数据路径 enforce）。

GPT-3/docx:BO 应只消费 **committed** 证据;history_db JSON 仅作导出/兼容。本模块把真实
`campaign_memory/history_db_*.json` 物化为 E-Mem 的证据图 + CommittedObservationView:
  - 每个 trial → 一个 EVIDENCE 节点 + 一条 Observation(按 objective_key 取目标值);
  - 证据失效(KK bug / Skill 撤销 / 校准失效)后,重建视图自动剔除该 trial → BO 训练集随之变化;
  - view_to_training_arrays 给优化器喂 (X, y),证明"只有 committed 证据进 BO"在真实数据上成立。
不改写 history_db(只读物化);失效在证据图层做,JSON 不动。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .claim_graph import ClaimGraph, NodeType
from .bo_rebuilder import Observation, CommittedObservationView, build_committed_view


def evidence_id_for_trial(trial: Dict[str, Any]) -> str:
    """trial → 稳定 evidence_id(供证据图/失效定位/BO 重训共用)。"""
    meta = trial.get("metadata") or {}
    sid = meta.get("sample_id")
    return f"trial::{trial.get('trial_id')}::{sid}" if sid else f"trial::{trial.get('trial_id')}"


# 向后兼容别名
_evidence_id_for_trial = evidence_id_for_trial


def load_trials(history_db_path: str | Path) -> List[Dict[str, Any]]:
    data = json.loads(Path(history_db_path).read_text(encoding="utf-8"))
    return list(data.get("trials", []) or [])


def materialize_committed_view(
    history_db_path: str | Path,
    *,
    objective_key: str = "combined_score",
    graph: Optional[ClaimGraph] = None,
    require_real: bool = False,
) -> Tuple[ClaimGraph, CommittedObservationView, Dict[str, int]]:
    """把真实 history_db 物化为证据图 + CommittedObservationView。

    require_real=True 时只纳入 metadata.source_mode=='real' 的 trial(更严的 committed 口径)。
    返回 (graph, view, id_to_trial)。id_to_trial: evidence_id → trial_id,便于失效定位。
    """
    graph = graph or ClaimGraph(":memory:")
    trials = load_trials(history_db_path)
    observations: List[Observation] = []
    id_to_trial: Dict[str, int] = {}
    for t in trials:
        objs = t.get("objectives") or {}
        if objective_key not in objs:
            continue
        if require_real and (t.get("metadata") or {}).get("source_mode") != "real":
            continue
        eid = _evidence_id_for_trial(t)
        graph.add_node(eid, NodeType.EVIDENCE,
                       label=str(t.get("trial_id")), valid=True,
                       meta={"trial_id": t.get("trial_id"), "parameters": t.get("parameters")})
        observations.append(Observation(
            evidence_id=eid, parameters=dict(t.get("parameters") or {}),
            objective_value=float(objs[objective_key]), objective_id=objective_key))
        id_to_trial[eid] = t.get("trial_id")
    view = build_committed_view(graph, observations, objective_key, version=1)
    return graph, view, id_to_trial


def view_to_training_arrays(
    view: CommittedObservationView, param_names: List[str],
) -> Tuple[List[List[float]], List[float]]:
    """把 committed 视图转成优化器可消费的 (X, y)。仅含视图内(=committed)观测。"""
    X: List[List[float]] = []
    y: List[float] = []
    for o in view.observations:
        try:
            X.append([float(o.parameters[p]) for p in param_names])
            y.append(float(o.objective_value))
        except (KeyError, TypeError, ValueError):
            continue
    return X, y
