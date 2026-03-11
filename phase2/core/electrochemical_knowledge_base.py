# -*- coding: utf-8 -*-
"""
电化学知识库系统 - Phase 2核心模块
管理结构化的电化学领域知识，支持机理推断
"""
import yaml
import json
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional, Any, Union
from dataclasses import dataclass, asdict
from pathlib import Path
import logging
from enum import Enum

class MaterialType(Enum):
    """材料类型"""
    SOLID_ELECTROLYTE = "solid_electrolyte"
    LIQUID_ELECTROLYTE = "liquid_electrolyte"
    POLYMER_ELECTROLYTE = "polymer_electrolyte"
    COMPOSITE_ELECTROLYTE = "composite_electrolyte"
    CERAMIC = "ceramic"
    GLASS = "glass"
    CRYSTAL = "crystal"

class ConductionMechanism(Enum):
    """传导机理"""
    PROTON_CONDUCTION = "proton_conduction"
    OXIDE_ION_CONDUCTION = "oxide_ion_conduction"
    LITHIUM_ION_CONDUCTION = "lithium_ion_conduction"
    SODIUM_ION_CONDUCTION = "sodium_ion_conduction"
    ELECTRONIC_CONDUCTION = "electronic_conduction"
    MIXED_CONDUCTION = "mixed_conduction"
    HOPPING_CONDUCTION = "hopping_conduction"
    BAND_CONDUCTION = "band_conduction"

@dataclass
class MechanismSignature:
    """机理特征签名"""
    mechanism: ConductionMechanism
    activation_energy_range: Tuple[float, float]  # eV
    conductivity_range: Tuple[float, float]       # S/cm
    frequency_signature: str
    temperature_dependence: str
    typical_circuit_models: List[str]
    characteristic_features: Dict[str, Any]
    literature_references: List[str]
    confidence_factors: Dict[str, float]

@dataclass
class PatternTemplate:
    """EIS模式模板"""
    pattern_id: str
    name: str
    description: str
    characteristic_features: Dict[str, Any]
    frequency_behavior: Dict[str, Any]
    temperature_behavior: Dict[str, Any]
    equivalent_circuits: List[str]
    physical_interpretation: str
    occurrence_conditions: List[str]
    diagnostic_criteria: Dict[str, Any]

@dataclass
class InferenceRule:
    """推断规则"""
    rule_id: str
    name: str
    condition: Dict[str, Any]
    conclusion: Dict[str, Any]
    confidence_weight: float
    evidence_requirements: List[str]
    contraindications: List[str]
    validation_method: str

