"""Discovery mode 合同 (P-Stage3-C)。

四种发现强度，对应论文中能写多强的 LLM-driven discovery 主张：

    blind_transfer:
        S09 之前完全不允许目标候选词（lotus / 藕粉 / Nelumbo / rhizome starch / ...）
        出现。最强 claim：'LLM independently discovered lotus-root starch from
        acid-in-clay evidence without any prior exposure to lotus terminology.'

    broad_literature_pool_selection:
        允许 lotus 等词出现在 S08 文献池中，但禁止出现在 S03–S07 推理阶段或
        prompt 示例中。可写：'LLM selected and recombined lotus-root-starch
        evidence from a broad biomass/clay/polymer literature pool.'

    human_seeded_ranking:
        允许用户把藕粉、淀粉、壳聚糖作为候选直接交给 LLM 排序。
        只能写：'LLM rationalized and ranked human-seeded biopolymer candidates.'

    retrospective_explanation:
        实验数据先于候选注册时使用。只能写：'retrospective explanation'，不能
        写 prospective discovery。
"""

from __future__ import annotations

from typing import Literal

DiscoveryMode = Literal[
    "blind_transfer",
    "broad_literature_pool_selection",
    "human_seeded_ranking",
    "retrospective_explanation",
]

CLAIM_STRENGTH_BY_MODE: dict[str, str] = {
    "blind_transfer": "strong",
    "broad_literature_pool_selection": "moderate",
    "human_seeded_ranking": "weak",
    "retrospective_explanation": "retrospective_only",
}

ALLOWED_CLAIM_BY_MODE: dict[str, str] = {
    "blind_transfer": (
        "LLM independently inferred the candidate motif from acid-in-clay evidence "
        "with zero prior exposure to lotus / rhizome / Nelumbo terminology."
    ),
    "broad_literature_pool_selection": (
        "LLM selected and recombined lotus-root-starch evidence from a broad biomass / "
        "polymer / clay literature pool."
    ),
    "human_seeded_ranking": (
        "LLM rationalised and ranked human-seeded biopolymer/clay/H3PO4 candidates."
    ),
    "retrospective_explanation": (
        "LLM provided a retrospective explanation for already-measured biopolymer "
        "candidates; this is NOT prospective discovery."
    ),
}

FORBIDDEN_CLAIM_BY_MODE: dict[str, str] = {
    "blind_transfer": (
        "Do not call this work 'broad pool selection' or 'human seeded' — that would "
        "downgrade the claim."
    ),
    "broad_literature_pool_selection": (
        "Do not claim that the LLM independently invented lotus-root starch; the term "
        "was reachable via the S08 literature pool."
    ),
    "human_seeded_ranking": (
        "Do not claim LLM-driven discovery; LLM only ranked candidates supplied by the user."
    ),
    "retrospective_explanation": (
        "Do not claim prospective closed-loop discovery; experiments preceded the "
        "candidate registry."
    ),
}
