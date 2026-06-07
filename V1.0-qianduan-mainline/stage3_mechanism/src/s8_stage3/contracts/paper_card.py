"""Paper Card — 单篇文献的结构化提取卡片。

只提取对 Stage3 有直接价值的信息，不是全文摘要。
每张卡片可追溯到 paper_id 和 trace_spans。
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class TraceSpan(BaseModel):
    """文本定位线索，标记证据来自论文的哪个位置。"""
    page: int | None = Field(None)
    section: str = Field("")
    text_snippet: str = Field("", description="原文片段, 最多 300 字符")


class PaperCard(BaseModel):
    """单篇论文的结构化提取卡。"""
    paper_id: str = Field(...)
    stage_target: str = Field(..., description="mechanism | materials")
    bibliography: dict = Field(
        default_factory=dict,
        description="title, authors, year, venue, doi",
    )
    system_identity: dict = Field(
        default_factory=dict,
        description="材料体系标识: base_material, dopant, form_factor 等",
    )
    measurement_scope: dict = Field(
        default_factory=dict,
        description="测量范围: temp_range, freq_range, humidity 等",
    )
    mechanism_relevant_findings: list[str] = Field(
        default_factory=list,
        description="与机理相关的关键发现（每条一句话）",
    )
    numerical_findings: list[dict] = Field(
        default_factory=list,
        description="数值结果: [{metric, value, unit, conditions}]",
    )
    eis_shape_findings: list[str] = Field(default_factory=list)
    arrhenius_vtf_findings: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    relevance_judgement: dict = Field(
        default_factory=dict,
        description="{score: float, reason: str}",
    )
    supports_axes: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "该论文结论最支持的机理维度取值 (与 S04 Hypothesis.mechanism_axes 对齐)。"
            " 推荐 keys: transport | phase_structure | temperature_dependence | transition_topology"
        ),
    )
    conflicts_axes: dict[str, str] = Field(
        default_factory=dict,
        description="该论文结论明确反对的机理维度取值。",
    )
    trace_spans: list[TraceSpan] = Field(default_factory=list)
