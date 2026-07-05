# -*- coding: utf-8 -*-
"""E1 B 轨离线证据（用本轮真实凹凸棒土 LRS 谱跑 v2 插件，只记录不夺权）。

两部分（对齐 HANDOFF §4 第2步 / §5 Rb-ACT 五级门 R0→R1）：
  1. measurement_txn 准入语义：对三份真实 stage0_result_bundle.json 跑
     submit_measurement_offline，验证
       - 干净 bundle + Rb-ACT 干净信号 → 进 BO、blind_retry=0；
       - 改坏谱质量（全点 qa_failed）→ 全链 REJECT、不进 BO；
       - 样品错配（expected_sample_id 不符）→ 全 REJECT、blind_retry=0。
  2. Rb-ACT R1 双跑：在每批真实谱上跑 analyze_spectrum，对照 legacy_rb_ohm 产 delta，
     **仍采用 legacy 值**（R1 不改数值链）；统计 report/abstain 与 |Δlog10 Rb|，
     标记任何"未解释翻转"（Rb-ACT REPORT 但与 legacy 偏离 > 0.3 dex）。

诚实边界：R0/R1 纯观察；legacy（rb_fitting.py）零改动。EIS-only 硬封顶 C4。
"""
from __future__ import annotations

import glob
import json
import math
import os
import statistics
import sys
from pathlib import Path
from typing import Dict, List, Optional

REPO = next(_p for _p in Path(__file__).resolve().parents if _p.name == "V1.0-qianduan-mainline").parent
MAIN = REPO / "V1.0-qianduan-mainline"
sys.path.insert(0, str(MAIN / "stage0_measurement"))
sys.path.insert(0, str(MAIN / "stage1_optimization"))

from modules.io_utils.chi_parser import parse_chi_file, extract_temperature_from_filename  # noqa: E402
from rb_act import analyze_spectrum, ABSTAIN, REPORT, REPORT_CONDITIONAL  # noqa: E402
from scientific_harness.measurement_txn import submit_measurement_offline  # noqa: E402
from scientific_harness.admission import IntendedUse, REJECT  # noqa: E402

OUT = MAIN / "output" / "e1_floor"
BUNDLE_ROOT = MAIN / "output" / "stage0_results"
FLIP_DEX = 0.30  # Rb-ACT REPORT 但与 legacy 偏离 > 0.30 dex → 未解释翻转（需复核）

BATCHES = [
    {"key": "A", "sample_id": "ATP-R0.186-N1.029-batchA-0624",
     "src": r"E:\固态电解质\2026.6.24-2", "L_cm": 0.0712, "S_cm2": 1.96},
    {"key": "B", "sample_id": "ATP-R0.186-N1.029-batchB-0625",
     "src": r"E:\固态电解质\2026.6.25-3", "L_cm": 0.0654, "S_cm2": 1.96},
    {"key": "C", "sample_id": "ATP-R0.186-N1.029-batchC-0626",
     "src": r"E:\固态电解质\2026.6.26-1", "L_cm": 0.0564, "S_cm2": 1.96},
]


def _statuses(use_admissions) -> Dict[str, str]:
    return {str(getattr(k, "name", k)): v["status"] for k, v in use_admissions.items()}


def measurement_txn_evidence() -> dict:
    """对真实 bundle 验证 U1–U6 准入语义随谱质量 / 样品配对而变。"""
    rows = []
    rbact_clean = {"rb_method_spread_dex": 0.02, "rb_method_success": True,
                   "ecm_fallback": False, "uncertainty_status": "QUANTIFIED"}
    for b in BATCHES:
        bundle = json.loads((BUNDLE_ROOT / b["sample_id"] / "stage0_result_bundle.json").read_text(encoding="utf-8"))

        clean = submit_measurement_offline(bundle, rb_act_signals=rbact_clean)

        bad = json.loads(json.dumps(bundle))
        for p in bad.get("eis_points", []):
            p.setdefault("quality_flags", []).append("legacy_failure")
        degraded = submit_measurement_offline(bad, rb_act_signals=rbact_clean)

        mism = submit_measurement_offline(bundle, expected_sample_id="WRONG-SAMPLE-ID",
                                          rb_act_signals=rbact_clean)
        rows.append({
            "batch": b["key"], "sample_id": b["sample_id"],
            "clean": {"physical_occurred": clean.physical_occurred, "entered_bo": clean.entered_bo,
                      "blind_retry_count": clean.blind_retry_count,
                      "evidence_id_present": clean.evidence_id is not None,
                      "admissions": _statuses(clean.use_admissions)},
            "degraded_qa_fail": {"entered_bo": degraded.entered_bo,
                                 "all_reject": all(a["status"] == REJECT for a in degraded.use_admissions.values()),
                                 "admissions": _statuses(degraded.use_admissions)},
            "sample_mismatch": {"physical_occurred": mism.physical_occurred, "entered_bo": mism.entered_bo,
                                "all_reject": all(a["status"] == REJECT for a in mism.use_admissions.values()),
                                "blind_retry_count": mism.blind_retry_count},
        })
    return {"note": "U1-U6 admission semantics on real bundles; clean enters BO, qa-fail & sample-mismatch fully REJECT.",
            "rows": rows}


