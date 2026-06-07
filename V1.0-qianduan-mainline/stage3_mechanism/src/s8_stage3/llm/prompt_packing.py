"""Prompt Packing — 为各 step 构建最小必要输入摘要，控制 token 成本。"""

from __future__ import annotations

import json
import re
from typing import Any


def _truncate(text: str, max_chars: int = 500) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "...[truncated]"


# ---------------------------------------------------------------------------
# D2 helper — decompose a paper card's "whole-formulation" summary into a set
# of independent component-evidence entries.
#
# 设计目的（方案 D2，见 tinging.md Layer-6 精神）：
#   S08 喂给 S09 的 summary 形如
#     "Substance: PAEK; phosphoric acid; biobased composite. starch and GO.
#      Findings: dense H-bond channels replace H3PO4 ..."
#   LLM 读到后会默认"PAEK + 磷酸 + starch + GO 是一个现成配方"，从而把
#   任一单独元素（例如 starch / 藕粉）锚定到这个 PAEK 骨架上。
#
#   解决办法：在 pack_for_s09 之前，把 summary 原子化为一组 per-component
#   evidence 条目，显式告诉 S09："这些组分分别出现在同一篇文献里，但你
#   不必按原文的方式把它们绑在一起——你可以自由地把它们和其他文献的组分
#   重新组合。"
#
# 原子化规则（保守、可回退）：
#   1. 优先从 summary 里识别 "Substance: ...;...;..." 段，用分号切分；
#   2. 再从 Substance 段之后的 "other" 句（例如 "starch and GO."）切分；
#   3. 剥离常见的量化 / 范围尾缀 ("biobased composite membranes" 这种整句
#      太泛的噪声直接丢弃）；
#   4. 若无法识别出至少 1 个组分，返回空 list → pack_for_s09 会回退到
#      把原 summary 直接贴出（和 D2 之前行为一致），从而不造成退化。
# ---------------------------------------------------------------------------


_SUBSTANCE_PATTERN = re.compile(r"Substance:\s*(.+?)\.\s", re.DOTALL)
_NOISE_TOKENS = {
    "composite membranes",
    "biobased composite membranes",
    "proton exchange membranes",
    "membranes",
    "film",
    "films",
    "composite",
}

_S09_RAW_FALLBACK_LIMIT_WHEN_D4_EXISTS = 8


def _clean_component(name: str) -> str:
    """Strip trailing noise and trivial qualifiers."""
    s = name.strip().strip(".,")
    s = re.sub(r"\s+", " ", s)
    return s


def _atomize_components(summary: str) -> list[str]:
    """Return a flat list of component-level names extracted from a card summary.

    Returns [] when the summary does not follow the `Substance: ...` convention,
    signalling that the caller should fall back to passing the raw summary.
    """
    if not summary or "Substance:" not in summary:
        return []

    m = _SUBSTANCE_PATTERN.search(summary)
    if not m:
        return []

    substance_line = m.group(1)
    # Primary split on ';' (S08 builder uses semicolons between substance pieces)
    raw = [p.strip() for p in substance_line.split(";") if p.strip()]

    # Secondary: the sentence after the Substance period is often "other and X." —
    # tolerate up to one more sentence before a Measurements: / Findings: section.
    tail_region = summary[m.end():]
    tail_stop = re.search(r"(?:Measurements:|Findings:|$)", tail_region)
    tail_text = tail_region[: tail_stop.start()] if tail_stop else tail_region
    tail_text = tail_text.strip().rstrip(".")
    if tail_text:
        for sub in re.split(r",|\band\b|\bwith\b|\+|/", tail_text):
            sub = sub.strip().rstrip(".")
            if 2 < len(sub) < 80:
                raw.append(sub)

    cleaned: list[str] = []
    seen: set[str] = set()
    for r in raw:
        name = _clean_component(r)
        if not name or len(name) < 2:
            continue
        if name.lower() in _NOISE_TOKENS:
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(name)

    return cleaned


