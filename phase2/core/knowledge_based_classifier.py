# -*- coding: utf-8 -*-
"""
基于知识库的质子传导机制分类器 V3
多指标综合判断 + 文献支撑 + 置信度量化
"""
import yaml
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import logging

class KnowledgeBasedMechanismClassifier:
    """
    基于知识库的机制分类器V3
    
    改进点：
    1. 基于5篇权威文献的阈值
    2. 5条规则综合判断（加权投票）
    3. 量化置信度计算
    4. 结合材料组成信息
    """
    
    def __init__(self, knowledge_base_dir: str = "phase2/knowledge"):
        """
        初始化分类器
        
        Args:
            knowledge_base_dir: 知识库目录路径
        """
        self.logger = logging.getLogger(__name__)
        self.kb_dir = Path(knowledge_base_dir)
        
        # 加载知识库
        self.mechanism_kb = self._load_yaml('proton_conduction_mechanisms.yaml')
        self.composition_kb = self._load_yaml('composition_performance_relationships.yaml')
        self.material_compositions = self._load_json('material_compositions.json')
        
        # 提取分类规则
        self.classification_rules = self.mechanism_kb['classification_rules']
        
        self.logger.info("知识库加载完成")
    
    def _load_yaml(self, filename: str) -> Dict:
        """加载YAML知识库"""
        filepath = self.kb_dir / filename
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            self.logger.error(f"知识库文件不存在: {filepath}")
            return {}
        except Exception as e:
            self.logger.error(f"加载知识库失败: {e}")
            return {}
    
    def _load_json(self, filename: str) -> Dict:
        """加载JSON数据"""
        filepath = self.kb_dir / filename
        try:
            import json
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            self.logger.warning(f"材料组成数据不存在: {filepath}")
            return {}
        except Exception as e:
            self.logger.warning(f"加载材料组成数据失败: {e}")
            return {}
    
    def classify(self, phase1_data: Dict) -> Dict:
        """
        分类主函数
        
        Args:
            phase1_data: Phase1分析结果
            
        Returns:
            分类结果（包含机制、置信度、证据等）
        """
        sample_id = phase1_data.get('metadata', {}).get('sample_id', 'unknown')
        
        # 提取特征
        features = self._extract_features(phase1_data, sample_id)
        
        # 应用5条规则
        rule_results = {}
        for rule_name, rule_config in self.classification_rules.items():
            result = self._apply_rule(rule_name, rule_config, features)
            rule_results[rule_name] = result
        
        # 加权投票
        final_mechanism, final_confidence = self._weighted_voting(rule_results)
        
        # 生成证据
        evidence = self._generate_evidence(rule_results, features)
        
        # 生成详细解释
        explanation = self._generate_explanation(
            final_mechanism, final_confidence, rule_results, features
        )
        
        return {
            'sample_id': sample_id,
            'mechanism': final_mechanism,
            'confidence': final_confidence,
            'rule_results': rule_results,
            'evidence': evidence,
            'explanation': explanation,
            'features_used': features
        }
    
    def _extract_features(self, phase1_data: Dict, sample_id: str) -> Dict:
        """提取分类所需特征"""
        features = {}
        
        # 1. 激活能特征
        arrhenius = phase1_data.get('arrhenius_analysis', {})
        features['ea_mean'] = arrhenius.get('ea_mean', 0)
        features['ea_std'] = arrhenius.get('ea_std', 0)
        features['ea_range'] = arrhenius.get('ea_range', [0, 0])
        features['num_segments'] = arrhenius.get('num_segments', 0)
        
        # 提取各分段Ea
        segments = arrhenius.get('segments', [])
        features['segment_eas'] = [seg.get('activation_energy_eV', 0) for seg in segments]
        features['segment_r2s'] = [seg.get('r_squared', 0) for seg in segments]
        
        # 2. DRT特征
        drt = phase1_data.get('drt_analysis', {})
        features['drt_num_peaks'] = drt.get('num_peaks', 0)
        features['drt_peaks'] = drt.get('peaks', [])
        
        # 判断DRT特征
        if features['drt_num_peaks'] == 1:
            features['drt_pattern'] = 'single_peak'
            if features['drt_peaks']:
                peak_tau = features['drt_peaks'][0].get('tau', 0)
                features['drt_peak_frequency'] = 1 / peak_tau if peak_tau > 0 else 0
        elif features['drt_num_peaks'] >= 2:
            features['drt_pattern'] = 'multiple_peaks'
        else:
            features['drt_pattern'] = 'no_peak'
        
        # 3. 温度分段特征
        if features['num_segments'] == 1:
            features['temperature_pattern'] = 'single_segment'
        elif features['num_segments'] >= 2:
            features['temperature_pattern'] = 'multiple_segments'
            # 计算Ea变化范围
            if len(features['segment_eas']) >= 2:
                features['ea_variation'] = max(features['segment_eas']) - min(features['segment_eas'])
        
        # 4. Modulus特征（如果有）
        modulus = phase1_data.get('modulus_analysis', {})
        features['has_modulus_peak'] = modulus.get('has_peak', False)
        
        # 5. 材料组成特征
        composition = self.material_compositions.get(sample_id, {})
        if composition:
            features['h2o_content'] = composition.get('h2o', {}).get('weight_pct', 0)
            features['h3po4_content'] = composition.get('h3po4', {}).get('weight_pct', 0)
            features['sepiolite_content'] = composition.get('sepiolite', {}).get('weight_pct', 0)
        else:
            features['h2o_content'] = 0
            features['h3po4_content'] = 0
            features['sepiolite_content'] = 0
        
        # 6. 数据质量特征
        quality = phase1_data.get('quality_metrics', {})
        features['kk_pass_rate'] = quality.get('kk_pass_rate', 0)
        features['arrhenius_r2_mean'] = quality.get('arrhenius_r_squared_mean', 0)
        
        return features
    
    def _apply_rule(self, rule_name: str, rule_config: Dict, features: Dict) -> Dict:
        """应用单条规则"""
        weight = rule_config.get('weight', 0)
        conditions = rule_config.get('conditions', [])
        
        # 检查每个条件
        for condition in conditions:
            if self._check_condition(condition, features):
                return {
                    'rule_name': rule_name,
                    'weight': weight,
                    'matched': True,
                    'conclusion': condition.get('conclusion', 'unknown'),
                    'confidence': condition.get('confidence', 0.5),
                    'literature': condition.get('literature', ''),
                    'rationale': condition.get('rationale', '')
                }
        
        # 无匹配条件
        return {
            'rule_name': rule_name,
            'weight': weight,
            'matched': False,
            'conclusion': 'unknown',
            'confidence': 0.0
        }
    
    def _check_condition(self, condition: Dict, features: Dict) -> bool:
        """检查条件是否满足"""
        condition_str = condition.get('condition', '')
        
        # Rule 1: Activation Energy
        if 'Ea' in condition_str:
            ea = features.get('ea_mean', 0)
            if '< 0.35' in condition_str:
                return ea < 0.35
            elif '>= 0.45' in condition_str:
                return ea >= 0.45
            elif '0.35 <= Ea < 0.45' in condition_str:
                return 0.35 <= ea < 0.45
        
        # Rule 2: DRT Features
        if 'single_peak' in condition_str:
            if features.get('drt_pattern') == 'single_peak':
                if 'peak_frequency > 1e3' in condition_str:
                    return features.get('drt_peak_frequency', 0) > 1e3
                return True
        
        if 'multiple_peaks' in condition_str:
            return features.get('drt_pattern') == 'multiple_peaks'
        
        if 'low_frequency_peak' in condition_str:
            # 简化：如果有多峰，假设有低频峰
            return features.get('drt_pattern') == 'multiple_peaks'
        
        # Rule 3: Temperature Segments
        if 'single_segment' in condition_str:
            if features.get('temperature_pattern') == 'single_segment':
                if 'Ea < 0.40' in condition_str:
                    return features.get('ea_mean', 0) < 0.40
                return True
        
        if 'multiple_segments' in condition_str:
            if features.get('temperature_pattern') == 'multiple_segments':
                if 'Ea_range > 0.30' in condition_str:
                    return features.get('ea_variation', 0) > 0.30
                return True
        
        if 'low_temp_segment_Ea' in condition_str:
            # 检查分段Ea
            segment_eas = features.get('segment_eas', [])
            if len(segment_eas) >= 2:
                return segment_eas[0] < 0.35 and segment_eas[-1] > 0.45
        
        # Rule 4: Modulus Analysis
        if 'strong_modulus_peak' in condition_str:
            return features.get('has_modulus_peak', False)
        
        if 'weak_or_no_modulus_peak' in condition_str:
            return not features.get('has_modulus_peak', False)
        
        # Rule 5: Material Composition
        if 'H2O_content' in condition_str:
            h2o = features.get('h2o_content', 0)
            if 'in [5, 15]' in condition_str:
                return 5 <= h2o <= 15
            elif '< 5' in condition_str:
                return h2o < 5
            elif '> 20' in condition_str:
                return h2o > 20
        
        if 'H3PO4_content' in condition_str:
            h3po4 = features.get('h3po4_content', 0)
            if '> 35' in condition_str:
                return h3po4 > 35
        
        return False
    
    def _weighted_voting(self, rule_results: Dict) -> Tuple[str, float]:
        """加权投票计算最终机制和置信度"""
        votes = {}  # {mechanism: weighted_confidence}
        
        for rule_name, result in rule_results.items():
            if not result['matched']:
                continue
            
            mechanism = result['conclusion']
            weight = result['weight']
            confidence = result['confidence']
            
            weighted_conf = weight * confidence
            
            if mechanism not in votes:
                votes[mechanism] = 0
            votes[mechanism] += weighted_conf
        
        if not votes:
            return 'unknown', 0.0
        
        # 找到得票最高的机制
        final_mechanism = max(votes.items(), key=lambda x: x[1])[0]
        final_confidence = votes[final_mechanism]
        
        # 归一化置信度（最大为1.0）
        final_confidence = min(final_confidence, 1.0)
        
        # 考虑数据质量调整置信度
        kk_pass = rule_results.get('rule_5_material_composition', {}).get('confidence', 1.0)
        if kk_pass < 0.90:
            final_confidence *= 0.85  # 降低15%
        
        return final_mechanism, round(final_confidence, 3)
    
    def _generate_evidence(self, rule_results: Dict, features: Dict) -> List[str]:
        """生成证据列表"""
        evidence = []
        
        for rule_name, result in rule_results.items():
            if result['matched']:
                evidence.append(
                    f"{result['rule_name']}: {result['conclusion']} "
                    f"(置信度={result['confidence']:.2f}, 权重={result['weight']:.2f})"
                )
                if result.get('literature'):
                    evidence.append(f"  文献支撑: {result['literature']}")
                if result.get('rationale'):
                    evidence.append(f"  理由: {result['rationale']}")
        
        # 添加特征证据
        evidence.append(f"\n关键特征:")
        evidence.append(f"  激活能: {features.get('ea_mean', 0):.3f} eV")
        evidence.append(f"  温度分段: {features.get('num_segments', 0)}个")
        evidence.append(f"  DRT峰数: {features.get('drt_num_peaks', 0)}个")
        
        if features.get('h2o_content', 0) > 0:
            evidence.append(f"  H2O含量: {features['h2o_content']:.1f} wt%")
            evidence.append(f"  H3PO4含量: {features['h3po4_content']:.1f} wt%")
        
        return evidence
    
    def _generate_explanation(self, mechanism: str, confidence: float, 
                             rule_results: Dict, features: Dict) -> str:
        """生成详细解释"""
        explanation_parts = []
        
        # 1. 结论
        explanation_parts.append(
            f"基于多指标综合判断，该样品的主导机制为：{mechanism}（置信度：{confidence:.1%}）"
        )
        
        # 2. 主要依据
        matched_rules = [r for r in rule_results.values() if r['matched']]
        if matched_rules:
            explanation_parts.append("\n主要判断依据：")
            for result in sorted(matched_rules, key=lambda x: x['weight'] * x['confidence'], reverse=True)[:3]:
                explanation_parts.append(
                    f"- {result['rule_name']}（权重{result['weight']:.0%}）: {result['rationale']}"
                )
        
        # 3. 机理解释（从知识库获取）
        mechanism_info = self.mechanism_kb['mechanisms'].get(mechanism.lower(), {})
        if mechanism_info:
            explanation_parts.append(f"\n{mechanism}机制特征：")
            description = mechanism_info.get('description', '')
            explanation_parts.append(f"- {description}")
            
            ea_range = mechanism_info.get('activation_energy', {}).get('typical_range', [])
            if ea_range:
                explanation_parts.append(
                    f"- 典型激活能范围：{ea_range[0]:.2f}-{ea_range[1]:.2f} eV"
                )
        
        # 4. 与文献对比
        ea = features.get('ea_mean', 0)
        if mechanism.lower() == 'grotthuss':
            if 0.10 <= ea <= 0.40:
                explanation_parts.append(
                    f"\n该样品Ea={ea:.3f} eV，符合Kreuer 2004报道的Grotthuss机制范围（0.10-0.40 eV）"
                )
        elif mechanism.lower() == 'vehicle':
            if 0.40 <= ea <= 0.80:
                explanation_parts.append(
                    f"\n该样品Ea={ea:.3f} eV，符合Kreuer 2004报道的Vehicle机制范围（0.40-0.80 eV）"
                )
        
        # 5. 组成分析
        h2o = features.get('h2o_content', 0)
        h3po4 = features.get('h3po4_content', 0)
        if h2o > 0:
            explanation_parts.append(f"\n材料组成分析：")
            explanation_parts.append(f"- H2O含量：{h2o:.1f} wt%")
            explanation_parts.append(f"- H3PO4含量：{h3po4:.1f} wt%")
            
            # 基于组成给出评价
            if 5 <= h2o <= 15:
                explanation_parts.append(
                    "  H2O含量在最优范围内（5-15 wt%），有利于Grotthuss机制"
                )
            elif h2o < 5:
                explanation_parts.append(
                    "  H2O含量偏低，氢键网络可能不完整，建议增加到10-15 wt%"
                )
            elif h2o > 20:
                explanation_parts.append(
                    "  H2O含量偏高，可能导致过度稀释，建议降低到10-15 wt%"
                )
        
        return "\n".join(explanation_parts)

