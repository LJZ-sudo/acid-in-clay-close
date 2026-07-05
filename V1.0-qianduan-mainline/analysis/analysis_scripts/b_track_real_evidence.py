# -*- coding: utf-8 -*-
"""B 轨真机收尾 · 软件侧证据（§11.2-A,SW-1/2/4,零硬件风险）。

对应 OPTIMIZATION_EXECUTION_PLAN_20260622.md §11:
  SW-1 故障对照矩阵 → shadow_discrepancy_report.json
       复用 scientific_harness/demo_a.py 的 6 场景(纯软件 InstrumentSimulator),
       量化"三重提交 Harness 挡住了哪些错误"vs ground-truth:
         - 真故障(temp/calib/kk/timeout_no_effect)必须被挡在 BO 外;
         - ack 丢失但文件在 → 物理状态被重建(RECONSTRUCTED)且照常进 BO;
         - 全程 blind_retry=0(超时先核对、不盲目重试)。
  SW-2 measurement_txn canary → measurement_txn_canary_evidence.json
       对 3 份真实 G1 bundle(R=0.186/N=1.029)跑 submit_measurement_offline:
         clean+Rb-ACT 干净信号→进 BO/blind_retry=0;坏谱→全 REJECT;样品错配→全 REJECT。
  SW-4 Rb-ACT R1 巩固 → 读 output/e1_floor/rb_act_delta_report.json 汇总(0 未解释翻转)。

诚实边界:本脚本是**软件侧**收尾(零硬件)。真机 live shadow / live 双跑是 HW-2/HW-3
(另起 run_online --harness_mode shadow + live 谱)。legacy 零改动;EIS-only 硬封顶 C4。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

REPO = next(_p for _p in Path(__file__).resolve().parents if _p.name == "V1.0-qianduan-mainline").parent
MAIN = REPO / "V1.0-qianduan-mainline"
sys.path.insert(0, str(MAIN / "stage0_measurement"))
sys.path.insert(0, str(MAIN / "stage1_optimization"))

from scientific_harness.demo_a import run as run_fault_matrix  # noqa: E402
from scientific_harness.measurement_txn import submit_measurement_offline  # noqa: E402
from scientific_harness.admission import REJECT  # noqa: E402

OUT = MAIN / "output" / "b_track_real"
BUNDLE_ROOT = MAIN / "output" / "stage0_results"
E1 = MAIN / "output" / "e1_floor"

BATCHES = [
    {"key": "A", "sample_id": "ATP-R0.186-N1.029-batchA-0624"},
    {"key": "B", "sample_id": "ATP-R0.186-N1.029-batchB-0625"},
    {"key": "C", "sample_id": "ATP-R0.186-N1.029-batchC-0626"},
]

# 真故障语义(应被挡在 BO 外);ack_lost 应被重建后进 BO;healthy 应进 BO
GENUINE_FAULTS = {"timeout_no_effect", "temp_not_equilibrated",
                  "calibration_expired", "kk_fail"}


def sw1_fault_discrepancy() -> Dict[str, Any]:
    """SW-1:故障对照矩阵 → 三重提交 Harness 挡住哪些错误。"""
    fm = run_fault_matrix()
    rows = []
    n_genuine = n_caught = n_missed = 0
    blind_retry_total = 0
    reconstruct_ok = None
    for s in fm["scenarios"]:
        name = s["scenario"]
        entered = s["entered_bo"]
        blind_retry_total += s.get("blind_retry_count", 0)
        is_fault = name in GENUINE_FAULTS
        verdict = "ADMITTED_TO_BO" if entered else "BLOCKED_FROM_BO"
        # 对照判定
        if is_fault:
            n_genuine += 1
            if entered:
                n_missed += 1
                catch = "MISSED (危险:故障进了 BO)"
            else:
                n_caught += 1
                catch = "CAUGHT (正确挡住)"
        elif name == "ack_lost_file_ok":
            reconstruct_ok = (s["physical_commit"] == "RECONSTRUCTED" and entered)
            catch = "RECONSTRUCTED+ADMITTED" if reconstruct_ok else "RECONSTRUCT_FAIL"
        else:  # healthy
            catch = "HEALTHY_ADMITTED" if entered else "HEALTHY_BLOCKED(异常)"
        rows.append({
            "scenario": name, "fault": s["fault"],
            "physical_commit": s["physical_commit"],
            "metrological_commit": s["metrological_commit"],
            "epistemic_commit": s["epistemic_commit"],
            "entered_bo": entered, "expected_entered_bo": s["expected_entered_bo"],
            "match_expectation": s["match"],
            "blind_retry_count": s.get("blind_retry_count", 0),
            "verdict": verdict, "fault_handling": catch,
        })
    acceptance = {
        "n_genuine_faults": n_genuine,
        "n_faults_caught": n_caught,
        "n_faults_missed_into_bo": n_missed,        # 必须 0
        "blind_retry_total": blind_retry_total,     # 必须 0(超时先核对)
        "ack_lost_reconstructed_and_admitted": bool(reconstruct_ok),
        "all_scenarios_match_expectation": all(r["match_expectation"] for r in rows),
        "event_chain_valid": fm["acceptance"]["event_chain_valid"],
    }
    acceptance_pass = (n_missed == 0 and blind_retry_total == 0
                       and bool(reconstruct_ok)
                       and acceptance["all_scenarios_match_expectation"]
                       and acceptance["event_chain_valid"])
    return {
        "task": "SW-1 fault-injection discrepancy (tri-commit harness vs ground-truth)",
        "note": "纯软件 InstrumentSimulator(5 类故障)+ reconciler;"
                "真故障全部挡在 BO 外、ack 丢失重建后进 BO、blind_retry=0。",
        "matrix": rows,
        "acceptance": acceptance,
        "acceptance_pass": acceptance_pass,
    }


def _statuses(use_admissions) -> Dict[str, str]:
    return {str(getattr(k, "name", k)): v["status"] for k, v in use_admissions.items()}


def sw2_txn_canary() -> Dict[str, Any]:
    """SW-2:真实 G1 bundle 测量事务化 canary(clean / 坏谱 / 样品错配)。"""
    rbact_clean = {"rb_method_spread_dex": 0.02, "rb_method_success": True,
                   "ecm_fallback": False, "uncertainty_status": "QUANTIFIED"}
    rows = []
    for b in BATCHES:
        bp = BUNDLE_ROOT / b["sample_id"] / "stage0_result_bundle.json"
        bundle = json.loads(bp.read_text(encoding="utf-8"))

        clean = submit_measurement_offline(bundle, rb_act_signals=rbact_clean)

        bad = json.loads(json.dumps(bundle))
        for p in bad.get("eis_points", []):
            p.setdefault("quality_flags", []).append("legacy_failure")
        degraded = submit_measurement_offline(bad, rb_act_signals=rbact_clean)

        mism = submit_measurement_offline(bundle, expected_sample_id="WRONG-SAMPLE-ID",
                                          rb_act_signals=rbact_clean)
        rows.append({
            "batch": b["key"], "sample_id": b["sample_id"],
            "clean": {"entered_bo": clean.entered_bo,
                      "blind_retry_count": clean.blind_retry_count,
                      "admissions": _statuses(clean.use_admissions)},
            "degraded_qa_fail": {"entered_bo": degraded.entered_bo,
                                 "all_reject": all(a["status"] == REJECT
                                                   for a in degraded.use_admissions.values())},
            "sample_mismatch": {"entered_bo": mism.entered_bo,
                                "all_reject": all(a["status"] == REJECT
                                                  for a in mism.use_admissions.values()),
                                "blind_retry_count": mism.blind_retry_count},
        })
    acceptance_pass = all(
        (not r["degraded_qa_fail"]["entered_bo"]) and r["degraded_qa_fail"]["all_reject"]
        and (not r["sample_mismatch"]["entered_bo"]) and r["sample_mismatch"]["all_reject"]
        and r["clean"]["blind_retry_count"] == 0
        for r in rows
    )
    return {
        "task": "SW-2 measurement_txn canary on real G1 bundles",
        "note": "clean(+Rb-ACT 干净信号)→进 BO/blind_retry=0;坏谱→全 REJECT;样品错配→全 REJECT。",
        "rows": rows,
        "acceptance_pass": acceptance_pass,
    }


def sw4_rb_act_consolidate() -> Dict[str, Any]:
    """SW-4:读既有 Rb-ACT R1 delta 报告,巩固 0 未解释翻转。"""
    p = E1 / "rb_act_delta_report.json"
    if not p.exists():
        return {"task": "SW-4 Rb-ACT R1 consolidation", "available": False,
                "note": "rb_act_delta_report.json 不存在(需先跑 e1_btrack_evidence.py)。"}
    rb = json.loads(p.read_text(encoding="utf-8"))
    d = rb.get("delta_log10_rb", {})
    return {
        "task": "SW-4 Rb-ACT R1 consolidation (offline real LRS spectra)",
        "available": True,
        "gate": rb.get("gate"),
        "n_paired_points": rb.get("n_paired_points"),
        "delta_log10_rb_median": d.get("median"),
        "delta_log10_rb_p90": d.get("p90"),
        "n_unexplained_flips": rb.get("n_unexplained_flips"),
        "flip_threshold_dex": rb.get("flip_threshold_dex"),
        "acceptance_pass": (rb.get("n_unexplained_flips") == 0),
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    sw1 = sw1_fault_discrepancy()
    sw2 = sw2_txn_canary()
    sw4 = sw4_rb_act_consolidate()

    (OUT / "shadow_discrepancy_report.json").write_text(
        json.dumps(sw1, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "measurement_txn_canary_evidence.json").write_text(
        json.dumps(sw2, ensure_ascii=False, indent=2), encoding="utf-8")

    summary = {
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "scope": "§11.2-A software-side B-track close-out (SW-1/2/4), zero hardware",
        "recipe": {"R": 0.186, "N": 1.029},
        "sw1_fault_discrepancy": sw1["acceptance"] | {"pass": sw1["acceptance_pass"]},
        "sw2_txn_canary_pass": sw2["acceptance_pass"],
        "sw4_rb_act": sw4,
        "honest_boundary": "软件侧;真机 live shadow/双跑见 HW-2/HW-3;legacy 零改动;EIS-only C4。",
    }
    (OUT / "b_track_real_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print("===== §11.2-A 软件侧 B 轨收尾 =====")
    print("[SW-1] 故障对照矩阵:")
    for r in sw1["matrix"]:
        print(f"  {r['scenario']:22s} {r['verdict']:14s} {r['fault_handling']}")
    a = sw1["acceptance"]
    print(f"  → 真故障 {a['n_faults_caught']}/{a['n_genuine_faults']} 挡住, "
          f"漏检={a['n_faults_missed_into_bo']}, blind_retry={a['blind_retry_total']}, "
          f"ack_lost 重建={a['ack_lost_reconstructed_and_admitted']}, pass={sw1['acceptance_pass']}")
    print("[SW-2] measurement_txn canary:")
    for r in sw2["rows"]:
        print(f"  batch {r['batch']}: clean entered_bo={r['clean']['entered_bo']} "
              f"blind_retry={r['clean']['blind_retry_count']} | "
              f"qa_fail all_reject={r['degraded_qa_fail']['all_reject']} | "
              f"mismatch all_reject={r['sample_mismatch']['all_reject']}")
    print(f"  → pass={sw2['acceptance_pass']}")
    print(f"[SW-4] Rb-ACT R1: paired={sw4.get('n_paired_points')} "
          f"flips={sw4.get('n_unexplained_flips')} pass={sw4.get('acceptance_pass')}")
    print(f"写出: {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
