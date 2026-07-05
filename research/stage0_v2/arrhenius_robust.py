# -*- coding: utf-8 -*-
"""M1-3 — 取消"按预期删点",改稳健回归 + 三敏感性。

对每个数据集:
  - all_admissible_points: 保留所有 QA 合格点(flag_sequence_anomalies),analyze_arrhenius;
  - robust_regression: 主导段 Student-t IRLS 稳健斜率(异常点降权而非删除),对照 OLS 的 Ea;
  - leave_one_point_out: 逐点剔除一次,看 n_segments / 断点是否稳定。

证明:① 不靠删点;② 转变对单点剔除稳健;③ 异常点不显著拖拽 Ea。
绝不改 legacy 产物;输出 *_v2。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from . import versions as V

sys.path.insert(0, str(V.MAINLINE_ROOT / "stage0_measurement"))
from modules.analysis.eis_pipeline import flag_sequence_anomalies  # noqa: E402
from modules.analysis.algorithms.arrhenius import analyze_arrhenius  # noqa: E402


def _records_from_aggregated(aggregated_json: Path) -> List[Dict[str, Any]]:
    data = json.loads(aggregated_json.read_text(encoding="utf-8"))
    recs = []
    for m in data.get("measurements", []) or []:
        recs.append({
            "success": bool(m.get("success")),
            "temperature_K": m.get("temperature_K"),
            "conductivity_s_per_cm": m.get("conductivity_S_per_cm"),
            "rb_ohm": m.get("rb_ohm"),
        })
    return recs


def _arr_summary(x: np.ndarray, y: np.ndarray) -> Dict[str, Any]:
    if len(x) < 5:
        return {"success": False, "n_points": int(len(x))}
    r = analyze_arrhenius(x, y, min_segment_points=3)
    if not r.get("success"):
        return {"success": False, "n_points": int(len(x)), "error": r.get("error")}
    return {
        "success": True,
        "n_points": int(len(x)),
        "n_segments": r.get("n_segments"),
        "has_transition": bool(r.get("has_transition")),
        "transition_temps_K": r.get("transition_temps_K") or [],
        "ea_eV": [seg.get("Ea_eV") for seg in r.get("segments", [])],
    }


def _student_t_irls_slope(x: np.ndarray, y: np.ndarray, dof: int = 4,
                          n_iter: int = 25) -> Dict[str, float]:
    """Student-t IRLS 稳健直线拟合(异常点降权,不删除)。返回 slope/intercept + Ea。"""
    x = np.asarray(x, float); y = np.asarray(y, float)
    w = np.ones_like(x)
    slope = intercept = 0.0
    for _ in range(n_iter):
        W = np.sum(w)
        xm = np.sum(w * x) / W
        ym = np.sum(w * y) / W
        sxx = np.sum(w * (x - xm) ** 2)
        sxy = np.sum(w * (x - xm) * (y - ym))
        slope = sxy / sxx if sxx > 0 else 0.0
        intercept = ym - slope * xm
        resid = y - (slope * x + intercept)
        s = np.median(np.abs(resid - np.median(resid))) * 1.4826
        s = s if s > 1e-12 else (np.std(resid) if np.std(resid) > 1e-12 else 1.0)
        w = (dof + 1.0) / (dof + (resid / s) ** 2)
    # Arrhenius: slope = d ln σ / d (1000/T) = -Ea/(R*1000) → Ea_eV
    R_GAS = 8.314
    EV = 96485.0
    ea_eV = -slope * R_GAS * 1000.0 / EV
    return {"slope": float(slope), "intercept": float(intercept), "Ea_eV": float(ea_eV)}


def assess_dataset(ds_dir: Path) -> Dict[str, Any]:
    recs = _records_from_aggregated(ds_dir / "aggregated_results.json")
    flagged = flag_sequence_anomalies(recs)
    pts = [p for p in flagged["points"] if p["raw_qc_valid"]]
    pts.sort(key=lambda p: p["temperature_K"], reverse=True)

    T = np.array([p["temperature_K"] for p in pts], float)
    sigma = np.array([p["conductivity_s_per_cm"] for p in pts], float)
    x = 1000.0 / T
    y = np.log(sigma)

    # ① 全点拟合
    all_fit = _arr_summary(x, y)

    # ② 主导段(最高温段)Student-t 稳健 Ea vs OLS Ea
    robust = {"available": False}
    if len(x) >= 5 and all_fit.get("success"):
        # 主导段 = 最高温(1000/T 最小)那批点;用前 ~60% 高温点近似
        order = np.argsort(x)
        k = max(4, int(round(len(x) * 0.6)))
        idx = order[:k]
        xr, yr = x[idx], y[idx]
        rob = _student_t_irls_slope(xr, yr)
        # OLS 对照
        A = np.vstack([xr, np.ones_like(xr)]).T
        ols_slope, ols_int = np.linalg.lstsq(A, yr, rcond=None)[0]
        ols_ea = -ols_slope * 8.314 * 1000.0 / 96485.0
        robust = {
            "available": True,
            "n_dominant_points": int(k),
            "ea_eV_robust_studentt": rob["Ea_eV"],
            "ea_eV_ols": float(ols_ea),
            "ea_eV_abs_delta": abs(rob["Ea_eV"] - float(ols_ea)),
        }

    # ③ 留一稳定性
    loo_nseg = []
    loo_breaks = []
    if len(x) >= 6:
        for i in range(len(x)):
            xi = np.delete(x, i); yi = np.delete(y, i)
            s = _arr_summary(xi, yi)
            if s.get("success"):
                loo_nseg.append(s["n_segments"])
                if s.get("transition_temps_K"):
                    loo_breaks.append(s["transition_temps_K"][0])
    loo = {}
    if loo_nseg:
        base_nseg = all_fit.get("n_segments")
        vals, counts = np.unique(np.array(loo_nseg), return_counts=True)
        loo = {
            "n_runs": len(loo_nseg),
            "n_segments_mode": int(vals[int(np.argmax(counts))]),
            "fraction_preserving_n_segments": float(
                np.mean([n == base_nseg for n in loo_nseg])) if base_nseg else None,
            "breakpoint_median_K": float(np.median(loo_breaks)) if loo_breaks else None,
            "breakpoint_ci95_K": (
                [float(np.percentile(loo_breaks, 2.5)), float(np.percentile(loo_breaks, 97.5))]
                if len(loo_breaks) >= 3 else None),
            "fraction_with_transition": float(np.mean([n > 1 for n in loo_nseg])),
        }

    return {
        "dataset": ds_dir.name,
        "provenance": V.make_provenance(),
        "n_points_kept": len(pts),
        "n_sequence_anomalies": flagged["n_anomalies"],
        "anomaly_temps_K": flagged["anomaly_temps_K"],
        "deleted_any_point": False,
        "all_admissible_points": all_fit,
        "robust_regression": robust,
        "leave_one_point_out": loo,
    }


def run_all(kind: str = "lineA", out_subdir: str = "arrhenius_robust") -> Dict[str, Any]:
    from . import raw_loader as rl
    out_dir = V.RESULTS_ROOT / out_subdir
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    datasets = rl.discover_datasets(kind)
    for ds in datasets:
        res = assess_dataset(ds)
        (out_dir / f"{ds.name}_robust_v2.json").write_text(
            json.dumps(res, ensure_ascii=False, indent=2, default=float), encoding="utf-8")
        rows.append({
            "dataset": res["dataset"],
            "n_points": res["n_points_kept"],
            "n_anomalies": res["n_sequence_anomalies"],
            "n_segments_all": res["all_admissible_points"].get("n_segments"),
            "loo_preserve_frac": res["leave_one_point_out"].get("fraction_preserving_n_segments"),
            "loo_transition_frac": res["leave_one_point_out"].get("fraction_with_transition"),
            "ea_robust_vs_ols_delta": res["robust_regression"].get("ea_eV_abs_delta"),
        })
    summary = {"provenance": V.make_provenance({"kind": kind}),
               "n_datasets": len(datasets), "datasets": rows}
    (out_dir / "arrhenius_robust_summary_v2.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=float), encoding="utf-8")
    return summary


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="M1-3 稳健 Arrhenius(不删点)")
    ap.add_argument("--kind", default="lineA")
    args = ap.parse_args()
    s = run_all(kind=args.kind)
    for r in s["datasets"]:
        print(f"  {r['dataset']:28s} pts={r['n_points']:2d} anom={r['n_anomalies']:2d} "
              f"nseg_all={r['n_segments_all']} loo_preserve={r['loo_preserve_frac']} "
              f"loo_trans={r['loo_transition_frac']} dEa(rob-ols)={r['ea_robust_vs_ols_delta']}")
