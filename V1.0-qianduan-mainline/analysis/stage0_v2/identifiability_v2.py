# -*- coding: utf-8 -*-
"""M1-7 — 实践不可辨识性(模型混淆矩阵)。

把"三机理律 ΔR²=0.006"升级为更严的"设计条件下实践不可辨识性":
从 Arrhenius / VTF / Mott 各自生成合成 σ(T)(用真实温度网格 + 实测噪声),再用 AIC
模型选择器互判,得到混淆矩阵。若三律经常互相误判 → 在当前温区/采样/噪声下"实践不可辨识"。

措辞:design-conditional practical non-identifiability(不写"EIS 原则上无法区分")。
绝不改 legacy;输出 *_v2。纯 scipy 拟合(无 pwlf,快)。
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from scipy.optimize import curve_fit

from . import versions as V

KEY_DATASETS = [
    "lineA_LRS_0509CS", "lineA_LRS_6.12", "lineA_LRS_6.15_merged", "lineA_LRS_0615_s2",
]


def _load_T_lnsigma(aggregated_json: Path) -> Tuple[np.ndarray, np.ndarray]:
    data = json.loads(aggregated_json.read_text(encoding="utf-8"))
    T, s = [], []
    for m in data.get("measurements", []) or []:
        if not m.get("success"):
            continue
        tk = m.get("temperature_K"); sg = m.get("conductivity_S_per_cm")
        if tk and sg and tk > 0 and 0 < sg < 1.0:
            T.append(float(tk)); s.append(float(sg))
    T = np.array(T); y = np.log(np.array(s))
    order = np.argsort(T)
    return T[order], y[order]


# --- 三个传导律(ln σ 形式) ---
def _fit_arrhenius(T, y):
    X = np.vstack([1.0 / T, np.ones_like(T)]).T
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    yp = X @ coef
    return yp, 2  # k=2


def _fit_mott(T, y):
    X = np.vstack([T ** (-0.25), np.ones_like(T)]).T
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    yp = X @ coef
    return yp, 2


def _fit_vtf(T, y):
    # ln σ = c0 - B/(T - T0),T0 < min(T)
    def model(T, c0, B, T0):
        return c0 - B / (T - T0)
    tmin = float(np.min(T))
    p0 = [float(np.max(y)), 500.0, tmin - 50.0]
    try:
        popt, _ = curve_fit(model, T, y, p0=p0,
                            bounds=([-50, 1.0, -1000.0], [50, 1e5, tmin - 1.0]),
                            maxfev=10000)
        yp = model(T, *popt)
        return yp, 3
    except Exception:
        # 退化为 Arrhenius
        yp, _ = _fit_arrhenius(T, y)
        return yp, 3


_FITTERS = {"arrhenius": _fit_arrhenius, "mott": _fit_mott, "vtf": _fit_vtf}


def _aic(y, yp, k):
    n = len(y)
    rss = float(np.sum((y - yp) ** 2))
    if rss <= 0 or n <= k + 1:
        return np.inf
    return n * math.log(rss / n) + 2 * k + (2 * k * (k + 1)) / (n - k - 1)


def _best_model(T, y) -> str:
    aics = {}
    for name, fit in _FITTERS.items():
        yp, k = fit(T, y)
        aics[name] = _aic(y, yp, k)
    return min(aics, key=aics.get)


def confusion_matrix(T: np.ndarray, y: np.ndarray, n_draws: int = 300,
                     seed: int = 20260622) -> Dict[str, Any]:
    """从每个真律生成合成数据→互判,得混淆矩阵 + 噪声(取 Arrhenius 残差 sd)。"""
    rng = np.random.default_rng(seed)
    # 噪声尺度:用各律拟合残差的中位 sd(更稳健)
    resid_sds = []
    fits = {}
    for name, fit in _FITTERS.items():
        yp, k = fit(T, y)
        fits[name] = yp
        resid_sds.append(float(np.std(y - yp)))
    noise_sd = float(np.median(resid_sds))

    labels = list(_FITTERS.keys())
    mat = {tl: {pl: 0 for pl in labels} for tl in labels}
    for true_law in labels:
        yp_true = fits[true_law]
        for _ in range(n_draws):
            yb = yp_true + rng.normal(0, noise_sd, size=len(T))
            pred = _best_model(T, yb)
            mat[true_law][pred] += 1

    # 正确率 = 对角线均值
    diag = np.mean([mat[l][l] / n_draws for l in labels])
    # 自我识别率(被判回自己)
    self_id = {l: mat[l][l] / n_draws for l in labels}
    return {
        "n_draws": n_draws,
        "noise_sd_ln": noise_sd,
        "labels": labels,
        "matrix_counts": mat,
        "matrix_rates": {tl: {pl: mat[tl][pl] / n_draws for pl in labels} for tl in labels},
        "mean_correct_rate": float(diag),
        "self_identification_rate": self_id,
        "real_best_model": _best_model(T, y),
    }


def assess_dataset(name: str, n_draws: int = 300) -> Dict[str, Any]:
    agg = V.DATA_ROOT / name / "aggregated_results.json"
    T, y = _load_T_lnsigma(agg)
    cm = confusion_matrix(T, y, n_draws=n_draws)
    # 实践可辨识性结论
    correct = cm["mean_correct_rate"]
    if correct >= 0.80:
        verdict = "models_distinguishable_under_design"
    elif correct >= 0.55:
        verdict = "partially_identifiable"
    else:
        verdict = "design_conditional_practical_non_identifiability"
    return {
        "dataset": name,
        "provenance": V.make_provenance({"n_draws": n_draws}),
        "n_points": int(len(T)),
        "T_range_C": [float(np.min(T) - 273.15), float(np.max(T) - 273.15)],
        "confusion": cm,
        "identifiability_verdict": verdict,
        "wording": ("在当前温区/采样点/噪声下,这些经验传导律实践上"
                    + ("可辨识" if correct >= 0.80 else "不可辨识(design-conditional)")),
    }


def run(datasets: Optional[List[str]] = None, n_draws: int = 300,
        out_subdir: str = "identifiability_v2") -> Dict[str, Any]:
    out_dir = V.RESULTS_ROOT / out_subdir
    out_dir.mkdir(parents=True, exist_ok=True)
    names = datasets or KEY_DATASETS
    rows = []
    for name in names:
        if not (V.DATA_ROOT / name / "aggregated_results.json").exists():
            continue
        res = assess_dataset(name, n_draws=n_draws)
        (out_dir / f"{name}_identifiability_v2.json").write_text(
            json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
        rows.append({
            "dataset": name,
            "mean_correct_rate": res["confusion"]["mean_correct_rate"],
            "real_best_model": res["confusion"]["real_best_model"],
            "verdict": res["identifiability_verdict"],
        })
    summary = {"provenance": V.make_provenance({"n_draws": n_draws}), "datasets": rows}
    (out_dir / "identifiability_v2_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="M1-7 实践不可辨识性(模型混淆)")
    ap.add_argument("--datasets", default="")
    ap.add_argument("--n_draws", type=int, default=300)
    args = ap.parse_args()
    names = [s.strip() for s in args.datasets.split(",") if s.strip()] or None
    s = run(datasets=names, n_draws=args.n_draws)
    for r in s["datasets"]:
        print(f"  {r['dataset']:24s} correct={r['mean_correct_rate']:.2f} "
              f"real_best={r['real_best_model']:9s} -> {r['verdict']}")
