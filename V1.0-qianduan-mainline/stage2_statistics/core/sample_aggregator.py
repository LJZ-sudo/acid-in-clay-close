"""按 sample_id 聚合 row-level CSV，构建 SampleSummary 与 RowLevelQC (P-Stage2-B/H)。

行 vs 样品分离：
    - row-level QC：每行做 sigma>0、T 在 100..600K、几何完整、EIS 完整四项检查；
    - sample-level summary：每样品做 R/N 一致性检查、温度网格覆盖、Arrhenius 拟合，并对
      6 个常用温度点 (299/273/253/233/213/193 K) 做线性插值得到电导率。
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from .schema_v2 import RawPoint, RowLevelQC, SampleSummary

K_BOLTZMANN_eV = 8.617_333_262e-5
INTERP_TEMPS_K: Tuple[int, ...] = (299, 273, 253, 233, 213, 193)


def _safe_float(v) -> Optional[float]:
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return f


def _alias(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    for c in candidates:
        if c in df.columns:
            return c
    return None


# ---------------------------------------------------------------------------
# Row-level
# ---------------------------------------------------------------------------

def build_raw_points(df: pd.DataFrame) -> List[RawPoint]:
    """从输入 DataFrame 抽出 RawPoint 列表（保留所有行，不过滤）。"""
    if df is None or df.empty or "sample_id" not in df.columns:
        return []

    t_col = _alias(df, ["T_K", "T", "T_avg_K", "T_mid", "temperature_K", "temperature"])
    sigma_col = _alias(df, ["sigma", "conductivity", "conductivity_S_cm"])
    rb_col = _alias(df, ["rb_ohm", "Rb", "R_b"])
    L_col = _alias(df, ["L_cm", "thickness_cm", "thickness"])
    A_col = _alias(df, ["S_cm2", "area_cm2", "area"])
    ea_col = _alias(df, ["Ea", "Ea_eV"])
    r2_col = _alias(df, ["R2", "r_squared"])

    arc_col = "arc_visible" if "arc_visible" in df.columns else None
    semi_col = "semicircle_visible" if "semicircle_visible" in df.columns else None
    src_col = _alias(df, ["scan_dir", "source_file", "raw_file"])

    out: List[RawPoint] = []
    for idx, row in df.iterrows():
        T = _safe_float(row.get(t_col)) if t_col else None
        if T is None:
            continue
        out.append(
            RawPoint(
                row_id=str(idx),
                sample_id=str(row["sample_id"]),
                R=_safe_float(row.get("R")),
                N=_safe_float(row.get("N")),
                T_K=T,
                sigma_S_cm=_safe_float(row.get(sigma_col)) if sigma_col else None,
                rb_ohm=_safe_float(row.get(rb_col)) if rb_col else None,
                thickness_cm=_safe_float(row.get(L_col)) if L_col else None,
                area_cm2=_safe_float(row.get(A_col)) if A_col else None,
                ea_reported_eV=_safe_float(row.get(ea_col)) if ea_col else None,
                r2_reported=_safe_float(row.get(r2_col)) if r2_col else None,
                arc_visible=bool(row[arc_col]) if arc_col and pd.notna(row[arc_col]) else None,
                semicircle_visible=(
                    bool(row[semi_col]) if semi_col and pd.notna(row[semi_col]) else None
                ),
                source_file=str(row[src_col]) if src_col and pd.notna(row[src_col]) else None,
                notes=None,
            )
        )
    return out


def build_row_level_qc(points: List[RawPoint]) -> List[RowLevelQC]:
    out: List[RowLevelQC] = []
    for p in points:
        flags: List[str] = []

        valid_sigma = p.sigma_S_cm is not None and p.sigma_S_cm > 0
        if not valid_sigma:
            flags.append("non_positive_or_missing_sigma")

        valid_temperature = 100.0 <= p.T_K <= 600.0
        if not valid_temperature:
            flags.append("temperature_out_of_range")

        valid_geometry = (
            p.thickness_cm is not None
            and p.area_cm2 is not None
            and p.thickness_cm > 0
            and p.area_cm2 > 0
        )
        if not valid_geometry:
            flags.append("missing_or_invalid_geometry")

        valid_eis = (p.rb_ohm is not None and p.rb_ohm > 0) or valid_sigma
        if not valid_eis:
            flags.append("missing_eis")

        out.append(
            RowLevelQC(
                row_id=p.row_id,
                sample_id=p.sample_id,
                valid_sigma=valid_sigma,
                valid_temperature=valid_temperature,
                valid_geometry=valid_geometry,
                valid_eis=valid_eis,
                flags=flags,
            )
        )
    return out


# ---------------------------------------------------------------------------
# Sample-level
# ---------------------------------------------------------------------------

def _interp_log_sigma_at(T_target: float, T_arr: np.ndarray, log_sigma: np.ndarray) -> Optional[float]:
    """在 ln(sigma) 空间对 T 做线性插值，仅在 [Tmin, Tmax] 内才返回。"""
    if T_arr.size < 2:
        return None
    if T_target < T_arr.min() or T_target > T_arr.max():
        return None
    order = np.argsort(T_arr)
    T_sorted = T_arr[order]
    Y_sorted = log_sigma[order]
    val = float(np.interp(T_target, T_sorted, Y_sorted))
    return float(math.exp(val))


def _fit_arrhenius(T: np.ndarray, sigma: np.ndarray) -> Optional[Dict[str, float]]:
    """单样品 Arrhenius 拟合 (在 ln(sigma) ~ 1/T 空间，最小二乘)。"""
    if T.size < 4:
        return None
    inv_T = 1.0 / T
    y = np.log(sigma)
    if not np.all(np.isfinite(y)):
        return None
    slope, intercept = np.polyfit(inv_T, y, 1)
    y_pred = slope * inv_T + intercept
    rss = float(np.sum((y - y_pred) ** 2))
    tss = float(np.sum((y - y.mean()) ** 2))
    r2 = 1.0 - rss / tss if tss > 0 else 0.0
    ea_eV = float(-slope * K_BOLTZMANN_eV)
    return {
        "ea_eV": ea_eV,
        "ln_sigma0": float(intercept),
        "r2": float(r2),
        "rss": rss,
        "n_points": int(T.size),
    }


def build_sample_summaries(
    df: pd.DataFrame,
    points: Optional[List[RawPoint]] = None,
) -> List[SampleSummary]:
    """从 row-level DataFrame 聚合每个 sample_id 的摘要。"""
    if df is None or df.empty or "sample_id" not in df.columns:
        return []

    if points is None:
        points = build_raw_points(df)

    by_sample: Dict[str, List[RawPoint]] = {}
    for p in points:
        by_sample.setdefault(p.sample_id, []).append(p)

    out: List[SampleSummary] = []
    for sid, plist in by_sample.items():
        T_arr = np.array(
            [p.T_K for p in plist if p.sigma_S_cm is not None and p.sigma_S_cm > 0],
            dtype=float,
        )
        sigma_arr = np.array(
            [p.sigma_S_cm for p in plist if p.sigma_S_cm is not None and p.sigma_S_cm > 0],
            dtype=float,
        )

        n_points = int(T_arr.size)
        T_min = float(T_arr.min()) if n_points else None
        T_max = float(T_arr.max()) if n_points else None

        log_sigma = np.log(sigma_arr) if sigma_arr.size else np.array([])
        sigma_at: Dict[int, Optional[float]] = {}
        for tt in INTERP_TEMPS_K:
            sigma_at[tt] = (
                _interp_log_sigma_at(float(tt), T_arr, log_sigma)
                if log_sigma.size >= 2
                else None
            )

        # R/N 一致性
        Rs = [p.R for p in plist if p.R is not None]
        Ns = [p.N for p in plist if p.N is not None]
        flags: List[str] = []
        R = N = None
        if Rs:
            R = float(np.median(Rs))
            if (max(Rs) - min(Rs)) > 1e-6:
                flags.append("RN_inconsistent_R")
        else:
            flags.append("missing_R")
        if Ns:
            N = float(np.median(Ns))
            if (max(Ns) - min(Ns)) > 1e-6:
                flags.append("RN_inconsistent_N")
        else:
            flags.append("missing_N")

        # 低温覆盖
        if T_min is not None and T_min > 233:
            flags.append("missing_low_temperature_coverage")
        if n_points < 5:
            flags.append("too_few_temperature_points")

        # Arrhenius 单段拟合
        arr_fit = _fit_arrhenius(T_arr, sigma_arr) if n_points >= 4 else None

        # 形貌标志
        has_arc = any(bool(p.arc_visible) for p in plist if p.arc_visible is not None)
        has_semi = any(
            bool(p.semicircle_visible) for p in plist if p.semicircle_visible is not None
        )

        out.append(
            SampleSummary(
                sample_id=sid,
                R=R,
                N=N,
                n_temperature_points=n_points,
                temperature_min_K=T_min,
                temperature_max_K=T_max,
                sigma_299K_interp_S_cm=sigma_at[299],
                sigma_273K_interp_S_cm=sigma_at[273],
                sigma_253K_interp_S_cm=sigma_at[253],
                sigma_233K_interp_S_cm=sigma_at[233],
                sigma_213K_interp_S_cm=sigma_at[213],
                sigma_193K_interp_S_cm=sigma_at[193],
                max_sigma_S_cm=float(sigma_arr.max()) if sigma_arr.size else None,
                min_sigma_S_cm=float(sigma_arr.min()) if sigma_arr.size else None,
                best_arrhenius_ea_eV=(arr_fit or {}).get("ea_eV"),
                best_arrhenius_ln_sigma0=(arr_fit or {}).get("ln_sigma0"),
                best_arrhenius_r2=(arr_fit or {}).get("r2"),
                has_arc_visible=has_arc,
                has_semicircle_visible=has_semi,
                quality_flags=flags,
            )
        )
    out.sort(key=lambda s: s.sample_id)
    return out


def sample_summaries_to_dataframe(summaries: List[SampleSummary]) -> pd.DataFrame:
    return pd.DataFrame([s.model_dump() for s in summaries])
