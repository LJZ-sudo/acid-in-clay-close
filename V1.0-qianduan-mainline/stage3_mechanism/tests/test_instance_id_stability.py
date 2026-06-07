"""Tier2: instance-id / candidate-id drift stabilization (S12 registry).

instance_id (I1..I5) is already deterministic (S09 from D4). The drift is in
``run_id`` / ``candidate_id``, which the legacy path seeds from output_dir + wall
clock, so a re-run into a NEW dir produces different candidate_ids and no longer
aligns with the frozen registry / S13 binding. These tests pin the opt-in
content-addressed run_id: reproducible across dirs/time, while the legacy default
still varies (so the frozen registry/run_id is untouched).
"""
from __future__ import annotations

from types import SimpleNamespace

from s8_stage3.agents.s12_prospective_registry import run_s12
from s8_stage3.contracts.material import MaterialInstanceSet
from s8_stage3.contracts.ranking import RankedCandidate, RankingResult


def _ranking() -> RankingResult:
    return RankingResult(
        ranked_candidates=[
            RankedCandidate(rank=1, instance_id="I1", instance_name="cand-1", total_score=0.8),
            RankedCandidate(rank=2, instance_id="I4", instance_name="cand-4", total_score=0.7),
        ]
    )


def _settings():
    return SimpleNamespace(discovery_mode="broad_literature_pool_selection")


def test_stable_run_id_is_reproducible_across_dirs(tmp_path):
    d1 = tmp_path / "runA"
    d2 = tmp_path / "runB"
    r1 = run_s12(_ranking(), MaterialInstanceSet(instances=[]), d1, _settings(), stable_run_id=True)
    r2 = run_s12(_ranking(), MaterialInstanceSet(instances=[]), d2, _settings(), stable_run_id=True)

    assert r1.run_id == r2.run_id, "stable run_id must not depend on output dir/time"
    assert [c.candidate_id for c in r1.candidates] == [c.candidate_id for c in r2.candidates]
    # instance_ids are stable regardless of mode.
    assert [c.instance_id for c in r1.candidates] == ["I1", "I4"]


def test_legacy_run_id_varies_across_dirs(tmp_path):
    d1 = tmp_path / "legacyA"
    d2 = tmp_path / "legacyB"
    r1 = run_s12(_ranking(), MaterialInstanceSet(instances=[]), d1, _settings(), stable_run_id=False)
    r2 = run_s12(_ranking(), MaterialInstanceSet(instances=[]), d2, _settings(), stable_run_id=False)

    # The legacy default seeds on resolved path (+ time) -> different ids per dir.
    assert r1.run_id != r2.run_id
