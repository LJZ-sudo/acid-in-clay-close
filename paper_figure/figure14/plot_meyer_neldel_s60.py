# -*- coding: utf-8 -*-
"""
Figure 14: S60 Meyer-Neldel 补偿效应图

与 Figure 13 对比：
- S60 (bulk/baseline) 的 ln(σ₀) vs Ea 关系
- 与 S8 (confined) 对比显示
- E_MN 差异分析

数据来源: close/output/phase3_results/
"""

import sys
import json
from pathlib import Path

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy import stats

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
OUT_DIR = SCRIPT_DIR


def load_data():
    """加载数据"""
    df = pd.read_csv(PHASE3_DIR / 'integrated_data.csv')
    
    df_s60 = df[df['material_type'] == 'S60'].dropna(subset=['Ea_eV', 'ln_sigma0']).copy()
    df_s60 = df_s60[df_s60['Ea_eV'] > 0]
    
    df_s8 = df[df['material_type'] == 'S8'].dropna(subset=['Ea_eV', 'ln_sigma0']).copy()
    df_s8 = df_s8[df_s8['Ea_eV'] > 0]
    
    return df_s60, df_s8


def fit_meyer_neldel(Ea, ln_sigma0):
    """Meyer-Neldel 拟合"""
    lr = stats.linregress(Ea, ln_sigma0)
    slope = lr.slope
    intercept = lr.intercept
    r2 = lr.rvalue ** 2
    stderr = lr.stderr
    
    if slope > 0:
        E_MN = 1.0 / slope
        E_MN_se = stderr / (slope ** 2) if stderr else None
    else:
        E_MN = np.nan
        E_MN_se = None
    
    return slope, intercept, r2, E_MN, E_MN_se, stderr


