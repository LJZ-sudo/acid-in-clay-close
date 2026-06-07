"""Segment-level Meyer–Neldel 分析 (P-Stage2-E)。

只使用 TemperatureSegment 中独立的 Arrhenius 拟合（非 row-level 重复行）。
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Tuple

import numpy as np
from scipy import stats

from .schema_v2 import TemperatureSegment
from .strength_rules import assign_strength


def _bootstrap_slope_ci(
    xs: np.ndarray, ys: np.ndarray, sample_ids: List[str], n_boot: int = 300, alpha: float = 0.05
) -> Tuple[float, float]:
    rng = np.random.default_rng(20260502)
    by_sample: Dict[str, List[int]] = {}
    for i, s in enumerate(sample_ids):
        by_sample.setdefault(s, []).append(i)
    sids = list(by_sample.keys())

    slopes: List[float] = []
    for _ in range(n_boot):
        chosen = rng.choice(len(sids), size=len(sids), replace=True)
        idx: List[int] = []
        for k in chosen:
            idx.extend(by_sample[sids[int(k)]])
        if len(idx) < 3:
            continue
        x_b = xs[idx]
        y_b = ys[idx]
        try:
            slope, _ = np.polyfit(x_b, y_b, 1)
            slopes.append(float(slope))
        except Exception:
            continue
    if not slopes:
        return float("nan"), float("nan")
    return float(np.quantile(slopes, alpha / 2)), float(np.quantile(slopes, 1 - alpha / 2))


def analyze_meyer_neldel_from_segments(segments: List[TemperatureSegment]) -> Dict[str, Any]:
    valid = [
        s
        for s in segments
        if s.arrhenius_ea_eV is not None
        and s.arrhenius_ln_sigma0 is not None
        and 0 < s.arrhenius_ea_eV < 2.0
        and s.segment_label in {"single", "piecewise_low", "piecewise_high"}
    ]

    if not valid:
        return {
            "n_independent_segments": 0,
            "n_unique_samples": 0,
            "r2": None,
            "slope": None,
            "intercept": None,
            "slope_ci": [None, None],
            "E_MN_eV": None,
            "strength": "tentative",
            "limitations": ["No segment-level Arrhenius fits available for Meyer-Neldel analysis."],
        }

    xs = np.array([s.arrhenius_ea_eV for s in valid], dtype=float)
    ys = np.array([s.arrhenius_ln_sigma0 for s in valid], dtype=float)
    sids = [s.sample_id for s in valid]

    slope, intercept = np.polyfit(xs, ys, 1)
    y_pred = slope * xs + intercept
    rss = float(np.sum((ys - y_pred) ** 2))
    tss = float(np.sum((ys - ys.mean()) ** 2))
    r2 = 1.0 - rss / tss if tss > 0 else 0.0

    ci_lo, ci_hi = _bootstrap_slope_ci(xs, ys, sids)

    n_segments = int(xs.size)
    n_unique = len(set(sids))

    if n_unique < 5:
        strength = "tentative"
    else:
        method_quality = "high" if r2 >= 0.9 else "medium" if r2 >= 0.7 else "low"
        strength = assign_strength(n_samples=n_unique, method_quality=method_quality, p_value=None)

    limitations: List[str] = []
    if n_unique < 10:
        limitations.append(
            f"Only {n_unique} unique samples contribute Arrhenius segments; treat MN as exploratory."
        )
    limitations.append(
        "Derived from segment-level Arrhenius fits; requires independent replication before promotion."
    )

    return {
        "n_independent_segments": n_segments,
        "n_unique_samples": n_unique,
        "r2": float(r2),
        "slope": float(slope),
        "intercept": float(intercept),
        "slope_ci": [None if math.isnan(ci_lo) else ci_lo, None if math.isnan(ci_hi) else ci_hi],
        "E_MN_eV": float(1.0 / slope) if slope != 0 else None,
        "strength": strength,
        "limitations": limitations,
    }
