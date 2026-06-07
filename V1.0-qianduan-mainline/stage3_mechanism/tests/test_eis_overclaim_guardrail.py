"""Tier2 (issue 3-cont): EIS-overclaim guardrail wiring into S14.

Before Tier2 the EIS guardrail regex existed but was never called anywhere.
These tests pin: (1) the regex catches absolute EIS claims and passes clean text;
(2) S14 runs the guardrail and is ADVISORY by default (no new blocker, frozen
publication_blockers=[] preserved); (3) strict mode promotes findings to blockers.
"""
from __future__ import annotations

from pathlib import Path

from s8_stage3.config.settings import Stage3Settings
from s8_stage3.preprocess.eis_guardrails import check_eis_absolute_claims


def test_check_eis_absolute_claims_detects_and_passes():
    assert check_eis_absolute_claims("EIS proves the grain boundary mechanism")
    assert check_eis_absolute_claims("等效电路已确定")
    # Hedged / correct phrasing must NOT trip the guardrail.
    assert not check_eis_absolute_claims(
        "The semicircle is consistent with an interfacial process; EIS suggests a trend."
    )


def test_s14_advisory_default_no_eis_blocker(tmp_path):
    from s8_stage3.agents.s14_claim_auditor import run_s14

    report = run_s14(tmp_path, Stage3Settings())
    # Advisory by default: count recorded, strict flag off, no EIS blocker injected.
    assert report.inputs_digest.get("eis_overclaim_strict") == "0"
    assert "eis_overclaim_findings_count" in report.inputs_digest
    assert not any(b.startswith("EIS_OVERCLAIM") for b in report.publication_blockers)


def test_s14_strict_promotes_findings_to_blockers(tmp_path, monkeypatch):
    import s8_stage3.agents.s14_claim_auditor as s14

    # Force a finding deterministically to exercise the strict promotion path.
    monkeypatch.setattr(
        s14, "check_eis_absolute_claims", lambda _text: ["Pattern matched: ...EIS proves..."]
    )
    report = s14.run_s14(tmp_path, Stage3Settings(), strict_eis_guardrail=True)
    assert report.inputs_digest.get("eis_overclaim_strict") == "1"
    assert report.inputs_digest.get("eis_overclaim_findings_count") == "1"
    assert any(b.startswith("EIS_OVERCLAIM(strict)") for b in report.publication_blockers)


def test_s14_advisory_does_not_block_even_with_findings(tmp_path, monkeypatch):
    import s8_stage3.agents.s14_claim_auditor as s14

    monkeypatch.setattr(
        s14, "check_eis_absolute_claims", lambda _text: ["Pattern matched: ...EIS confirms..."]
    )
    report = s14.run_s14(tmp_path, Stage3Settings(), strict_eis_guardrail=False)
    assert report.inputs_digest.get("eis_overclaim_findings_count") == "1"
    assert not any(b.startswith("EIS_OVERCLAIM") for b in report.publication_blockers)
