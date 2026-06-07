# -*- coding: utf-8 -*-
"""Tier2 (issues 7 & 8): Stage2 plot field availability.

issue 8 (Meyer-Neldel): model_competitor must ALWAYS produce slope/intercept/r2
so the MN figure is renderable, even below the strong-evidence R² threshold or
when slope<=0 (no positive compensation).

issue 7 (EIS alignment): Stage2Agent must build a temperature axis + feature
series from the S8 morphology columns so the existing viz_engine.plot_eis_alignment
can actually be called (previously it bailed claiming insufficient data).
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STAGE2_DIR = PROJECT_ROOT / "stage2_statistics"
if str(STAGE2_DIR) not in sys.path:
    sys.path.insert(0, str(STAGE2_DIR))

from specialists.model_competitor import ModelCompetitor  # noqa: E402
from main_agent import Stage2Agent  # noqa: E402


def _mn_metrics(evidences):
    for ev in evidences:
        if "meyer_neldel_diagnostic" in ev.tags:
            return ev.support_metrics
    return None


def test_mn_diagnostic_emitted_below_threshold():
    # Positive but weak correlation (r2 < 0.9): no strong evidence, but the
    # diagnostic with slope/intercept must still appear.
    rng = np.random.default_rng(0)
    ea = np.linspace(0.1, 0.6, 8)
    ln_sigma0 = 2.0 * ea + rng.normal(0, 0.5, size=ea.size)  # noisy -> low r2
    df = pd.DataFrame({"Ea": ea, "ln_sigma0": ln_sigma0})

    ev = ModelCompetitor()._analyze_meyer_neldel(df)
    diag = _mn_metrics(ev)
    assert diag is not None, "diagnostic MN evidence must always be emitted"
    for k in ("slope", "intercept", "r_squared", "n_points", "slope_positive"):
        assert k in diag


def test_mn_diagnostic_handles_negative_slope():
    ea = np.linspace(0.1, 0.6, 8)
    ln_sigma0 = -3.0 * ea + 1.0  # negative slope -> no positive compensation
    df = pd.DataFrame({"Ea": ea, "ln_sigma0": ln_sigma0})

    diag = _mn_metrics(ModelCompetitor()._analyze_meyer_neldel(df))
    assert diag is not None
    assert diag["slope_positive"] is False
    assert diag["E_MN_eV"] is None  # E_MN undefined for slope<=0, not fabricated


def test_build_eis_alignment_series_from_s8_columns():
    df = pd.DataFrame({
        "T_K": [200, 210, 220, 230, 240],
        "arc_diameter_ohm": [10.0, 12.0, 9.0, 14.0, 11.0],
        "characteristic_frequency": [1e3, 9e2, 1.1e3, 8e2, 1.2e3],
    })
    # _build_eis_alignment_series only uses pandas + its args (no self state).
    T_axis, features = Stage2Agent._build_eis_alignment_series(SimpleNamespace(), df)
    assert T_axis is not None
    assert list(T_axis) == [200.0, 210.0, 220.0, 230.0, 240.0]
    assert features  # at least one feature series
    assert all(len(arr) == len(T_axis) for arr in features.values())


def test_build_eis_alignment_series_without_columns_returns_empty():
    df = pd.DataFrame({"T_K": [200, 210], "unrelated": [1, 2]})
    T_axis, features = Stage2Agent._build_eis_alignment_series(SimpleNamespace(), df)
    assert T_axis is None and features == {}