def pack_evidence_for_s04(
    evidence_bundle: dict,
    system_context: dict | None = None,
) -> str:
    """S04 包装 evidence cards + system_context。

    system_context 提供"实验体系是什么"（酸、水、限域主体、参数物理含义），
    不是答案——是让 LLM 推机理时有物质锚点，而不是完全在抽象层打转。
    """
    cards = evidence_bundle.get("evidence_cards", [])
    packed = []
    for c in cards:
        packed.append({
            "id": c.get("card_id", ""),
            "type": c.get("claim_type", ""),
            "statement": _truncate(c.get("statement", ""), 300),
            "confidence": c.get("confidence", 0.5),
        })
    payload: dict = {"evidence_cards": packed}
    if system_context:
        payload["system_context"] = {
            "chemistry_summary": _truncate(system_context.get("chemistry_summary", ""), 800),
            "key_variables": system_context.get("key_variables", {}),
            "temperature_window_K": system_context.get("temperature_window_K", []),
            "provenance": system_context.get("provenance", ""),
        }
    return json.dumps(payload, ensure_ascii=False)


def pack_for_s06(
    evidence_bundle: dict,
    mechanism_literature: dict,
    hypothesis_board: dict | None = None,
    system_context: dict | None = None,
) -> str:
    """S06 需要证据 + 机理文献摘要 + **S04 假说板** + 可选 SystemContext。

    hypothesis_board 打包后会成为 JSON 顶层的 `hypotheses` 字段，
    使 LLM 必须在这些确定的 `hypothesis_id` 中选一个（见 prompt 约束）。
    system_context 让 S06 在仲裁时可以引用物质层面的一致性（如"该假说
    与磷酸-水限域体系的已知物理一致"）。
    """
    ev_cards = evidence_bundle.get("evidence_cards", [])
    lit_cards = mechanism_literature.get("cards", [])

    ev_packed = [
        {"id": c.get("card_id"), "statement": _truncate(c.get("statement", ""), 200)}
        for c in ev_cards
    ]
    lit_packed = [
        {
            "id": c.get("card_id"),
            "summary": _truncate(c.get("summary", ""), 200),
            "supports": c.get("supports_hypothesis_ids", []),
        }
        for c in lit_cards
    ]
    notes = mechanism_literature.get("synthesis_notes", "")

    hyps_packed: list[dict] = []
    if hypothesis_board:
        for h in hypothesis_board.get("hypotheses", []):
            hyps_packed.append({
                "hypothesis_id": h.get("hypothesis_id"),
                "mechanism_label": _truncate(h.get("mechanism_label", ""), 120),
                "description": _truncate(h.get("description", ""), 220),
                "mechanism_axes": h.get("mechanism_axes", {}),
                "prior_plausibility": h.get("prior_plausibility", 0.5),
            })

    payload_s06: dict = {
        "hypotheses": hyps_packed,
        "evidence_cards": ev_packed,
        "mechanism_literature": lit_packed,
        "synthesis_notes": _truncate(str(notes), 400),
    }
    if system_context:
        payload_s06["system_context"] = {
            "chemistry_summary": _truncate(system_context.get("chemistry_summary", ""), 800),
            "key_variables": system_context.get("key_variables", {}),
            "temperature_window_K": system_context.get("temperature_window_K", []),
        }
    return json.dumps(payload_s06, ensure_ascii=False)


def pack_mechanism_for_s07(mechanism_card: dict) -> str:
    """S07 只需机理卡的核心字段。"""
    return json.dumps({
        "selected_hypothesis": mechanism_card.get("selected_hypothesis_id", ""),
        "mechanism_label": _truncate(mechanism_card.get("mechanism_label", ""), 200),
        "justification": _truncate(mechanism_card.get("justification", ""), 400),
        "t_arc_t_break_explanation": _truncate(
            mechanism_card.get("t_arc_t_break_explanation", ""), 300
        ),
        "eis_evolution_explanation": _truncate(
            mechanism_card.get("eis_evolution_explanation", ""), 400
        ),
        "caveats": mechanism_card.get("caveats", []),
    }, ensure_ascii=False)


