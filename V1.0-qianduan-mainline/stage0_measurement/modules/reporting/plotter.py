# -*- coding: utf-8 -*-
"""
EIS 实验结果绘图工具（纯函数版）

提供 Arrhenius 电导率图、温度曲线图等科研级可视化

核心原则：
1. 纯函数 - 只接受数据数组/字典和输出路径参数
2. 标准错误字典 - 失败时返回 {"success": False, "error": "..."}
3. 无全局副作用 - 不修改模块级 matplotlib.rcParams
4. 明确参数传递 - 不在内部推导路径

版本：3.0.0 (重构版)
"""

import os
from typing import Dict, List, Tuple, Optional, Any

import matplotlib
matplotlib.use('Agg')  # 非交互式后端
import matplotlib.pyplot as plt
import numpy as np
from scipy import stats


# ============================================================
# 公共接口：Arrhenius 电导率图（文献风格）
# ============================================================

def plot_conductivity_arrhenius(
    temperatures_K,
    conductivities_S_cm,
    output_path,
    segments=None,
    material_name="Sample",
    phase_transitions=None,
    plot_style=None
):
    """
    绘制电导率 Arrhenius 图（纯函数版）
    
    双横坐标：底部 1000/T (K^-1)，顶部 T (°C)
    
    Args:
        temperatures_K: 温度数组 (K)
        conductivities_S_cm: 电导率数组 (S/cm)
        output_path: 输出文件路径（完整路径，包括文件名）
        segments: 分段信息列表（可选）
            [{"T_range_C": (T_low, T_high), "Ea_kJ_per_mol": float, ...}, ...]
        material_name: 材料名称（默认 "Sample"）
        phase_transitions: 相变点列表（可选）
            [{"range": (T_high, T_low), ...}, ...]
        plot_style: 绘图风格字典（可选）
            {"figure_size": (10, 8), "dpi": 300, "font_family": "Arial", ...}
    
    Returns:
        dict: 包含以下字段
            - success: bool
            - filepath: str，保存的文件路径
            - n_points: int，绘制的数据点数
            - n_segments: int，分段数
            - error: str or None
    """
    # 验证输入
    if len(temperatures_K) != len(conductivities_S_cm):
        return {
            'success': False,
            'filepath': None,
            'n_points': 0,
            'n_segments': 0,
            'error': 'Temperature and conductivity arrays have different lengths'
        }
    
    if len(temperatures_K) == 0:
        return {
            'success': False,
            'filepath': None,
            'n_points': 0,
            'n_segments': 0,
            'error': 'No data points to plot'
        }
    
    # 转换为 numpy 数组
    temps_K = np.array(temperatures_K, dtype=float)
    sigma_S_cm = np.array(conductivities_S_cm, dtype=float)
    
    # 过滤无效数据
    valid_mask = (temps_K > 0) & (sigma_S_cm > 0) & np.isfinite(temps_K) & np.isfinite(sigma_S_cm)
    temps_K = temps_K[valid_mask]
    sigma_S_cm = sigma_S_cm[valid_mask]
    
    if len(temps_K) == 0:
        return {
            'success': False,
            'filepath': None,
            'n_points': 0,
            'n_segments': 0,
            'error': 'No valid data points after filtering'
        }
    
    # 转换单位和坐标
    temps_C = temps_K - 273.15
    inv_T_1000 = 1000.0 / temps_K
    sigma_mS_cm = sigma_S_cm * 1000  # S/cm -> mS/cm
    log_sigma = np.log10(sigma_mS_cm)
    
    # 排序（按 1000/T 从小到大）
    sort_idx = np.argsort(inv_T_1000)
    inv_T_sorted = inv_T_1000[sort_idx]
    log_sigma_sorted = log_sigma[sort_idx]
    temps_C_sorted = temps_C[sort_idx]
    temps_K_sorted = temps_K[sort_idx]
    
    # 绘图风格
    style = plot_style or {}
    fig_size = style.get('figure_size', (10, 8))
    dpi = style.get('dpi', 300)
    font_family = style.get('font_family', 'Arial')
    font_size = style.get('font_size', 12)
    line_width = style.get('line_width', 1.5)
    
    try:
        # 创建图形（在函数内设置 rcParams，避免全局污染）
        with plt.rc_context({
            'font.family': font_family,
            'font.size': font_size,
            'axes.linewidth': line_width,
            'font.sans-serif': ['SimHei', 'DejaVu Sans'],
            'axes.unicode_minus': False
        }):
            fig, ax1 = plt.subplots(figsize=fig_size)
            ax1.set_facecolor('white')
            fig.patch.set_facecolor('white')
            
            # 绘制数据点和拟合线
            if segments and len(segments) > 0:
                # 分段绘制
                markers = ['*', 's', '^', 'o', 'D', 'p', 'v', 'h']
                colors = ['#E74C3C', '#27AE60', '#F39C12', '#3498DB', '#9B59B6', '#1ABC9C', '#E67E22', '#34495E']
                
                for idx, seg in enumerate(segments):
                    # 支持两种字段名：T_range_C (摄氏度) 或 temp_range_K (开尔文)
                    t_range_c = seg.get('T_range_C')
                    if t_range_c is None:
                        # 如果没有 T_range_C，尝试从 temp_range_K 转换
                        temp_range_k = seg.get('temp_range_K')
                        if temp_range_k and len(temp_range_k) == 2:
                            t_range_c = (temp_range_k[0] - 273.15, temp_range_k[1] - 273.15)
                    
                    if t_range_c is None or len(t_range_c) != 2:
                        continue
                    if t_range_c[0] is None or t_range_c[1] is None:
                        continue
                    
                    t_k_min = min(t_range_c) + 273.15
                    t_k_max = max(t_range_c) + 273.15
                    
                    mask = (temps_K_sorted >= t_k_min) & (temps_K_sorted <= t_k_max)
                    if not np.any(mask):
                        continue
                    
                    inv_T_seg = inv_T_sorted[mask]
                    log_sigma_seg = log_sigma_sorted[mask]
                    
                    # 支持两种字段名：Ea_kJ_per_mol 或 ea_kJ_per_mol
                    Ea = seg.get('Ea_kJ_per_mol') or seg.get('ea_kJ_per_mol', 0)
                    
                    # 散点
                    ax1.scatter(
                        inv_T_seg,
                        log_sigma_seg,
                        label=f"{material_name} (Ea={Ea:.1f} kJ/mol)" if idx == 0 else f"Segment {idx+1} (Ea={Ea:.1f} kJ/mol)",
                        color=colors[idx % len(colors)],
                        marker=markers[idx % len(markers)],
                        s=120,
                        edgecolors='white' if markers[idx % len(markers)] == '*' else 'black',
                        linewidths=1.0,
                        alpha=0.9,
                        zorder=10
                    )
                    
                    # 拟合线
                    if len(inv_T_seg) >= 2:
                        slope, intercept, _, _, _ = stats.linregress(inv_T_seg, log_sigma_seg)
                        x_fit = np.linspace(inv_T_seg.min(), inv_T_seg.max(), 100)
                        y_fit = slope * x_fit + intercept
                        ax1.plot(x_fit, y_fit, color='gray', linestyle='--', linewidth=1.5, alpha=0.7, zorder=5)
            else:
                # 无分段，整体绘制
                ax1.scatter(
                    inv_T_sorted,
                    log_sigma_sorted,
                    color='#E74C3C',
                    s=120,
                    label=material_name,
                    marker='*',
                    edgecolors='white',
                    linewidths=1.0,
                    alpha=0.9,
                    zorder=10
                )
                
                # 整体拟合
                if len(inv_T_sorted) >= 2:
                    slope, intercept, _, _, _ = stats.linregress(inv_T_sorted, log_sigma_sorted)
                    R = 8.314
                    Ea_J_mol = -slope * 2.303 * R * 1000
                    Ea_kJ_mol = Ea_J_mol / 1000
                    
                    x_fit = np.linspace(inv_T_sorted.min(), inv_T_sorted.max(), 100)
                    y_fit = slope * x_fit + intercept
                    ax1.plot(x_fit, y_fit, color='gray', linestyle='--', linewidth=1.5, alpha=0.7,
                            label=f'Linear fit (Ea={Ea_kJ_mol:.1f} kJ/mol)')
            
            # 相变标记
            if phase_transitions:
                plotted_phases = set()
                for phase in phase_transitions:
                    T_high, T_low = phase.get('range', (None, None))
                    if T_high is None or T_low is None:
                        continue
                    
                    phase_key = (round(T_high, 1), round(T_low, 1))
                    if phase_key in plotted_phases:
                        continue
                    plotted_phases.add(phase_key)
                    
                    inv_T_high = 1000.0 / (T_high + 273.15)
                    inv_T_low = 1000.0 / (T_low + 273.15)
                    ax1.axvspan(
                        min(inv_T_high, inv_T_low),
                        max(inv_T_high, inv_T_low),
                        alpha=0.15,
                        color='red',
                        label=f"Phase transition ({T_low:.0f} to {T_high:.0f} °C)"
                    )
            
            # 坐标轴设置
            x_margin = (inv_T_sorted.max() - inv_T_sorted.min()) * 0.1
            ax1.set_xlim(inv_T_sorted.min() - x_margin, inv_T_sorted.max() + x_margin)
            
            y_margin = (log_sigma_sorted.max() - log_sigma_sorted.min()) * 0.15
            ax1.set_ylim(log_sigma_sorted.min() - y_margin, log_sigma_sorted.max() + y_margin)
            
            ax1.set_xlabel(r'$1000/T$ (K$^{-1}$)', fontsize=14, fontweight='bold')
            ax1.set_ylabel(r'log $\sigma$ (mS cm$^{-1}$)', fontsize=14, fontweight='bold')
            
            # 顶部横坐标（温度 °C）
            ax2 = ax1.twiny()
            ax2.set_xlim(ax1.get_xlim())
            
            # 计算温度刻度
            typical_temps = []
            temp_min_C, temp_max_C = temps_C_sorted.min(), temps_C_sorted.max()
            for t in [60, 40, 20, 0, -20, -40, -60, -80, -100, -120]:
                if temp_min_C - 10 <= t <= temp_max_C + 10:
                    typical_temps.append(t)
            
            if len(typical_temps) < 3:
                typical_temps = np.linspace(temp_min_C, temp_max_C, 5).astype(int).tolist()
            
            typical_temps = sorted(typical_temps, reverse=True)
            typical_inv_T = [1000.0 / (t + 273.15) for t in typical_temps]
            
            ax2.set_xticks(typical_inv_T)
            ax2.set_xticklabels([f'{int(t)}' for t in typical_temps])
            ax2.set_xlabel(r'$T$ (°C)', fontsize=14, fontweight='bold')
            
            # 刻度样式
            ax1.tick_params(axis='both', which='major', labelsize=12, width=1.5, length=6, direction='in')
            ax2.tick_params(axis='x', which='major', labelsize=12, width=1.5, length=6, direction='in')
            
            # 网格
            ax1.grid(True, which='major', linestyle='--', linewidth=0.5, alpha=0.4, color='gray')
            
            # 图例
            handles, labels = ax1.get_legend_handles_labels()
            by_label = dict(zip(labels, handles))
            ax1.legend(by_label.values(), by_label.keys(), loc='upper right', framealpha=0.95, edgecolor='gray', fontsize=10)
            
            # 标题
            ax1.set_title(f'Arrhenius Plot - {material_name}', fontsize=16, fontweight='bold', pad=35)
            
            # 边框
            for spine in ax1.spines.values():
                spine.set_linewidth(1.5)
            for spine in ax2.spines.values():
                spine.set_linewidth(1.5)
            
            plt.tight_layout()
            
            # 保存
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            plt.savefig(output_path, dpi=dpi, bbox_inches='tight', facecolor='white')
            plt.close(fig)
            
            return {
                'success': True,
                'filepath': output_path,
                'n_points': len(temps_K),
                'n_segments': len(segments) if segments else 0,
                'error': None
            }
    
    except Exception as e:
        return {
            'success': False,
            'filepath': output_path,
            'n_points': len(temps_K),
            'n_segments': len(segments) if segments else 0,
            'error': f'Failed to plot Arrhenius: {str(e)}'
        }


