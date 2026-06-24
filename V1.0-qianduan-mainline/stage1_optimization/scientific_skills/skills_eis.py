# -*- coding: utf-8 -*-
"""六个真实 EIS 流程的 Scientific Skill 合同（WP2-b / PC-Skills）。

把现有真实 Stage0/Stage1 流程拆成带类型、前后置、适用包络、副作用、见证、validators 的
Scientific Skill(docx §6.2),取代 demo 里的抽象 Skill。每个 Skill 都锚定真实代码:
  verify_sample_identity      ← 样品/制备记录
  verify_thermal_equilibrium  ← 温控轨迹(controllers/online_workflow + temp_driver)
  acquire_eis_spectrum        ← modules/automation/chi_executor(物理副作用、不可逆)
  assess_eis_quality          ← modules/analysis/{data_quality, kk_validation}
  extract_transport_metrics   ← modules/analysis/{rb_fitting, arrhenius}
  admit_observation_to_bo     ← canonical_input + objectives.registry + evidence_admission

能力 token(pre/postconditions)串成唯一链:
  sample_identity_verified → thermal_equilibrium_assessed → raw_spectrum_registered
  → qa_kk_admission → transport_metrics(+primary_evidence) → evidence_commit
组合校验 post(S_i) ⊨ pre(S_{i+1}) 由 registry.check_composition 保证。
"""
from __future__ import annotations

from typing import List

from .contracts import ScientificSkillContract

# 凹凸棒土搜索域(与 campaign 一致),用于 acquire/admit 的适用包络数值检查
_ATP_DOMAIN = {"R": [0.0, 1.04], "N": [0.5, 1.3]}


def build_eis_skill_chain() -> List[ScientificSkillContract]:
    """返回 6 个真实 EIS Skill 合同(按执行顺序)。"""
    return [
        ScientificSkillContract(
            skill_id="verify_sample_identity", version="1.0.0",
            input_schema={"sample_id": "str", "preparation_batch_id": "str", "geometry": "dict"},
            output_schema={"sample_identity_verified": "bool", "witness": "SampleIdentityWitness"},
            preconditions=[],
            postconditions=["sample_identity_verified"],
            physical_side_effects=[],
            failure_modes=["sample_id_missing", "prep_record_missing", "geometry_missing"],
            validators=["sample_id_present", "prep_record_present", "geometry_present"],
            required_evidence_level="PRIMARY", autonomy_level="CANARY",
        ),
        ScientificSkillContract(
            skill_id="verify_thermal_equilibrium", version="1.0.0",
            input_schema={"temperature_trace": "array", "stability_window_s": "float"},
            output_schema={"thermal_equilibrium_assessed": "bool", "equilibrium_probability": "float"},
            preconditions=["sample_identity_verified"],
            postconditions=["thermal_equilibrium_assessed"],
            physical_side_effects=["adds_thermal_history"],
            failure_modes=["not_equilibrated", "trace_missing"],
            validators=["stability_window_met", "wait_rule_met"],
            required_evidence_level="PRIMARY", autonomy_level="CANARY",
        ),
        ScientificSkillContract(
            skill_id="acquire_eis_spectrum", version="1.0.0",
            input_schema={"temperature_K": "float", "frequency_range_Hz": "interval"},
            output_schema={"raw_spectrum_registered": "bool", "raw_file_hash": "str"},
            applicability_domain=_ATP_DOMAIN,
            preconditions=["sample_identity_verified", "thermal_equilibrium_assessed",
                           "calibration_valid", "instrument_reserved"],
            postconditions=["raw_spectrum_registered"],
            physical_side_effects=["measurement_time", "may_change_conditioning"],
            failure_modes=["instrument_timeout", "file_not_generated", "calibration_expired"],
            validators=["instrument_ack", "raw_file_hash", "temperature_trace"],
            required_evidence_level="PRIMARY", autonomy_level="CANARY",
        ),
        ScientificSkillContract(
            skill_id="assess_eis_quality", version="1.0.0",
            input_schema={"frequencies": "array", "z_real": "array", "z_imag": "array"},
            output_schema={"qa_status": "str", "kk_status": "str"},
            preconditions=["raw_spectrum_registered"],
            postconditions=["qa_kk_admission"],
            physical_side_effects=[],
            failure_modes=["qa_fatal", "kk_inconsistent"],
            validators=["qa_assessed", "kk_assessed"],
            required_evidence_level="PRIMARY", autonomy_level="AUTONOMOUS",
        ),
        ScientificSkillContract(
            skill_id="extract_transport_metrics", version="1.0.0",
            input_schema={"qa_kk_admission": "dict", "thickness_cm": "float", "area_cm2": "float"},
            output_schema={"rb_ohm": "float", "conductivity_S_per_cm": "float",
                           "ea_eV": "float", "t_break_K": "float", "uncertainty": "dict"},
            preconditions=["qa_kk_admission"],
            postconditions=["transport_metrics", "primary_evidence"],
            physical_side_effects=[],
            failure_modes=["rb_method_disagreement", "arrhenius_unidentifiable"],
            validators=["rb_method_consistency", "arrhenius_model_competition"],
            required_evidence_level="PRIMARY", autonomy_level="AUTONOMOUS",
        ),
        ScientificSkillContract(
            skill_id="admit_observation_to_bo", version="1.0.0",
            input_schema={"transport_metrics": "dict", "objective_definition_id": "str"},
            output_schema={"evidence_commit_id": "str", "observation_view_entry": "dict"},
            applicability_domain=_ATP_DOMAIN,
            preconditions=["transport_metrics", "primary_evidence"],
            postconditions=["evidence_commit", "observation_view_entry"],
            physical_side_effects=[],            # 改模型状态,不改样品
            failure_modes=["objective_invalid", "not_primary_admissible", "ce_rejected"],
            validators=["cm_update_bo_passed", "ce_passed", "objective_registered"],
            required_evidence_level="PRIMARY", autonomy_level="AUTONOMOUS",
        ),
    ]


EIS_SKILL_CHAIN_ORDER = [
    "verify_sample_identity", "verify_thermal_equilibrium", "acquire_eis_spectrum",
    "assess_eis_quality", "extract_transport_metrics", "admit_observation_to_bo",
]

# 环境前置:由系统/上下文(仪器预留、校准有效)提供,**非上游 Skill 产出 token**。
# 组合校验时作为初始 available 注入(见 registry.check_composition(provided=...))。
ENVIRONMENTAL_CAPABILITIES = {"calibration_valid", "instrument_reserved"}
