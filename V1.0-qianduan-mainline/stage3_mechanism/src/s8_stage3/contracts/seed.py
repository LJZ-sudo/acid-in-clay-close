"""Stage3 输入层合同 — Stage3SeedBundle 是 Stage3 的统一起点对象。

这是 Stage3 的中间起点，不是实验原始数据层。
可由 mock_seed_factory 生成（测试模式）或由 stage2_seed_adapter 从真实 Stage2 输出构建。

(P-Stage3-A) 新增 ``stage2_seed_v2`` 可选字段，承载 Stage2 的
``stage3_seed.json`` 全文（含 EvidenceUnitV2 + sample_summary +
model_comparison_summary + morphology_summary + stage3_guardrails）。
S03 evidence_builder 在它存在时会**优先**消费 V2 evidence_units 而不是
重新自由解释 row-level 数据。
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class SeedSegment(BaseModel):
    """单个样品的单个温区片段。"""

    segment_id: str = Field(...)
    sample_id: str = Field(...)
    scan_dir: Literal["heating", "cooling", "unknown"] = Field("unknown")
    t_min: float = Field(...)
    t_max: float = Field(...)
    n_points: int = Field(0)
    representative_ea: float | None = Field(None, description="eV")
    representative_sigma0: float | None = Field(None, description="S/cm")
    segment_order: int = Field(0)
    fit_type: str = Field("", description="arrhenius / vtf / unknown")
    is_wide_range: bool = Field(False)


class SeedSampleSummary(BaseModel):
    """单样品级别的汇总元数据。"""

    sample_id: str = Field(...)
    composition_r: float = Field(0.0, description="R = acid/PVA molar ratio")
    composition_n: float = Field(0.0, description="N = H2O/acid molar ratio")
    scan_dirs: list[str] = Field(default_factory=list)
    t_break_k: float | None = Field(None, description="传导行为转变温度 K")
    t_arc_k: float | None = Field(None, description="EIS 弧线消失温度 K（启发式）")
    has_eis_feature: bool = Field(False)
    conductivity_trend: str = Field("", description="increasing / decreasing / non-monotonic")
    segment_ids: list[str] = Field(default_factory=list)


class SeedCompositionNode(BaseModel):
    """组成节点：按 (R, N) 聚合的样品组。"""

    node_id: str = Field(...)
    r: float = Field(...)
    n: float = Field(...)
    sample_ids: list[str] = Field(default_factory=list)
    sample_count: int = Field(0)
    available_scan_dirs: list[str] = Field(default_factory=list)


class SeedAtlasHint(BaseModel):
    """来自 Stage2 Evidence Atlas 的上下文提示（仅作参考，不得直接升为 direct evidence）。"""

    hint_id: str = Field(...)
    source: str = Field("stage2_evidence_atlas")
    claim_level: Literal["observation", "interpretation", "question"] = Field("observation")
    theme: str = Field("")
    statement: str = Field(...)
    confidence: float = Field(0.5, ge=0.0, le=1.0)
    tags: list[str] = Field(default_factory=list)
    support_metrics: dict[str, Any] = Field(default_factory=dict)
    usage_policy: Literal[
        "allowed_as_observation_hint",
        "allowed_as_context_only",
        "forbidden_as_direct_evidence",
    ] = Field("allowed_as_context_only")


class SystemContext(BaseModel):
    """实验体系的基本物质描述（不是答案！只是"数据来源于什么实验"的如实记录）。

    这个字段回答的是："这批 σ(T) 数据是在什么物质体系里测的？"
    它不回答："推荐用什么新材料来改进？"

    例如对 S8 体系：
        chemistry_summary = "aqueous phosphoric acid confined in 1-D sepiolite nanochannels"
        key_variables = {"R": "n(H3PO4)/n(H2O)", "N": "liquid/solid mass ratio"}
        temperature_window_K = [180.0, 300.0]
    """

    chemistry_summary: str = Field(
        "",
        description="实验体系的 1-3 句物质层面描述（酸是什么、水有没有、限域主体是什么、有无聚合物等）",
    )
    key_variables: dict[str, str] = Field(
        default_factory=dict,
        description="数据表中参数（R, N 等）在物理上代表什么",
    )
    temperature_window_K: list[float] = Field(
        default_factory=list,
        description="可选，实验温度窗口 [T_min, T_max]",
    )
    provenance: str = Field(
        "",
        description="context 来源（stage1 campaign / adapter default / manual override）",
    )


class Stage3SeedBundle(BaseModel):
    """Stage3 的统一输入对象。

    - mock 模式：由 mock_seed_factory.create_mock_seed_bundle() 生成
    - real 模式：由 stage2_seed_adapter.build_seed_bundle_from_stage2() 生成
    """

    bundle_id: str = Field(...)
    source_mode: Literal["mock", "real"] = Field("mock")
    seed_segments: list[SeedSegment] = Field(default_factory=list)
    seed_sample_summaries: list[SeedSampleSummary] = Field(default_factory=list)
    seed_composition_nodes: list[SeedCompositionNode] = Field(default_factory=list)
    seed_atlas_hints: list[SeedAtlasHint] = Field(default_factory=list)
    upstream_facts: dict[str, Any] = Field(
        default_factory=dict,
        description="全局统计信息：宽温区、T_arc < T_break 比例等",
    )
    system_context: SystemContext = Field(
        default_factory=SystemContext,
        description=(
            "实验体系的基本物质层面描述（酸/水/限域主体/聚合物/温窗/参数物理意义）。"
            "不是答案，是'这批数据来自什么实验'的记录。"
            "用于让下游 agent 在机理推理时理解物质背景，避免在完全物质无关的抽象层打转。"
        ),
    )
    adapter_warnings: list[str] = Field(
        default_factory=list,
        description="adapter 转换过程中的警告（非致命）",
    )

    # ------------------------------------------------------------------
    # P-Stage3-A: V2 seed (authoritative when present)
    # ------------------------------------------------------------------
    stage2_seed_v2: Optional[dict[str, Any]] = Field(
        default=None,
        description=(
            "完整 stage3_seed.json (V2)。包含 evidence_units (含 strength / supporting_sample_ids / "
            "limitations / safe_for_stage3) 与 stage3_guardrails。S03 evidence_builder 在它存在时"
            "会优先消费 V2 evidence_units，从而避免 LLM 二次自由解释 row-level 数据。"
        ),
    )
    stage2_seed_v2_path: Optional[str] = Field(
        default=None,
        description="stage3_seed.json 的源文件路径（审计/复现用）。",
    )
