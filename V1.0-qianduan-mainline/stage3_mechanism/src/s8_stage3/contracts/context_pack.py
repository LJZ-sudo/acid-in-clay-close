"""Context Pack — 下游 agent 消费的最小上下文包。

从 CuratedEvidenceTable 生成，只保留最相关的证据行。
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ContextPack(BaseModel):
    """下游 step 的输入上下文。"""
    pack_id: str = Field(..., description="e.g. ctx-s05, ctx-s08")
    stage_target: str = Field(..., description="s05 | s06 | s08 | s09 | s10")
    included_row_ids: list[str] = Field(default_factory=list)
    excluded_row_ids: list[str] = Field(default_factory=list)
    summary: str = Field("", description="证据综合摘要")
    key_supports: list[str] = Field(default_factory=list)
    key_weakens: list[str] = Field(default_factory=list)
    key_unknowns: list[str] = Field(default_factory=list)
    usage_notes: list[str] = Field(
        default_factory=list,
        description="使用注意事项, e.g. 某条证据仅适用于特定温度范围",
    )
