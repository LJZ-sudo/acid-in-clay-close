# -*- coding: utf-8 -*-
"""测量提交路径事务化（ESAS-OS 2.0 / §10.1）契约测试。

验收(对齐 OPTIMIZATION_EXECUTION_PLAN §10.6 测量事务化行):
  - 同一 bundle 改变谱质量 → U1–U6 准入随之变化;
  - ¬C_P(样品错配/无原始文件)⇒ 全 REJECT、不进 BO、blind_retry=0;
  - Rb-ACT 低分歧信号才解锁 BO(无 Rb-ACT → 保守不进 BO)。
"""
from __future__ import annotations

import sys
from pathlib import Path

MAINLINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MAINLINE / "stage1_optimization"))

from scientific_harness.measurement_txn import (  # noqa: E402
    build_measurement_signals_from_bundle, submit_measurement_offline, ReplayInstrument,
)
from scientific_harness.admission import IntendedUse, ADMIT, CONDITIONAL, REJECT  # noqa: E402
from scientific_harness.transaction import ClaimRequest  # noqa: E402


def _bundle(*, n=10, rb_method="reverse_zero_crossing", kk=0.05, qa_ok=True,
            with_files=True, t_break=240.0):
    pts = []
    for i in range(n):
        T = 200.0 + i * 8.0
        flags = [] if qa_ok else ["legacy_failure"]
        pts.append({
            "scan_dir": "300-120K 3K-min", "T_K": T, "status": "OK",
            "rb_ohm": 100.0 + i, "rb_method": rb_method, "kk_residual": kk,
            "kk_passed": kk < 0.2, "sigma_S_cm": 1e-4, "quality_flags": flags,
            "semicircle_visible": True,
        })
    return {
        "sample_id": "S8-LRS-001",
        "geometry": {"area_cm2": 1.0, "thickness_cm": 0.1},
        "eis_points": pts,
        "arrhenius": {"success": True, "n_segments": 2, "t_break_K": t_break,
                      "transition_temps_K": [t_break]},
        "file_hashes": ({"300-120K 3K-min/aggregated_results.json": "deadbeef"} if with_files else {}),
    }


_RBACT_CLEAN = {"rb_method_spread_dex": 0.02, "rb_method_success": True,
                "ecm_fallback": False, "uncertainty_status": "QUANTIFIED"}
_RBACT_ABSTAIN = {"rb_method_spread_dex": 0.5, "rb_method_success": False,
                  "ecm_fallback": False, "uncertainty_status": "UNKNOWN"}


# ---- 信号物化 ----------------------------------------------------------------

def test_signals_mapping_from_bundle():
    sig = build_measurement_signals_from_bundle(_bundle(n=12, kk=0.04))
    assert sig["qa_failed"] is False
    assert sig["kk_mu_median"] == 0.04
    assert sig["geometry_valid"] is True
    assert sig["n_series_points"] == 12
    assert sig["rb_method_success"] is True
    # 方法分歧不在 bundle 里 → 缺省不带（保守）
    assert "rb_method_spread_dex" not in sig


def test_rbact_signal_injection():
    sig = build_measurement_signals_from_bundle(_bundle(), rb_act_signals=_RBACT_CLEAN)
    assert sig["rb_method_spread_dex"] == 0.02
    assert sig["uncertainty_status"] == "QUANTIFIED"


# ---- C_P / 进 BO ------------------------------------------------------------

def test_clean_bundle_with_rbact_confirms_and_enters_bo():
    r = submit_measurement_offline(_bundle(), rb_act_signals=_RBACT_CLEAN)
    assert r.physical_occurred == "confirmed"
    assert r.entered_bo is True
    assert r.use_admissions[IntendedUse.UPDATE_BO]["status"] in (ADMIT, CONDITIONAL)
    assert r.evidence_id is not None
    assert r.blind_retry_count == 0


def test_rbact_abstain_only_tightens_admission():
    """§10.4 R2:Rb-ACT 只收紧、不放松。同一干净 bundle:
       无 Rb-ACT(分歧未评估→WEAK,现行 M1-4 仍判 PRIMARY)→ 进 BO;
       Rb-ACT 弃权(分歧大→FAIL)→ 拦下 BO 与单点用途。"""
    base = submit_measurement_offline(_bundle())                      # 无 Rb-ACT
    tightened = submit_measurement_offline(_bundle(), rb_act_signals=_RBACT_ABSTAIN)
    assert base.entered_bo is True                                    # 现行策略下仍进
    assert tightened.entered_bo is False                              # Rb-ACT 弃权拦下
    assert tightened.use_admissions[IntendedUse.ESTIMATE_POINT_CONDUCTIVITY]["status"] == REJECT


# ---- ¬C_P:样品错配 / 无原始文件 → 全 REJECT --------------------------------

def test_sample_mismatch_quarantines_all():
    r = submit_measurement_offline(_bundle(), expected_sample_id="S8-OTHER-999",
                                   rb_act_signals=_RBACT_CLEAN)
    assert r.physical_occurred == "unknown"
    assert r.entered_bo is False
    assert r.evidence_id is None
    assert all(a["status"] == REJECT for a in r.use_admissions.values())
    assert r.blind_retry_count == 0


def test_no_raw_file_not_confirmed():
    r = submit_measurement_offline(_bundle(with_files=False), rb_act_signals=_RBACT_CLEAN)
    assert r.physical_occurred != "confirmed"
    assert r.entered_bo is False


def test_qa_fail_bundle_rejects_even_with_rbact():
    r = submit_measurement_offline(_bundle(qa_ok=False), rb_act_signals=_RBACT_CLEAN)
    # 所有点都是 legacy_failure → qa_failed → U1 起全链 REJECT，绝不进 BO
    assert r.entered_bo is False
    assert r.use_admissions[IntendedUse.PRESERVE_OBSERVATION]["status"] == REJECT


# ---- C_E 绑定主张 ------------------------------------------------------------

def test_claim_overclaim_rejected_in_transaction():
    # 用单点电导用途(cap C1)请求 C4 主张 → 过度声称 REJECT
    claims = [ClaimRequest(claim_id="CL-1", intended_use=IntendedUse.ESTIMATE_POINT_CONDUCTIVITY,
                           requested_level="C4")]
    r = submit_measurement_offline(_bundle(), rb_act_signals=_RBACT_CLEAN, target_claims=claims)
    ce = r.claim_admissions[0]
    assert ce["ce_status"] == REJECT
    assert any("OVERCLAIM" in c for c in ce["reason_codes"])


def test_replay_instrument_witnesses():
    inst = ReplayInstrument(_bundle())
    assert inst.query_output_file("x")           # raw file present
    assert inst.query_instrument_state() == "DONE"
    assert inst.query_sample_id() == "S8-LRS-001"
    inst2 = ReplayInstrument(_bundle(with_files=False))
    assert not inst2.query_output_file("x")
    assert inst2.query_instrument_state() == "IDLE"
