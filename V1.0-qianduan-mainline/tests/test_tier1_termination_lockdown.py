# -*- coding: utf-8 -*-
"""Stage1 termination rules B3 / D3 contract (updated for Tier2, 2026-06-01).

Tier1 froze B3/D3 as INERT (no producer persisted the data). Tier2 wired the
producers: the optimizer persists GP predicted_std into round_*_suggestion.json
(B3) and stage0 failures are read from round_*_stage0_result.json (D3). This test
now pins BOTH halves of the real contract:

  - WITHOUT persisted data, B3/D3 must still be ok=False (cannot false-trigger).
  - WITH persisted data over the window/threshold, B3/D3 must fire (ok=True).
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
_TE_PATH = (
    PROJECT_ROOT / "stage1_optimization" / "closed_loop" / "termination_evaluator.py"
)

_spec = importlib.util.spec_from_file_location("termination_evaluator_locktest", _TE_PATH)
_te = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_te)


def test_d3_inert_without_persisted_stage0_results():
    res = _te._eval_anomaly(
        trials=[], rounds=[], anomaly={"stage0_consecutive_fail": 1}, bounds={}
    )
    d3 = [r for r in res["rules"] if r["id"] == "stage0_consecutive_fail"]
    assert d3 and d3[0]["ok"] is False


def test_d3_fires_with_consecutive_stage0_failures():
    stage0_results = [
        {"validity_flags": ["stage0_failed"]},
        {"validity_flags": ["arrhenius_invalid"]},
    ]
    res = _te._eval_anomaly(
        trials=[], rounds=[], anomaly={"stage0_consecutive_fail": 2}, bounds={},
        stage0_results=stage0_results,
    )
    d3 = [r for r in res["rules"] if r["id"] == "stage0_consecutive_fail"][0]
    assert d3["ok"] is True
    assert d3["value"]["max_streak"] == 2
    assert res["triggered"] is True


def test_d3_resets_streak_on_success():
    stage0_results = [
        {"validity_flags": ["stage0_failed"]},
        {"validity_flags": []},  # success resets the streak
        {"validity_flags": ["stage0_failed"]},
    ]
    res = _te._eval_anomaly(
        trials=[], rounds=[], anomaly={"stage0_consecutive_fail": 2}, bounds={},
        stage0_results=stage0_results,
    )
    d3 = [r for r in res["rules"] if r["id"] == "stage0_consecutive_fail"][0]
    assert d3["ok"] is False  # max streak is only 1


def test_b3_inert_without_persisted_std():
    res = _te._eval_convergence(
        trials=[], rounds=[], conv={"predicted_std_max": 0.5}, bounds={}
    )
    b3 = [r for r in res["rules"] if r["id"] == "predicted_std"][0]
    assert b3["ok"] is False


def test_b3_fires_with_persisted_low_std():
    rounds = [
        {"bo_provenance": {"predicted_std": 0.10}},
        {"bo_provenance": {"predicted_std": 0.08}},
        {"bo_provenance": {"predicted_std": 0.05}},
    ]
    res = _te._eval_convergence(
        trials=[], rounds=rounds,
        conv={"predicted_std_max": 0.5, "recommendation_shift_window": 3}, bounds={},
    )
    b3 = [r for r in res["rules"] if r["id"] == "predicted_std"][0]
    assert b3["ok"] is True
