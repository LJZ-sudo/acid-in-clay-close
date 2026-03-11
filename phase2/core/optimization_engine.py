# -*- coding: utf-8 -*-
"""
优化建议引擎 - 基于分析结果生成实验优化建议
"""
import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from enum import Enum
import json

class OptimizationType(Enum):
    """优化类型"""
    MEASUREMENT_PARAMETERS = "measurement_parameters"
    SAMPLE_PREPARATION = "sample_preparation"
    EXPERIMENTAL_CONDITIONS = "experimental_conditions"
    DATA_QUALITY = "data_quality"
    ANALYSIS_METHOD = "analysis_method"

class Priority(Enum):
    """优先级"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

@dataclass
class OptimizationSuggestion:
    """优化建议"""
    suggestion_id: str
    type: OptimizationType
    priority: Priority
    title: str
    description: str
    rationale: str
    expected_improvement: str
    implementation_steps: List[str]
    parameters: Dict[str, Any]
    confidence: float

class OptimizationEngine:
    """优化建议引擎"""
    
    def __init__(self):
        """初始化优化引擎"""
        self.optimization_rules = self._initialize_optimization_rules()
        self.suggestion_templates = self._load_suggestion_templates()
    
    def _initialize_optimization_rules(self) -> List[Dict]:
        """初始化优化规则"""
        return [
            {
                "rule_id": "low_data_quality",
                "condition": self._check_low_data_quality,
                "suggestions": ["improve_measurement_parameters", "increase_averaging"]
            },
            {
                "rule_id": "insufficient_frequency_range",
                "condition": self._check_frequency_range,
                "suggestions": ["extend_frequency_range", "optimize_frequency_points"]
            },
            {
                "rule_id": "poor_kk_consistency",
                "condition": self._check_kk_consistency,
                "suggestions": ["improve_stability", "check_linearity", "reduce_noise"]
            },
            {
                "rule_id": "unclear_mechanism",
                "condition": self._check_mechanism_clarity,
                "suggestions": ["temperature_series", "atmosphere_variation", "additional_characterization"]
            },
            {
                "rule_id": "fitting_convergence_issues",
                "condition": self._check_fitting_quality,
                "suggestions": ["adjust_initial_parameters", "change_equivalent_circuit", "data_preprocessing"]
            },
            {
                "rule_id": "low_conductivity_precision",
                "condition": self._check_conductivity_precision,
                "suggestions": ["improve_geometry_measurement", "temperature_calibration", "contact_optimization"]
            }
        ]
    
    def _load_suggestion_templates(self) -> Dict:
        """加载建议模板"""
        return {
            "improve_measurement_parameters": {
                "type": OptimizationType.MEASUREMENT_PARAMETERS,
                "priority": Priority.HIGH,
                "title": "优化测量参数",
                "description": "调整EIS测量参数以提高数据质量",
                "rationale": "当前测量参数可能不够优化，导致数据质量较低",
                "expected_improvement": "提高信噪比和测量精度",
                "implementation_steps": [
                    "增加每个频率点的平均次数",
                    "调整交流信号幅度",
                    "优化等待时间设置",
                    "检查测量范围设置"
                ]
            },
            "extend_frequency_range": {
                "type": OptimizationType.MEASUREMENT_PARAMETERS,
                "priority": Priority.MEDIUM,
                "title": "扩展频率范围",
                "description": "扩展测量频率范围以获得更完整的阻抗信息",
                "rationale": "当前频率范围可能无法捕获所有相关的物理过程",
                "expected_improvement": "获得更完整的阻抗谱特征",
                "implementation_steps": [
                    "向低频扩展至0.01 Hz或更低",
                    "向高频扩展至1 MHz或更高",
                    "增加频率点密度",
                    "验证扩展范围的数据质量"
                ]
            },
            "temperature_series": {
                "type": OptimizationType.EXPERIMENTAL_CONDITIONS,
                "priority": Priority.HIGH,
                "title": "进行变温测量",
                "description": "进行系统的变温EIS测量以确定传导机理",
                "rationale": "温度依赖性是确定传导机理的关键信息",
                "expected_improvement": "明确传导机理和激活能",
                "implementation_steps": [
                    "设计合适的温度范围(通常200-600°C)",
                    "选择适当的温度间隔(25-50°C)",
                    "确保温度稳定性(±1°C)",
                    "每个温度点进行多次测量"
                ]
            },
            "improve_stability": {
                "type": OptimizationType.EXPERIMENTAL_CONDITIONS,
                "priority": Priority.HIGH,
                "title": "提高测量稳定性",
                "description": "改善实验条件以提高测量稳定性",
                "rationale": "不稳定的测量条件导致K-K一致性较差",
                "expected_improvement": "提高数据可靠性和重现性",
                "implementation_steps": [
                    "检查温度控制系统",
                    "确保气氛稳定",
                    "检查电极接触",
                    "延长平衡时间"
                ]
            },
            "contact_optimization": {
                "type": OptimizationType.SAMPLE_PREPARATION,
                "priority": Priority.MEDIUM,
                "title": "优化电极接触",
                "description": "改善电极与样品的接触质量",
                "rationale": "接触电阻影响测量精度",
                "expected_improvement": "降低接触电阻，提高测量精度",
                "implementation_steps": [
                    "选择合适的电极材料",
                    "优化电极制备工艺",
                    "检查电极附着质量",
                    "考虑使用导电胶或焊接"
                ]
            },
            "data_preprocessing": {
                "type": OptimizationType.DATA_QUALITY,
                "priority": Priority.MEDIUM,
                "title": "数据预处理优化",
                "description": "应用适当的数据预处理方法",
                "rationale": "原始数据包含噪声或异常点",
                "expected_improvement": "提高拟合质量和分析准确性",
                "implementation_steps": [
                    "应用平滑滤波",
                    "移除异常数据点",
                    "数据归一化处理",
                    "验证预处理效果"
                ]
            }
        }
    
    def generate_optimization_suggestions(self, analysis_results: Dict, 
                                        experimental_conditions: Dict = None) -> List[OptimizationSuggestion]:
        """生成优化建议"""
        suggestions = []
        
        # 应用优化规则
        for rule in self.optimization_rules:
            if rule["condition"](analysis_results, experimental_conditions or {}):
                for suggestion_key in rule["suggestions"]:
                    if suggestion_key in self.suggestion_templates:
                        template = self.suggestion_templates[suggestion_key]
                        
                        suggestion = OptimizationSuggestion(
                            suggestion_id=f"{rule['rule_id']}_{suggestion_key}",
                            type=template["type"],
                            priority=template["priority"],
                            title=template["title"],
                            description=template["description"],
                            rationale=template["rationale"],
                            expected_improvement=template["expected_improvement"],
                            implementation_steps=template["implementation_steps"],
                            parameters=self._extract_specific_parameters(
                                analysis_results, suggestion_key
                            ),
                            confidence=self._calculate_suggestion_confidence(
                                analysis_results, suggestion_key
                            )
                        )
                        
                        suggestions.append(suggestion)
        
        # 去重和排序
        suggestions = self._deduplicate_suggestions(suggestions)
        suggestions.sort(key=lambda s: (s.priority.value, -s.confidence))
        
        return suggestions
    
    def _check_low_data_quality(self, analysis_results: Dict, conditions: Dict) -> bool:
        """检查数据质量是否较低"""
        # 检查拟合质量
        if 'impedance_fitting' in analysis_results:
            fitting = analysis_results['impedance_fitting']
            if fitting.get('r_squared', 1.0) < 0.95:
                return True
        
        # 检查K-K一致性
        if 'kk_validation' in analysis_results:
            kk_result = analysis_results['kk_validation']
            if not kk_result.get('passed', True):
                return True
        
        return False
    
    def _check_frequency_range(self, analysis_results: Dict, conditions: Dict) -> bool:
        """检查频率范围是否足够"""
        if 'data_info' in analysis_results:
            data_info = analysis_results['data_info']
            freq_min = data_info.get('frequency_min', 0.01)
            freq_max = data_info.get('frequency_max', 1e6)
            
            # 检查是否需要扩展频率范围
            if freq_min > 0.1 or freq_max < 1e5:
                return True
        
        return False
    
    def _check_kk_consistency(self, analysis_results: Dict, conditions: Dict) -> bool:
        """检查K-K一致性"""
        if 'kk_validation' in analysis_results:
            kk_result = analysis_results['kk_validation']
            return not kk_result.get('passed', True)
        return False
    
    def _check_mechanism_clarity(self, analysis_results: Dict, conditions: Dict) -> bool:
        """检查机理是否明确"""
        if 'mechanism_inference' in analysis_results:
            inference = analysis_results['mechanism_inference']
            hypotheses = inference.get('hypotheses', [])
            
            if not hypotheses or hypotheses[0].get('confidence', 0) < 0.7:
                return True
        
        return False
    
    def _check_fitting_quality(self, analysis_results: Dict, conditions: Dict) -> bool:
        """检查拟合质量"""
        if 'impedance_fitting' in analysis_results:
            fitting = analysis_results['impedance_fitting']
            
            # 检查拟合收敛性
            if not fitting.get('converged', True):
                return True
            
            # 检查拟合优度
            if fitting.get('r_squared', 1.0) < 0.9:
                return True
        
        return False
    
    def _check_conductivity_precision(self, analysis_results: Dict, conditions: Dict) -> bool:
        """检查电导率精度"""
        if 'conductivity_analysis' in analysis_results:
            conductivity = analysis_results['conductivity_analysis']
            
            # 检查几何参数不确定度
            geometry_uncertainty = conductivity.get('geometry_uncertainty', 0)
            if geometry_uncertainty > 0.05:  # 5%
                return True
        
        return False
    
    def _extract_specific_parameters(self, analysis_results: Dict, suggestion_key: str) -> Dict[str, Any]:
        """提取特定建议的参数"""
        parameters = {}
        
        if suggestion_key == "extend_frequency_range":
            if 'data_info' in analysis_results:
                data_info = analysis_results['data_info']
                parameters['current_freq_min'] = data_info.get('frequency_min', 0.01)
                parameters['current_freq_max'] = data_info.get('frequency_max', 1e6)
                parameters['suggested_freq_min'] = min(0.01, data_info.get('frequency_min', 0.01) / 10)
                parameters['suggested_freq_max'] = max(1e6, data_info.get('frequency_max', 1e6) * 10)
        
        elif suggestion_key == "temperature_series":
            if 'current_temperature' in analysis_results:
                current_temp = analysis_results['current_temperature']
                parameters['current_temperature'] = current_temp
                parameters['suggested_temp_range'] = (max(200, current_temp - 200), 
                                                    min(800, current_temp + 200))
                parameters['suggested_temp_step'] = 25
        
        elif suggestion_key == "improve_measurement_parameters":
            if 'measurement_settings' in analysis_results:
                settings = analysis_results['measurement_settings']
                parameters['current_ac_amplitude'] = settings.get('ac_amplitude', 0.01)
                parameters['current_averaging'] = settings.get('averaging', 1)
                parameters['suggested_ac_amplitude'] = min(0.1, settings.get('ac_amplitude', 0.01) * 2)
                parameters['suggested_averaging'] = min(10, settings.get('averaging', 1) * 3)
        
        return parameters
    
    def _calculate_suggestion_confidence(self, analysis_results: Dict, suggestion_key: str) -> float:
        """计算建议的置信度"""
        base_confidence = 0.7
        
        # 基于问题严重程度调整置信度
        if suggestion_key == "improve_stability":
            if 'kk_validation' in analysis_results:
                kk_result = analysis_results['kk_validation']
                if kk_result.get('max_relative_error', 0) > 0.1:
                    base_confidence = 0.9
        
        elif suggestion_key == "temperature_series":
            if 'mechanism_inference' in analysis_results:
                inference = analysis_results['mechanism_inference']
                hypotheses = inference.get('hypotheses', [])
                if not hypotheses or hypotheses[0].get('confidence', 0) < 0.5:
                    base_confidence = 0.95
        
        elif suggestion_key == "extend_frequency_range":
            if 'data_info' in analysis_results:
                data_info = analysis_results['data_info']
                freq_range_ratio = (data_info.get('frequency_max', 1e6) / 
                                  data_info.get('frequency_min', 0.01))
                if freq_range_ratio < 1e5:  # 频率范围小于5个数量级
                    base_confidence = 0.85
        
        return base_confidence
    
    def _deduplicate_suggestions(self, suggestions: List[OptimizationSuggestion]) -> List[OptimizationSuggestion]:
        """去除重复建议"""
        seen_titles = set()
        unique_suggestions = []
        
        for suggestion in suggestions:
            if suggestion.title not in seen_titles:
                seen_titles.add(suggestion.title)
                unique_suggestions.append(suggestion)
        
        return unique_suggestions
    
    def generate_optimization_plan(self, suggestions: List[OptimizationSuggestion]) -> Dict:
        """生成优化计划"""
        # 按优先级分组
        high_priority = [s for s in suggestions if s.priority == Priority.HIGH]
        medium_priority = [s for s in suggestions if s.priority == Priority.MEDIUM]
        low_priority = [s for s in suggestions if s.priority == Priority.LOW]
        
        # 估算实施时间
        time_estimates = {
            OptimizationType.MEASUREMENT_PARAMETERS: 1,  # 天
            OptimizationType.SAMPLE_PREPARATION: 3,
            OptimizationType.EXPERIMENTAL_CONDITIONS: 2,
            OptimizationType.DATA_QUALITY: 1,
            OptimizationType.ANALYSIS_METHOD: 1
        }
        
        plan = {
            "phase_1_immediate": {
                "suggestions": high_priority,
                "estimated_time_days": sum(time_estimates.get(s.type, 1) for s in high_priority),
                "description": "立即实施的高优先级改进"
            },
            "phase_2_short_term": {
                "suggestions": medium_priority,
                "estimated_time_days": sum(time_estimates.get(s.type, 1) for s in medium_priority),
                "description": "短期内实施的中等优先级改进"
            },
            "phase_3_long_term": {
                "suggestions": low_priority,
                "estimated_time_days": sum(time_estimates.get(s.type, 1) for s in low_priority),
                "description": "长期规划的低优先级改进"
            }
        }
        
        return plan
    
    def generate_optimization_report(self, suggestions: List[OptimizationSuggestion], 
                                   optimization_plan: Dict) -> str:
        """生成优化建议报告"""
        report = [
            "EIS实验优化建议报告",
            "=" * 40,
            "",
            f"总共识别出 {len(suggestions)} 个优化建议",
            ""
        ]
        
        # 按阶段输出建议
        for phase_name, phase_data in optimization_plan.items():
            phase_suggestions = phase_data["suggestions"]
            if phase_suggestions:
                report.extend([
                    f"{phase_data['description']} ({len(phase_suggestions)}项)",
                    f"预计实施时间: {phase_data['estimated_time_days']} 天",
                    "-" * 30
                ])
                
                for i, suggestion in enumerate(phase_suggestions, 1):
                    report.extend([
                        f"{i}. {suggestion.title}",
                        f"   类型: {suggestion.type.value}",
                        f"   置信度: {suggestion.confidence:.2f}",
                        f"   描述: {suggestion.description}",
                        f"   理由: {suggestion.rationale}",
                        f"   预期效果: {suggestion.expected_improvement}",
                        "   实施步骤:"
                    ])
                    
                    for step in suggestion.implementation_steps:
                        report.append(f"     • {step}")
                    
                    if suggestion.parameters:
                        report.append("   具体参数:")
                        for key, value in suggestion.parameters.items():
                            report.append(f"     {key}: {value}")
                    
                    report.append("")
        
        # 添加总结
        total_time = sum(phase["estimated_time_days"] for phase in optimization_plan.values())
        report.extend([
            "实施建议:",
            f"• 建议按阶段逐步实施，总预计时间: {total_time} 天",
            "• 优先实施高优先级建议，可快速改善数据质量",
            "• 定期评估改进效果，调整后续实施计划",
            "• 记录每次改进的效果，建立优化知识库",
            ""
        ])
        
        return "\n".join(report)
    
    def export_suggestions(self, suggestions: List[OptimizationSuggestion], 
                          file_path: str, format: str = 'json'):
        """导出优化建议"""
        if format == 'json':
            data = []
            for suggestion in suggestions:
                data.append({
                    'id': suggestion.suggestion_id,
                    'type': suggestion.type.value,
                    'priority': suggestion.priority.value,
                    'title': suggestion.title,
                    'description': suggestion.description,
                    'rationale': suggestion.rationale,
                    'expected_improvement': suggestion.expected_improvement,
                    'implementation_steps': suggestion.implementation_steps,
                    'parameters': suggestion.parameters,
                    'confidence': suggestion.confidence
                })
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        
        elif format == 'csv':
            import pandas as pd
            
            data = []
            for suggestion in suggestions:
                data.append({
                    'ID': suggestion.suggestion_id,
                    'Type': suggestion.type.value,
                    'Priority': suggestion.priority.value,
                    'Title': suggestion.title,
                    'Description': suggestion.description,
                    'Confidence': suggestion.confidence
                })
            
            df = pd.DataFrame(data)
            df.to_csv(file_path, index=False, encoding='utf-8')

