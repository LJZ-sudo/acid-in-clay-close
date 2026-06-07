"""P-Stage3-D: 可迁移设计原则 (S06b) 合同。

从 S06 仲裁后的获胜机理中提炼"可迁移"层面的设计原则，供 S07 descriptor /
S09 candidate 明确依赖。与 S07 descriptor 的区别：
    - descriptor 侧重"要测什么量 / 要满足什么数值关系"；
    - design_principle 侧重"要选什么类型的组分 / 哪种几何 / 哪种化学角色"。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


PrincipleType = Literal[
    "proton_source",
    "confinement_geometry",
    "bound_water_network",
    "acid_retention",
    "film_processability",
    "cold_window_stability",
    "failure_mode_control",
]


class TransferableDesignPrinciple(BaseModel):
    principle_id: str = Field(..., description="例如 P1 / P2 / P3")
    principle_type: PrincipleType
    acid_in_clay_origin: str = Field(
        ...,
        description="来自 acid-in-clay 证据的原始观察（一句话，引用 evidence_card_ids）",
    )
    transferable_rule: str = Field(
        ...,
        description=(
            "把原始观察抽象为一条对生物聚合物/黏土/磷酸新体系同样成立的规则；"
            "**禁止**在此字段里出现具体物种名（例如 lotus、corn starch），只能写到"
            "'OH-rich biopolymer' / '1D fibrous clay' / 'phosphoric acid at %X loading' 等抽象级别。"
        ),
    )
    target_material_descriptor: str = Field(
        ...,
        description="供 S09 匹配组分的材料级描述符（仍然抽象，物种/品种名仅由 S09 根据 S08 pool 填入）",
    )
    required_validation: list[str] = Field(
        default_factory=list,
        description="为验证这条原则需要的实验（SEM dispersion / DSC freezing suppression / EIS thickness dependence / ...）",
    )
    failure_modes: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(
        default_factory=list,
        description="支撑此原则的 S03 EvidenceCard id 列表",
    )
    mechanism_links: list[str] = Field(
        default_factory=list,
        description="支撑此原则的 S06 mechanism node id 列表",
    )


class TransferableDesignPrincipleSet(BaseModel):
    step_id: str = Field(default="s06b_transfer_principles")
    principles: list[TransferableDesignPrinciple] = Field(default_factory=list)
    migration_summary: str = Field(
        default="",
        description="对从 acid-in-clay 迁移到 biopolymer/clay/H3PO4 的一段总结",
    )