# ============================================================
# 公共接口：温度曲线图
# ============================================================

def plot_temperature_profile(
    temperature_history,
    measurement_history,
    output_path,
    phase_transitions=None,
    material_name="Sample",
    plot_style=None
):
    """
    绘制温度变化曲线（纯函数版）
    
    Args:
        temperature_history: 温度历史列表 [(timestamp, temp_C), ...]
        measurement_history: 测量历史列表 [{"timestamp": float, "temperature_C": float, ...}, ...]
        output_path: 输出文件路径（完整路径，包括文件名）
        phase_transitions: 相变点列表（可选）
        material_name: 材料名称（默认 "Sample"）
        plot_style: 绘图风格字典（可选）
    
    Returns:
        dict: 包含以下字段
            - success: bool
            - filepath: str
            - n_points: int
            - error: str or None
    """
    # 验证输入
    if not temperature_history and not measurement_history:
        return {
            'success': False,
            'filepath': None,
            'n_points': 0,
            'error': 'No temperature data provided'
        }
    
    # 提取数据
    if temperature_history:
        times, temps = zip(*temperature_history)
    else:
        times = [m['timestamp'] for m in measurement_history]
        temps = [m['temperature_C'] for m in measurement_history]
    
    if not times:
        return {
            'success': False,
            'filepath': None,
            'n_points': 0,
            'error': 'No temperature data points'
        }
    
    # 计算相对时间
    if measurement_history:
        start_time = min(m['timestamp'] for m in measurement_history)
    else:
        start_time = min(times)
    
    timestamps = [max(0, t - start_time) / 3600 for t in times]  # 转换为小时
    
    # 绘图风格
    style = plot_style or {}
    fig_size = style.get('figure_size', (10, 6))
    dpi = style.get('dpi', 300)
    
    try:
        with plt.rc_context({
            'font.family': 'Arial',
            'font.size': 12,
            'axes.linewidth': 1.5,
            'font.sans-serif': ['SimHei', 'DejaVu Sans'],
            'axes.unicode_minus': False
        }):
            fig, ax = plt.subplots(figsize=fig_size)
            ax.set_facecolor('white')
            fig.patch.set_facecolor('white')
            
            # 绘制温度曲线
            ax.plot(timestamps, temps, color='#2E86AB', linewidth=2.0, label='Temperature', zorder=5)
            
            # 绘制测量点
            if measurement_history:
                meas_times = [max(0, m['timestamp'] - start_time) / 3600 for m in measurement_history]
                meas_temps = [m['temperature_C'] for m in measurement_history]
                ax.scatter(meas_times, meas_temps, c='#E74C3C', s=80, marker='o', edgecolors='white',
                          linewidths=1.5, label='EIS Measurement', zorder=10)
            
            # 相变标记
            if phase_transitions:
                plotted_phases = set()
                phase_colors = ['#27AE60', '#9B59B6', '#F39C12', '#1ABC9C']
                for idx, phase in enumerate(phase_transitions):
                    T_high, T_low = phase.get('range', (None, None))
                    if T_high is None or T_low is None:
                        continue
                    
                    phase_key = (round(T_high, 1), round(T_low, 1))
                    if phase_key in plotted_phases:
                        continue
                    plotted_phases.add(phase_key)
                    
                    mid_temp = (T_high + T_low) / 2
                    min_diff = float('inf')
                    phase_time = None
                    
                    for t, temp in zip(times, temps):
                        if t >= start_time:
                            diff = abs(temp - mid_temp)
                            if diff < min_diff:
                                min_diff = diff
                                phase_time = t
                    
                    if phase_time is not None:
                        phase_time_hours = max(0, phase_time - start_time) / 3600
                        color = phase_colors[idx % len(phase_colors)]
                        ax.axvline(x=phase_time_hours, color=color, linestyle='--', linewidth=1.5, alpha=0.8,
                                  label=f"Phase transition ({phase_key[1]:.0f} to {phase_key[0]:.0f} °C)")
            
            # 坐标轴设置
            ax.set_xlabel('Time (h)', fontsize=14, fontweight='bold')
            ax.set_ylabel('Temperature (°C)', fontsize=14, fontweight='bold')
            ax.set_title(f'Temperature Profile - {material_name}', fontsize=16, fontweight='bold', pad=15)
            ax.tick_params(axis='both', which='major', labelsize=12, width=1.5, length=6, direction='in')
            ax.grid(True, which='major', linestyle='--', linewidth=0.5, alpha=0.5, color='gray')
            ax.set_xlim(left=0)
            
            # 图例
            handles, labels = ax.get_legend_handles_labels()
            by_label = dict(zip(labels, handles))
            ax.legend(by_label.values(), by_label.keys(), loc='upper right', framealpha=0.95, edgecolor='gray', fontsize=10)
            
            # 边框
            for spine in ax.spines.values():
                spine.set_linewidth(1.5)
            
            plt.tight_layout()
            
            # 保存
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            plt.savefig(output_path, dpi=dpi, bbox_inches='tight', facecolor='white')
            plt.close(fig)
            
            return {
                'success': True,
                'filepath': output_path,
                'n_points': len(times),
                'error': None
            }
    
    except Exception as e:
        return {
            'success': False,
            'filepath': output_path,
            'n_points': len(times) if times else 0,
            'error': f'Failed to plot temperature profile: {str(e)}'
        }


