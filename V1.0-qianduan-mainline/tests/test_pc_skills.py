# -*- coding: utf-8 -*-
"""WP2 PC-Skills:6 真实 Skill + 三层证书 + runtime + 双账户 gate。"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

MAINLINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MAINLINE / "stage1_optimization"))

from scientific_skills.skills_eis import (  # noqa: E402
    build_eis_skill_chain, EIS_SKILL_CHAIN_ORDER, ENVIRONMENTAL_CAPABILITIES,
)
from scientific_skills.registry import SkillRegistry  # noqa: E402
from scientific_skills.contracts import Lifecycle  # noqa: E402
from scientific_skills.certificate_service import (  # noqa: E402
    certify_skill, wilson_lower_bound,
)
from scientific_skills.runtime import (  # noqa: E402
    decide_execution, build_evidence_bundle, check_chain_executable,
    ALLOW, SHADOW, HUMAN_APPROVAL, REJECT,
)
from scientific_skills.dual_account import RiskClearing  # noqa: E402

_METROLOGY_OK = {"calibration_valid": True, "analysis_version": "stage0_v2@1",
                 "uncertainty_status": "QUANTIFIED"}
_STRONG_HISTORY = {"n_success": 49, "n_total": 50}
_SMALL_HISTORY = {"n_success": 3, "n_total": 3}


def _registry_with_chain():
    reg = SkillRegistry()
    for c in build_eis_skill_chain():
        reg.register(c, state=Lifecycle.DRAFT)
    return reg


# ---- WP2-b: 6 个真实 Skill + 组合 ----

def test_six_skills_and_composition_holds():
    reg = _registry_with_chain()
    assert [c.skill_id for c in build_eis_skill_chain()] == EIS_SKILL_CHAIN_ORDER
    # 注入环境前置(calibration_valid/instrument_reserved 由系统提供,非上游产出)
    ok, detail = reg.check_composition(EIS_SKILL_CHAIN_ORDER, provided=ENVIRONMENTAL_CAPABILITIES)
    assert ok, detail   # post(S_i) ⊨ pre(S_{i+1}) 必须成立


def test_composition_breaks_if_reordered():
    reg = _registry_with_chain()
    bad = list(reversed(EIS_SKILL_CHAIN_ORDER))
    ok, _ = reg.check_composition(bad, provided=ENVIRONMENTAL_CAPABILITIES)
    assert ok is False   # 逆序后 admit 先行,缺 transport_metrics → 仍应失败


# ---- WP2-c: 三层证书由检查产生 ----

def test_wilson_lower_bound_monotone():
    assert wilson_lower_bound(3, 3) < wilson_lower_bound(49, 50)
    assert wilson_lower_bound(0, 0) == 0.0


def test_strong_history_certifies():
    c = build_eis_skill_chain()[3]  # assess_eis_quality
    rep = certify_skill(c, history=_STRONG_HISTORY, metrology=_METROLOGY_OK)
    assert rep.all_layers_pass is True
    assert rep.provisional is False
    assert all(rep.validator_results.values())


def test_small_sample_is_provisional_and_not_certified_at_high_bar():
    c = build_eis_skill_chain()[3]
    rep = certify_skill(c, history=_SMALL_HISTORY, metrology=_METROLOGY_OK, min_pass_rate=0.8)
    assert rep.statistical["provisional"] is True
    assert rep.statistical["ok"] is False         # 置信下界达不到 0.8
    assert rep.recommended_autonomy in ("SHADOW", "DRAFT")
    assert not all(rep.validator_results.values())  # 不全 True → 不可发证


def test_metrological_failure_blocks_certification():
    c = build_eis_skill_chain()[3]
    rep = certify_skill(c, history=_STRONG_HISTORY,
                        metrology={"calibration_valid": False, "analysis_version": "",
                                   "uncertainty_status": "UNKNOWN"})
    assert rep.metrological["ok"] is False
    assert rep.all_layers_pass is False


def test_certificate_service_feeds_registry_certify():
    reg = _registry_with_chain()
    c = reg.get("assess_eis_quality")
    rep = certify_skill(c, history=_STRONG_HISTORY, metrology=_METROLOGY_OK)
    ok, cert = reg.certify("assess_eis_quality", rep.validator_results,
                           rep.risk_estimate, rep.risk_upper_bound, code_hash="abc")
    assert ok and cert is not None
    assert reg.state("assess_eis_quality") == Lifecycle.VALIDATED


# ---- WP2-d / WP2-f: runtime + 双账户 ----

def _validated_registry():
    reg = _registry_with_chain()
    c = reg.get("assess_eis_quality")
    rep = certify_skill(c, history=_STRONG_HISTORY, metrology=_METROLOGY_OK)
    reg.certify("assess_eis_quality", rep.validator_results,
                rep.risk_estimate, rep.risk_upper_bound, code_hash="abc")
    return reg


def test_unvalidated_skill_rejected():
    reg = _registry_with_chain()  # 全 DRAFT,未发证
    d = decide_execution(reg, "assess_eis_quality", {})
    assert d.decision == REJECT


def test_validated_skill_allowed():
    reg = _validated_registry()
    d = decide_execution(reg, "assess_eis_quality", {}, risk_clearing=RiskClearing(r_max=0.2))
    assert d.decision == ALLOW


def test_dual_account_ignores_claimed_confidence():
    """同一风险下,自报置信 0.5 vs 0.999 必须得到相同决策(执行权≠自信)。"""
    reg = _validated_registry()
    low = decide_execution(reg, "assess_eis_quality", {}, claimed_confidence=0.5)
    high = decide_execution(reg, "assess_eis_quality", {}, claimed_confidence=0.999)
    assert low.decision == high.decision


def test_high_risk_requires_human_approval():
    reg = _validated_registry()
    # r_max 收紧到极小 → 风险清算失败 → 需人工
    d = decide_execution(reg, "assess_eis_quality", {}, risk_clearing=RiskClearing(r_max=0.0))
    assert d.decision == HUMAN_APPROVAL


def test_evidence_bundle_binds_cert_and_outputs():
    reg = _validated_registry()
    b = build_evidence_bundle(reg, "assess_eis_quality",
                              context={"T": 298}, outputs={"qa_status": "PASS"},
                              witnesses=["raw_file_hash"], transaction_id="txn-1", decision=ALLOW)
    assert b.skill_id == "assess_eis_quality"
    assert b.certificate_id is not None
    assert b.outputs["qa_status"] == "PASS"
    assert b.transaction_id == "txn-1"


# ---- WP2-e: 漂移 + 撤销 ----

def test_code_change_suspends_drift():
    from scientific_skills.drift import detect_drift, DriftAction
    d = detect_drift(baseline_code_hash="aaaa1111", current_code_hash="bbbb2222")
    assert d.drifted and d.action == DriftAction.SUSPEND


def test_success_drop_degrades_drift():
    from scientific_skills.drift import detect_drift, DriftAction
    d = detect_drift(baseline_success_rate=0.95, current_success_rate=0.70)
    assert d.drifted and d.action == DriftAction.DEGRADE


def test_no_drift_when_stable():
    from scientific_skills.drift import detect_drift, DriftAction
    d = detect_drift(baseline_code_hash="x", current_code_hash="x",
                     baseline_success_rate=0.95, current_success_rate=0.93)
    assert d.action == DriftAction.NONE


def test_suspend_drops_cert_and_blocks_execution():
    reg = _validated_registry()
    assert decide_execution(reg, "assess_eis_quality", {}).decision == ALLOW
    reg.suspend("assess_eis_quality", reason="firmware_changed")
    assert reg.certificate("assess_eis_quality") is None
    assert decide_execution(reg, "assess_eis_quality", {}).decision == REJECT


def test_revoke_produces_impact_request_and_blocks():
    from scientific_skills.revocation import revoke_skill
    reg = _validated_registry()
    req = revoke_skill(reg, "assess_eis_quality", reason="bad_calibration",
                       evidence_index={"assess_eis_quality": ["E-1", "E-2"]})
    assert req.affected_evidence_ids == ["E-1", "E-2"]
    assert req.downstream_propagation_done is False     # E-Mem(WP3)未接入,显式标未传播
    assert decide_execution(reg, "assess_eis_quality", {}).decision == REJECT
