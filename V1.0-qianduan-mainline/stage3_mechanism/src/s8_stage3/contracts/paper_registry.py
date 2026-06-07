"""Paper Registry Entry — 每篇文献在 registry 中的记录。"""

from __future__ import annotations

from pydantic import BaseModel, Field, computed_field


class PaperRegistryEntry(BaseModel):
    """文献注册表条目，跟踪每篇论文从入箱到证据提取的全生命周期。"""
    paper_id: str = Field(..., description="唯一标识, e.g. manual_a1b2c3")
    title: str | None = Field(None)
    authors: list[str] = Field(default_factory=list)
    year: int | None = Field(None)
    venue: str | None = Field(None)
    doi: str | None = Field(None)
    source_stage: str = Field("", description="s05_mechanism | s08_materials | shared")
    local_path: str = Field("", description="本地文件路径（相对于 literature_workspace）")
    source_type: str = Field("pdf", description="pdf | html | txt | json | md | bib | ris")
    manually_added: bool = Field(True)
    query_packet_id: str | None = Field(None)
    query_id: str | None = Field(None)
    dedupe_key: str | None = Field(None)
    ingest_status: str = Field(
        "new",
        description="new | parsed | carded | extracted | rejected",
    )
    provider_metadata: dict = Field(default_factory=dict)

    @computed_field
    @property
    def computed_dedupe_key(self) -> str:
        if self.doi:
            return f"doi:{self.doi.lower().strip()}"
        title_part = (self.title or "").lower().strip()[:60]
        return f"titleyear:{title_part}:{self.year or 0}"
