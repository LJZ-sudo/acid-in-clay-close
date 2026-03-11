# -*- coding: utf-8 -*-
"""
Figure 11: ΔEa 分布图（单峰性/偏度分析）

展示 ΔEa 的分布特征：
- Panel (a): 直方图 + KDE 曲线
- Panel (b): 各温区分布对比
- 单峰性检验、偏度、峰度统计

数据来源: close/output/phase3_results/confinement/
"""

import sys
from pathlib import Path

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy import stats
from scipy.signal import find_peaks

# 显式路径配置，便于 standalone 使用
SCRIPT_DIR = Path(__file__).resolve().parent
PAPER_FIG_DIR = SCRIPT_DIR.parent
CLOSE_ROOT = PAPER_FIG_DIR.parent
if str(PAPER_FIG_DIR) not in sys.path:
    sys.path.insert(0, str(PAPER_FIG_DIR))
from am_style_config import (
    setup_am_style, COLORS, save_figure, add_panel_label
)

# 路径配置
PHASE3_DIR = CLOSE_ROOT / 'output' / 'phase3_results'
CONFINEMENT_DIR = PHASE3_DIR / 'confinement'
OUT_DIR = SCRIPT_DIR


def load_delta_ea_data():
    """加载 ΔEa 数据"""
    delta_ea_csv = CONFINEMENT_DIR / 'delta_ea_by_segment.csv'
    if delta_ea_csv.exists():
        return pd.read_csv(delta_ea_csv)
    
    fig9_data = Path(__file__).resolve().parent.parent / 'figure9' / 'figure9_data.csv'
    if fig9_data.exists():
        return pd.read_csv(fig9_data)
    
    raise FileNotFoundError("ΔEa data not found.")


def dip_test(data):
    """
    Hartigan's Dip Test for unimodality
    使用简化版本：检测 KDE 曲线的峰值数量
    """
    from scipy.stats import gaussian_kde
    
    data = np.asarray(data).flatten()
    data = data[~np.isnan(data)]
    
    if len(data) < 10:
        return 1, 1.0  # 数据太少，假设单峰
    
    # KDE 估计
    kde = gaussian_kde(data, bw_method='scott')
    x_eval = np.linspace(data.min(), data.max(), 200)
    y_eval = kde(x_eval)
    
    # 找峰值
    peaks, properties = find_peaks(y_eval, height=max(y_eval) * 0.1,
                                   distance=20)
    
    n_peaks = len(peaks)
    
    return n_peaks, None  # 简化版不返回 p 值


