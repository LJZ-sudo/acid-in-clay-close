# -*- coding: utf-8 -*-
"""WP1-a：C_M 按用途分级准入(U1–U6)契约测试。"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

MAINLINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MAINLINE / "stage1_optimization"))

from scientific_harness.admission import (  # noqa: E402
    IntendedUse, assess_use, assess_all_uses, assess_claim_admission, USE_MAX_CLAIM_LEVEL,
    ADMIT, CONDITIONAL, REJECT, CONTESTED,
)

_CLEAN = dict(
    qa_failed=False, kk_mu_median=0.05, rb_method_spread_dex=0.02,
    uncertainty_status="QUANTIFIED", geometry_valid=True, rb_method_success=True,
    n_series_points=37, method_routing_sensitivity_passed=True, synthetic_fpr_passed=True,
    model_comparison_ok=True, identifiable=True, independent_support=True, alternatives_present=True,
)


def _sig(**over):
    s = dict(_CLEAN)
    s.update(over)
    return s


def test_u1_rejects_qa_fatal_admits_clean():
    assert assess_use(IntendedUse.PRESERVE_OBSERVATION, _sig()).status == ADMIT
    assert assess_use(IntendedUse.PRESERVE_OBSERVATION, _sig(qa_failed=True)).status == REJECT


def test_u2_rejects_rb_disagreement_conditional_on_ecm():
    # Rb 方法严重不一致 → 底层 rb_extractability=FAIL → U2 REJECT
    bad = assess_use(IntendedUse.ESTIMATE_POINT_CONDUCTIVITY, _sig(rb_method_spread_dex=0.5))
    assert bad.status == REJECT
    # 等效电路兜底 → CONDITIONAL
    cond = assess_use(IntendedUse.ESTIMATE_POINT_CONDUCTIVITY, _sig(ecm_fallback=True))
    assert cond.status == CONDITIONAL
    assert assess_use(IntendedUse.ESTIMATE_POINT_CONDUCTIVITY, _sig()).status == ADMIT


def test_u3_contested_when_breakpoint_matches_method_switch():
    c = assess_use(IntendedUse.ESTIMATE_BREAKPOINT, _sig(breakpoint_matches_method_switch=True))
    assert c.status == CONTESTED
    assert "BREAKPOINT_COINCIDES_RB_METHOD_SWITCH" in c.reason_codes


def test_u3_rejects_insufficient_points():
    assert assess_use(IntendedUse.ESTIMATE_BREAKPOINT, _sig(n_series_points=5)).status == REJECT


def test_u4_conditional_when_non_identifiable():
    c = assess_use(IntendedUse.COMPARE_TRANSPORT_MODELS, _sig(identifiable=False))
    assert c.status == CONDITIONAL
    assert "NON_IDENTIFIABLE_MODEL_EQUIVALENCE_ONLY" in c.reason_codes


def test_u5_update_bo_requires_primary_and_objective_valid():
    # KK 警告 → SENSITIVITY_ONLY(非 PRIMARY)→ U5 REJECT
    r = assess_use(IntendedUse.UPDATE_BO, _sig(kk_mu_median=0.25))
    assert r.status == REJECT
    assert assess_use(IntendedUse.UPDATE_BO, _sig()).status == ADMIT


def test_u6_requires_independent_support_and_alternatives():
    assert assess_use(IntendedUse.MECHANISTIC_CONSISTENCY, _sig(independent_support=False)).status == REJECT
    assert assess_use(IntendedUse.MECHANISTIC_CONSISTENCY, _sig(alternatives_present=False)).status == REJECT
    ok = assess_use(IntendedUse.MECHANISTIC_CONSISTENCY, _sig())
    assert ok.status == CONDITIONAL and ok.max_claim_level == "C4"


def test_eis_only_hard_cap_c4():
    order = ["C0", "C1", "C2", "C3", "C4", "C5"]
    for use, cap in USE_MAX_CLAIM_LEVEL.items():
        assert order.index(cap) <= order.index("C4"), use


def test_assess_all_uses_returns_six():
    res = assess_all_uses(_sig())
    assert set(res.keys()) == set(IntendedUse.ALL)
    assert len(res) == 6


# --- WP1-b: C_E 绑定主张 -----------------------------------------------------

def _claim(**over):
    kw = dict(evidence_id="E-1", claim_id="C-1",
              intended_use=IntendedUse.ESTIMATE_BREAKPOINT, requested_level="C3",
              signals=_sig())
    kw.update(over)
    return assess_claim_admission(**kw)


def test_ce_admits_breakpoint_claim_at_c3():
    a = _claim()
    assert a.ce_status == ADMIT and a.granted_level == "C3"


def test_ce_rejects_overclaim_beyond_use_cap():
    # 用断点用途(cap C3)去支持 C4 主张 → 过度声称 REJECT,granted=cap C3
    a = _claim(requested_level="C4")
    assert a.ce_status == REJECT and a.granted_level == "C3"
    assert any("OVERCLAIM" in r for r in a.reason_codes)


def test_ce_never_exceeds_c4_eis_cap():
    # 机制一致性用途请求 C5 → 必拒(EIS 硬封顶 C4)
    a = _claim(intended_use=IntendedUse.MECHANISTIC_CONSISTENCY, requested_level="C5")
    assert a.ce_status == REJECT
    assert _C_ORDER.index(a.granted_level) <= _C_ORDER.index("C4")


def test_ce_rejects_when_use_contested():
    a = _claim(signals=_sig(breakpoint_matches_method_switch=True))
    assert a.cm_status == CONTESTED and a.ce_status == REJECT and a.granted_level == "C0"


_C_ORDER = ["C0", "C1", "C2", "C3", "C4", "C5"]
