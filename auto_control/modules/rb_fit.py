# -*- coding: utf-8 -*-
"""
Rb拟合模块：滤波 + Rb拟合 + 质量评估
"""

import os
import sys
from pathlib import Path
import numpy as np
from typing import Dict, Tuple, Optional

# 统一 standalone 路径初始化
CLOSE_ROOT = Path(__file__).resolve().parents[2]
if str(CLOSE_ROOT) not in sys.path:
    sys.path.insert(0, str(CLOSE_ROOT))

# ============================================================
# 🔥 强制导入真实模块，不使用任何模拟代码
# ============================================================
from specific_conductance.data_processing import filter_data
from specific_conductance.rb_fitting import calculate_rb
from specific_conductance.conductivity import get_fit_params, calculate_conductivity
MODULES_AVAILABLE = True
print("[rb_fit] imported specific_conductance successfully")


def perform_rb_fitting(
    frequencies: np.ndarray,
    z_real: np.ndarray,
    z_imag: np.ndarray,
    temperature_C: float,
    thickness: float = 0.01,
    area: float = 1.0,
    circle_dir: str = None
) -> Dict:
    """
    执行完整的Rb拟合流程
    
    参数:
        frequencies: 频率数组
        z_real: 实部阻抗数组
        z_imag: 虚部阻抗数组
        temperature_C: 温度（摄氏度）
        thickness: 样品厚度（cm）
        area: 样品面积（cm²）
        circle_dir: 圆拟合图片保存目录
        
    返回:
        结果字典，包含：
        - success: bool
        - rb_ohm: float
        - rb_method: str
        - fit_quality: float (r值)
        - conductivity_S_per_cm: float
        - failure_reason: str (如果失败)
        - data_points_original: int
        - data_points_filtered: int
    """
    # 模块必须可用，否则导入时就会失败
    
    try:
        # 1. 数据滤波
        freq_filtered, zreal_filtered, zimag_filtered = filter_data(
            frequencies, z_real, z_imag
        )
        
        if len(freq_filtered) < 5:
            return {
                'success': False,
                'rb_ohm': None,
                'rb_method': '滤波失败',
                'fit_quality': None,
                'conductivity_S_per_cm': None,
                'failure_reason': f'滤波后数据点不足 ({len(freq_filtered)}个)',
                'data_points_original': len(frequencies),
                'data_points_filtered': len(freq_filtered)
            }
        
        # 2. 获取拟合参数
        fit_params = get_fit_params()
        
        # 3. 创建circle_dir
        if circle_dir is None:
            circle_dir = os.path.join(str(CLOSE_ROOT), 'experiment_data', 'circle_fits')
        os.makedirs(circle_dir, exist_ok=True)
        
        # 4. Rb拟合
        temperature_K = temperature_C + 273.15
        rb_result = calculate_rb(
            zreal_filtered,
            zimag_filtered,
            temperature_K,
            fit_params,
            circle_dir=circle_dir,
            freq=freq_filtered  # 传递频率数组用于X轴交点检测
        )
        
        # 5. 提取结果
        rb = rb_result.get('rb')
        method = rb_result.get('method', '未知')
        r_value = rb_result.get('r')
        
        # 6. 判断成功/失败
        if rb is None or method == 'failed':
            return {
                'success': False,
                'rb_ohm': rb,
                'rb_method': method,
                'fit_quality': r_value,
                'conductivity_S_per_cm': None,
                'failure_reason': '拟合失败：所有拟合方法（线性/逐步线性/圆弧）均未达标',
                'data_points_original': len(frequencies),
                'data_points_filtered': len(freq_filtered)
            }
        
        # 7. 计算电导率
        conductivity = None
        if rb > 0:
            conductivity = calculate_conductivity(rb, thickness, area)
        
        return {
            'success': True,
            'rb_ohm': rb,
            'rb_method': method,
            'fit_quality': r_value,
            'conductivity_S_per_cm': conductivity,
            'failure_reason': None,
            'data_points_original': len(frequencies),
            'data_points_filtered': len(freq_filtered)
        }
        
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        
        return {
            'success': False,
            'rb_ohm': None,
            'rb_method': '处理异常',
            'fit_quality': None,
            'conductivity_S_per_cm': None,
            'failure_reason': f'处理异常: {str(e)}',
            'error_detail': error_detail,
            'data_points_original': len(frequencies),
            'data_points_filtered': 0
        }


def assess_fit_quality(fit_result: Dict) -> str:
    """
    评估拟合质量
    
    参数:
        fit_result: perform_rb_fitting的返回结果
        
    返回:
        质量等级：'excellent', 'good', 'acceptable', 'poor', 'failed'
    """
    if not fit_result.get('success'):
        return 'failed'
    
    r_value = fit_result.get('fit_quality')
    method = fit_result.get('rb_method')
    
    if r_value is None:
        return 'poor'
    
    # 根据拟合方法和r值评估
    if method == 'linear' and r_value >= 0.999:
        return 'excellent'
    elif method == 'linear_progressive' and r_value >= 0.995:
        return 'good'
    elif method == 'circle':
        return 'good'
    elif method == 'linear_relaxed' and r_value >= 0.99:
        return 'acceptable'
    elif r_value >= 0.98:
        return 'acceptable'
    else:
        return 'poor'

