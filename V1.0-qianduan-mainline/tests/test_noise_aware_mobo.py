# -*- coding: utf-8 -*-
"""M2-3 契约测试:噪声感知 MOBO(skopt 逐点 alpha)+ botorch 门控。

只读真实 campaign + history DB,不写入。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

STAGE1 = Path(__file__).resolve().parents[1] / "stage1_optimization"
sys.path.insert(0, str(STAGE1))

from canonical_input.campaign_parser import CampaignConfig
from canonical_input.design_space import ParameterSpace
from campaign_memory.memory_manager import MemoryManager
from optimizers.botorch_mobo_v2 import (
    NoiseAwareParEGO, build_noise_aware_optimizer, build_botorch_mobo,
    botorch_available, OPTIMIZER_BACKENDS,
)
from optimizers.mobo_optimizer import MOBOOptimizer, locked_v2_objectives

CAMPAIGN = STAGE1 / "campaigns" / "attapulgite_aice_campaign.json"
HISTORY_DB = STAGE1 / "campaign_memory" / "history_db_attapulgite.json"

# 与真实闭环一致:把 v2 spec 键映射到 history DB 真实键
HISTORY_KEYS = {
    "sigma_key": "conductivity_room_temp_S_cm",
    "ea_high_key": "ea_high_temp_eV",
    "ea_low_excess_key": "ea_low_excess_eV",
}


def _objs():
    return locked_v2_objectives(**HISTORY_KEYS)


@pytest.fixture()
def ps_mm():
    cfg = CampaignConfig(str(CAMPAIGN))
    ps = ParameterSpace(cfg)
    mm = MemoryManager(db_path=str(HISTORY_DB), campaign_name=cfg.campaign_name)
    return ps, mm


def test_noise_aware_suggest_in_bounds(ps_mm):
    ps, mm = ps_mm
    opt = NoiseAwareParEGO(ps, mm, objectives=_objs(), cold_start_threshold=5, random_state=7)
    s = opt.suggest_next()
    assert set(s.keys()) == set(ps.campaign_config.parameters.keys())
    for name, (lo, hi) in zip(ps.campaign_config.parameters.keys(),
                              [tuple(b) for b in ps.get_bounds()]):
        assert lo <= s[name] <= hi


def test_noise_aware_provenance_marks_noise(ps_mm):
    ps, mm = ps_mm
    opt = NoiseAwareParEGO(ps, mm, objectives=_objs(), cold_start_threshold=5, random_state=7)
    opt.suggest_next()
    prov = opt.get_provenance()
    assert prov["noise_aware"] is True
    assert prov["backend"] == "noise_aware_skopt"
    # G1 前噪声应标 CROSS_SYSTEM_PROXY(诚实)
    assert prov["noise_source"] == "CROSS_SYSTEM_PROXY"


def test_consumes_per_observation_variance(ps_mm):
    """逐点 alpha 走通:有真实 10 点历史时应进入 noise_aware_parego 而非冷启动。"""
    ps, mm = ps_mm
    opt = NoiseAwareParEGO(ps, mm, objectives=_objs(), cold_start_threshold=5, random_state=7)
    opt.suggest_next()
    assert opt.get_provenance()["mode"] == "noise_aware_parego"
    assert opt.get_provenance()["mean_obs_variance"] > 0


def test_backend_selector(ps_mm):
    ps, mm = ps_mm
    assert isinstance(build_noise_aware_optimizer("legacy", ps, mm), MOBOOptimizer)
    assert isinstance(build_noise_aware_optimizer("noise_aware_skopt", ps, mm), NoiseAwareParEGO)
    with pytest.raises(ValueError):
        build_noise_aware_optimizer("nonsense", ps, mm)


def test_botorch_gated_not_faked(ps_mm):
    """botorch 未安装时必须明确报错,绝不伪造回退。"""
    ps, mm = ps_mm
    if not botorch_available():
        with pytest.raises(ImportError):
            build_noise_aware_optimizer("botorch_v2", ps, mm)


@pytest.mark.skipif(not botorch_available(), reason="botorch/torch 未安装")
def test_botorch_backend_real_multiobjective(ps_mm):
    """botorch 已装:真实 qLogNEHVI 路径应吃满 10 点历史、给出 in-bounds 建议。"""
    from optimizers.botorch_mobo_v2 import BotorchMOBO
    ps, mm = ps_mm
    opt = build_noise_aware_optimizer("botorch_v2", ps, mm, objectives=_objs(),
                                      cold_start_threshold=5, random_state=7)
    assert isinstance(opt, BotorchMOBO)
    s = opt.suggest_next()
    for name, (lo, hi) in zip(ps.campaign_config.parameters.keys(),
                              [tuple(b) for b in ps.get_bounds()]):
        assert lo <= s[name] <= hi
    prov = opt.get_provenance()
    assert prov["backend"] == "botorch_v2"
    assert prov["mode"] == "botorch_qlognehvi"          # 非冷启动 = 键映射正确
    assert prov["n_train_points"] == len(mm.get_history())
    assert prov["noise_aware"] is True
    assert len(prov["ref_point"]) == 3
