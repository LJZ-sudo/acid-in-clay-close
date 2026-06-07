"""材料候选合同 — Step 09 Candidate Family Generator。

组合新颖度 (combination_novelty) — 方案 B（本轮重构）：
    - ``novel_combination``: 整条配方未在任一篇 S08 文献里被完整报道；
      但每个组分都能在 S08 里找到 element-level 类比（见 ``element_evidence``）。
      这是 Top-list 的主体。
    - ``close_variant``: 配方与某一篇 S08 文献的组合差 ≤ 1 个组分。允许，但不应占多。
    - ``exact_match``: 整条配方本质上就是某一篇 S08 文献的原样配方。
      允许保留但要明确作为 **control baseline**；Top-list 最多 1 条。

element_evidence: 每个组分必须单独提供文献类比（可为空但要求 analog_reason 说明推理依据）。
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


CombinationNovelty = Literal["novel_combination", "close_variant", "exact_match"]

CandidateOrigin = Literal[
    "llm_proposed_blind",
    "llm_selected_from_broad_pool",
    "human_seeded_llm_ranked",
    "retrospective_explained",
    "control_baseline",
    # Tier3 (issue 4): deterministic, non-LLM evidence-based descriptor-match
    # branch (s09_evidence_based_generation=True). Truthful label — NOT an LLM
    # selection.
    "deterministic_evidence_based_descriptor_match",
]


class ElementEvidence(BaseModel):
    """单个组分的 element-level 文献类比。

    设计哲学（参考 tinging.md Layer-6 / Layer-7 + 方案 D2）：
      - 新材料 = 已知组分的新组合；
      - 每个组分都应有独立的文献支持（性能类比或机理类比），
        但整条配方不必存在于单篇文献中；
      - (D2) ``descriptor_satisfied`` 显式记录该组分满足哪些机理描述符
        （D1/D2/...），下游 S10 的 evidence_support 维度按"描述符被覆盖
        的比例"打分，而不是按"paper_id 数量"——这样即便某组分只有类比
        性文献支撑（非原样配方），只要它满足的描述符在池里有证据，就不
        会被扣分。
    """

    component: str = Field(
        ...,
        description=(
            "组分名（物种/化学级别），例如 'biomass starch (species/cultivar level)' 或 "
            "'1D fibrous clay (e.g. attapulgite/sepiolite)'。**不要在此 description 中写"
            "任何具体目标候选词**，所有具体材料名应仅由 S08 文献池或用户提供。"
        ),
    )
    role_in_formulation: str = Field(..., description="该组分在配方里承担的机理角色（D1/D2/... 的一句话描述）")
    descriptor_satisfied: list[str] = Field(
        default_factory=list,
        description=(
            "此组分满足的机理描述符 id 列表（如 ['D1','D3']）。S10 的 evidence_support "
            "按 instance 范围内'被覆盖描述符并集 / 描述符总数'打分。"
        ),
    )
    analog_paper_ids: list[str] = Field(
        default_factory=list,
        description=(
            "支撑此组分的 S08 paper_id 列表；可为空，但此时 analog_reason 必须"
            "明确注明 'no S08 analog; inferred from public physicochemical knowledge'。"
        ),
    )
    analog_reason: str = Field(
        default="",
        description="为什么这些文献对此组分形成类比支撑（一句话）。",
    )

    @field_validator("descriptor_satisfied", mode="before")
    @classmethod
    def coerce_descriptor_satisfied(cls, v):
        """LLM 偶尔返回单字符串或 dict，转为 list[str]。"""
        if v is None:
            return []
        if isinstance(v, list):
            return [str(x).strip() for x in v if str(x).strip()]
        if isinstance(v, str):
            parts = [p.strip() for p in v.replace(",", "/").replace(";", "/").split("/")]
            return [p for p in parts if p]
        return []


class MaterialFamily(BaseModel):
    """材料 family 级别（抽象类别，还不是具体配方）。"""

    family_id: str = Field(...)
    family_name: str = Field(...)
    family_description: str = Field("")
    descriptor_match: list[str] = Field(
        default_factory=list,
        description="匹配的描述符列表（列表项：'descriptor_id: 匹配说明'）",
    )
    literature_support_card_ids: list[str] = Field(default_factory=list)

    @field_validator("descriptor_match", mode="before")
    @classmethod
    def coerce_descriptor_match(cls, v):
        if v is None:
            return []
        if isinstance(v, list):
            result = []
            for item in v:
                if isinstance(item, str):
                    result.append(item)
                elif isinstance(item, dict):
                    result.append(str(item))
                else:
                    result.append(str(item))
            return result
        if isinstance(v, dict):
            return [f"{k}: {val}" for k, val in v.items()]
        if isinstance(v, str):
            return [v]
        return []


class MaterialInstance(BaseModel):
    """具体材料路线/配方实例（S09 才允许出现具体材料名）。

    核心字段 (本轮重构):
      - ``combination_novelty``: 整条配方相对于 S08 文献池的新颖度
        （novel_combination / close_variant / exact_match）。
      - ``element_evidence``: **每个组分** 的 element-level 类比文献；下游 S10
        的 evidence_support 维度按此字段的覆盖度评分。
      - ``novelty_rationale``: 整条配方的新颖性说明（对所有 instance 都必填），
        说明"为什么此组合相对现有文献是新的 / 它相对最近 exact 配方的差异"。
      - ``literature_support_card_ids``: = 所有 element_evidence 里 paper_id 的
        去重并集；供 S11 报告做链接。S09 agent 填写，无需 LLM 输出。
    """

    instance_id: str = Field(...)
    family_id: str = Field(...)
    instance_name: str = Field(...)
    composition_description: str = Field("")
    components: list[str] = Field(
        default_factory=list,
        description="组分列表（字符串数组），与 element_evidence 一一对应。",
    )
    expected_properties: list[str] = Field(
        default_factory=list,
        description="预期属性列表（格式：'属性名: 预期值'），低熵扁平结构",
    )
    risk_flags: list[str] = Field(default_factory=list)

    combination_novelty: CombinationNovelty = Field(
        default="novel_combination",
        description=(
            "组合新颖度：novel_combination(整条配方为新)/close_variant(差≤1组分)/"
            "exact_match(整条就是某篇文献的原样配方, 仅允许作为 control baseline)"
        ),
    )
    element_evidence: list[ElementEvidence] = Field(
        default_factory=list,
        description=(
            "每个组分独立的 element-level 文献类比。至少覆盖 instance 的主要组分；"
            "S10 的 evidence_support 打分按此字段的覆盖比例。"
        ),
    )
    literature_support_card_ids: list[str] = Field(
        default_factory=list,
        description=(
            "派生字段：所有 element_evidence 里 paper_id 的去重并集。"
            "S09 agent 在验证阶段自动填充；LLM 输出可缺省。"
        ),
    )
    novelty_rationale: str = Field(
        default="",
        description=(
            "整条配方的新颖性陈述（对所有 combination_novelty 都必填）："
            "novel_combination / close_variant 要说明'相对最近 exact 配方的差异'；"
            "exact_match 要说明'为什么作为 control baseline 而非 novel 候选'。"
        ),
    )

    # P-Stage3-F: 候选来源标签 (由 S09 post-validation 自动填充)
    origin: CandidateOrigin = Field(
        default="llm_selected_from_broad_pool",
        description=(
            "候选来源：llm_proposed_blind / llm_selected_from_broad_pool / "
            "human_seeded_llm_ranked / retrospective_explained / control_baseline / "
            "deterministic_evidence_based_descriptor_match。"
            "由 S09 agent 根据 discovery_mode + combination_novelty 自动填充；"
            "当 s09_evidence_based_generation=True 时填充为 "
            "deterministic_evidence_based_descriptor_match (非 LLM 选择)。"
        ),
    )
    source_mode: str = Field(
        default="",
        description="settings.discovery_mode 的镜像 (P-Stage3-F)，用于下游 S10 审计",
    )
    user_candidate_id: Optional[str] = Field(
        default=None,
        description="human_seeded_ranking 模式下映射到用户给定候选的 id",
    )
    design_principle_ids: list[str] = Field(
        default_factory=list,
        description="对应 S06b (P-Stage3-D) 的可迁移设计原则 id；S09 回填",
    )
    descriptor_claim_coverage: Optional[float] = Field(
        default=None,
        description=(
            "派生字段（S10 计算）：candidate 声称的 descriptor 在 S08 "
            "descriptor_claim_pool 中有多少比例能找到 component-level 支持。"
        ),
    )

    @field_validator("expected_properties", "components", mode="before")
    @classmethod
    def coerce_str_list(cls, v):
        if v is None:
            return []
        if isinstance(v, list):
            return [str(item) for item in v]
        if isinstance(v, dict):
            return [f"{k}: {val}" for k, val in v.items()]
        if isinstance(v, str):
            return [v]
        return []

    @model_validator(mode="after")
    def _populate_derived_paper_ids(self):
        """派生 literature_support_card_ids = 所有 element_evidence 里 paper_id 的去重并集。

        仅在 agent 未显式填充时补齐；若 agent 已显式填了（例如承袭自上游），保留原值。
        """
        if not self.literature_support_card_ids and self.element_evidence:
            derived: list[str] = []
            seen: set[str] = set()
            for ev in self.element_evidence:
                for pid in ev.analog_paper_ids:
                    if pid and pid not in seen:
                        seen.add(pid)
                        derived.append(pid)
            object.__setattr__(self, "literature_support_card_ids", derived)
        return self


class MaterialFamilySet(BaseModel):
    """Family 层完整输出。"""

    step_id: str = Field(default="s09_families")
    families: list[MaterialFamily] = Field(default_factory=list)


class MaterialInstanceSet(BaseModel):
    """Instance 层完整输出。"""

    step_id: str = Field(default="s09_instances")
    instances: list[MaterialInstance] = Field(default_factory=list)
