# -*- coding: utf-8 -*-
"""
Kramers-Kronig (KK) 一致性校验模块

实现轻量级 lin-KK 方法（基于 Schönleber 2014）：
- 不依赖外部重型库
- 通过残差分析评估数据质量
- 输出 KK 一致性评分和通过/失败状态

参考文献:
Schönleber et al. (2014) "A Method for Improving the Robustness of linear 
Kramers-Kronig Validity Tests" Electrochimica Acta, 131, 20-27.

从 eis_data_analysis/phase1/core/kk_validation.py 移植
"""

import numpy as np
from typing import Dict, Tuple, Optional


class KKValidator:
    """Kramers-Kronig 一致性校验器（轻量工程版）"""
    
    def __init__(self, 
                 residual_threshold: float = 0.30,
                 min_points: int = 10,
                 freq_decades_min: float = 2.0):
        """
        初始化 KK 校验器
        
        Args:
            residual_threshold: 残差阈值（< 30% 为通过，工程版阈值）
            min_points: 最小数据点数
            freq_decades_min: 最小频率跨度（decade）
        """
        self.residual_threshold = residual_threshold
        self.min_points = min_points
        self.freq_decades_min = freq_decades_min
    
    def check(self, freq: np.ndarray, zreal: np.ndarray, zimag: np.ndarray) -> Dict:
        """
        执行 KK 一致性校验
        
        Args:
            freq: 频率数组 (Hz)
            zreal: 阻抗实部 (Ω)
            zimag: 阻抗虚部 (Ω)
        
        Returns:
            {
                'ok': bool,
                'score': float,  # 0-1，越高越好
                'residual_real': float,
                'residual_imag': float,
                'method': str,
                'message': str,
                'details': dict
            }
        """
        # 预检查
        if len(freq) < self.min_points:
            return {
                'ok': False,
                'score': 0.0,
                'residual_real': None,
                'residual_imag': None,
                'method': 'lin_kk_lite',
                'message': f'数据点不足（需要至少 {self.min_points} 个，实际 {len(freq)}）',
                'details': {}
            }
        
        # 检查频率跨度
        freq_decades = np.log10(freq.max()) - np.log10(freq.min())
        if freq_decades < self.freq_decades_min:
            return {
                'ok': False,
                'score': 0.0,
                'residual_real': None,
                'residual_imag': None,
                'method': 'lin_kk_lite',
                'message': f'频率跨度不足（需要至少 {self.freq_decades_min:.1f} decade，实际 {freq_decades:.1f}）',
                'details': {'freq_decades': freq_decades}
            }
        
        try:
            residual_real, residual_imag = self._lin_kk_check(freq, zreal, zimag)
            max_residual = max(residual_real, residual_imag)
            score = max(0.0, 1.0 - max_residual / self.residual_threshold)
            ok = max_residual < self.residual_threshold
            
            message = 'KK 校验通过' if ok else f'KK 校验失败（残差 {max_residual:.2%} > {self.residual_threshold:.2%}）'
            
            return {
                'ok': ok,
                'score': float(score),
                'residual_real': float(residual_real),
                'residual_imag': float(residual_imag),
                'method': 'lin_kk_lite',
                'message': message,
                'details': {'freq_decades': freq_decades, 'n_points': len(freq)}
            }
            
        except Exception as e:
            return {
                'ok': False,
                'score': 0.0,
                'residual_real': None,
                'residual_imag': None,
                'method': 'lin_kk_lite',
                'message': f'KK 校验异常: {str(e)}',
                'details': {'error': str(e)}
            }
    
    def _lin_kk_check(self, freq: np.ndarray, zreal: np.ndarray, zimag: np.ndarray) -> Tuple[float, float]:
        """轻量级 lin-KK 校验实现"""
        sort_idx = np.argsort(freq)
        freq = freq[sort_idx]
        zreal = zreal[sort_idx]
        zimag = zimag[sort_idx]
        
        omega = 2 * np.pi * freq
        
        zimag_predicted = self._kk_real_to_imag(omega, zreal)
        zreal_predicted = self._kk_imag_to_real(omega, zimag)
        
        z_magnitude = np.sqrt(zreal**2 + zimag**2)
        z_magnitude_mean = np.mean(z_magnitude)
        
        if z_magnitude_mean > 0:
            residual_real = np.mean(np.abs(zreal - zreal_predicted)) / z_magnitude_mean
            residual_imag = np.mean(np.abs(zimag - zimag_predicted)) / z_magnitude_mean
        else:
            residual_real = 1.0
            residual_imag = 1.0
        
        return residual_real, residual_imag
    
    def _kk_real_to_imag(self, omega: np.ndarray, zreal: np.ndarray) -> np.ndarray:
        """从实部通过 KK 关系预测虚部"""
        zimag_pred = np.zeros_like(omega)
        
        for i, w in enumerate(omega):
            zreal_inf = zreal[-1]
            mask = np.abs(omega - w) > 0.1 * w
            if np.sum(mask) < 3:
                continue
            
            x = omega[mask]
            y = (zreal[mask] - zreal_inf) / (x**2 - w**2)
            integral = np.trapz(y, x)
            zimag_pred[i] = -(2 * w / np.pi) * integral
        
        return zimag_pred
    
    def _kk_imag_to_real(self, omega: np.ndarray, zimag: np.ndarray) -> np.ndarray:
        """从虚部通过 KK 关系预测实部"""
        zreal_pred = np.zeros_like(omega)
        zreal_inf = 0.0
        
        for i, w in enumerate(omega):
            mask = np.abs(omega - w) > 0.1 * w
            if np.sum(mask) < 3:
                zreal_pred[i] = zreal_inf
                continue
            
            x = omega[mask]
            y = x * zimag[mask] / (x**2 - w**2)
            integral = np.trapz(y, x)
            zreal_pred[i] = zreal_inf + (2 / np.pi) * integral
        
        return zreal_pred