def test_classifier():
    """测试分类器"""
    import json
    from phase1.integration.phase1_to_phase2_integrator import Phase1ToPhase2Integrator
    
    # 初始化
    integrator = Phase1ToPhase2Integrator()
    classifier = KnowledgeBasedMechanismClassifier()
    
    # 测试样品
    test_samples = [
        'phase1_S8-3-11-1_300-150K 1K-min',  # Ea=0.330
        'phase1_S8-2-2-2_300-120K 3K-min',   # Ea=0.609
        'phase1_S60-2-10-1_300-140K 1K-min'  # Ea=0.386
    ]
    
    print("="*80)
    print("基于知识库的机制分类器V3测试")
    print("="*80)
    print()
    
    for i, sample_dir in enumerate(test_samples, 1):
        print(f"[{i}/3] 测试样品: {sample_dir}")
        print("-"*80)
        
        # 整合Phase1数据
        phase1_data = integrator.integrate_sample(sample_dir)
        
        # 分类
        result = classifier.classify(phase1_data)
        
        # 显示结果
        print(f"样品ID: {result['sample_id']}")
        print(f"机制: {result['mechanism']}")
        print(f"置信度: {result['confidence']:.1%}")
        print()
        print("解释:")
        print(result['explanation'])
        print()
        print("="*80)
        print()
    
    print("[SUCCESS] 测试完成")

if __name__ == '__main__':
    test_classifier()

