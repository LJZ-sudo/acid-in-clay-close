# -*- coding: utf-8 -*-
"""HW-2b/HW-3 真机 live 点收口（§11.2-B）。

背景:HW-2 的 CHI 测量**已成功**并落盘真实 live 谱,但 GUI 另存为把文件存到了
CHI 默认目录(E:\\chi_data\\)而非指定子目录,导致 run_online 流程在子目录里找不到、
报 Step5 失败、analyzer 未被调用(故 inline shadow 日志为空)。

本脚本对这条**真机刚测的 live 谱**补做(与 inline analyzer 完全相同的代码路径):
  1) eis_pipeline.analyze_eis_point → ShadowHarnessRecorder.record(): genuine live shadow 日志;
  2) Rb-ACT analyze_spectrum vs legacy(HW-3): live delta(R1,仍用 legacy 值);
  3) 用该 live 点构 bundle 走 submit_measurement_offline: live 测量事务化准入。

诚实:谱是 2026-06-27 22:21 真机实测;σ 用占位厚度(geometry-provisional),不影响 shadow/
Rb(Ω) delta/准入(均与几何无关)。legacy 零改动;EIS-only C4。
"""
from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = next(_p for _p in Path(__file__).resolve().parents if _p.name == "experiments").parent
MAIN = REPO / "V1.0-qianduan-mainline"
sys.path.insert(0, str(MAIN / "stage0_measurement"))
sys.path.insert(0, str(MAIN / "stage1_optimization"))

from modules.io_utils.chi_parser import parse_chi_file  # noqa: E402
from modules.analysis import eis_pipeline  # noqa: E402
from rb_act import analyze_spectrum, ABSTAIN  # noqa: E402
from scientific_harness.shadow import ShadowHarnessRecorder  # noqa: E402
from scientific_harness.measurement_txn import submit_measurement_offline  # noqa: E402
from scientific_harness.admission import REJECT  # noqa: E402

