"""排名合同 — Step 10 Instance Ranker。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


CombinationNovelty = Literal["novel_combination", "close_variant", "exact_match"]


def _to_float(v, default: float = 0.0) -> float:
    try:
        return float(v) if v is not None else default
    except (TypeError, ValueError):
        return default


class RankingCriterion(BaseModel):
    criterion_name: str = Field(...)
    score: float = Field(0.0, ge=0.0, le=1.0)
    weight: float = Field(1.0, ge=0.0)
    rationale: str = Field("")

    @field_validator("score", "weight", mode="before")
    @classmethod
    def coerce_float(cls, v):
        return _to_float(v)


class RankedCandidate(BaseModel):
    rank: int = Field(...)
    instance_id: str = Field(...)
    instance_name: str = Field(...)
    total_score: float = Field(0.0)
    criteria_scores: list[RankingCriterion] = Field(default_factory=list)
    ranking_rationale: str = Field("")
    combination_novelty: CombinationNovelty = Field(
        default="novel_combination",
        description="承袭自 MaterialInstance，用于审计与排序",
    )
    literature_support_card_ids: list[str] = Field(
        default_factory=list,
        description="承袭自 MaterialInstance（= element_evidence 里 paper_id 的去重并集）",
    )
    novelty_rationale: str = Field(
        default="",
        description="承袭自 MaterialInstance：所有 instance 都填",
    )
    risk_summary: str = Field("")

    @field_validator("total_score", mode="before")
    @classmethod
    def coerce_total_score(cls, v):
        return _to_float(v)

    @field_validator("rank", mode="before")
    @classmethod
    def coerce_rank(cls, v):
        try:
            return int(float(v)) if v is not None else 0
        except (TypeError, ValueError):
            return 0


class RankingResult(BaseModel):
    """排名层完整输出。"""

    step_id: str = Field(default="s10_ranking")
    ranked_candidates: list[RankedCandidate] = Field(default_factory=list)
    ranking_notes: str = Field("")
