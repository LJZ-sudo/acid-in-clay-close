# -*- coding: utf-8 -*-
"""
Figure 13: S8 Meyer-Neldel 补偿效应图

ln(σ₀) vs Ea 散点图，展示 Meyer-Neldel 补偿规律：
- 全温度范围线性拟合
- 分温区（高温/中温/低温）对比
- E_MN (Meyer-Neldel 能量) 计算
- 分机制段显示

数据来源: close/output/phase3_results/
"""

import sys
import io
import json
from pathlib import Path

# 修复 Windows 控制台编码
if sys.platform == 'win32':
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass

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
    df_s8 = df[df['material_type'] == 'S8'].dropna(subset=['Ea_eV', 'ln_sigma0']).copy()
    df_s8 = df_s8[df_s8['Ea_eV'] > 0]  # 排除无效 Ea
    
    # 加载已有的 Meyer-Neldel 分析结果
    mn_summary_path = PHASE3_DIR / 'meyer_neldel' / 'summary.json'
    if mn_summary_path.exists():
        with open(mn_summary_path, 'r') as f:
            mn_summary = json.load(f)
    else:
        mn_summary = {}
    
    return df_s8, mn_summary


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
    
    return slope, intercept, r2, E_MN, E_MN_se


def plot_figure13():
    """绘制 Figure 13: S8 Meyer-Neldel"""
    
    print("=" * 60)
    print("Figure 13: S8 Meyer-Neldel Compensation Effect")
    print("=" * 60)
    
    setup_am_style()
    
    # 加载数据
    df_s8, mn_summary = load_data()
    
    Ea = df_s8['Ea_eV'].values
    ln_sigma0 = df_s8['ln_sigma0'].values
    T = df_s8['T_avg_K'].values
    
    # 温区划分
    low_T_mask = T < 230
    mid_T_mask = (T >= 230) & (T < 270)
    high_T_mask = T >= 270
    
    # 全范围拟合
    slope_all, intercept_all, r2_all, E_MN_all, E_MN_se_all = fit_meyer_neldel(Ea, ln_sigma0)
    
    print(f"  All data: n={len(Ea)}, E_MN={E_MN_all:.4f} eV, R²={r2_all:.4f}")
    
    # 分温区拟合
    results = {}
    if high_T_mask.sum() >= 5:
        s, i, r2, e_mn, e_se = fit_meyer_neldel(Ea[high_T_mask], ln_sigma0[high_T_mask])
        results['high_T'] = {'slope': s, 'intercept': i, 'r2': r2, 'E_MN': e_mn, 'n': high_T_mask.sum()}
        print(f"  High T (≥270K): n={high_T_mask.sum()}, E_MN={e_mn:.4f} eV, R²={r2:.4f}")
    
    if low_T_mask.sum() >= 5:
        s, i, r2, e_mn, e_se = fit_meyer_neldel(Ea[low_T_mask], ln_sigma0[low_T_mask])
        results['low_T'] = {'slope': s, 'intercept': i, 'r2': r2, 'E_MN': e_mn, 'n': low_T_mask.sum()}
        print(f"  Low T (<230K): n={low_T_mask.sum()}, E_MN={e_mn:.4f} eV, R²={r2:.4f}")
    
    # 创建图形 (1x2 布局)
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    
    # ==================== Panel (a): 全范围 + 温区着色 ====================
    ax1 = axes[0]
    
    # 按温区着色的散点
    ax1.scatter(Ea[high_T_mask], ln_sigma0[high_T_mask],
               c=COLORS['high_temp'], alpha=0.7, s=60,
               edgecolors='white', linewidths=0.8,
               label=f'High T (≥270K, n={high_T_mask.sum()})')
    
    ax1.scatter(Ea[mid_T_mask], ln_sigma0[mid_T_mask],
               c=COLORS['mid_temp'], alpha=0.7, s=60,
               edgecolors='white', linewidths=0.8,
               label=f'Mid T (230-270K, n={mid_T_mask.sum()})')
    
    ax1.scatter(Ea[low_T_mask], ln_sigma0[low_T_mask],
               c=COLORS['low_temp'], alpha=0.7, s=60,
               edgecolors='white', linewidths=0.8,
               label=f'Low T (<230K, n={low_T_mask.sum()})')
    
    # 全范围拟合线
    Ea_line = np.linspace(Ea.min(), Ea.max(), 100)
    ln_sigma0_line = slope_all * Ea_line + intercept_all
    ax1.plot(Ea_line, ln_sigma0_line, '-', color=COLORS['fit_line'], linewidth=2.5,
             label=f'All data fit (R²={r2_all:.3f})')
    
    ax1.set_xlabel('$E_a$ (eV)', fontsize=11)
    ax1.set_ylabel('ln($\\sigma_0$) (S/cm)', fontsize=11)
    ax1.set_title('S8: Meyer-Neldel Compensation', fontsize=12, fontweight='bold')
    ax1.legend(loc='lower right', fontsize=9)
    ax1.grid(True, alpha=0.35)
    
    # 统计信息框
    stats_text = (
        f'Meyer-Neldel Rule:\n'
        f'ln(σ₀) = ln(σ₀₀) + Ea/E_MN\n'
        f'─────────────────\n'
        f'Slope = {slope_all:.2f}\n'
        f'E_MN = {E_MN_all:.4f} eV\n'
        f'     = {E_MN_all * 1000:.1f} meV\n'
        f'R² = {r2_all:.4f}\n'
        f'n = {len(Ea)}'
    )
    ax1.text(0.05, 0.95, stats_text, transform=ax1.transAxes,
             fontsize=9, verticalalignment='top',
             bbox=dict(boxstyle='round,pad=0.5', facecolor='white',
                      edgecolor='#CCCCCC', alpha=0.95),
             family='monospace')
    
    add_panel_label(ax1, 'a')
    
    # ==================== Panel (b): 分温区拟合对比 ====================
    ax2 = axes[1]
    
    # 散点
    ax2.scatter(Ea[high_T_mask], ln_sigma0[high_T_mask],
               c=COLORS['high_temp'], alpha=0.5, s=40,
               edgecolors='white', linewidths=0.5)
    ax2.scatter(Ea[low_T_mask], ln_sigma0[low_T_mask],
               c=COLORS['low_temp'], alpha=0.5, s=40,
               edgecolors='white', linewidths=0.5)
    
    # 分温区拟合线
    if 'high_T' in results:
        r = results['high_T']
        x_high = Ea[high_T_mask]
        Ea_h = np.linspace(x_high.min(), x_high.max(), 50)
        ax2.plot(Ea_h, r['slope'] * Ea_h + r['intercept'], '-',
                color=COLORS['high_temp'], linewidth=2.5,
                label=f'High T (E_MN={r["E_MN"]:.3f} eV, R²={r["r2"]:.3f})')
    
    if 'low_T' in results:
        r = results['low_T']
        x_low = Ea[low_T_mask]
        Ea_l = np.linspace(x_low.min(), x_low.max(), 50)
        ax2.plot(Ea_l, r['slope'] * Ea_l + r['intercept'], '-',
                color=COLORS['low_temp'], linewidth=2.5,
                label=f'Low T (E_MN={r["E_MN"]:.3f} eV, R²={r["r2"]:.3f})')
    
    ax2.set_xlabel('$E_a$ (eV)', fontsize=11)
    ax2.set_ylabel('ln($\\sigma_0$) (S/cm)', fontsize=11)
    ax2.set_title('S8: Temperature-Dependent MN Effect', fontsize=12, fontweight='bold')
    ax2.legend(loc='lower right', fontsize=9)
    ax2.grid(True, alpha=0.35)
    
    # 物理解释
    if 'high_T' in results and 'low_T' in results:
        e_mn_high = results['high_T']['E_MN']
        e_mn_low = results['low_T']['E_MN']
        
        if e_mn_high > e_mn_low:
            interp = 'E_MN(High T) > E_MN(Low T)\nDifferent transport mechanisms'
        else:
            interp = 'E_MN(Low T) > E_MN(High T)\nStronger compensation at low T'
        
        ax2.text(0.05, 0.05, interp, transform=ax2.transAxes,
                fontsize=9, verticalalignment='bottom',
                bbox=dict(boxstyle='round,pad=0.4', facecolor='#FFF9C4',
                         edgecolor='#FBC02D', alpha=0.9))
    
    add_panel_label(ax2, 'b')
    
    plt.tight_layout()
    
    # 保存
    save_figure(fig, str(OUT_DIR / 'figure13_meyer_neldel_s8'))
    plt.close(fig)
    
    # 保存数据
    df_out = df_s8[['sample_id', 'Ea_eV', 'ln_sigma0', 'T_avg_K', 'segment']].copy()
    df_out['temp_region'] = 'Mid'
    df_out.loc[df_out['T_avg_K'] < 230, 'temp_region'] = 'Low'
    df_out.loc[df_out['T_avg_K'] >= 270, 'temp_region'] = 'High'
    df_out.to_csv(OUT_DIR / 'figure13_s8_mn_data.csv', index=False, encoding='utf-8-sig')
    
    # 拟合结果
    fit_results = {
        'all_data': {
            'slope': float(slope_all),
            'intercept': float(intercept_all),
            'r_squared': float(r2_all),
            'E_MN_eV': float(E_MN_all),
            'E_MN_meV': float(E_MN_all * 1000),
            'n': int(len(Ea))
        }
    }
    for key, val in results.items():
        fit_results[key] = {k: (float(v) if isinstance(v, (np.floating, float)) else (int(v) if isinstance(v, (np.integer, int)) else v))
                           for k, v in val.items()}
    
    with open(OUT_DIR / 'figure13_fit_results.json', 'w') as f:
        json.dump(fit_results, f, indent=2)
    
    print(f'\nData saved:')
    print(f'  {OUT_DIR / "figure13_s8_mn_data.csv"}')
    print(f'  {OUT_DIR / "figure13_fit_results.json"}')
    
    print(f'\n[Figure 13 完成]')


if __name__ == '__main__':
    plot_figure13()
