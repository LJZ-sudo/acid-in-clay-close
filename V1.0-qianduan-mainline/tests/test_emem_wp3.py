# -*- coding: utf-8 -*-
"""WP3 E-Mem:版本快照/写门、独立根去重、失效→BO 重建(+WP2 桥接)、压缩证书。"""
from __future__ import annotations

import sys
from pathlib import Path

MAINLINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MAINLINE / "stage1_optimization"))

from scientific_memory.claim_graph import ClaimGraph, NodeType  # noqa: E402
from scientific_memory.invalidation_engine import InvalidationEngine  # noqa: E402
from scientific_memory.snapshots import (  # noqa: E402
    take_snapshot, validate_write, ACCEPT, REBASE_REQUIRED, REJECTED,
)
from scientific_memory.root_dedup import (  # noqa: E402
    EvidenceSource, RootKind, count_independent_roots, dedup_sources,
)
from scientific_memory.bo_rebuilder import (  # noqa: E402
    Observation, build_committed_view, rebuild_after_invalidation, apply_revocation_impact,
)
from scientific_memory.compression import MemoryState, compress_and_verify  # noqa: E402


def _graph_with_evidence():
    g = ClaimGraph(":memory:")
    for e in ("E1", "E2", "E3"):
        g.add_node(e, NodeType.EVIDENCE)
    return g


# ---- WP3-a snapshots / 写门 ----

def test_write_gate_accepts_fresh():
    g = _graph_with_evidence()
    snap = take_snapshot(g)
    assert validate_write(g, snap, ["E1", "E2"]).decision == ACCEPT


def test_write_gate_rejects_invalid_evidence():
    g = _graph_with_evidence()
    snap = take_snapshot(g)
    InvalidationEngine(g).mark_invalid(["E1"], reason="kk_bug")
    assert validate_write(g, snap, ["E1"]).decision == REJECTED


def test_write_gate_requires_rebase_after_invalidation():
    g = _graph_with_evidence()
    snap = take_snapshot(g)                      # 快照在失效之前
    InvalidationEngine(g).mark_invalid(["E3"], reason="ece_leak")
    # 写入用的是 E2(仍有效),但图版本已前进 → 需 rebase
    assert validate_write(g, snap, ["E2"]).decision == REBASE_REQUIRED


# ---- WP3-b 根去重 ----

def test_multi_agent_same_doi_counts_one_root():
    srcs = [
        EvidenceSource(RootKind.LITERATURE_EXPERIMENT, doi="10.1/x", locator="fig2", cited_by_agent="A"),
        EvidenceSource(RootKind.LITERATURE_EXPERIMENT, doi="10.1/X", locator="FIG2", cited_by_agent="B"),
        EvidenceSource(RootKind.LITERATURE_EXPERIMENT, doi="10.1/x", locator="fig2", cited_by_agent="C"),
    ]
    assert count_independent_roots(srcs) == 1


def test_analysis_and_agent_statement_are_not_roots():
    srcs = [
        EvidenceSource(RootKind.INDEPENDENT_EXPERIMENT, physical_effect_id="P1", sample_batch_id="B1"),
        EvidenceSource(RootKind.ANALYSIS_RESULT, source_evidence_ids=["E1"], analysis_version="v2"),
        EvidenceSource(RootKind.AGENT_STATEMENT),
        EvidenceSource(RootKind.SUMMARY),
    ]
    d = dedup_sources(srcs)
    assert d["n_independent"] == 1 and d["n_non_root"] == 3


# ---- WP3-c 失效→BO 视图重建 ----

def _obs():
    return [
        Observation("E1", {"R": 0.186, "N": 1.029}, objective_value=-1.94, objective_id="combined_score"),
        Observation("E2", {"R": 0.50, "N": 1.20}, objective_value=-2.50, objective_id="combined_score"),
        Observation("E3", {"R": 0.28, "N": 0.96}, objective_value=-2.10, objective_id="combined_score"),
    ]


def test_committed_view_excludes_invalidated():
    g = _graph_with_evidence()
    prev = build_committed_view(g, _obs(), "combined_score", version=1)
    assert prev.best().evidence_id == "E1"
    InvalidationEngine(g).mark_invalid(["E1"], reason="kk_bug")
    new_view, report = rebuild_after_invalidation(g, _obs(), "combined_score", prev)
    assert "E1" in report.removed_evidence_ids
    assert report.best_changed is True
    assert new_view.best().evidence_id == "E3"     # E1 移除后次优
    assert report.n_after == 2


def test_revocation_bridge_rebuilds_and_marks_done():
    """WP2→WP3:Skill 撤销请求 → 失效其证据 → 重建视图 → 标 downstream_propagation_done。"""
    sys.path.insert(0, str(MAINLINE / "stage1_optimization"))
    from scientific_skills.revocation import RevocationImpactRequest
    g = _graph_with_evidence()
    prev = build_committed_view(g, _obs(), "combined_score", version=1)
    req = RevocationImpactRequest(skill_id="extract_transport_metrics", version="1.0.0",
                                  reason="rb_method_bug", affected_evidence_ids=["E1"])
    new_view, report = apply_revocation_impact(g, req, _obs(), "combined_score", prev,
                                               recommendations={"rec-7": ["E1"]})
    assert req.downstream_propagation_done is True
    assert "E1" in report.removed_evidence_ids
    assert "rec-7" in report.recommendations_affected
    assert new_view.best().evidence_id == "E3"


# ---- WP3-d 压缩证书 ----

def _src_state():
    return MemoryState(
        claim_levels={"C-break": "C3"}, conditions={"heating_branch", "batch_B3"},
        counterevidence={"E-counter-1"}, source_node_ids=["E1", "E2", "C-break"])


def test_faithful_compression_certifies():
    src = _src_state()
    summary = MemoryState(claim_levels={"C-break": "C3"},
                          conditions={"heating_branch", "batch_B3"},
                          counterevidence={"E-counter-1"}, source_node_ids=["E1", "C-break"])
    ok, cert = compress_and_verify(src, summary, raw_recovery_pointer="crate://run-1")
    assert ok and cert.ok


def test_compression_rejected_if_counterevidence_lost():
    src = _src_state()
    bad = MemoryState(claim_levels={"C-break": "C3"}, conditions={"heating_branch", "batch_B3"},
                      counterevidence=set(), source_node_ids=["E1"])   # 丢反证
    ok, cert = compress_and_verify(src, bad)
    assert not ok
    assert any("COUNTEREVIDENCE_LOST" in r for r in cert.reasons)


def test_compression_rejected_if_claim_amplified():
    src = _src_state()
    bad = MemoryState(claim_levels={"C-break": "C5"},   # 把 C3 吹成 C5
                      conditions={"heating_branch", "batch_B3"},
                      counterevidence={"E-counter-1"}, source_node_ids=["E1"])
    ok, cert = compress_and_verify(src, bad)
    assert not ok
    assert any("CLAIM_LEVEL_AMPLIFIED" in r for r in cert.reasons)


def test_compression_rejected_if_action_flips():
    src = _src_state()
    summary = MemoryState(claim_levels={"C-break": "C3"}, conditions={"heating_branch", "batch_B3"},
                          counterevidence={"E-counter-1"}, source_node_ids=["E1"])
    # decision_probe:源含 E2 → 动作 'X';摘要无 E2 → 动作 'Y' → 动作翻转应拒
    probe = lambda st: "X" if "E2" in st.source_node_ids else "Y"
    ok, cert = compress_and_verify(src, summary, decision_probe=probe)
    assert not ok
    assert any("ACTION_DIVERGENCE" in r for r in cert.reasons)
