"""EIS 形貌特征汇总 (P-Stage2-F)。

约束：
    - 输出 sample-level + (sample, T) 级别特征表；
    - 全局稀疏 → MorphologySummary.sparsity_warning=True；
    - 仅产生数据，不直接生成自然语言证据（由 EvidenceSynthesizer 加 limitations）。
"""

from __future__ import annotations

import math
from typing import List, Optional

import numpy as np
import pandas as pd

from .schema_v2 import MorphologySummary, RawPoint, SampleSummary


MORPHOLOGY_COLUMN_ORDER = [
    "sample_id",
    "T_K",
    "R",
    "N",
    "arc_visible",
    "semicircle_visible",
    "rb_ohm",
    "kk_residual",
    "morphology_quality_flag",
]


def _safe(v) -> Optional[float]:
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return f


def build_morphology_features(
    points: List[RawPoint], df_raw: pd.DataFrame
) -> pd.DataFrame:
    """生成 (sample_id, T_K) 级别的 EIS 形貌特征表。"""
    rows = []
    extra_cols_present = {
        "kk_residual": "kk_residual" in df_raw.columns,
        "median_zimag_ohm": "median_zimag_ohm" in df_raw.columns,
        "arc_diameter_ohm": "arc_diameter_ohm" in df_raw.columns,
        "characteristic_frequency": "characteristic_frequency" in df_raw.columns,
        "nyquist_peak_ratio": "nyquist_peak_ratio" in df_raw.columns,
    }
    df_indexed = df_raw.reset_index(drop=False)

    for p in points:
        try:
            row = df_raw.loc[int(p.row_id)]
        except (KeyError, TypeError, ValueError):
            row = None
        kk_residual = (
            _safe(row.get("kk_residual"))
            if row is not None and extra_cols_present["kk_residual"]
            else None
        )
        flag = "ok"
        if not (p.arc_visible or p.semicircle_visible):
            flag = "no_arc_no_semicircle"
        elif kk_residual is not None and kk_residual > 0.1:
            flag = "kk_residual_high"

        rec = {
            "sample_id": p.sample_id,
            "T_K": p.T_K,
            "R": p.R,
            "N": p.N,
            "arc_visible": bool(p.arc_visible) if p.arc_visible is not None else None,
            "semicircle_visible": (
                bool(p.semicircle_visible) if p.semicircle_visible is not None else None
            ),
            "rb_ohm": p.rb_ohm,
            "kk_residual": kk_residual,
            "morphology_quality_flag": flag,
        }
        # passthrough optional features
        if row is not None:
            for col in ("arc_diameter_ohm", "characteristic_frequency", "nyquist_peak_ratio", "median_zimag_ohm"):
                if extra_cols_present[col]:
                    rec[col] = _safe(row.get(col))
        rows.append(rec)

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    front = [c for c in MORPHOLOGY_COLUMN_ORDER if c in df.columns]
    rest = [c for c in df.columns if c not in front]
    return df[front + rest]


def summarize_morphology(
    summaries: List[SampleSummary], features_df: pd.DataFrame
) -> MorphologySummary:
    n_total = len(summaries)
    n_arc = sum(1 for s in summaries if s.has_arc_visible)
    n_semi = sum(1 for s in summaries if s.has_semicircle_visible)

    if features_df is None or features_df.empty:
        arc_rate = semi_rate = 0.0
    else:
        arc_rate = float(np.mean(features_df["arc_visible"].fillna(False).astype(bool)))
        semi_rate = float(np.mean(features_df["semicircle_visible"].fillna(False).astype(bool)))

    sparsity = (n_arc < 5) or (n_semi < 5) or (arc_rate < 0.05 and semi_rate < 0.05)

    return MorphologySummary(
        n_samples_total=n_total,
        n_samples_with_arc_evidence=n_arc,
        n_samples_with_semicircle_evidence=n_semi,
        arc_visible_rate=arc_rate,
        semicircle_visible_rate=semi_rate,
        sparsity_warning=sparsity,
    )
