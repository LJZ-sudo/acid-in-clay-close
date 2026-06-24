# -*- coding: utf-8 -*-
"""M1-6 / G7 契约测试:目标函数注册表(隔离训练 vs 审计目标)。"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STAGE1_DIR = PROJECT_ROOT / "stage1_optimization"
if str(STAGE1_DIR) not in sys.path:
    sys.path.insert(0, str(STAGE1_DIR))

from objectives import registry as R  # noqa: E402


class _FakeMM:
    def __init__(self, trials):
        self._trials = trials

    def get_history(self):
        return self._trials

    def get_best_trial(self, objective_name, goal="maximize"):
        ts = [t for t in self._trials if objective_name in t["objectives"]]
        if not ts:
            return None
        key = lambda t: t["objectives"][objective_name]  # noqa: E731
        return max(ts, key=key) if goal == "maximize" else min(ts, key=key)


def test_two_objectives_distinct_hashes():
    reg = R.load_registry()
    assert set(reg.keys()) == {"attapulgite_combined_score_v1", "audit_score_v3"}
    assert reg["attapulgite_combined_score_v1"].role == "optimization_primary"
    assert reg["audit_score_v3"].role == "diagnostic_only"
    # 两式哈希必须不同(口径隔离的根)
    assert reg["attapulgite_combined_score_v1"].sha256 != reg["audit_score_v3"].sha256
    # trial 键名分别为 combined_score / score_v3
    assert reg["attapulgite_combined_score_v1"].trial_objective_key == "combined_score"
    assert reg["audit_score_v3"].trial_objective_key == "score_v3"


def test_role_binding_training_is_combined_score():
    assert R.objective_for_role("training").id == "attapulgite_combined_score_v1"
    assert R.objective_for_role("pareto_annotation").id == "audit_score_v3"


def test_stamp_metadata_shape():
    stamp = R.stamp_metadata("attapulgite_combined_score_v1")
    assert stamp["objective_definition_id"] == "attapulgite_combined_score_v1"
    assert stamp["objective_role"] == "optimization_primary"
    assert len(stamp["objective_definition_sha256"]) == 64


def test_get_best_trial_by_definition_uses_correct_key():
    trials = [
        {"trial_id": 1, "objectives": {"combined_score": -1.941}, "metadata": {}},
        {"trial_id": 2, "objectives": {"combined_score": -3.20}, "metadata": {}},
        {"trial_id": 3, "objectives": {"combined_score": -2.10}, "metadata": {}},
    ]
    mm = _FakeMM(trials)
    best = R.get_best_trial_by_definition(mm, "attapulgite_combined_score_v1")
    assert best["trial_id"] == 1  # 最大 combined_score


def test_consistency_lenient_backfills_unstamped():
    trials = [{"trial_id": i, "objectives": {"combined_score": -2.0}, "metadata": {}} for i in range(3)]
    rep = R.assert_trial_objective_consistency(trials, "attapulgite_combined_score_v1")
    assert rep["n_backfilled"] == 3 and rep["n_mismatch"] == 0


def test_consistency_strict_raises_on_unstamped():
    trials = [{"trial_id": 1, "objectives": {"combined_score": -2.0}, "metadata": {}}]
    with pytest.raises(ValueError):
        R.assert_trial_objective_consistency(trials, "attapulgite_combined_score_v1", require_stamp=True)


def test_consistency_detects_mismatch():
    bad = R.stamp_metadata("audit_score_v3")  # 串了审计目标的章
    trials = [{"trial_id": 1, "objectives": {"combined_score": -2.0}, "metadata": bad}]
    rep = R.assert_trial_objective_consistency(trials, "attapulgite_combined_score_v1")
    assert rep["n_mismatch"] == 1


# --- P0-1: campaign 口径漂移守卫 ---------------------------------------------

def test_campaign_matches_role_passes_for_real_campaign():
    # 真实 campaign 是 combined_score / maximize,与注册表 training 角色一致
    stamp = R.assert_campaign_matches_role("combined_score", "maximize", role="training")
    assert stamp["objective_definition_id"] == "attapulgite_combined_score_v1"
    assert stamp["trial_objective_key"] == "combined_score"
    assert stamp["direction"] == "maximize"


def test_campaign_matches_role_raises_on_key_drift():
    with pytest.raises(ValueError):
        R.assert_campaign_matches_role("score_v3", "maximize", role="training")


def test_campaign_matches_role_raises_on_goal_drift():
    with pytest.raises(ValueError):
        R.assert_campaign_matches_role("combined_score", "minimize", role="training")
