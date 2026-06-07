"""Prospective Candidate Registry 合同 (P-Stage3-H / S12)。

核心目的：
    在实验验证数据写入 pipeline 之前，冻结 Top-N 候选材料的身份与
    rank/score，确保论文中的 "prospective validation" 主张有可审计证据。

关键不变量：
    1. 一经 preregistered_at 时间戳写入，`candidate_id` / `rank_before_experiment`
       / `score_before_experiment` / `prompt_hashes` / `output_hashes` 等字段
       再也不能被 S13 或后续步骤修改。
    2. S13 validation binder 只能**追加** validation_record_ids，不能反向覆盖
       此 registry 的生成记录。
    3. `allowed_claim` / `forbidden_claim` 由 discovery_mode 决定。
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class ProspectiveCandidate(BaseModel):
    """单个被冻结的候选材料。"""

    candidate_id: str = Field(
        ...,
        description="注册层主键，格式 'PC-<run_id_short>-<rank>'；一经写入永不修改。",
    )
    instance_id: str = Field(..., description="指向 S09 MaterialInstance 的 id")
    instance_name: str = Field(...)
    origin: str = Field(
        default="llm_selected_from_broad_pool",
        description=(
            "候选来源：llm_proposed_blind / llm_selected_from_broad_pool / "
            "human_seeded_llm_ranked / retrospective_explained / control_baseline"
        ),
    )
    discovery_mode: str = Field(
        default="broad_literature_pool_selection",
        description="来自 Stage3Settings.discovery_mode，决定 allowed_claim",
    )
    rank_before_experiment: Optional[int] = Field(default=None)
    score_before_experiment: Optional[float] = Field(default=None)
    combination_novelty: str = Field(default="novel_combination")

    components: list[str] = Field(default_factory=list)
    composition_description: str = Field(default="")
    design_principle_ids: list[str] = Field(default_factory=list)
    descriptor_ids: list[str] = Field(default_factory=list)
    evidence_card_ids: list[str] = Field(default_factory=list)
    literature_card_ids: list[str] = Field(default_factory=list)

    source_run_id: str = Field(default="")
    preregistered_at: str = Field(default="", description="ISO-8601 UTC，冻结时间戳")
    prompt_hashes: dict[str, str] = Field(default_factory=dict)
    input_hashes: dict[str, str] = Field(default_factory=dict)
    output_hashes: dict[str, str] = Field(default_factory=dict)
    settings_snapshot: dict[str, str] = Field(
        default_factory=dict,
        description="关键 settings 快照：llm_mode/model_tier/discovery_mode/final_audit/enable_cache",
    )

    validation_status: str = Field(
        default="not_synthesized",
        description=(
            "not_synthesized / in_progress / validated_consistent / "
            "validated_inconsistent / retrospective_linked"
        ),
    )
    validation_record_ids: list[str] = Field(default_factory=list)

    allowed_claim: str = Field(default="")
    forbidden_claim: str = Field(default="")


class ProspectiveCandidateRegistry(BaseModel):
    """注册表。"""

    step_id: str = Field(default="s12_prospective_registry")
    run_id: str = Field(default="")
    preregistered_at: str = Field(default="")
    discovery_mode: str = Field(default="")
    top_n: int = Field(default=0)
    n_candidates: int = Field(default=0)
    candidates: list[ProspectiveCandidate] = Field(default_factory=list)
    registry_hash: str = Field(
        default="",
        description="所有 candidate JSON 串联后的 sha256，用于后续完整性校验",
    )
    notes: str = Field(default="")
