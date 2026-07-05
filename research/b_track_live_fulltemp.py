# -*- coding: utf-8 -*-
"""全温区 live 收口（§12.3,FT-1..FT-4）——把 B 轨 / ESAS-OS 2.0 的离线模拟真实接上。

消费一次全温区 live 降温实验的产物:
  - live 原始谱目录(run_online --chi_data_dir,内含 `<material>_T<温度>_f..._V0.txt`);
  - live shadow 目录(run_online --harness_mode shadow → shadow_harness_{log.jsonl,summary.json})。

产出 output/b_track_real/fulltemp/:
  FT-1  全温区 live shadow 汇总(n_points / agreement_rate / blind_retry / shadow_looser)。
  FT-2  Rb-ACT **R2**:逐点 analyze_spectrum vs legacy,|Δlog10 Rb| 分布 + 未解释翻转(目标 0)。
  FT-3  measurement_txn **live 逐点准入**:每点 entered_bo / U1–U6 / blind_retry。
  FT-4  live Arrhenius + σ(T) vs 离线复现地板:live 作第 4 片,与三批逐温配对 |Δlog10σ|,
        核验 warm/cold 是否落在 LINE_B_LOCAL_DIRECT 地板内(warm p90 0.146 / cold p90 0.356)。

诚实:谱为真机实测;厚度=0.0564cm(在机=离线 batch C 同片几何);legacy rb_fitting 零改动;EIS-only C4。
用法:
  python b_track_live_fulltemp.py \
      --chi_data_dir E:\\chi_data\\b_track_fulltemp \
      --material ATP-R0.186-N1.029-live-fulltemp \
      --thickness 0.0564 --area 1.96
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

REPO = Path(__file__).resolve().parent.parent
MAIN = REPO / "V1.0-qianduan-mainline"
sys.path.insert(0, str(MAIN / "stage0_measurement"))
sys.path.insert(0, str(MAIN / "stage1_optimization"))

from modules.io_utils.chi_parser import parse_chi_file  # noqa: E402
from modules.analysis import eis_pipeline  # noqa: E402
from rb_act import analyze_spectrum, ABSTAIN  # noqa: E402
from scientific_harness.measurement_txn import submit_measurement_offline  # noqa: E402
from scientific_harness.admission import REJECT  # noqa: E402

OUT = MAIN / "output" / "b_track_real" / "fulltemp"
FLOOR = MAIN / "output" / "e1_floor" / "LINE_B_LOCAL_DIRECT.json"
OFFLINE_BUNDLES = MAIN / "output" / "stage0_results"
FLIP_DEX = 0.30
WARM_CUT_C = -20.0
# 兼容两种温度写法:正常 `_T-1.0_` 与宏救援/文件名清洗后的 `_T-1p0_`(小数点→'p')。
_T_RE = re.compile(r"_T(-?\d+(?:[.p]\d+)?)_")


def _temp_from_name(name: str) -> Optional[float]:
    m = _T_RE.search(name)
    if not m:
        return None
    return float(m.group(1).replace("p", "."))


def _percentiles(vals: List[float]) -> Dict[str, Optional[float]]:
    if not vals:
        return {"n": 0, "median": None, "p90": None, "max": None}
    a = np.array(sorted(vals), dtype=float)
    return {"n": int(a.size), "median": float(np.median(a)),
            "p90": float(np.percentile(a, 90)), "max": float(a.max())}


def collect_live_points(chi_dir: Path, thickness: float, area: float) -> List[Dict[str, Any]]:
    """解析 live 目录所有谱,逐点 EIS pipeline + Rb-ACT 双跑。"""
    pts: List[Dict[str, Any]] = []
    files = sorted(chi_dir.glob("*.txt"))
    for fp in files:
        T_C = _temp_from_name(fp.name)
        if T_C is None:
            continue
        parsed = parse_chi_file(str(fp))
        if not parsed.get("success"):
            pts.append({"file": fp.name, "T_C": T_C, "parse_ok": False})
            continue
        freq, zr, zi = parsed["frequencies"], parsed["z_real"], parsed["z_imag"]
        T_K = T_C + 273.15
        eis = eis_pipeline.analyze_eis_point(frequencies=freq, z_real=zr, z_imag=zi,
                                             temperature_C=T_C, thickness_cm=thickness,
                                             area_cm2=area)
        rb_res = eis.get("rb_result") or {}
        # Rb-ACT 双跑
        r = analyze_spectrum(freq, zr, zi, thickness_cm=thickness, area_cm2=area)
        legacy_rb = getattr(r, "legacy_rb_ohm", None)
        rbact_rb = getattr(r.posterior, "rb_ohm", None) if getattr(r, "posterior", None) else None
        delta = None
        if r.decision != ABSTAIN and legacy_rb and rbact_rb and legacy_rb > 0 and rbact_rb > 0:
            delta = abs(math.log10(rbact_rb) - math.log10(legacy_rb))
        pts.append({
            "file": fp.name, "T_C": T_C, "T_K": T_K, "parse_ok": True,
            "status": eis.get("status"),
            "rb_ohm": rb_res.get("rb_ohm"), "rb_method": rb_res.get("method"),
            "sigma_S_cm": rb_res.get("conductivity_s_per_cm"),
            "kk_residual": (eis.get("kk_result") or {}).get("mu_median"),
            "rbact_decision": str(r.decision),
            "legacy_rb_ohm": legacy_rb, "rbact_rb_ohm": rbact_rb,
            "abs_dlog10_rb": delta,
            "unexplained_flip": bool(delta is not None and delta > FLIP_DEX),
            "admission_signals": dict(getattr(r, "admission_signals", {}) or {}),
        })
    return pts


def ft1_shadow(shadow_dir: Path) -> Dict[str, Any]:
    sp = shadow_dir / "shadow_harness_summary.json"
    if not sp.exists():
        return {"task": "FT-1 full-temp live shadow", "available": False,
                "note": f"未找到 {sp}（确认 run_online --harness_mode shadow 已产出）"}
    s = json.loads(sp.read_text(encoding="utf-8"))
    return {"task": "FT-1 full-temp live shadow", "available": True,
            "n_points": s.get("n_points"), "agreement_rate": s.get("agreement_rate"),
            "blind_retry_count": s.get("blind_retry_count"),
            "shadow_looser_than_live_count": s.get("shadow_looser_than_live_count"),
            "acceptance_pass": (s.get("blind_retry_count") == 0)}


def ft2_rb_act_r2(pts: List[Dict[str, Any]]) -> Dict[str, Any]:
    ok = [p for p in pts if p.get("parse_ok") and p.get("abs_dlog10_rb") is not None]
    deltas = [p["abs_dlog10_rb"] for p in ok]
    flips = [p for p in ok if p["unexplained_flip"]]
    abst = [p for p in pts if p.get("rbact_decision") == str(ABSTAIN)]
    return {
        "task": "FT-2 Rb-ACT R2 (full-temp live double-run vs legacy)",
        "gate": "R2", "policy": "legacy adopted; Rb-ACT shadow delta only",
        "n_paired_points": len(ok),
        "delta_log10_rb": _percentiles(deltas),
        "flip_threshold_dex": FLIP_DEX,
        "n_unexplained_flips": len(flips),
        "unexplained_flips": [{"file": p["file"], "T_C": p["T_C"], "dex": p["abs_dlog10_rb"]} for p in flips],
        "n_abstain": len(abst),
        "acceptance_pass": (len(flips) == 0 and len(ok) > 0),
    }


def ft3_txn_live(pts: List[Dict[str, Any]], sample_id: str, thickness: float,
                 area: float) -> Dict[str, Any]:
    rows = []
    all_ok = True
    for p in pts:
        if not p.get("parse_ok"):
            continue
        bundle = {
            "sample_id": sample_id,
            "geometry": {"thickness_cm": thickness, "area_cm2": area},
            "file_hashes": {p["file"]: "live"},
            "eis_points": [{"T_K": p["T_K"], "status": p.get("status") or "OK",
                            "kk_residual": p.get("kk_residual"), "rb_ohm": p.get("rb_ohm"),
                            "rb_method": p.get("rb_method")}],
            "arrhenius": {},
        }
        txn = submit_measurement_offline(bundle, rb_act_signals=p.get("admission_signals") or {})
        adm = {str(getattr(k, "name", k)): v["status"] for k, v in txn.use_admissions.items()}
        rows.append({"file": p["file"], "T_C": p["T_C"], "entered_bo": txn.entered_bo,
                     "blind_retry_count": txn.blind_retry_count, "admissions": adm})
        if txn.blind_retry_count != 0:
            all_ok = False
    return {"task": "FT-3 measurement_txn live per-point admission",
            "n_points": len(rows), "rows": rows,
            "acceptance_pass": all_ok and len(rows) > 0}


def _sigma_at(pts_by_T: List[Tuple[float, float]], T: float) -> Optional[float]:
    """在 live σ(T) 曲线上对温度 T 做线性插值(log10σ vs T)。"""
    xs = [t for t, _ in pts_by_T]
    if not xs or T < min(xs) or T > max(xs):
        return None
    arr = sorted(pts_by_T)
    ts = np.array([t for t, _ in arr]); ys = np.array([math.log10(s) for _, s in arr])
    return float(np.interp(T, ts, ys))  # 返回 log10σ


def ft4_floor(pts: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not FLOOR.exists():
        return {"task": "FT-4 live Arrhenius vs floor", "available": False}
    floor = json.loads(FLOOR.read_text(encoding="utf-8"))["floor"]
    live = [(p["T_C"], p["sigma_S_cm"]) for p in pts
            if p.get("parse_ok") and p.get("sigma_S_cm") and p["sigma_S_cm"] > 0]
    if len(live) < 3:
        return {"task": "FT-4 live Arrhenius vs floor", "available": False,
                "note": f"live σ(T) 点太少({len(live)})"}
    # 与三批离线逐温配对 |Δlog10σ|
    warm, cold = [], []
    for key, bp in floor.get("bundle_paths", {}).items():
        try:
            b = json.loads(Path(bp).read_text(encoding="utf-8"))
        except Exception:
            continue
        for ep in b.get("eis_points", []):
            T = ep.get("T_C"); s = ep.get("sigma_S_cm")
            if T is None or not s or s <= 0:
                continue
            lv = _sigma_at(live, T)
            if lv is None:
                continue
            d = abs(lv - math.log10(s))
            (warm if T >= WARM_CUT_C else cold).append(d)
    fw, fc = floor.get("warm", {}), floor.get("cold", {})
    lw, lc = _percentiles(warm), _percentiles(cold)
    return {
        "task": "FT-4 live σ(T) vs LINE_B_LOCAL_DIRECT floor (live as 4th pellet)",
        "available": True,
        "live_n_sigma_points": len(live),
        "live_T_range_C": [max(t for t, _ in live), min(t for t, _ in live)],
        "warm_vs_floor": {"live": lw, "floor_p90": fw.get("p90"),
                          "within_floor": (lw["p90"] is not None and fw.get("p90") is not None
                                           and lw["p90"] <= fw["p90"])},
        "cold_vs_floor": {"live": lc, "floor_p90": fc.get("p90"),
                          "within_floor": (lc["p90"] is not None and fc.get("p90") is not None
                                           and lc["p90"] <= fc["p90"])},
        "note": "live 与离线三批逐温配对 |Δlog10σ|;within_floor=True 表示 live 复现性落在已建地板内。",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--chi_data_dir", required=True, help="live 原始谱目录")
    ap.add_argument("--material", default="ATP-R0.186-N1.029-live-fulltemp")
    ap.add_argument("--shadow_dir", default=None, help="默认 <chi_data_dir>/shadow_harness")
    ap.add_argument("--thickness", type=float, default=0.0564)
    ap.add_argument("--area", type=float, default=1.96)
    args = ap.parse_args()

    chi_dir = Path(args.chi_data_dir)
    shadow_dir = Path(args.shadow_dir) if args.shadow_dir else (chi_dir / "shadow_harness")
    OUT.mkdir(parents=True, exist_ok=True)

    if not chi_dir.exists():
        print(f"[FT] live 目录不存在: {chi_dir}（先跑 §12.2 的 run_online 全温区实验）")
        return 1

    pts = collect_live_points(chi_dir, args.thickness, args.area)
    n_ok = sum(1 for p in pts if p.get("parse_ok"))
    if n_ok == 0:
        print(f"[FT] {chi_dir} 下未解析到任何 live 谱(.txt 且文件名含 _T<温度>_)。")
        return 1

    ft1 = ft1_shadow(shadow_dir)
    ft2 = ft2_rb_act_r2(pts)
    ft3 = ft3_txn_live(pts, args.material, args.thickness, args.area)
    ft4 = ft4_floor(pts)

    summary = {
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "scope": "§12.3 full-temp live close-out (FT-1..FT-4)",
        "recipe": {"R": 0.186, "N": 1.029}, "thickness_cm": args.thickness, "area_cm2": args.area,
        "n_live_points_parsed": n_ok,
        "ft1_shadow": ft1, "ft2_rb_act_r2": ft2, "ft3_txn_live": ft3, "ft4_floor": ft4,
        "honest_boundary": "谱真机实测;厚度0.0564cm(在机=离线batchC同片);legacy零改动;EIS-only C4。",
    }
    (OUT / "b_track_live_fulltemp_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "live_points_detail.json").write_text(
        json.dumps(pts, ensure_ascii=False, indent=2), encoding="utf-8")

    print("===== §12.3 全温区 live 收口 =====")
    print(f"[FT-0] 解析 live 谱 {n_ok} 点, T 区间 "
          f"{max((p['T_C'] for p in pts if p.get('parse_ok')), default='?')}→"
          f"{min((p['T_C'] for p in pts if p.get('parse_ok')), default='?')}°C")
    print(f"[FT-1] shadow: available={ft1.get('available')} n={ft1.get('n_points')} "
          f"agreement={ft1.get('agreement_rate')} blind_retry={ft1.get('blind_retry_count')}")
    print(f"[FT-2] Rb-ACT R2: paired={ft2['n_paired_points']} "
          f"median|Δlog10Rb|={ft2['delta_log10_rb']['median']} flips={ft2['n_unexplained_flips']} "
          f"pass={ft2['acceptance_pass']}")
    print(f"[FT-3] txn live: n={ft3['n_points']} pass={ft3['acceptance_pass']}")
    if ft4.get("available"):
        print(f"[FT-4] floor: warm within={ft4['warm_vs_floor']['within_floor']} "
              f"(live p90={ft4['warm_vs_floor']['live']['p90']} ≤ {ft4['warm_vs_floor']['floor_p90']}); "
              f"cold within={ft4['cold_vs_floor']['within_floor']}")
    print(f"写出: {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
