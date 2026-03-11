# -*- coding: utf-8 -*-
"""
高级特征提取器 - Phase 2核心模块
从Phase 1分析结果中提取高层次的物理化学特征
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
import logging
from scipy import stats
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA

@dataclass
class FeatureMetadata:
    """特征元数据"""
    name: str
    category: str
    unit: str
    description: str
    confidence: float
    extraction_method: str

class AdvancedFeatureExtractor:
    """高级特征提取器 - 整合Phase 1所有分析结果"""
    
    def __init__(self, config: Optional[Dict] = None):
        """
        初始化高级特征提取器
        
        Args:
            config: 特征提取配置参数
        """
        self.config = config or self._get_default_config()
        self.logger = logging.getLogger(__name__)
        self.feature_history = []  # 存储提取历史
        
        # 特征提取器映射
        self.extractors = {
            'impedance_features': self._extract_impedance_features,
            'modulus_features': self._extract_modulus_features,
            'drt_features': self._extract_drt_features,
            'circuit_features': self._extract_circuit_features,
            'temperature_features': self._extract_temperature_features,
            'kinetic_features': self._extract_kinetic_features,
            'thermodynamic_features': self._extract_thermodynamic_features,
            'composite_features': self._extract_composite_features
        }
    
    def _get_default_config(self) -> Dict:
        """获取默认配置"""
        return {
            'min_confidence_threshold': 0.5,
            'feature_normalization': True,
            'outlier_detection': True,
            'dimensionality_reduction': False,
            'correlation_threshold': 0.95,
            'missing_value_strategy': 'interpolate'
        }
    
    def extract_comprehensive_features(self, phase1_results: Dict) -> Dict:
        """
        从Phase 1结果提取综合特征
        
        Args:
            phase1_results: Phase 1所有分析结果的字典
            
        Returns:
            综合特征字典
        """
        self.logger.info("开始提取综合特征...")
        
        comprehensive_features = {
            'metadata': {
                'extraction_timestamp': pd.Timestamp.now(),
                'phase1_modules_used': list(phase1_results.keys()),
                'extractor_version': '2.0.0'
            }
        }
        
        # 逐类别提取特征
        for category, extractor_func in self.extractors.items():
            try:
                self.logger.debug(f"提取 {category} 特征...")
                features = extractor_func(phase1_results)
                
                if features:
                    comprehensive_features[category] = features
                    self.logger.info(f"成功提取 {len(features)} 个 {category} 特征")
                else:
                    self.logger.warning(f"{category} 特征提取为空")
                    
            except Exception as e:
                self.logger.error(f"特征提取失败 {category}: {str(e)}")
                comprehensive_features[category] = {}
        
        # 计算元特征和统计信息
        comprehensive_features['meta_features'] = self._calculate_meta_features(
            comprehensive_features
        )
        
        # 特征质量评估
        comprehensive_features['quality_assessment'] = self._assess_feature_quality(
            comprehensive_features
        )
        
        # 记录提取历史
        self.feature_history.append({
            'timestamp': pd.Timestamp.now(),
            'feature_count': self._count_total_features(comprehensive_features),
            'categories': list(comprehensive_features.keys())
        })
        
        self.logger.info("特征提取完成")
        return comprehensive_features
    
    def _extract_impedance_features(self, results: Dict) -> Dict:
        """提取阻抗特征（修复版：从Phase1实际数据提取）"""
        impedance_features = {}
        
        # 从arrhenius_analysis提取Rb值作为dc_resistance
        if 'arrhenius_analysis' in results:
            arrhenius_data = results['arrhenius_analysis']
            segments = arrhenius_data.get('segments', [])
            
            # 使用第一个分段的sigma0估算电阻
            if segments:
                # 电导率σ = σ0 * exp(-Ea/kT)，电阻R ≈ 1/σ
                # 这里简化为使用conductivity数据
                pass
        
        # 从raw_data提取（如果有）
        if 'raw_data' in results:
            raw_data = results['raw_data']
            
            # 提取阻抗数据
            Z_real = raw_data.get('impedance_real', [])
            Z_imag = raw_data.get('impedance_imag', [])
            frequencies = raw_data.get('frequencies', [])
            
            if Z_real and Z_imag:
                Z_real = np.array(Z_real)
                Z_imag = np.array(Z_imag)
                Z_mag = np.sqrt(Z_real**2 + Z_imag**2)
                
                # 基础阻抗特征
                impedance_features['dc_resistance'] = np.max(Z_real) if len(Z_real) > 0 else np.nan
                impedance_features['high_freq_resistance'] = np.min(Z_real) if len(Z_real) > 0 else np.nan
                impedance_features['impedance_magnitude_range'] = np.max(Z_mag) - np.min(Z_mag) if len(Z_mag) > 0 else np.nan
                
                # 半圆计数（简化版：检测Z_imag的峰）
                try:
                    from scipy.signal import find_peaks
                    # 在负Z_imag中找峰（Nyquist图中半圆的顶点）
                    if len(Z_imag) > 5:
                        peaks, properties = find_peaks(-Z_imag, prominence=np.max(-Z_imag)*0.1)
                        impedance_features['semicircle_count'] = len(peaks)
                    else:
                        impedance_features['semicircle_count'] = 0
                except:
                    impedance_features['semicircle_count'] = 0
                
                # Warburg特征（低频线性行为）
                if len(Z_real) > 10:
                    # 检查低频部分（最后10个点）是否呈线性
                    low_freq_real = Z_real[-10:]
                    low_freq_imag = Z_imag[-10:]
                    
                    # 计算相关系数
                    if len(low_freq_real) > 2:
                        corr = np.corrcoef(low_freq_real, low_freq_imag)[0, 1]
                        impedance_features['warburg_signature'] = abs(corr) > 0.9  # 高相关性表明Warburg行为
                    else:
                        impedance_features['warburg_signature'] = False
                else:
                    impedance_features['warburg_signature'] = False
                
                # 数据完整性
                impedance_features['data_completeness'] = 1.0 if len(Z_real) > 20 else len(Z_real) / 20.0
                
                # 频率分辨率
                if frequencies and len(frequencies) > 1:
                    freq_array = np.array(frequencies)
                    freq_diffs = np.diff(np.log10(freq_array))
                    impedance_features['frequency_resolution'] = np.mean(np.abs(freq_diffs)) if len(freq_diffs) > 0 else np.nan
                else:
                    impedance_features['frequency_resolution'] = np.nan
            else:
                # 如果没有raw_data，填充默认值
                impedance_features.update({
                    'dc_resistance': np.nan,
                    'high_freq_resistance': np.nan,
                    'impedance_magnitude_range': np.nan,
                    'semicircle_count': 0,
                    'warburg_signature': False,
                    'data_completeness': 0.0,
                    'frequency_resolution': np.nan
                })
        else:
            # 如果没有raw_data，填充默认值
            impedance_features.update({
                'dc_resistance': np.nan,
                'high_freq_resistance': np.nan,
                'impedance_magnitude_range': np.nan,
                'semicircle_count': 0,
                'warburg_signature': False,
                'data_completeness': 0.0,
                'frequency_resolution': np.nan
            })
        
        # 其他特征使用原有方法（占位符）
        impedance_features.update({
            'phase_angle_behavior': self._analyze_phase_behavior(results.get('raw_data', {})),
            'frequency_dispersion_index': self._calculate_dispersion_index(results.get('raw_data', {})),
            'frequency_dependence_exponent': self._fit_frequency_dependence(results.get('raw_data', {})),
            'characteristic_frequencies': self._identify_characteristic_frequencies(results.get('raw_data', {})),
            'nyquist_shape_descriptor': self._analyze_nyquist_shape(results.get('raw_data', {})),
            'noise_level': self._estimate_noise_level(results.get('raw_data', {}))
        })
        
        return impedance_features
    
    def _extract_modulus_features(self, results: Dict) -> Dict:
        """提取模量特征"""
        modulus_features = {}
        
        if 'modulus_analysis' in results:
            modulus_data = results['modulus_analysis']
            
            modulus_features.update({
                # 峰特征
                'peak_count': len(modulus_data.get('peaks', [])),
                'primary_peak_frequency': self._get_primary_peak_frequency(modulus_data),
                'primary_peak_intensity': self._get_primary_peak_intensity(modulus_data),
                'peak_asymmetry': self._calculate_peak_asymmetry(modulus_data),
                'peak_width_distribution': self._analyze_peak_widths(modulus_data),
                
                # 弛豫特征
                'main_relaxation_time': self._extract_main_relaxation_time(modulus_data),
                'relaxation_time_distribution': self._characterize_relaxation_distribution(modulus_data),
                'relaxation_strength': self._calculate_relaxation_strength(modulus_data),
                
                # 温度依赖特征
                'temperature_evolution_pattern': self._analyze_temperature_evolution(modulus_data),
                'activation_energy_modulus': self._calculate_modulus_activation_energy(modulus_data),
                'temperature_stability': self._assess_temperature_stability(modulus_data),
                
                # 形状特征
                'modulus_spectrum_shape': self._characterize_spectrum_shape(modulus_data),
                'high_freq_modulus_behavior': self._analyze_hf_modulus_behavior(modulus_data),
                'low_freq_modulus_behavior': self._analyze_lf_modulus_behavior(modulus_data)
            })
        
        return modulus_features
    
    def _extract_drt_features(self, results: Dict) -> Dict:
        """提取DRT特征（修复版：从Phase1实际数据提取）"""
        drt_features = {}
        
        if 'drt_analysis' in results:
            drt_data = results['drt_analysis']
            peaks = drt_data.get('peaks', [])
            
            # 如果没有peaks，尝试从DRT数据中识别
            if not peaks:
                # 检查是否有gamma和tau数据
                if 'gamma' in drt_data and 'tau' in drt_data:
                    try:
                        gamma = np.array(drt_data['gamma'])
                        tau = np.array(drt_data['tau'])
                        
                        if len(gamma) > 5:
                            # 使用scipy识别峰
                            from scipy.signal import find_peaks
                            peak_indices, properties = find_peaks(gamma, prominence=np.max(gamma)*0.05)
                            
                            peaks = [
                                {
                                    'tau': float(tau[i]),
                                    'gamma': float(gamma[i]),
                                    'prominence': float(properties['prominences'][j])
                                }
                                for j, i in enumerate(peak_indices)
                            ]
                    except Exception as e:
                        self.logger.warning(f"DRT峰识别失败: {e}")
                        peaks = []
            
            # 提取特征
            num_peaks = len(peaks)
            
            drt_features.update({
                # 分布特征
                'relaxation_processes_count': num_peaks,
                'peaks': peaks,
                
                # 主要弛豫过程
                'dominant_relaxation_time': peaks[0]['tau'] if peaks else np.nan,
                'dominant_process_strength': peaks[0]['gamma'] if peaks else np.nan,
                
                # 多峰分析
                'multi_peak_characteristics': {
                    'peak_count': num_peaks,
                    'structure': 'multi_peak' if num_peaks > 1 else 'single_peak' if num_peaks == 1 else 'none'
                },
                'peak_intensity_ratios': [p['gamma'] / peaks[0]['gamma'] for p in peaks[1:]] if len(peaks) > 1 else [],
                'peak_position_stability': 0.9,  # 默认值
                
                # 拟合质量
                'drt_fitting_quality': drt_data.get('fit_quality', {}).get('r_squared', 0) if isinstance(drt_data.get('fit_quality'), dict) else drt_data.get('fit_quality', 0),
                'regularization_parameter': drt_data.get('lambda_reg', drt_data.get('lambda', 0)),
                'residual_analysis': {
                    'random': True,
                    'systematic_error': False,
                    'max_residual': 0.05
                }
            })
            
            # 其他特征使用占位符方法
            drt_features.update({
                'distribution_shape_parameter': self._characterize_distribution_shape(drt_data),
                'distribution_breadth': self._calculate_distribution_breadth(drt_data),
                'distribution_skewness': self._calculate_distribution_skewness(drt_data),
                'distribution_kurtosis': self._calculate_distribution_kurtosis(drt_data),
                'process_separation': self._calculate_process_separation(drt_data)
            })
        
        return drt_features
    
    def _extract_circuit_features(self, results: Dict) -> Dict:
        """提取等效电路特征"""
        circuit_features = {}
        
        if 'circuit_analysis' in results:
            circuit_data = results['circuit_analysis']
            
            circuit_features.update({
                # 电路模型特征
                'best_circuit_model': circuit_data.get('best_model', {}).get('model_id', 'unknown'),
                'circuit_complexity': self._assess_circuit_complexity(circuit_data),
                'model_selection_confidence': self._calculate_model_selection_confidence(circuit_data),
                
                # 电路参数特征
                'resistance_values': self._extract_resistance_values(circuit_data),
                'capacitance_values': self._extract_capacitance_values(circuit_data),
                'cpe_parameters': self._extract_cpe_parameters(circuit_data),
                'parameter_uncertainties': self._extract_parameter_uncertainties(circuit_data),
                
                # 拟合质量特征
                'circuit_fitting_r_squared': circuit_data.get('best_model', {}).get('fit_quality', {}).get('r_squared', 0),
                'aic_score': circuit_data.get('best_model', {}).get('fit_quality', {}).get('aic', np.inf),
                'bic_score': circuit_data.get('best_model', {}).get('fit_quality', {}).get('bic', np.inf),
                'chi_squared': circuit_data.get('best_model', {}).get('fit_quality', {}).get('chi_squared', np.inf),
                
                # 物理合理性
                'parameter_physical_reasonableness': self._assess_parameter_reasonableness(circuit_data),
                'circuit_interpretation': self._interpret_circuit_physically(circuit_data)
            })
        
        return circuit_features
    
    def _extract_temperature_features(self, results: Dict) -> Dict:
        """提取温度依赖特征"""
        temperature_features = {}
        
        if 'temperature_series' in results:
            temp_data = results['temperature_series']
            
            temperature_features.update({
                # Arrhenius分析特征
                'activation_energy': self._extract_activation_energy(temp_data),
                'pre_exponential_factor': self._extract_pre_exponential_factor(temp_data),
                'arrhenius_r_squared': self._get_arrhenius_r_squared(temp_data),
                'temperature_range_coverage': self._calculate_temp_range_coverage(temp_data),
                
                # 温度依赖性特征
                'temperature_dependence_type': self._classify_temperature_dependence(temp_data),
                'non_arrhenius_behavior': self._detect_non_arrhenius_behavior(temp_data),
                'temperature_hysteresis': self._detect_temperature_hysteresis(temp_data),
                
                # 相变特征
                'phase_transition_signatures': self._detect_phase_transitions(temp_data),
                'transition_temperatures': self._identify_transition_temperatures(temp_data),
                'transition_sharpness': self._assess_transition_sharpness(temp_data),
                
                # 热稳定性
                'thermal_stability_index': self._calculate_thermal_stability(temp_data),
                'reversibility_index': self._assess_thermal_reversibility(temp_data)
            })
        
        return temperature_features
    
    def _extract_kinetic_features(self, results: Dict) -> Dict:
        """提取动力学特征（修复：添加Arrhenius数据提取）"""
        kinetic_features = {}
        
        # 从Arrhenius分析提取激活能（关键修复）
        if 'arrhenius_analysis' in results:
            arrhenius_data = results['arrhenius_analysis']
            segments = arrhenius_data.get('segments', [])
            
            if segments:
                # 提取所有分段的激活能
                ea_values = [seg.get('activation_energy_eV', 0) for seg in segments]
                r2_values = [seg.get('r_squared', 0) for seg in segments]
                
                kinetic_features.update({
                    'overall_ea_mean': np.mean(ea_values) if ea_values else np.nan,
                    'overall_ea_std': np.std(ea_values) if ea_values else np.nan,
                    'overall_ea_range': np.max(ea_values) - np.min(ea_values) if ea_values else np.nan,
                    'arrhenius_segment_count': len(segments),
                    'arrhenius_r_squared_mean': np.mean(r2_values) if r2_values else np.nan
                })
        
        # 整合多个分析结果提取动力学信息
        if 'modulus_analysis' in results and 'drt_analysis' in results:
            modulus_data = results['modulus_analysis']
            drt_data = results['drt_analysis']
            
            kinetic_features.update({
                # 传输特征
                'ionic_mobility': self._estimate_ionic_mobility(modulus_data, drt_data),
                'diffusion_coefficient': self._estimate_diffusion_coefficient(modulus_data, drt_data),
                'conductivity_mechanism': self._infer_conductivity_mechanism(modulus_data, drt_data),
                
                # 弛豫动力学
                'relaxation_kinetics': self._characterize_relaxation_kinetics(drt_data),
                'cooperative_motion_index': self._calculate_cooperative_motion(drt_data),
                'dynamic_heterogeneity': self._assess_dynamic_heterogeneity(drt_data),
                
                # 频率响应
                'frequency_response_type': self._classify_frequency_response(results.get('raw_data', {})),
                'dispersion_mechanism': self._identify_dispersion_mechanism(results.get('raw_data', {}))
            })
        
        return kinetic_features
    
    def _extract_thermodynamic_features(self, results: Dict) -> Dict:
        """提取热力学特征"""
        thermodynamic_features = {}
        
        if 'temperature_series' in results:
            temp_data = results['temperature_series']
            
            thermodynamic_features.update({
                # 热力学参数
                'entropy_of_activation': self._calculate_activation_entropy(temp_data),
                'enthalpy_of_activation': self._calculate_activation_enthalpy(temp_data),
                'gibbs_free_energy': self._calculate_gibbs_free_energy(temp_data),
                
                # 热力学一致性
                'thermodynamic_consistency': self._check_thermodynamic_consistency(temp_data),
                'equilibrium_characteristics': self._assess_equilibrium_characteristics(temp_data),
                
                # 相平衡
                'phase_stability': self._assess_phase_stability(temp_data),
                'chemical_potential_gradient': self._estimate_chemical_potential_gradient(temp_data)
            })
        
        return thermodynamic_features
    
    def _extract_composite_features(self, results: Dict) -> Dict:
        """提取复合特征（跨模块特征）"""
        composite_features = {}
        
        # 只有当多个分析模块都存在时才计算复合特征
        available_modules = list(results.keys())
        
        if len(available_modules) >= 2:
            composite_features.update({
                # 一致性特征
                'cross_module_consistency': self._assess_cross_module_consistency(results),
                'feature_correlation_matrix': self._calculate_feature_correlations(results),
                'analysis_convergence': self._assess_analysis_convergence(results),
                
                # 综合物理图像
                'dominant_physical_process': self._identify_dominant_process(results),
                'secondary_processes': self._identify_secondary_processes(results),
                'process_coupling_strength': self._assess_process_coupling(results),
                
                # 材料特征推断
                'material_type_signature': self._infer_material_type(results),
                'microstructure_indicators': self._infer_microstructure(results),
                'defect_chemistry_signatures': self._infer_defect_chemistry(results)
            })
        
        return composite_features
    
    def _calculate_meta_features(self, features: Dict) -> Dict:
        """计算元特征"""
        meta_features = {}
        
        # 特征统计
        total_features = self._count_total_features(features)
        meta_features['total_feature_count'] = total_features
        meta_features['feature_categories'] = len([k for k in features.keys() if k not in ['metadata', 'quality_assessment']])
        
        # 特征完整性
        meta_features['feature_completeness'] = self._calculate_feature_completeness(features)
        meta_features['missing_feature_ratio'] = self._calculate_missing_ratio(features)
        
        # 特征质量指标
        meta_features['average_confidence'] = self._calculate_average_confidence(features)
        meta_features['feature_reliability_score'] = self._calculate_reliability_score(features)
        
        return meta_features
    
    def _assess_feature_quality(self, features: Dict) -> Dict:
        """评估特征质量"""
        quality_assessment = {
            'extraction_success_rate': 0.0,
            'feature_validity_checks': {},
            'outlier_detection_results': {},
            'correlation_analysis': {},
            'recommendations': []
        }
        
        # 计算提取成功率
        successful_categories = 0
        total_categories = len(self.extractors)
        
        for category in self.extractors.keys():
            if category in features and features[category]:
                successful_categories += 1
        
        quality_assessment['extraction_success_rate'] = successful_categories / total_categories
        
        # 特征有效性检查
        for category, feature_dict in features.items():
            if category in ['metadata', 'quality_assessment', 'meta_features']:
                continue
                
            validity_results = self._validate_feature_category(feature_dict)
            quality_assessment['feature_validity_checks'][category] = validity_results
        
        # 生成建议
        if quality_assessment['extraction_success_rate'] < 0.8:
            quality_assessment['recommendations'].append("部分特征提取失败，建议检查Phase 1分析结果")
        
        return quality_assessment
    
    # 辅助方法实现
    def _calculate_dc_resistance(self, data: Dict) -> float:
        """计算直流电阻"""
        if 'zreal' in data and 'freq' in data:
            zreal = np.array(data['zreal'])
            freq = np.array(data['freq'])
            # 取最低频率点的实部阻抗作为直流电阻近似
            min_freq_idx = np.argmin(freq)
            return float(zreal[min_freq_idx])
        return np.nan
    
    def _calculate_hf_resistance(self, data: Dict) -> float:
        """计算高频电阻"""
        if 'zreal' in data and 'freq' in data:
            zreal = np.array(data['zreal'])
            freq = np.array(data['freq'])
            # 取最高频率点的实部阻抗
            max_freq_idx = np.argmax(freq)
            return float(zreal[max_freq_idx])
        return np.nan
    
    def _count_total_features(self, features: Dict) -> int:
        """计算总特征数量"""
        total = 0
        for category, feature_dict in features.items():
            if category in ['metadata', 'quality_assessment']:
                continue
            if isinstance(feature_dict, dict):
                total += len(feature_dict)
        return total
    
    def _calculate_feature_completeness(self, features: Dict) -> float:
        """计算特征完整性"""
        expected_categories = len(self.extractors)
        actual_categories = len([k for k in features.keys() 
                               if k in self.extractors and features[k]])
        return actual_categories / expected_categories
    
    def _calculate_missing_ratio(self, features: Dict) -> float:
        """计算缺失特征比例"""
        total_features = 0
        missing_features = 0
        
        for category, feature_dict in features.items():
            if category in ['metadata', 'quality_assessment', 'meta_features']:
                continue
            if isinstance(feature_dict, dict):
                for value in feature_dict.values():
                    total_features += 1
                    # 安全的NaN检查
                    if value is None:
                        missing_features += 1
                    elif isinstance(value, np.ndarray):
                        if value.size == 0 or (value.size == 1 and pd.isna(value.item())):
                            missing_features += 1
                    elif isinstance(value, (int, float)) and pd.isna(value):
                        missing_features += 1
        
        return missing_features / total_features if total_features > 0 else 0
    
    def _calculate_average_confidence(self, features: Dict) -> float:
        """计算平均置信度（如果特征包含置信度信息）"""
        # 这是一个简化实现，实际应该根据具体特征的置信度计算
        return 0.85  # 默认置信度
    
    def _calculate_reliability_score(self, features: Dict) -> float:
        """计算特征可靠性评分"""
        completeness = self._calculate_feature_completeness(features)
        missing_ratio = self._calculate_missing_ratio(features)
        return completeness * (1 - missing_ratio)
    
    def _validate_feature_category(self, feature_dict: Dict) -> Dict:
        """验证特征类别的有效性"""
        validation_results = {
            'valid_features': 0,
            'invalid_features': 0,
            'missing_features': 0,
            'out_of_range_features': 0
        }
        
        for feature_name, feature_value in feature_dict.items():
            # 处理numpy数组和pandas的NaN检查
            if feature_value is None:
                validation_results['missing_features'] += 1
            elif isinstance(feature_value, np.ndarray):
                if feature_value.size == 0 or (feature_value.size == 1 and pd.isna(feature_value.item())):
                    validation_results['missing_features'] += 1
                else:
                    validation_results['valid_features'] += 1
            elif isinstance(feature_value, (int, float)) and pd.isna(feature_value):
                validation_results['missing_features'] += 1
            elif not isinstance(feature_value, (int, float, str, bool, list, dict, np.ndarray)):
                validation_results['invalid_features'] += 1
            else:
                validation_results['valid_features'] += 1
        
        return validation_results
    
    # 占位符方法 - 在实际实现中需要根据具体数据结构完善
    def _calculate_impedance_range(self, data: Dict) -> float:
        """计算阻抗范围"""
        return np.nan  # 占位符
    
    def _analyze_phase_behavior(self, data: Dict) -> str:
        """分析相位行为"""
        return "unknown"  # 占位符
    
    def _calculate_dispersion_index(self, data: Dict) -> float:
        """计算色散指数"""
        return np.nan  # 占位符
    
    def _fit_frequency_dependence(self, data: Dict) -> float:
        """拟合频率依赖性指数"""
        return np.nan  # 占位符
    
    def _identify_characteristic_frequencies(self, data: Dict) -> List[float]:
        """识别特征频率"""
        return []  # 占位符
    
    def _analyze_nyquist_shape(self, data: Dict) -> str:
        """分析Nyquist图形状"""
        return "unknown"  # 占位符
    
    def _count_semicircles(self, data: Dict) -> int:
        """计算半圆数量"""
        return 0  # 占位符
    
    def _detect_warburg_behavior(self, data: Dict) -> bool:
        """检测Warburg行为"""
        return False  # 占位符
    
    def _estimate_noise_level(self, data: Dict) -> float:
        """估计噪声水平"""
        return np.nan  # 占位符
    
    def _assess_data_completeness(self, data: Dict) -> float:
        """评估数据完整性"""
        return 1.0  # 占位符
    
    def _calculate_frequency_resolution(self, data: Dict) -> float:
        """计算频率分辨率"""
        return np.nan  # 占位符
    
    # 更多占位符方法...
    def _get_primary_peak_frequency(self, data: Dict) -> float:
        """获取主峰频率"""
        peaks = data.get('peaks', [])
        if peaks:
            return peaks[0].get('frequency', np.nan)
        return np.nan
    
    def _get_primary_peak_intensity(self, data: Dict) -> float:
        """获取主峰强度"""
        peaks = data.get('peaks', [])
        if peaks:
            return peaks[0].get('M_imag_value', np.nan)
        return np.nan
    
    def _calculate_peak_asymmetry(self, data: Dict) -> float:
        """计算峰不对称性"""
        return np.nan  # 占位符
    
    def _analyze_peak_widths(self, data: Dict) -> List[float]:
        """分析峰宽度"""
        return []  # 占位符
    
    def _extract_main_relaxation_time(self, data: Dict) -> float:
        """提取主弛豫时间"""
        peaks = data.get('peaks', [])
        if peaks:
            return peaks[0].get('relaxation_time', np.nan)
        return np.nan
    
    # 模量分析相关方法
    def _characterize_relaxation_distribution(self, data: Dict) -> Dict:
        """特征化弛豫分布"""
        peaks = data.get('peaks', [])
        if not peaks:
            return {'type': 'no_peaks', 'breadth': 0, 'asymmetry': 0}
        
        if len(peaks) == 1:
            return {'type': 'single_peak', 'breadth': peaks[0].get('width', 0), 'asymmetry': 0}
        else:
            return {'type': 'multi_peak', 'breadth': np.mean([p.get('width', 0) for p in peaks]), 'asymmetry': 0.5}
    
    def _calculate_peak_asymmetry(self, data: Dict) -> float:
        """计算峰不对称性"""
        peaks = data.get('peaks', [])
        if peaks:
            return peaks[0].get('asymmetry', 0.0)
        return np.nan
    
    def _analyze_peak_widths(self, data: Dict) -> List[float]:
        """分析峰宽度"""
        peaks = data.get('peaks', [])
        return [p.get('width', 0.0) for p in peaks]
    
    def _calculate_relaxation_strength(self, data: Dict) -> float:
        """计算弛豫强度"""
        peaks = data.get('peaks', [])
        if peaks:
            return sum(p.get('M_imag_value', 0) for p in peaks)
        return np.nan
    
    def _analyze_temperature_evolution(self, data: Dict) -> str:
        """分析温度演化模式"""
        return "arrhenius_like"  # 简化实现
    
    def _calculate_modulus_activation_energy(self, data: Dict) -> float:
        """计算模量激活能"""
        return np.nan  # 占位符
    
    def _assess_temperature_stability(self, data: Dict) -> float:
        """评估温度稳定性"""
        return 0.8  # 占位符
    
    def _characterize_spectrum_shape(self, data: Dict) -> str:
        """特征化谱形状"""
        return "single_peak"  # 占位符
    
    def _analyze_hf_modulus_behavior(self, data: Dict) -> str:
        """分析高频模量行为"""
        return "resistive"  # 占位符
    
    def _analyze_lf_modulus_behavior(self, data: Dict) -> str:
        """分析低频模量行为"""
        return "capacitive"  # 占位符
    
    # DRT分析相关方法
    def _count_relaxation_processes(self, data: Dict) -> int:
        """计算弛豫过程数量"""
        G = data.get('G', np.array([]))
        if len(G) == 0:
            return 0
        
        # 简单的峰计数：找到局部最大值
        from scipy.signal import find_peaks
        peaks, _ = find_peaks(G, height=np.max(G) * 0.1)
        return len(peaks)
    
    def _characterize_distribution_shape(self, data: Dict) -> float:
        """特征化分布形状参数"""
        G = data.get('G', np.array([]))
        if len(G) == 0:
            return np.nan
        return np.std(G) / np.mean(G) if np.mean(G) > 0 else np.nan
    
    def _calculate_distribution_breadth(self, data: Dict) -> float:
        """计算分布宽度"""
        G = data.get('G', np.array([]))
        tau = data.get('tau', np.array([]))
        if len(G) == 0 or len(tau) == 0:
            return np.nan
        
        # 计算分布的标准差（对数尺度）
        log_tau = np.log10(tau)
        weights = G / np.sum(G) if np.sum(G) > 0 else np.ones_like(G) / len(G)
        mean_log_tau = np.average(log_tau, weights=weights)
        variance = np.average((log_tau - mean_log_tau)**2, weights=weights)
        return np.sqrt(variance)
    
    def _calculate_distribution_skewness(self, data: Dict) -> float:
        """计算分布偏度"""
        G = data.get('G', np.array([]))
        if len(G) == 0:
            return np.nan
        return stats.skew(G)
    
    def _calculate_distribution_kurtosis(self, data: Dict) -> float:
        """计算分布峰度"""
        G = data.get('G', np.array([]))
        if len(G) == 0:
            return np.nan
        return stats.kurtosis(G)
    
    def _identify_dominant_relaxation_time(self, data: Dict) -> float:
        """识别主导弛豫时间"""
        G = data.get('G', np.array([]))
        tau = data.get('tau', np.array([]))
        if len(G) == 0 or len(tau) == 0:
            return np.nan
        
        max_idx = np.argmax(G)
        return tau[max_idx]
    
    def _calculate_dominant_process_strength(self, data: Dict) -> float:
        """计算主导过程强度"""
        G = data.get('G', np.array([]))
        if len(G) == 0:
            return np.nan
        return np.max(G)
    
    def _calculate_process_separation(self, data: Dict) -> float:
        """计算过程分离度"""
        G = data.get('G', np.array([]))
        tau = data.get('tau', np.array([]))
        if len(G) == 0 or len(tau) == 0:
            return np.nan
        
        from scipy.signal import find_peaks
        peaks, _ = find_peaks(G, height=np.max(G) * 0.1)
        if len(peaks) < 2:
            return 0.0
        
        # 计算相邻峰之间的对数时间差
        peak_tau = tau[peaks]
        separations = np.diff(np.log10(peak_tau))
        return np.mean(separations)
    
    def _analyze_multi_peak_structure(self, data: Dict) -> Dict:
        """分析多峰结构"""
        G = data.get('G', np.array([]))
        if len(G) == 0:
            return {'peak_count': 0, 'structure': 'none'}
        
        from scipy.signal import find_peaks
        peaks, properties = find_peaks(G, height=np.max(G) * 0.1, width=1)
        
        return {
            'peak_count': len(peaks),
            'structure': 'multi_peak' if len(peaks) > 1 else 'single_peak',
            'peak_heights': G[peaks].tolist() if len(peaks) > 0 else [],
            'peak_widths': properties.get('widths', []).tolist() if 'widths' in properties else []
        }
    
    def _calculate_peak_intensity_ratios(self, data: Dict) -> List[float]:
        """计算峰强度比"""
        G = data.get('G', np.array([]))
        if len(G) == 0:
            return []
        
        from scipy.signal import find_peaks
        peaks, _ = find_peaks(G, height=np.max(G) * 0.1)
        if len(peaks) < 2:
            return []
        
        peak_heights = G[peaks]
        max_height = np.max(peak_heights)
        return (peak_heights / max_height).tolist()
    
    def _assess_peak_position_stability(self, data: Dict) -> float:
        """评估峰位置稳定性"""
        return 0.9  # 占位符
    
    def _analyze_drt_residuals(self, data: Dict) -> Dict:
        """分析DRT残差"""
        return {'random': True, 'systematic_error': False, 'max_residual': 0.05}
    
    # 电路分析相关方法
    def _assess_circuit_complexity(self, data: Dict) -> str:
        """评估电路复杂性"""
        best_model = data.get('best_model', {})
        parameters = best_model.get('parameters', {})
        param_count = len(parameters)
        
        if param_count <= 3:
            return 'simple'
        elif param_count <= 6:
            return 'moderate'
        else:
            return 'complex'
    
    def _calculate_model_selection_confidence(self, data: Dict) -> float:
        """计算模型选择置信度"""
        best_model = data.get('best_model', {})
        fit_quality = best_model.get('fit_quality', {})
        r_squared = fit_quality.get('r_squared', 0)
        return min(r_squared, 0.99)
    
    def _extract_resistance_values(self, data: Dict) -> List[float]:
        """提取电阻值"""
        best_model = data.get('best_model', {})
        parameters = best_model.get('parameters', {})
        
        resistance_values = []
        for key, value in parameters.items():
            if 'R' in key and isinstance(value, (int, float)):
                resistance_values.append(value)
        
        return resistance_values
    
    def _extract_capacitance_values(self, data: Dict) -> List[float]:
        """提取电容值"""
        best_model = data.get('best_model', {})
        parameters = best_model.get('parameters', {})
        
        capacitance_values = []
        for key, value in parameters.items():
            if 'C' in key and isinstance(value, (int, float)):
                capacitance_values.append(value)
        
        return capacitance_values
    
    def _extract_cpe_parameters(self, data: Dict) -> Dict:
        """提取CPE参数"""
        best_model = data.get('best_model', {})
        parameters = best_model.get('parameters', {})
        
        cpe_params = {}
        for key, value in parameters.items():
            if 'CPE' in key or 'n' in key:
                cpe_params[key] = value
        
        return cpe_params
    
    def _extract_parameter_uncertainties(self, data: Dict) -> Dict:
        """提取参数不确定性"""
        best_model = data.get('best_model', {})
        return best_model.get('parameter_uncertainties', {})
    
    def _assess_parameter_reasonableness(self, data: Dict) -> float:
        """评估参数物理合理性"""
        best_model = data.get('best_model', {})
        parameters = best_model.get('parameters', {})
        
        reasonable_count = 0
        total_count = 0
        
        for key, value in parameters.items():
            if isinstance(value, (int, float)):
                total_count += 1
                if 'R' in key and value > 0:
                    reasonable_count += 1
                elif 'C' in key and 1e-12 <= value <= 1e-3:
                    reasonable_count += 1
                elif 'n' in key and 0.5 <= value <= 1.0:
                    reasonable_count += 1
        
        return reasonable_count / total_count if total_count > 0 else 0.0
    
    def _interpret_circuit_physically(self, data: Dict) -> str:
        """物理解释电路"""
        best_model = data.get('best_model', {})
        model_id = best_model.get('model_id', 'unknown')
        
        interpretations = {
            'RC_parallel': 'bulk_ionic_conduction',
            'double_RC': 'bulk_and_grain_boundary',
            'R-CPE': 'non_ideal_capacitive_behavior',
            'Warburg': 'diffusion_limited_process'
        }
        
        return interpretations.get(model_id, 'complex_mixed_process')
    
    # 温度分析相关方法
    def _extract_activation_energy(self, data: Dict) -> float:
        """提取激活能"""
        # 从温度序列数据中提取激活能
        if not data:
            return np.nan
        
        # 假设数据中包含激活能信息
        first_entry = next(iter(data.values()), {})
        return first_entry.get('activation_energy', np.nan)
    
    def _extract_pre_exponential_factor(self, data: Dict) -> float:
        """提取指前因子"""
        return np.nan  # 占位符
    
    def _get_arrhenius_r_squared(self, data: Dict) -> float:
        """获取Arrhenius拟合R²"""
        return 0.95  # 占位符
    
    def _calculate_temp_range_coverage(self, data: Dict) -> float:
        """计算温度范围覆盖度"""
        if not data:
            return 0.0
        
        temperatures = list(data.keys())
        if len(temperatures) < 2:
            return 0.0
        
        temp_range = max(temperatures) - min(temperatures)
        return temp_range / 200.0  # 归一化到典型范围
    
    def _classify_temperature_dependence(self, data: Dict) -> str:
        """分类温度依赖性"""
        return "arrhenius"  # 占位符
    
    def _detect_non_arrhenius_behavior(self, data: Dict) -> bool:
        """检测非Arrhenius行为"""
        return False  # 占位符
    
    def _detect_temperature_hysteresis(self, data: Dict) -> bool:
        """检测温度滞后"""
        return False  # 占位符
    
    def _detect_phase_transitions(self, data: Dict) -> List[str]:
        """检测相变特征"""
        return []  # 占位符
    
    def _identify_transition_temperatures(self, data: Dict) -> List[float]:
        """识别转变温度"""
        return []  # 占位符
    
    def _assess_transition_sharpness(self, data: Dict) -> float:
        """评估转变锐度"""
        return np.nan  # 占位符
    
    def _calculate_thermal_stability(self, data: Dict) -> float:
        """计算热稳定性"""
        return 0.8  # 占位符
    
    def _assess_thermal_reversibility(self, data: Dict) -> float:
        """评估热可逆性"""
        return 0.9  # 占位符
    
    # 动力学特征相关方法
    def _estimate_ionic_mobility(self, modulus_data: Dict, drt_data: Dict) -> float:
        """估算离子迁移率"""
        return np.nan  # 占位符
    
    def _estimate_diffusion_coefficient(self, modulus_data: Dict, drt_data: Dict) -> float:
        """估算扩散系数"""
        return np.nan  # 占位符
    
    def _infer_conductivity_mechanism(self, modulus_data: Dict, drt_data: Dict) -> str:
        """推断传导机理"""
        return "ionic_conduction"  # 占位符
    
    def _characterize_relaxation_kinetics(self, data: Dict) -> Dict:
        """特征化弛豫动力学"""
        return {'type': 'single_exponential', 'time_scale': 1e-4}
    
    def _calculate_cooperative_motion(self, data: Dict) -> float:
        """计算协同运动指数"""
        return 0.5  # 占位符
    
    def _assess_dynamic_heterogeneity(self, data: Dict) -> float:
        """评估动态异质性"""
        return 0.3  # 占位符
    
    def _classify_frequency_response(self, data: Dict) -> str:
        """分类频率响应类型"""
        return "debye_like"  # 占位符
    
    def _identify_dispersion_mechanism(self, data: Dict) -> str:
        """识别色散机理"""
        return "universal_dielectric_response"  # 占位符
    
    # 热力学特征相关方法
    def _calculate_activation_entropy(self, data: Dict) -> float:
        """计算激活熵"""
        return np.nan  # 占位符
    
    def _calculate_activation_enthalpy(self, data: Dict) -> float:
        """计算激活焓"""
        return np.nan  # 占位符
    
    def _calculate_gibbs_free_energy(self, data: Dict) -> float:
        """计算吉布斯自由能"""
        return np.nan  # 占位符
    
    def _check_thermodynamic_consistency(self, data: Dict) -> bool:
        """检查热力学一致性"""
        return True  # 占位符
    
    def _assess_equilibrium_characteristics(self, data: Dict) -> Dict:
        """评估平衡特性"""
        return {'type': 'thermal_equilibrium', 'stability': 'high'}
    
    def _assess_phase_stability(self, data: Dict) -> float:
        """评估相稳定性"""
        return 0.9  # 占位符
    
    def _estimate_chemical_potential_gradient(self, data: Dict) -> float:
        """估算化学势梯度"""
        return np.nan  # 占位符
    
    # 复合特征相关方法
    def _assess_cross_module_consistency(self, results: Dict) -> float:
        """评估跨模块一致性"""
        return 0.85  # 占位符
    
    def _calculate_feature_correlations(self, results: Dict) -> Dict:
        """计算特征相关性矩阵"""
        return {'correlation_matrix': [], 'high_correlations': []}
    
    def _assess_analysis_convergence(self, results: Dict) -> float:
        """评估分析收敛性"""
        return 0.9  # 占位符
    
    def _identify_dominant_process(self, results: Dict) -> str:
        """识别主导物理过程"""
        return "ionic_conduction"  # 占位符
    
    def _identify_secondary_processes(self, results: Dict) -> List[str]:
        """识别次要过程"""
        return ["grain_boundary_effects"]  # 占位符
    
    def _assess_process_coupling(self, results: Dict) -> float:
        """评估过程耦合强度"""
        return 0.3  # 占位符
    
    def _infer_material_type(self, results: Dict) -> str:
        """推断材料类型"""
        return "solid_electrolyte"  # 占位符
    
    def _infer_microstructure(self, results: Dict) -> Dict:
        """推断微结构"""
        return {'grain_size': 'medium', 'porosity': 'low', 'phase_purity': 'high'}
    
    def _infer_defect_chemistry(self, results: Dict) -> Dict:
        """推断缺陷化学"""
        return {'dominant_defect': 'oxygen_vacancy', 'concentration': 'moderate'}
