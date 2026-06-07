"""假说层合同 — Step 04 Hypothesis Generator 的输入输出模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

_PLAUSIBILITY_MAP: dict[str, float] = {
    "very high": 0.9, "high": 0.75, "medium-high": 0.65, "medium": 0.5,
    "low-medium": 0.35, "low": 0.25, "very low": 0.1,
}


class Hypothesis(BaseModel):
    """单条竞争机理假说。"""

    hypothesis_id: str = Field(..., description="假说唯一标识，如 H1")
    mechanism_label: str = Field(..., description="机理简称（由 LLM 基于维度选择自生成，不预设固定名）")
    description: str = Field(...)
    key_prediction: str = Field("", description="核心预测")
    mechanism_axes: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Hypothesis positions on mechanism axes. Recommended keys: "
            "transport | phase_structure | temperature_dependence | transition_topology"
        ),
    )
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    conflicting_evidence_ids: list[str] = Field(default_factory=list)
    prior_plausibility: float = Field(0.5, ge=0.0, le=1.0)

    @field_validator("prior_plausibility", mode="before")
    @classmethod
    def coerce_plausibility(cls, v):
        """兜底：将文字概率映射为浮点数。Structured Outputs 正常时不触发。"""
        if isinstance(v, str):
            return _PLAUSIBILITY_MAP.get(v.strip().lower(), 0.5)
        return float(v) if v is not None else 0.5


class HypothesisBoard(BaseModel):
    """假说层完整输出。"""

    step_id: str = Field(default="s04_hypotheses")
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    reasoning_notes: str = Field("")
