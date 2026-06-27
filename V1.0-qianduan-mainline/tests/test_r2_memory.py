# -*- coding: utf-8 -*-
"""R²-Memory（ESAS-OS 2.0 / §10.2）契约测试。

验收(对齐 §10.6 R²-Memory 行):
  - forbidden-use(S8 作训练标签)拦截率 = 100%(显式 + 投影双重);
  - stale(旧版本)写入被拒;角色无写权限被拒;用途自相矛盾被拒;
  - 同 topic 反极性并存 → CONTESTED(不"最后写入者胜出");
  - 失效项不再出现在有效读投影(无泄漏);
  - 压缩前后 top-1 动作 + 主张等级一致(决策保持);丢反证被抓;
  - ProtonAgentMemoryBench 全过。
"""
from __future__ import annotations

import sys
from pathlib import Path

MAINLINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MAINLINE / "stage1_optimization"))

from scientific_memory.agent_memory import (  # noqa: E402
    AgentMemory, MemoryItem, RoundState, Role, Use, UsageViolation, bench,
)
from scientific_memory.agent_memory.models import (  # noqa: E402
    ACCEPT, REBASE_REQUIRED, DENY, ACTIVE, CONTESTED, INVALID,
)
from scientific_memory.compression import MemoryState  # noqa: E402


def _item(mem, item_id="I1", role=Role.ANALYSIS, domain="biopolymer_clay", **kw):
    base = dict(content={}, author_role=role, domain=domain,
                allowed_uses={Use.CLAIM_SUPPORT}, writable_by={role},
                based_on_version=mem.version())
    base.update(kw)
    return MemoryItem(item_id=item_id, **base)


# ---- 写入门 -----------------------------------------------------------------

def test_role_without_write_permission_denied():
    mem = AgentMemory()
    it = _item(mem, role=Role.MEASUREMENT, writable_by={Role.ANALYSIS})
    d = mem.propose(it)
    assert d.decision == DENY and "ROLE_CANNOT_WRITE" in d.reasons[0]


def test_use_policy_contradiction_denied():
    mem = AgentMemory()
    it = _item(mem, allowed_uses={Use.TRAINING_LABEL}, forbidden_uses={Use.TRAINING_LABEL})
    d = mem.propose(it)
    assert d.decision == DENY and "USE_POLICY_CONTRADICTION" in d.reasons[0]


def test_stale_write_rejected():
    mem = AgentMemory()
    assert mem.propose(_item(mem, item_id="A")).decision == ACCEPT      # version bumps to 1
    stale = _item(mem, item_id="B")
    stale.based_on_version = 0                                          # 基于过期版本
    d = mem.propose(stale)
    assert d.decision == REBASE_REQUIRED and "STALE_WRITE" in d.reasons[0]


def test_opposing_polarity_becomes_contested():
    mem = AgentMemory()
    sup = _item(mem, item_id="S", topic="LRS@branch", polarity="support")
    assert mem.propose(sup).decision == ACCEPT
    ref = _item(mem, item_id="R", topic="LRS@branch", polarity="refute",
                based_on_version=mem.version())
    d = mem.propose(ref)
    assert d.decision == ACCEPT and d.status == CONTESTED
    assert mem._items["S"].status == CONTESTED        # 双方都标 CONTESTED，旧的不被覆盖


# ---- 用途守卫 / 角色投影 ----------------------------------------------------

def test_forbidden_use_intercept_100pct():
    mem = AgentMemory()
    mem.propose(_item(mem, item_id="S8", domain="acid_in_clay",
                      allowed_uses={Use.TRANSFER_REFERENCE},
                      forbidden_uses={Use.TRAINING_LABEL},
                      writable_by={Role.ANALYSIS}))
    for _ in range(20):
        assert mem.can_use("S8", Use.TRAINING_LABEL) is False
    try:
        mem.assert_use("S8", Use.TRAINING_LABEL)
        raised = False
    except UsageViolation:
        raised = True
    assert raised
    assert mem.can_use("S8", Use.TRANSFER_REFERENCE) is True
    assert "S8" not in [x.item_id for x in mem.training_labels_for("biopolymer_clay")]
    assert "S8" not in [x.item_id for x in mem.training_labels_for("acid_in_clay")]


def test_role_projection_visibility():
    mem = AgentMemory()
    mem.propose(_item(mem, item_id="onlyopt", visible_to={Role.OPTIMIZATION}))
    assert [x.item_id for x in mem.read(Role.OPTIMIZATION)] == ["onlyopt"]
    assert mem.read(Role.REVIEW) == []


def test_invalidation_no_leak_in_projection():
    mem = AgentMemory()
    mem.propose(_item(mem, item_id="EV"))
    assert any(x.item_id == "EV" for x in mem.read(Role.ANALYSIS, use=Use.CLAIM_SUPPORT))
    assert mem.invalidate("EV", reason="recheck_fail") is True
    assert all(x.item_id != "EV" for x in mem.read(Role.ANALYSIS, use=Use.CLAIM_SUPPORT))
    assert mem._items["EV"].status == INVALID


# ---- L0 事件层 / 多轮 -------------------------------------------------------

def test_l0_events_append_only_and_version():
    mem = AgentMemory()
    v0 = mem.version()
    mem.propose(_item(mem, item_id="X"))
    assert mem.version() == v0 + 1
    evs = mem.events()
    evs.append({"seq": 999})                          # 改副本不应影响内部
    assert mem.version() == v0 + 1
    assert [e["kind"] for e in mem.events()][-1] == "write"


def test_round_continuity_detects_drift():
    mem = AgentMemory()
    mem.push_round(RoundState(1, "g", Role.OPTIMIZATION, pending=["p"], next_step="s"))
    mem.push_round(RoundState(2, "g2", Role.OPTIMIZATION, next_step="t"))   # 目标漂移+丢 p
    rc = mem.round_continuity()
    assert rc["ok"] is False and rc["goal_stable"] is False


# ---- 决策回放 / 压缩保持 ----------------------------------------------------

def test_compression_preserves_decision_and_level():
    mem = AgentMemory()
    mem.propose(_item(mem, item_id="main", claim_level="C3", conditions={"c1"}))
    mem.propose(_item(mem, item_id="counter", is_counterevidence=True,
                      based_on_version=mem.version()))

    def probe(state: MemoryState) -> str:
        return "HOLD" if state.counterevidence else "PROCEED"

    bad = mem.verify_compression(["main"], decision_probe=probe)
    good = mem.verify_compression(["main", "counter"], decision_probe=probe)
    assert bad.ok is False
    assert any("COUNTEREVIDENCE_LOST" in r or "ACTION_DIVERGENCE" in r for r in bad.reasons)
    assert good.ok is True
    assert good.claim_level_before == good.claim_level_after == "C3"


# ---- benchmark --------------------------------------------------------------

def test_proton_agent_memory_bench_all_pass():
    res = bench.run()
    assert res["overall_ok"] is True, res
    assert res["tasks"]["T1_cross_domain_guard"]["detail"]["intercept_rate"] == 1.0
