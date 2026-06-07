"""
Data Profiler - 数据画像器
识别 R/N 的覆盖范围与数据质量
"""

from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np

try:
    from ..config import Config
except ImportError:
    from config import Config


class DataProfiler:
    """
    数据画像器
    
    核心任务：
    1. 统计数据规模（行数、R/N 取值数量）
    2. 评估温度覆盖度（范围、是否宽温区）
    3. 检测特征完整度（EIS 形貌特征）
    4. 评估数据质量（R² 分布）
    """
    
    def __init__(
        self,
        name: str = "DataProfiler",
        wide_temp_threshold: float = None,
        high_quality_r2_threshold: float = None,
        low_temp_threshold: float = None,
        high_temp_threshold: float = None
    ):
        """
        初始化数据画像器
        
        Args:
            name: 画像器名称
            wide_temp_threshold: 宽温区判定阈值（K）
            high_quality_r2_threshold: 高质量数据 R² 阈值
            low_temp_threshold: 低温区上限（K），默认 230K
            high_temp_threshold: 高温区下限（K），默认 270K
        """
        self.name = name
        # 使用配置文件中的默认值
        self.wide_temp_threshold = wide_temp_threshold if wide_temp_threshold is not None else Config.data_profile.WIDE_TEMP_THRESHOLD
        self.high_quality_r2_threshold = high_quality_r2_threshold if high_quality_r2_threshold is not None else Config.data_profile.HIGH_QUALITY_R2_THRESHOLD
        self.low_temp_threshold = low_temp_threshold if low_temp_threshold is not None else Config.data_profile.LOW_TEMP_THRESHOLD
        self.high_temp_threshold = high_temp_threshold if high_temp_threshold is not None else Config.data_profile.HIGH_TEMP_THRESHOLD
    
    def profile(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        生成数据画像
        
        Args:
            df: 输入数据（DataFrame）
            
        Returns:
            Dict: 数据画像字典，包含所有统计信息
        """
        profile = {
            'profiler_name': self.name,
            'data_scale': {},
            'temperature_coverage': {},
            'feature_completeness': {},
            'quality_assessment': {},
            'warnings': [],
            'recommendations': []
        }
        
        # 检查数据是否为空
        if df is None or df.empty:
            profile['warnings'].append("数据为空，无法生成画像")
            profile['data_scale']['total_rows'] = 0
            return profile
        
        # 1. 数据规模统计
        profile['data_scale'] = self._assess_data_scale(df)
        
        # 2. 温度覆盖度评估
        profile['temperature_coverage'] = self._assess_temperature_coverage(df)
        
        # 3. 特征完整度检测
        profile['feature_completeness'] = self._assess_feature_completeness(df)
        
        # 4. 质量评估
        profile['quality_assessment'] = self._assess_data_quality(df)
        
        # 5. 生成建议
        profile['recommendations'] = self._generate_recommendations(profile)
        
        return profile
    
    def _assess_data_scale(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        评估数据规模
        
        Args:
            df: 输入数据
            
        Returns:
            Dict: 数据规模统计
        """
        scale = {
            'total_rows': len(df),
            'total_columns': len(df.columns),
            'column_names': list(df.columns)
        }
        
        # 统计 R 的取值
        r_columns = ['R', 'r', 'R_value', 'composition_R']
        for col in r_columns:
            if col in df.columns:
                r_values = df[col].dropna()
                if len(r_values) > 0:
                    scale['R_unique_count'] = int(r_values.nunique())
                    scale['R_min'] = float(r_values.min())
                    scale['R_max'] = float(r_values.max())
                    scale['R_range'] = float(r_values.max() - r_values.min())
                    scale['R_column'] = col
                    break
        
        # 统计 N 的取值
        n_columns = ['N', 'n', 'N_value', 'composition_N']
        for col in n_columns:
            if col in df.columns:
                n_values = df[col].dropna()
                if len(n_values) > 0:
                    scale['N_unique_count'] = int(n_values.nunique())
                    scale['N_min'] = float(n_values.min())
                    scale['N_max'] = float(n_values.max())
                    scale['N_range'] = float(n_values.max() - n_values.min())
                    scale['N_column'] = col
                    break
        
        # 如果没有找到 R 或 N 列
        if 'R_unique_count' not in scale:
            scale['R_unique_count'] = 0
            scale['R_available'] = False
        else:
            scale['R_available'] = True
        
        if 'N_unique_count' not in scale:
            scale['N_unique_count'] = 0
            scale['N_available'] = False
        else:
            scale['N_available'] = True
        
        return scale
    
    def _assess_temperature_coverage(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        评估温度覆盖度
        
        Args:
            df: 输入数据
            
        Returns:
            Dict: 温度覆盖度统计
        """
        coverage = {
            'has_temperature': False,
            'is_wide_temperature_range': False
        }
        
        # 查找温度列
        temp_columns = ['T', 'T_K', 'T_mid', 'temperature', 'temp', 'T_avg_K']
        temp_col = None
        
        for col in temp_columns:
            if col in df.columns:
                temp_col = col
                break
        
        if temp_col is None:
            coverage['warning'] = "未找到温度列"
            return coverage
        
        # 提取温度数据
        temp_values = df[temp_col].dropna()
        
        if len(temp_values) == 0:
            coverage['warning'] = "温度列无有效数据"
            return coverage
        
        coverage['has_temperature'] = True
        coverage['temperature_column'] = temp_col
        coverage['T_min'] = float(temp_values.min())
        coverage['T_max'] = float(temp_values.max())
        coverage['T_range'] = float(temp_values.max() - temp_values.min())
        coverage['T_mean'] = float(temp_values.mean())
        coverage['T_std'] = float(temp_values.std())
        coverage['n_temperature_points'] = int(len(temp_values))
        
        # 判断是否为宽温区
        coverage['is_wide_temperature_range'] = coverage['T_range'] > self.wide_temp_threshold
        
        # 温度区间分布
        if coverage['T_range'] > 0:
            # 定义温度区间（使用可配置阈值）
            if coverage['T_max'] >= self.high_temp_threshold:
                coverage['has_high_T'] = True
                coverage['high_T_count'] = int((temp_values >= self.high_temp_threshold).sum())
            else:
                coverage['has_high_T'] = False
                coverage['high_T_count'] = 0
            
            if coverage['T_min'] < self.low_temp_threshold:
                coverage['has_low_T'] = True
                coverage['low_T_count'] = int((temp_values < self.low_temp_threshold).sum())
            else:
                coverage['has_low_T'] = False
                coverage['low_T_count'] = 0
            
            mid_T_mask = (temp_values >= self.low_temp_threshold) & (temp_values < self.high_temp_threshold)
            coverage['has_mid_T'] = mid_T_mask.any()
            coverage['mid_T_count'] = int(mid_T_mask.sum())
        
        return coverage
    
    def _assess_feature_completeness(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        评估特征完整度
        
        Args:
            df: 输入数据
            
        Returns:
            Dict: 特征完整度统计
        """
        completeness = {
            'has_eis_features': False,
            'eis_feature_columns': [],
            'has_activation_energy': False,
            'has_conductivity': False,
            'has_composition': False
        }
        
        # 检测 EIS 形貌特征列
        eis_feature_names = [
            'arc_visible', 'semicircle_visible', 'nyquist_arc',
            'characteristic_frequency', 'peak_frequency',
            'arc_diameter', 'impedance_arc', 'eis_shape',
            'arc_diameter_ohm', 'semicircle_quality',
            'peak_neg_zimag_ohm', 'nyquist_peak_ratio',
            'nyquist_rising_ratio', 'nyquist_falling_ratio',
            'R_high_freq_ohm', 'R_low_freq_ohm', 'delta_R_ohm',
            'R_ratio', 'Rb', 'rb_ohm', 'R_bulk', 'resistance'
        ]
        
        for col in eis_feature_names:
            if col in df.columns:
                completeness['eis_feature_columns'].append(col)
        
        completeness['has_eis_features'] = len(completeness['eis_feature_columns']) > 0
        completeness['n_eis_features'] = len(completeness['eis_feature_columns'])
        
        # 检测活化能列
        ea_columns = ['Ea', 'Ea_eV', 'activation_energy', 'E_a']
        for col in ea_columns:
            if col in df.columns:
                ea_values = df[col].dropna()
                if len(ea_values) > 0:
                    completeness['has_activation_energy'] = True
                    completeness['activation_energy_column'] = col
                    completeness['Ea_min'] = float(ea_values.min())
                    completeness['Ea_max'] = float(ea_values.max())
                    completeness['Ea_mean'] = float(ea_values.mean())
                    completeness['n_Ea_points'] = int(len(ea_values))
                    break
        
        # 检测电导率列
        sigma_columns = ['sigma', 'conductivity', 'ln_sigma', 'log_sigma']
        for col in sigma_columns:
            if col in df.columns:
                sigma_values = df[col].dropna()
                if len(sigma_values) > 0:
                    completeness['has_conductivity'] = True
                    completeness['conductivity_column'] = col
                    completeness['n_conductivity_points'] = int(len(sigma_values))
                    break
        
        # 检测组分列
        has_R = any(col in df.columns for col in ['R', 'r', 'R_value'])
        has_N = any(col in df.columns for col in ['N', 'n', 'N_value'])
        completeness['has_composition'] = has_R or has_N
        
        # 计算特征完整度评分（0-100）
        score = 0
        if completeness['has_activation_energy']:
            score += 30
        if completeness['has_conductivity']:
            score += 25
        if completeness['has_composition']:
            score += 25
        if completeness['has_eis_features']:
            score += 20
        
        completeness['completeness_score'] = score
        
        return completeness
    
    def _assess_data_quality(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        评估数据质量
        
        Args:
            df: 输入数据
            
        Returns:
            Dict: 数据质量统计
        """
        quality = {
            'has_r2': False,
            'r2_statistics': {}
        }
        
        # 查找 R² 列
        r2_columns = ['R2', 'r2', 'R_squared', 'r_squared', 'fit_quality']
        r2_col = None
        
        for col in r2_columns:
            if col in df.columns:
                r2_col = col
                break
        
        if r2_col is None:
            quality['warning'] = "未找到 R2 列"
            return quality
        
        # 提取 R² 数据
        r2_values = df[r2_col].dropna()
        
        if len(r2_values) == 0:
            quality['warning'] = "R2 列无有效数据"
            return quality
        
        quality['has_r2'] = True
        quality['r2_column'] = r2_col
        
        # 统计 R² 分布
        quality['r2_statistics'] = {
            'n_points': int(len(r2_values)),
            'mean': float(r2_values.mean()),
            'std': float(r2_values.std()),
            'min': float(r2_values.min()),
            'max': float(r2_values.max()),
            'median': float(r2_values.median()),
            'q25': float(r2_values.quantile(0.25)),
            'q75': float(r2_values.quantile(0.75))
        }
        
        # 高质量数据占比
        high_quality_mask = r2_values > self.high_quality_r2_threshold
        quality['high_quality_count'] = int(high_quality_mask.sum())
        quality['high_quality_ratio'] = float(high_quality_mask.sum() / len(r2_values))
        
        # 质量等级评估
        if quality['high_quality_ratio'] >= 0.8:
            quality['quality_grade'] = 'excellent'
        elif quality['high_quality_ratio'] >= 0.6:
            quality['quality_grade'] = 'good'
        elif quality['high_quality_ratio'] >= 0.4:
            quality['quality_grade'] = 'fair'
        else:
            quality['quality_grade'] = 'poor'
        
        # 低质量数据统计
        low_quality_mask = r2_values < 0.85
        quality['low_quality_count'] = int(low_quality_mask.sum())
        quality['low_quality_ratio'] = float(low_quality_mask.sum() / len(r2_values))
        
        return quality
    
    def _generate_recommendations(self, profile: Dict[str, Any]) -> List[str]:
        """
        根据画像生成分析建议
        
        Args:
            profile: 数据画像
            
        Returns:
            List[str]: 建议列表
        """
        recommendations = []
        
        # 数据规模建议
        scale = profile['data_scale']
        if scale.get('total_rows', 0) < 10:
            recommendations.append("数据量过少（< 10 行），建议增加数据点以提高分析可靠性")
        
        if not scale.get('R_available', False) and not scale.get('N_available', False):
            recommendations.append("缺少组分信息（R 或 N），无法进行组分敏感性分析")
        
        # 温度覆盖度建议
        temp_cov = profile['temperature_coverage']
        if temp_cov.get('has_temperature', False):
            if not temp_cov.get('is_wide_temperature_range', False):
                recommendations.append(
                    f"温度范围较窄（{temp_cov.get('T_range', 0):.1f} K < {self.wide_temp_threshold} K），"
                    f"建议扩展温度范围以进行 VTF 模型拟合"
                )
            
            if not temp_cov.get('has_low_T', False):
                recommendations.append(f"缺少低温数据（T < {self.low_temp_threshold} K），可能影响相变特征检测")
            
            if not temp_cov.get('has_high_T', False):
                recommendations.append(f"缺少高温数据（T >= {self.high_temp_threshold} K），可能影响高温传输机制分析")
        else:
            recommendations.append("缺少温度信息，无法进行温度依赖性分析")
        
        # 特征完整度建议
        features = profile['feature_completeness']
        if not features.get('has_activation_energy', False):
            recommendations.append("缺少活化能数据，无法进行 Meyer-Neldel 分析")
        
        if not features.get('has_conductivity', False):
            recommendations.append("缺少电导率数据，无法进行 Arrhenius/VTF 模型竞争")
        
        if not features.get('has_eis_features', False):
            recommendations.append("缺少 EIS 形貌特征，无法进行 EIS-Arrhenius 对齐分析")
        
        # 数据质量建议
        quality = profile['quality_assessment']
        if quality.get('has_r2', False):
            if quality.get('quality_grade') == 'poor':
                recommendations.append(
                    f"数据质量较差（高质量数据占比 {quality.get('high_quality_ratio', 0)*100:.1f}%），"
                    f"建议进行数据清洗或重新拟合"
                )
            elif quality.get('quality_grade') == 'fair':
                recommendations.append(
                    f"数据质量一般（高质量数据占比 {quality.get('high_quality_ratio', 0)*100:.1f}%），"
                    f"建议关注低 R2 数据点的物理合理性"
                )
        
        # 如果没有任何建议，说明数据质量良好
        if not recommendations:
            recommendations.append("数据质量良好，可以进行全面的证据挖掘分析")
        
        return recommendations
    
    def print_summary(self, profile: Dict[str, Any]) -> None:
        """
        打印数据画像摘要
        
        Args:
            profile: 数据画像
        """
        print("\n" + "=" * 60)
        print("数据画像摘要")
        print("=" * 60)
        
        # 数据规模
        scale = profile['data_scale']
        print(f"\n[数据规模]")
        print(f"  总行数: {scale.get('total_rows', 0)}")
        print(f"  总列数: {scale.get('total_columns', 0)}")
        if scale.get('R_available', False):
            print(f"  R 取值数: {scale.get('R_unique_count', 0)} "
                  f"(范围: {scale.get('R_min', 0):.2f} - {scale.get('R_max', 0):.2f})")
        if scale.get('N_available', False):
            print(f"  N 取值数: {scale.get('N_unique_count', 0)} "
                  f"(范围: {scale.get('N_min', 0):.2f} - {scale.get('N_max', 0):.2f})")
        
        # 温度覆盖度
        temp_cov = profile['temperature_coverage']
        print(f"\n[温度覆盖度]")
        if temp_cov.get('has_temperature', False):
            print(f"  温度范围: {temp_cov.get('T_min', 0):.1f} - {temp_cov.get('T_max', 0):.1f} K "
                  f"(跨度: {temp_cov.get('T_range', 0):.1f} K)")
            print(f"  宽温区: {'是' if temp_cov.get('is_wide_temperature_range', False) else '否'}")
            print(f"  温度点数: {temp_cov.get('n_temperature_points', 0)}")
        else:
            print("  无温度数据")
        
        # 特征完整度
        features = profile['feature_completeness']
        print(f"\n[特征完整度]")
        print(f"  完整度评分: {features.get('completeness_score', 0)}/100")
        print(f"  活化能: {'有' if features.get('has_activation_energy', False) else '无'}")
        print(f"  电导率: {'有' if features.get('has_conductivity', False) else '无'}")
        print(f"  EIS 特征: {'有' if features.get('has_eis_features', False) else '无'} "
              f"({features.get('n_eis_features', 0)} 个特征列)")
        
        # 数据质量
        quality = profile['quality_assessment']
        print(f"\n[数据质量]")
        if quality.get('has_r2', False):
            r2_stats = quality.get('r2_statistics', {})
            print(f"  R2 平均值: {r2_stats.get('mean', 0):.3f}")
            print(f"  R2 中位数: {r2_stats.get('median', 0):.3f}")
            print(f"  高质量数据占比: {quality.get('high_quality_ratio', 0)*100:.1f}% "
                  f"(R2 > {self.high_quality_r2_threshold})")
            print(f"  质量等级: {quality.get('quality_grade', 'unknown')}")
        else:
            print("  无 R2 数据")
        
        # 建议
        recommendations = profile.get('recommendations', [])
        if recommendations:
            print(f"\n[分析建议]")
            for i, rec in enumerate(recommendations, 1):
                print(f"  {i}. {rec}")
        
        print("\n" + "=" * 60)
    
    def __repr__(self) -> str:
        return f"DataProfiler(name='{self.name}')"
