# -*- coding: utf-8 -*-
"""
Figure 9: ΔEa vs T 线性拟合 + 95% CI

核心主图：限域强度的温度依赖性
- ΔEa = Ea(S8) - Ea(S60_predicted) vs Temperature
- 线性拟合 + 95% 置信区间/预测区间
- 按温区着色

数据来源: close/output/phase3_results/confinement/
"""

import sys
import io
import json
import pickle
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
    setup_am_style, COLORS, save_figure, add_panel_label,
    format_r2, format_pvalue
)

# 路径配置
PHASE3_DIR = CLOSE_ROOT / 'output' / 'phase3_results'
CONFINEMENT_DIR = PHASE3_DIR / 'confinement'
OUT_DIR = SCRIPT_DIR


def load_delta_ea_data():
    """加载 ΔEa 数据"""
    # 首先检查是否存在预计算的数据
    delta_ea_csv = CONFINEMENT_DIR / 'delta_ea_by_segment.csv'
    if delta_ea_csv.exists():
        df = pd.read_csv(delta_ea_csv)
        return df
    
    # 如果没有，从原始数据计算
    df_all = pd.read_csv(PHASE3_DIR / 'integrated_data.csv')
    df_s8 = df_all[df_all['material_type'] == 'S8'].dropna(subset=['R', 'N', 'T_avg_K', 'Ea_eV']).copy()
    df_s8['N'] = df_s8['N'].fillna(df_s8['N'].mean())
    
    # 加载 S60 模型进行预测
    with open(PHASE3_DIR / 'models' / 's60_baseline.pkl', 'rb') as f:
        model_data = pickle.load(f)
    pipeline = model_data['pipeline']
    
    ea_bulk = np.array([pipeline.predict(np.array([[r, t]]))[0] 
                        for r, t in zip(df_s8['R'], df_s8['T_avg_K'])])
    df_s8['Ea_bulk'] = ea_bulk
    df_s8['delta_Ea'] = df_s8['Ea_eV'] - df_s8['Ea_bulk']
    
    return df_s8


def compute_ci_band(x, y, x_pred, ci_level=0.95):
    """计算线性回归的置信区间带"""
    n = len(x)
    slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)
    
    y_pred = slope * x_pred + intercept
    y_fitted = slope * x + intercept
    
    # 残差标准误
    residuals = y - y_fitted
    s_err = np.sqrt(np.sum(residuals**2) / (n - 2))
    
    # t 值
    t_val = stats.t.ppf((1 + ci_level) / 2, n - 2)
    
    # 置信区间
    x_mean = np.mean(x)
    ss_x = np.sum((x - x_mean)**2)
    
    ci_band = t_val * s_err * np.sqrt(1/n + (x_pred - x_mean)**2 / ss_x)
    pi_band = t_val * s_err * np.sqrt(1 + 1/n + (x_pred - x_mean)**2 / ss_x)
    
    return y_pred, ci_band, pi_band, slope, intercept, r_value**2, p_value, std_err


