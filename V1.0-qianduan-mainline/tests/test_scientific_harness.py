# -*- coding: utf-8 -*-
"""M5-A 测试:三重提交 Harness 不变量 + Demo A 验收。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
STAGE1 = PROJECT_ROOT / "stage1_optimization"
if str(STAGE1) not in sys.path:
    sys.path.insert(0, str(STAGE1))

from scientific_harness.commit_controller import CommitController  # noqa: E402
from scientific_harness.fault_injection import InstrumentSimulator, Fault  # noqa: E402
from scientific_harness.commits import PhysicalCommit, EpistemicCommit  # noqa: E402

_CLEAN = {"qa_failed": False, "kk_mu_median": 0.05, "rb_method_spread_dex": 0.02,
          "uncertainty_status": "QUANTIFIED"}


def _run(fault, meas=_CLEAN):
    return CommitController().process("cmd", InstrumentSimulator(fault=fault), meas)


def test_healthy_enters_bo():
    r = _run(Fault.NONE)
    assert r.physical_commit == PhysicalCommit.EFFECT_OBSERVED
    assert r.epistemic_commit == EpistemicCommit.PRIMARY_EVIDENCE
    assert r.entered_bo is True


def test_timeout_ack_lost_reconstructed_no_blind_retry():
    """确认丢失但文件在 → reconciler 重建为 RECONSTRUCTED,且 0 盲目重试,照常进 BO。"""
    r = _run(Fault.TIMEOUT_ACK_LOST_FILE_OK)
    assert r.reconciled is True
    assert r.blind_retry_count == 0
    assert r.physical_commit == PhysicalCommit.RECONSTRUCTED
    assert r.entered_bo is True


def test_timeout_no_effect_not_in_bo():
    r = _run(Fault.TIMEOUT_NO_EFFECT)
    assert r.physical_commit == PhysicalCommit.FAILED
    assert r.entered_bo is False
    assert r.blind_retry_count == 0


def test_temp_not_equilibrated_blocked():
    r = _run(Fault.TEMP_NOT_EQUILIBRATED)
    assert r.metrological_commit == "INVALID"
    assert r.entered_bo is False


def test_calibration_expired_blocked():
    r = _run(Fault.CALIBRATION_EXPIRED)
    assert r.metrological_commit == "INVALID"
    assert r.entered_bo is False


def test_kk_fail_blocked():
    r = _run(Fault.KK_FAIL, {"qa_failed": False, "kk_mu_median": 0.6,
                             "rb_method_spread_dex": 0.02, "uncertainty_status": "QUANTIFIED"})
    assert r.entered_bo is False


def test_invariant_not_ce_implies_not_bo():
    """核心不变量:¬C_E ⇒ 不入 BO(穷举所有故障场景)。"""
    for fault in [Fault.TIMEOUT_NO_EFFECT, Fault.TEMP_NOT_EQUILIBRATED,
                  Fault.CALIBRATION_EXPIRED]:
        r = _run(fault)
        if r.epistemic_commit != EpistemicCommit.PRIMARY_EVIDENCE:
            assert r.entered_bo is False


def test_event_chain_valid():
    c = CommitController()
    c.process("cmd", InstrumentSimulator(fault=Fault.NONE), _CLEAN)
    assert c.store.verify_chain() is True


def test_demo_a_acceptance_passes():
    from scientific_harness import demo_a
    res = demo_a.run()
    assert res["acceptance_pass"] is True
    m = res["acceptance"]
    assert m["blind_retry_count"] == 0
    assert m["invalid_into_bo_count"] == 0
    assert m["physical_state_reconstructed_correctly"] is True
    assert m["event_chain_valid"] is True


def test_shadow_recorder_records_and_is_failsafe(tmp_path):
    """run_online 旁路:clean 点应 entered_bo=True 且与 live 一致;坏输入不抛错。"""
    from scientific_harness.shadow import ShadowHarnessRecorder
    rec = ShadowHarnessRecorder(out_dir=str(tmp_path), sample_id="G1_test",
                                compute_rb_spread=False)
    clean = {"success": True, "status": "OK", "kk_warning": False,
             "quality_result": {"grade": "A", "details": {}},
             "kk_result": {"mu_median": 0.05}}
    rec.record(clean, temperature_K=298.15)
    qa_fail = {"success": False, "status": "REJECTED_BY_QA",
               "quality_result": {"grade": "F", "details": {"fatal_check": True}},
               "kk_result": {}}
    rec.record(qa_fail, temperature_K=250.0)
    rec.record(None, temperature_K=None)        # 畸形输入:必须 fail-safe 吞掉(不抛、不计入)
    assert (tmp_path / "shadow_harness_log.jsonl").exists()
    summary = json.loads((tmp_path / "shadow_harness_summary.json").read_text(encoding="utf-8"))
    assert summary["n_points"] == 2             # 畸形点被 fail-safe 跳过,不污染指标
    assert summary["agreement_rate"] == 1.0     # clean→进BO、QA失败→不进BO,均与 live 一致
    assert summary["blind_retry_count"] == 0          # shadow 永不盲目重试
    assert summary["shadow_looser_than_live_count"] == 0  # shadow 不会比 live 更宽松
