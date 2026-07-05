# -*- coding: utf-8 -*-
"""R²-Memory live 接线桥（ESAS-OS 2.0 / §10.2 真实接入）。

把 `AgentMemory` 真正接到 live 测量回路:每个真实测量点 → 一条 MEMORY 记忆项(经 L0
写门),逐点 RoundState,收尾做跨域守卫 + 多轮一致性 + 决策保持压缩证书。

设计:纯加法、fail-safe。`hardware_adapter` 逐点调 `record_point`,收尾调 `finalize`;
同一组函数也被离线验证脚本用真实 run 的事件喂入 → 确保"live 接线"与"可复算验证"同源。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .agent_memory import AgentMemory, MemoryItem, RoundState, Role, Use

DOMAIN_DEFAULT = "acid_in_clay"
FOREIGN_DOMAIN = "biopolymer_clay"
WARM_CUT_C = -20.0


def new_campaign_memory() -> AgentMemory:
    return AgentMemory()


def install_cross_domain_guard(mem: AgentMemory, foreign_domain: str = FOREIGN_DOMAIN) -> Optional[str]:
    """放一条外域 transfer_reference 记忆(forbidden=training_label),
    用于真实演示"跨域记忆绝不被当作本域 BO 训练标签"。返回其 item_id。"""
    v = mem.version()
    item = MemoryItem(
        item_id=f"xref-{foreign_domain}-S8",
        content={"note": "foreign-domain transfer reference; read-only heuristic"},
        author_role=Role.ANALYSIS,
        domain=foreign_domain,
        # 外域项可作迁移参照 / 进 LLM 上下文(只读启发),但**永远禁作本域训练标签**。
        allowed_uses={Use.TRANSFER_REFERENCE, Use.PROMPT_CONTEXT},
        forbidden_uses={Use.TRAINING_LABEL},
        writable_by={Role.ANALYSIS},
        claim_level="C0",
        based_on_version=v,
        conditions={f"domain_{foreign_domain}"},
    )
    dec = mem.propose(item)
    if dec.decision == "REBASE_REQUIRED":
        item.based_on_version = mem.version()
        dec = mem.propose(item)
    return item.item_id if dec.accepted() else None


def _regime(T_C: Optional[float]) -> str:
    try:
        return "regime_warm" if float(T_C) >= WARM_CUT_C else "regime_cold"
    except (TypeError, ValueError):
        return "regime_unknown"


def record_point(
    mem: AgentMemory,
    *,
    step_idx: int,
    sample_id: str,
    T_C: Optional[float],
    rb_ohm: Optional[float],
    sigma_S_cm: Optional[float],
    qc_grade: Optional[str] = None,
    governance_verdict: Optional[str] = None,
    domain: str = DOMAIN_DEFAULT,
    allow_training_label: bool = True,
    goal: str = "map_sigma_vs_T",
) -> Dict[str, Any]:
    """把一个真实测量点写入记忆(经写门),并推一条 RoundState。fail-safe 返回摘要。"""
    # 本域测量项:可进主张支持集 + LLM 决策上下文;(可选)作 BO 训练标签。
    uses = {Use.CLAIM_SUPPORT, Use.PROMPT_CONTEXT}
    if allow_training_label:
        uses.add(Use.TRAINING_LABEL)
    v = mem.version()
    item = MemoryItem(
        item_id=f"meas-{sample_id}-step{step_idx}",
        content={
            "step_idx": step_idx, "T_C": T_C, "rb_ohm": rb_ohm,
            "sigma_S_cm": sigma_S_cm, "qc_grade": qc_grade,
            "governance_verdict": governance_verdict,
        },
        author_role=Role.MEASUREMENT,
        domain=domain,
        allowed_uses=uses,
        writable_by={Role.MEASUREMENT},
        claim_level="C1",
        based_on_version=v,
        conditions={f"sample_{sample_id}", _regime(T_C)},
    )
    dec = mem.propose(item)
    if dec.decision == "REBASE_REQUIRED":
        item.based_on_version = mem.version()
        dec = mem.propose(item)
    mem.push_round(RoundState(
        round_id=int(step_idx),
        goal=goal,
        actor_role=Role.MEASUREMENT,
        known=[f"step{step_idx}: T={T_C}C sigma={sigma_S_cm}"],
        pending=[],
        resolved=[f"measure_step{step_idx - 1}"] if step_idx > 0 else [],
        next_step="cool_to_next_setpoint",
    ))
    return {"item_id": item.item_id, "decision": dec.decision, "status": dec.status}


def read_projection(
    mem: AgentMemory,
    *,
    domain: str = DOMAIN_DEFAULT,
    max_items: int = 10,
) -> Dict[str, Any]:
    """把治理过的记忆投影成 **LLM 决策可读** 的紧凑摘要(§10.2 / L3 角色上下文)。

    这是 R²-Memory "被 agent 真正消费" 的接口:agent 决策 prompt 注入的是
    *经写门 + 用途门 + 来源域守卫* 后的视图,而非裸历史。关键不变量:
      - in_domain_recent: 本域、`Use.PROMPT_CONTEXT` 合法的测量记忆(经治理可读);
      - cross_domain_refs: 外域 transfer_reference —— 带 `usable_as_training_label=False`,
        即 agent 可把它当只读启发,但治理层保证它**绝不能**漏成本域 BO 标签。
    """
    decision_items = [
        it for it in mem.read(Role.OPTIMIZATION, use=Use.PROMPT_CONTEXT, domain=domain)
    ]

    def _proj(it: MemoryItem) -> Dict[str, Any]:
        c = it.content or {}
        return {
            "item_id": it.item_id,
            "claim_level": it.claim_level,
            "conditions": sorted(it.conditions),
            "T_C": c.get("T_C"),
            "rb_ohm": c.get("rb_ohm"),
            "sigma_S_cm": c.get("sigma_S_cm"),
            "qc_grade": c.get("qc_grade"),
            "governance_verdict": c.get("governance_verdict"),
        }

    in_domain = [_proj(it) for it in decision_items][-max_items:]

    refs: List[Dict[str, Any]] = []
    for it in mem.read(Role.REVIEW):  # REVIEW 可见全部活动项
        if it.domain == domain:
            continue
        refs.append({
            "item_id": it.item_id,
            "domain": it.domain,
            "claim_level": it.claim_level,
            "note": (it.content or {}).get("note"),
            # 治理层裁决:此外域项能否作本域训练标签(应恒为 False)。
            "usable_as_training_label": mem.can_use(it.item_id, Use.TRAINING_LABEL),
        })

    labels = mem.training_labels_for(domain)
    return {
        "memory_version": mem.version(),
        "n_in_domain_memory": len(decision_items),
        "in_domain_recent": in_domain,
        "n_training_labels": len(labels),
        "cross_domain_refs": refs,
        "guard_note": (
            "cross_domain_refs 仅作只读启发;治理层禁止其成为本域 BO 训练标签"
            "(usable_as_training_label=False)。"
        ),
    }


def _decision_probe(state) -> str:
    """决策探针:仅依据(主张等级 + 是否有反证)给 top-1 标签 —— 压缩前后须一致。"""
    return f"maxclaim={state.max_level()}|counter={bool(state.counterevidence)}"


def _condition_covering_keep(mem: AgentMemory) -> List[str]:
    """贪心选一个仍覆盖**全部活动项条件**的最小子集(真实压缩,非恒等)。
    覆盖范围含外域守卫项的 domain_* 条件,因此压缩前后 critical_conditions 零损失。"""
    keep: List[str] = []
    covered: set = set()
    for it in mem.read(Role.REVIEW):  # REVIEW ∈ 默认 visible_to,可见全部活动项
        new = set(it.conditions) - covered
        if new:
            keep.append(it.item_id)
            covered |= set(it.conditions)
    return keep


def finalize(
    mem: AgentMemory,
    *,
    sample_id: str,
    domain: str = DOMAIN_DEFAULT,
    foreign_item_id: Optional[str] = None,
) -> Dict[str, Any]:
    """收尾:多轮一致性 + 训练标签投影(外域被排除) + 跨域守卫断言 + 决策保持压缩证书。"""
    cont = mem.round_continuity()
    labels = mem.training_labels_for(domain)
    label_ids = {it.item_id for it in labels}
    foreign_excluded = (foreign_item_id is None) or (foreign_item_id not in label_ids)

    # 跨域守卫:显式企图把外域项用作本域 training_label 必须被拦截
    guard_blocked = None
    if foreign_item_id is not None:
        guard_blocked = not mem.can_use(foreign_item_id, Use.TRAINING_LABEL)

    keep = _condition_covering_keep(mem)
    cert = mem.verify_compression(keep, decision_probe=_decision_probe)

    active = [it for it in mem.read(Role.OPTIMIZATION) if it.domain == domain]
    return {
        "n_memory_points": len(active),
        "n_training_labels": len(labels),
        "foreign_excluded_from_labels": foreign_excluded,
        "cross_domain_guard_blocked": guard_blocked,
        "round_continuity": cont,
        "compression_certificate": cert.to_dict(),
        "memory_version": mem.version(),
    }
