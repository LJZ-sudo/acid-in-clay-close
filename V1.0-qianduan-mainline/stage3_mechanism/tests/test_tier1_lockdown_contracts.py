"""Tier1 lock-down contracts (2026-06-01).

These tests PIN documented Tier1 "known limitations / stubs" so they cannot
drift silently. They are NOT asserting that the behavior is correct/desirable —
they assert that the current, intentionally-frozen behavior is unchanged. When
Tier2/Tier3 wires up the real behavior, the matching assertion here is expected
to be updated deliberately (which is the point: it forces a conscious change).

Covered:
  - ``prospective_status_score`` default path (no S13 binding) is still 0.0, so the
    live S10 pass + frozen ranking are unchanged. (Tier2 wired the non-default path.)
  - S09 candidate generation is deterministic-from-D4 by default, over a fixed
    family/instance set (so "Top-list stability" has a deterministic component).
"""
from __future__ import annotations

import inspect
import os


def _toy_inputs():
    instance_dumps = [
        {"instance_id": "I1", "element_evidence": []},
        {"instance_id": "I4", "element_evidence": []},
    ]
    ranking = {
        "ranked_candidates": [
            {"instance_id": "I1", "instance_name": "cand-1", "total_score": 0.5},
            {"instance_id": "I4", "instance_name": "cand-4", "total_score": 0.5},
        ]
    }
    return instance_dumps, ranking


def test_prospective_status_score_defaults_to_zero_without_binding(tmp_path):
    # Tier2: with NO validation binding supplied (the live S10 path), every
    # candidate must still score 0.0 — this is what keeps the frozen ranking intact.
    from s8_stage3.scoring.candidate_audit import audit_candidates

    instance_dumps, ranking = _toy_inputs()
    rows, _ = audit_candidates(instance_dumps, ranking, tmp_path)
    assert rows, "expected audit rows"
    assert all(r["prospective_status_score"] == 0.0 for r in rows)
    assert all(r["has_prospective_validation"] is False for r in rows)


def test_prospective_status_score_reads_s13_binding(tmp_path):
    # Tier2: when the S13 binding is fed back in, only instances with a BOUND
    # prospective record get 1.0; the rest stay 0.0. No fabrication.
    from s8_stage3.scoring.candidate_audit import audit_candidates

    instance_dumps, ranking = _toy_inputs()
    validation_binding = {
        "records": [
            {"instance_id": "I4", "validation_timing": "prospective"},
            {"instance_id": "I9", "validation_timing": "retrospective"},
        ]
    }
    rows, _ = audit_candidates(
        instance_dumps, ranking, tmp_path, validation_binding=validation_binding
    )
    by = {r["instance_id"]: r for r in rows}
    assert by["I4"]["prospective_status_score"] == 1.0
    assert by["I4"]["has_prospective_validation"] is True
    assert by["I1"]["prospective_status_score"] == 0.0
    assert by["I1"]["has_prospective_validation"] is False


def test_s09_deterministic_from_d4_default_is_true():
    # When the override env var is unset, the default must remain True.
    os.environ.pop("STAGE3_S09_DETERMINISTIC_FROM_D4", None)
    from s8_stage3.config.settings import Stage3Settings

    assert Stage3Settings().s09_deterministic_from_d4 is True


def test_s09_deterministic_candidate_set_is_fixed():
    from s8_stage3.agents import s09_candidate_family_generator as s09

    src = inspect.getsource(s09._build_d4_deterministic_output)
    for fid in ("F1", "F2", "F3"):
        assert f'family_id="{fid}"' in src, f"missing fixed family {fid}"
    for iid in ("I1", "I2", "I3", "I4", "I5"):
        assert f'instance_id="{iid}"' in src, f"missing fixed instance {iid}"
