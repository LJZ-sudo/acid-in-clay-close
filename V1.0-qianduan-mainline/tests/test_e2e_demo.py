# -*- coding: utf-8 -*-
"""WP5：端到端撤销演示 + 基线消融 + 故障矩阵。

证明三项创新**共同**阻止一条真实错误链(故障→拦截→撤销→BO 重建→下一动作变),
且严格优于无治理基线;并参数化验证 SciTX 对各类故障的防线。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

MAINLINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MAINLINE / "stage1_optimization"))

from scientific_e2e.demo_end_to_end import (  # noqa: E402
    run, baseline_ablation, ablation_over_scenarios,
)
from scientific_harness.transaction import EvidenceTransaction, ClaimRequest  # noqa: E402
from scientific_harness.admission import IntendedUse  # noqa: E402
from scientific_harness.fault_injection import InstrumentSimulator, Fault  # noqa: E402


# ---- WP5-a 端到端 ----

def test_end_to_end_acceptance():
    res = run()
    assert res["acceptance_pass"] is True
    # 关键:撤销使最优从 E1 变 E3
    assert res["governed"]["best_before"] == "E1"
    assert res["governed"]["best_after"] == "E3"


def test_governed_strictly_beats_ungoverned():
    res = run()
    g, b = res["governed"]["metrics"], res["baseline"]["metrics"]
    assert g["invalid_evidence_admission_rate"] == 0.0 and b["invalid_evidence_admission_rate"] == 1.0
    assert g["bo_contamination_rate"] == 0.0 and b["bo_contamination_rate"] == 1.0
    assert g["wrong_claim_survival_rate"] == 0.0 and b["wrong_claim_survival_rate"] == 1.0
    assert g["invalidation_propagation_recall"] == 1.0 and b["invalidation_propagation_recall"] == 0.0


# ---- WP5-b 基线消融 ----

def test_baseline_ablation_monotone_improvement():
    abl = baseline_ablation()   # 现为真实独立运行每臂(非投影)
    # 无效证据准入率:B0 高,B2(SciTX)起就被挡住
    assert abl["B0_none"]["invalid_evidence_admission_rate"] == 1.0
    assert abl["B2_scitx"]["invalid_evidence_admission_rate"] == 0.0
    # 错误最优存活:要到 B4(加 E-Mem)才被杀
    assert abl["B2_scitx"]["wrong_claim_survival_rate"] == 1.0
    assert abl["B4_scitx_emem"]["wrong_claim_survival_rate"] == 0.0
    assert abl["B5_full"]["wrong_claim_survival_rate"] == 0.0
    # 每层保护各加一项可区分能力:B4 无 skill 撤销覆盖,B5 才有
    assert abl["B4_scitx_emem"]["skill_revocation_coverage"] == 0.0
    assert abl["B5_full"]["skill_revocation_coverage"] == 1.0


def test_ablation_invariant_across_scenario_family():
    """治理保证对场景稳健:跨场景每臂每指标取值不变(确定性,非噪声→不伪造 CI)。"""
    res = ablation_over_scenarios()
    assert res["n_scenarios"] >= 3
    for arm, metrics in res["arms"].items():
        for mname, info in metrics.items():
            assert info["invariant"] is True, (arm, mname, info["values"])
    # B0 跨场景恒坏,B5 跨场景恒好
    assert res["arms"]["B0_none"]["wrong_claim_survival_rate"]["values"] == [1.0]
    assert res["arms"]["B5_full"]["wrong_claim_survival_rate"]["values"] == [0.0]


# ---- WP5-c 故障矩阵(SciTX 防线) ----

_CLEAN = dict(
    qa_failed=False, kk_mu_median=0.05, rb_method_spread_dex=0.02,
    uncertainty_status="QUANTIFIED", geometry_valid=True, rb_method_success=True,
    n_series_points=37, method_routing_sensitivity_passed=True, synthetic_fpr_passed=True,
    model_comparison_ok=True, identifiable=True, independent_support=True, alternatives_present=True,
)


@pytest.mark.parametrize("fault,signals_over,expect_occurred,expect_bo,expect_blind_retry", [
    (Fault.NONE, {}, "confirmed", True, 0),                       # 正常 → 进 BO
    (Fault.TIMEOUT_ACK_LOST_FILE_OK, {}, "confirmed", True, 0),   # ACK 丢失但文件在 → 重建,不盲目重试
    (Fault.TIMEOUT_NO_EFFECT, {}, "not_occurred", False, 0),      # 无文件空闲 → 未发生,不进 BO,不重试
    (Fault.NONE, {"qa_failed": True}, "confirmed", False, 0),     # 物理发生但计量不合格 → 不进 BO
])
def test_fault_matrix_defenses(fault, signals_over, expect_occurred, expect_bo, expect_blind_retry):
    sig = dict(_CLEAN); sig.update(signals_over)
    inst = InstrumentSimulator(fault=fault, sample_id="S1")
    res = EvidenceTransaction().process(
        command_id="pt", command="EIS_SWEEP", instrument=inst, measurement_signals=sig,
        intended_uses=[IntendedUse.UPDATE_BO],
        target_claims=[ClaimRequest("c", IntendedUse.ESTIMATE_BREAKPOINT, "C3")],
        expected_sample_id="S1")
    assert res.physical_occurred == expect_occurred
    assert res.entered_bo is expect_bo
    assert res.blind_retry_count == expect_blind_retry
