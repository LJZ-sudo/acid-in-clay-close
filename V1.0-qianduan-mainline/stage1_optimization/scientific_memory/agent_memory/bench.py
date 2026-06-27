# -*- coding: utf-8 -*-
"""ProtonAgentMemoryBench（ESAS-OS 2.0 / §10.2 验收）。

四类可复算任务,锚定本项目真实语义(acid-in-clay 的 S8 → biopolymer 迁移):
  T1 跨域守卫    : S8 标 transfer_reference / 禁 training_label,跨域作训练标签**拦截率=100%**;
  T2 失效传播    : 撤销证据后,有效读投影不再返回它(无泄漏);
  T3 多轮一致    : 目标不漂移 + pending 最终被 resolved → round_continuity ok;
  T4 压缩保持    : 丢反证 → 证书 ok=False(被抓);保关键集 → top-1 动作 + 主张等级一致。
`run()` 返回 {task: {ok, detail}},全过 → overall ok。
"""
from __future__ import annotations

from typing import Any, Dict

from .models import MemoryItem, RoundState, Role, Use, ACCEPT, CONTESTED
from .store import AgentMemory, UsageViolation
from ..compression import MemoryState


def _s8_item(mem: AgentMemory) -> MemoryItem:
    """acid-in-clay 的 S8:可作迁移参照/上下文,**禁**直接作 biopolymer 训练标签。"""
    return MemoryItem(
        item_id="S8-acidclay-transfer", content={"motif": "acid-in-clay sigma(T)"},
        author_role=Role.ANALYSIS, domain="acid_in_clay",
        allowed_uses={Use.TRANSFER_REFERENCE, Use.PROMPT_CONTEXT},
        forbidden_uses={Use.TRAINING_LABEL},
        writable_by={Role.ANALYSIS, Role.REVIEW},
        claim_level="C2", based_on_version=mem.version())


def task_cross_domain_guard() -> Dict[str, Any]:
    mem = AgentMemory()
    d = mem.propose(_s8_item(mem))
    assert d.decision == ACCEPT
    attempts, blocked = 0, 0
    # 优化角色多次尝试把 S8 当 biopolymer 训练标签 → 每次都应被拦
    for _ in range(5):
        attempts += 1
        if not mem.can_use("S8-acidclay-transfer", Use.TRAINING_LABEL):
            blocked += 1
    raised = False
    try:
        mem.assert_use("S8-acidclay-transfer", Use.TRAINING_LABEL)
    except UsageViolation:
        raised = True
    # 取 biopolymer 域训练标签也绝不能含 S8
    leaked = any(it.item_id == "S8-acidclay-transfer"
                 for it in mem.training_labels_for("biopolymer_clay"))
    # 但迁移参照用途必须放行(不是一刀切封死)
    ref_ok = mem.can_use("S8-acidclay-transfer", Use.TRANSFER_REFERENCE)
    ok = (blocked == attempts) and raised and (not leaked) and ref_ok
    return {"ok": ok, "detail": {"intercept_rate": blocked / attempts,
            "raised": raised, "leaked_into_training": leaked, "transfer_allowed": ref_ok}}


def task_invalidation_no_leak() -> Dict[str, Any]:
    mem = AgentMemory()
    it = MemoryItem(item_id="EV-1", content={"rb": 1e4}, author_role=Role.MEASUREMENT,
                    domain="biopolymer_clay", allowed_uses={Use.CLAIM_SUPPORT},
                    writable_by={Role.MEASUREMENT}, claim_level="C1",
                    based_on_version=mem.version())
    mem.propose(it)
    before = any(x.item_id == "EV-1" for x in mem.read(Role.ANALYSIS, use=Use.CLAIM_SUPPORT))
    mem.invalidate("EV-1", reason="kk_fail_on_recheck")
    after = any(x.item_id == "EV-1" for x in mem.read(Role.ANALYSIS, use=Use.CLAIM_SUPPORT))
    ok = before and not after
    return {"ok": ok, "detail": {"visible_before": before, "visible_after": after}}


def task_multi_round_consistency() -> Dict[str, Any]:
    mem = AgentMemory()
    mem.push_round(RoundState(1, goal="find LRS", actor_role=Role.OPTIMIZATION,
                              known=["seed grid"], pending=["measure A", "measure B"],
                              next_step="run A"))
    mem.push_round(RoundState(2, goal="find LRS", actor_role=Role.MEASUREMENT,
                              known=["A done"], pending=["measure B"], resolved=["measure A"],
                              next_step="run B"))
    mem.push_round(RoundState(3, goal="find LRS", actor_role=Role.ANALYSIS,
                              known=["A,B done"], pending=[], resolved=["measure B"],
                              next_step="fit Arrhenius"))
    good = mem.round_continuity()
    # 负对照:目标漂移应被检出
    mem2 = AgentMemory()
    mem2.push_round(RoundState(1, goal="find LRS", actor_role=Role.OPTIMIZATION,
                               pending=["x"], next_step="a"))
    mem2.push_round(RoundState(2, goal="maximize sigma at RT", actor_role=Role.OPTIMIZATION,
                               next_step="b"))  # 目标突变 + 丢了未决 x
    drift = mem2.round_continuity()
    ok = good["ok"] and (not drift["ok"])
    return {"ok": ok, "detail": {"good": good, "drift_detected": not drift["ok"]}}


def task_compression_preservation() -> Dict[str, Any]:
    mem = AgentMemory()
    v = mem.version()
    mem.propose(MemoryItem("C-main", {"claim": "LRS exists"}, Role.ANALYSIS, "biopolymer_clay",
                           allowed_uses={Use.CLAIM_SUPPORT}, claim_level="C3",
                           conditions={"humid_30RH", "branchLRS"}, based_on_version=v))
    mem.propose(MemoryItem("C-counter", {"note": "CHITO null at boundary"}, Role.REVIEW,
                           "biopolymer_clay", allowed_uses={Use.CLAIM_SUPPORT},
                           is_counterevidence=True, claim_level="C1",
                           based_on_version=mem.version()))

    def probe(state: MemoryState) -> str:
        # 有反证 → 保守 HOLD;主张等级越界 → ESCALATE;否则 PROCEED
        if state.counterevidence:
            return "HOLD"
        return "PROCEED"

    # 坏压缩:丢掉反证 → 决策从 HOLD 翻到 PROCEED,必须被抓
    bad = mem.verify_compression(["C-main"], decision_probe=probe)
    # 好压缩:保留反证与条件 → 决策保持、等级不增、条件/反证零损失
    good = mem.verify_compression(["C-main", "C-counter"], decision_probe=probe)
    ok = (not bad.ok) and good.ok
    return {"ok": ok, "detail": {"bad_reasons": bad.reasons, "good_ok": good.ok,
            "lvl": (good.claim_level_before, good.claim_level_after)}}


def run() -> Dict[str, Any]:
    tasks = {
        "T1_cross_domain_guard": task_cross_domain_guard(),
        "T2_invalidation_no_leak": task_invalidation_no_leak(),
        "T3_multi_round_consistency": task_multi_round_consistency(),
        "T4_compression_preservation": task_compression_preservation(),
    }
    overall = all(t["ok"] for t in tasks.values())
    return {"overall_ok": overall, "tasks": tasks}


if __name__ == "__main__":
    import json
    print(json.dumps(run(), ensure_ascii=False, indent=2))