def preprocess_eis_data(freq: np.ndarray, zreal: np.ndarray, zimag: np.ndarray,
                        remove_outliers: bool = True,
                        outlier_iqr_factor: float = 1.5) -> tuple:
    """
    EIS 数据预处理：频率排序 + 离群点剔除
    """
    preprocess_info = {
        'original_points': len(freq),
        'freq_sorted': False,
        'outliers_removed': 0
    }
    
    if not np.all(np.diff(freq) <= 0):
        sort_idx = np.argsort(freq)[::-1]
        freq = freq[sort_idx]
        zreal = zreal[sort_idx]
        zimag = zimag[sort_idx]
        preprocess_info['freq_sorted'] = True
    
    if remove_outliers and len(freq) > 10:
        z_magnitude = np.sqrt(zreal**2 + zimag**2)
        q1, q3 = np.percentile(z_magnitude, [25, 75])
        iqr = q3 - q1
        
        if iqr > 0:
            lower = q1 - outlier_iqr_factor * iqr
            upper = q3 + outlier_iqr_factor * iqr
            mask = (z_magnitude >= lower) & (z_magnitude <= upper)
            
            if np.sum(mask) >= len(freq) * 0.8:
                n_removed = len(freq) - np.sum(mask)
                freq = freq[mask]
                zreal = zreal[mask]
                zimag = zimag[mask]
                preprocess_info['outliers_removed'] = int(n_removed)
    
    preprocess_info['final_points'] = len(freq)
    return freq, zreal, zimag, preprocess_info


def kk_check(freq: np.ndarray, zreal: np.ndarray, zimag: np.ndarray, 
             residual_threshold: float = 0.30,
             preprocess: bool = True) -> Dict:
    """
    便捷函数：执行 KK 一致性校验
    
    Args:
        freq: 频率数组 (Hz)
        zreal: 阻抗实部 (Ω)
        zimag: 阻抗虚部 (Ω)
        residual_threshold: 残差阈值（默认 30%）
        preprocess: 是否进行预处理
    
    Returns:
        KK 校验结果字典
    """
    preprocess_info = None
    
    if preprocess:
        freq, zreal, zimag, preprocess_info = preprocess_eis_data(freq, zreal, zimag)
    
    validator = KKValidator(residual_threshold=residual_threshold)
    result = validator.check(freq, zreal, zimag)
    
    if preprocess_info:
        result['details']['preprocess'] = preprocess_info
    
    return result
