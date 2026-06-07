"""机理仲裁层合同 — Step 06 Mechanism Arbiter 的输入输出模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

_CONF_MAP: dict[str, float] = {
    "very high": 0.9, "high": 0.8, "medium-high": 0.7, "medium": 0.6,
    "low-medium": 0.45, "low": 0.3, "very low": 0.15,
}


class MechanismCard(BaseModel):
    """机理仲裁结论。"""

    selected_hypothesis_id: str = Field(...)
    mechanism_label: str = Field(...)
    justification: str = Field(...)
    confidence: float = Field(0.6, ge=0.0, le=1.0)
    evidence_alignment: list[str] = Field(default_factory=list)
    literature_support: list[str] = Field(default_factory=list)
    t_arc_t_break_explanation: str = Field("", description="T_arc 与 T_break 不同温的解释")
    eis_evolution_explanation: str = Field(
        "",
        description=(
            "解释 EIS 形貌随温度演化（室温直线 → 低温 '半圆+直线'）的机理来源，"
            "应说明该演化是由 (a) 弛豫时间进入测量窗口, (b) 低温涌现慢过程, "
            "(c) 结构/组成变化引入电阻性过程, 的哪一种或其组合驱动。"
        ),
    )
    caveats: list[str] = Field(default_factory=list)
    rejected_hypotheses: list[str] = Field(default_factory=list)
    why_not: list[str] = Field(
        default_factory=list,
        description=(
            "对每个未被选中的假说写一条反驳自检："
            "该假说是否能比当选假说更好地解释某一条证据；"
            "若无，则写 'none identified'。"
        ),
    )

    @field_validator("confidence", mode="before")
    @classmethod
    def coerce_confidence(cls, v):
        if isinstance(v, str):
            return _CONF_MAP.get(v.strip().lower(), 0.6)
        try:
            return float(v) if v is not None else 0.6
        except (TypeError, ValueError):
            return 0.6


class MechanismArbitrationResult(BaseModel):
    """机理仲裁层完整输出。"""

    step_id: str = Field(default="s06_mechanism")
    mechanism_card: MechanismCard
    arbitration_method: str = Field("")
