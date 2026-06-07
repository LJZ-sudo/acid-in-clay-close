"""Evidence Row — 从 Paper Card 拆出的单条结构化证据。

一条 row 只承载一个核心 claim，可追溯到 paper_id。
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class EvidenceRow(BaseModel):
    """单条证据行。"""
    row_id: str = Field(..., description="唯一标识, e.g. ER-001")
    paper_id: str = Field(..., description="来源论文 ID")
    stage_target: str = Field(..., description="mechanism | materials")
    evidence_type: str = Field(
        ...,
        description="direct_measurement | mechanism_claim | comparator | limitation | context",
    )
    claim_text: str = Field(..., description="原始 claim 文本")
    normalized_claim: str = Field("", description="归一化后的 claim")
    system_scope: str | None = Field(None, description="适用材料体系")
    temperature_scope: str | None = Field(None, description="温度范围")
    eis_scope: str | None = Field(None, description="EIS 相关范围")
    arrhenius_scope: str | None = Field(None, description="Arrhenius/VTF 相关")
    mechanism_tags: list[str] = Field(default_factory=list)
    material_family_tags: list[str] = Field(default_factory=list)
    numeric_payload: dict = Field(
        default_factory=dict,
        description="{metric: str, value: float, unit: str, conditions: str}",
    )
    confidence: float = Field(0.5, ge=0.0, le=1.0)
    supports: list[str] = Field(default_factory=list, description="支持的假说 ID")
    weakens: list[str] = Field(default_factory=list, description="削弱的假说 ID")
    trace_ref: str = Field("", description="定位线索: page/section/snippet")


class CuratedEvidenceTable(BaseModel):
    """筛选后的证据表。"""
    table_id: str = Field(...)
    stage_target: str = Field(...)
    included_rows: list[EvidenceRow] = Field(default_factory=list)
    excluded_rows: list[EvidenceRow] = Field(default_factory=list)
    exclusion_reasons: dict = Field(
        default_factory=dict,
        description="{row_id: reason}",
    )
    summary: str = Field("")
