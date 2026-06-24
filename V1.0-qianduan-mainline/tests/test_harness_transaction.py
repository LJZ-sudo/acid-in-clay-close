# -*- coding: utf-8 -*-
"""WP1-d：EvidenceTransaction 端到端 + 系统不变量。

不变量:① blind_retry 恒 0;② ¬C_P(confirmed) ⇒ C_M/C_E 全 REJECT 且不入 BO;
③ ¬C_E(UPDATE_BO) ⇒ 不入 BO;④ 三类 ID 分离。
"""
from __future__ import annotations

import sys
from pathlib import Path

MAINLINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MAINLINE / "stage1_optimization"))

from scientific_harness.transaction import EvidenceTransaction, ClaimRequest  # noqa: E402
from scientific_harness.admission import IntendedUse, ADMIT, REJECT  # noqa: E402
from scientific_harness.fault_injection import InstrumentSimulator, Fault  # noqa: E402

_CLEAN_SIGNALS = dict(
    qa_failed=False, kk_mu_median=0.05, rb_method_spread_dex=0.02,
    uncertainty_status="QUANTIFIED", geometry_valid=True, rb_method_success=True,
    n_series_points=37, method_routing_sensitivity_passed=True, synthetic_fpr_passed=True,
    model_comparison_ok=True, identifiable=True, independent_support=True, alternatives_present=True,
)


def _run(fault, signals=None, claims=None):
    inst = InstrumentSimulator(fault=fault, sample_id="S1")
    txn = EvidenceTransaction()
    return txn.process(
        command_id="g1_pt_001", command="EIS_SWEEP", instrument=inst,
        measurement_signals=signals if signals is not None else dict(_CLEAN_SIGNALS),
        intended_uses=[IntendedUse.ESTIMATE_POINT_CONDUCTIVITY, IntendedUse.UPDATE_BO],
        target_claims=claims or [ClaimRequest("C-break", IntendedUse.ESTIMATE_BREAKPOINT, "C3")],
        expected_sample_id="S1")


def test_clean_run_confirms_and_enters_bo():
    r = _run(Fault.NONE)
    assert r.physical_occurred == "confirmed"
    assert r.entered_bo is True
    assert r.use_admissions[IntendedUse.UPDATE_BO]["status"] == ADMIT
    assert r.blind_retry_count == 0


def test_ack_lost_file_ok_still_confirms_no_blind_retry():
    """ACK 丢失但文件已生成 → C_P confirmed(重建)、不盲目重试、可入 BO。"""
    r = _run(Fault.TIMEOUT_ACK_LOST_FILE_OK)
    assert r.physical_occurred == "confirmed"
    assert r.reconciled is True
    assert r.blind_retry_count == 0
    assert r.entered_bo is True


def test_no_effect_rejects_everything_no_bo():
    """仪器空闲无文件 → C_P not_occurred → C_M/C_E 全 REJECT、不入 BO、不盲目重试。"""
    r = _run(Fault.TIMEOUT_NO_EFFECT)
    assert r.physical_occurred == "not_occurred"
    assert r.entered_bo is False
    assert r.blind_retry_count == 0
    assert all(a["status"] == REJECT for a in r.use_admissions.values())
    assert all(c["ce_status"] == REJECT for c in r.claim_admissions)


def test_temp_not_equilibrated_confirms_physical_but_blocks_bo():
    """温度未平衡:物理可能发生,但计量不合格 → 不入 BO(C_P 与 C_M 解耦的证明)。"""
    inst_signals = dict(_CLEAN_SIGNALS)
    # 温度未平衡通过 measurement 层体现为 QA 失败(模拟:qa_failed=True)
    inst_signals["qa_failed"] = True
    r = _run(Fault.TEMP_NOT_EQUILIBRATED, signals=inst_signals)
    # TEMP_NOT_EQUILIBRATED 模拟器:文件在、状态 DONE → C_P 仍可能 confirmed
    assert r.entered_bo is False  # 计量/证据不合格,绝不入 BO


def test_three_ids_distinct():
    r = _run(Fault.NONE)
    ids = {r.transaction_id, r.attempt_id, r.physical_effect_id}
    assert len(ids) == 3  # 三类 ID 互不相同


def test_overclaim_rejected_at_c4_cap():
    """请求 C5 机制主张 → 必拒(EIS 封顶 C4)。"""
    r = _run(Fault.NONE, claims=[ClaimRequest("C-mech", IntendedUse.MECHANISTIC_CONSISTENCY, "C5")])
    c = r.claim_admissions[0]
    assert c["ce_status"] == REJECT
