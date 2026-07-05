# -*- coding: utf-8 -*-
"""M1-2 — 合成全管线假阳性 / 检出力。

把"我们检测到转变"升级为"该转变超过管线在当前温度网格+噪声下的经验检出极限":
  - smooth_null: 用单段平滑 Arrhenius(无转变)+ 真实段内残差噪声生成 σ(T),跑 analyze_arrhenius,
    统计 FPR_break = P(管线在无转变数据上误报分段);并看假断点温度分布是否扎堆。
  - injected_break: 注入已知位置/强度的断点,统计检出率、断点位置偏差、最小可检 Δslope。

噪声模型:取真实数据"最佳分段模型的段内残差"作为真实测量噪声(已扣除真实结构),
再从"无断点单段"生成数据 → 干净地隔离"管线是否自造转变"。
绝不改 legacy;输出 *_v2。pwlf 慢,默认关键 LRS 数据集 + 适中抽样数。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from . import versions as V

sys.path.insert(0, str(V.MAINLINE_ROOT / "stage0_measurement"))
from modules.analysis.algorithms.arrhenius import analyze_arrhenius  # noqa: E402

KEY_DATASETS = [
    "lineA_LRS_0509CS", "lineA_LRS_6.12", "lineA_LRS_6.15_merged", "lineA_LRS_0615_s2",
]


def _xy_from_aggregated(aggregated_json: Path) -> Tuple[np.ndarray, np.ndarray]:
    data = json.loads(aggregated_json.read_text(encoding="utf-8"))
    T, s = [], []
    for m in data.get("measurements", []) or []:
        if not m.get("success"):
            continue
        tk = m.get("temperature_K"); sg = m.get("conductivity_S_per_cm")
        if tk and sg and tk > 0 and 0 < sg < 1.0:
            T.append(float(tk)); s.append(float(sg))
    T = np.array(T); s = np.array(s)
    order = np.argsort(1000.0 / T)
    return (1000.0 / T)[order], np.log(s)[order]


def _within_model_residuals(x: np.ndarray, y: np.ndarray) -> Tuple[np.ndarray, Dict[str, Any]]:
    """真实数据最佳分段模型的段内残差(真实测量噪声,已扣除真实结构)。"""
    base = analyze_arrhenius(x, y, min_segment_points=3)
    if not base.get("success"):
        return y - np.polyval(np.polyfit(x, y, 1), x), base
    yp = np.full_like(x, np.nan)
    for seg in base.get("segments") or []:
        sl, ic = seg.get("slope"), seg.get("intercept")
        si, ei = int(seg.get("start_idx", 0)), int(seg.get("end_idx", len(x)))
        if sl is None or ic is None:
            continue
        si = max(0, min(si, len(x))); ei = max(si + 1, min(ei, len(x)))
        yp[si:ei] = sl * x[si:ei] + ic
    if np.any(~np.isfinite(yp)):
        yp = np.polyval(np.polyfit(x, y, 1), x)
    return y - yp, base


def _single_line(x: np.ndarray, y: np.ndarray) -> Tuple[float, float]:
    A = np.vstack([x, np.ones_like(x)]).T
    sl, ic = np.linalg.lstsq(A, y, rcond=None)[0]
    return float(sl), float(ic)


def smooth_null_fpr(x: np.ndarray, y: np.ndarray, n_draws: int, seed: int) -> Dict[str, Any]:
    """无转变(单段)+ 真实噪声 → 误报分段的概率 + 假断点温度分布。"""
    resid, _ = _within_model_residuals(x, y)
    resid = resid[np.isfinite(resid)]
    sl, ic = _single_line(x, y)              # 无断点生成模型
    rng = np.random.default_rng(seed)
    n = len(x)
    false_breaks = 0
    ok = 0
    false_bp_K: List[float] = []
    for _ in range(n_draws):
        yb = sl * x + ic + rng.choice(resid, size=n, replace=True)
        r = analyze_arrhenius(x, yb, min_segment_points=3)
        if not r.get("success"):
            continue
        ok += 1
        if r.get("n_segments", 1) > 1:
            false_breaks += 1
            tt = r.get("transition_temps_K") or []
            if tt:
                false_bp_K.append(float(tt[0]))
    fpr = false_breaks / ok if ok else None
    return {
        "n_draws_ok": ok,
        "false_positive_rate_break": fpr,
        "false_breakpoint_median_K": float(np.median(false_bp_K)) if false_bp_K else None,
        "false_breakpoint_temps_K": false_bp_K[:50],
        "noise_sd_dex": float(np.std(resid) / np.log(10)),  # ln→log10
    }


def injected_break_power(x: np.ndarray, y: np.ndarray, n_draws: int, seed: int,
                         break_x: Optional[float] = None,
                         delta_slope: float = 2.0) -> Dict[str, Any]:
    """注入已知断点(在 break_x 处斜率突变 delta_slope)→ 检出率 + 断点位置偏差。"""
    resid, _ = _within_model_residuals(x, y)
    resid = resid[np.isfinite(resid)]
    sl, ic = _single_line(x, y)
    if break_x is None:
        break_x = float(np.median(x))
    rng = np.random.default_rng(seed)
    n = len(x)
    detected = 0; ok = 0
    bp_err = []
    for _ in range(n_draws):
        base = sl * x + ic
        bump = np.where(x >= break_x, delta_slope * (x - break_x), 0.0)
        yb = base + bump + rng.choice(resid, size=n, replace=True)
        r = analyze_arrhenius(x, yb, min_segment_points=3)
        if not r.get("success"):
            continue
        ok += 1
        if r.get("n_segments", 1) > 1:
            detected += 1
            tt = r.get("transition_temps_K") or []
            if tt:
                bp_err.append(abs(1000.0 / tt[0] - break_x))  # 在 1000/T 空间比较
    return {
        "injected_break_x_invK": break_x,
        "injected_break_T_K": 1000.0 / break_x,
        "delta_slope": delta_slope,
        "n_draws_ok": ok,
        "detection_rate": detected / ok if ok else None,
        "breakpoint_bias_invK_median": float(np.median(bp_err)) if bp_err else None,
    }


def assess_dataset(name: str, n_draws: int, seed: int) -> Dict[str, Any]:
    agg = V.DATA_ROOT / name / "aggregated_results.json"
    x, y = _xy_from_aggregated(agg)
    null = smooth_null_fpr(x, y, n_draws=n_draws, seed=seed)
    inj = injected_break_power(x, y, n_draws=n_draws, seed=seed + 1)
    # 对照:真实数据本身的分段
    real = analyze_arrhenius(x, y, min_segment_points=3)
    return {
        "dataset": name,
        "provenance": V.make_provenance({"n_draws": n_draws}),
        "n_points": int(len(x)),
        "real_n_segments": real.get("n_segments"),
        "real_transition_temps_K": real.get("transition_temps_K") or [],
        "smooth_null": null,
        "injected_break": inj,
        "interpretation": _interpret(null, real),
    }


def _interpret(null: Dict[str, Any], real: Dict[str, Any]) -> str:
    fpr = null.get("false_positive_rate_break")
    real_has = (real.get("n_segments") or 1) > 1
    if fpr is None:
        return "inconclusive"
    if real_has and fpr <= 0.10:
        return "real transition exceeds pipeline false-positive floor (FPR<=0.10)"
    if real_has and fpr <= 0.30:
        return "real transition above a moderate FPR; report FPR alongside"
    if not real_has:
        return "real data single-segment; null FPR reported for reference"
    return "high pipeline FPR; transition NOT distinguishable from analysis artifact"


def run(datasets: Optional[List[str]] = None, n_draws: int = 100, seed: int = 20260622,
        out_subdir: str = "synthetic_validation") -> Dict[str, Any]:
    out_dir = V.NDA_ROOT / out_subdir
    out_dir.mkdir(parents=True, exist_ok=True)
    names = datasets or KEY_DATASETS
    rows = []
    for name in names:
        if not (V.DATA_ROOT / name / "aggregated_results.json").exists():
            continue
        res = assess_dataset(name, n_draws=n_draws, seed=seed)
        (out_dir / f"{name}_synthetic_v2.json").write_text(
            json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
        rows.append({
            "dataset": name,
            "real_n_segments": res["real_n_segments"],
            "fpr_break": res["smooth_null"]["false_positive_rate_break"],
            "false_bp_median_K": res["smooth_null"]["false_breakpoint_median_K"],
            "injected_detection_rate": res["injected_break"]["detection_rate"],
            "interpretation": res["interpretation"],
        })
    summary = {"provenance": V.make_provenance({"n_draws": n_draws}), "datasets": rows}
    (out_dir / "synthetic_validation_summary_v2.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="M1-2 合成全管线假阳性/检出力")
    ap.add_argument("--datasets", default="")
    ap.add_argument("--n_draws", type=int, default=100)
    args = ap.parse_args()
    names = [s.strip() for s in args.datasets.split(",") if s.strip()] or None
    s = run(datasets=names, n_draws=args.n_draws)
    for r in s["datasets"]:
        print(f"  {r['dataset']:24s} real_nseg={r['real_n_segments']} "
              f"FPR={r['fpr_break']} false_bpK={r['false_bp_median_K']} "
              f"inj_detect={r['injected_detection_rate']} | {r['interpretation']}")
