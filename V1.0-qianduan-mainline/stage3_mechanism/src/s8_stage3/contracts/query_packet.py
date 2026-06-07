"""Query Packet — 供人工检索使用的结构化查询包。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class QuerySpec(BaseModel):
    """单条检索指令。"""
    query_id: str = Field(..., description="查询唯一标识, e.g. QM01")
    intent: str = Field(..., description="这条查询想回答什么问题")
    query_text: str = Field(..., description="建议的检索文本")
    query_type: str = Field(
        "google_scholar",
        description="google_scholar | publisher | database | api_assist",
    )
    include_terms: list[str] = Field(default_factory=list)
    exclude_terms: list[str] = Field(default_factory=list)
    year_hint: str | None = Field(None, description="建议年份范围, e.g. 2015-2025")
    notes: str | None = Field(None, description="补充说明, e.g. 建议看 cited by")


class QueryPacket(BaseModel):
    """一个阶段的完整检索包，供人工在 Google Scholar 等平台操作。"""
    packet_id: str = Field(..., description="唯一标识, e.g. QP-S05-001")
    stage_target: str = Field(..., description="s05_mechanism | s08_materials")
    focus_question: str = Field(..., description="本阶段核心问题的一句话定义")
    search_queries: list[QuerySpec] = Field(default_factory=list)
    screening_notes: list[str] = Field(
        default_factory=list,
        description="筛选建议: 哪些文献优先保留/排除",
    )
    stop_rule: str = Field(
        "",
        description="建议停止规则, e.g. 连续 10 篇不相关则停止",
    )
    generated_from: dict = Field(
        default_factory=dict,
        description="生成来源: hypothesis_board / descriptor_sheet 的摘要",
    )
    created_at: str = Field("", description="生成时间戳")
