# -*- coding: utf-8 -*-
"""Tier3 (issue 11): MOBO / Pareto optimizer contract tests.

These cover the v2 multi-objective capability that is intentionally NOT wired
into the frozen single-objective closed loop. Pure Pareto utilities are tested
deterministically; the ParEGO suggester is tested against the real campaign
parameter space.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STAGE1_DIR = PROJECT_ROOT / "stage1_optimization"
if str(STAGE1_DIR) not in sys.path:
    sys.path.insert(0, str(STAGE1_DIR))

from optimizers.mobo_optimizer import (  # noqa: E402
    Objective,
    annotate_pareto,
    dominated_hypervolume,
    dominates,
    locked_v2_objectives,
    parego_scalarize,
    pareto_front_indices,
    score_v3,
)

CAMPAIGN = STAGE1_DIR / "campaigns" / "attapulgite_aice_campaign.json"


# -- pure Pareto utilities --------------------------------------------------- #
def _pts():
    # sigma_RT max, Ea_high min, ea_low_excess min
    return [
        {"sigma_RT": 1e-3, "Ea_high": 0.20, "ea_low_excess": 0.05},  # A
        {"sigma_RT": 2e-3, "Ea_high": 0.25, "ea_low_excess": 0.05},  # B (better sigma, worse Ea)
        {"sigma_RT": 5e-4, "Ea_high": 0.30, "ea_low_excess": 0.10},  # C (dominated by A)
    ]


def test_dominance_matches_locked_rule():
    objs = locked_v2_objectives()
    A, B, C = _pts()
    assert dominates(A, C, objs)  # A better on all three
    assert not dominates(A, B, objs)  # trade-off: neither dominates
    assert not dominates(B, A, objs)


def test_pareto_front_excludes_dominated():
    objs = locked_v2_objectives()
    front = pareto_front_indices(_pts(), objs)
    assert set(front) == {0, 1}  # A and B on front, C dominated


def test_score_v3_formula():
    p = {"sigma_RT": 1e-3, "Ea_high": 0.2, "ea_low_excess": 0.1}
    # log10(1e-3) - 1.0*0.2 - 0.2*0.1 = -3 - 0.2 - 0.02
    assert score_v3(p) == pytest.approx(-3.22)


def test_annotate_pareto_tags_and_scores():
    rows = annotate_pareto(_pts(), locked_v2_objectives())
    statuses = [r["pareto_status"] for r in rows]
    assert statuses == ["pareto", "pareto", "dominated"]
    assert all("score_v3" in r for r in rows)


def test_hypervolume_increases_when_front_improves():
    objs = locked_v2_objectives()
    base = _pts()
    hv_base = dominated_hypervolume(base, objs, seed=1)
    # add a clearly better point (higher sigma, lower Ea, lower penalty)
    improved = base + [{"sigma_RT": 5e-3, "Ea_high": 0.15, "ea_low_excess": 0.02}]
    hv_better = dominated_hypervolume(improved, objs, seed=1)
    assert hv_better >= hv_base


def test_parego_scalarize_shape_and_monotonicity():
    import numpy as np

    Y_min = np.array([[0.0, 0.0], [1.0, 1.0], [0.5, 0.5]])
    s = parego_scalarize(Y_min, np.array([0.5, 0.5]), rho=0.05)
    assert s.shape == (3,)
    # the all-min row should have the smallest scalar
    assert s.argmin() == 0


# -- ParEGO suggester integration ------------------------------------------- #
def _build_space_and_memory(tmp_path):
    from campaign_memory.memory_manager import MemoryManager
    from canonical_input.campaign_parser import CampaignConfig
    from canonical_input.design_space import ParameterSpace

    cfg = CampaignConfig(str(CAMPAIGN))
    space = ParameterSpace(cfg)
    mm = MemoryManager(str(tmp_path / "history.json"), campaign_name=cfg.campaign_name)
    # seed 6 distinct R/N trials, each with the 3 locked objectives
    seeds = [
        (0.30, 0.90, 1.0e-3, 0.22, 0.05),
        (0.35, 0.95, 1.5e-3, 0.20, 0.04),
        (0.40, 1.00, 2.0e-3, 0.25, 0.06),
        (0.45, 1.05, 1.2e-3, 0.18, 0.03),
        (0.50, 1.10, 9.0e-4, 0.30, 0.08),
        (0.55, 1.15, 2.5e-3, 0.21, 0.05),
    ]
    for r, n, sig, eah, eal in seeds:
        mm.add_trial(
            parameters={"R": r, "N": n},
            objectives={"sigma_RT": sig, "Ea_high": eah, "ea_low_excess": eal},
            metadata={"sample_id": f"S-{r}-{n}"},
        )
    return space, mm


def test_mobo_suggest_returns_valid_design_point(tmp_path):
    pytest.importorskip("skopt")
    space, mm = _build_space_and_memory(tmp_path)
    from optimizers.mobo_optimizer import MOBOOptimizer

    opt = MOBOOptimizer(space, mm, random_state=7, fixed_weights=[0.6, 0.3, 0.1])
    suggestion = opt.suggest_next()
    assert set(suggestion.keys()) == {"R", "N"}
    assert opt.validate_suggestion(suggestion)

    prov = opt.get_provenance()
    assert prov["method"] == "ParEGO_augmented_tchebycheff"
    assert prov["mode"] == "parego"
    assert prov["pareto_front_size"] >= 1
    assert prov["weights"] == [0.6, 0.3, 0.1]


def test_mobo_cold_start_when_history_too_small(tmp_path):
    pytest.importorskip("skopt")
    from campaign_memory.memory_manager import MemoryManager
    from canonical_input.campaign_parser import CampaignConfig
    from canonical_input.design_space import ParameterSpace
    from optimizers.mobo_optimizer import MOBOOptimizer

    cfg = CampaignConfig(str(CAMPAIGN))
    space = ParameterSpace(cfg)
    mm = MemoryManager(str(tmp_path / "h.json"), campaign_name=cfg.campaign_name)
    mm.add_trial(
        parameters={"R": 0.3, "N": 0.9},
        objectives={"sigma_RT": 1e-3, "Ea_high": 0.2, "ea_low_excess": 0.05},
        metadata={"sample_id": "only-one"},
    )
    opt = MOBOOptimizer(space, mm, random_state=3)
    suggestion = opt.suggest_next()
    assert set(suggestion.keys()) == {"R", "N"}
    assert opt.get_provenance()["mode"] == "cold_start"
