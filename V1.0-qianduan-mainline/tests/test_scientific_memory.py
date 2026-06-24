# -*- coding: utf-8 -*-
"""M5-B 测试:证据超图 + 四值逻辑 + 失效传播 + Demo B 验收。"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
STAGE1 = PROJECT_ROOT / "stage1_optimization"
if str(STAGE1) not in sys.path:
    sys.path.insert(0, str(STAGE1))

from scientific_memory.claim_graph import ClaimGraph, NodeType, ClaimStatus  # noqa: E402
from scientific_memory.invalidation_engine import InvalidationEngine  # noqa: E402


def _g():
    return ClaimGraph(":memory:")


def test_four_valued_logic_all_states():
    g = _g()
    for ev in ["e_s", "e_r"]:
        g.add_node(ev, NodeType.EVIDENCE, ev)
    # UNKNOWN: 无支持无反驳
    g.add_node("c_unknown", NodeType.CLAIM)
    # SUPPORTED
    g.add_node("c_sup", NodeType.CLAIM); g.add_support(["e_s"], "c_sup", "s1")
    # REFUTED
    g.add_node("c_ref", NodeType.CLAIM); g.add_refute(["e_r"], "c_ref", "r1")
    # CONTESTED:正反并存
    g.add_node("c_con", NodeType.CLAIM)
    g.add_support(["e_s"], "c_con", "s1"); g.add_refute(["e_r"], "c_con", "r1")
    g.recompute_all()
    assert g.get_status("c_unknown") == ClaimStatus.UNKNOWN
    assert g.get_status("c_sup") == ClaimStatus.SUPPORTED
    assert g.get_status("c_ref") == ClaimStatus.REFUTED
    assert g.get_status("c_con") == ClaimStatus.CONTESTED


def test_minimal_support_set_all_valid_required():
    """支持集需全部证据有效才算支持(一条失效则该集失效)。"""
    g = _g()
    g.add_node("e1", NodeType.EVIDENCE); g.add_node("e2", NodeType.EVIDENCE)
    g.add_node("c", NodeType.CLAIM)
    g.add_support(["e1", "e2"], "c", "s1")  # 需要 e1 且 e2
    g.recompute_all()
    assert g.get_status("c") == ClaimStatus.SUPPORTED
    InvalidationEngine(g).mark_invalid(["e2"], "drop one member")
    assert g.get_status("c") == ClaimStatus.UNKNOWN  # 支持集塌


def test_invalidation_downgrades_sole_support():
    g = _g()
    g.add_node("e", NodeType.EVIDENCE); g.add_node("c", NodeType.CLAIM)
    g.add_support(["e"], "c", "s1")
    g.recompute_all()
    assert g.get_status("c") == ClaimStatus.SUPPORTED
    InvalidationEngine(g).mark_invalid(["e"], "bug")
    assert g.get_status("c") == ClaimStatus.UNKNOWN


def test_independent_support_preservation():
    """两个独立支持集,失效一个 → 主张仍 SUPPORTED。"""
    g = _g()
    g.add_node("eA", NodeType.EVIDENCE); g.add_node("eB", NodeType.EVIDENCE)
    g.add_node("c", NodeType.CLAIM)
    g.add_support(["eA"], "c", "sA"); g.add_support(["eB"], "c", "sB")
    g.recompute_all()
    rep = InvalidationEngine(g).mark_invalid(["eA"], "drop A")
    assert g.get_status("c") == ClaimStatus.SUPPORTED
    assert rep.metrics["independent_support_preservation_rate"] == 1.0


def test_no_leak_invalidated_not_retrieved():
    g = _g()
    g.add_node("e", NodeType.EVIDENCE)
    assert "e" in g.valid_evidence()
    InvalidationEngine(g).mark_invalid(["e"], "x")
    assert "e" not in g.valid_evidence()


def test_depends_on_marks_affected():
    g = _g()
    g.add_node("e", NodeType.EVIDENCE)
    g.add_node("c_base", NodeType.CLAIM); g.add_support(["e"], "c_base", "s1")
    g.add_node("c_dec", NodeType.CLAIM); g.add_dependency("c_dec", "c_base")
    g.recompute_all()
    InvalidationEngine(g).mark_invalid(["e"], "bug")
    assert g.is_affected("c_dec") is True


def test_no_last_writer_wins_contested_preserved():
    """正反并存必须保留 CONTESTED,不能被某一方覆盖。"""
    g = _g()
    g.add_node("es", NodeType.EVIDENCE); g.add_node("er", NodeType.EVIDENCE)
    g.add_node("c", NodeType.CLAIM)
    g.add_support(["es"], "c", "s1"); g.add_refute(["er"], "c", "r1")
    g.recompute_all()
    assert g.get_status("c") == ClaimStatus.CONTESTED


def test_demo_b_acceptance_passes():
    from scientific_memory import demo_b
    res = demo_b.run()
    assert res["acceptance_pass"] is True
    m = res["acceptance"]
    assert m["invalidated_evidence_retrieval_rate"] == 0.0
    assert m["downstream_claim_recomputation_rate"] == 1.0
    assert m["independent_support_preservation_rate"] == 1.0
    nc = res["narrative_checks"]
    assert nc["C_kk_fail_after"] == "REFUTED"
    assert nc["C_ece_005_after"] == "UNKNOWN"
    assert nc["C_transition_survives_via_independent_support"] is True
