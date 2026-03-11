# -*- coding: utf-8 -*-
"""
Figure 6: S8 Confined Model Performance (Ea_pred vs Ea_obs)

展示 S8 限域效应模型的预测性能：
- Figure 6a: Ea 预测值 vs 观测值散点图（按温度着色）
- Figure 6b: 残差 vs 温度散点图

数据来源: close/output/phase3_results/
"""

import sys
import io
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
from matplotlib.colors import Normalize
from scipy import stats

# 显式路径配置，便于 standalone 使用
SCRIPT_DIR = Path(__file__).resolve().parent
PAPER_FIG_DIR = SCRIPT_DIR.parent
CLOSE_ROOT = PAPER_FIG_DIR.parent
if str(PAPER_FIG_DIR) not in sys.path:
    sys.path.insert(0, str(PAPER_FIG_DIR))
from am_style_config import (
    setup_am_style, COLORS, save_figure, get_temperature_cmap
)

# 路径配置
PHASE3_DIR = CLOSE_ROOT / 'output' / 'phase3_results'
OUT_DIR = SCRIPT_DIR


def load_data_and_model():
    """加载数据和模型"""
    # 加载数据
    df = pd.read_csv(PHASE3_DIR / 'integrated_data.csv')
    df_s8 = df[df['material_type'] == 'S8'].dropna(subset=['R', 'N', 'T_avg_K', 'Ea_eV']).copy()
    df_s8['N'] = df_s8['N'].fillna(df_s8['N'].mean())
    
    # 加载模型
    with open(PHASE3_DIR / 'models' / 's8_confinement.pkl', 'rb') as f:
        model_data = pickle.load(f)
    model = model_data['model']
    feature_names = model_data['feature_names']
    
    # 加载指标
    import json
    with open(PHASE3_DIR / 'models' / 'metrics.json', 'r') as f:
        metrics = json.load(f)
    
    return df_s8, model, feature_names, metrics['s8']


def plot_figure6a(df_s8, y_obs, y_pred, temperatures, metrics):
    """绘制 Figure 6a: Pred vs Obs（按温度着色）"""
    
    print("Generating Figure 6a: Pred vs Obs...")
    setup_am_style()
    
    # 创建单独的图形
    fig, ax = plt.subplots(figsize=(6, 5))
    
    # 温度颜色映射
    temp_cmap = get_temperature_cmap()
    norm = Normalize(vmin=temperatures.min(), vmax=temperatures.max())
    
    # 散点图
    scatter = ax.scatter(y_obs, y_pred, 
                         c=temperatures, cmap=temp_cmap, norm=norm,
                         alpha=0.8, s=50, 
                         edgecolors='white', linewidths=0.8)
    
    # 颜色条
    cbar = fig.colorbar(scatter, ax=ax, shrink=0.8, pad=0.02)
    cbar.set_label('Temperature (K)', fontsize=11)
    
    # 45度参考线
    lims = [min(y_obs.min(), y_pred.min()) - 0.05, 
            max(y_obs.max(), y_pred.max()) + 0.05]
    ax.plot(lims, lims, '-', color=COLORS['fit_line'], linewidth=2,
            label='Perfect prediction (y=x)', zorder=1)
    
    ax.set_xlim(lims)
    ax.set_ylim(lims)
    ax.set_xlabel('$E_a$ observed (eV)', fontsize=12)
    ax.set_ylabel('$E_a$ predicted (eV)', fontsize=12)
    ax.set_title('S8 Confined Model: $E_a$ Prediction', fontsize=13, fontweight='bold')
    ax.legend(loc='lower right', fontsize=10)
    ax.grid(True, alpha=0.35)
    ax.set_aspect('equal', adjustable='box')
    
    # 统计信息框
    stats_text = (
        f'n = {len(y_obs)}\n'
        f'R² = {metrics["r2"]:.3f}\n'
        f'CV R² = {metrics["cv_r2_mean"]:.3f}'
    )
    ax.text(0.05, 0.95, stats_text, transform=ax.transAxes,
            fontsize=10, verticalalignment='top',
            bbox=dict(boxstyle='round,pad=0.4', facecolor='white', 
                     edgecolor='#CCCCCC', alpha=0.9))
    
    plt.tight_layout()
    
    # 保存
    save_figure(fig, str(OUT_DIR / 'figure6a_pred_vs_obs'))
    plt.close(fig)


