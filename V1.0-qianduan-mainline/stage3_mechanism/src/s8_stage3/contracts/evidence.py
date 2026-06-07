"""证据层合同 — Step 03 Evidence Builder。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class EvidenceCard(BaseModel):
    """单条证据卡片。"""

    card_id: str = Field(...)
    claim_type: Literal["observation", "interpretation", "question"] = Field("observation")
    statement: str = Field(...)
    source_sample_ids: list[str] = Field(default_factory=list)
    support_metrics: dict[str, str] = Field(default_factory=dict)
    counterexamples: list[str] = Field(default_factory=list)
    language_guardrail: str = Field("", description="声明时适用的语言约束/免责说明")
    allowed_downstream_use: list[str] = Field(default_factory=list)
    confidence: float = Field(0.5, ge=0.0, le=1.0)


class EvidenceBundle(BaseModel):
    """证据层完整输出（S03 输出）。"""

    step_id: str = Field(default="s03_evidence")
    evidence_cards: list[EvidenceCard] = Field(default_factory=list)
    summary_notes: str = Field("")
