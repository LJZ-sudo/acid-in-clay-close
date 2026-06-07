"""Tests for the v2 engine tools (first batch + Phase A hardening).

All tests use synthetic_not_real_evidence fixtures and tmp dirs. No test reads or
writes three_pillars/ (round templates / evidence) or V1.0-qianduan-mainline/, and
no test emits a real result.
"""

from __future__ import annotations

import shutil
from argparse import Namespace
from pathlib import Path

from conftest import FIXTURES

import build_round_hash_manifest as brh
import verify_round_hash_manifest as vrh
import verify_approval_binding as vab
import verify_append_only_chain as vac
import validate_manual_rb_qc as vrb
import validate_score_layers as vsl
import v2_claim_unlock_check as vcu
import summarize_kk_residuals as skk
import check_chi_automation_preconditions as cchi
import verify_text_claims as vtc
import verify_memory_safe as vms
import run_all_checks as rac
from v2tools_common import TOOLS_DIR, is_iso8601, load_json

ROUND = FIXTURES / "round_valid_synthetic_not_real_evidence"
SCHEMA = load_json(TOOLS_DIR / "manual_rb_qc_schema.json")


# === existing-behavior regression =========================================

def test_build_manifest_complete():
    m = brh.build_manifest(ROUND)
    assert m["complete"] is True and m["rollup_sha256"]


def test_verify_manifest_ok_and_tampered(tmp_path):
    dst = tmp_path / "round"
    shutil.copytree(ROUND, dst)
    m = brh.build_manifest(dst)
    assert vrh.verify_manifest(dst, m)["verdict"] == "OK"
    (dst / "stage0_result.json").write_text('{"_marker":"synthetic_not_real_evidence","x":1}',
                                            encoding="utf-8")
    assert vrh.verify_manifest(dst, m)["verdict"] == "TAMPERED"


def test_approval_binding_match_and_mismatch(tmp_path):
    assert vab.verify_binding(ROUND)["verdict"] == "MATCH"
    dst = tmp_path / "round"
    shutil.copytree(ROUND, dst)
    (dst / "recipe.json").write_text('{"_marker":"synthetic_not_real_evidence","R":0.9}',
                                     encoding="utf-8")
    assert vab.verify_binding(dst)["verdict"] == "MISMATCH"


def test_score_clean_and_forbidden():
    assert vsl.validate_score(load_json(FIXTURES / "score_clean_synthetic_not_real_evidence.json"))["valid"]
    bad = vsl.validate_score(load_json(FIXTURES / "score_forbidden_synthetic_not_real_evidence.json"))
    assert bad["valid"] is False


# === 1. claim unlock: evidence-bound vs declared ==========================

def test_unlock_declared_never_allows():
    cond = {k: True for k in vcu.UNLOCK_CONDITIONS}
    r = vcu.evaluate_declared(cond)
    assert r["verdict"] == "DECLARED_ONLY_NOT_AUTHORITATIVE"
    assert r["authoritative"] is False
    # even a fully-true hand-written boolean JSON can NEVER reach ALLOW
    assert r["verdict"] != "ALLOW"


def test_unlock_declared_partial_hold():
    r = vcu.evaluate_declared({"signed_hash_bound_approval": True})
    assert r["verdict"] == "HOLD"


def test_unlock_evidence_none_holds():
    r = vcu.evaluate_evidence(None)
    assert r["verdict"] == "HOLD" and r["authoritative"] is True


def _full_evidence_map():
    base = FIXTURES / "unlock_evidence_synthetic_not_real_evidence"
    reports = {
        "signed_hash_bound_approval": ("approval_binding.json", "MATCH"),
        "real_append_only_raw_eis": ("append_only_chain.json", "OK"),
        "stage0_result_gate_pass": ("stage0_gate.json", None),
        "manual_rb_qc_acceptable": ("rb_qc.json", None),
        "score_gate_pass": ("score_gate.json", None),
        "history_import_reviewed": ("history_review.json", None),
        "stage3_rerun_claim_gate_passed": ("stage3_rerun.json", None),
        "new_frozen_manifest_and_presubmission_pass": ("new_freeze.json", None),
    }
    conditions = {}
    for cond, (fname, expected) in reports.items():
        entry = {"report": str(base / fname)}
        if expected is not None:
            entry["expected_verdict"] = expected
        conditions[cond] = entry
    return {"round_hash_manifest": str(base / "round_hash_manifest.json"),
            "conditions": conditions}


def test_unlock_evidence_full_allows():
    r = vcu.evaluate_evidence(_full_evidence_map())
    assert r["verdict"] == "ALLOW"
    assert r["round_hash_manifest_ok"] is True


def test_unlock_evidence_missing_report_holds():
    em = _full_evidence_map()
    em["conditions"]["score_gate_pass"]["report"] = str(FIXTURES / "does_not_exist.json")
    r = vcu.evaluate_evidence(em)
    assert r["verdict"] == "HOLD"
    assert any("score_gate_pass" in p for p in r["problems"])