def plot_figure6b(temperatures, residuals):
    """绘制 Figure 6b: Residual vs Temperature"""
    
    print("Generating Figure 6b: Residual vs Temperature...")
    setup_am_style()
    
    # 创建单独的图形
    fig, ax = plt.subplots(figsize=(6, 4.5))
    
    # 残差 vs 温度散点图
    ax.scatter(temperatures, residuals,
               c=COLORS['S8'], alpha=0.7, s=50,
               edgecolors='white', linewidths=0.8)
    
    # 零线
    ax.axhline(0, color=COLORS['reference'], linestyle='--', linewidth=1.5)
    
    # 温区分隔线
    ax.axvline(230, color=COLORS['grid'], linestyle=':', linewidth=1, alpha=0.7)
    ax.axvline(270, color=COLORS['grid'], linestyle=':', linewidth=1, alpha=0.7)
    
    # 标注温区
    y_max = max(abs(residuals.min()), abs(residuals.max()))
    ax.text(200, y_max * 0.85, 'Low T', fontsize=10, ha='center', color=COLORS['low_temp'])
    ax.text(250, y_max * 0.85, 'Mid T', fontsize=10, ha='center', color=COLORS['mid_temp'])
    ax.text(290, y_max * 0.85, 'High T', fontsize=10, ha='center', color=COLORS['high_temp'])
    
    # LOWESS 平滑趋势线 (如果可用)
    try:
        from statsmodels.nonparametric.smoothers_lowess import lowess
        smoothed = lowess(residuals, temperatures, frac=0.3)
        ax.plot(smoothed[:, 0], smoothed[:, 1], '-', color=COLORS['fit_line'],
                linewidth=2, label='LOWESS trend')
        ax.legend(loc='upper right', fontsize=10)
    except ImportError:
        pass
    
    ax.set_xlabel('Temperature (K)', fontsize=12)
    ax.set_ylabel('Residual (eV)', fontsize=12)
    ax.set_title('Residual vs Temperature', fontsize=13, fontweight='bold')
    ax.grid(True, alpha=0.35)
    
    # 残差统计
    residual_stats = (
        f'Mean = {residuals.mean():.4f} eV\n'
        f'Std = {residuals.std():.4f} eV'
    )
    ax.text(0.05, 0.05, residual_stats, transform=ax.transAxes,
            fontsize=10, verticalalignment='bottom',
            bbox=dict(boxstyle='round,pad=0.4', facecolor='white',
                     edgecolor='#CCCCCC', alpha=0.9))
    
    plt.tight_layout()
    
    # 保存
    save_figure(fig, str(OUT_DIR / 'figure6b_residual_vs_temp'))
    plt.close(fig)


def plot_figure6():
    """绘制 Figure 6: S8 Confined Model Performance"""
    
    print("=" * 60)
    print("Figure 6: S8 Confined Model Performance")
    print("=" * 60)
    
    # 加载数据
    df_s8, model, feature_names, metrics = load_data_and_model()
    
    # 构建特征
    df_s8 = df_s8.copy()
    df_s8['T_N'] = df_s8['T_avg_K'] * df_s8['N']
    df_s8['T_R'] = df_s8['T_avg_K'] * df_s8['R']
    df_s8['R_N'] = df_s8['R'] * df_s8['N']
    
    X = df_s8[feature_names].values
    y_obs = df_s8['Ea_eV'].values
    y_pred = model.predict(X)
    temperatures = df_s8['T_avg_K'].values
    
    # 计算残差
    residuals = y_obs - y_pred
    
    # 生成两张独立的图
    plot_figure6a(df_s8, y_obs, y_pred, temperatures, metrics)
    plot_figure6b(temperatures, residuals)
    
    # 保存数据
    df_out = pd.DataFrame({
        'sample_id': df_s8['sample_id'].values,
        'Ea_observed_eV': y_obs,
        'Ea_predicted_eV': y_pred,
        'residual_eV': residuals,
        'R': df_s8['R'].values,
        'N': df_s8['N'].values,
        'T_avg_K': temperatures
    })
    df_out.to_csv(OUT_DIR / 'figure6_data.csv', index=False, encoding='utf-8-sig')
    print(f'Data saved: {OUT_DIR / "figure6_data.csv"}')
    
    print(f'\nStatistics:')
    print(f'  n = {len(y_obs)}')
    print(f'  R^2 = {metrics["r2"]:.4f}')
    print(f'  CV R^2 = {metrics["cv_r2_mean"]:.4f}')
    print(f'\n[Figure 6 Done]')


if __name__ == '__main__':
    plot_figure6()
