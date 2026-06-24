# -*- coding: utf-8 -*-
"""🅰️ Demo A（M5-A Tier S 解锁演示）— 故障注入验证三重提交不变量。

6 个场景(纯软件、零硬件):
  healthy / ack_lost_file_ok(超时但文件在) / timeout_no_effect(真失败) /
  temp_not_equilibrated / calibration_expired / kk_fail
验证:① 超时后不盲目重试(blind_retry=0);② 无效测量不进 BO(¬C_E ⇒ 不入);
③ 确认丢失时物理状态被正确重建(RECONSTRUCTED 且照常进 BO)。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

_THIS = Path(__file__).resolve()
STAGE1 = _THIS.parents[1]
if str(STAGE1) not in sys.path:
    sys.path.insert(0, str(STAGE1))

from scientific_harness.commit_controller import CommitController  # noqa: E402
from scientific_harness.fault_injection import InstrumentSimulator, Fault  # noqa: E402

REPO_ROOT = _THIS.parents[3]
OUT_DIR = REPO_ROOT / "_new_data_analysis" / "scientific_harness"

# 干净测量(analysis 层)
_CLEAN = {"qa_failed": False, "kk_mu_median": 0.05, "rb_method_spread_dex": 0.02,
          "uncertainty_status": "QUANTIFIED"}
_KK_FAIL = {"qa_failed": False, "kk_mu_median": 0.6, "rb_method_spread_dex": 0.02,
            "uncertainty_status": "QUANTIFIED"}

SCENARIOS = [
    ("healthy", Fault.NONE, _CLEAN, True),
    ("ack_lost_file_ok", Fault.TIMEOUT_ACK_LOST_FILE_OK, _CLEAN, True),    # 应重建后照常进 BO
    ("timeout_no_effect", Fault.TIMEOUT_NO_EFFECT, _CLEAN, False),
    ("temp_not_equilibrated", Fault.TEMP_NOT_EQUILIBRATED, _CLEAN, False),
    ("calibration_expired", Fault.CALIBRATION_EXPIRED, _CLEAN, False),
    ("kk_fail", Fault.KK_FAIL, _KK_FAIL, False),
]


def run() -> Dict[str, Any]:
    controller = CommitController()
    rows: List[Dict[str, Any]] = []
    for name, fault, meas, expect_bo in SCENARIOS:
        inst = InstrumentSimulator(fault=fault, sample_id="S1")
        res = controller.process(f"cmd_{name}", inst, meas)
        rows.append({
            "scenario": name, "fault": fault,
            "physical_commit": res.physical_commit,
            "metrological_commit": res.metrological_commit,
            "epistemic_commit": res.epistemic_commit,
            "entered_bo": res.entered_bo,
            "expected_entered_bo": expect_bo,
            "match": res.entered_bo == expect_bo,
            "blind_retry_count": res.blind_retry_count,
            "reconciled": res.reconciled,
        })

    blind_retry_total = sum(r["blind_retry_count"] for r in rows)
    invalid_into_bo = sum(1 for r in rows if r["entered_bo"] and not r["expected_entered_bo"])
    ack_lost = next(r for r in rows if r["scenario"] == "ack_lost_file_ok")
    reconstruct_ok = (ack_lost["physical_commit"] == "RECONSTRUCTED" and ack_lost["entered_bo"])
    all_match = all(r["match"] for r in rows)
    chain_ok = controller.store.verify_chain()

    metrics = {
        "blind_retry_count": blind_retry_total,
        "invalid_into_bo_count": invalid_into_bo,
        "physical_state_reconstructed_correctly": bool(reconstruct_ok),
        "all_scenarios_match_expectation": bool(all_match),
        "event_chain_valid": bool(chain_ok),
    }
    acceptance_pass = (blind_retry_total == 0 and invalid_into_bo == 0
                       and reconstruct_ok and all_match and chain_ok)
    result = {
        "demo": "A - tri-commit physical belief-state harness",
        "scenarios": rows,
        "acceptance": metrics,
        "acceptance_pass": acceptance_pass,
        "n_events": len(controller.store.events()),
    }
    return result


def write_report() -> Dict[str, Any]:
    res = run()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "demo_a_fault_injection_report.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    return res


if __name__ == "__main__":
    res = write_report()
    print("Demo A acceptance:", json.dumps(res["acceptance"], ensure_ascii=False))
    print("acceptance_pass:", res["acceptance_pass"])
    for r in res["scenarios"]:
        print(f"  {r['scenario']:22s} C_P={r['physical_commit']:14s} "
              f"C_M={r['metrological_commit']:11s} C_E={r['epistemic_commit']:16s} "
              f"BO={r['entered_bo']}(exp {r['expected_entered_bo']}) match={r['match']}")