# ============================================================
# 辅助函数：数据质量图表
# ============================================================

def plot_r_squared_distribution(
    r_squared_values,
    output_path,
    plot_style=None
):
    """
    绘制 R² 分布饼图（纯函数版）
    
    Args:
        r_squared_values: R² 值列表
        output_path: 输出文件路径
        plot_style: 绘图风格字典（可选）
    
    Returns:
        dict: 标准结果字典
    """
    if not r_squared_values:
        return {
            'success': False,
            'filepath': None,
            'error': 'No R-squared values provided'
        }
    
    # 分类统计
    dist = {
        "Excellent (>=0.99)": 0,
        "Good (0.95-0.99)": 0,
        "Acceptable (0.90-0.95)": 0,
        "Poor (<0.90)": 0
    }
    
    for r2 in r_squared_values:
        if r2 >= 0.99:
            dist["Excellent (>=0.99)"] += 1
        elif r2 >= 0.95:
            dist["Good (0.95-0.99)"] += 1
        elif r2 >= 0.90:
            dist["Acceptable (0.90-0.95)"] += 1
        else:
            dist["Poor (<0.90)"] += 1
    
    # 过滤空类别
    labels = [k for k, v in dist.items() if v > 0]
    sizes = [v for v in dist.values() if v > 0]
    
    if not sizes:
        return {
            'success': False,
            'filepath': None,
            'error': 'No valid R-squared distribution'
        }
    
    colors = ['#2ecc71', '#3498db', '#f39c12', '#e74c3c'][:len(labels)]
    
    style = plot_style or {}
    fig_size = style.get('figure_size', (8, 6))
    dpi = style.get('dpi', 150)
    
    try:
        fig, ax = plt.subplots(figsize=fig_size)
        ax.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%', startangle=90)
        ax.set_title('R-squared Distribution', fontsize=14)
        ax.axis('equal')
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        plt.savefig(output_path, dpi=dpi, bbox_inches='tight')
        plt.close(fig)
        
        return {
            'success': True,
            'filepath': output_path,
            'error': None
        }
    
    except Exception as e:
        return {
            'success': False,
            'filepath': output_path,
            'error': f'Failed to plot R-squared distribution: {str(e)}'
        }


