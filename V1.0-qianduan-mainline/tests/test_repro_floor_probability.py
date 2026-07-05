# -*- coding: utf-8 -*-
"""M2-1 / G8 测试:复现地板"差<地板"→ 概率判定(确定性数学)。"""
from __future__ import annotations

import sys
from pathlib import Path

MAINLINE = Path(__file__).resolve().parents[1]
if str(MAINLINE) not in sys.path:
    sys.path.insert(0, str(MAINLINE))

from analysis.stage0_v2.repro_floor_variance import (  # noqa: E402
    prob_meaningful_difference,
)


def test_zero_difference_is_most_indistinguishable():
    r0 = prob_meaningful_difference(delta=0.0, floor_sd=0.25)
    # Δ=0 是最不可区分的情形:indist > distinguishable,且 > 0.5
    assert r0["p_indistinguishable"] > 0.5
    assert r0["p_indistinguishable"] > r0["p_abs_delta_gt_meaningful"]
    # 单调:|Δ| 越大越可区分
    r1 = prob_meaningful_difference(delta=0.5, floor_sd=0.25)
    assert r1["p_indistinguishable"] < r0["p_indistinguishable"]


def test_large_difference_is_distinguishable():
    # Δ 远大于地板 → 几乎一定可区分
    r = prob_meaningful_difference(delta=2.0, floor_sd=0.25)
    assert r["p_abs_delta_gt_meaningful"] > 0.95
    assert r["p_indistinguishable"] < 0.05


def test_probabilities_sum_to_one():
    r = prob_meaningful_difference(delta=0.3, floor_sd=0.25, delta_meaningful=0.25)
    assert abs(r["p_indistinguishable"] + r["p_abs_delta_gt_meaningful"] - 1.0) < 1e-9


def test_scale_is_sqrt2_times_floor():
    r = prob_meaningful_difference(delta=0.1, floor_sd=0.2)
    assert abs(r["diff_scale_dex"] - (2 ** 0.5) * 0.2) < 1e-9


def test_default_delta_meaningful_is_floor():
    r = prob_meaningful_difference(delta=0.1, floor_sd=0.25)
    assert abs(r["delta_meaningful"] - 0.25) < 1e-9
