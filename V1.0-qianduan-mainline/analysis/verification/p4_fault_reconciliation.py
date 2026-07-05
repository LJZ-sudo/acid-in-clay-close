# -*- coding: utf-8 -*-
"""Phase 4 / Tier-S 硬门 —— 故障注入对账证据（双治理路径，真机谱）。

把"故障注入"打通到 **两条真正在用的治理路径**,产出可复算的 Tier-S 对账证据:

  路径 A · CommitController(三重提交)—— Demo A 的 6 场景。
    覆盖 **在线见证类** 故障:ACK 丢失(物理已发生→应重建后照常进 BO)、
    真超时无效果、温度未平衡、校准过期、KK 差。验证三条不变量:
      ① 超时不盲目重试(blind_retry=0);② 无效测量不进 BO;③ ACK 丢失被正确重建。

  路径 B · measurement_txn(EvidenceTransaction)—— **前端 live 回路 Phase 1 真正调用的同一函数**
    `submit_measurement_offline`。用 18 条 **真机谱** 里最暖的一条做健康基线,再注入
    **bundle 级计量/溯源类** 故障:原始文件缺失、KK 失败、样品错配、Rb-ACT 弃权。
    验证:健康谱按用途准入(可进 BO),每类故障都被对应 U1–U6 门控正确拒绝 / 不进 BO。

诚实边界:ACK/温度/校准属"在线见证",只能由仪器 ground-truth(模拟器/真机)对账 → 走路径 A;
文件缺失/KK/样品/Rb 分歧属"已落盘 bundle 可判" → 走路径 B(与前端同源)。两条路径合起来
覆盖湿实验里"软件 success ≠ 物理/计量有效"的完整故障谱。本脚本纯软件、零硬件、可复算。
"""
from __future__ import annotations

