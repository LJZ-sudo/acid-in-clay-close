# -*- coding: utf-8 -*-
"""M1-5 — 断点不确定度(残差 bootstrap)。

把"我们检测到一个转变"升级为带不确定度的判断:
  - model_probabilities: 各分段模型出现频率(bootstrap)
  - p_any_break: 出现 ≥2 段的频率
  - breakpoint_median_K / breakpoint_ci95_K: 断点位置 + 95% CI
  - slope_change_samples: 断点两侧斜率差分布
  - practical_identifiability: 据 p_break × CI 宽度分级

方法:残差 bootstrap(x=1000/T 固定,重采样模型残差 → 重拟合 analyze_arrhenius)。
绝不改 legacy;输出 *_v2。pwlf 较慢,默认只跑关键 LRS 数据集,n_boot 可调。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from . import versions as V

sys.path.insert(0, str(V.MAINLINE_ROOT / "stage0_measurement"))
from modules.analysis.algorithms.arrhenius import analyze_arrhenius  # noqa: E402

# 转变主张所依赖的关键 LRS 重复(默认集)
KEY_DATASETS = [
    "lineA_LRS_0429CS", "lineA_LRS_0509CS", "lineA_LRS_6.12",
    "lineA_LRS_6.15_merged", "lineA_LRS_0615_s2",
]


def _xy_from_aggregated(aggregated_json: Path):
    data = json.loads(aggregated_json.read_text(encoding="utf-8"))
    T, s = [], []
    for m in data.get("measurements", []) or []:
        if not m.get("success"):
            continue
        tk = m.get("temperature_K")
        sg = m.get("conductivity_S_per_cm")
        if tk and sg and tk > 0 and 0 < sg < 1.0:
            T.append(float(tk)); s.append(float(sg))
    T = np.array(T); s = np.array(s)
    order = np.argsort(1000.0 / T)
    x = (1000.0 / T)[order]
    y = np.log(s)[order]
    return x, y


def _reconstruct_ypred(x: np.ndarray, base: Dict[str, Any]) -> Optional[np.ndarray]:
    segs = base.get("segments") or []
    if not segs:
        return None
    yp = np.full_like(x, np.nan, dtype=float)
    for seg in segs:
        sl = seg.get("slope"); ic = seg.get("intercept")
        si = seg.get("start_idx", 0); ei = seg.get("end_idx", len(x))
        if sl is None or ic is None:
            return None
        si = max(0, min(int(si), len(x)))
        ei = max(si + 1, min(int(ei), len(x)))
        yp[si:ei] = sl * x[si:ei] + ic
    if np.any(~np.isfinite(yp)):
        # 单段兜底
        s0 = segs[0]
        if s0.get("slope") is not None and s0.get("intercept") is not None:
            yp = s0["slope"] * x + s0["intercept"]
        else:
            return None
    return yp


def bootstrap_breakpoints(x: np.ndarray, y: np.ndarray, n_boot: int = 200,
                          seed: int = 20260622) -> Dict[str, Any]:
    if len(x) < 5:
        return {"success": False, "error": "insufficient points", "n_points": int(len(x))}
    base = analyze_arrhenius(x, y, min_segment_points=3)
    if not base.get("success"):
        return {"success": False, "error": base.get("error"), "n_points": int(len(x))}

    y_pred = _reconstruct_ypred(x, base)
    if y_pred is None:
        return {"success": False, "error": "cannot reconstruct y_pred", "n_points": int(len(x))}
    resid = y - y_pred

    rng = np.random.default_rng(seed)
    n = len(x)
    model_counts: Dict[str, int] = {}
    n_seg_list: List[int] = []
    breaks: List[float] = []
    slope_changes: List[float] = []
    for _ in range(n_boot):
        yb = y_pred + rng.choice(resid, size=n, replace=True)
        r = analyze_arrhenius(x, yb, min_segment_points=3)
        if not r.get("success"):
            continue
        mt = r.get("best_model_type", "single")
        model_counts[mt] = model_counts.get(mt, 0) + 1
        nseg = r.get("n_segments", 1)
        n_seg_list.append(nseg)
        tt = r.get("transition_temps_K") or []
        if tt:
            breaks.append(float(tt[0]))
        segs = r.get("segments") or []
        if len(segs) >= 2 and segs[0].get("slope") is not None and segs[1].get("slope") is not None:
            slope_changes.append(float(segs[1]["slope"] - segs[0]["slope"]))

    n_ok = len(n_seg_list)
    if n_ok == 0:
        return {"success": False, "error": "all bootstrap fits failed", "n_points": int(n)}
    p_any_break = float(np.mean([ns > 1 for ns in n_seg_list]))
    model_probabilities = {k: v / n_ok for k, v in model_counts.items()}

    bp_med = float(np.median(breaks)) if breaks else None
    bp_ci = ([float(np.percentile(breaks, 2.5)), float(np.percentile(breaks, 97.5))]
             if len(breaks) >= 3 else None)
    bp_width = (bp_ci[1] - bp_ci[0]) if bp_ci else None

    # 实践可辨识性分级
    pol = V.load_config("stage0_v2_policy").get("breakpoint_uncertainty", {})
    p_low = float(pol.get("p_break_low", 0.50))
    p_high = float(pol.get("p_break_high", 0.90))
    if p_any_break < p_low:
        identifiability = "no_stable_break"
    elif p_any_break >= p_high and (bp_width is not None and bp_width <= 15.0):
        identifiability = "robust_empirical_transition"
    else:
        identifiability = "weak_or_wide_break"

    return {
        "success": True,
        "n_points": int(n),
        "base_model_type": base.get("best_model_type"),
        "base_n_segments": base.get("n_segments"),
        "base_transition_temps_K": base.get("transition_temps_K") or [],
        "n_boot_ok": n_ok,
        "model_probabilities": model_probabilities,
        "p_any_break": p_any_break,
        "breakpoint_median_K": bp_med,
        "breakpoint_ci95_K": bp_ci,
        "breakpoint_ci95_width_K": bp_width,
        "slope_change_median": float(np.median(slope_changes)) if slope_changes else None,
        "slope_change_ci95": ([float(np.percentile(slope_changes, 2.5)),
                               float(np.percentile(slope_changes, 97.5))]
                              if len(slope_changes) >= 3 else None),
        "practical_identifiability": identifiability,
    }


def run(datasets: Optional[List[str]] = None, n_boot: int = 200,
        out_subdir: str = "breakpoint_uncertainty") -> Dict[str, Any]:
    out_dir = V.RESULTS_ROOT / out_subdir
    out_dir.mkdir(parents=True, exist_ok=True)
    names = datasets or KEY_DATASETS
    rows = []
    for name in names:
        ds = V.DATA_ROOT / name
        agg = ds / "aggregated_results.json"
        if not agg.exists():
            continue
        x, y = _xy_from_aggregated(agg)
        res = bootstrap_breakpoints(x, y, n_boot=n_boot)
        res["dataset"] = name
        res["provenance"] = V.make_provenance({"n_boot": n_boot})
        (out_dir / f"{name}_breakpoint_v2.json").write_text(
            json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
        rows.append({
            "dataset": name, "p_any_break": res.get("p_any_break"),
            "breakpoint_median_K": res.get("breakpoint_median_K"),
            "breakpoint_ci95_K": res.get("breakpoint_ci95_K"),
            "practical_identifiability": res.get("practical_identifiability"),
        })
    summary = {"provenance": V.make_provenance({"n_boot": n_boot}), "datasets": rows}
    (out_dir / "breakpoint_uncertainty_summary_v2.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="M1-5 断点不确定度(残差 bootstrap)")
    ap.add_argument("--datasets", default="", help="逗号分隔数据集名;空=关键 LRS 集")
    ap.add_argument("--n_boot", type=int, default=200)
    args = ap.parse_args()
    names = [s.strip() for s in args.datasets.split(",") if s.strip()] or None
    s = run(datasets=names, n_boot=args.n_boot)
    for r in s["datasets"]:
        print(f"  {r['dataset']:24s} p_break={r['p_any_break']:.2f} "
              f"bp={r['breakpoint_median_K']} ci95={r['breakpoint_ci95_K']} "
              f"-> {r['practical_identifiability']}")
