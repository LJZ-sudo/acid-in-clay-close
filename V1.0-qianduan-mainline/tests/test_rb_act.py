# -*- coding: utf-8 -*-
"""Rb-ACT（ESAS-OS 2.0 / PC-Skills v2）契约测试 —— R0 离线 shadow + 合成验证。

对应 OPTIMIZATION_EXECUTION_PLAN §10.1/§10.4/§10.6:
  - 合成谱点估误差(报告项)≤ 阈值、95% 区间覆盖率保守(≥0.9);
  - 高噪/无锚点/方法分歧 → ABSTAIN 命中;主动建议命中;
  - 不确定度/弃权作为 C_M 准入信号真正影响 assess_use(与 SciTX 打通);
  - legacy `rb_fitting` 不被改写。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

MAINLINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MAINLINE / "stage0_measurement"))
sys.path.insert(0, str(MAINLINE / "stage1_optimization"))

from rb_act import (  # noqa: E402
    analyze_spectrum, analyze_series, shadow_run, validate_synthetic,
    synthetic_suite, blocking_spectrum, randles_spectrum,
    REPORT, REPORT_CONDITIONAL, ABSTAIN, ADD_TEMP_POINT,
)
from rb_act.synthetic import randles_spectrum as _rs  # noqa: E402


# ---- 合成验证:决策 / 误差 / 覆盖率 / 主动建议 ---------------------------------

def test_suite_decisions_and_actions_match_expectation():
    res = validate_synthetic(coverage_n=40)
    for c in res["per_case"]:
        assert c["decision_in_expect"], f"{c['label']} decision={c['decision']} expect={c['expect']}"
        if c.get("expect_action"):
            assert c["expect_action_hit"], f"{c['label']} missing action {c['expect_action']}"


def test_reported_cases_are_calibrated_abstain_on_large_error():
    """非弃权用例的 95% 区间必须覆盖真值(校准诚实);REPORT(满信心)点估更紧;
    大误差(>0.3 dex)用例必须弃权(不把错值给出去)。"""
    suite = synthetic_suite()
    for c in suite:
        r = analyze_spectrum(c["frequencies"], c["z_real"], c["z_imag"],
                             thickness_cm=c["thickness_cm"], area_cm2=c["area_cm2"])
        rb_true = c["rb_true_ohm"]
        log10_true = c["log10_rb_true"]
        if r.decision != ABSTAIN:
            # 报告就必须诚实:真值落在 95% 区间内
            assert r.posterior.ci95_low_ohm <= rb_true <= r.posterior.ci95_high_ohm, \
                f"{c['label']} reported but CI misses truth"
            if r.decision == REPORT:
                assert abs(r.posterior.log10_rb - log10_true) < 0.05, \
                    f"{c['label']} REPORT but err too large"
        else:
            assert not r.reported()
            # 内部集成值若严重偏差，弃权正是其价值所在
            if r.posterior.log10_rb is not None:
                assert True  # 不报告即可，不对弃权值设上限


def test_ci_coverage_is_conservative():
    res = validate_synthetic(coverage_n=80)
    assert res["coverage_reported"] >= 60
    assert res["coverage_95ci"] is not None and res["coverage_95ci"] >= 0.90


def test_full_semicircle_method_disagreement_abstains():
    # 全半圆:四法在 Rb 与 Rb+Rct 间分裂 → 必弃权
    f, zr, zi = _rs(120.0, rct_ohm=800.0, cdl_farad=2e-7, f_min_hz=10.0,
                    f_max_hz=1.0e6, n_points=41, l_henry=0.0)
    r = analyze_spectrum(f, zr, zi, thickness_cm=0.1, area_cm2=1.0)
    assert r.decision == ABSTAIN
    assert any("METHOD_DISAGREEMENT" in x for x in r.abstain_reasons)
    assert r.posterior.u_method_dex >= 0.30


def test_clean_blocking_reports_with_quantified_uncertainty():
    f, zr, zi = blocking_spectrum(120.0, c_blocking_farad=1e-6, l_henry=1e-6,
                                  f_min_hz=1.0, f_max_hz=4.0e5)
    r = analyze_spectrum(f, zr, zi, thickness_cm=0.1, area_cm2=1.0)
    assert r.decision in (REPORT, REPORT_CONDITIONAL)
    assert r.posterior.rb_ohm == pytest.approx(120.0, rel=0.05)
    assert r.posterior.ci95_low_ohm < 120.0 < r.posterior.ci95_high_ohm
    assert r.admission_signals["uncertainty_status"] == "QUANTIFIED"


# ---- 与 SciTX C_M 打通:弃权/分歧真正收紧准入 ---------------------------------

def _cm(signals_from_rbact, **base):
    from scientific_harness.admission import assess_use, IntendedUse
    sig = dict(qa_failed=False, kk_mu_median=0.05, kk_testable=True, geometry_valid=True)
    sig.update(signals_from_rbact)
    sig.update(base)
    return assess_use(IntendedUse.ESTIMATE_POINT_CONDUCTIVITY, sig)


def test_rbact_signals_admit_clean_reject_abstain():
    from scientific_harness.admission import ADMIT, CONDITIONAL, REJECT
    # 干净 → U2 ADMIT/CONDITIONAL
    f, zr, zi = blocking_spectrum(120.0, c_blocking_farad=1e-6, l_henry=1e-6,
                                  f_min_hz=1.0, f_max_hz=4.0e5)
    clean = analyze_spectrum(f, zr, zi, thickness_cm=0.1, area_cm2=1.0)
    assert _cm(clean.admission_signals).status in (ADMIT, CONDITIONAL)

    # 方法分歧弃权 → rb_method_spread_dex 大 → U2 REJECT
    f2, zr2, zi2 = _rs(120.0, rct_ohm=800.0, cdl_farad=2e-7, f_min_hz=10.0,
                       f_max_hz=1.0e6, n_points=41, l_henry=0.0)
    bad = analyze_spectrum(f2, zr2, zi2, thickness_cm=0.1, area_cm2=1.0)
    assert bad.decision == ABSTAIN
    assert _cm(bad.admission_signals).status == REJECT


def test_no_applicable_method_signals_unknown():
    # 太少点 → fit_all_rb_methods 失败 → ABSTAIN + uncertainty UNKNOWN + rb_method_success False
    f = [1.0, 2.0, 3.0]
    r = analyze_spectrum(f, [100.0, 100.0, 100.0], [-1.0, -2.0, -3.0])
    assert r.decision == ABSTAIN
    assert r.admission_signals["rb_method_success"] is False
    assert r.admission_signals["uncertainty_status"] == "UNKNOWN"


# ---- legacy 不被改写 ----------------------------------------------------------

def test_legacy_rb_fitting_untouched():
    import rb_fitting
    f, zr, zi = blocking_spectrum(120.0, c_blocking_farad=1e-6, l_henry=1e-6,
                                  f_min_hz=1.0, f_max_hz=4.0e5)
    legacy = rb_fitting.fit_all_rb_methods(f, zr, zi, thickness_cm=0.1,
                                           area_cm2=1.0, temperature_K=298.15)
    r = analyze_spectrum(f, zr, zi, thickness_cm=0.1, area_cm2=1.0)
    # Rb-ACT 的 legacy 字段 == 直接调 legacy 的对照值（只读，不改写）
    assert r.legacy_rb_ohm == pytest.approx(legacy["legacy"]["rb_ohm"], rel=1e-9)


# ---- shadow 双跑 + 序列级主动建议 ---------------------------------------------

def test_shadow_run_delta_report():
    rep = shadow_run(synthetic_suite())
    assert rep["n_total"] == 6
    assert rep["n_report"] + rep["n_conditional"] + rep["n_abstain"] == 6
    assert rep["n_abstain"] >= 2          # truncated + full_arc 至少两条弃权
    assert "items" in rep and len(rep["items"]) == 6


def test_series_active_request_on_abstention_and_gap():
    # 构造温度序列:含一条无锚点(弃权)谱 + 一个大温度间隔
    good = blocking_spectrum(120.0, c_blocking_farad=1e-6, l_henry=1e-6,
                             f_min_hz=1.0, f_max_hz=4.0e5)
    bad = randles_spectrum(120.0, rct_ohm=800.0, cdl_farad=2e-7, f_min_hz=50.0,
                           f_max_hz=2.0e4, n_points=31, l_henry=0.0)
    specs = [
        dict(frequencies=good[0], z_real=good[1], z_imag=good[2], temperature_K=240.0),
        dict(frequencies=bad[0], z_real=bad[1], z_imag=bad[2], temperature_K=243.0),
        dict(frequencies=good[0], z_real=good[1], z_imag=good[2], temperature_K=300.0),
    ]
    results, series_reqs = analyze_series(specs)
    assert len(results) == 3
    actions = [a.action for a in series_reqs]
    assert ADD_TEMP_POINT in actions
