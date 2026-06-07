"""Tier3 (issue 12): Stage3 agentic layer — memory / heartbeat / critic.

These modules are standalone v2 capabilities (not wired into the frozen linear
orchestrator). Tests pin their core contracts deterministically.
"""
from __future__ import annotations

from s8_stage3.agentic import (
    Critic,
    EpisodicMemory,
    Heartbeat,
    eis_overclaim_rule,
    nonempty_rule,
    overclaim_rule,
)


# -- memory ------------------------------------------------------------------ #
def test_memory_records_recall_and_ordering():
    mem = EpisodicMemory()
    mem.record("s04", "hypothesis", {"h": 1}, tags=["draft"])
    mem.record("s06", "verdict", "supported")
    mem.record("s04", "hypothesis", {"h": 2}, tags=["revised"])

    s04 = mem.recall(step="s04")
    assert [r.seq for r in s04] == [0, 2]  # monotonic ordering, append-only
    assert mem.latest(step="s04", key="hypothesis").value == {"h": 2}
    assert mem.recall(tag="revised")[0].value == {"h": 2}
    assert mem.summary()["by_step"] == {"s04": 2, "s06": 1}


def test_memory_persist_and_reload(tmp_path):
    path = tmp_path / "mem.json"
    mem = EpisodicMemory(path)
    mem.record("s10", "ranking", ["I1", "I2"])
    mem.persist()

    reloaded = EpisodicMemory(path)
    assert len(reloaded) == 1
    assert reloaded.latest(step="s10").value == ["I1", "I2"]
    # continues the sequence counter, stays append-only across runs
    reloaded.record("s11", "report", "ok")
    assert [r.seq for r in reloaded.recall()] == [0, 1]


# -- heartbeat --------------------------------------------------------------- #
def test_heartbeat_detects_stall_with_fake_clock():
    now = {"t": 0.0}
    hb = Heartbeat(clock=lambda: now["t"], stall_seconds=100.0)
    hb.beat("s05", "running")
    now["t"] = 50.0
    assert not hb.is_stalled()
    now["t"] = 250.0
    assert hb.is_stalled()
    rep = hb.report()
    assert rep["n_beats"] == 1 and rep["stalled"] is True


def test_heartbeat_done_is_not_stalled():
    now = {"t": 0.0}
    hb = Heartbeat(clock=lambda: now["t"], stall_seconds=10.0)
    hb.beat("s14", "done")
    now["t"] = 9999.0
    assert hb.is_stalled() is False


# -- critic ------------------------------------------------------------------ #
def test_critic_flags_overclaim_and_passes_hedged():
    critic = Critic([nonempty_rule, overclaim_rule, eis_overclaim_rule])
    bad = critic.review("EIS proves the grain-boundary mechanism")
    assert not bad.ok and any("overclaim" in i for i in bad.issues)

    good = critic.review("The semicircle is consistent with an interfacial process; EIS suggests a trend.")
    assert good.ok and good.issues == []


def test_critic_refine_loop_revises_until_clean():
    critic = Critic([overclaim_rule])
    drafts = [
        "This result proves the universal optimum.",  # round 0: overclaim
        "This result is consistent with the proposed mechanism.",  # round 1: clean
    ]

    def produce(prev):
        return drafts[prev.round + 1] if prev is not None else drafts[0]

    text, history = critic.refine(produce, max_rounds=3)
    assert history[0].ok is False
    assert history[-1].ok is True
    assert "consistent with" in text
    assert len(history) == 2  # stopped as soon as clean


def test_critic_rule_error_does_not_crash():
    def boom(_text):
        raise RuntimeError("bad rule")

    crit = Critic([boom])
    result = crit.review("anything")
    assert not result.ok
    assert any("rule_error" in i for i in result.issues)
