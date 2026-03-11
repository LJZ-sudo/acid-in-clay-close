# -*- coding: utf-8 -*-
"""
Figure 12: 残差诊断图（Q-Q Plot / Shapiro-Wilk）

线性拟合 ΔEa(T) 的残差诊断：
- Panel (a): Q-Q Plot (正态性)
- Panel (b): Residual vs Fitted (同方差性)
- Panel (c): Histogram of Residuals
- Panel (d): Scale-Location Plot

数据来源: close/output/phase3_results/confinement/
"""

import sys
import pickle
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


def compute_residuals(T, delta_Ea):
    """计算线性拟合残差"""
    slope, intercept, r_value, p_value, std_err = stats.linregress(T, delta_Ea)
    fitted = slope * T + intercept
    residuals = delta_Ea - fitted
    
    # 标准化残差
    residual_std = np.std(residuals)
    standardized_residuals = residuals / residual_std
    
    return residuals, fitted, standardized_residuals, slope, intercept, r_value**2


def plot_figure12():
    """绘制 Figure 12: 残差诊断"""
    
    print("=" * 60)
    print("Figure 12: Residual Diagnostics")
    print("=" * 60)
    
    setup_am_style()
    
    # 加载数据
    df = load_delta_ea_data()
    T = df['T_avg_K'].values
    delta_Ea = df['delta_Ea'].values
    
    # 计算残差
    residuals, fitted, std_residuals, slope, intercept, r2 = compute_residuals(T, delta_Ea)
    
    # 统计检验
    shapiro_stat, shapiro_p = stats.shapiro(residuals)
    
    # Durbin-Watson (自相关检验)
    def durbin_watson(resid):
        diff = np.diff(resid)
        dw = np.sum(diff**2) / np.sum(resid**2)
        return dw
    
    dw_stat = durbin_watson(residuals)
    
    # Breusch-Pagan (异方差检验) - 简化版
    # 检测残差平方与拟合值的相关性
    bp_r, bp_p = stats.pearsonr(fitted, residuals**2)
    
    print(f"  Shapiro-Wilk W = {shapiro_stat:.4f}, p = {shapiro_p:.4f}")
    print(f"  Durbin-Watson = {dw_stat:.4f}")
    print(f"  Residual² ~ Fitted r = {bp_r:.4f}, p = {bp_p:.4f}")
    
    # 创建图形 (2x2 布局)
    fig, axes = plt.subplots(2, 2, figsize=(10, 9))
    
    # ==================== Panel (a): Q-Q Plot ====================
    ax1 = axes[0, 0]
    
    # Q-Q 图
    (osm, osr), (slope_qq, intercept_qq, r_qq) = stats.probplot(std_residuals, dist="norm")
    
    ax1.scatter(osm, osr, c=COLORS['S8'], alpha=0.7, s=50,
               edgecolors='white', linewidths=0.8)
    
    # 参考线
    line_x = np.array([osm.min(), osm.max()])
    line_y = slope_qq * line_x + intercept_qq
    ax1.plot(line_x, line_y, '-', color=COLORS['fit_line'], linewidth=2,
             label=f'Reference line (R²={r_qq**2:.3f})')
    
    ax1.set_xlabel('Theoretical Quantiles', fontsize=11)
    ax1.set_ylabel('Sample Quantiles', fontsize=11)
    ax1.set_title('Q-Q Plot (Normal)', fontsize=12, fontweight='bold')
    ax1.legend(loc='lower right', fontsize=9)
    ax1.grid(True, alpha=0.35)
    
    # 正态性判断
    normal_text = (
        f'Shapiro-Wilk Test:\n'
        f'W = {shapiro_stat:.4f}\n'
        f'p = {shapiro_p:.4f}\n'
        f'Normal: {"Yes" if shapiro_p > 0.05 else "No"}'
    )
    ax1.text(0.05, 0.95, normal_text, transform=ax1.transAxes,
             fontsize=9, verticalalignment='top',
             bbox=dict(boxstyle='round,pad=0.4', facecolor='white',
                      edgecolor='#CCCCCC', alpha=0.95))
    
    add_panel_label(ax1, 'a')
    
    # ==================== Panel (b): Residual vs Fitted ====================
    ax2 = axes[0, 1]
    
    ax2.scatter(fitted, residuals, c=COLORS['S8'], alpha=0.7, s=50,
               edgecolors='white', linewidths=0.8)
    
    # 零线
    ax2.axhline(0, color=COLORS['reference'], linestyle='--', linewidth=1.5)
    
    # LOWESS 平滑线
    try:
        from statsmodels.nonparametric.smoothers_lowess import lowess
        smoothed = lowess(residuals, fitted, frac=0.5)
        ax2.plot(smoothed[:, 0], smoothed[:, 1], '-', color=COLORS['fit_line'],
                 linewidth=2, label='LOWESS')
        ax2.legend(loc='best', fontsize=9)
    except ImportError:
        pass
    
    ax2.set_xlabel('Fitted Values (eV)', fontsize=11)
    ax2.set_ylabel('Residuals (eV)', fontsize=11)
    ax2.set_title('Residuals vs Fitted', fontsize=12, fontweight='bold')
    ax2.grid(True, alpha=0.35)
    
    # 异方差检验结果
    hetero_text = (
        f'Heteroscedasticity:\n'
        f'r(Resid², Fitted) = {bp_r:.3f}\n'
        f'p = {bp_p:.4f}\n'
        f'Constant variance: {"Yes" if bp_p > 0.05 else "No"}'
    )
    ax2.text(0.95, 0.95, hetero_text, transform=ax2.transAxes,
             fontsize=9, verticalalignment='top', horizontalalignment='right',
             bbox=dict(boxstyle='round,pad=0.4', facecolor='white',
                      edgecolor='#CCCCCC', alpha=0.95))
    
    add_panel_label(ax2, 'b')
    
    # ==================== Panel (c): Histogram of Residuals ====================
    ax3 = axes[1, 0]
    
    n_bins = 15
    n, bins, patches = ax3.hist(residuals, bins=n_bins, density=True,
                                 alpha=0.7, color=COLORS['S8'],
                                 edgecolor='white', linewidth=1)
    
    # 正态分布曲线
    mu, sigma = np.mean(residuals), np.std(residuals)
    x_norm = np.linspace(residuals.min(), residuals.max(), 100)
    y_norm = stats.norm.pdf(x_norm, mu, sigma)
    ax3.plot(x_norm, y_norm, '-', color=COLORS['fit_line'], linewidth=2,
             label=f'Normal (μ={mu:.4f}, σ={sigma:.4f})')
    
    ax3.axvline(0, color=COLORS['reference'], linestyle='--', linewidth=1.5)
    
    ax3.set_xlabel('Residuals (eV)', fontsize=11)
    ax3.set_ylabel('Density', fontsize=11)
    ax3.set_title('Residual Distribution', fontsize=12, fontweight='bold')
    ax3.legend(loc='upper right', fontsize=9)
    ax3.grid(True, alpha=0.35, axis='y')
    
    add_panel_label(ax3, 'c')
    
    # ==================== Panel (d): Scale-Location Plot ====================
    ax4 = axes[1, 1]
    
    # sqrt(|standardized residuals|)
    sqrt_abs_std_resid = np.sqrt(np.abs(std_residuals))
    
    ax4.scatter(fitted, sqrt_abs_std_resid, c=COLORS['S8'], alpha=0.7, s=50,
               edgecolors='white', linewidths=0.8)
    
    # 平滑线
    try:
        from statsmodels.nonparametric.smoothers_lowess import lowess
        smoothed = lowess(sqrt_abs_std_resid, fitted, frac=0.5)
        ax4.plot(smoothed[:, 0], smoothed[:, 1], '-', color=COLORS['fit_line'],
                 linewidth=2, label='LOWESS')
        ax4.legend(loc='best', fontsize=9)
    except ImportError:
        pass
    
    ax4.set_xlabel('Fitted Values (eV)', fontsize=11)
    ax4.set_ylabel('$\\sqrt{|\\mathrm{Standardized\\ Residuals}|}$', fontsize=11)
    ax4.set_title('Scale-Location Plot', fontsize=12, fontweight='bold')
    ax4.grid(True, alpha=0.35)
    
    # Durbin-Watson 结果
    dw_text = (
        f'Durbin-Watson:\n'
        f'd = {dw_stat:.3f}\n'
        f'(d≈2: no autocorr)'
    )
    ax4.text(0.95, 0.95, dw_text, transform=ax4.transAxes,
             fontsize=9, verticalalignment='top', horizontalalignment='right',
             bbox=dict(boxstyle='round,pad=0.4', facecolor='white',
                      edgecolor='#CCCCCC', alpha=0.95))
    
    add_panel_label(ax4, 'd')
    
    plt.tight_layout()
    
    # 保存
    save_figure(fig, str(OUT_DIR / 'figure12_residual_diagnostics'))
    plt.close(fig)
    
    # 保存诊断数据
    diag_df = pd.DataFrame({
        'T_avg_K': T,
        'delta_Ea': delta_Ea,
        'fitted': fitted,
        'residual': residuals,
        'std_residual': std_residuals
    })
    diag_df.to_csv(OUT_DIR / 'figure12_residual_data.csv', index=False, encoding='utf-8-sig')
    
    # 诊断结果汇总
    import json
    diagnostics = {
        'shapiro_wilk': {
            'W': float(shapiro_stat),
            'p_value': float(shapiro_p),
            'is_normal': bool(shapiro_p > 0.05)
        },
        'durbin_watson': {
            'statistic': float(dw_stat),
            'interpretation': 'No autocorrelation' if 1.5 < dw_stat < 2.5 else 'Possible autocorrelation'
        },
        'heteroscedasticity': {
            'correlation': float(bp_r),
            'p_value': float(bp_p),
            'constant_variance': bool(bp_p > 0.05)
        },
        'linear_fit': {
            'slope': float(slope),
            'intercept': float(intercept),
            'r_squared': float(r2)
        }
    }
    with open(OUT_DIR / 'figure12_diagnostics.json', 'w') as f:
        json.dump(diagnostics, f, indent=2)
    
    print(f'\nDiagnostic Summary:')
    print(f'  Normality (Shapiro-Wilk): {"PASS" if shapiro_p > 0.05 else "FAIL"} (p={shapiro_p:.4f})')
    print(f'  No Autocorrelation (Durbin-Watson): {"PASS" if 1.5 < dw_stat < 2.5 else "CHECK"} (d={dw_stat:.3f})')
    print(f'  Homoscedasticity: {"PASS" if bp_p > 0.05 else "FAIL"} (p={bp_p:.4f})')
    
    print(f'\nData saved:')
    print(f'  {OUT_DIR / "figure12_residual_data.csv"}')
    print(f'  {OUT_DIR / "figure12_diagnostics.json"}')
    
    print(f'\n[Figure 12 完成]')


if __name__ == '__main__':
    plot_figure12()