def plot_figure11():
    """绘制 Figure 11: ΔEa 分布"""
    
    print("=" * 60)
    print("Figure 11: ΔEa Distribution Analysis")
    print("=" * 60)
    
    setup_am_style()
    
    # 加载数据
    df = load_delta_ea_data()
    delta_Ea = df['delta_Ea'].values
    T = df['T_avg_K'].values
    
    # 温区数据
    low_T = delta_Ea[T < 230]
    mid_T = delta_Ea[(T >= 230) & (T < 270)]
    high_T = delta_Ea[T >= 270]
    
    # 统计量
    mean = np.mean(delta_Ea)
    std = np.std(delta_Ea)
    median = np.median(delta_Ea)
    skewness = stats.skew(delta_Ea)
    kurtosis = stats.kurtosis(delta_Ea)
    
    # 正态性检验
    shapiro_stat, shapiro_p = stats.shapiro(delta_Ea)
    
    # D'Agostino-Pearson 检验
    dagostino_stat, dagostino_p = stats.normaltest(delta_Ea)
    
    # 单峰性检测
    n_peaks, _ = dip_test(delta_Ea)
    unimodal = n_peaks == 1
    
    print(f"  Mean = {mean:.4f} eV")
    print(f"  Std = {std:.4f} eV")
    print(f"  Skewness = {skewness:.4f}")
    print(f"  Kurtosis = {kurtosis:.4f}")
    print(f"  Shapiro-Wilk p = {shapiro_p:.4f}")
    print(f"  Number of peaks: {n_peaks} ({'unimodal' if unimodal else 'multimodal'})")
    
    # 创建图形 (1x2 布局)
    fig, axes = plt.subplots(1, 2, figsize=(11, 5))
    
    # ==================== Panel (a): 整体分布 ====================
    ax1 = axes[0]
    
    # 直方图
    n_bins = 20
    n, bins, patches = ax1.hist(delta_Ea, bins=n_bins, 
                                 density=True, alpha=0.7,
                                 color=COLORS['S8'], edgecolor='white',
                                 linewidth=1, label='Histogram')
    
    # KDE 曲线
    kde = stats.gaussian_kde(delta_Ea, bw_method='scott')
    x_kde = np.linspace(delta_Ea.min() - 0.1, delta_Ea.max() + 0.1, 200)
    y_kde = kde(x_kde)
    ax1.plot(x_kde, y_kde, '-', color=COLORS['fit_line'], linewidth=2.5,
             label='KDE')
    
    # 正态分布参考
    x_norm = np.linspace(delta_Ea.min() - 0.1, delta_Ea.max() + 0.1, 200)
    y_norm = stats.norm.pdf(x_norm, mean, std)
    ax1.plot(x_norm, y_norm, '--', color=COLORS['reference'], linewidth=2,
             label=f'Normal (μ={mean:.3f}, σ={std:.3f})')
    
    # 均值和中位数线
    ax1.axvline(mean, color=COLORS['segment2'], linestyle='-', linewidth=2,
                label=f'Mean = {mean:.3f}', alpha=0.8)
    ax1.axvline(median, color=COLORS['segment3'], linestyle='-.', linewidth=2,
                label=f'Median = {median:.3f}', alpha=0.8)
    
    # 零线
    ax1.axvline(0, color='black', linestyle=':', linewidth=1.5, alpha=0.5)
    
    ax1.set_xlabel('$\\Delta E_a$ (eV)', fontsize=11)
    ax1.set_ylabel('Probability Density', fontsize=11)
    ax1.set_title('$\\Delta E_a$ Distribution (Overall)', fontsize=12, fontweight='bold')
    ax1.legend(loc='upper right', fontsize=8)
    ax1.grid(True, alpha=0.35, axis='y')
    
    # 统计信息框
    stats_text = (
        f'n = {len(delta_Ea)}\n'
        f'Skewness = {skewness:.3f}\n'
        f'Kurtosis = {kurtosis:.3f}\n'
        f'Shapiro-Wilk p = {shapiro_p:.4f}\n'
        f'Peaks: {n_peaks} ({"unimodal" if unimodal else "multimodal"})'
    )
    ax1.text(0.02, 0.98, stats_text, transform=ax1.transAxes,
             fontsize=9, verticalalignment='top',
             bbox=dict(boxstyle='round,pad=0.4', facecolor='white',
                      edgecolor='#CCCCCC', alpha=0.95),
             family='monospace')
    
    # 偏度解释
    if skewness > 0.5:
        skew_interp = 'Right-skewed\n(long tail at high values)'
    elif skewness < -0.5:
        skew_interp = 'Left-skewed\n(long tail at low values)'
    else:
        skew_interp = 'Approximately\nsymmetric'
    
    ax1.text(0.98, 0.02, skew_interp, transform=ax1.transAxes,
             fontsize=9, verticalalignment='bottom', horizontalalignment='right',
             bbox=dict(boxstyle='round,pad=0.3', facecolor='#FFF9C4',
                      edgecolor='#FBC02D', alpha=0.9))
    
    add_panel_label(ax1, 'a')
    
    # ==================== Panel (b): 各温区分布对比 ====================
    ax2 = axes[1]
    
    # 各温区 KDE
    if len(low_T) > 5:
        kde_low = stats.gaussian_kde(low_T, bw_method='scott')
        x_low = np.linspace(min(delta_Ea) - 0.1, max(delta_Ea) + 0.1, 200)
        ax2.fill_between(x_low, kde_low(x_low), alpha=0.3, color=COLORS['low_temp'])
        ax2.plot(x_low, kde_low(x_low), '-', color=COLORS['low_temp'], linewidth=2,
                 label=f'Low T (<230K, n={len(low_T)})')
    
    if len(mid_T) > 5:
        kde_mid = stats.gaussian_kde(mid_T, bw_method='scott')
        x_mid = np.linspace(min(delta_Ea) - 0.1, max(delta_Ea) + 0.1, 200)
        ax2.fill_between(x_mid, kde_mid(x_mid), alpha=0.3, color=COLORS['mid_temp'])
        ax2.plot(x_mid, kde_mid(x_mid), '-', color=COLORS['mid_temp'], linewidth=2,
                 label=f'Mid T (230-270K, n={len(mid_T)})')
    
    if len(high_T) > 5:
        kde_high = stats.gaussian_kde(high_T, bw_method='scott')
        x_high = np.linspace(min(delta_Ea) - 0.1, max(delta_Ea) + 0.1, 200)
        ax2.fill_between(x_high, kde_high(x_high), alpha=0.3, color=COLORS['high_temp'])
        ax2.plot(x_high, kde_high(x_high), '-', color=COLORS['high_temp'], linewidth=2,
                 label=f'High T (≥270K, n={len(high_T)})')
    
    # 零线
    ax2.axvline(0, color='black', linestyle=':', linewidth=1.5, alpha=0.5,
                label='Zero effect')
    
    ax2.set_xlabel('$\\Delta E_a$ (eV)', fontsize=11)
    ax2.set_ylabel('Probability Density', fontsize=11)
    ax2.set_title('$\\Delta E_a$ Distribution by Temperature', fontsize=12, fontweight='bold')
    ax2.legend(loc='upper right', fontsize=9)
    ax2.grid(True, alpha=0.35, axis='y')
    
    # 温区均值
    temp_means = (
        f'Mean ΔEa:\n'
        f'Low T: {np.mean(low_T):.3f} eV\n'
        f'Mid T: {np.mean(mid_T):.3f} eV\n'
        f'High T: {np.mean(high_T):.3f} eV'
    )
    ax2.text(0.02, 0.98, temp_means, transform=ax2.transAxes,
             fontsize=9, verticalalignment='top',
             bbox=dict(boxstyle='round,pad=0.4', facecolor='white',
                      edgecolor='#CCCCCC', alpha=0.95))
    
    add_panel_label(ax2, 'b')
    
    plt.tight_layout()
    
    # 保存
    save_figure(fig, str(OUT_DIR / 'figure11_delta_ea_distribution'))
    plt.close(fig)
    
    # 保存统计数据
    stats_df = pd.DataFrame({
        'statistic': ['n', 'mean', 'std', 'median', 'skewness', 'kurtosis',
                     'shapiro_W', 'shapiro_p', 'n_peaks', 'is_unimodal'],
        'value': [len(delta_Ea), mean, std, median, skewness, kurtosis,
                 shapiro_stat, shapiro_p, n_peaks, unimodal]
    })
    stats_df.to_csv(OUT_DIR / 'figure11_distribution_stats.csv', index=False, encoding='utf-8-sig')
    
    # 温区统计
    temp_stats = pd.DataFrame({
        'temperature_region': ['Low T', 'Mid T', 'High T'],
        'n': [len(low_T), len(mid_T), len(high_T)],
        'mean': [np.mean(low_T), np.mean(mid_T), np.mean(high_T)],
        'std': [np.std(low_T), np.std(mid_T), np.std(high_T)],
        'skewness': [stats.skew(low_T) if len(low_T) > 2 else np.nan,
                    stats.skew(mid_T) if len(mid_T) > 2 else np.nan,
                    stats.skew(high_T) if len(high_T) > 2 else np.nan]
    })
    temp_stats.to_csv(OUT_DIR / 'figure11_temp_region_stats.csv', index=False, encoding='utf-8-sig')
    
    print(f'\nData saved:')
    print(f'  {OUT_DIR / "figure11_distribution_stats.csv"}')
    print(f'  {OUT_DIR / "figure11_temp_region_stats.csv"}')
    
    print(f'\n[Figure 11 完成]')


if __name__ == '__main__':
    plot_figure11()
