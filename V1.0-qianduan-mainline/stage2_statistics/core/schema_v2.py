"""Stage2 四层数据契约 (V2) — 与旧 EvidenceAtlas 共存，逐步迁移。

四层结构：
    row-level     ->  RawPoint, RowLevelQC
    sample-level  ->  SampleSummary
    segment-level ->  TemperatureSegment
    evidence-level->  TrendResult, EvidenceUnitV2

唯一对外 Stage3 接口：
    Stage3Seed (聚合 sample/segment/evidence + guardrails)
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


EvidenceStrength = Literal["strong", "moderate", "weak", "tentative"]
EvidenceLayer = Literal[
    "composition_trend",
    "temperature_transport",
    "model_competition",
    "eis_morphology",
    "mechanism_question",
    "validation_gap",
    "data_quality",
]


class RawPoint(BaseModel):
    """每个温度点 / 每条 EIS 测量的最小记录单元。"""

    row_id: str
    sample_id: str

    R: Optional[float] = None
    N: Optional[float] = None
    T_K: float

    sigma_S_cm: Optional[float] = None
    rb_ohm: Optional[float] = None
    thickness_cm: Optional[float] = None
    area_cm2: Optional[float] = None

    ea_reported_eV: Optional[float] = None
    r2_reported: Optional[float] = None

    arc_visible: Optional[bool] = None
    semicircle_visible: Optional[bool] = None

    source_file: Optional[str] = None
    notes: Optional[str] = None


class RowLevelQC(BaseModel):
    """行级 QC 结果。"""

    row_id: str
    sample_id: str
    valid_sigma: bool
    valid_temperature: bool
    valid_geometry: bool
    valid_eis: bool
    flags: List[str] = Field(default_factory=list)


class SampleSummary(BaseModel):
    """样品级摘要 — 后续所有 sample-level 趋势分析的最小单位。"""

    sample_id: str
    R: Optional[float] = None
    N: Optional[float] = None

    n_temperature_points: int = 0
    temperature_min_K: Optional[float] = None
    temperature_max_K: Optional[float] = None

    sigma_299K_interp_S_cm: Optional[float] = None
    sigma_273K_interp_S_cm: Optional[float] = None
    sigma_253K_interp_S_cm: Optional[float] = None
    sigma_233K_interp_S_cm: Optional[float] = None
    sigma_213K_interp_S_cm: Optional[float] = None
    sigma_193K_interp_S_cm: Optional[float] = None

    max_sigma_S_cm: Optional[float] = None
    min_sigma_S_cm: Optional[float] = None

    best_arrhenius_ea_eV: Optional[float] = None
    best_arrhenius_ln_sigma0: Optional[float] = None
    best_arrhenius_r2: Optional[float] = None

    has_arc_visible: bool = False
    has_semicircle_visible: bool = False

    quality_flags: List[str] = Field(default_factory=list)


class TemperatureSegment(BaseModel):
    """单样品某温区的拟合结果。"""

    segment_id: str
    sample_id: str

    T_min_K: float
    T_max_K: float
    n_points: int

    segment_label: str  # high_T / mid_T / low_T / single / piecewise_high / piecewise_low

    arrhenius_ea_eV: Optional[float] = None
    arrhenius_ln_sigma0: Optional[float] = None
    arrhenius_r2: Optional[float] = None
    arrhenius_aic: Optional[float] = None

    vtf_params: Dict[str, float] = Field(default_factory=dict)
    vtf_aic: Optional[float] = None

    piecewise_model_params: Dict[str, Any] = Field(default_factory=dict)
    quality_flags: List[str] = Field(default_factory=list)


class TrendResult(BaseModel):
    """单条统计趋势的可审计输出。"""

    trend_id: str
    target_metric: str
    predictor: str  # R, N, R+N
    method: str  # spearman, segmented_regression, gam, bootstrap
    n_samples: int
    effect_size: Optional[float] = None
    p_value: Optional[float] = None
    ci_low: Optional[float] = None
    ci_high: Optional[float] = None
    candidate_transition_points: List[Dict[str, Any]] = Field(default_factory=list)
    strength: EvidenceStrength = "tentative"
    limitations: List[str] = Field(default_factory=list)


class EvidenceUnitV2(BaseModel):
    """Stage2 → Stage3 的核心证据载体（强度分级 + 可追溯）。"""

    evidence_id: str
    layer: EvidenceLayer
    title: str
    statement: str

    strength: EvidenceStrength
    confidence: float

    supporting_sample_ids: List[str] = Field(default_factory=list)
    supporting_segment_ids: List[str] = Field(default_factory=list)
    supporting_metrics: Dict[str, Any] = Field(default_factory=dict)

    statistical_method: str = ""
    limitations: List[str] = Field(default_factory=list)
    required_followup: List[str] = Field(default_factory=list)

    safe_for_stage3: bool = True

    @field_validator("confidence")
    @classmethod
    def _check_confidence(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"confidence must be in [0,1], got {v}")
        return v


class ModelComparisonSummary(BaseModel):
    """所有样品 Arrhenius/piecewise/VTF 偏好分布的汇总。"""

    n_samples_total: int = 0
    n_samples_with_fit: int = 0
    best_model_counts: Dict[str, int] = Field(default_factory=dict)
    mean_delta_aic_arrhenius_vs_piecewise: Optional[float] = None
    mean_delta_aic_arrhenius_vs_vtf: Optional[float] = None


class MorphologySummary(BaseModel):
    """EIS 形貌覆盖度摘要。"""

    n_samples_total: int = 0
    n_samples_with_arc_evidence: int = 0
    n_samples_with_semicircle_evidence: int = 0
    arc_visible_rate: float = 0.0
    semicircle_visible_rate: float = 0.0
    sparsity_warning: bool = False


class Stage3Seed(BaseModel):
    """Stage2 → Stage3 的唯一主输入。"""

    schema_version: str = "0.2.0"
    seed_id: str
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    source_stage2_run_id: str = ""
    source_system: str = "s8_reference"
    source_mode: str = "retrospective"
    input_files: Dict[str, str] = Field(default_factory=dict)
    input_hashes: Dict[str, str] = Field(default_factory=dict)
    stage3_ready: bool = True
    stage3_blocking_reasons: List[str] = Field(default_factory=list)

    data_profile: Dict[str, Any] = Field(default_factory=dict)
    sample_summary: List[SampleSummary] = Field(default_factory=list)
    segment_fits: List[TemperatureSegment] = Field(default_factory=list)
    model_comparison_summary: ModelComparisonSummary = Field(
        default_factory=ModelComparisonSummary
    )
    morphology_summary: MorphologySummary = Field(default_factory=MorphologySummary)
    evidence_units: List[EvidenceUnitV2] = Field(default_factory=list)

    top_candidate_regions: List[Dict[str, Any]] = Field(default_factory=list)
    unresolved_questions: List[Dict[str, Any]] = Field(default_factory=list)

    stage3_guardrails: Dict[str, Any] = Field(
        default_factory=lambda: {
            "do_not_overclaim": [
                "Do not treat sparse EIS morphology flags as direct proof of a phase transition.",
                "Do not treat row-level repeated temperature points as independent samples.",
                "Do not claim lotus-root starch or any biopolymer candidate is closed-loop optimized "
                "unless Stage1 was actually run on that material.",
            ],
            "allowed_inference": [
                "Use Stage2 evidence to generate mechanism hypotheses.",
                "Use mechanism hypotheses to derive transferable design principles.",
                "Mark all mechanism claims as hypotheses unless supported by independent validation.",
            ],
        }
    )