def plot_conductivity_trend(
    temperatures_C,
    conductivities_S_cm,
    output_path,
    plot_style=None
):
    """
    绘制电导率-温度趋势图（纯函数版）
    
    Args:
        temperatures_C: 温度列表 (°C)
        conductivities_S_cm: 电导率列表 (S/cm)
        output_path: 输出文件路径
        plot_style: 绘图风格字典（可选）
    
    Returns:
        dict: 标准结果字典
    """
    if len(temperatures_C) != len(conductivities_S_cm):
        return {
            'success': False,
            'filepath': None,
            'error': 'Temperature and conductivity arrays have different lengths'
        }
    
    if len(temperatures_C) == 0:
        return {
            'success': False,
            'filepath': None,
            'error': 'No data points provided'
        }
    
    style = plot_style or {}
    fig_size = style.get('figure_size', (10, 6))
    dpi = style.get('dpi', 150)
    
    try:
        fig, ax = plt.subplots(figsize=fig_size)
        ax.scatter(temperatures_C, conductivities_S_cm, c='#3498db', alpha=0.7, s=50)
        ax.set_xlabel('Temperature (C)', fontsize=12)
        ax.set_ylabel('Conductivity (S/cm)', fontsize=12)
        ax.set_title('Conductivity vs Temperature', fontsize=14)
        ax.set_yscale('log')
        ax.grid(True, alpha=0.3)
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        plt.savefig(output_path, dpi=dpi, bbox_inches='tight')
        plt.close(fig)
        
        return {
            'success': True,
            'filepath': output_path,
            'error': None
        }
    
    except Exception as e:
        return {
            'success': False,
            'filepath': output_path,
            'error': f'Failed to plot conductivity trend: {str(e)}'
        }