import json
import re
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO = next(_p for _p in Path(__file__).resolve().parents if _p.name == "V1.0-qianduan-mainline").parent
MAIN = REPO / "V1.0-qianduan-mainline"
for p in (MAIN, MAIN / "stage0_measurement", MAIN / "stage1_optimization", MAIN / "backend_api"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from modules.io_utils.chi_parser import parse_chi_file  # noqa: E402
from services.hardware_adapter import HardwareAdapter  # noqa: E402
from scientific_harness.measurement_txn import submit_measurement_offline  # noqa: E402
from scientific_harness.admission import IntendedUse  # noqa: E402
from rb_act import analyze_spectrum, ABSTAIN  # noqa: E402

import scientific_harness.demo_a as demo_a  # noqa: E402

CHI_DIR = Path(r"E:\chi_data\b_track_fulltemp")
THICKNESS_CM = 0.0564
AREA_CM2 = 1.96
SAMPLE_ID = "ATP-R0.186-N1.029-live-fulltemp"
OUT = REPO / "experiments" / "scientific_harness" / "p4_fault_reconciliation_report.json"

_T_RE = re.compile(r"_T(-?\d+(?:[.p]\d+)?)_")


def temp_from_name(name: str) -> Optional[float]:
    m = _T_RE.search(name)
    return float(m.group(1).replace("p", ".")) if m else None


def _adm(txn) -> Dict[str, str]:
    """{U1..U6: status}（保持 U 序）。"""
    return {str(getattr(k, "name", k)): v["status"] for k, v in txn.use_admissions.items()}


def build_healthy_bundle() -> Dict[str, Any]:
    """用最暖的一条真机谱构健康 bundle:走 live 同源的 _do_rb_fitting 取 rb/kk,
    再用 rb_act 取准入信号(rb_method_spread_dex 等)。"""
    files = sorted(
        (p for p in CHI_DIR.glob("*.txt") if temp_from_name(p.name) is not None),
        key=lambda p: temp_from_name(p.name),
        reverse=True,
    )
    if not files:
        raise FileNotFoundError(f"无真机谱:{CHI_DIR}")
    fp = files[0]
    T_C = temp_from_name(fp.name)
    parsed = parse_chi_file(str(fp))
    if not parsed.get("success"):
        raise RuntimeError(f"解析失败:{fp.name}")
    freq, zr, zi = parsed["frequencies"], parsed["z_real"], parsed["z_imag"]

    a = HardwareAdapter()
    a._thickness_cm, a._area_cm2 = THICKNESS_CM, AREA_CM2
    rb_result = a._do_rb_fitting(freq, zr, zi, T_C)
    raw = rb_result.get("raw") if isinstance(rb_result, dict) else None
    kk_res = (raw.get("kk_result") or {}).get("mu_median") if isinstance(raw, dict) else None

    r = analyze_spectrum(freq, zr, zi, thickness_cm=THICKNESS_CM, area_cm2=AREA_CM2)
    rb_act_signals = dict(getattr(r, "admission_signals", {}) or {})

    bundle = {
        "sample_id": SAMPLE_ID,
        "geometry": {"thickness_cm": THICKNESS_CM, "area_cm2": AREA_CM2},
        "file_hashes": {fp.name: parsed.get("sha256") or "real_file"},
        "eis_points": [{
            "T_K": float(T_C) + 273.15,
            "status": (rb_result.get("status") if isinstance(rb_result, dict) else None) or "OK",
            "kk_residual": kk_res,
            "rb_ohm": rb_result.get("rb_ohm") if isinstance(rb_result, dict) else None,
            "rb_method": rb_result.get("rb_method") if isinstance(rb_result, dict) else None,
        }],
        "arrhenius": {},
    }
    meta = {"source_file": fp.name, "temperature_C": T_C, "kk_residual": kk_res,
            "rb_decision": str(r.decision), "rb_act_signals": rb_act_signals}
    return {"bundle": bundle, "rb_act_signals": rb_act_signals, "meta": meta}


def run_txn_path() -> Dict[str, Any]:
    """路径 B:前端 live 同源 submit_measurement_offline 的故障矩阵(真机谱)。"""
    h = build_healthy_bundle()
    base_bundle, base_sig, meta = h["bundle"], h["rb_act_signals"], h["meta"]

    # 各场景:对健康 bundle / 信号做最小注入,期望"是否进 BO"。
    def scen_healthy():
        return base_bundle, dict(base_sig), base_bundle["sample_id"]

    def scen_no_file():
        b = deepcopy(base_bundle); b["file_hashes"] = {}      # 原始文件缺失 → C_P 不确认
        return b, dict(base_sig), b["sample_id"]

    def scen_sample_mismatch():
        return base_bundle, dict(base_sig), "WRONG-SAMPLE-XYZ"  # 样品错配 → C_P unknown

    def scen_kk_fail():
        b = deepcopy(base_bundle); b["eis_points"][0]["kk_residual"] = 0.60  # 谱质量差
        return b, dict(base_sig), b["sample_id"]

    def scen_rb_abstain():
        sig = dict(base_sig)
        sig["rb_method_spread_dex"] = 0.50   # ≥0.30 → Rb 可提取性 FAIL（Rb-ACT 弃权语义）
        sig["rb_method_success"] = False
        return base_bundle, sig, base_bundle["sample_id"]

    # (name, builder, 期望进BO, 该故障必须使其 REJECT 的关键用途)
    scenarios = [
        ("healthy",         scen_healthy,         True,  []),
        ("no_file",         scen_no_file,         False, list(IntendedUse.ALL)),
        ("sample_mismatch", scen_sample_mismatch, False, list(IntendedUse.ALL)),
        ("kk_fail",         scen_kk_fail,         False, [IntendedUse.UPDATE_BO]),
        ("rb_abstain",      scen_rb_abstain,      False, [IntendedUse.ESTIMATE_POINT_CONDUCTIVITY,
                                                          IntendedUse.UPDATE_BO]),
    ]

    rows: List[Dict[str, Any]] = []
    for name, build, expect_bo, must_reject in scenarios:
        bundle, sig, expected_sid = build()
        txn = submit_measurement_offline(bundle, expected_sample_id=expected_sid, rb_act_signals=sig)
        adm = _adm(txn)
        reject_ok = all(adm.get(u) in ("REJECT", "CONTESTED") for u in must_reject)
        rows.append({
            "scenario": name,
            "entered_bo": txn.entered_bo,
            "expected_entered_bo": expect_bo,
            "bo_match": txn.entered_bo == expect_bo,
            "blind_retry_count": txn.blind_retry_count,
            "must_reject_uses": must_reject,
            "must_reject_satisfied": reject_ok,
            "admissions": adm,
        })

    invalid_into_bo = sum(1 for r in rows if r["entered_bo"] and not r["expected_entered_bo"])
    healthy = next(r for r in rows if r["scenario"] == "healthy")
    all_bo_match = all(r["bo_match"] for r in rows)
    all_reject_ok = all(r["must_reject_satisfied"] for r in rows)
    blind_total = sum(r["blind_retry_count"] for r in rows)

    return {
        "path": "B - measurement_txn (前端 live 同源)",
        "baseline": meta,
        "scenarios": rows,
        "acceptance": {
            "invalid_into_bo_count": invalid_into_bo,
            "healthy_entered_bo": bool(healthy["entered_bo"]),
            "all_bo_match_expectation": bool(all_bo_match),
            "all_fault_uses_rejected": bool(all_reject_ok),
            "blind_retry_count": blind_total,
        },
        "acceptance_pass": (invalid_into_bo == 0 and all_bo_match and all_reject_ok and blind_total == 0),
    }


def main() -> int:
    path_a = demo_a.run()                       # CommitController 三重提交 6 场景
    path_b = run_txn_path()                      # measurement_txn 前端同源 5 场景

    overall_pass = bool(path_a["acceptance_pass"] and path_b["acceptance_pass"])
    report = {
        "title": "Phase 4 / Tier-S 故障注入对账证据(双治理路径,真机谱)",
        "sample_id": SAMPLE_ID,
        "geometry": {"thickness_cm": THICKNESS_CM, "area_cm2": AREA_CM2},
        "path_A_commit_controller": path_a,
        "path_B_measurement_txn": path_b,
        "honest_scope": {
            "online_witness_faults": ["ack_lost_file_ok", "timeout_no_effect",
                                      "temp_not_equilibrated", "calibration_expired"],
            "bundle_level_faults": ["no_file", "kk_fail", "sample_mismatch", "rb_abstain"],
            "note": "在线见证类故障只能由仪器 ground-truth 对账(路径 A 模拟器/真机);"
                    "bundle 可判类用真机谱走前端同源准入(路径 B)。两路合并即完整故障谱。",
        },
        "tier_s_gate_pass": overall_pass,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=" * 72)
    print("路径 A · CommitController(Demo A):", "PASS" if path_a["acceptance_pass"] else "FAIL")
    for r in path_a["scenarios"]:
        print(f"   {r['scenario']:22s} C_P={r['physical_commit']:14s} "
              f"BO={r['entered_bo']}(exp {r['expected_entered_bo']}) match={r['match']}")
    print("-" * 72)
    print("路径 B · measurement_txn(前端同源):", "PASS" if path_b["acceptance_pass"] else "FAIL")
    print(f"   基线谱: {path_b['baseline']['source_file']} "
          f"(T={path_b['baseline']['temperature_C']}°C, kk={path_b['baseline']['kk_residual']})")
    for r in path_b["scenarios"]:
        print(f"   {r['scenario']:16s} BO={str(r['entered_bo']):5s}(exp {r['expected_entered_bo']}) "
              f"reject_ok={r['must_reject_satisfied']}  {r['admissions']}")
    print("=" * 72)
    print(f"Tier-S 门:{'PASS' if overall_pass else 'FAIL'}  →  {OUT}")
    return 0 if overall_pass else 1


if __name__ == "__main__":
    sys.exit(main())
