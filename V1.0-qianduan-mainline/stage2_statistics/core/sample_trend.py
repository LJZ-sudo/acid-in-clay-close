"""Sample-level 趋势分析 (P-Stage2-C)。

强约束：
    - 所有趋势必须基于 SampleSummary，不得使用 row-level 重复行；
    - n_samples 是 sample 数，不是 row 数；
    - 临界点用 segmented regression 的 break-point 检测。
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats

from .schema_v2 import SampleSummary, TrendResult
from .strength_rules import assign_strength

# (target_metric, predictor) pairs we always try
DEFAULT_PAIRS: Tuple[Tuple[str, str], ...] = (
    ("sigma_299K_interp_S_cm", "R"),
    ("sigma_299K_interp_S_cm", "N"),
    ("sigma_233K_interp_S_cm", "R"),
    ("sigma_233K_interp_S_cm", "N"),
    ("best_arrhenius_ea_eV", "R"),
    ("best_arrhenius_ea_eV", "N"),
)


def _series(summaries: List[SampleSummary], target: str, predictor: str):
    xs, ys, ids = [], [], []
    for s in summaries:
        d = s.model_dump()
        x = d.get(predictor)
        y = d.get(target)
        if x is None or y is None:
            continue
        if isinstance(y, float) and (math.isnan(y) or math.isinf(y)):
            continue
        if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
            continue
        if target.startswith("sigma_") and y <= 0:
            continue
        if target.startswith("sigma_"):
            y = math.log10(y)
        xs.append(float(x))
        ys.append(float(y))
        ids.append(s.sample_id)
    return np.array(xs, dtype=float), np.array(ys, dtype=float), ids


def _bootstrap_ci(xs: np.ndarray, ys: np.ndarray, n_boot: int = 200, alpha: float = 0.05):
    if xs.size < 5:
        return None, None
    rng = np.random.default_rng(20260501)
    rhos = []
    for _ in range(n_boot):
        idx = rng.integers(0, xs.size, size=xs.size)
        x_b, y_b = xs[idx], ys[idx]
        if np.unique(x_b).size < 2 or np.unique(y_b).size < 2:
            continue
        rho, _ = stats.spearmanr(x_b, y_b)
        if not math.isnan(rho):
            rhos.append(rho)
    if not rhos:
        return None, None
    lo = float(np.quantile(rhos, alpha / 2))
    hi = float(np.quantile(rhos, 1 - alpha / 2))
    return lo, hi


def _segmented_break(xs: np.ndarray, ys: np.ndarray, min_seg: int = 3) -> Optional[Dict[str, float]]:
    """简单 brute-force segmented regression break-point on log10(sigma) ~ x."""
    if xs.size < (2 * min_seg):
        return None
    order = np.argsort(xs)
    xs_s, ys_s = xs[order], ys[order]
    best = None
    for split in range(min_seg, xs_s.size - min_seg + 1):
        x_lo, y_lo = xs_s[:split], ys_s[:split]
        x_hi, y_hi = xs_s[split:], ys_s[split:]
        s_lo, b_lo = np.polyfit(x_lo, y_lo, 1)
        s_hi, b_hi = np.polyfit(x_hi, y_hi, 1)
        rss = float(
            np.sum((y_lo - (s_lo * x_lo + b_lo)) ** 2)
            + np.sum((y_hi - (s_hi * x_hi + b_hi)) ** 2)
        )
        if best is None or rss < best["rss"]:
            best = {
                "rss": rss,
                "x_break": float(xs_s[split]),
                "slope_low": float(s_lo),
                "slope_high": float(s_hi),
            }
    if best is None:
        return None
    # only flag as break-point if slopes differ substantially
    if abs(best["slope_high"] - best["slope_low"]) < 0.2:
        return None
    return best


def analyze_sample_trends(
    summaries: List[SampleSummary],
    pairs: Tuple[Tuple[str, str], ...] = DEFAULT_PAIRS,
) -> List[TrendResult]:
    out: List[TrendResult] = []
    for target, predictor in pairs:
        xs, ys, ids = _series(summaries, target, predictor)
        if xs.size < 5:
            out.append(
                TrendResult(
                    trend_id=f"trend::{target}::{predictor}",
                    target_metric=target,
                    predictor=predictor,
                    method="spearman_sample_level",
                    n_samples=int(xs.size),
                    effect_size=None,
                    p_value=None,
                    ci_low=None,
                    ci_high=None,
                    strength="tentative",
                    limitations=[
                        f"Only {int(xs.size)} samples have both {predictor} and {target}; bootstrap suppressed."
                    ],
                )
            )
            continue

        rho, p = stats.spearmanr(xs, ys)
        if math.isnan(rho):
            rho, p = 0.0, 1.0
        ci_low, ci_high = _bootstrap_ci(xs, ys)
        breakpoint = _segmented_break(xs, ys)

        method_quality = "high" if xs.size >= 20 else "medium" if xs.size >= 10 else "low"
        strength = assign_strength(
            n_samples=int(xs.size),
            method_quality=method_quality,
            p_value=float(p) if p is not None else None,
            bootstrap_ci=(ci_low, ci_high) if ci_low is not None else None,
        )

        limitations: List[str] = []
        if xs.size < 10:
            limitations.append("Sample-level n < 10; treat as exploratory.")
        if target == "best_arrhenius_ea_eV":
            limitations.append(
                "best_arrhenius_ea_eV uses single-segment Arrhenius; piecewise/VTF preferences ignored."
            )

        cps = []
        if breakpoint is not None:
            cps.append(
                {
                    "predictor_value": breakpoint["x_break"],
                    "slope_below": breakpoint["slope_low"],
                    "slope_above": breakpoint["slope_high"],
                    "method": "segmented_regression_brute_force",
                }
            )

        out.append(
            TrendResult(
                trend_id=f"trend::{target}::{predictor}",
                target_metric=target,
                predictor=predictor,
                method="spearman_sample_level",
                n_samples=int(xs.size),
                effect_size=float(rho),
                p_value=float(p),
                ci_low=ci_low,
                ci_high=ci_high,
                candidate_transition_points=cps,
                strength=strength,
                limitations=limitations,
            )
        )
    return out