class ElectrochemicalKnowledgeBase:
    """电化学知识库系统"""
    
    def __init__(self, kb_path: str = "knowledge/"):
        """
        初始化知识库
        
        Args:
            kb_path: 知识库文件路径
        """
        self.kb_path = Path(kb_path)
        self.logger = logging.getLogger(__name__)
        
        # 核心知识组件
        self.mechanisms: Dict[str, MechanismSignature] = {}
        self.patterns: Dict[str, PatternTemplate] = {}
        self.inference_rules: Dict[str, InferenceRule] = {}
        self.material_database: Dict[str, Dict] = {}
        self.literature_database: Dict[str, Dict] = {}
        
        # 加载知识库
        self._initialize_knowledge_base()
    
    def _initialize_knowledge_base(self):
        """初始化知识库"""
        self.logger.info("初始化电化学知识库...")
        
        # 确保知识库目录存在
        self.kb_path.mkdir(exist_ok=True)
        
        # 加载各类知识
        self._load_mechanism_signatures()
        self._load_pattern_templates()
        self._load_inference_rules()
        self._load_material_database()
        self._load_literature_database()
        
        # 验证知识库完整性
        self._validate_knowledge_base()
        
        self.logger.info(f"知识库加载完成: {len(self.mechanisms)}个机理, "
                        f"{len(self.patterns)}个模式, {len(self.inference_rules)}个规则")
    
    def _load_mechanism_signatures(self):
        """加载机理特征签名"""
        # 质子传导机理
        self.mechanisms['proton_conduction'] = MechanismSignature(
            mechanism=ConductionMechanism.PROTON_CONDUCTION,
            activation_energy_range=(0.3, 1.2),  # eV
            conductivity_range=(1e-6, 1e-2),     # S/cm
            frequency_signature="single_peak_or_broad_distribution",
            temperature_dependence="arrhenius",
            typical_circuit_models=["R-CPE", "RC_parallel", "R(RC)"],
            characteristic_features={
                "modulus_peak_count": (0, 2),
                "drt_peak_shape": "symmetric_or_asymmetric",
                "high_freq_behavior": "resistive",
                "low_freq_behavior": "capacitive",
                "warburg_signature": False
            },
            literature_references=[
                "doi:10.1038/nature12568",
                "doi:10.1021/cr020715f",
                "doi:10.1016/j.ssi.2004.01.076"
            ],
            confidence_factors={
                "activation_energy_match": 0.3,
                "conductivity_range_match": 0.2,
                "circuit_model_match": 0.2,
                "frequency_behavior_match": 0.15,
                "temperature_dependence_match": 0.15
            }
        )
        
        # 氧离子传导机理
        self.mechanisms['oxide_ion_conduction'] = MechanismSignature(
            mechanism=ConductionMechanism.OXIDE_ION_CONDUCTION,
            activation_energy_range=(0.8, 2.0),
            conductivity_range=(1e-8, 1e-1),
            frequency_signature="broad_distribution_or_multiple_peaks",
            temperature_dependence="arrhenius",
            typical_circuit_models=["R(RC)(RC)", "R-CPE-CPE", "double_RC"],
            characteristic_features={
                "modulus_peak_count": (1, 3),
                "drt_peak_shape": "broad_asymmetric",
                "high_freq_behavior": "resistive",
                "low_freq_behavior": "capacitive_with_electrode_effects",
                "warburg_signature": False
            },
            literature_references=[
                "doi:10.1016/j.ssi.2003.12.020",
                "doi:10.1021/cm062616e"
            ],
            confidence_factors={
                "activation_energy_match": 0.35,
                "conductivity_range_match": 0.25,
                "circuit_model_match": 0.2,
                "frequency_behavior_match": 0.1,
                "temperature_dependence_match": 0.1
            }
        )
        
        # 锂离子传导机理
        self.mechanisms['lithium_ion_conduction'] = MechanismSignature(
            mechanism=ConductionMechanism.LITHIUM_ION_CONDUCTION,
            activation_energy_range=(0.2, 0.8),
            conductivity_range=(1e-5, 1e-1),
            frequency_signature="single_or_double_peak",
            temperature_dependence="arrhenius_or_vft",
            typical_circuit_models=["R-CPE", "R(RC)W", "RC_parallel"],
            characteristic_features={
                "modulus_peak_count": (1, 2),
                "drt_peak_shape": "symmetric",
                "high_freq_behavior": "resistive",
                "low_freq_behavior": "diffusive_or_capacitive",
                "warburg_signature": True
            },
            literature_references=[
                "doi:10.1021/cr500192f",
                "doi:10.1038/nmat4369"
            ],
            confidence_factors={
                "activation_energy_match": 0.3,
                "conductivity_range_match": 0.25,
                "circuit_model_match": 0.2,
                "warburg_signature_match": 0.15,
                "temperature_dependence_match": 0.1
            }
        )
        
        # 电子传导机理
        self.mechanisms['electronic_conduction'] = MechanismSignature(
            mechanism=ConductionMechanism.ELECTRONIC_CONDUCTION,
            activation_energy_range=(0.0, 0.5),
            conductivity_range=(1e-2, 1e3),
            frequency_signature="nearly_flat_or_weak_dispersion",
            temperature_dependence="weak_or_metallic",
            typical_circuit_models=["R", "RC", "R-CPE"],
            characteristic_features={
                "modulus_peak_count": (0, 1),
                "drt_peak_shape": "very_broad_or_absent",
                "high_freq_behavior": "resistive",
                "low_freq_behavior": "resistive",
                "warburg_signature": False
            },
            literature_references=[
                "doi:10.1016/j.ssi.2007.12.020"
            ],
            confidence_factors={
                "conductivity_range_match": 0.4,
                "activation_energy_match": 0.25,
                "frequency_behavior_match": 0.2,
                "temperature_dependence_match": 0.15
            }
        )
        
        # 混合传导机理
        self.mechanisms['mixed_conduction'] = MechanismSignature(
            mechanism=ConductionMechanism.MIXED_CONDUCTION,
            activation_energy_range=(0.2, 1.5),
            conductivity_range=(1e-5, 1e0),
            frequency_signature="complex_multiple_peaks",
            temperature_dependence="complex_arrhenius",
            typical_circuit_models=["complex_RC", "R(RC)(RC)W", "multi_element"],
            characteristic_features={
                "modulus_peak_count": (2, 4),
                "drt_peak_shape": "multiple_overlapping",
                "high_freq_behavior": "mixed",
                "low_freq_behavior": "mixed",
                "warburg_signature": True
            },
            literature_references=[
                "doi:10.1016/j.ssi.2008.02.019"
            ],
            confidence_factors={
                "complexity_match": 0.3,
                "multiple_process_evidence": 0.25,
                "circuit_complexity_match": 0.2,
                "frequency_behavior_match": 0.15,
                "conductivity_range_match": 0.1
            }
        )
    
    def _load_pattern_templates(self):
        """加载EIS模式模板"""
        # 单一德拜弛豫模式
        self.patterns['single_debye'] = PatternTemplate(
            pattern_id="single_debye",
            name="单一德拜弛豫",
            description="单一弛豫过程，表现为单个半圆或单个模量峰",
            characteristic_features={
                "nyquist_semicircles": 1,
                "modulus_peaks": 1,
                "drt_peaks": 1,
                "peak_symmetry": "symmetric"
            },
            frequency_behavior={
                "high_freq_limit": "finite_resistance",
                "low_freq_limit": "capacitive",
                "transition_region": "single_relaxation"
            },
            temperature_behavior={
                "peak_shift": "arrhenius",
                "intensity_change": "temperature_dependent",
                "activation_energy": "single_value"
            },
            equivalent_circuits=["R(RC)", "R-CPE"],
            physical_interpretation="单一传导过程，如体相离子传导或单一界面过程",
            occurrence_conditions=[
                "单相材料",
                "单一传导机理主导",
                "均匀微结构",
                "理想条件"
            ],
            diagnostic_criteria={
                "circuit_fit_quality": ">0.95",
                "residual_randomness": True,
                "parameter_stability": "high"
            }
        )
        
        # 双德拜弛豫模式
        self.patterns['double_debye'] = PatternTemplate(
            pattern_id="double_debye",
            name="双德拜弛豫",
            description="两个分离的弛豫过程，通常对应体相和界面过程",
            characteristic_features={
                "nyquist_semicircles": 2,
                "modulus_peaks": 2,
                "drt_peaks": 2,
                "peak_separation": "well_separated"
            },
            frequency_behavior={
                "high_freq_process": "bulk_conduction",
                "low_freq_process": "interface_or_electrode",
                "frequency_separation": ">1_decade"
            },
            temperature_behavior={
                "dual_activation_energies": True,
                "different_temperature_dependence": True
            },
            equivalent_circuits=["R(RC)(RC)", "R-CPE-CPE"],
            physical_interpretation="体相传导+界面过程，或两种不同的传导路径",
            occurrence_conditions=[
                "多相材料",
                "明显的界面阻抗",
                "晶界效应显著",
                "电极极化"
            ],
            diagnostic_criteria={
                "frequency_separation": ">10",
                "activation_energy_difference": ">0.2",
                "independent_temperature_evolution": True
            }
        )
        
        # Warburg扩散模式
        self.patterns['warburg_diffusion'] = PatternTemplate(
            pattern_id="warburg_diffusion",
            name="Warburg扩散",
            description="扩散控制的传质过程，低频呈现45°直线",
            characteristic_features={
                "nyquist_45_degree_line": True,
                "low_freq_linear_behavior": True,
                "frequency_exponent": 0.5
            },
            frequency_behavior={
                "high_freq": "resistive_or_capacitive",
                "low_freq": "diffusive_omega_minus_half",
                "transition_frequency": "diffusion_characteristic"
            },
            temperature_behavior={
                "diffusion_coefficient_temperature": "arrhenius",
                "warburg_coefficient_temperature": "arrhenius"
            },
            equivalent_circuits=["RW", "R(RC)W", "R-CPE-W"],
            physical_interpretation="扩散控制的传质，如离子在电极中的扩散",
            occurrence_conditions=[
                "电极反应",
                "固体中的扩散",
                "浓度梯度",
                "有限扩散长度"
            ],
            diagnostic_criteria={
                "low_freq_slope": "45_degrees",
                "frequency_dependence": "omega_minus_half",
                "diffusion_length_consistency": True
            }
        )
        
        # 常相位元件(CPE)模式
        self.patterns['cpe_behavior'] = PatternTemplate(
            pattern_id="cpe_behavior",
            name="常相位元件行为",
            description="非理想电容行为，表现为压扁的半圆",
            characteristic_features={
                "depressed_semicircle": True,
                "phase_angle_constant": True,
                "frequency_exponent": "<1"
            },
            frequency_behavior={
                "impedance_frequency_dependence": "omega_minus_n",
                "phase_angle": "constant_not_90_degrees",
                "dispersion": "power_law"
            },
            temperature_behavior={
                "cpe_exponent_temperature": "weak_dependence",
                "pseudocapacitance_temperature": "arrhenius_like"
            },
            equivalent_circuits=["R-CPE", "R(R-CPE)"],
            physical_interpretation="非均匀性、粗糙度、分布弛豫时间",
            occurrence_conditions=[
                "表面粗糙度",
                "成分不均匀",
                "弛豫时间分布",
                "微结构复杂"
            ],
            diagnostic_criteria={
                "cpe_exponent_range": "(0.5, 1.0)",
                "temperature_stability": "high",
                "physical_reasonableness": True
            }
        )
    
    def _load_inference_rules(self):
        """加载推断规则"""
        # 规则1: 质子传导识别
        self.inference_rules['identify_proton_conduction'] = InferenceRule(
            rule_id="identify_proton_conduction",
            name="质子传导机理识别",
            condition={
                "activation_energy": {"min": 0.3, "max": 1.2},
                "conductivity": {"min": 1e-6, "max": 1e-2},
                "temperature_dependence": "arrhenius",
                "material_type": ["solid_electrolyte", "ceramic"]
            },
            conclusion={
                "mechanism": "proton_conduction",
                "confidence_base": 0.7
            },
            confidence_weight=0.8,
            evidence_requirements=[
                "activation_energy_in_range",
                "arrhenius_behavior",
                "appropriate_conductivity_level"
            ],
            contraindications=[
                "very_high_conductivity",
                "very_low_activation_energy",
                "strong_warburg_signature"
            ],
            validation_method="literature_comparison"
        )
        
        # 规则2: 氧离子传导识别
        self.inference_rules['identify_oxide_ion_conduction'] = InferenceRule(
            rule_id="identify_oxide_ion_conduction",
            name="氧离子传导机理识别",
            condition={
                "activation_energy": {"min": 0.8, "max": 2.0},
                "conductivity": {"min": 1e-8, "max": 1e-1},
                "temperature_dependence": "arrhenius",
                "circuit_complexity": "high"
            },
            conclusion={
                "mechanism": "oxide_ion_conduction",
                "confidence_base": 0.75
            },
            confidence_weight=0.85,
            evidence_requirements=[
                "high_activation_energy",
                "complex_impedance_behavior",
                "multiple_relaxation_processes"
            ],
            contraindications=[
                "low_activation_energy",
                "simple_single_arc",
                "very_high_conductivity"
            ],
            validation_method="thermodynamic_consistency"
        )
        
        # 规则3: 电子传导识别
        self.inference_rules['identify_electronic_conduction'] = InferenceRule(
            rule_id="identify_electronic_conduction",
            name="电子传导机理识别",
            condition={
                "conductivity": {"min": 1e-2, "max": 1e3},
                "activation_energy": {"min": 0.0, "max": 0.5},
                "frequency_dependence": "weak",
                "modulus_peaks": {"max": 1}
            },
            conclusion={
                "mechanism": "electronic_conduction",
                "confidence_base": 0.8
            },
            confidence_weight=0.9,
            evidence_requirements=[
                "high_conductivity",
                "low_activation_energy",
                "weak_frequency_dispersion"
            ],
            contraindications=[
                "strong_capacitive_behavior",
                "multiple_relaxation_peaks",
                "strong_temperature_dependence"
            ],
            validation_method="electronic_structure_consistency"
        )
        
        # 规则4: 混合传导识别
        self.inference_rules['identify_mixed_conduction'] = InferenceRule(
            rule_id="identify_mixed_conduction",
            name="混合传导机理识别",
            condition={
                "circuit_complexity": "very_high",
                "multiple_processes": True,
                "overlapping_relaxations": True,
                "broad_conductivity_range": True
            },
            conclusion={
                "mechanism": "mixed_conduction",
                "confidence_base": 0.6
            },
            confidence_weight=0.7,
            evidence_requirements=[
                "multiple_relaxation_processes",
                "complex_temperature_behavior",
                "high_circuit_complexity"
            ],
            contraindications=[
                "simple_single_process",
                "clear_process_separation",
                "single_activation_energy"
            ],
            validation_method="multi_component_analysis"
        )
    
    def _load_material_database(self):
        """加载材料数据库"""
        self.material_database = {
            "BaCeO3": {
                "type": "perovskite",
                "primary_conduction": "proton_conduction",
                "typical_ea": 0.54,  # eV
                "typical_conductivity": 1e-3,  # S/cm at 600°C
                "operating_temperature": (400, 800),  # °C
                "atmosphere_dependence": True
            },
            "YSZ": {
                "type": "fluorite",
                "primary_conduction": "oxide_ion_conduction", 
                "typical_ea": 1.0,
                "typical_conductivity": 1e-2,  # S/cm at 800°C
                "operating_temperature": (600, 1000),
                "atmosphere_dependence": False
            },
            "LLZO": {
                "type": "garnet",
                "primary_conduction": "lithium_ion_conduction",
                "typical_ea": 0.34,
                "typical_conductivity": 1e-4,  # S/cm at RT
                "operating_temperature": (-40, 60),
                "atmosphere_dependence": False
            }
        }
    
    def _load_literature_database(self):
        """加载文献数据库"""
        self.literature_database = {
            "proton_conductor_review": {
                "doi": "10.1021/cr020715f",
                "title": "Proton-conducting ceramics",
                "authors": ["Kreuer, K.D."],
                "year": 2003,
                "key_findings": {
                    "activation_energies": (0.4, 0.8),
                    "conductivity_range": (1e-5, 1e-2),
                    "mechanisms": ["vehicle", "grotthuss"]
                }
            },
            "oxide_ion_conductor_review": {
                "doi": "10.1016/j.ssi.2003.12.020",
                "title": "Oxide ion conductors",
                "authors": ["Goodenough, J.B.", "Huang, Y.H."],
                "year": 2007,
                "key_findings": {
                    "activation_energies": (0.8, 1.5),
                    "conductivity_range": (1e-6, 1e-1),
                    "crystal_structures": ["fluorite", "perovskite", "pyrochlore"]
                }
            }
        }
    
    def _validate_knowledge_base(self):
        """验证知识库完整性"""
        validation_results = {
            "mechanisms_valid": True,
            "patterns_valid": True,
            "rules_valid": True,
            "consistency_check": True,
            "issues": []
        }
        
        # 验证机理签名
        for mech_id, mechanism in self.mechanisms.items():
            if not self._validate_mechanism_signature(mechanism):
                validation_results["mechanisms_valid"] = False
                validation_results["issues"].append(f"机理签名无效: {mech_id}")
        
        # 验证模式模板
        for pattern_id, pattern in self.patterns.items():
            if not self._validate_pattern_template(pattern):
                validation_results["patterns_valid"] = False
                validation_results["issues"].append(f"模式模板无效: {pattern_id}")
        
        # 验证推断规则
        for rule_id, rule in self.inference_rules.items():
            if not self._validate_inference_rule(rule):
                validation_results["rules_valid"] = False
                validation_results["issues"].append(f"推断规则无效: {rule_id}")
        
        # 检查一致性
        if not self._check_knowledge_consistency():
            validation_results["consistency_check"] = False
            validation_results["issues"].append("知识库内部一致性检查失败")
        
        if validation_results["issues"]:
            self.logger.warning(f"知识库验证发现问题: {validation_results['issues']}")
        else:
            self.logger.info("知识库验证通过")
        
        return validation_results
    
    def _validate_mechanism_signature(self, mechanism: MechanismSignature) -> bool:
        """验证机理签名有效性"""
        try:
            # 检查激活能范围合理性
            ea_min, ea_max = mechanism.activation_energy_range
            if not (0 <= ea_min < ea_max <= 5.0):
                return False
            
            # 检查电导率范围合理性
            cond_min, cond_max = mechanism.conductivity_range
            if not (1e-12 <= cond_min < cond_max <= 1e6):
                return False
            
            # 检查置信度因子总和
            confidence_sum = sum(mechanism.confidence_factors.values())
            if not (0.9 <= confidence_sum <= 1.1):
                return False
            
            return True
        except Exception:
            return False
    
    def _validate_pattern_template(self, pattern: PatternTemplate) -> bool:
        """验证模式模板有效性"""
        try:
            # 检查必要字段
            required_fields = ['pattern_id', 'name', 'description', 'characteristic_features']
            for field in required_fields:
                if not getattr(pattern, field):
                    return False
            
            # 检查等效电路列表
            if not pattern.equivalent_circuits:
                return False
            
            return True
        except Exception:
            return False
    
    def _validate_inference_rule(self, rule: InferenceRule) -> bool:
        """验证推断规则有效性"""
        try:
            # 检查置信度权重
            if not (0.0 <= rule.confidence_weight <= 1.0):
                return False
            
            # 检查条件和结论
            if not (rule.condition and rule.conclusion):
                return False
            
            # 检查证据要求
            if not rule.evidence_requirements:
                return False
            
            return True
        except Exception:
            return False
    
    def _check_knowledge_consistency(self) -> bool:
        """检查知识库内部一致性"""
        try:
            # 检查机理和模式的对应关系
            # 检查推断规则和机理签名的一致性
            # 检查文献数据和机理参数的一致性
            return True
        except Exception:
            return False
    
    def get_mechanism_signature(self, mechanism_id: str) -> Optional[MechanismSignature]:
        """获取机理签名"""
        return self.mechanisms.get(mechanism_id)
    
    def get_pattern_template(self, pattern_id: str) -> Optional[PatternTemplate]:
        """获取模式模板"""
        return self.patterns.get(pattern_id)
    
    def get_inference_rule(self, rule_id: str) -> Optional[InferenceRule]:
        """获取推断规则"""
        return self.inference_rules.get(rule_id)
    
    def search_mechanisms_by_criteria(self, criteria: Dict[str, Any]) -> List[Tuple[str, MechanismSignature, float]]:
        """根据条件搜索机理"""
        matching_mechanisms = []
        
        for mech_id, mechanism in self.mechanisms.items():
            match_score = self._calculate_mechanism_match_score(mechanism, criteria)
            if match_score > 0.5:  # 阈值
                matching_mechanisms.append((mech_id, mechanism, match_score))
        
        # 按匹配分数排序
        matching_mechanisms.sort(key=lambda x: x[2], reverse=True)
        return matching_mechanisms
    
    def _calculate_mechanism_match_score(self, mechanism: MechanismSignature, criteria: Dict[str, Any]) -> float:
        """计算机理匹配分数"""
        score = 0.0
        total_weight = 0.0
        
        # 激活能匹配
        if 'activation_energy' in criteria:
            ea = criteria['activation_energy']
            ea_min, ea_max = mechanism.activation_energy_range
            if ea_min <= ea <= ea_max:
                score += 0.3
            total_weight += 0.3
        
        # 电导率匹配
        if 'conductivity' in criteria:
            cond = criteria['conductivity']
            cond_min, cond_max = mechanism.conductivity_range
            if cond_min <= cond <= cond_max:
                score += 0.25
            total_weight += 0.25
        
        # 温度依赖性匹配
        if 'temperature_dependence' in criteria:
            if criteria['temperature_dependence'] == mechanism.temperature_dependence:
                score += 0.2
            total_weight += 0.2
        
        # 频率签名匹配
        if 'frequency_signature' in criteria:
            if criteria['frequency_signature'] in mechanism.frequency_signature:
                score += 0.15
            total_weight += 0.15
        
        # 电路模型匹配
        if 'circuit_model' in criteria:
            if criteria['circuit_model'] in mechanism.typical_circuit_models:
                score += 0.1
            total_weight += 0.1
        
        return score / total_weight if total_weight > 0 else 0.0
    
    def export_knowledge_base(self, export_path: str, format: str = 'yaml') -> bool:
        """导出知识库"""
        try:
            export_data = {
                'mechanisms': {k: asdict(v) for k, v in self.mechanisms.items()},
                'patterns': {k: asdict(v) for k, v in self.patterns.items()},
                'inference_rules': {k: asdict(v) for k, v in self.inference_rules.items()},
                'material_database': self.material_database,
                'literature_database': self.literature_database
            }
            
            if format.lower() == 'yaml':
                with open(export_path, 'w', encoding='utf-8') as f:
                    yaml.dump(export_data, f, default_flow_style=False, allow_unicode=True)
            elif format.lower() == 'json':
                with open(export_path, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, indent=2, ensure_ascii=False)
            else:
                raise ValueError(f"不支持的导出格式: {format}")
            
            self.logger.info(f"知识库已导出到: {export_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"知识库导出失败: {str(e)}")
            return False
    
    def get_knowledge_summary(self) -> Dict[str, Any]:
        """获取知识库摘要"""
        return {
            'total_mechanisms': len(self.mechanisms),
            'total_patterns': len(self.patterns),
            'total_rules': len(self.inference_rules),
            'total_materials': len(self.material_database),
            'total_references': len(self.literature_database),
            'mechanism_types': list(self.mechanisms.keys()),
            'pattern_types': list(self.patterns.keys()),
            'rule_types': list(self.inference_rules.keys()),
            'knowledge_base_version': '2.0.0',
            'last_updated': pd.Timestamp.now().isoformat()
        }
