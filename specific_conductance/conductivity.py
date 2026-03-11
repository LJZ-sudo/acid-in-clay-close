# -*- coding: utf-8 -*-
"""
电导率计算模块 - Phase 1整合版

参数配置已更新为Phase 1的宽松阈值，适应真实数据噪声
"""

import os
import matplotlib.pyplot as plt
import matplotlib
from .rb_fitting import calculate_rb, visualize_fitting

# 全局设置matplotlib支持中文和负号
matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
matplotlib.rcParams['axes.unicode_minus'] = False


def get_fit_params():
    """
    获取拟合参数 (Phase 1整合版)
    
    参数说明：
    - linear_threshold: 整体线性判断阈值（降低以适应真实数据噪声）
    - linear_progressive_threshold: 渐进线性判断阈值
    - circle_linear_threshold: 圆拟合中线性区判断阈值
    - relaxed_threshold: 宽松线性阈值
    - very_relaxed_threshold: 最宽松线性阈值（Phase 1新增）
    - max_remove_ratio: 最多移除数据比例（增加以允许移除更多低频扩散尾）
    - enable_preprocessing: 是否启用Savitzky-Golay预处理
    """
    return {
        # Phase 1 降低阈值（从0.999→0.92），适应真实数据
        'linear_threshold': 0.92,
        'linear_progressive_threshold': 0.92,
        'circle_linear_threshold': 0.95,
        
        # 宽松阈值
        'relaxed_threshold': 0.88,        # 原为0.9
        'very_relaxed_threshold': 0.85,   # Phase 1新增
        
        # Phase 1 增加移除比例（从0.2→0.35）
        'max_remove_ratio': 0.35,
        
        # 圆拟合参数
        'huber_tau': 10.0,
        'circle_max_iter': 50,            # 增加迭代次数
        'circle_tol': 1e-6,
        
        # Phase 1新增：预处理参数
        'enable_preprocessing': True,
        'filter_window': 7,
        'filter_poly': 3,
        'outlier_threshold': 3.0,
    }


def calculate_conductivity(rb, thickness, area):
    """
    计算单一温度下的电导率
    
    Args:
        rb: 体相电阻 (Ω)
        thickness: 薄膜厚度 (cm)
        area: 电极面积 (cm²)
    
    Returns:
        conductivity: 电导率 (S/cm)，如果rb为None则返回None
    """
    if rb is None or rb <= 0:
        return None
    return thickness / (rb * area)


def visualize_conductivity(conductivity_results, save_dir):
    """
    绘制温度-电导率关系图
    
    Args:
        conductivity_results: [(温度, 电导率), ...]
        save_dir: 图片保存目录
    """
    matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
    matplotlib.rcParams['axes.unicode_minus'] = False
    
    os.makedirs(save_dir, exist_ok=True)
    
    if not conductivity_results:
        print("无有效电导率数据, 跳过可视化")
        return
    
    temps, conds = zip(*conductivity_results)
    
    plt.figure(figsize=(6, 5))
    plt.plot(temps, conds, 'bo-', markersize=6)
    plt.xlabel('温度 (K)')
    plt.ylabel('电导率 (S/cm)')
    plt.title('电导率随温度变化')
    plt.grid(True)
    plt.tight_layout()
    
    save_path = os.path.join(save_dir, 'conductivity_vs_temperature.png')
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"电导率-温度关系图已保存: {save_path}")
