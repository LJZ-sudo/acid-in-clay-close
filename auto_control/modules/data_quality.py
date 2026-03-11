# -*- coding: utf-8 -*-
"""
EIS数据质量检查器 - 精简版
提供数据质量评估和评级功能

从 eis_data_analysis/phase1/core/data_quality_checker.py 移植
"""
import numpy as np
from typing import Dict, List, Tuple, Optional


class DataQualityChecker:
    """EIS数据质量检查器"""
    
    def __init__(self, 
                 rb_jump_threshold: float = 10.0,
                 noise_threshold: float = 0.8,
                 quality_threshold: float = 0.75,
                 consecutive_bad: int = 2):
        """
        Args:
            rb_jump_threshold: 体电阻相邻点跳变倍数阈值
            noise_threshold: 噪声水平阈值
            quality_threshold: 最低质量分数阈值
            consecutive_bad: 连续异常点数判定为系统性问题
        """
        self.rb_jump_threshold = rb_jump_threshold
        self.noise_threshold = noise_threshold
        self.quality_threshold = quality_threshold
        self.consecutive_bad = consecutive_bad
    
    def check_single_eis(self, freq: np.ndarray, zreal: np.ndarray, 
                         zimag: np.ndarray, temperature: float = None) -> Dict:
        """
        检查单个EIS测量的数据质量
        
        Args:
            freq: 频率数组 (Hz)
            zreal: 阻抗实部 (Ω)
            zimag: 阻抗虚部 (Ω)
            temperature: 温度 (K)，可选
        
        Returns:
            质量评估字典
        """
        if len(freq) < 5:
            return {
                'valid': False,
                'quality_score': 0.0,
                'grade': 'F',
                'message': '数据点不足',
                'details': {}
            }
        
        # 1. 计算噪声水平
        noise_level = self._calculate_noise_level(freq, zreal, zimag)
        
        # 2. 检查Nyquist图质量
        nyquist_quality = self._check_nyquist_quality(zreal, zimag)
        
        # 3. 检查频率覆盖
        freq_coverage = self._check_frequency_coverage(freq)
        
        # 4. 检查数据连续性
        continuity = self._check_data_continuity(freq, zreal, zimag)
        
        # 5. 综合质量分数
        quality_score = (
            nyquist_quality * 0.35 +
            (1 - min(1.0, noise_level)) * 0.25 +
            freq_coverage * 0.20 +
            continuity * 0.20
        )
        
        # 6. 评级
        if quality_score >= 0.9:
            grade = 'A'
        elif quality_score >= 0.75:
            grade = 'B'
        elif quality_score >= 0.6:
            grade = 'C'
        elif quality_score >= 0.4:
            grade = 'D'
        else:
            grade = 'F'
        
        return {
            'valid': quality_score >= self.quality_threshold,
            'quality_score': float(quality_score),
            'grade': grade,
            'message': f'数据质量评级: {grade} ({quality_score:.2f})',
            'details': {
                'noise_level': float(noise_level),
                'nyquist_quality': float(nyquist_quality),
                'freq_coverage': float(freq_coverage),
                'continuity': float(continuity),
                'n_points': len(freq),
                'freq_range': (float(freq.min()), float(freq.max())),
                'temperature': temperature
            }
        }
    
    def _calculate_noise_level(self, freq: np.ndarray, zreal: np.ndarray, 
                               zimag: np.ndarray) -> float:
        """计算噪声水平"""
        if len(freq) < 5:
            return 1.0
        
        # 按频率排序
        sort_idx = np.argsort(freq)
        zreal_sorted = zreal[sort_idx]
        zimag_sorted = zimag[sort_idx]
        
        # 计算相邻点差分的标准差
        zreal_diff = np.diff(zreal_sorted)
        zimag_diff = np.diff(zimag_sorted)
        
        mean_zreal = np.mean(np.abs(zreal))
        mean_zimag = np.mean(np.abs(zimag))
        
        if mean_zreal > 0 and mean_zimag > 0:
            noise_real = np.std(zreal_diff) / mean_zreal
            noise_imag = np.std(zimag_diff) / mean_zimag
            noise_level = (noise_real + noise_imag) / 2
        else:
            noise_level = 1.0
        
        return min(1.0, noise_level)
    
    def _check_nyquist_quality(self, zreal: np.ndarray, zimag: np.ndarray) -> float:
        """检查Nyquist图质量"""
        # 检查是否有完整的半圆
        zreal_range = zreal.max() - zreal.min()
        zimag_max = np.abs(zimag).max()
        
        if zreal_range <= 0:
            return 0.0
        
        # 理想半圆的高度应该约为直径的一半
        semicircle_ratio = (zimag_max / zreal_range) * 2
        
        # 评分：比值接近1为最佳
        if semicircle_ratio > 0.3 and semicircle_ratio < 2.0:
            quality = min(1.0, semicircle_ratio if semicircle_ratio < 1 else 2 - semicircle_ratio)
        else:
            quality = 0.3
        
        return quality
    
    def _check_frequency_coverage(self, freq: np.ndarray) -> float:
        """检查频率覆盖范围"""
        freq_decades = np.log10(freq.max()) - np.log10(freq.min())
        
        # 理想覆盖：5个数量级
        coverage = min(1.0, freq_decades / 5.0)
        return coverage
    
    def _check_data_continuity(self, freq: np.ndarray, zreal: np.ndarray, 
                               zimag: np.ndarray) -> float:
        """检查数据连续性"""
        if len(freq) < 3:
            return 0.5
        
        # 检查是否有异常跳变
        z_magnitude = np.sqrt(zreal**2 + zimag**2)
        z_diff = np.abs(np.diff(z_magnitude))
        z_mean = np.mean(z_magnitude)
        
        if z_mean > 0:
            jump_ratio = z_diff / z_mean
            n_jumps = np.sum(jump_ratio > 0.5)  # 超过50%的跳变
            continuity = 1.0 - (n_jumps / len(z_diff))
        else:
            continuity = 0.5
        
        return max(0.0, continuity)


def assess_data_quality(freq: np.ndarray, zreal: np.ndarray, 
                        zimag: np.ndarray, temperature: float = None) -> Dict:
    """
    便捷函数：评估EIS数据质量
    
    Args:
        freq: 频率数组 (Hz)
        zreal: 阻抗实部 (Ω)
        zimag: 阻抗虚部 (Ω)
        temperature: 温度 (K)，可选
    
    Returns:
        质量评估结果字典
    """
    checker = DataQualityChecker()
    return checker.check_single_eis(freq, zreal, zimag, temperature)
