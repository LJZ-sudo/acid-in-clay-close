# -*- coding: utf-8 -*-
"""C³-Harness（ESAS-OS 2.0 / §10.5）契约测试。

验收(对齐 §10.6 C³ 行 + §10.7 单调不变量):
  - 动作组合可复算(同输入同输出);
  - 注入"已收敛但仍探索 / 未收敛却想停"场景 → C³ 比 legacy **更少错误提前停止**;
  - **C³ 的"停"单调 ⊆ legacy 的"停"**(永不更早停 → 永不与 legacy 矛盾);
  - 预算耗尽是硬门:C³ 不得推迟;
  - 收敛证书字段完整、与 legacy verdict 不矛盾。
"""
from __future__ import annotations

import sys
from pathlib import Path

MAINLINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MAINLINE / "stage1_optimization"))

from scientific_convergence import (  # noqa: E402
    Action, ConvergenceState, shadow_convergence, certify, build_state_from_termination, bench,
)
from scientific_convergence.policy import recommend, score_actions  # noqa: E402


def _term(verdict="continue", triggered=None, budget_exhausted=False):
    return {
        "verdict": verdict, "triggered_by": triggered or [],
        "convergence": {"triggered": "convergence" in (triggered or [])},
        "anomaly": {"triggered": "anomaly" in (triggered or [])},
        "budget": ({"triggered": True, "status": "exhausted"} if budget_exhausted
                   else {"triggered": False}),
        "progress": {},
    }


# ---- 状态投影 ---------------------------------------------------------------

def test_state_projection_normalizes():
    st = build_state_from_termination(
        _term("loop_can_end", ["convergence"]),
        metrological_uncertainty_dex=0.30, metro_fail_dex=0.30,
        repro_replicates_have=0, repro_replicates_required=3, claim_stability=0.5)
    assert st.metrological_uncertainty == 1.0
    assert st.reproducibility_unmet == 1.0
    assert abs(st.claim_instability - 0.5) < 1e-9
    assert st.legacy_allows_end() is True


# ---- 单调不变量:C³ 停 ⊆ legacy 停 -----------------------------------------

def test_c3_never_stops_earlier_than_legacy():
    # legacy 还要继续,但状态"看起来可停"(全 0 不确定度)→ C³ 也不得 STOP 居首
    st = ConvergenceState(performance_gap=0.0, metrological_uncertainty=0.0,
                          reproducibility_unmet=0.0, claim_instability=0.0,
                          legacy_verdict="continue", legacy_triggered_by=[])
    cert = certify(st)
    assert cert.legacy_stop is False
    assert cert.c3_stop is False
    assert cert.consistent_with_legacy is True
    assert cert.recommended_action != Action.STOP


def test_c3_defers_stop_when_evidence_insufficient():
    cert = shadow_convergence(
        _term("loop_can_end", ["convergence"]),
        metrological_uncertainty_dex=0.28, repro_replicates_have=1,
        repro_replicates_required=3, claim_stability=0.7,
        rb_act_active_requests=["EXTEND_FREQ_HIGH"])
    assert cert.legacy_stop is True
    assert cert.c3_stop is False
    assert cert.delta_vs_legacy == "c3_defers_stop"
    assert cert.recommended_action in (Action.REMEASURE, Action.REPLICATE, Action.EXTEND_FREQ)
    assert cert.consistent_with_legacy is True


def test_c3_agrees_stop_when_resolved():
    cert = shadow_convergence(
        _term("loop_can_end", ["convergence", "performance_target"]),
        metrological_uncertainty_dex=0.04, repro_replicates_have=3,
        repro_replicates_required=3, claim_stability=1.0)
    assert cert.c3_stop is True
    assert cert.delta_vs_legacy == "agree_stop"
    assert cert.recommended_action == Action.STOP


def test_budget_exhausted_is_hard_stop():
    cert = shadow_convergence(
        _term("loop_must_end_budget", ["budget"], budget_exhausted=True),
        metrological_uncertainty_dex=0.25, repro_replicates_have=1)
    assert cert.c3_stop is True            # 硬门:不能推迟
    assert cert.recommended_action == Action.STOP


# ---- 动作语义 ---------------------------------------------------------------

def test_anomaly_prefers_diagnose():
    st = build_state_from_termination(_term("continue", ["anomaly"]),
                                      metrological_uncertainty_dex=0.05,
                                      repro_replicates_have=3)
    port = recommend(st)
    assert port[0].action == Action.DIAGNOSE


def test_high_repro_unmet_prefers_replicate_over_remeasure():
    # 计量已可靠但只有 1 片 → REPLICATE 优于 REMEASURE
    st = ConvergenceState(metrological_uncertainty=0.0, reproducibility_unmet=1.0,
                          claim_instability=0.0, legacy_verdict="loop_can_end")
    port = recommend(st)
    actions = [u.action for u in port]
    assert actions[0] == Action.REPLICATE
    assert actions.index(Action.REPLICATE) < actions.index(Action.REMEASURE)


def test_portfolio_is_deterministic_reproducible():
    st = build_state_from_termination(_term("loop_can_end", ["convergence"]),
                                      metrological_uncertainty_dex=0.2,
                                      repro_replicates_have=2)
    a = [u.to_dict() for u in score_actions(st)]
    b = [u.to_dict() for u in score_actions(st)]
    assert a == b


# ---- 证书字段完整 -----------------------------------------------------------

def test_certificate_fields_complete():
    cert = shadow_convergence(_term("loop_can_end", ["convergence"]),
                              metrological_uncertainty_dex=0.28, repro_replicates_have=1)
    d = cert.to_dict()
    for key in ("certificate_id", "state", "portfolio", "recommended_action",
                "c3_stop", "legacy_stop", "consistent_with_legacy", "delta_vs_legacy", "reasons"):
        assert key in d
    assert len(d["portfolio"]) == len(Action.ALL)
    assert d["state"]["unresolved"] >= 0.0


# ---- benchmark --------------------------------------------------------------

def test_convergence_bench_c3_fewer_wrong_stops():
    res = bench.run()
    assert res["ok"] is True, res
    assert res["c3_wrong_stops"] < res["legacy_wrong_stops"]
    assert res["consistent_all"] is True