def test_unlock_evidence_wrong_verdict_holds():
    em = _full_evidence_map()
    em["conditions"]["signed_hash_bound_approval"]["expected_verdict"] = "MISMATCH"
    r = vcu.evaluate_evidence(em)
    assert r["verdict"] == "HOLD"


def test_unlock_evidence_no_manifest_holds():
    em = _full_evidence_map()
    del em["round_hash_manifest"]
    r = vcu.evaluate_evidence(em)
    assert r["verdict"] == "HOLD" and r["round_hash_manifest_ok"] is False


# === 2. append-only chain: payload dual verification ======================

def test_chain_payload_clean():
    r = vac.verify_chain(FIXTURES / "append_only_payload_clean_synthetic_not_real_evidence")
    assert r["verdict"] == "OK"
    assert r["payload_checked_seqs"] == [0, 1, 2]


def test_chain_payload_missing():
    r = vac.verify_chain(FIXTURES / "append_only_payload_missing_synthetic_not_real_evidence")
    assert r["verdict"] == "PAYLOAD_MISSING"
    assert 1 in r["payload_missing_seqs"]


def test_chain_payload_replaced():
    r = vac.verify_chain(FIXTURES / "append_only_payload_replaced_synthetic_not_real_evidence")
    assert r["verdict"] == "PAYLOAD_REPLACED"
    assert 1 in r["payload_replaced_seqs"]


def test_chain_legacy_modes_still_work():
    assert vac.verify_chain(FIXTURES / "append_only_clean_synthetic_not_real_evidence")["verdict"] == "OK"
    assert vac.verify_chain(FIXTURES / "append_only_broken_synthetic_not_real_evidence")["verdict"] == "BROKEN_CHAIN"
    assert vac.verify_chain(FIXTURES / "append_only_overwrite_synthetic_not_real_evidence")["verdict"] == "OVERWRITE_DETECTED"


# === 3. manual Rb QC schema v2 ============================================

def test_iso8601_helper():
    assert is_iso8601("2026-06-01T00:00:00Z")
    assert is_iso8601("2026-06-01 00:00:00")
    assert not is_iso8601("06/01/2026")
    assert not is_iso8601("2026-06-01")  # bare date, no time component


def test_rb_qc_valid_v2():
    r = vrb.validate_csv(FIXTURES / "manual_rb_qc_valid_synthetic_not_real_evidence.csv", SCHEMA)
    assert r["valid"] is True


def test_rb_qc_invalid_v2():
    r = vrb.validate_csv(FIXTURES / "manual_rb_qc_invalid_synthetic_not_real_evidence.csv", SCHEMA)
    assert r["valid"] is False
    flat = " ".join(e for row in r["row_errors"] for e in row["errors"])
    assert "round_id" in flat            # empty round_id on main-text row
    assert "reviewed_at" in flat         # non-ISO timestamp
    assert "acceptance_decision" in flat or "qc_tier" in flat  # accepted+screening forbidden


# === 4. KK residual: kk_passed=false forces caveat ========================

def test_kk_passed_false_forces_caveat():
    r = skk.summarize(load_json(FIXTURES / "kk_bundle_passed_flag_synthetic_not_real_evidence.json"))
    assert r["kk_failed_points"] == 1
    # the failing point is within threshold numerically but must still caveat
    failing = [p for p in r["points"] if p["kk_passed"] is False]
    assert failing and failing[0]["bounded_caveat_required"] is True
    assert failing[0]["verdict"] == "KK_FAILED_BOUNDED_CAVEAT"
    assert r["any_bounded_caveat_required"] is True


def test_kk_numeric_above_threshold_still_caveats():
    r = skk.summarize(load_json(FIXTURES / "kk_bundle_numeric_synthetic_not_real_evidence.json"))
    assert r["above_threshold_points"] == 1
    assert r["eis_is_mechanism_proof"] is False


# === 5. CHI: synthetic vs real evidence ===================================

def test_chi_disabled_no_dir():
    r = cchi.check(None)
    assert r["verdict"] == "DISABLED" and r["enables_chi_automation"] is False


def test_chi_synthetic_preconditions_met():
    r = cchi.check(FIXTURES / "chi_full_evidence_synthetic_not_real_evidence")
    assert r["verdict"] == "PRECONDITIONS_MET_SYNTHETIC"
    assert r["evidence_looks_synthetic"] is True
    assert r["enables_chi_automation"] is False


def test_chi_real_evidence_requires_human_review(tmp_path):
    # Copy the real-ish fixture into a marker-free dir so it reads as "real".
    src = FIXTURES / "chi_realish_evidence_synthetic_not_real_evidence"
    dst = tmp_path / "chi_device_evidence"
    dst.mkdir()
    for name in ("CHI_AUTOMATION_POLICY.md", "CHI_MACRO_VALIDATION.md",
                 "CHI_MACRO_COMMAND_REGISTRY.md", "macro_command_registry.yaml",
                 "macrotest_evidence.json", "dummy_cell_evidence.json",
                 "chi_eis_preflight_gate.json"):
        shutil.copyfile(src / name, dst / name)
    r = cchi.check(dst)
    assert r["verdict"] == "HUMAN_DEVICE_REVIEW_REQUIRED"
    assert r["evidence_looks_synthetic"] is False
    assert r["enables_chi_automation"] is False  # NEVER enables


