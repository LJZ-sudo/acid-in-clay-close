# -*- coding: utf-8 -*-
"""Tier2 (issue 10) contract tests for Stage0 result bundle.

Locks in two upgrades to ``result_bundle.py``:
  1. Numerical Kramers-Kronig residuals (mu_median + aux stats) are propagated
     into each EISPoint when the source measurement carries them.
  2. ``rb_confidence`` is always paired with ``rb_confidence_basis`` so the
     arc-fit-R^2 proxy is no longer mistakable for a calibrated probability.

Also asserts honest backward-compat: legacy measurements (only a ``kk_warning``
bool) still yield ``kk_residual=None`` + an explanatory flag/limitation, with no
fabricated numbers.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
IO_UTILS_DIR = PROJECT_ROOT / "stage0_measurement" / "modules" / "io_utils"
if str(IO_UTILS_DIR) not in sys.path:
    sys.path.insert(0, str(IO_UTILS_DIR))

import result_bundle as rb  # noqa: E402


def _write_scan(sample_dir: Path, scan_name: str, measurements: list) -> None:
    scan = sample_dir / scan_name
    scan.mkdir(parents=True, exist_ok=True)
    (scan / "aggregated_results.json").write_text(
        json.dumps({"measurements": measurements}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _numeric_measurement(temp_c: float) -> dict:
    return {
        "temperature_C": temp_c,
        "temperature_K": temp_c + 273.15,
        "status": "OK",
        "kk_warning": False,
        # numeric KK residuals as emitted by the upgraded offline pipeline
        "kk_mu_median": 0.0123,
        "kk_mu_rmse": 0.0211,
        "kk_mu_max": 0.0890,
        "kk_score": 0.84,
        "kk_passed": True,
        "kk_threshold": 0.05,
        "kk_method": "linKK_impedance",
        "rb_ohm": 1234.5,
        "conductivity_S_per_cm": 1.0e-4,
        "rb_method": "arc_fit",
        "fit_quality": 0.991,
        "success": True,
    }


def _legacy_measurement(temp_c: float) -> dict:
    # Pre-Tier2 record: only a bool, no numerical residual.
    return {
        "temperature_C": temp_c,
        "temperature_K": temp_c + 273.15,
        "status": "OK",
        "kk_warning": True,
        "rb_ohm": 2222.0,
        "conductivity_S_per_cm": 5.0e-5,
        "rb_method": "arc_fit",
        "fit_quality": 0.95,
        "success": True,
    }


def test_numeric_kk_residual_is_propagated(tmp_path):
    sample = tmp_path / "S8-001"
    _write_scan(sample, "300-120K 3K-min", [_numeric_measurement(-10.0), _numeric_measurement(-20.0)])

    bundle = rb.build_bundle_for_sample(sample, "S8-001")

    assert len(bundle.eis_points) == 2
    pt = bundle.eis_points[0]
    assert pt.kk_residual == pytest.approx(0.0123)
    assert pt.kk_residual_metric == "mu_median_linKK"
    assert pt.kk_mu_rmse == pytest.approx(0.0211)
    assert pt.kk_score == pytest.approx(0.84)
    assert pt.kk_passed is True
    assert pt.kk_threshold == pytest.approx(0.05)

    # rb_confidence is interpretable: value + explicit basis label.
    assert pt.rb_confidence == pytest.approx(0.991)
    assert pt.rb_confidence_basis == "arc_fit_r2"
    assert "rb_confidence_is_arc_fit_r2_proxy" in pt.quality_flags

    # No "kk_residual is None" limitation when numeric residuals exist.
    assert not any("kk_residual is None for all points" in lim for lim in bundle.limitations)
    # But the rb proxy caveat IS present and quantified.
    assert any("arc-fit R^2 proxy" in lim for lim in bundle.limitations)


def test_legacy_record_stays_honest_without_fabrication(tmp_path):
    sample = tmp_path / "S8-002"
    _write_scan(sample, "300-120K 3K-min", [_legacy_measurement(-10.0)])

    bundle = rb.build_bundle_for_sample(sample, "S8-002")

    pt = bundle.eis_points[0]
    # No numerical residual is invented for legacy records.
    assert pt.kk_residual is None
    assert pt.kk_residual_metric is None
    assert pt.kk_score is None
    assert "kk_residual_unavailable_legacy_record" in pt.quality_flags
    assert "kk_warning_set_by_legacy_pipeline" in pt.quality_flags
    assert any("predate Tier2 numerical" in lim for lim in bundle.limitations)


def test_mixed_records_report_partial_coverage(tmp_path):
    sample = tmp_path / "S8-003"
    _write_scan(
        sample,
        "300-120K 3K-min",
        [_numeric_measurement(-10.0), _legacy_measurement(-20.0)],
    )

    bundle = rb.build_bundle_for_sample(sample, "S8-003")

    numeric = [p for p in bundle.eis_points if p.kk_residual is not None]
    legacy = [p for p in bundle.eis_points if p.kk_residual is None]
    assert len(numeric) == 1
    assert len(legacy) == 1
    assert any("1/2 points" in lim for lim in bundle.limitations)
