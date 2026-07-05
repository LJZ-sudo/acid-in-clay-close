# -*- coding: utf-8 -*-
"""P6 验证:真机故障注入升级 —— 在**前端驱动 genuine-live** 全温区谱上,诱发 bundle 类故障
(删文件 / 样品错配 / 坏谱)并核验治理(measurement_txn / Rb-ACT)真拒;在线见证类诚实保留。

与 §Phase4 的 p4_fault_reconciliation 同源(同一 submit_measurement_offline,前端 live 回路真调),
区别:(1) 谱目录换成前端驱动 genuine-live(E:\\chi_data\\p3_fulltemp_fe2);
      (2) 新增 **真·坏谱**:直接污染原始 Z(freq/zr/zi),经 _do_rb_fitting+analyze_spectrum 全链路
          产出坏 bundle,验证"软件 success ≠ 计量有效"也被准入门挡下。

诚实边界:ACK/温控/校准等"在线见证"类只能由仪器 ground-truth 对账(见 p4_fault_reconciliation
路径 A · CommitController),无真机不在此伪造;本脚本只覆盖"已落盘 bundle 可判"类。
"""
from __future__ import annotations

import json
import re
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

REPO = Path(__file__).resolve().parent.parent
MAIN = REPO / "V1.0-qianduan-mainline"
for p in (MAIN, MAIN / "stage0_measurement", MAIN / "stage1_optimization", MAIN / "backend_api"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from modules.io_utils.chi_parser import parse_chi_file  # noqa: E402
from services.hardware_adapter import HardwareAdapter  # noqa: E402
from scientific_harness.measurement_txn import submit_measurement_offline  # noqa: E402
from scientific_harness.admission import IntendedUse  # noqa: E402
from rb_act import analyze_spectrum, ABSTAIN  # noqa: E402

CHI_DIR = Path(r"E:\chi_data\p3_fulltemp_fe2")
THICKNESS_CM = 0.0564
AREA_CM2 = 1.96
SAMPLE_ID = "ATP-R0.186-N1.029-fulltemp-fe2"
OUT = REPO / "_new_data_analysis" / "scientific_harness" / "p6_fault_live_fulltemp_report.json"
_T_RE = re.compile(r"_T(-?\d+(?:[.p]\d+)?)_")


def temp_from_name(name):
    m = _T_RE.search(name)
    return float(m.group(1).replace("p", ".")) if m else None


def _adm(txn):
    return {str(getattr(k, "name", k)): v["status"] for k, v in txn.use_admissions.items()}


def _bundle_from_spectrum(freq, zr, zi, T_C, sample_id=SAMPLE_ID, file_tag="live"):
    """走 live 同源 _do_rb_fitting + analyze_spectrum,把一条(可被污染的)谱物化成 bundle。"""
    a = HardwareAdapter()
    a._thickness_cm, a._area_cm2 = THICKNESS_CM, AREA_CM2
    try:
        rb_result = a._do_rb_fitting(freq, zr, zi, T_C)
    except Exception:  # noqa: BLE001
        rb_result = {"status": "FAILED", "rb_ohm": None, "rb_method": None, "raw": None}
    raw = rb_result.get("raw") if isinstance(rb_result, dict) else None
    kk_res = (raw.get("kk_result") or {}).get("mu_median") if isinstance(raw, dict) else None
    try:
        r = analyze_spectrum(freq, zr, zi, thickness_cm=THICKNESS_CM, area_cm2=AREA_CM2)
        rb_act_signals = dict(getattr(r, "admission_signals", {}) or {})
        decision = str(r.decision)
    except Exception:  # noqa: BLE001
        rb_act_signals, decision = {}, str(ABSTAIN)
    bundle = {
        "sample_id": sample_id,
        "geometry": {"thickness_cm": THICKNESS_CM, "area_cm2": AREA_CM2},
        "file_hashes": {f"{file_tag}.txt": "real_file"},
        "eis_points": [{
            "T_K": float(T_C) + 273.15,
            "status": (rb_result.get("status") if isinstance(rb_result, dict) else None) or "OK",
            "kk_residual": kk_res,
            "rb_ohm": rb_result.get("rb_ohm") if isinstance(rb_result, dict) else None,
            "rb_method": rb_result.get("rb_method") if isinstance(rb_result, dict) else None,
        }],
        "arrhenius": {},
    }
    return bundle, rb_act_signals, decision, kk_res


def main():
    print("== P6 fault injection on FRONTEND-DRIVEN genuine-live spectra ==")
    files = sorted((p for p in CHI_DIR.glob("*.txt") if temp_from_name(p.name) is not None),
                   key=lambda p: temp_from_name(p.name), reverse=True)
    if not files:
        print(f"无谱: {CHI_DIR}")
        return 1
    warm = files[0]
    T_C = temp_from_name(warm.name)
    parsed = parse_chi_file(str(warm))
    if not parsed.get("success"):
        print(f"解析失败: {warm.name}")
        return 1
    freq, zr, zi = parsed["frequencies"], parsed["z_real"], parsed["z_imag"]
    print(f"healthy baseline spectrum: {warm.name} (T={T_C}°C)")

    healthy_bundle, healthy_sig, healthy_dec, healthy_kk = _bundle_from_spectrum(freq, zr, zi, T_C)

    # 真·坏谱:对原始 Z 注入大噪声(非物理/非因果)→ 全链路重算。固定种子可复算。
    rng = np.random.default_rng(0)
    zr_a, zi_a = np.asarray(zr, float), np.asarray(zi, float)
    bad_zr = list(zr_a * (1 + rng.normal(0, 3, len(zr_a))))
    bad_zi = list(zi_a + rng.normal(0, float(np.abs(zi_a).max() or 1.0), len(zi_a)))
    bad_bundle, bad_sig, bad_dec, bad_kk = _bundle_from_spectrum(
        freq, bad_zr, bad_zi, T_C, file_tag="corrupted")

    def healthy():
        return healthy_bundle, dict(healthy_sig), SAMPLE_ID

    def deleted_file():
        b = deepcopy(healthy_bundle); b["file_hashes"] = {}
        return b, dict(healthy_sig), SAMPLE_ID

    def sample_mismatch():
        return healthy_bundle, dict(healthy_sig), "WRONG-SAMPLE-XYZ"

    def corrupted_spectrum():
        return bad_bundle, dict(bad_sig), SAMPLE_ID

    scenarios = [
        ("healthy",            healthy,            True,  []),
        ("deleted_file",       deleted_file,       False, list(IntendedUse.ALL)),
        ("sample_mismatch",    sample_mismatch,    False, list(IntendedUse.ALL)),
        ("corrupted_spectrum", corrupted_spectrum, False, [IntendedUse.ESTIMATE_POINT_CONDUCTIVITY,
                                                           IntendedUse.UPDATE_BO]),
    ]

    rows = []
    for name, build, expect_bo, must_reject in scenarios:
        bundle, sig, expected_sid = build()
        txn = submit_measurement_offline(bundle, expected_sample_id=expected_sid, rb_act_signals=sig)
        adm = _adm(txn)
        reject_ok = all(adm.get(u) in ("REJECT", "CONTESTED") for u in must_reject)
        rows.append({"scenario": name, "entered_bo": txn.entered_bo,
                     "expected_entered_bo": expect_bo, "bo_match": txn.entered_bo == expect_bo,
                     "blind_retry_count": txn.blind_retry_count,
                     "must_reject_satisfied": reject_ok, "admissions": adm})
        print(f"  {name:20s} entered_bo={str(txn.entered_bo):5s}(exp {expect_bo}) "
              f"reject_ok={reject_ok} blind_retry={txn.blind_retry_count}")

    print(f"corrupted-spectrum chain: rb_decision={bad_dec} kk={bad_kk} "
          f"(healthy decision={healthy_dec} kk={healthy_kk})")

    invalid_into_bo = sum(1 for r in rows if r["entered_bo"] and not r["expected_entered_bo"])
    blind_total = sum(r["blind_retry_count"] for r in rows)
    healthy_row = next(r for r in rows if r["scenario"] == "healthy")
    checks = {
        "healthy_entered_bo": bool(healthy_row["entered_bo"]),
        "no_invalid_into_bo": invalid_into_bo == 0,
        "all_bo_match": all(r["bo_match"] for r in rows),
        "all_fault_uses_rejected": all(r["must_reject_satisfied"] for r in rows),
        "no_blind_retry": blind_total == 0,
        "corrupted_not_in_bo": not next(r for r in rows if r["scenario"] == "corrupted_spectrum")["entered_bo"],
    }
    print("-- checks --")
    all_ok = True
    for k, v in checks.items():
        print(f"  [{'PASS' if v else 'FAIL'}] {k}")
        all_ok = all_ok and v

    report = {
        "title": "P6 故障注入(前端驱动 genuine-live 谱):bundle 类故障被治理真拒",
        "spectra_dir": str(CHI_DIR), "sample_id": SAMPLE_ID,
        "baseline": {"file": warm.name, "T_C": T_C, "rb_decision": healthy_dec, "kk": healthy_kk},
        "corrupted_chain": {"rb_decision": bad_dec, "kk": bad_kk},
        "scenarios": rows, "checks": checks,
        "honest_scope": {
            "bundle_level_faults": ["deleted_file", "sample_mismatch", "corrupted_spectrum"],
            "online_witness_faults_retained": ["ack_lost", "timeout_no_effect",
                                               "temp_not_equilibrated", "calibration_expired"],
            "note": "在线见证类只能由仪器 ground-truth 对账(见 p4_fault_reconciliation 路径 A),"
                    "无真机不在此伪造;本脚本覆盖已落盘 bundle 可判类。",
        },
        "acceptance_pass": all_ok,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"== {'ALL PASS' if all_ok else 'FAILED'} ==  → {OUT}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
