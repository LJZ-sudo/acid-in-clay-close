# -*- coding: utf-8 -*-
"""M2-2 测试:ConductivityEstimate 误差传播 + combined_score MC 分布。"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from _new_data_analysis.stage0_v2.conductivity_uncertainty import (  # noqa: E402
    estimate_point, combined_score_distribution,
)


def _synthetic_point(rb_true=100.0, n=60):
    freq = np.logspace(0, 6, n)
    zimag = np.linspace(-50.0, 20.0, n)
    zreal = rb_true + 12.0 * np.sin(np.linspace(-0.6, 0.6, n))
    return {
        "freq": freq, "z_real": zreal, "z_imag": zimag,
        "temperature_C": 25.0, "temperature_K": 298.15,
        "conductivity_legacy": 0.07 / (rb_true * 1.96), "rb_ohm_legacy": rb_true,
    }


def test_geometry_uncertainty_is_unknown_not_zero():
    est = estimate_point(_synthetic_point(), geom_ratio=0.0357)
    assert est.uncertainty_scope == "RB_AND_METHOD"
    # 几何不确定度必须显式 UNKNOWN,绝不默认 0
    assert est.variance_components["var_log10_thickness"] == "UNKNOWN"
    assert est.variance_components["var_log10_area"] == "UNKNOWN"


def test_log10_sigma_estimate_has_sd_and_ci():
    est = estimate_point(_synthetic_point(), geom_ratio=0.0357)
    assert est.log10_sigma_mean is not None
    assert est.log10_sigma_sd is not None and est.log10_sigma_sd >= 0.0
    assert est.ci95[0] <= est.log10_sigma_mean <= est.ci95[1]


def test_combined_score_distribution_mean_and_spread():
    d = combined_score_distribution(
        log10_sigma_room_mean=-1.6, log10_sigma_room_sd=0.05,
        ea_high_mean=0.10, ea_low_excess_mean=0.0, n_mc=40000, seed=1)
    # 期望 ≈ -1.6 - 3*0.10 - 0.5*0 = -1.9
    assert abs(d["combined_score_mean"] - (-1.9)) < 0.02
    assert d["combined_score_sd"] > 0
    lo, hi = d["combined_score_ci95"]
    assert lo < d["combined_score_mean"] < hi


def test_combined_score_sd_dominated_by_ea_when_sigma_tight():
    # σ 很紧(sd 极小),combined_score 不确定度应由 Ea 地板(×3)主导
    d = combined_score_distribution(
        log10_sigma_room_mean=-1.5, log10_sigma_room_sd=1e-4,
        ea_high_mean=0.10, ea_low_excess_mean=0.0, ea_high_sd=0.019, n_mc=40000, seed=2)
    # 3*0.019 ≈ 0.057 量级
    assert 0.04 < d["combined_score_sd"] < 0.08