def plot_figure14():
    """绘制 Figure 14: S60 Meyer-Neldel + S8 对比"""
    
    print("=" * 60)
    print("Figure 14: S60 vs S8 Meyer-Neldel Comparison")
    print("=" * 60)
    
    setup_am_style()
    
    # 加载数据
    df_s60, df_s8 = load_data()
    
    Ea_s60 = df_s60['Ea_eV'].values
    ln_sigma0_s60 = df_s60['ln_sigma0'].values
    
    Ea_s8 = df_s8['Ea_eV'].values
    ln_sigma0_s8 = df_s8['ln_sigma0'].values
    
    # S60 拟合
    slope_s60, intercept_s60, r2_s60, E_MN_s60, E_MN_se_s60, se_s60 = fit_meyer_neldel(Ea_s60, ln_sigma0_s60)
    print(f"  S60: n={len(Ea_s60)}, E_MN={E_MN_s60:.4f} eV, R²={r2_s60:.4f}")
    
    # S8 拟合
    slope_s8, intercept_s8, r2_s8, E_MN_s8, E_MN_se_s8, se_s8 = fit_meyer_neldel(Ea_s8, ln_sigma0_s8)
    print(f"  S8: n={len(Ea_s8)}, E_MN={E_MN_s8:.4f} eV, R²={r2_s8:.4f}")
    
    # 创建图形 (1x2 布局)
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    
    # ==================== Panel (a): S60 单独 ====================
    ax1 = axes[0]
    
    # S60 散点
    ax1.scatter(Ea_s60, ln_sigma0_s60,
               c=COLORS['S60'], alpha=0.7, s=60,
               edgecolors='white', linewidths=0.8,
               label=f'S60 (n={len(Ea_s60)})')
    
    # S60 拟合线
    Ea_line = np.linspace(Ea_s60.min(), Ea_s60.max(), 100)
    ln_sigma0_line = slope_s60 * Ea_line + intercept_s60
    ax1.plot(Ea_line, ln_sigma0_line, '-', color=COLORS['S60'], linewidth=2.5,
             alpha=0.8, label=f'Linear fit (R²={r2_s60:.3f})')
    
    ax1.set_xlabel('$E_a$ (eV)', fontsize=11)
    ax1.set_ylabel('ln($\\sigma_0$) (S/cm)', fontsize=11)
    ax1.set_title('S60 (Baseline): Meyer-Neldel', fontsize=12, fontweight='bold')
    ax1.legend(loc='lower right', fontsize=9)
    ax1.grid(True, alpha=0.35)
    
    # 统计信息
    stats_text = (
        f'S60 (Bulk reference)\n'
        f'─────────────────\n'
        f'Slope = {slope_s60:.2f}\n'
        f'E_MN = {E_MN_s60:.4f} eV\n'
        f'     = {E_MN_s60 * 1000:.1f} meV\n'
        f'R² = {r2_s60:.4f}'
    )
    ax1.text(0.05, 0.95, stats_text, transform=ax1.transAxes,
             fontsize=9, verticalalignment='top',
             bbox=dict(boxstyle='round,pad=0.5', facecolor='white',
                      edgecolor='#CCCCCC', alpha=0.95),
             family='monospace')
    
    add_panel_label(ax1, 'a')
    
    # ==================== Panel (b): S8 vs S60 对比 ====================
    ax2 = axes[1]
    
    # S60 散点（淡色）
    ax2.scatter(Ea_s60, ln_sigma0_s60,
               c=COLORS['S60'], alpha=0.4, s=40,
               edgecolors='white', linewidths=0.5,
               label=f'S60 (n={len(Ea_s60)})')
    
    # S8 散点
    ax2.scatter(Ea_s8, ln_sigma0_s8,
               c=COLORS['S8'], alpha=0.4, s=40,
               edgecolors='white', linewidths=0.5,
               label=f'S8 (n={len(Ea_s8)})')
    
    # 拟合线
    # S60
    Ea_range = np.linspace(min(Ea_s60.min(), Ea_s8.min()),
                           max(Ea_s60.max(), Ea_s8.max()), 100)
    ax2.plot(Ea_range, slope_s60 * Ea_range + intercept_s60, '-',
             color=COLORS['S60'], linewidth=2.5,
             label=f'S60: E_MN={E_MN_s60:.3f} eV')
    
    # S8
    ax2.plot(Ea_range, slope_s8 * Ea_range + intercept_s8, '-',
             color=COLORS['S8'], linewidth=2.5,
             label=f'S8: E_MN={E_MN_s8:.3f} eV')
    
    ax2.set_xlabel('$E_a$ (eV)', fontsize=11)
    ax2.set_ylabel('ln($\\sigma_0$) (S/cm)', fontsize=11)
    ax2.set_title('S8 vs S60: Meyer-Neldel Comparison', fontsize=12, fontweight='bold')
    ax2.legend(loc='lower right', fontsize=9)
    ax2.grid(True, alpha=0.35)
    
    # 对比信息
    delta_E_MN = E_MN_s8 - E_MN_s60
    delta_slope = slope_s8 - slope_s60
    
    comparison_text = (
        f'Comparison:\n'
        f'─────────────────\n'
        f'ΔE_MN = {delta_E_MN:.4f} eV\n'
        f'       ({delta_E_MN/E_MN_s60*100:+.1f}%)\n'
        f'Δslope = {delta_slope:.2f}'
    )
    ax2.text(0.05, 0.95, comparison_text, transform=ax2.transAxes,
             fontsize=9, verticalalignment='top',
             bbox=dict(boxstyle='round,pad=0.5', facecolor='white',
                      edgecolor='#CCCCCC', alpha=0.95),
             family='monospace')
    
    # 物理解释
    if abs(delta_E_MN) < 0.005:
        interp = 'Similar E_MN:\nSame compensation mechanism'
    elif delta_E_MN > 0:
        interp = 'E_MN(S8) > E_MN(S60):\nWeaker compensation in confinement'
    else:
        interp = 'E_MN(S8) < E_MN(S60):\nStronger compensation in confinement'
    
    ax2.text(0.98, 0.05, interp, transform=ax2.transAxes,
             fontsize=9, verticalalignment='bottom', horizontalalignment='right',
             bbox=dict(boxstyle='round,pad=0.4', facecolor='#FFF9C4',
                      edgecolor='#FBC02D', alpha=0.9))
    
    add_panel_label(ax2, 'b')
    
    plt.tight_layout()
    
    # 保存
    save_figure(fig, str(OUT_DIR / 'figure14_meyer_neldel_s60'))
    plt.close(fig)
    
    # 保存数据
    df_s60_out = df_s60[['sample_id', 'Ea_eV', 'ln_sigma0', 'T_avg_K']].copy()
    df_s60_out['material'] = 'S60'
    df_s60_out.to_csv(OUT_DIR / 'figure14_s60_mn_data.csv', index=False, encoding='utf-8-sig')
    
    # 对比结果
    comparison_results = {
        'S60': {
            'n': len(Ea_s60),
            'slope': float(slope_s60),
            'intercept': float(intercept_s60),
            'r_squared': float(r2_s60),
            'E_MN_eV': float(E_MN_s60),
            'E_MN_meV': float(E_MN_s60 * 1000)
        },
        'S8': {
            'n': len(Ea_s8),
            'slope': float(slope_s8),
            'intercept': float(intercept_s8),
            'r_squared': float(r2_s8),
            'E_MN_eV': float(E_MN_s8),
            'E_MN_meV': float(E_MN_s8 * 1000)
        },
        'comparison': {
            'delta_E_MN_eV': float(delta_E_MN),
            'delta_E_MN_percent': float(delta_E_MN / E_MN_s60 * 100),
            'delta_slope': float(delta_slope)
        }
    }
    
    with open(OUT_DIR / 'figure14_comparison_results.json', 'w') as f:
        json.dump(comparison_results, f, indent=2)
    
    print(f'\nComparison:')
    print(f'  ΔE_MN = {delta_E_MN:.4f} eV ({delta_E_MN/E_MN_s60*100:+.1f}%)')
    print(f'  Δslope = {delta_slope:.2f}')
    
    print(f'\nData saved:')
    print(f'  {OUT_DIR / "figure14_s60_mn_data.csv"}')
    print(f'  {OUT_DIR / "figure14_comparison_results.json"}')
    
    print(f'\n[Figure 14 完成]')


if __name__ == '__main__':
    plot_figure14()
