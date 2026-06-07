"""真实文献 provider 返回的统一 PaperRecord 合同。"""

from __future__ import annotations

from pydantic import BaseModel, Field, computed_field


class PaperRecord(BaseModel):
    """来自真实文献 provider 的标准化论文记录。"""

    paper_id: str = Field(...)
    title: str = Field("")
    authors: str = Field("")
    year: int = Field(0)
    venue: str = Field("")
    doi: str = Field("")
    abstract: str = Field("")
    source_provider: str = Field("")
    source_url: str = Field("")
    citation_count: int = Field(0)
    pdf_url: str = Field("")
    relevance_score: float = Field(0.0)
    matched_queries: list[str] = Field(default_factory=list)
    provider_metadata: dict = Field(default_factory=dict)

    @computed_field
    @property
    def normalized_doi(self) -> str:
        return self.doi.lower().strip()

    @computed_field
    @property
    def dedup_key(self) -> str:
        if self.doi:
            return f"doi:{self.normalized_doi}"
        return f"titleyear:{self.title.lower()[:60]}:{self.year}"