def pack_for_s09(
    descriptor_sheet: dict,
    material_literature: dict,
    system_context: dict | None = None,
) -> str:
    """S09 需要描述符 + 材料文献（方案 D4：组件 × 描述符 × 量化锚点 claim 池）。

    三层数据一并喂给 S09，优先级从高到低：

      **1. ``descriptor_claim_pool`` (方案 D4 首要输入)** — 一个扁平 list，
         每项是一条可独立引用的 claim
         ``{component, descriptor_id, paper_id, quantitative_anchor,
            claim_text, confidence, paper_title}``。
         一条 claim 相当于 "这篇论文的数据支持'这个组件能做这个描述符'"。
         S09 应当用这些 claim 构造 element_evidence[i].descriptor_satisfied，
         使得下游 S10 的 evidence_support 能按"我声称覆盖的 descriptor 里有
         几个能被上游 claim 独立锚定"打分，消除 LLM 自报自证的回路。

      **2. ``component_evidence_pool`` (方案 D2 兼容层)** — 从 summary 正则
         化原子化出来的 {component, paper_id, paper_descriptor_axes,
         short_title} 扁平记录。当某卡没有 D4 claims 时起兜底作用。

      **3. ``raw_cards_fallback``** — 仅当 D4 claim + D2 atomization 都没有
         产生任何条目时，把 raw summary 原样留着供 S09 查阅；明确注释
         "DO NOT treat as recipe template"。

    这样的好处：如果 S08 成功产出 D4 claim，S09 直接看到"组件×描述符×量化
    锚点"三元组，符合 tinging.md Layer-6 哲学；如果 S08 还是旧流程 (mock /
    老 survey)，系统自动退回 D2 原子化，不会 crash。
    """
    descs = descriptor_sheet.get("descriptors", [])
    lit_cards = material_literature.get("cards", [])

    desc_packed = [
        {
            "id": d.get("descriptor_id"),
            "text": d.get("descriptor_text"),
            "priority": d.get("priority"),
        }
        for d in descs
    ]

    claim_pool: list[dict] = []
    component_pool: list[dict] = []
    raw_cards_fallback: list[dict] = []

    for c in lit_cards:
        paper_id = c.get("card_id", "")
        summary = c.get("summary", "")
        relevance = c.get("relevance_to_descriptors", "")
        short_title = _truncate(c.get("title", ""), 100)

        # ---- Layer 1: D4 structured claims (preferred) ----
        raw_claims = c.get("component_descriptor_claims") or []
        card_produced_d4 = False
        if isinstance(raw_claims, list) and raw_claims:
            for cl in raw_claims:
                if not isinstance(cl, dict):
                    continue
                comp = (cl.get("component") or "").strip()
                if not comp:
                    continue
                dids = cl.get("descriptor_ids") or []
                if isinstance(dids, str):
                    dids = [dids]
                # 扁平化：每个 (component, descriptor_id) 产生一条独立可引用的 claim
                for did in dids:
                    did_s = str(did).strip()
                    if not did_s:
                        continue
                    claim_pool.append({
                        "component": comp,
                        "descriptor_id": did_s,
                        "paper_id": paper_id,
                        "paper_title": short_title,
                        "quantitative_anchor": _truncate(
                            str(cl.get("quantitative_anchor") or ""), 160
                        ),
                        "claim_text": _truncate(
                            str(cl.get("claim_text") or ""), 300
                        ),
                        "confidence": cl.get("confidence") or "supported",
                    })
                    card_produced_d4 = True

        # ---- Layer 2: D2 atomization fallback (only if D4 claims absent) ----
        if not card_produced_d4:
            components = _atomize_components(summary)
            if components:
                for comp in components:
                    component_pool.append({
                        "component": comp,
                        "paper_id": paper_id,
                        "paper_descriptor_axes": _truncate(relevance, 200),
                        "short_title": short_title,
                    })
            else:
                # ---- Layer 3: raw summary fallback ----
                raw_cards_fallback.append({
                    "id": paper_id,
                    "title": short_title,
                    "summary": _truncate(summary, 400),
                    "relevance": _truncate(relevance, 200),
                })

    raw_cards_fallback_total = len(raw_cards_fallback)
    raw_cards_fallback_omitted_count = 0
    if claim_pool and raw_cards_fallback_total > _S09_RAW_FALLBACK_LIMIT_WHEN_D4_EXISTS:
        raw_cards_fallback_omitted_count = (
            raw_cards_fallback_total - _S09_RAW_FALLBACK_LIMIT_WHEN_D4_EXISTS
        )
        raw_cards_fallback = raw_cards_fallback[:_S09_RAW_FALLBACK_LIMIT_WHEN_D4_EXISTS]

    payload_s09: dict = {
        "descriptors": desc_packed,
        "descriptor_claim_pool": claim_pool,
        "component_evidence_pool": component_pool,
        "raw_cards_fallback": raw_cards_fallback,
        "raw_cards_fallback_omitted_count": raw_cards_fallback_omitted_count,
    }
    if system_context:
        payload_s09["system_context"] = {
            "chemistry_summary": _truncate(system_context.get("chemistry_summary", ""), 800),
            "key_variables": system_context.get("key_variables", {}),
            "temperature_window_K": system_context.get("temperature_window_K", []),
        }
    payload_s09["usage_note"] = (
        "PRIMARY INPUT: `descriptor_claim_pool` is your primary source of "
        "literature evidence — each entry is an atomic "
        "component×descriptor×quantitative_anchor claim. When you write "
        "`element_evidence[i].descriptor_satisfied`, every descriptor you "
        "list SHOULD be backed by at least one matching claim in this pool "
        "(same `component` substring or clear analog, and the `descriptor_id` "
        "present in the claim's `descriptor_id` field). Cite the claim's "
        "`paper_id` in `analog_paper_ids`. "
        "FALLBACK INPUT: `component_evidence_pool` gives you component-level "
        "evidence with looser descriptor tagging (from D2 regex parsing). "
        "Use it only when no D4 claim covers the component you need. "
        "COLD-SIDE (方案 L): `system_context.temperature_window_K` is the "
        "authoritative experimental window (expect ~[182, 299]); favour "
        "cold-side-friendly motifs (anti-freeze co-solvents, bound-water hosts, "
        "low-Tg matrices). Do not let HT-PEM archetypes dominate. "
        "CRITICAL: Components sharing a `paper_id` are NOT required to be "
        "combined — you are encouraged to mix components from DIFFERENT "
        "`paper_id`s to build novel formulations. Copying one paper's full "
        "recipe produces only a control baseline, not a novel candidate."
    )
    return json.dumps(payload_s09, ensure_ascii=False)