def plot_figure9():
    """绘制 Figure 9: ΔEa vs T"""
    
    print("=" * 60)
    print("Figure 9: ΔEa vs Temperature with 95% CI")
    print("=" * 60)
    
    setup_am_style()
    
    # 加载数据
    df = load_delta_ea_data()
    
    T = df['T_avg_K'].values
    delta_Ea = df['delta_Ea'].values
    
    # 加载统计摘要
    with open(CONFINEMENT_DIR / 'summary.json', 'r') as f:
        summary = json.load(f)
    fit_info = summary.get('delta_Ea_vs_T_linear_fit', {})
    
    # 计算线性拟合和置信区间
    T_pred = np.linspace(T.min() - 5, T.max() + 5, 200)
    y_pred, ci_band, pi_band, slope, intercept, r2, p_value, std_err = compute_ci_band(T, delta_Ea, T_pred)
    
    # 创建图形
    fig, ax = plt.subplots(figsize=(8, 5.5))
    
    # 温区划分
    low_T_mask = T < 230
    mid_T_mask = (T >= 230) & (T < 270)
    high_T_mask = T >= 270
    
    # 散点图（按温区着色）
    ax.scatter(T[high_T_mask], delta_Ea[high_T_mask], 
               c=COLORS['high_temp'], alpha=0.7, s=60, 
               edgecolors='white', linewidths=0.8,
               label=f'High T (≥270K, n={high_T_mask.sum()})')
    ax.scatter(T[mid_T_mask], delta_Ea[mid_T_mask], 
               c=COLORS['mid_temp'], alpha=0.7, s=60, 
               edgecolors='white', linewidths=0.8,
               label=f'Mid T (230-270K, n={mid_T_mask.sum()})')
    ax.scatter(T[low_T_mask], delta_Ea[low_T_mask], 
               c=COLORS['low_temp'], alpha=0.7, s=60, 
               edgecolors='white', linewidths=0.8,
               label=f'Low T (<230K, n={low_T_mask.sum()})')
    
    # 95% 置信区间带
    ax.fill_between(T_pred, y_pred - ci_band, y_pred + ci_band,
                    color=COLORS['ci_fill'], alpha=0.5, label='95% CI')
    
    # 线性拟合线
    ax.plot(T_pred, y_pred, '-', color=COLORS['fit_line'], linewidth=2.5,
            label=f'Linear fit')
    
    # 零线
    ax.axhline(0, color=COLORS['reference'], linestyle='--', linewidth=1.5, alpha=0.7)
    
    # 温区分隔线
    ax.axvline(230, color=COLORS['grid'], linestyle=':', linewidth=1, alpha=0.5)
    ax.axvline(270, color=COLORS['grid'], linestyle=':', linewidth=1, alpha=0.5)
    
    # 标签和标题
    ax.set_xlabel('Temperature (K)', fontsize=12)
    ax.set_ylabel('$\\Delta E_a$ = $E_a$(S8) − $E_a$(S60 pred) (eV)', fontsize=12)
    ax.set_title('Confinement Effect: $\\Delta E_a$ vs Temperature', fontsize=13, fontweight='bold')
    
    # 图例
    ax.legend(loc='upper right', fontsize=9, framealpha=0.9)
    
    # 统计信息框
    slope_ci = fit_info.get('slope_ci_95', [None, None])
    stats_text = (
        f'Linear Fit: $\\Delta E_a$ = {slope:.5f}·T + {intercept:.3f}\n'
        f'Slope = {slope:.5f} eV/K\n'
        f'Slope 95% CI: [{slope_ci[0]:.5f}, {slope_ci[1]:.5f}]\n'
        f'R² = {r2:.3f}\n'
        f'n = {len(T)}'
    )
    ax.text(0.05, 0.05, stats_text, transform=ax.transAxes,
            fontsize=9, verticalalignment='bottom',
            bbox=dict(boxstyle='round,pad=0.5', facecolor='white',
                     edgecolor='#CCCCCC', alpha=0.95),
            family='monospace')
    
    # 物理解释注释
    if slope < 0:
        interp_text = (
            'Negative slope indicates:\n'
            'Confinement effect ↓ as T ↑\n'
            '(Stronger effect at low T)'
        )
    else:
        interp_text = (
            'Positive slope indicates:\n'
            'Confinement effect ↑ as T ↑'
        )
    ax.text(0.98, 0.98, interp_text, transform=ax.transAxes,
            fontsize=9, verticalalignment='top', horizontalalignment='right',
            bbox=dict(boxstyle='round,pad=0.4', facecolor='#FFF9C4',
                     edgecolor='#FBC02D', alpha=0.9))
    
    ax.grid(True, alpha=0.35)
    
    plt.tight_layout()
    
    # 保存
    save_figure(fig, str(OUT_DIR / 'figure9_delta_ea_vs_T'))
    plt.close(fig)
    
    # 保存数据
    df_out = df[['sample_id', 'T_avg_K', 'Ea_eV', 'Ea_bulk', 'delta_Ea']].copy()
    df_out['temp_region'] = 'Mid'
    df_out.loc[df_out['T_avg_K'] < 230, 'temp_region'] = 'Low'
    df_out.loc[df_out['T_avg_K'] >= 270, 'temp_region'] = 'High'
    df_out.to_csv(OUT_DIR / 'figure9_data.csv', index=False, encoding='utf-8-sig')
    
    fit_df = pd.DataFrame({
        'T_K': T_pred,
        'delta_Ea_pred': y_pred,
        'ci_lower': y_pred - ci_band,
        'ci_upper': y_pred + ci_band
    })
    fit_df.to_csv(OUT_DIR / 'figure9_fit_line.csv', index=False, encoding='utf-8-sig')
    
    print(f'\nFit Statistics:')
    print(f'  Slope = {slope:.6f} eV/K')
    print(f'  Slope 95% CI: [{slope_ci[0]:.6f}, {slope_ci[1]:.6f}]')
    print(f'  Intercept = {intercept:.4f} eV')
    print(f'  R² = {r2:.4f}')
    print(f'  n = {len(T)}')
    
    print(f'\nData saved:')
    print(f'  {OUT_DIR / "figure9_data.csv"}')
    print(f'  {OUT_DIR / "figure9_fit_line.csv"}')
    
    print(f'\n[Figure 9 完成]')


if __name__ == '__main__':
    plot_figure9()