def rb_act_r1_double_run() -> dict:
    """每批真实谱：Rb-ACT analyze_spectrum vs legacy_rb_ohm，产 delta（采用 legacy 值）。"""
    per_batch = []
    all_deltas: List[float] = []
    flips: List[dict] = []
    for b in BATCHES:
        files = sorted(glob.glob(os.path.join(b["src"], "R0.186*.txt")))
        items = []
        n_report = n_cond = n_abstain = 0
        for fp in files:
            parsed = parse_chi_file(fp)
            if not parsed.get("success"):
                continue
            T_C = extract_temperature_from_filename(os.path.basename(fp)).get("temperature_C")
            r = analyze_spectrum(parsed["frequencies"], parsed["z_real"], parsed["z_imag"],
                                 thickness_cm=b["L_cm"], area_cm2=b["S_cm2"])
            dec = r.decision
            if dec == ABSTAIN:
                n_abstain += 1
            elif dec == REPORT:
                n_report += 1
            elif dec == REPORT_CONDITIONAL:
                n_cond += 1
            legacy_rb = getattr(r, "legacy_rb_ohm", None)
            rbact_rb = getattr(r.posterior, "rb_ohm", None) if getattr(r, "posterior", None) else None
            delta = None
            if dec != ABSTAIN and legacy_rb and rbact_rb and legacy_rb > 0 and rbact_rb > 0:
                delta = abs(math.log10(rbact_rb) - math.log10(legacy_rb))
                all_deltas.append(delta)
                if delta > FLIP_DEX:
                    flips.append({"batch": b["key"], "T_C": T_C, "decision": str(dec),
                                  "legacy_rb_ohm": legacy_rb, "rbact_rb_ohm": rbact_rb,
                                  "abs_dlog10_rb": delta})
            items.append({"T_C": T_C, "decision": str(dec), "legacy_rb_ohm": legacy_rb,
                          "rbact_rb_ohm": rbact_rb, "abs_dlog10_rb": delta})
        per_batch.append({"batch": b["key"], "n_spectra": len(items),
                          "n_report": n_report, "n_conditional": n_cond, "n_abstain": n_abstain,
                          "items": items})

    ds = sorted(all_deltas)
    def pct(p):
        if not ds:
            return None
        if len(ds) == 1:
            return ds[0]
        k = p * (len(ds) - 1); lo = int(k); hi = min(lo + 1, len(ds) - 1)
        return ds[lo] + (ds[hi] - ds[lo]) * (k - lo)
    return {
        "gate": "R1 (online/offline double-run; legacy values STILL adopted; numbers unchanged)",
        "policy": "Rb-ACT observe-only; legacy rb_fitting untouched.",
        "n_paired_points": len(ds),
        "delta_log10_rb": {"median": (statistics.median(ds) if ds else None),
                            "p90": pct(0.90), "max": (ds[-1] if ds else None)},
        "flip_threshold_dex": FLIP_DEX,
        "n_unexplained_flips": len(flips),
        "unexplained_flips": flips,
        "per_batch": per_batch,
    }


def main() -> int:
    txn = measurement_txn_evidence()
    rb = rb_act_r1_double_run()
    (OUT / "b_track_measurement_txn_evidence.json").write_text(
        json.dumps(txn, indent=2, ensure_ascii=False), encoding="utf-8")
    (OUT / "rb_act_delta_report.json").write_text(
        json.dumps(rb, indent=2, ensure_ascii=False), encoding="utf-8")

    print("===== B 轨离线证据 =====")
    print("[measurement_txn] 真实 bundle 准入：")
    for row in txn["rows"]:
        print(f"  batch {row['batch']}: clean entered_bo={row['clean']['entered_bo']} "
              f"blind_retry={row['clean']['blind_retry_count']} | "
              f"qa_fail all_reject={row['degraded_qa_fail']['all_reject']} | "
              f"mismatch all_reject={row['sample_mismatch']['all_reject']} "
              f"blind_retry={row['sample_mismatch']['blind_retry_count']}")
    print("[Rb-ACT R1 双跑] vs legacy：")
    for pb in rb["per_batch"]:
        print(f"  batch {pb['batch']}: n={pb['n_spectra']} report={pb['n_report']} "
              f"cond={pb['n_conditional']} abstain={pb['n_abstain']}")
    d = rb["delta_log10_rb"]
    md = f"{d['median']:.4f}" if d["median"] is not None else "n/a"
    p9 = f"{d['p90']:.4f}" if d["p90"] is not None else "n/a"
    print(f"  paired={rb['n_paired_points']}  |Δlog10 Rb| median={md} p90={p9} dex  "
          f"未解释翻转(>{FLIP_DEX}dex)={rb['n_unexplained_flips']}")
    print(f"  写出: {OUT/'b_track_measurement_txn_evidence.json'}")
    print(f"  写出: {OUT/'rb_act_delta_report.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
