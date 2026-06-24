# -*- coding: utf-8 -*-
"""M1-4 集成测试:证据准入(KK/QA → 用途分级)。

锁定核心不变量:P(无效谱进入 BO)=0，坏数据仍可诊断、不删。
测试名对齐 OPTIMIZATION_EXECUTION_PLAN §3 M1-4 / §4 CI 矩阵。
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ANALYSIS_DIR = PROJECT_ROOT / "stage0_measurement" / "modules" / "analysis"
if str(ANALYSIS_DIR) not in sys.path:
    sys.path.insert(0, str(ANALYSIS_DIR))

import evidence_admission as EA  # noqa: E402


def test_kk_fail_cannot_enter_real_history():
    s = EA.assess_admissibility(qa_failed=False, kk_mu_median=0.6)
    assert s.kk_status == "FAIL"
    assert EA.can_enter_bo(s) is False
    assert EA.can_enter_claim(s) is False
    assert s.objective_valid is False


def test_qa_fail_cannot_enter_bo():
    s = EA.assess_admissibility(qa_failed=True, kk_mu_median=0.01)
    assert s.qa_status == "FAIL"
    assert EA.can_enter_bo(s) is False
    assert s.scientific_admissibility == "DIAGNOSTIC_ONLY"


def test_kk_warn_inflates_variance():
    s = EA.assess_admissibility(qa_failed=False, kk_mu_median=0.25, rb_method_spread_dex=0.05)
    assert s.kk_status == "WARN"
    assert s.usage["bo_training"] == "variance_inflated"
    assert s.variance_multiplier > 1.0
    # 警告数据可进 BO 但需膨胀方差(算"允许")
    assert EA.can_enter_bo(s) is True


def test_rb_method_disagreement_blocks_bo_but_keeps_sensitivity():
    s = EA.assess_admissibility(qa_failed=False, kk_mu_median=0.05, rb_method_spread_dex=0.5)
    assert s.rb_extractability == "FAIL"
    assert EA.can_enter_bo(s) is False
    assert s.scientific_admissibility == "SENSITIVITY_ONLY"


def test_objective_valid_is_policy_derived():
    # 干净 + 不确定度已量化 → PRIMARY 且 objective_valid
    s = EA.assess_admissibility(qa_failed=False, kk_mu_median=0.05,
                                rb_method_spread_dex=0.02, uncertainty_status="QUANTIFIED")
    assert s.scientific_admissibility == "PRIMARY"
    assert s.objective_valid is True
    # 同样干净但不确定度 UNKNOWN → 不可作主证据
    s2 = EA.assess_admissibility(qa_failed=False, kk_mu_median=0.05,
                                 rb_method_spread_dex=0.02, uncertainty_status="UNKNOWN")
    assert s2.objective_valid is False


def test_diagnostic_data_remains_queryable():
    # 所有坏数据 diagnostic 始终 True(不删,供故障学习)
    for case in [
        dict(qa_failed=True, kk_mu_median=0.01),
        dict(qa_failed=False, kk_mu_median=0.6),
        dict(qa_failed=False, kk_mu_median=0.05, rb_method_spread_dex=0.5),
    ]:
        s = EA.assess_admissibility(**case)
        assert s.usage["diagnostic"] is True


def test_kk_not_testable():
    s = EA.assess_admissibility(qa_failed=False, kk_mu_median=None, kk_testable=False)
    assert s.kk_status == "NOT_TESTABLE"