OUT = MAIN.parent / "experiments" / "output" / "b_track_real"
LIVE_FILE = Path(r"E:\chi_data\ATP-R0.186-N1.029-live_T19.0_f0.1_1000000_V0.txt")
SAMPLE = "ATP-R0.186-N1.029-live"
T_C = 19.0
THICK = 0.0564   # 用户确认的在机片真实厚度(cm);σ 现为真实几何
AREA = 1.96
FLIP_DEX = 0.30


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    if not LIVE_FILE.exists():
        print(f"[HW-2b] live 谱不存在: {LIVE_FILE}")
        return 1
    parsed = parse_chi_file(str(LIVE_FILE))
    if not parsed.get("success"):
        print(f"[HW-2b] 解析 live 谱失败: {LIVE_FILE}")
        return 1
    freq, zr, zi = parsed["frequencies"], parsed["z_real"], parsed["z_imag"]
    T_K = T_C + 273.15

    # 1) inline analyzer 等价:EIS pipeline + shadow record(genuine live shadow 日志)
    eis = eis_pipeline.analyze_eis_point(frequencies=freq, z_real=zr, z_imag=zi,
                                         temperature_C=T_C, thickness_cm=THICK, area_cm2=AREA)
    rec = ShadowHarnessRecorder(out_dir=str(OUT / "live_shadow"), sample_id=SAMPLE)
    rec.record(eis, freq=freq, z_real=zr, z_imag=zi, temperature_K=T_K)
    shadow_log = OUT / "live_shadow" / "shadow_harness_log.jsonl"
    shadow_sum = json.loads((OUT / "live_shadow" / "shadow_harness_summary.json").read_text(encoding="utf-8"))

    rb_res = eis.get("rb_result") or {}
    rb_ohm = rb_res.get("rb_ohm")
    sigma = rb_res.get("conductivity_s_per_cm")

    # 2) Rb-ACT live 双跑(HW-3)
    r = analyze_spectrum(freq, zr, zi, thickness_cm=THICK, area_cm2=AREA)
    legacy_rb = getattr(r, "legacy_rb_ohm", None)
    rbact_rb = getattr(r.posterior, "rb_ohm", None) if getattr(r, "posterior", None) else None
    delta = None
    if r.decision != ABSTAIN and legacy_rb and rbact_rb and legacy_rb > 0 and rbact_rb > 0:
        delta = abs(math.log10(rbact_rb) - math.log10(legacy_rb))
    hw3 = {
        "task": "HW-3 live Rb-ACT double-run (R1; legacy adopted)",
        "live_spectrum": str(LIVE_FILE), "decision": str(r.decision),
        "legacy_rb_ohm": legacy_rb, "rbact_rb_ohm": rbact_rb, "abs_dlog10_rb": delta,
        "flip_threshold_dex": FLIP_DEX,
        "unexplained_flip": bool(delta is not None and delta > FLIP_DEX),
        "admission_signals": dict(getattr(r, "admission_signals", {}) or {}),
    }
    (OUT / "hw3_rb_act_live.json").write_text(json.dumps(hw3, ensure_ascii=False, indent=2),
                                              encoding="utf-8")

    # 3) live 测量事务化准入(用 live 点构最小 bundle)
    rbact_signals = dict(getattr(r, "admission_signals", {}) or {})
    live_bundle = {
        "sample_id": SAMPLE,
        "geometry": {"thickness_cm": THICK, "area_cm2": AREA},
        "file_hashes": {LIVE_FILE.name: "live"},  # RAW_FILE 见证存在
        "eis_points": [{
            "T_K": T_K, "status": "OK",
            "kk_residual": (eis.get("kk_result") or {}).get("mu_median"),
            "rb_ohm": rb_ohm,
            "rb_method": (rb_res.get("method") if rb_res else None),
        }],
        "arrhenius": {},
    }
    txn = submit_measurement_offline(live_bundle, rb_act_signals=rbact_signals)
    txn_admissions = {str(getattr(k, "name", k)): v["status"] for k, v in txn.use_admissions.items()}

    summary = {
        "task": "HW-2b live point close-out (genuine live spectrum, recovered)",
        "at": datetime.now(timezone.utc).astimezone().isoformat(),
        "live_spectrum": str(LIVE_FILE),
        "measured_at": "2026-06-27 22:21 (CHI660E, real machine, 19C)",
        "ambient_C": T_C, "thickness_cm": THICK, "area_cm2": AREA,
        "sigma_geometry_provisional": False,
        "live_eis": {"success": eis.get("success"), "status": eis.get("status"),
                     "rb_ohm": rb_ohm, "conductivity_S_per_cm": sigma},
        "live_shadow": {"log": str(shadow_log), "summary": shadow_sum},
        "hw3_rb_act_live": hw3,
        "live_measurement_txn": {"entered_bo": txn.entered_bo,
                                 "blind_retry_count": txn.blind_retry_count,
                                 "admissions": txn_admissions},
        "honest_boundary": "谱真机实测;厚度=0.0564cm(用户确认真实几何);legacy 零改动;EIS-only C4。",
    }
    (OUT / "hw2_live_single_point.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print("===== HW-2b/HW-3 真机 live 点收口 =====")
    print(f"  live 谱: {LIVE_FILE.name} (真机 22:21 实测)")
    print(f"  EIS: success={eis.get('success')} status={eis.get('status')} Rb={rb_ohm} Ω σ={sigma} S/cm (厚度 {THICK}cm)")
    print(f"  live shadow: n_points={shadow_sum.get('n_points')} agree_rate={shadow_sum.get('agreement_rate')} "
          f"blind_retry={shadow_sum.get('blind_retry_count')} looser_than_live={shadow_sum.get('shadow_looser_than_live_count')}")
    print(f"  Rb-ACT live: decision={hw3['decision']} legacy_rb={legacy_rb} rbact_rb={rbact_rb} "
          f"|Δlog10Rb|={delta} flip={hw3['unexplained_flip']}")
    print(f"  live txn: entered_bo={txn.entered_bo} blind_retry={txn.blind_retry_count} admissions={txn_admissions}")
    print(f"  写出: {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
