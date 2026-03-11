# -*- coding: utf-8 -*-
"""
机理推断引擎 - 基于EIS特征的物理机理智能推断
"""
import os
import numpy as np
import json
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from enum import Enum
import logging

class ConductionMechanism(Enum):
    """传导机理类型"""
    IONIC = "ionic"
    ELECTRONIC = "electronic"
    MIXED = "mixed"
    PROTON = "proton"
    OXIDE_ION = "oxide_ion"
    UNKNOWN = "unknown"

class PhysicalProcess(Enum):
    """物理过程类型"""
    BULK_CONDUCTION = "bulk_conduction"
    GRAIN_BOUNDARY = "grain_boundary"
    ELECTRODE_REACTION = "electrode_reaction"
    DIFFUSION = "diffusion"
    CHARGE_TRANSFER = "charge_transfer"
    DOUBLE_LAYER = "double_layer"
    UNKNOWN = "unknown"

@dataclass
class EISFeature:
    """EIS特征描述"""
    feature_type: str
    value: float
    frequency_range: Tuple[float, float]
    confidence: float
    description: str

@dataclass
class MechanismHypothesis:
    """机理假设"""
    mechanism: ConductionMechanism
    process: PhysicalProcess
    confidence: float
    evidence: List[str]
    equivalent_circuit: str
    description: str
    parameters: Dict[str, Any]