def pack_for_s10(
    instances: list[dict],
    mechanism_card: dict,
    material_literature: dict,
    system_context: dict | None = None,
) -> str:
    """S10 需要候选实例 + 机理核心 + 材料文献 + system_context（方案 L）+
    descriptor_claim_pool（方案 D4）。

    透传 combination_novelty / element_evidence / novelty_rationale 使 S10 可以
    按组合新颖度 + 元素级证据打分（见 s10_instance_ranker.md 的 criterion 6/11）。

    方案 L: 额外透传 ``system_context.temperature_window_K``，让 S10 在
    ``cold_to_room_T_robustness``（criterion 3）打分时有明确的冷端基准。

    方案 D4: 额外构造 ``descriptor_claim_pool``——从每张卡的
    ``component_descriptor_claims`` 扁平化后作为独立审计输入，
    ``evidence_support``（criterion 6）据此判断 S09 声明的
    (component, descriptor) 覆盖率是否被上游证据真正锚定。
    """
    packed_inst = [
        {
            "id": i.get("instance_id"),
            "name": i.get("instance_name"),
            "family_id": i.get("family_id"),
            "components": i.get("components", []),
            "expected_properties": i.get("expected_properties", []),
            "risk_flags": i.get("risk_flags", []),
            "combination_novelty": i.get("combination_novelty", "novel_combination"),
            "element_evidence": i.get("element_evidence", []),
            "literature_support_card_ids": i.get("literature_support_card_ids", []),
            "novelty_rationale": i.get("novelty_rationale", ""),
        }
        for i in instances
    ]
    mech = {
        "label": mechanism_card.get("mechanism_label", ""),
        "confidence": mechanism_card.get("confidence", 0.5),
    }
    lit_packed = [
        {
            "id": c.get("card_id"),
            "title": _truncate(c.get("title", ""), 120),
            "summary": _truncate(c.get("summary", ""), 250),
        }
        for c in material_literature.get("cards", [])
    ]

    # 方案 D4: 扁平化 descriptor_claim_pool，供 S10 做独立审计。
    claim_pool: list[dict] = []
    for c in material_literature.get("cards", []):
        paper_id = c.get("card_id", "")
        short_title = _truncate(c.get("title", ""), 100)
        for cl in (c.get("component_descriptor_claims") or []):
            if not isinstance(cl, dict):
                continue
            comp = (cl.get("component") or "").strip()
            if not comp:
                continue
            dids = cl.get("descriptor_ids") or []
            if isinstance(dids, str):
                dids = [dids]
            for did in dids:
                did_s = str(did).strip()
                if not did_s:
                    continue
                claim_pool.append({
                    "component": comp,
                    "descriptor_id": did_s,
                    "paper_id": paper_id,
                    "paper_title": short_title,
                    "quantitative_anchor": _truncate(
                        str(cl.get("quantitative_anchor") or ""), 160
                    ),
                })

    payload_s10: dict = {
        "candidates": packed_inst,
        "mechanism": mech,
        "material_literature": lit_packed,
        "descriptor_claim_pool": claim_pool,
    }
    if system_context:
        payload_s10["system_context"] = {
            "chemistry_summary": _truncate(system_context.get("chemistry_summary", ""), 800),
            "key_variables": system_context.get("key_variables", {}),
            "temperature_window_K": system_context.get("temperature_window_K", []),
        }
    return json.dumps(payload_s10, ensure_ascii=False)


