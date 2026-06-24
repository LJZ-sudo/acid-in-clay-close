# -*- coding: utf-8 -*-
"""M1-1 / G2 契约测试:fit_all_rb_methods(Rb 方法不变性)。

锁定:
  1. 全方法并行返回结构契约(4 方法 + ensemble + legacy + credible 标注)。
  2. 与 legacy fit_rb_and_conductivity 内部一致:legacy 选中的方法,其 Rb 必须等于
     fit_all_rb_methods 中同名方法的 Rb(证明是同一套 _preprocess/_method_*)。
  3. 可信集一致性:可信方法间 log10(Rb) 分歧小。
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ALGO_DIR = PROJECT_ROOT / "stage0_measurement"
if str(ALGO_DIR) not in sys.path:
    sys.path.insert(0, str(ALGO_DIR))

from modules.analysis.algorithms.rb_fitting import (  # noqa: E402
    fit_all_rb_methods, fit_rb_and_conductivity,
)


def _synthetic_spectrum(rb_true: float = 100.0, n: int = 60):
    """合成一条带清晰过零点的谱:Z'' 由负(低频容抗)单调升到正(高频感抗),
    过零处 Z' ≈ rb_true。频率升序 1 Hz..1 MHz。"""
    freq = np.logspace(0, 6, n)              # 升序
    zimag = np.linspace(-50.0, 20.0, n)      # 单调过零
    # Z' 在过零点附近 ≈ rb_true,两侧平滑变化
    zreal = rb_true + 12.0 * np.sin(np.linspace(-0.6, 0.6, n))
    return freq, zreal, zimag


def test_fit_all_rb_methods_contract():
    freq, zreal, zimag = _synthetic_spectrum(rb_true=100.0)
    res = fit_all_rb_methods(freq, zreal, zimag, thickness_cm=0.07, area_cm2=1.96,
                             temperature_K=298.15)

    assert res["success"] is True
    # 4 方法键齐全
    assert set(res["methods"].keys()) == {
        "reverse_zero_crossing", "reverse_valley", "low_freq_plateau", "equivalent_circuit"}
    for name, m in res["methods"].items():
        assert set(["applicable", "rb_ohm", "log10_rb", "fit_quality",
                    "failure_reason", "credible"]).issubset(m.keys())
    # 至少一种方法适用,ensemble 给出正 Rb 与 σ
    assert res["n_applicable"] >= 1
    ens = res["ensemble"]
    assert ens["rb_ohm"] is not None and ens["rb_ohm"] > 0
    assert ens["conductivity_s_per_cm"] is not None and ens["conductivity_s_per_cm"] > 0
    # σ = t/(Rb·A)
    assert ens["conductivity_s_per_cm"] == pytest.approx(0.07 / (ens["rb_ohm"] * 1.96), rel=1e-6)


def test_legacy_consistency():
    """legacy 路由选中的方法,其 Rb == fit_all 中同名方法的 Rb(同一套内部实现)。"""
    freq, zreal, zimag = _synthetic_spectrum(rb_true=100.0)
    legacy = fit_rb_and_conductivity(freq, zreal, zimag, 0.07, 1.96, 298.15)
    allm = fit_all_rb_methods(freq, zreal, zimag, 0.07, 1.96, 298.15)

    assert legacy["success"] is True
    legacy_method = legacy["method"]
    assert allm["legacy"]["method"] == legacy_method
    assert allm["legacy"]["rb_ohm"] == pytest.approx(legacy["rb_ohm"], rel=1e-9)
    # 同名方法 Rb 必须一致
    m = allm["methods"][legacy_method]
    assert m["applicable"] is True
    assert m["rb_ohm"] == pytest.approx(legacy["rb_ohm"], rel=1e-9)


def test_zero_crossing_recovers_rb():
    """干净过零谱:reverse_zero_crossing 应适用且 Rb 在 rb_true 附近。"""
    freq, zreal, zimag = _synthetic_spectrum(rb_true=100.0)
    res = fit_all_rb_methods(freq, zreal, zimag, 0.07, 1.96, 298.15)
    zc = res["methods"]["reverse_zero_crossing"]
    assert zc["applicable"] is True
    assert zc["rb_ohm"] == pytest.approx(100.0, abs=15.0)


def test_credible_spread_small_on_clean_spectrum():
    """可信集内方法分歧应远小于"全体适用"分歧(排除不适用方法后更紧)。"""
    freq, zreal, zimag = _synthetic_spectrum(rb_true=100.0)
    res = fit_all_rb_methods(freq, zreal, zimag, 0.07, 1.96, 298.15)
    ens = res["ensemble"]
    if res["n_applicable"] >= 2 and ens["n_credible"] >= 2:
        assert ens["method_spread_dex"] is not None
        # 可信集分歧应较小(干净谱)
        assert ens["method_spread_dex"] <= 0.30


def test_degenerate_input_returns_failure():
    res = fit_all_rb_methods([1, 2, 3], [1, 1, 1], [0, 0, 0],
                             thickness_cm=0.07, area_cm2=1.96, temperature_K=298.15)
    assert res["success"] is False
    assert res["error"] is not None