class MechanismInferenceEngine:
    """机理推断引擎"""
    
    def __init__(self, knowledge_base_path: Optional[str] = None):
        """
        初始化机理推断引擎
        
        Args:
            knowledge_base_path: 知识库文件路径
        """
        self.knowledge_base = self._load_knowledge_base(knowledge_base_path)
        self.inference_rules = self._initialize_inference_rules()
        self.logger = logging.getLogger(__name__)
    
    def _load_knowledge_base(self, path: Optional[str]) -> Dict:
        """加载知识库"""
        default_kb = {
            "material_signatures": {
                "proton_conductor": {
                    "activation_energy_range": (0.3, 1.2),  # eV
                    "conductivity_range": (1e-6, 1e-2),     # S/cm
                    "frequency_dependence": "debye_like",
                    "temperature_dependence": "arrhenius"
                },
                "oxide_ion_conductor": {
                    "activation_energy_range": (0.8, 2.0),
                    "conductivity_range": (1e-8, 1e-1),
                    "frequency_dependence": "universal_dielectric",
                    "temperature_dependence": "arrhenius"
                },
                "electronic_conductor": {
                    "activation_energy_range": (0.0, 0.5),
                    "conductivity_range": (1e-2, 1e3),
                    "frequency_dependence": "nearly_flat",
                    "temperature_dependence": "weak"
                }
            },
            "circuit_patterns": {
                "single_debye": {
                    "circuit": "R(RC)",
                    "mechanism": "bulk_ionic_conduction",
                    "signature": "single_semicircle"
                },
                "double_debye": {
                    "circuit": "R(RC)(RC)",
                    "mechanism": "bulk_and_grain_boundary",
                    "signature": "two_semicircles"
                },
                "warburg": {
                    "circuit": "R(RC)W",
                    "mechanism": "diffusion_limited",
                    "signature": "45_degree_tail"
                },
                "cpe": {
                    "circuit": "R(R-CPE)",
                    "mechanism": "non_ideal_capacitance",
                    "signature": "depressed_semicircle"
                }
            }
        }
        
        if path and os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    loaded_kb = json.load(f)
                    default_kb.update(loaded_kb)
            except Exception as e:
                self.logger.warning(f"知识库加载失败，使用默认知识库: {e}")
        
        return default_kb
    
    def _initialize_inference_rules(self) -> List[Dict]:
        """
        初始化推断规则（适配Dict格式特征）
        
        修改说明：将原有的EISFeature对象访问改为Dict访问
        """
        def get_feature_value(features: Dict, category: str, feature_name: str, default=None):
            """从Dict格式特征中提取值"""
            return features.get(category, {}).get(feature_name, default)
        
        return [
            # 激活能相关规则（扩展）
            {
                "rule_id": "very_low_activation_energy",
                "condition": lambda features: (
                    0.1 <= get_feature_value(features, 'kinetic_features', 'overall_ea_mean', 0) < 0.3
                ),
                "inference": {
                    "mechanism": ConductionMechanism.PROTON,
                    "confidence": 0.75,
                    "evidence": ["低激活能(0.1-0.3eV)表明快速质子传导或表面传导"]
                }
            },
            {
                "rule_id": "low_temperature_activation",
                "condition": lambda features: (
                    0.3 <= get_feature_value(features, 'kinetic_features', 'overall_ea_mean', 0) <= 0.6
                ),
                "inference": {
                    "mechanism": ConductionMechanism.PROTON,
                    "confidence": 0.9,
                    "evidence": ["中低激活能(0.3-0.6eV)表明质子传导机理(Grotthuss机制)"]
                }
            },
            {
                "rule_id": "medium_activation_energy",
                "condition": lambda features: (
                    0.6 < get_feature_value(features, 'kinetic_features', 'overall_ea_mean', 0) <= 1.2
                ),
                "inference": {
                    "mechanism": ConductionMechanism.PROTON,
                    "confidence": 0.85,
                    "evidence": ["中等激活能(0.6-1.2eV)表明质子传导机理(Vehicle机制或受阻传导)"]
                }
            },
            {
                "rule_id": "high_activation_energy",
                "condition": lambda features: (
                    1.2 < get_feature_value(features, 'kinetic_features', 'overall_ea_mean', 0) <= 2.0
                ),
                "inference": {
                    "mechanism": ConductionMechanism.OXIDE_ION,
                    "confidence": 0.85,
                    "evidence": ["高激活能(1.2-2.0eV)表明氧离子传导机理"]
                }
            },
            {
                "rule_id": "very_high_activation_energy",
                "condition": lambda features: (
                    get_feature_value(features, 'kinetic_features', 'overall_ea_mean', 0) > 2.0
                ),
                "inference": {
                    "mechanism": ConductionMechanism.OXIDE_ION,
                    "confidence": 0.9,
                    "evidence": ["极高激活能(>2.0eV)表明氧离子传导或晶格缺陷传导"]
                }
            },
            
            # 阻抗特征规则
            {
                "rule_id": "high_frequency_resistance",
                "condition": lambda features: (
                    get_feature_value(features, 'impedance_features', 'high_freq_resistance', 0) > 1e6
                ),
                "inference": {
                    "mechanism": ConductionMechanism.IONIC,
                    "confidence": 0.8,
                    "evidence": ["高频电阻值表明离子传导机理"]
                }
            },
            {
                "rule_id": "single_semicircle",
                "condition": lambda features: (
                    get_feature_value(features, 'impedance_features', 'semicircle_count', 0) == 1
                ),
                "inference": {
                    "process": PhysicalProcess.BULK_CONDUCTION,
                    "confidence": 0.7,
                    "evidence": ["单一半圆弧表明体相传导过程"]
                }
            },
            {
                "rule_id": "double_semicircle", 
                "condition": lambda features: (
                    get_feature_value(features, 'impedance_features', 'semicircle_count', 0) == 2
                ),
                "inference": {
                    "process": PhysicalProcess.GRAIN_BOUNDARY,
                    "confidence": 0.8,
                    "evidence": ["双半圆弧表明体相和晶界传导过程"]
                }
            },
            {
                "rule_id": "warburg_diffusion",
                "condition": lambda features: (
                    get_feature_value(features, 'impedance_features', 'warburg_element_present', False)
                ),
                "inference": {
                    "process": PhysicalProcess.DIFFUSION,
                    "confidence": 0.8,
                    "evidence": ["Warburg阻抗表明扩散限制过程"]
                }
            },
            
            # 多分段Arrhenius规则
            {
                "rule_id": "multiple_arrhenius_segments",
                "condition": lambda features: (
                    get_feature_value(features, 'kinetic_features', 'arrhenius_segment_count', 0) >= 3
                ),
                "inference": {
                    "process": PhysicalProcess.BULK_CONDUCTION,
                    "confidence": 0.75,
                    "evidence": ["多分段Arrhenius行为表明存在相变或传导机制转变"]
                }
            },
            
            # 高质量拟合规则
            {
                "rule_id": "high_quality_arrhenius_fit",
                "condition": lambda features: (
                    get_feature_value(features, 'kinetic_features', 'arrhenius_r_squared_mean', 0) > 0.98
                ),
                "inference": {
                    "mechanism": ConductionMechanism.IONIC,
                    "confidence": 0.7,
                    "evidence": ["高质量Arrhenius拟合(R²>0.98)表明单一传导机理"]
                }
            },
            
            # 复合特征规则
            {
                "rule_id": "solid_electrolyte_signature",
                "condition": lambda features: (
                    get_feature_value(features, 'composite_features', 'material_type_signature', '') == 'solid_electrolyte'
                ),
                "inference": {
                    "mechanism": ConductionMechanism.IONIC,
                    "confidence": 0.8,
                    "evidence": ["材料特征表明固体电解质类型"]
                }
            },
            {
                "rule_id": "ionic_conduction_dominant",
                "condition": lambda features: (
                    get_feature_value(features, 'composite_features', 'dominant_physical_process', '') == 'ionic_conduction'
                ),
                "inference": {
                    "mechanism": ConductionMechanism.IONIC,
                    "confidence": 0.85,
                    "evidence": ["主导物理过程为离子传导"]
                }
            }
        ]
    
    def extract_features(self, analysis_results: Dict) -> List[EISFeature]:
        """从分析结果中提取特征"""
        features = []
        
        # 从阻抗拟合结果提取特征
        if 'impedance_fitting' in analysis_results:
            fitting_result = analysis_results['impedance_fitting']
            
            # 高频电阻
            if 'R_inf' in fitting_result:
                features.append(EISFeature(
                    feature_type="high_freq_resistance",
                    value=fitting_result['R_inf'],
                    frequency_range=(1e6, 1e8),
                    confidence=0.9,
                    description="高频极限电阻"
                ))
            
            # 半圆弧数量
            if 'circuit_elements' in fitting_result:
                rc_count = sum(1 for elem in fitting_result['circuit_elements'] 
                             if elem.get('type') == 'RC')
                features.append(EISFeature(
                    feature_type="semicircle_count",
                    value=rc_count,
                    frequency_range=(1e-2, 1e6),
                    confidence=0.8,
                    description=f"检测到{rc_count}个RC元件"
                ))
        
        # 从阿伦尼乌斯分析提取特征
        if 'arrhenius_analysis' in analysis_results:
            arrhenius_result = analysis_results['arrhenius_analysis']
            
            if 'activation_energy' in arrhenius_result:
                features.append(EISFeature(
                    feature_type="activation_energy",
                    value=arrhenius_result['activation_energy'],
                    frequency_range=(0, 0),  # 不依赖频率
                    confidence=arrhenius_result.get('r_squared', 0.5),
                    description=f"激活能: {arrhenius_result['activation_energy']:.2f} eV"
                ))
        
        # 从模量分析提取特征
        if 'modulus_analysis' in analysis_results:
            modulus_result = analysis_results['modulus_analysis']
            
            if 'peaks' in modulus_result:
                peak_count = len(modulus_result['peaks'])
                features.append(EISFeature(
                    feature_type="modulus_peaks",
                    value=peak_count,
                    frequency_range=(1e-2, 1e6),
                    confidence=0.7,
                    description=f"模量谱检测到{peak_count}个峰"
                ))
        
        # 从DRT分析提取特征
        if 'drt_analysis' in analysis_results:
            drt_result = analysis_results['drt_analysis']
            
            if 'peaks' in drt_result:
                peak_count = len(drt_result['peaks'])
                features.append(EISFeature(
                    feature_type="drt_peaks",
                    value=peak_count,
                    frequency_range=(1e-2, 1e6),
                    confidence=0.8,
                    description=f"DRT分析检测到{peak_count}个弛豫过程"
                ))
        
        return features
    
    def infer_mechanisms(self, comprehensive_features: Dict, phase1_results: Dict) -> Dict:
        """
        从综合特征推断机理
        
        Args:
            comprehensive_features: 高级特征提取结果
            phase1_results: Phase 1分析结果
            
        Returns:
            机理推断结果字典
        """
        # 转换为EISFeature格式
        eis_features = self._convert_to_eis_features(comprehensive_features)
        
        # 执行机理推断
        mechanism_hypotheses = self.infer_mechanism(eis_features)
        
        # 格式化输出结果
        if mechanism_hypotheses:
            primary = mechanism_hypotheses[0]
            alternatives = mechanism_hypotheses[1:3] if len(mechanism_hypotheses) > 1 else []
            
            return {
                'primary_mechanism': {
                    'mechanism': primary.mechanism.value,
                    'process': primary.process.value,
                    'confidence': primary.confidence,
                    'evidence': primary.evidence,
                    'equivalent_circuit': primary.equivalent_circuit,
                    'description': primary.description
                },
                'alternative_mechanisms': [
                    {
                        'mechanism': alt.mechanism.value,
                        'process': alt.process.value,
                        'confidence': alt.confidence,
                        'evidence': alt.evidence[:2]  # 简化证据
                    }
                    for alt in alternatives
                ],
                'analysis_summary': {
                    'total_hypotheses': len(mechanism_hypotheses),
                    'high_confidence_count': sum(1 for h in mechanism_hypotheses if h.confidence > 0.7),
                    'inference_quality': 'high' if mechanism_hypotheses[0].confidence > 0.8 else 'moderate'
                }
            }
        else:
            return {
                'primary_mechanism': None,
                'alternative_mechanisms': [],
                'analysis_summary': {
                    'total_hypotheses': 0,
                    'high_confidence_count': 0,
                    'inference_quality': 'failed'
                }
            }
    
    def _convert_to_eis_features(self, comprehensive_features: Dict) -> List[EISFeature]:
        """将综合特征转换为EISFeature格式"""
        eis_features = []
        
        # 从阻抗特征提取
        if 'impedance_features' in comprehensive_features:
            imp_features = comprehensive_features['impedance_features']
            
            dc_r = imp_features.get('dc_resistance')
            if dc_r and not np.isnan(dc_r):
                eis_features.append(EISFeature(
                    feature_type='dc_resistance',
                    value=dc_r,
                    frequency_range=(0.1, 1.0),
                    confidence=0.9,
                    description=f'直流电阻: {dc_r:.2f} Ω'
                ))
        
        # 从模量特征提取
        if 'modulus_features' in comprehensive_features:
            mod_features = comprehensive_features['modulus_features']
            
            peak_count = mod_features.get('peak_count', 0)
            if peak_count > 0:
                eis_features.append(EISFeature(
                    feature_type='modulus_peak_count',
                    value=float(peak_count),
                    frequency_range=(1e2, 1e6),
                    confidence=0.8,
                    description=f'模量峰数量: {peak_count}'
                ))
        
        # 从电路特征提取
        if 'circuit_features' in comprehensive_features:
            circuit_features = comprehensive_features['circuit_features']
            
            model = circuit_features.get('best_circuit_model', 'unknown')
            r_squared = circuit_features.get('circuit_fitting_r_squared', 0)
            
            if r_squared > 0:
                eis_features.append(EISFeature(
                    feature_type='circuit_model',
                    value=r_squared,
                    frequency_range=(0.1, 1e6),
                    confidence=r_squared,
                    description=f'最佳电路模型: {model}'
                ))
        
        # 从温度特征提取
        if 'temperature_features' in comprehensive_features:
            temp_features = comprehensive_features['temperature_features']
            
            ea = temp_features.get('activation_energy')
            if ea and not np.isnan(ea):
                eis_features.append(EISFeature(
                    feature_type='activation_energy',
                    value=ea,
                    frequency_range=(0.1, 1e6),
                    confidence=0.9,
                    description=f'激活能: {ea:.2f} eV'
                ))
        
        return eis_features
    
    def infer_mechanism(self, features) -> Dict:
        """
        基于特征推断传导机理（适配Dict格式特征 + 规则权重系统）
        
        Args:
            features: Dict格式的特征（从AdvancedFeatureExtractor输出）
        
        Returns:
            推断结果Dict
        """
        # 定义规则权重（激活能规则优先级最高）
        rule_weights = {
            # 激活能规则（最高优先级）
            'very_low_activation_energy': 1.3,
            'low_temperature_activation': 1.4,
            'medium_activation_energy': 1.3,
            'high_activation_energy': 1.3,
            'very_high_activation_energy': 1.3,
            
            # 阻抗特征规则（中等优先级）
            'high_frequency_resistance': 1.0,
            'single_semicircle': 1.0,
            'double_semicircle': 1.1,
            'warburg_diffusion': 1.0,
            
            # 多分段和拟合质量规则（中等优先级）
            'multiple_arrhenius_segments': 1.0,
            'high_quality_arrhenius_fit': 0.9,
            
            # 复合特征规则（较低优先级）
            'solid_electrolyte_signature': 0.7,
            'ionic_conduction_dominant': 0.7
        }
        
        hypotheses = []
        
        # 应用推断规则
        for rule in self.inference_rules:
            try:
                if rule["condition"](features):
                    inference = rule["inference"]
                    
                    # 应用权重调整置信度
                    weight = rule_weights.get(rule['rule_id'], 1.0)
                    adjusted_confidence = inference["confidence"] * weight
                    adjusted_confidence = min(adjusted_confidence, 1.0)  # 不超过1.0
                    
                    hypothesis = MechanismHypothesis(
                        mechanism=inference.get("mechanism", ConductionMechanism.UNKNOWN),
                        process=inference.get("process", PhysicalProcess.UNKNOWN),
                        confidence=adjusted_confidence,
                        evidence=inference["evidence"],
                        equivalent_circuit="",  # 稍后填充
                        description="",  # 稍后填充
                        parameters={}
                    )
                    
                    hypotheses.append(hypothesis)
            except Exception as e:
                self.logger.warning(f"规则 {rule['rule_id']} 应用失败: {e}")
                continue
        
        # 合并和排序假设
        hypotheses = self._merge_hypotheses(hypotheses)
        hypotheses.sort(key=lambda h: h.confidence, reverse=True)
        
        # 为每个假设添加等效电路和描述
        for hypothesis in hypotheses:
            hypothesis.equivalent_circuit = self._suggest_equivalent_circuit(hypothesis, features)
            hypothesis.description = self._generate_mechanism_description(hypothesis)
        
        # 转换为Dict格式返回
        if hypotheses:
            primary = hypotheses[0]
            return {
                'primary_mechanism': primary.mechanism.value,
                'primary_process': primary.process.value,
                'confidence': primary.confidence,
                'evidence': primary.evidence,
                'equivalent_circuit': primary.equivalent_circuit,
                'description': primary.description,
                'alternative_hypotheses': [
                    {
                        'mechanism': h.mechanism.value,
                        'process': h.process.value,
                        'confidence': h.confidence,
                        'evidence': h.evidence
                    }
                    for h in hypotheses[1:3]
                ]
            }
        else:
            return {
                'primary_mechanism': 'unknown',
                'primary_process': 'unknown',
                'confidence': 0.0,
                'evidence': ['未找到匹配的推断规则'],
                'equivalent_circuit': 'Rs(RC)',
                'description': '无法确定传导机理',
                'alternative_hypotheses': []
            }
    
    def _merge_hypotheses(self, hypotheses: List[MechanismHypothesis]) -> List[MechanismHypothesis]:
        """合并相似的假设"""
        merged = {}
        
        for hyp in hypotheses:
            key = (hyp.mechanism, hyp.process)
            
            if key in merged:
                # 合并证据和提高置信度
                merged[key].evidence.extend(hyp.evidence)
                merged[key].confidence = min(1.0, merged[key].confidence + hyp.confidence * 0.1)
            else:
                merged[key] = hyp
        
        return list(merged.values())
    
    def _suggest_equivalent_circuit(self, hypothesis: MechanismHypothesis, 
                                  features: Dict) -> str:
        """为假设建议等效电路（适配Dict格式特征）"""
        # 基于机理和过程类型建议电路
        if hypothesis.mechanism == ConductionMechanism.PROTON:
            if hypothesis.process == PhysicalProcess.BULK_CONDUCTION:
                return "Rs(RbCb)"
            elif hypothesis.process == PhysicalProcess.GRAIN_BOUNDARY:
                return "Rs(RbCb)(RgbCgb)"
        
        elif hypothesis.mechanism == ConductionMechanism.OXIDE_ION:
            return "Rs(RbCb)(RgbCgb)W"
        
        elif hypothesis.mechanism == ConductionMechanism.ELECTRONIC:
            return "Rs + Rb"
        
        # 默认电路
        return "Rs(RC)"
    
    def _generate_mechanism_description(self, hypothesis: MechanismHypothesis) -> str:
        """生成机理描述"""
        descriptions = {
            ConductionMechanism.PROTON: "质子传导机理：质子通过材料中的氢键网络或空位机制进行传输",
            ConductionMechanism.OXIDE_ION: "氧离子传导机理：氧离子通过晶格空位进行长程迁移",
            ConductionMechanism.ELECTRONIC: "电子传导机理：电子或空穴载流子传导",
            ConductionMechanism.MIXED: "混合传导机理：同时存在离子和电子传导",
            ConductionMechanism.IONIC: "离子传导机理：离子载流子主导的传导过程"
        }
        
        process_descriptions = {
            PhysicalProcess.BULK_CONDUCTION: "体相传导过程",
            PhysicalProcess.GRAIN_BOUNDARY: "晶界效应显著",
            PhysicalProcess.DIFFUSION: "扩散限制过程",
            PhysicalProcess.ELECTRODE_REACTION: "电极反应过程"
        }
        
        desc = descriptions.get(hypothesis.mechanism, "未知机理")
        if hypothesis.process != PhysicalProcess.UNKNOWN:
            desc += f"，{process_descriptions.get(hypothesis.process, '')}"
        
        return desc
    
    def calculate_confidence_score(self, hypothesis: MechanismHypothesis, 
                                 features: List[EISFeature]) -> float:
        """计算假设的总体置信度"""
        base_confidence = hypothesis.confidence
        
        # 基于特征一致性调整置信度
        consistency_bonus = 0
        feature_count = len([f for f in features if f.confidence > 0.5])
        
        if feature_count >= 3:
            consistency_bonus = 0.1
        elif feature_count >= 2:
            consistency_bonus = 0.05
        
        # 基于证据数量调整
        evidence_bonus = min(0.1, len(hypothesis.evidence) * 0.02)
        
        final_confidence = min(1.0, base_confidence + consistency_bonus + evidence_bonus)
        return final_confidence
    
    def generate_inference_report(self, hypotheses: List[MechanismHypothesis], 
                                features: List[EISFeature]) -> str:
        """生成机理推断报告"""
        report = [
            "EIS机理推断分析报告",
            "=" * 40,
            "",
            "检测到的特征:",
        ]
        
        for i, feature in enumerate(features, 1):
            report.append(f"  {i}. {feature.description} (置信度: {feature.confidence:.2f})")
        
        report.extend([
            "",
            "机理推断结果:",
            ""
        ])
        
        for i, hyp in enumerate(hypotheses, 1):
            final_confidence = self.calculate_confidence_score(hyp, features)
            
            report.extend([
                f"假设 {i}: {hyp.mechanism.value} - {hyp.process.value}",
                f"  置信度: {final_confidence:.3f}",
                f"  描述: {hyp.description}",
                f"  建议等效电路: {hyp.equivalent_circuit}",
                f"  支持证据:",
            ])
            
            for evidence in hyp.evidence:
                report.append(f"    • {evidence}")
            
            report.append("")
        
        # 添加建议
        if hypotheses:
            best_hypothesis = hypotheses[0]
            best_confidence = self.calculate_confidence_score(best_hypothesis, features)
            
            report.extend([
                "推荐结论:",
                f"  最可能的机理: {best_hypothesis.mechanism.value}",
                f"  主要过程: {best_hypothesis.process.value}",
                f"  置信度: {best_confidence:.3f}",
                ""
            ])
            
            if best_confidence < 0.6:
                report.extend([
                    "注意:",
                    "  置信度较低，建议:",
                    "  • 增加更多温度点的测量",
                    "  • 进行不同气氛下的测试",
                    "  • 结合其他表征手段验证",
                    ""
                ])
        
        return "\n".join(report)
    
    def export_knowledge_base(self, path: str):
        """导出知识库"""
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(self.knowledge_base, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.error(f"知识库导出失败: {e}")
    
    def update_knowledge_base(self, new_knowledge: Dict):
        """更新知识库"""
        self.knowledge_base.update(new_knowledge)
        self.logger.info("知识库已更新")

