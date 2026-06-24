# -*- coding: utf-8 -*-
"""M5-C 测试:可认证 Skills + 双账户 + risk-coverage + Demo C 验收。"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
STAGE1 = PROJECT_ROOT / "stage1_optimization"
if str(STAGE1) not in sys.path:
    sys.path.insert(0, str(STAGE1))

from scientific_skills.contracts import ScientificSkillContract, Lifecycle  # noqa: E402
from scientific_skills.registry import SkillRegistry  # noqa: E402
from scientific_skills.dual_account import EpistemicAccount, RiskClearing  # noqa: E402
from scientific_skills.risk_coverage import risk_coverage_curve  # noqa: E402


def _draft_skill():
    return ScientificSkillContract(
        skill_id="s", version="1.0.0",
        applicability_domain={"R": [0.0, 1.04]},
        preconditions=[], postconditions=["x"], validators=["v1"])


def test_control_plane_only_validated():
    reg = SkillRegistry()
    reg.register(_draft_skill(), state=Lifecycle.DRAFT)
    ok, reason = reg.can_execute("s", {"R": 0.5})
    assert ok is False and "not_validated" in reason
    # 认证后可执行
    reg.certify("s", {"v1": True}, risk_estimate=0.01, risk_upper_bound=0.05)
    ok2, _ = reg.can_execute("s", {"R": 0.5})
    assert ok2 is True


def test_out_of_certified_domain_rejected():
    reg = SkillRegistry()
    reg.register(_draft_skill())
    reg.certify("s", {"v1": True}, 0.01, 0.05)
    ok, reason = reg.can_execute("s", {"R": 2.0})  # 超出 [0,1.04]
    assert ok is False and reason == "out_of_certified_domain"


def test_certify_fails_if_validator_fails():
    reg = SkillRegistry()
    reg.register(_draft_skill())
    ok, cert = reg.certify("s", {"v1": False}, 0.01, 0.05)
    assert ok is False and cert is None
    assert reg.state("s") == Lifecycle.DRAFT


def test_composition_post_models_pre():
    reg = SkillRegistry()
    reg.register(ScientificSkillContract("a", "1", preconditions=[], postconditions=["p1"]))
    reg.register(ScientificSkillContract("b", "1", preconditions=["p1"], postconditions=["p2"]))
    ok, _ = reg.check_composition(["a", "b"])
    assert ok is True
    broken, det = reg.check_composition(["b"])   # b 需 p1 但无上游
    assert broken is False
    assert det[0]["missing_preconditions"] == ["p1"]


def test_dual_account_confidence_not_authority():
    rc = RiskClearing(r_max=0.2)
    low = rc.act(cert_valid=True, in_domain=True, risk_estimate=0.05, uncertainty=0.02,
                 claimed_confidence=0.50)
    high = rc.act(cert_valid=True, in_domain=True, risk_estimate=0.05, uncertainty=0.02,
                  claimed_confidence=0.999)
    assert low == high                      # 自报置信度不改变执行权
    assert rc.authority_depends_on_confidence() is False


def test_risk_clearing_blocks_high_risk():
    rc = RiskClearing(r_max=0.2)
    assert rc.act(cert_valid=True, in_domain=True, risk_estimate=0.3, uncertainty=0.05) is False
    assert rc.act(cert_valid=False, in_domain=True, risk_estimate=0.01, uncertainty=0.0) is False


def test_overconfidence_penalized_by_brier():
    epi = EpistemicAccount()
    for _ in range(10):
        epi.record("over", 0.99, 0)
        epi.record("cal", 0.5, 0)
    assert epi.brier("over") > epi.brier("cal")


def test_risk_coverage_beats_const_hold():
    claims = [(0.95, 1), (0.9, 1), (0.8, 0), (0.6, 1), (0.4, 0)]
    rc = risk_coverage_curve(claims)
    assert rc["const_hold_coverage"] == 0.0
    assert rc["max_coverage_at_risk_0.10"] > 0.0   # 选择性放行优于恒 HOLD


def test_demo_c_acceptance_passes():
    from scientific_skills import demo_c
    res = demo_c.run()
    assert res["acceptance_pass"] is True
    c = res["checks"]
    assert c["control_plane_only_validated_and_in_domain"] is True
    assert c["composition_post_models_pre"] is True
    assert c["dual_account_separated_confidence_not_authority"] is True
