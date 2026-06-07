"""按 sample_id 拟合 Arrhenius 单段 + 两段 piecewise + VTF (P-Stage2-D/E)。

所有 RSS / AIC 都在 ln(sigma) 残差空间统一计算，禁止混用 sigma-space 与 log-space。
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy.optimize import curve_fit

from .schema_v2 import (
    ModelComparisonSummary,
    RawPoint,
    SampleSummary,
    TemperatureSegment,
)
from .sample_aggregator import K_BOLTZMANN_eV


# ---------------------------------------------------------------------------
# basic fit primitives (operating in ln(sigma)-1/T or ln(sigma)-1/(T-T0) space)
# ---------------------------------------------------------------------------

def _aicc(rss: float, n: int, k: int) -> Optional[float]:
    if n <= k + 1 or rss <= 0:
        return None
    aic = n * math.log(rss / n) + 2 * k
    return aic + (2 * k * (k + 1)) / (n - k - 1)


def _fit_single_arrhenius(T: np.ndarray, ln_sigma: np.ndarray) -> Optional[Dict[str, float]]:
    if T.size < 4:
        return None
    inv_T = 1.0 / T
    slope, intercept = np.polyfit(inv_T, ln_sigma, 1)
    y_pred = slope * inv_T + intercept
    rss = float(np.sum((ln_sigma - y_pred) ** 2))
    tss = float(np.sum((ln_sigma - ln_sigma.mean()) ** 2))
    r2 = 1.0 - rss / tss if tss > 0 else 0.0
    return {
        "ea_eV": float(-slope * K_BOLTZMANN_eV),
        "ln_sigma0": float(intercept),
        "r2": float(r2),
        "rss": rss,
        "k": 2,
    }


def _fit_two_segment_arrhenius(
    T: np.ndarray, ln_sigma: np.ndarray, min_seg_points: int = 4
) -> Optional[Dict[str, object]]:
    """暴力扫描断点，使两段 Arrhenius 在 ln(sigma) 空间总 RSS 最小。"""
    if T.size < (2 * min_seg_points):
        return None
    order = np.argsort(T)
    T_s = T[order]
    Y_s = ln_sigma[order]
    inv_T = 1.0 / T_s

    best = None
    for split in range(min_seg_points, T_s.size - min_seg_points + 1):
        x_lo, y_lo = inv_T[:split], Y_s[:split]
        x_hi, y_hi = inv_T[split:], Y_s[split:]
        slope_lo, b_lo = np.polyfit(x_lo, y_lo, 1)
        slope_hi, b_hi = np.polyfit(x_hi, y_hi, 1)
        rss_lo = float(np.sum((y_lo - (slope_lo * x_lo + b_lo)) ** 2))
        rss_hi = float(np.sum((y_hi - (slope_hi * x_hi + b_hi)) ** 2))
        rss = rss_lo + rss_hi
        if best is None or rss < best["rss"]:
            best = {
                "rss": rss,
                "k": 4,
                "T_break_K": float(T_s[split]),
                "low_segment": {
                    "T_min_K": float(T_s[:split].min()),
                    "T_max_K": float(T_s[:split].max()),
                    "n_points": int(split),
                    "ea_eV": float(-slope_lo * K_BOLTZMANN_eV),
                    "ln_sigma0": float(b_lo),
                    "rss": rss_lo,
                },
                "high_segment": {
                    "T_min_K": float(T_s[split:].min()),
                    "T_max_K": float(T_s[split:].max()),
                    "n_points": int(T_s.size - split),
                    "ea_eV": float(-slope_hi * K_BOLTZMANN_eV),
                    "ln_sigma0": float(b_hi),
                    "rss": rss_hi,
                },
            }
    return best


def _vtf_model(T, ln_sigma0, B, T0):
    return ln_sigma0 - B / (T - T0)


def _fit_vtf(T: np.ndarray, ln_sigma: np.ndarray) -> Optional[Dict[str, float]]:
    if T.size < 6:
        return None
    T_min = float(T.min())
    p0 = (float(ln_sigma.max()), 1000.0, max(50.0, T_min - 50.0))
    try:
        popt, _ = curve_fit(
            _vtf_model,
            T,
            ln_sigma,
            p0=p0,
            bounds=(
                [-100.0, 1.0, 50.0],
                [100.0, 1.0e5, max(100.0, T_min - 1.0)],
            ),
            maxfev=5000,
        )
    except Exception:
        return None
    ln_sigma0, B, T0 = popt
    y_pred = _vtf_model(T, *popt)
    rss = float(np.sum((ln_sigma - y_pred) ** 2))
    return {
        "ln_sigma0": float(ln_sigma0),
        "B": float(B),
        "T0": float(T0),
        "rss": rss,
        "k": 3,
    }


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------

def fit_per_sample(
    points: List[RawPoint],
    summaries: List[SampleSummary],
) -> Tuple[List[TemperatureSegment], List[Dict[str, object]], ModelComparisonSummary]:
    """每个样品做 Arrhenius / two-segment / VTF 拟合，返回 segments + 行级 model 比较 + 汇总。"""

    by_sample: Dict[str, List[RawPoint]] = {}
    for p in points:
        if p.sigma_S_cm is None or p.sigma_S_cm <= 0:
            continue
        by_sample.setdefault(p.sample_id, []).append(p)
    summary_map = {s.sample_id: s for s in summaries}

    segments: List[TemperatureSegment] = []
    rows: List[Dict[str, object]] = []
    best_counts: Dict[str, int] = {"Arrhenius": 0, "Piecewise": 0, "VTF": 0}
    delta_pw_list: List[float] = []
    delta_vtf_list: List[float] = []
    n_with_fit = 0

    for sid in sorted(by_sample.keys()):
        plist = by_sample[sid]
        T = np.array([p.T_K for p in plist], dtype=float)
        ln_sigma = np.log(np.array([p.sigma_S_cm for p in plist], dtype=float))
        if T.size < 4:
            continue

        single = _fit_single_arrhenius(T, ln_sigma)
        piece = _fit_two_segment_arrhenius(T, ln_sigma)
        vtf = _fit_vtf(T, ln_sigma)

        if single is None:
            continue
        n_with_fit += 1

        aic_single = _aicc(single["rss"], T.size, single["k"])
        aic_piece = _aicc(piece["rss"], T.size, piece["k"]) if piece else None
        aic_vtf = _aicc(vtf["rss"], T.size, vtf["k"]) if vtf else None

        # add single segment
        segments.append(
            TemperatureSegment(
                segment_id=f"{sid}::single",
                sample_id=sid,
                T_min_K=float(T.min()),
                T_max_K=float(T.max()),
                n_points=int(T.size),
                segment_label="single",
                arrhenius_ea_eV=single["ea_eV"],
                arrhenius_ln_sigma0=single["ln_sigma0"],
                arrhenius_r2=single["r2"],
                arrhenius_aic=aic_single,
            )
        )

        # add piecewise segments if available
        if piece:
            for label_key, label in (("low_segment", "piecewise_low"), ("high_segment", "piecewise_high")):
                seg = piece[label_key]
                segments.append(
                    TemperatureSegment(
                        segment_id=f"{sid}::{label}",
                        sample_id=sid,
                        T_min_K=seg["T_min_K"],
                        T_max_K=seg["T_max_K"],
                        n_points=seg["n_points"],
                        segment_label=label,
                        arrhenius_ea_eV=seg["ea_eV"],
                        arrhenius_ln_sigma0=seg["ln_sigma0"],
                        arrhenius_r2=None,
                        arrhenius_aic=None,
                        piecewise_model_params={"T_break_K": piece["T_break_K"]},
                    )
                )

        # add VTF as a degenerate "segment" record for traceability
        if vtf:
            segments.append(
                TemperatureSegment(
                    segment_id=f"{sid}::vtf",
                    sample_id=sid,
                    T_min_K=float(T.min()),
                    T_max_K=float(T.max()),
                    n_points=int(T.size),
                    segment_label="vtf",
                    arrhenius_ea_eV=None,
                    arrhenius_ln_sigma0=None,
                    arrhenius_r2=None,
                    arrhenius_aic=None,
                    vtf_params={"B": vtf["B"], "T0": vtf["T0"], "ln_sigma0": vtf["ln_sigma0"]},
                    vtf_aic=aic_vtf,
                )
            )

        # decide best model
        candidates = [("Arrhenius", aic_single)]
        if aic_piece is not None:
            candidates.append(("Piecewise", aic_piece))
        if aic_vtf is not None:
            candidates.append(("VTF", aic_vtf))
        candidates_sorted = sorted(candidates, key=lambda x: (x[1] is None, x[1]))
        best_model = candidates_sorted[0][0]
        best_counts[best_model] = best_counts.get(best_model, 0) + 1

        delta_pw = (aic_single - aic_piece) if aic_piece is not None else None
        delta_vtf = (aic_single - aic_vtf) if aic_vtf is not None else None
        if delta_pw is not None:
            delta_pw_list.append(delta_pw)
        if delta_vtf is not None:
            delta_vtf_list.append(delta_vtf)

        smry = summary_map.get(sid)
        rows.append(
            {
                "sample_id": sid,
                "R": smry.R if smry else None,
                "N": smry.N if smry else None,
                "n_points": int(T.size),
                "best_model": best_model,
                "arrhenius_aic": aic_single,
                "piecewise_arrhenius_aic": aic_piece,
                "vtf_aic": aic_vtf,
                "delta_aic_arrhenius_vs_piecewise": delta_pw,
                "delta_aic_arrhenius_vs_vtf": delta_vtf,
                "ea_single_eV": single["ea_eV"],
                "ea_high_eV": piece["high_segment"]["ea_eV"] if piece else None,
                "ea_low_eV": piece["low_segment"]["ea_eV"] if piece else None,
                "t_break_K": piece["T_break_K"] if piece else None,
                "fit_quality_flag": "ok" if single["r2"] >= 0.85 else "low_r2_single",
            }
        )

    summary_obj = ModelComparisonSummary(
        n_samples_total=len(by_sample),
        n_samples_with_fit=n_with_fit,
        best_model_counts=best_counts,
        mean_delta_aic_arrhenius_vs_piecewise=(
            float(np.mean(delta_pw_list)) if delta_pw_list else None
        ),
        mean_delta_aic_arrhenius_vs_vtf=(
            float(np.mean(delta_vtf_list)) if delta_vtf_list else None
        ),
    )
    return segments, rows, summary_obj


def model_rows_to_dataframe(rows: List[Dict[str, object]]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def segments_to_dataframe(segments: List[TemperatureSegment]) -> pd.DataFrame:
    return pd.DataFrame([s.model_dump() for s in segments])
