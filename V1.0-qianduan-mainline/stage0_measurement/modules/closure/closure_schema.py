"""Pydantic schemas for the Sample Closure Card.

Aligned 1:1 with paper/closed_loop1_optimization_plan_zh.md §4.3.

Design rules:
    - All numeric fields are filled deterministically by `closure_features.py`
      from a Stage0ResultBundle.  The LLM only writes a small number of short
      Chinese text fields.
    - The LLM cannot invent new phase-transition temperatures or new segment
      indices.  All such IDs/values must already exist in the input.
    - The report is read-only for the researcher.  It is never consumed by
      Stage1 / Stage2 / Stage3.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------


class UserPrepForm(BaseModel):
    """User-supplied material preparation context.

    None of these fields are required for the report to render — when the
    researcher does not provide a sidecar `user_prep.json`, an empty form is
    used and the identity section is filled solely from the Stage0 recipe.
    """

    material_system: Optional[str] = None
    formula: Dict[str, float] = Field(default_factory=dict)
    R: Optional[float] = None
    N: Optional[float] = None
    solvent: Optional[str] = None
    acid_or_base: Optional[str] = None
    drying_temp_C: Optional[float] = None
    drying_time_h: Optional[float] = None
    electrode_type: Optional[str] = None
    sample_thickness_cm: Optional[float] = None
    sample_area_cm2: Optional[float] = None
    parent_recipe_id: Optional[str] = None
    free_text_notes: Optional[str] = None


class CampaignContextLite(BaseModel):
    """Tiny campaign reference passed in only to enable a one-line ranking.

    Note: we deliberately do not pass a Pareto front, neighbours, or any
    multi-sample list, to remove the LLM's ability to invent neighbour
    sample IDs.
    """

    campaign_name: Optional[str] = None
    n_samples_so_far: Optional[int] = None
    current_best_sigma_RT_S_per_cm: Optional[float] = None


class ClosureAgentInput(BaseModel):
    """Everything the closure agent receives."""

    # The Stage0 result bundle is passed as a plain dict to keep this module
    # decoupled from `result_bundle.Stage0ResultBundle` import.  The required
    # keys are validated by `closure_features.build_deterministic_features`.
    sample_summary: Dict
    user_prep_form: UserPrepForm = Field(default_factory=UserPrepForm)
    campaign_context: CampaignContextLite = Field(default_factory=CampaignContextLite)


# ---------------------------------------------------------------------------
# Output: top-level report
# ---------------------------------------------------------------------------


class ReportMeta(BaseModel):
    sample_id: str
    run_id: Optional[str] = None
    generated_at: str
    schema_version: str = "0.1.0"
    llm_used: bool = False
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    prompt_version: Optional[str] = None
    prompt_sha256: Optional[str] = None
    seed: Optional[int] = None
    input_summary_sha256: Optional[str] = None
    fallback_reason: Optional[str] = None


class SampleIdentity(BaseModel):
    """Echo of recipe + user-supplied preparation context. LLM does not write here."""

    sample_id: str
    material_system: Optional[str] = None
    R: Optional[float] = None
    N: Optional[float] = None
    acid_type: Optional[str] = None
    clay_type: Optional[str] = None
    thickness_cm: Optional[float] = None
    area_cm2: Optional[float] = None
    user_prep_text_sha256: Optional[str] = None
    user_prep_summary: Optional[str] = None  # ≤ 200 chars, deterministically built


# ----- 2. PerformanceCard -----


class ArrheniusSegmentRow(BaseModel):
    idx: int
    T_low_C: Optional[float] = None
    T_high_C: Optional[float] = None
    Ea_eV: Optional[float] = None
    Ea_kJ_per_mol: Optional[float] = None
    R2: Optional[float] = None
    n_points: Optional[int] = None


class PerformanceCard(BaseModel):
    sigma_RT_S_per_cm: Optional[float] = None
    sigma_max_S_per_cm: Optional[float] = None
    T_at_sigma_max_C: Optional[float] = None
    T_min_measured_C: Optional[float] = None
    sigma_at_T_min_S_per_cm: Optional[float] = None
    transport_model: Optional[str] = None
    n_segments: int = 0
    transition_temps_C: List[float] = Field(default_factory=list)
    segments: List[ArrheniusSegmentRow] = Field(default_factory=list)
    arrhenius_confidence: Optional[float] = None
    highlight_zh: str = ""  # ≤ 80 chars, written by LLM


# ----- 3. QualityCard -----


class DRTPeak(BaseModel):
    tau_s: float
    intensity: float
    T_C: Optional[float] = None


class QualityCard(BaseModel):
    n_eis_points: int = 0
    n_eis_ok: int = 0
    n_eis_rejected: int = 0
    KK_pass_rate: Optional[float] = None
    rb_confidence_p25: Optional[float] = None
    rb_confidence_p50: Optional[float] = None
    rb_confidence_p75: Optional[float] = None
    qc_distribution: Dict[str, int] = Field(default_factory=dict)
    nyquist_morphology_auto: Optional[str] = None  # 例: 'compressed_arc' / 'two_arcs' / 'tail'
    drt_peaks: List[DRTPeak] = Field(default_factory=list)
    verdict_zh: str = ""  # ≤ 120 chars, written by LLM


# ----- 4. PhaseTransitionInterp -----


PhaseTransitionType = Literal[
    "eutectic",
    "glass_transition",
    "ice_nucleation",
    "transport_mechanism_switch",
    "uncertain",
]


class PhaseTransitionInterp(BaseModel):
    T_C: float
    type_zh: str  # one of {共晶, 玻璃化, 冰核化, 输运机制切换, 不确定}
    type_code: PhaseTransitionType = "uncertain"
    confidence: Literal["low", "medium", "high"] = "low"
    note_zh: str = ""  # ≤ 60 chars

    @field_validator("note_zh")
    @classmethod
    def _note_zh_len(cls, v: str) -> str:
        return v[:60] if v else ""


# ----- 5. MechanismNote -----


class MechanismNote(BaseModel):
    primary_zh: str = ""  # ≤ 400 chars — multi-step mechanism reasoning
    supporting_segment_ids: List[int] = Field(default_factory=list)
    caveat_zh: str = ""  # ≤ 200 chars

    @field_validator("primary_zh")
    @classmethod
    def _primary_len(cls, v: str) -> str:
        return v[:400] if v else ""

    @field_validator("caveat_zh")
    @classmethod
    def _caveat_len(cls, v: str) -> str:
        return v[:200] if v else ""


# ----- 6. RiskFlag -----


RiskCode = Literal[
    "RB_BELOW_1OHM",
    "KK_WARN_HIGH",
    "FEW_POINTS_PER_SEGMENT",
    "QC_DEGRADED",
    "ARRHENIUS_LOW_CONFIDENCE",
    "USER_PREP_MISSING",
    "TRANSITION_AMBIGUOUS",
]


class RiskFlag(BaseModel):
    code: RiskCode
    severity: Literal["info", "warn", "error"] = "warn"
    human_zh: str = ""  # ≤ 60 chars

    @field_validator("human_zh")
    @classmethod
    def _human_len(cls, v: str) -> str:
        return v[:60] if v else ""


# ----- 7. Campaign comparison (lite) -----


class CampaignComparisonLite(BaseModel):
    rank_by_sigma_RT: Optional[int] = None
    delta_vs_best_pct: Optional[float] = None
    one_liner_zh: str = ""  # ≤ 200 chars

    @field_validator("one_liner_zh")
    @classmethod
    def _one_liner_len(cls, v: str) -> str:
        return v[:200] if v else ""


# ---------------------------------------------------------------------------
# Top-level report
# ---------------------------------------------------------------------------


class SampleClosureReport(BaseModel):
    """Researcher-facing closure card.  NOT consumed by downstream stages."""

    meta: ReportMeta
    identity: SampleIdentity
    performance_card: PerformanceCard
    quality_card: QualityCard
    phase_transitions: List[PhaseTransitionInterp] = Field(default_factory=list)
    mechanism_note: MechanismNote = Field(default_factory=MechanismNote)
    risks_warnings: List[RiskFlag] = Field(default_factory=list)
    campaign_comparison: CampaignComparisonLite = Field(default_factory=CampaignComparisonLite)
    # NEW: 跨卡片综合分析（v4-pro 主写）
    # 把 performance / quality / phase_transitions / prep 串起来推理一次。
    # ≤ 600 chars，仍然只能引用输入里已有的数字、段 idx、风险码。
    comprehensive_analysis_zh: str = ""
    do_not_overclaim: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# LLM-only narrative slice
# ---------------------------------------------------------------------------


class ClosureLLMNarrative(BaseModel):
    """Sub-schema returned by the LLM.  Everything else is filled by code.

    Keeping the LLM's writable surface this small is the main hallucination
    guard.  See `closure_agent.generate_sample_closure_report` for how the
    deterministic facts and these narrative fields are merged.
    """

    performance_highlight_zh: str = ""
    quality_verdict_zh: str = ""
    # NOTE: T_C may come back as float OR str depending on the model
    # (v4-pro echoes it as a number, v3.x as a string). The downstream guard
    # `_validate_narrative` already coerces with float(), so we accept both.
    phase_transition_notes: List[Dict[str, Any]] = Field(default_factory=list)
    # each entry: {"T_C": <number or str>, "type_zh": "...", "type_code": "...",
    #              "confidence": "low|medium|high", "note_zh": "..."}
    mechanism_primary_zh: str = ""
    mechanism_supporting_segment_ids: List[int] = Field(default_factory=list)
    mechanism_caveat_zh: str = ""
    risk_human_messages: Dict[str, str] = Field(default_factory=dict)  # code -> ≤ 60 chars
    campaign_one_liner_zh: str = ""
    # NEW: 综合推理段，由 v4-pro 把 performance / quality / phase / prep 串起来分析。
    # 仍然只能引用已有数字 + 段 idx，不能引入新数据 / 邻居样品 / 文献。
    comprehensive_analysis_zh: str = ""

    @field_validator(
        "performance_highlight_zh",
        "quality_verdict_zh",
        "mechanism_primary_zh",
        "mechanism_caveat_zh",
        "campaign_one_liner_zh",
        "comprehensive_analysis_zh",
    )
    @classmethod
    def _short_str(cls, v: str) -> str:
        return v.strip() if v else ""