def pack_for_s11(state: dict[str, Any], top_k: int = 5) -> str:
    """S11 需要所有上游结构化产物的简洁摘要。

    Top 列表策略 (方案 B):
    - top_k 默认 5：取 ranked_candidates 的前 min(top_k, N) 条作为主榜单。
    - 额外纳入所有未进主榜单的 `novel_combination` 候选（novel_extras），保证
      新组合路线不会在排名被某些 exact_match/close_variant 挤走时静默丢失。
    - 保留 top_3 / top_5 字段用于向后兼容。
    """
    ranked = state.get("ranked_candidates", [])
    k = min(top_k, len(ranked))
    top_main = ranked[:k]
    top_main_ids = {c.get("instance_id") for c in top_main}
    novel_extras = [
        c for c in ranked
        if c.get("combination_novelty") == "novel_combination"
        and c.get("instance_id") not in top_main_ids
    ]
    top_candidates = top_main + novel_extras

    mc = state.get("mechanism_card", {}) or {}

    return json.dumps({
        "mechanism_label": mc.get("mechanism_label", ""),
        "mechanism_justification": _truncate(mc.get("justification", ""), 600),
        "t_arc_t_break_explanation": _truncate(mc.get("t_arc_t_break_explanation", ""), 400),
        "eis_evolution_explanation": _truncate(mc.get("eis_evolution_explanation", ""), 600),
        "mechanism_caveats": mc.get("caveats", []),
        "n_evidence_cards": len(state.get("evidence_bundle", {}).get("evidence_cards", [])),
        "n_descriptors": len(state.get("descriptor_sheet", {}).get("descriptors", [])),
        "n_families": len(state.get("material_families", {}).get("families", [])),
        "n_instances": len(state.get("material_instances", {}).get("instances", [])),
        "top_k": k,
        "top_3": ranked[:3],
        "top_5": ranked[:5],
        "top_candidates": top_candidates,
        "novel_extras_note": (
            f"{len(novel_extras)} additional novel_combination candidate(s) outside the "
            f"top-{k} main list were appended so the full novel design space is represented."
            if novel_extras else ""
        ),
        "eis_disclaimer": (
            "EIS morphology is heuristic only and does not uniquely determine mechanism."
        ),
    }, ensure_ascii=False)
