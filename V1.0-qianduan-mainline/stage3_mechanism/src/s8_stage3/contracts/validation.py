"""Validation Binder 合同 (P-Stage3-I / S13)。

S13 职责：把已经测量的生物聚合物体系实验数据（藕粉/玉米淀粉/壳聚糖 +
PVA + 凹凸棒土 + 磷酸）绑定到 S12 已冻结的候选 registry。

绑定原则：
    1. 单向：实验结果只能绑定到 candidate_id，不能反向修改 S09/S10/S12。
    2. 若实验时间早于 preregistered_at，timing 必须标 "retrospective"；
       此时 claim_level 只能是 retrospective_validation。
    3. 派生字段自动计算：pure_h3po4_g、h3po4_to_dry_matrix、
       attapulgite_wt_fraction_dry_matrix、pva_to_biopolymer 等。
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

ValidationTiming = Literal[
    "prospective",
    "retrospective",
    "unknown",
]


class DerivedFormulation(BaseModel):
    pure_h3po4_g: Optional[float] = None
    water_from_acid_g: Optional[float] = None
    dry_matrix_g: Optional[float] = None
    h3po4_to_dry_matrix: Optional[float] = None
    attapulgite_wt_fraction_dry_matrix: Optional[float] = None
    pva_to_biopolymer: Optional[float] = None


class ValidationRecord(BaseModel):
    """单次实验记录（对应 CSV 的一行）。"""

    validation_id: str = Field(...)
    candidate_id: Optional[str] = Field(
        default=None,
        description="指向 ProspectiveCandidate.candidate_id；None 表示未绑定到任何候选",
    )
    instance_id: Optional[str] = Field(
        default=None,
        description=(
            "Optional pointer to ProspectiveCandidate.instance_id. JSON feedback may "
            "use candidate_id or instance_id; S13 resolves both without mutating S12."
        ),
    )
    sample_id: str = Field(default="")
    material_system: str = Field(default="biopolymer_clay_h3po4")
    validation_timing: ValidationTiming = Field(default="unknown")
    measured_at: str = Field(
        default="",
        description=(
            "ISO-8601 experiment timestamp. Prospective claims require measured_at "
            "to be later than registry.preregistered_at."
        ),
    )

    # 原始配方（单位 g）
    lotus_starch_g: float = Field(default=0.0)
    starch_g: float = Field(default=0.0)
    chitosan_g: float = Field(default=0.0)
    pva_g: float = Field(default=0.0)
    attapulgite_g: float = Field(default=0.0)
    h3po4_85wt_g: float = Field(default=0.0)
    water_g: float = Field(default=0.0)
    acetic_acid_1wt_g: float = Field(default=0.0)

    # 工艺
    pva_dissolution_temp_C: Optional[float] = None
    gelatinization_schedule_C: str = Field(default="")
    drying_temp_C: Optional[float] = None
    seal_pressure_MPa: Optional[float] = None
    final_mass_g: Optional[float] = None
    thickness_cm: Optional[float] = None
    electrode_area_cm2: Optional[float] = None

    # 宽温 σ（S/cm）
    sigma_299k_s_cm: Optional[float] = None
    sigma_273k_s_cm: Optional[float] = None
    sigma_253k_s_cm: Optional[float] = None
    sigma_233k_s_cm: Optional[float] = None
    sigma_213k_s_cm: Optional[float] = None
    sigma_193k_s_cm: Optional[float] = None

    # Arrhenius
    ea_high_eV: Optional[float] = None
    ea_low_eV: Optional[float] = None
    t_break_K: Optional[float] = None
    t_arc_K: Optional[float] = None

    # 失效模式
    leakage_score: Optional[float] = None
    mass_loss_pct: Optional[float] = None
    notes: str = Field(default="")

    # 派生
    derived: DerivedFormulation = Field(default_factory=DerivedFormulation)


class CandidateValidationLink(BaseModel):
    """候选 × 实验的绑定状态。"""

    candidate_id: str
    instance_name: str = ""
    n_experiments_bound: int = 0
    experiment_ids: list[str] = Field(default_factory=list)
    best_sigma_299k_s_cm: Optional[float] = None
    best_sigma_193k_s_cm: Optional[float] = None
    any_prospective: bool = False
    any_retrospective: bool = False
    claim_eligibility: str = Field(
        default="retrospective_validation",
        description=(
            "prospective_validation（实验晚于注册且 consistent）/ "
            "retrospective_validation / unvalidated_candidate"
        ),
    )
    binding_notes: str = ""


class ValidationBindingReport(BaseModel):
    step_id: str = Field(default="s13_validation_binding")
    run_id: str = Field(default="")
    n_records: int = 0
    n_bound: int = 0
    n_unbound: int = 0
    records: list[ValidationRecord] = Field(default_factory=list)
    candidate_links: list[CandidateValidationLink] = Field(default_factory=list)
    source_csv_path: str = ""
    source_feedback_path: str = ""
    feedback_schema_valid: bool = False
    feedback_warnings: list[str] = Field(default_factory=list)
    input_hashes: dict[str, str] = Field(default_factory=dict)
    notes: str = ""
