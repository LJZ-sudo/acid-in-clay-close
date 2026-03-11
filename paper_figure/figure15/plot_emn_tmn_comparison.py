# -*- coding: utf-8 -*-
"""
Figure 15: E_MN 与 T_MN 对比（条形图 + 误差棒）

Meyer-Neldel 补偿参数对比：
- E_MN (Meyer-Neldel 能量)
- T_MN (Meyer-Neldel 温度 = E_MN / k_B)
- S8 vs S60 对比
- 不同温区对比

数据来源: close/output/phase3_results/meyer_neldel/
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

# 物理常数
k_B = 8.617333262e-5  # eV/K (玻尔兹曼常数)

# 路径配置
PHASE3_DIR = CLOSE_ROOT / 'output' / 'phase3_results'
MN_DIR = PHASE3_DIR / 'meyer_neldel'
OUT_DIR = SCRIPT_DIR


def load_mn_results():
    """加载 Meyer-Neldel 分析结果"""
    # 首先尝试加载预计算结果
    summary_path = MN_DIR / 'summary.json'
    if summary_path.exists():
        with open(summary_path, 'r') as f:
            return json.load(f)
    
    # 如果没有，从 Figure 13/14 加载
    results = {}
    
    fig13_path = Path(__file__).resolve().parent.parent / 'figure13' / 'figure13_fit_results.json'
    if fig13_path.exists():
        with open(fig13_path, 'r') as f:
            s8_results = json.load(f)
            results['S8'] = s8_results.get('all_data', {})
            if 'high_T' in s8_results:
                results['S8_high_T'] = s8_results['high_T']
            if 'low_T' in s8_results:
                results['S8_low_T'] = s8_results['low_T']
    
    fig14_path = Path(__file__).resolve().parent.parent / 'figure14' / 'figure14_comparison_results.json'
    if fig14_path.exists():
        with open(fig14_path, 'r') as f:
            comparison = json.load(f)
            if 'S60' in comparison:
                results['S60'] = comparison['S60']
    
    return results


def compute_from_data():
    """如果没有预计算结果，从数据重新计算"""
    df = pd.read_csv(PHASE3_DIR / 'integrated_data.csv')
    
    results = {}
    
    # S8
    df_s8 = df[df['material_type'] == 'S8'].dropna(subset=['Ea_eV', 'ln_sigma0'])
    df_s8 = df_s8[df_s8['Ea_eV'] > 0]
    if len(df_s8) >= 5:
        lr = stats.linregress(df_s8['Ea_eV'], df_s8['ln_sigma0'])
        results['S8'] = {
            'E_MN_eV': 1.0 / lr.slope if lr.slope > 0 else None,
            'E_MN_se': lr.stderr / (lr.slope**2) if lr.slope > 0 else None,
            'r_squared': lr.rvalue**2,
            'n': len(df_s8)
        }
        
        # 高温
        high_T = df_s8[df_s8['T_avg_K'] >= 270]
        if len(high_T) >= 5:
            lr_h = stats.linregress(high_T['Ea_eV'], high_T['ln_sigma0'])
            results['S8_high_T'] = {
                'E_MN_eV': 1.0 / lr_h.slope if lr_h.slope > 0 else None,
                'E_MN_se': lr_h.stderr / (lr_h.slope**2) if lr_h.slope > 0 else None,
                'r_squared': lr_h.rvalue**2,
                'n': len(high_T)
            }
        
        # 低温
        low_T = df_s8[df_s8['T_avg_K'] < 230]
        if len(low_T) >= 5:
            lr_l = stats.linregress(low_T['Ea_eV'], low_T['ln_sigma0'])
            results['S8_low_T'] = {
                'E_MN_eV': 1.0 / lr_l.slope if lr_l.slope > 0 else None,
                'E_MN_se': lr_l.stderr / (lr_l.slope**2) if lr_l.slope > 0 else None,
                'r_squared': lr_l.rvalue**2,
                'n': len(low_T)
            }
    
    # S60
    df_s60 = df[df['material_type'] == 'S60'].dropna(subset=['Ea_eV', 'ln_sigma0'])
    df_s60 = df_s60[df_s60['Ea_eV'] > 0]
    if len(df_s60) >= 5:
        lr = stats.linregress(df_s60['Ea_eV'], df_s60['ln_sigma0'])
        results['S60'] = {
            'E_MN_eV': 1.0 / lr.slope if lr.slope > 0 else None,
            'E_MN_se': lr.stderr / (lr.slope**2) if lr.slope > 0 else None,
            'r_squared': lr.rvalue**2,
            'n': len(df_s60)
        }
    
    return results


def plot_figure15():
    """绘制 Figure 15: E_MN 和 T_MN 对比"""
    
    print("=" * 60)
    print("Figure 15: E_MN and T_MN Comparison")
    print("=" * 60)
    
    setup_am_style()
    
    # 加载数据
    results = load_mn_results()
    if not results:
        print("  Computing from raw data...")
        results = compute_from_data()
    
    # 准备绘图数据
    categories = []
    E_MN_values = []
    E_MN_errors = []
    colors = []
    
    # S8 全范围
    if 'S8' in results and results['S8'].get('E_MN_eV'):
        categories.append('S8\n(All)')
        E_MN_values.append(results['S8']['E_MN_eV'])
        E_MN_errors.append(results['S8'].get('E_MN_se', 0) or 0)
        colors.append(COLORS['S8'])
    
    # S8 高温
    if 'S8_high_T' in results and results['S8_high_T'].get('E_MN_eV'):
        categories.append('S8\n(High T)')
        E_MN_values.append(results['S8_high_T']['E_MN_eV'])
        E_MN_errors.append(results['S8_high_T'].get('E_MN_se', 0) or 0)
        colors.append(COLORS['mn_s8_high'])
    
    # S8 低温
    if 'S8_low_T' in results and results['S8_low_T'].get('E_MN_eV'):
        categories.append('S8\n(Low T)')
        E_MN_values.append(results['S8_low_T']['E_MN_eV'])
        E_MN_errors.append(results['S8_low_T'].get('E_MN_se', 0) or 0)
        colors.append(COLORS['mn_s8_low'])
    
    # S60
    if 'S60' in results and results['S60'].get('E_MN_eV'):
        categories.append('S60\n(Bulk)')
        E_MN_values.append(results['S60']['E_MN_eV'])
        E_MN_errors.append(results['S60'].get('E_MN_se', 0) or 0)
        colors.append(COLORS['S60'])
    
    E_MN_values = np.array(E_MN_values)
    E_MN_errors = np.array(E_MN_errors)
    
    # 计算 T_MN = E_MN / k_B
    T_MN_values = E_MN_values / k_B
    T_MN_errors = E_MN_errors / k_B
    
    print(f"  Found {len(categories)} categories")
    for cat, e_mn, t_mn in zip(categories, E_MN_values, T_MN_values):
        print(f"    {cat.replace(chr(10), ' ')}: E_MN={e_mn:.4f} eV, T_MN={t_mn:.0f} K")
    
    # 创建图形 (1x2 布局)
    fig, axes = plt.subplots(1, 2, figsize=(11, 5))
    
    # ==================== Panel (a): E_MN 条形图 ====================
    ax1 = axes[0]
    
    x_pos = np.arange(len(categories))
    bars1 = ax1.bar(x_pos, E_MN_values * 1000,  # 转换为 meV
                    yerr=E_MN_errors * 1000,
                    color=colors, alpha=0.8,
                    edgecolor='white', linewidth=2,
                    capsize=5, error_kw={'linewidth': 2})
    
    # 数值标注
    for i, (bar, val, err) in enumerate(zip(bars1, E_MN_values * 1000, E_MN_errors * 1000)):
        ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + err + 0.5,
                f'{val:.1f}', ha='center', va='bottom', fontsize=10, fontweight='bold')
    
    ax1.set_xticks(x_pos)
    ax1.set_xticklabels(categories, fontsize=10)
    ax1.set_ylabel('$E_{MN}$ (meV)', fontsize=11)
    ax1.set_title('Meyer-Neldel Energy ($E_{MN}$)', fontsize=12, fontweight='bold')
    ax1.grid(True, alpha=0.35, axis='y')
    ax1.set_ylim(0, max(E_MN_values * 1000) * 1.3)
    
    # 参考线
    if len(E_MN_values) > 1:
        mean_E_MN = np.mean(E_MN_values) * 1000
        ax1.axhline(mean_E_MN, color=COLORS['reference'], linestyle='--', 
                   linewidth=1.5, alpha=0.7, label=f'Mean = {mean_E_MN:.1f} meV')
        ax1.legend(loc='upper right', fontsize=9)
    
    add_panel_label(ax1, 'a')
    
    # ==================== Panel (b): T_MN 条形图 ====================
    ax2 = axes[1]
    
    bars2 = ax2.bar(x_pos, T_MN_values,
                    yerr=T_MN_errors,
                    color=colors, alpha=0.8,
                    edgecolor='white', linewidth=2,
                    capsize=5, error_kw={'linewidth': 2})
    
    # 数值标注
    for i, (bar, val, err) in enumerate(zip(bars2, T_MN_values, T_MN_errors)):
        ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + err + 5,
                f'{val:.0f}', ha='center', va='bottom', fontsize=10, fontweight='bold')
    
    ax2.set_xticks(x_pos)
    ax2.set_xticklabels(categories, fontsize=10)
    ax2.set_ylabel('$T_{MN}$ = $E_{MN}$/$k_B$ (K)', fontsize=11)
    ax2.set_title('Meyer-Neldel Temperature ($T_{MN}$)', fontsize=12, fontweight='bold')
    ax2.grid(True, alpha=0.35, axis='y')
    ax2.set_ylim(0, max(T_MN_values) * 1.3)
    
    # 参考温度线
    ax2.axhline(300, color=COLORS['high_temp'], linestyle=':', 
               linewidth=1.5, alpha=0.7, label='Room T (300 K)')
    ax2.axhline(200, color=COLORS['low_temp'], linestyle=':', 
               linewidth=1.5, alpha=0.7, label='Low T (200 K)')
    ax2.legend(loc='upper right', fontsize=9)
    
    # 物理意义解释
    phys_text = (
        r'$T_{MN}$ interpretation:' + '\n'
        r'$T < T_{MN}$: $E_a$ dominates' + '\n'
        r'$T > T_{MN}$: $\sigma_0$ dominates'
    )
    ax2.text(0.02, 0.98, phys_text, transform=ax2.transAxes,
             fontsize=9, verticalalignment='top',
             bbox=dict(boxstyle='round,pad=0.4', facecolor='#E3F2FD',
                      edgecolor='#1976D2', alpha=0.9))
    
    add_panel_label(ax2, 'b')
    
    plt.tight_layout()
    
    # 保存
    save_figure(fig, str(OUT_DIR / 'figure15_emn_tmn_comparison'))
    plt.close(fig)
    
    # 保存数据
    summary_df = pd.DataFrame({
        'category': [c.replace('\n', ' ') for c in categories],
        'E_MN_eV': E_MN_values,
        'E_MN_meV': E_MN_values * 1000,
        'E_MN_se': E_MN_errors,
        'T_MN_K': T_MN_values,
        'T_MN_se': T_MN_errors
    })
    summary_df.to_csv(OUT_DIR / 'figure15_emn_tmn_data.csv', index=False, encoding='utf-8-sig')
    
    print(f'\nData saved:')
    print(f'  {OUT_DIR / "figure15_emn_tmn_data.csv"}')
    
    print(f'\n[Figure 15 完成]')


if __name__ == '__main__':
    plot_figure15()
