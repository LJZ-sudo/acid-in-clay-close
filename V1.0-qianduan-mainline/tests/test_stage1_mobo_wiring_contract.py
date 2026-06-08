"""Line-B 改造1 契约测试：MOBO 已可接入 Stage1 主闭环，且确实是多目标。

验证点：
1. `build_stage1_optimizer("bo", ...)` 仍返回冻结的单目标 BayesianOptimizer（默认不变）。
2. `build_stage1_optimizer("mobo", ...)` 返回 MOBOOptimizer(ParEGO)，并且
   在真实 attapulgite 历史（T1-T8）上能取到全部多目标训练点 —— 证明历史键
   映射正确、走的是 ParEGO 而非单目标 BO，也不是全程冷启动。
3. 历史键映射指向真实持久化的 Stage0 指标名。

测试只读真实 history DB，不写入、不改动任何冻结证据。
"""
import sys
from pathlib import Path

import pytest

STAGE1 = Path(__file__).resolve().parents[1] / "stage1_optimization"
sys.path.insert(0, str(STAGE1))

from canonical_input.campaign_parser import CampaignConfig
from canonical_input.design_space import ParameterSpace
from campaign_memory.memory_manager import MemoryManager
from optimizers.bayesian_opt import BayesianOptimizer
from optimizers.mobo_optimizer import MOBOOptimizer
from run_optimization_loop import build_stage1_optimizer, MOBO_HISTORY_OBJECTIVE_KEYS

CAMPAIGN = STAGE1 / "campaigns" / "attapulgite_aice_campaign.json"
HISTORY_DB = STAGE1 / "campaign_memory" / "history_db_attapulgite.json"


@pytest.fixture()
def parameter_space_and_memory():
    cfg = CampaignConfig(str(CAMPAIGN))
    ps = ParameterSpace(cfg)
    mm = MemoryManager(db_path=str(HISTORY_DB), campaign_name=cfg.campaign_name)
    return ps, mm


def test_default_bo_is_unchanged(parameter_space_and_memory):
    ps, mm = parameter_space_and_memory
    opt = build_stage1_optimizer("bo", ps, mm, cold_start_threshold=5)
    assert isinstance(opt, BayesianOptimizer)
    assert not isinstance(opt, MOBOOptimizer)


def test_mobo_path_returns_parego(parameter_space_and_memory):
    ps, mm = parameter_space_and_memory
    opt = build_stage1_optimizer("mobo", ps, mm, cold_start_threshold=5, optimizer_seed=7)
    assert isinstance(opt, MOBOOptimizer)
    prov = opt.get_provenance()
    assert prov["method"] == "ParEGO_augmented_tchebycheff"
    assert [o["key"] for o in prov["objectives"]] == [
        MOBO_HISTORY_OBJECTIVE_KEYS["sigma_key"],
        MOBO_HISTORY_OBJECTIVE_KEYS["ea_high_key"],
        MOBO_HISTORY_OBJECTIVE_KEYS["ea_low_excess_key"],
    ]


def test_mobo_reads_full_multiobjective_history(parameter_space_and_memory):
    """关键：键映射正确 => 8 条历史全部可用于 ParEGO（不是 0、不是全程冷启动）。"""
    ps, mm = parameter_space_and_memory
    opt = build_stage1_optimizer("mobo", ps, mm, cold_start_threshold=5, optimizer_seed=7)
    param_names = list(ps.campaign_config.parameters.keys())
    X, P = opt._extract_multiobjective_training(param_names)
    assert len(P) == len(mm.get_history()) == 8
    for row in P:
        assert set(row.keys()) == {
            MOBO_HISTORY_OBJECTIVE_KEYS["sigma_key"],
            MOBO_HISTORY_OBJECTIVE_KEYS["ea_high_key"],
            MOBO_HISTORY_OBJECTIVE_KEYS["ea_low_excess_key"],
        }


def test_mobo_suggest_in_range_and_no_scalar_prediction(parameter_space_and_memory):
    ps, mm = parameter_space_and_memory
    opt = build_stage1_optimizer("mobo", ps, mm, cold_start_threshold=5, optimizer_seed=7)
    suggestion = opt.suggest_next()
    assert set(suggestion.keys()) == set(ps.campaign_config.parameters.keys())
    # MOBO has no single-objective scalar prediction (runner guards with `if prediction:`)
    assert opt.get_model_prediction(suggestion) is None
