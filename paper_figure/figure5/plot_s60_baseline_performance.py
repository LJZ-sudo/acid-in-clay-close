# -*- coding: utf-8 -*-
"""
Figure 5: S60 Baseline Model Performance (Ea_pred vs Ea_obs)

展示 S60 基准模型（纯酸液参照系）的预测性能：
- Figure 5a: Ea 预测值 vs 观测值散点图
- Figure 5b: 残差分布直方图

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
from scipy import stats

# 显式路径配置，便于 standalone 使用
SCRIPT_DIR = Path(__file__).resolve().parent
PAPER_FIG_DIR = SCRIPT_DIR.parent
CLOSE_ROOT = PAPER_FIG_DIR.parent
if str(PAPER_FIG_DIR) not in sys.path:
    sys.path.insert(0, str(PAPER_FIG_DIR))
from am_style_config import (
    setup_am_style, COLORS, save_figure, format_r2
)

# 路径配置
PHASE3_DIR = CLOSE_ROOT / 'output' / 'phase3_results'
OUT_DIR = SCRIPT_DIR


def load_data_and_model():
    """加载数据和模型"""
    # 加载数据
    df = pd.read_csv(PHASE3_DIR / 'integrated_data.csv')
    df_s60 = df[df['material_type'] == 'S60'].dropna(subset=['R', 'T_avg_K', 'Ea_eV']).copy()
    
    # 加载模型
    with open(PHASE3_DIR / 'models' / 's60_baseline.pkl', 'rb') as f:
        model_data = pickle.load(f)
    pipeline = model_data['pipeline']
    
    # 加载指标
    import json
    with open(PHASE3_DIR / 'models' / 'metrics.json', 'r') as f:
        metrics = json.load(f)
    
    return df_s60, pipeline, metrics['s60']


def plot_figure5a():
    """绘制 Figure 5a: Pred vs Obs 散点图"""
    
    print("Generating Figure 5a: Pred vs Obs...")
    setup_am_style()
    
    # 加载数据
    df_s60, pipeline, metrics = load_data_and_model()
    
    # 预测
    X = df_s60[['R', 'T_avg_K']].values
    y_obs = df_s60['Ea_eV'].values
    y_pred = pipeline.predict(X)
    
    # 创建单独的图形
    fig, ax = plt.subplots(figsize=(5.5, 5))
    
    # 散点图
    ax.scatter(y_obs, y_pred, 
               c=COLORS['S60'], alpha=0.7, s=60, 
               edgecolors='white', linewidths=0.8,
               label='S60 samples')
    
    # 45度参考线 (完美预测线)
    lims = [min(y_obs.min(), y_pred.min()) - 0.05, 
            max(y_obs.max(), y_pred.max()) + 0.05]
    ax.plot(lims, lims, '-', color=COLORS['fit_line'], linewidth=2,
            label='Perfect prediction (y=x)', zorder=1)
    
    ax.set_xlim(lims)
    ax.set_ylim(lims)
    ax.set_xlabel('$E_a$ observed (eV)', fontsize=12)
    ax.set_ylabel('$E_a$ predicted (eV)', fontsize=12)
    ax.set_title('S60 Baseline Model: $E_a$ Prediction', fontsize=13, fontweight='bold')
    ax.legend(loc='lower right', fontsize=10)
    ax.grid(True, alpha=0.35)
    ax.set_aspect('equal', adjustable='box')
    
    # 统计信息框
    stats_text = (
        f'n = {len(y_obs)}\n'
        f'R² = {metrics["r2"]:.3f}\n'
        f'CV R² = {metrics["cv_r2_mean"]:.3f} ± {metrics["cv_r2_std"]:.3f}\n'
        f'MAE = {metrics["mae_eV"]:.4f} eV'
    )
    ax.text(0.05, 0.95, stats_text, transform=ax.transAxes,
            fontsize=10, verticalalignment='top',
            bbox=dict(boxstyle='round,pad=0.4', facecolor='white', 
                     edgecolor='#CCCCCC', alpha=0.9))
    
    plt.tight_layout()
    
    # 保存
    save_figure(fig, str(OUT_DIR / 'figure5a_pred_vs_obs'))
    plt.close(fig)
    
    return y_obs, y_pred, df_s60


def plot_figure5b(y_obs, y_pred):
    """绘制 Figure 5b: 残差分布"""
    
    print("Generating Figure 5b: Residual Distribution...")
    setup_am_style()
    
    # 计算残差
    residuals = y_obs - y_pred
    
    # 创建单独的图形
    fig, ax = plt.subplots(figsize=(5.5, 4.5))
    
    # 残差直方图
    n_bins = 15
    n, bins, patches = ax.hist(residuals, bins=n_bins, 
                                color=COLORS['S60'], alpha=0.7,
                                edgecolor='white', linewidth=1)
    
    # 正态分布拟合曲线
    mu, std = residuals.mean(), residuals.std()
    x_norm = np.linspace(residuals.min(), residuals.max(), 100)
    y_norm = stats.norm.pdf(x_norm, mu, std) * len(residuals) * (bins[1] - bins[0])
    ax.plot(x_norm, y_norm, '-', color=COLORS['fit_line'], linewidth=2,
            label=f'Normal fit\n(μ={mu:.4f}, σ={std:.4f})')
    
    # 零线
    ax.axvline(0, color=COLORS['reference'], linestyle='--', linewidth=1.5,
               label='Zero residual')
    
    ax.set_xlabel('Residual (eV)', fontsize=12)
    ax.set_ylabel('Frequency', fontsize=12)
    ax.set_title('Residual Distribution', fontsize=13, fontweight='bold')
    ax.legend(loc='upper right', fontsize=10)
    ax.grid(True, alpha=0.35, axis='y')
    
    # Shapiro-Wilk 检验
    if len(residuals) >= 3:
        shapiro_stat, shapiro_p = stats.shapiro(residuals)
        normality_text = f'Shapiro-Wilk\nW = {shapiro_stat:.3f}\np = {shapiro_p:.4f}'
        ax.text(0.95, 0.95, normality_text, transform=ax.transAxes,
                fontsize=10, verticalalignment='top', horizontalalignment='right',
                bbox=dict(boxstyle='round,pad=0.4', facecolor='white',
                         edgecolor='#CCCCCC', alpha=0.9))
    
    plt.tight_layout()
    
    # 保存
    save_figure(fig, str(OUT_DIR / 'figure5b_residual_distribution'))
    plt.close(fig)


def plot_figure5():
    """生成 Figure 5 的两张独立图"""
    
    print("=" * 60)
    print("Figure 5: S60 Baseline Model Performance")
    print("=" * 60)
    
    # 加载数据
    df_s60, pipeline, metrics = load_data_and_model()
    X = df_s60[['R', 'T_avg_K']].values
    y_obs = df_s60['Ea_eV'].values
    y_pred = pipeline.predict(X)
    residuals = y_obs - y_pred
    
    # 生成两张独立的图
    plot_figure5a()
    plot_figure5b(y_obs, y_pred)
    
    # 保存数据
    df_out = pd.DataFrame({
        'sample_id': df_s60['sample_id'].values,
        'Ea_observed_eV': y_obs,
        'Ea_predicted_eV': y_pred,
        'residual_eV': residuals,
        'R': df_s60['R'].values,
        'T_avg_K': df_s60['T_avg_K'].values
    })
    df_out.to_csv(OUT_DIR / 'figure5_data.csv', index=False, encoding='utf-8-sig')
    print(f'Data saved: {OUT_DIR / "figure5_data.csv"}')
    
    print(f'\nStatistics:')
    print(f'  n = {len(y_obs)}')
    print(f'  R^2 = {metrics["r2"]:.4f}')
    print(f'  CV R^2 = {metrics["cv_r2_mean"]:.4f} +/- {metrics["cv_r2_std"]:.4f}')
    print(f'  MAE = {metrics["mae_eV"]:.4f} eV')
    print(f'\n[Figure 5 Done]')


if __name__ == '__main__':
    plot_figure5()
