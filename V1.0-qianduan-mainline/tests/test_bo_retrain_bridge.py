# -*- coding: utf-8 -*-
"""WP5/P1：失效 → BO 真正重训回灌(GP 在更小 committed 集上重新拟合)。

用真实 campaign + 真实 history_db:
  1) 物化 committed 视图 → 优化器在全 N 点上重训给建议;
  2) 失效"最优"那条证据 → 优化器在 N-1 点上**重新拟合 GP** → n_train 减少、仍给 in-bounds 建议。
证明"失效→BO"闭到 GP 重训,而非仅改训练集。
"""
from __future__ import annotations

import sys
from pathlib import Path

MAINLINE = Path(__file__).resolve().parents[1]
STAGE1 = MAINLINE / "stage1_optimization"
sys.path.insert(0, str(STAGE1))

from canonical_input.campaign_parser import CampaignConfig  # noqa: E402
from canonical_input.design_space import ParameterSpace  # noqa: E402
from optimizers.mobo_optimizer import locked_v2_objectives  # noqa: E402
from run_optimization_loop import MOBO_HISTORY_OBJECTIVE_KEYS  # noqa: E402
from scientific_memory.history_bridge import (  # noqa: E402
    materialize_committed_view, evidence_id_for_trial,
)
from scientific_memory.bo_retrain_bridge import rebuild_and_resuggest, CommittedMemoryView  # noqa: E402
from scientific_memory.invalidation_engine import InvalidationEngine  # noqa: E402

CAMPAIGN = STAGE1 / "campaigns" / "attapulgite_aice_campaign.json"
HISTORY_DB = STAGE1 / "campaign_memory" / "history_db_attapulgite.json"


def _ps():
    cfg = CampaignConfig(str(CAMPAIGN))
    return ParameterSpace(cfg)


def _objs():
    return locked_v2_objectives(**MOBO_HISTORY_OBJECTIVE_KEYS)


def test_committed_memory_view_hides_invalidated():
    graph, _view, _ = materialize_committed_view(HISTORY_DB, objective_key="combined_score")
    from scientific_memory.history_bridge import load_trials
    trials = load_trials(HISTORY_DB)
    shim = CommittedMemoryView(trials, graph)
    n0 = len(shim.get_history())
    # 失效第一条 trial 的证据
    first = trials[0]
    InvalidationEngine(graph).mark_invalid([evidence_id_for_trial(first)], reason="test")
    assert len(shim.get_history()) == n0 - 1
    graph.close()


def test_invalidation_shrinks_gp_training_and_resuggests():
    graph, _view, _ = materialize_committed_view(HISTORY_DB, objective_key="combined_score")
    from scientific_memory.history_bridge import load_trials
    trials = load_trials(HISTORY_DB)
    ps, objs = _ps(), _objs()

    before = rebuild_and_resuggest(graph, trials, ps, objs, backend="noise_aware_skopt", seed=7)
    # 真实 10 点历史 → 非冷启动,GP 重训
    assert before["mode"] == "noise_aware_parego"
    assert before["n_train_points"] == before["n_committed"] >= 6

    # 失效最优证据(trial 1, R0.186)→ 重训应在更少点上
    first = trials[0]
    InvalidationEngine(graph).mark_invalid([evidence_id_for_trial(first)], reason="post_hoc_bug")
    after = rebuild_and_resuggest(graph, trials, ps, objs, backend="noise_aware_skopt", seed=7)

    assert after["n_committed"] == before["n_committed"] - 1     # committed 少一条
    assert after["n_train_points"] == before["n_train_points"] - 1  # GP 在更小集上重拟合
    # 建议仍在参数域内
    names = list(ps.campaign_config.parameters.keys())
    bounds = dict(zip(names, [tuple(b) for b in ps.get_bounds()]))
    for k, v in after["suggestion"].items():
        assert bounds[k][0] <= v <= bounds[k][1]
    graph.close()