def test_chi_needs_macro_disabled():
    r = cchi.check(FIXTURES / "chi_needs_macro_synthetic_not_real_evidence")
    assert r["verdict"] == "DISABLED"


# === 6. text-claim traceability ===========================================

def test_text_clean_traces():
    text = (FIXTURES / "text_clean_synthetic_not_real_evidence.md").read_text(encoding="utf-8")
    cm = load_json(FIXTURES / "claim_map_synthetic_not_real_evidence.json")
    r = vtc.verify_text(text, cm)
    assert r["valid"] is True
    assert r["performance_numbers_found"] >= 3


def test_text_untraceable_fails():
    text = (FIXTURES / "text_untraceable_synthetic_not_real_evidence.md").read_text(encoding="utf-8")
    cm = load_json(FIXTURES / "claim_map_synthetic_not_real_evidence.json")
    r = vtc.verify_text(text, cm)
    assert r["valid"] is False
    assert any(abs(n["value"] - 0.9999) < 1e-6 for n in r["untraceable_numbers"])


def test_text_forbidden_wording_fails():
    cm = load_json(FIXTURES / "claim_map_synthetic_not_real_evidence.json")
    r = vtc.verify_text("synthetic: this is the global optimum.", cm)
    assert r["valid"] is False
    assert "global optimum" in r["forbidden_wording_hits"]


def test_text_anchor_without_provenance_ignored():
    # an allowed_number lacking sample_id/path is not a valid trace
    cm = {"allowed_numbers": [{"value": "0.5", "unit": "eV"}]}
    r = vtc.verify_text("synthetic Ea_high 0.5 eV", cm)
    assert r["valid"] is False


# === 7. memory safety =====================================================

def test_memory_safe():
    r = vms.verify_memory(load_json(FIXTURES / "memory_safe_synthetic_not_real_evidence.json"))
    assert r["verdict"] == "SAFE" and r["violation_count"] == 0


def test_memory_unsafe():
    r = vms.verify_memory(load_json(FIXTURES / "memory_unsafe_synthetic_not_real_evidence.json"))
    assert r["verdict"] == "UNSAFE"
    types = {v["type"] for v in r["violations"]}
    assert "forbidden_wording" in types
    assert "unsourced_performance_number" in types
    assert "fabricated_experiment_result" in types


# === 8. run_all_checks aggregator =========================================

def _args(**kw):
    base = dict(round_dir=None, intake_dir=None, kk_bundle=None, text=None,
                claim_map=None, memory=None, chi_evidence_dir=None,
                evidence_map=None, write=None)
    base.update(kw)
    return Namespace(**base)


def test_run_all_dryrun_allowed_when_green():
    args = _args(
        round_dir=str(ROUND),
        intake_dir=str(FIXTURES / "append_only_payload_clean_synthetic_not_real_evidence"),
        kk_bundle=str(FIXTURES / "kk_bundle_numeric_synthetic_not_real_evidence.json"),
        text=str(FIXTURES / "text_clean_synthetic_not_real_evidence.md"),
        claim_map=str(FIXTURES / "claim_map_synthetic_not_real_evidence.json"),
        memory=str(FIXTURES / "memory_safe_synthetic_not_real_evidence.json"),
        chi_evidence_dir=str(FIXTURES / "chi_full_evidence_synthetic_not_real_evidence"),
    )
    r = rac.run_all(args)
    assert r["gate"] == "DRYRUN_ALLOWED"
    assert r["v2_claims_status"] == "HOLD"
    assert r["enables_chi_automation"] is False
    # claim unlock stays HOLD (no evidence map supplied)
    assert r["claim_unlock"]["verdict"] == "HOLD"


def test_run_all_holds_on_failed_check():
    args = _args(
        round_dir=str(ROUND),
        intake_dir=str(FIXTURES / "append_only_payload_missing_synthetic_not_real_evidence"),
    )
    r = rac.run_all(args)
    assert r["gate"] == "HOLD"
    assert "append_only_chain" in r["failed_checks"]


def test_run_all_holds_on_unsafe_memory():
    args = _args(
        round_dir=str(ROUND),
        memory=str(FIXTURES / "memory_unsafe_synthetic_not_real_evidence.json"),
    )
    r = rac.run_all(args)
    assert r["gate"] == "HOLD"
    assert "memory_safe" in r["failed_checks"]


# === boundary guarantee ===================================================

def test_protected_prefixes_declared():
    from v2tools_common import PROTECTED_PREFIXES
    assert "three_pillars" in PROTECTED_PREFIXES
    assert "V1.0-qianduan-mainline" in PROTECTED_PREFIXES
