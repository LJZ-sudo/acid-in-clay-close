# -*- coding: utf-8 -*-
"""
Rb拟合模块 - 简化版
从V1.0-qianduan迁移核心功能
"""
import numpy as np
from sklearn.linear_model import LinearRegression
from typing import Dict, Any, Optional
import warnings
warnings.filterwarnings('ignore')


def get_fit_params() -> Dict[str, Any]:
    """获取拟合参数"""
    return {
        'linear_threshold': 0.92,
        'linear_progressive_threshold': 0.92,
        'max_remove_ratio': 0.35,
        'relaxed_threshold': 0.88,
        'very_relaxed_threshold': 0.85,
    }


def calculate_rb(
    zreal: np.ndarray, 
    zimag: np.ndarray, 
    temperature: float = None,
    fit_params: Dict = None,
    **kwargs
) -> Dict[str, Any]:
    """
    计算体相电阻Rb
    
    Args:
        zreal: 阻抗实部数组
        zimag: 阻抗虚部数组（绝对值）
        temperature: 温度（可选）
        fit_params: 拟合参数
        
    Returns:
        {'rb': float, 'method': str, 'r': float}
    """
    if fit_params is None:
        fit_params = get_fit_params()
    
    zreal = np.array(zreal)
    zimag = np.abs(np.array(zimag))  # 确保虚部为正
    
    # 过滤无效数据
    valid_mask = (zreal > 0) & (zimag >= 0) & np.isfinite(zreal) & np.isfinite(zimag)
    zreal = zreal[valid_mask]
    zimag = zimag[valid_mask]
    
    if len(zreal) < 5:
        return {'rb': None, 'method': 'failed', 'r': 0}
    
    # 方法1: X轴截距法（最高优先级）
    result = _x_intercept_method(zreal, zimag, fit_params)
    if result['rb'] is not None and result['rb'] > 0:
        return result
    
    # 方法2: 渐进线性拟合
    result = _progressive_linear_fit(zreal, zimag, fit_params)
    if result['rb'] is not None and result['rb'] > 0:
        return result
    
    # 方法3: 宽松线性拟合
    result = _relaxed_linear_fit(zreal, zimag, fit_params)
    if result['rb'] is not None and result['rb'] > 0:
        return result
    
    # 方法4: 高频平均兜底
    result = _high_freq_average(zreal, zimag)
    return result


def _x_intercept_method(
    zreal: np.ndarray, 
    zimag: np.ndarray,
    fit_params: Dict
) -> Dict[str, Any]:
    """X轴截距法：找Z_imag最接近0的点"""
    # 找Z_imag最接近0的点
    idx = np.argmin(np.abs(zimag))
    rb = zreal[idx]
    
    # 检查是否足够接近X轴
    if zimag[idx] < 5:  # Z_imag < 5Ω
        return {'rb': float(rb), 'method': 'x_intercept', 'r': 0.99}
    
    # 线性外推到X轴
    threshold = fit_params.get('linear_threshold', 0.92)
    
    # 取低频段数据（后20%）
    n = len(zreal)
    low_freq_start = int(n * 0.8)
    if n - low_freq_start < 3:
        return {'rb': None, 'method': 'x_intercept_failed', 'r': 0}
    
    x_seg = zreal[low_freq_start:]
    y_seg = zimag[low_freq_start:]
    
    r = _correlation(x_seg, y_seg)
    
    if abs(r) >= threshold:
        # 线性外推
        reg = LinearRegression().fit(x_seg.reshape(-1, 1), y_seg)
        if reg.coef_[0] != 0:
            rb = -reg.intercept_ / reg.coef_[0]
            if rb > 0:
                return {'rb': float(rb), 'method': 'x_intercept_extrapolate', 'r': abs(r)}
    
    return {'rb': None, 'method': 'x_intercept_failed', 'r': abs(r)}


def _progressive_linear_fit(
    zreal: np.ndarray, 
    zimag: np.ndarray,
    fit_params: Dict
) -> Dict[str, Any]:
    """渐进线性拟合：逐步移除低频数据"""
    threshold = fit_params.get('linear_progressive_threshold', 0.92)
    max_remove = int(len(zreal) * fit_params.get('max_remove_ratio', 0.35))
    
    best_rb = None
    best_r = 0
    
    for i in range(max_remove + 1):
        if i > 0:
            x_seg = zreal[:-i]
            y_seg = zimag[:-i]
        else:
            x_seg = zreal
            y_seg = zimag
        
        if len(x_seg) < 5:
            break
        
        r = abs(_correlation(x_seg, y_seg))
        
        if r >= threshold and r > best_r:
            reg = LinearRegression().fit(x_seg.reshape(-1, 1), y_seg)
            if reg.coef_[0] != 0:
                rb = -reg.intercept_ / reg.coef_[0]
                if rb > 0:
                    best_rb = rb
                    best_r = r
    
    if best_rb is not None:
        return {'rb': float(best_rb), 'method': 'progressive_linear', 'r': best_r}
    
    return {'rb': None, 'method': 'progressive_linear_failed', 'r': best_r}


def _relaxed_linear_fit(
    zreal: np.ndarray, 
    zimag: np.ndarray,
    fit_params: Dict
) -> Dict[str, Any]:
    """宽松线性拟合"""
    threshold = fit_params.get('relaxed_threshold', 0.88)
    
    # 取中段数据
    n = len(zreal)
    start = int(n * 0.2)
    end = int(n * 0.8)
    
    x_seg = zreal[start:end]
    y_seg = zimag[start:end]
    
    if len(x_seg) < 5:
        return {'rb': None, 'method': 'relaxed_failed', 'r': 0}
    
    r = abs(_correlation(x_seg, y_seg))
    
    if r >= threshold:
        reg = LinearRegression().fit(x_seg.reshape(-1, 1), y_seg)
        if reg.coef_[0] != 0:
            rb = -reg.intercept_ / reg.coef_[0]
            if rb > 0:
                return {'rb': float(rb), 'method': 'relaxed_linear', 'r': r}
    
    return {'rb': None, 'method': 'relaxed_failed', 'r': r}


def _high_freq_average(zreal: np.ndarray, zimag: np.ndarray) -> Dict[str, Any]:
    """高频平均兜底方法"""
    # 取高频端（前10%）最小Z_real
    n = len(zreal)
    high_freq_count = max(3, int(n * 0.1))
    
    rb = np.min(zreal[:high_freq_count])
    
    return {'rb': float(rb), 'method': 'high_freq_min', 'r': 0.5}


def _correlation(x: np.ndarray, y: np.ndarray) -> float:
    """计算皮尔逊相关系数"""
    if len(x) < 3:
        return 0.0
    
    x_mean = np.mean(x)
    y_mean = np.mean(y)
    
    numerator = np.sum((x - x_mean) * (y - y_mean))
    denominator = np.sqrt(np.sum((x - x_mean)**2) * np.sum((y - y_mean)**2))
    
    if denominator == 0:
        return 0.0
    
    return numerator / denominator
