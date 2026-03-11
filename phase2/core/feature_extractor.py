# -*- coding: utf-8 -*-
"""
特征提取器 - 为Phase 3机器学习准备特征

功能：
1. 提取基础特征（R, N, T等）
2. 生成派生特征（R², log(N)等）
3. 生成交互特征（R×N等）
4. 温度区间编码
5. 数据质量特征

作者: AI Assistant
日期: 2025-11-19
"""
import numpy as np
from typing import Dict, Any

class FeatureExtractor:
    """特征提取器"""
    
    def extract_features(self, sample_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        提取特征
        
        Parameters
        ----------
        sample_data : dict
            样品数据（来自enhanced_data_integrator的integrated_data）
            
        Returns
        -------
        dict : 特征字典
        """
        features = {}
        
        # 1. 基础特征 - 从metadata提取
        metadata = sample_data.get('metadata', {})
        # 处理None值，确保转换为0
        features['R'] = metadata.get('R', 0) or 0
        features['N'] = metadata.get('N', 0) or 0
        features['Sepiolite_mg'] = metadata.get('sepiolite_mg', 0) or 0
        features['H3PO4_wt%'] = metadata.get('h3po4_wt%', 0) or 0
        
        # 2. 温度特征 - 从phase1_data提取
        phase1 = sample_data.get('phase1_data', {})
        arrhenius = phase1.get('arrhenius', {})
        segments = arrhenius.get('segments', [])
        
        if segments:
            # 从所有分段中提取温度范围
            T_min_list = []
            T_max_list = []
            for seg in segments:
                if isinstance(seg, dict):
                    # 尝试多种键名
                    T_min = seg.get('T_min_K') or seg.get('temperature_range', [0, 0])[0]
                    T_max = seg.get('T_max_K') or seg.get('temperature_range', [0, 0])[1]
                    if T_min > 0:
                        T_min_list.append(T_min)
                    if T_max > 0:
                        T_max_list.append(T_max)
            
            T_min = min(T_min_list) if T_min_list else 180
            T_max = max(T_max_list) if T_max_list else 300
        else:
            T_min = 180
            T_max = 300
        
        features['T_min'] = T_min
        features['T_max'] = T_max
        features['T_range'] = T_max - T_min
        features['T_avg'] = (T_min + T_max) / 2
        
        # 3. 派生特征（基于物理意义）
        if features['R'] > 0:
            features['R_squared'] = features['R']**2
            features['log_R'] = np.log(features['R'] + 1e-6)
        else:
            features['R_squared'] = 0
            features['log_R'] = -10
        
        if features['N'] > 0:
            features['N_squared'] = features['N']**2
            features['log_N'] = np.log(features['N'])
            features['exp_minus_N'] = np.exp(-features['N'] / 4.0)  # 限域效应衰减
        else:
            features['N_squared'] = 0
            features['log_N'] = 0
            features['exp_minus_N'] = 1.0
        
        # 4. 交互特征
        features['R_times_N'] = features['R'] * features['N']
        
        # 5. 温度区间编码（与 Phase 3 统一：<230K / 230-270K / ≥270K）
        features['is_low_temp'] = int(features['T_avg'] < 230)
        features['is_mid_temp'] = int(230 <= features['T_avg'] < 270)
        features['is_high_temp'] = int(features['T_avg'] >= 270)
        
        # 6. 数据质量特征 - 从Phase 1的quality字段提取
        quality = phase1.get('quality', {})
        features['quality_score'] = quality.get('quality_score', 0)
        features['quality_level'] = quality.get('quality_level', 'unknown')
        features['use_for_modeling'] = quality.get('use_for_modeling', False)
        
        # 7. Arrhenius特征
        if segments:
            features['n_segments'] = len(segments)
            # 计算平均R²
            r2_values = []
            for seg in segments:
                if isinstance(seg, dict):
                    # 尝试多种可能的字段名
                    r2 = seg.get('r_squared') or seg.get('R_squared') or seg.get('r2', 0)
                    if r2 and r2 > 0:
                        r2_values.append(r2)
            features['avg_R_squared'] = np.mean(r2_values) if r2_values else 0
            
            # 8. Arrhenius误差和sigma0特征（新增）
            sigma0_values = []
            ea_stderr_values = []
            p_values = []
            for seg in segments:
                if isinstance(seg, dict):
                    # 提取sigma0
                    sigma0 = seg.get('sigma0_S_cm') or seg.get('sigma0', 0)
                    if sigma0 > 0:
                        sigma0_values.append(sigma0)
                    # 提取Ea标准误差
                    ea_stderr = seg.get('Ea_stderr') or seg.get('Ea_error')
                    if ea_stderr is not None:
                        ea_stderr_values.append(ea_stderr)
                    # 提取p-value
                    p_val = seg.get('p_value')
                    if p_val is not None:
                        p_values.append(p_val)
            
            # sigma0统计
            if sigma0_values:
                features['sigma0_mean'] = np.mean(sigma0_values)
                features['sigma0_median'] = np.median(sigma0_values)
                features['sigma0_log_mean'] = np.log(np.mean(sigma0_values) + 1e-10)
            else:
                features['sigma0_mean'] = 0
                features['sigma0_median'] = 0
                features['sigma0_log_mean'] = 0
            
            # Ea误差统计
            if ea_stderr_values:
                features['Ea_stderr_mean'] = np.mean(ea_stderr_values)
                features['Ea_stderr_max'] = np.max(ea_stderr_values)
            else:
                features['Ea_stderr_mean'] = 0
                features['Ea_stderr_max'] = 0
            
            # p-value统计
            if p_values:
                features['p_value_mean'] = np.mean(p_values)
                features['p_value_min'] = np.min(p_values)
                features['all_segments_significant'] = int(all(p < 0.05 for p in p_values))
            else:
                features['p_value_mean'] = 1.0
                features['p_value_min'] = 1.0
                features['all_segments_significant'] = 0
        else:
            features['n_segments'] = 0
            features['avg_R_squared'] = 0
            features['sigma0_mean'] = 0
            features['sigma0_median'] = 0
            features['sigma0_log_mean'] = 0
            features['Ea_stderr_mean'] = 0
            features['Ea_stderr_max'] = 0
            features['p_value_mean'] = 1.0
            features['p_value_min'] = 1.0
            features['all_segments_significant'] = 0
        
        return features
    
    def get_feature_description(self) -> Dict[str, str]:
        """
        获取特征描述
        
        Returns
        -------
        dict : 特征名称 -> 描述
        """
        return {
            # 基础特征
            'R': 'H3PO4/H2O摩尔比',
            'N': '液固比（液体/Sepiolite质量比）',
            'Sepiolite_mg': 'Sepiolite质量 (mg)',
            'H3PO4_wt%': '磷酸重量百分比',
            
            # 温度特征
            'T_min': '最低温度 (K)',
            'T_max': '最高温度 (K)',
            'T_range': '温度范围 (K)',
            'T_avg': '平均温度 (K)',
            
            # 派生特征
            'R_squared': 'R的平方',
            'log_R': 'R的对数',
            'N_squared': 'N的平方',
            'log_N': 'N的对数',
            'exp_minus_N': 'exp(-N/4)，限域效应衰减因子',
            
            # 交互特征
            'R_times_N': 'R×N交互项',
            
            # 温度区间（与 Phase 3 一致）
            'is_low_temp': '是否为低温段 (<230K)',
            'is_mid_temp': '是否为中温段 (230-270K)',
            'is_high_temp': '是否为高温段 (≥270K)',
            
            # 质量特征
            'quality_score': '数据质量评分 (0-100)',
            'quality_level': '质量等级 (excellent/good/acceptable/poor)',
            'use_for_modeling': '是否适合用于建模',
            
            # Arrhenius特征
            'n_segments': 'Arrhenius分段数量',
            'avg_R_squared': '平均拟合R²',
            
            # Arrhenius误差和sigma0特征（新增）
            'sigma0_mean': '前因子平均值 (S/cm)',
            'sigma0_median': '前因子中位数 (S/cm)',
            'sigma0_log_mean': '前因子对数平均值',
            'Ea_stderr_mean': 'Ea标准误差平均值 (eV)',
            'Ea_stderr_max': 'Ea标准误差最大值 (eV)',
            'p_value_mean': 'p-value平均值',
            'p_value_min': 'p-value最小值',
            'all_segments_significant': '所有分段是否显著 (1=是, 0=否)'
        }

