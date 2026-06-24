# -*- coding: utf-8 -*-
"""M1-3 契约测试:flag_sequence_anomalies(标记不删点)。

锁定:
  1. 输出点数 == QA 合格输入点数(绝不删点)。
  2. 降温链上 Rb 反常下降被标 sequence_anomaly=True,但仍 included_in_primary_fit。
  3. 与已废弃的 extract_valid_arrhenius_series 对比:后者会删点(点数更少)。
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ALGO_DIR = PROJECT_ROOT / "stage0_measurement"
if str(ALGO_DIR) not in sys.path:
    sys.path.insert(0, str(ALGO_DIR))

from modules.analysis.eis_pipeline import (  # noqa: E402
    flag_sequence_anomalies, extract_valid_arrhenius_series,
)


def _records():
    # 沿降温(温度从高到低)Rb 整体上升,但在 253K 处插入一个反常下降点
    return [
        {"success": True, "temperature_K": 298.0, "conductivity_s_per_cm": 1e-2, "rb_ohm": 10.0},
        {"success": True, "temperature_K": 283.0, "conductivity_s_per_cm": 8e-3, "rb_ohm": 12.0},
        {"success": True, "temperature_K": 273.0, "conductivity_s_per_cm": 6e-3, "rb_ohm": 16.0},
        {"success": True, "temperature_K": 253.0, "conductivity_s_per_cm": 9e-3, "rb_ohm": 11.0},  # 反常↓
        {"success": True, "temperature_K": 233.0, "conductivity_s_per_cm": 2e-3, "rb_ohm": 40.0},
    ]


def test_keeps_all_qc_valid_points():
    recs = _records()
    out = flag_sequence_anomalies(recs)
    assert out["n_total"] == 5            # 5 个 QA 合格点,一个不少
    assert all(p["included_in_primary_fit"] for p in out["points"])


def test_flags_anomaly_without_deleting():
    out = flag_sequence_anomalies(_records())
    anomalies = [p for p in out["points"] if p["sequence_anomaly"]]
    assert out["n_anomalies"] == 1
    assert anomalies[0]["temperature_K"] == 253.0
    assert anomalies[0]["anomaly_reason"] == "rb_decreased_on_cooling"
    # 被标异常但仍参与主拟合(不删)
    assert anomalies[0]["included_in_primary_fit"] is True


def test_superseded_filter_deletes_more():
    """对照:废弃的 extract_valid_arrhenius_series 会删掉反常点,点数更少。"""
    recs = _records()
    temps, sigmas = extract_valid_arrhenius_series(recs)
    flagged = flag_sequence_anomalies(recs)
    assert len(temps) < flagged["n_total"]   # 旧逻辑删点 → 更少
    assert flagged["n_total"] == 5


def test_qc_invalid_excluded_from_count():
    recs = _records() + [
        {"success": False, "temperature_K": 200.0, "conductivity_s_per_cm": 1e-3, "rb_ohm": 50.0},
        {"success": True, "temperature_K": 210.0, "conductivity_s_per_cm": 5.0, "rb_ohm": 0.1},  # σ>1 & Rb<0.5
    ]
    out = flag_sequence_anomalies(recs)
    # success=False 被丢;物理越界点 raw_qc_valid=False(但仍在 points 里,只是不算合格)
    qc_valid = [p for p in out["points"] if p["raw_qc_valid"]]
    assert len(qc_valid) == 5
