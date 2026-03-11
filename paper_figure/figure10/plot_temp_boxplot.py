# -*- coding: utf-8 -*-
"""
Figure 10: 低温/高温 ΔEa 箱线图 + Bootstrap CI + 统计检验

展示不同温区的限域效应差异：
- 箱线图 + 散点叠加
- Bootstrap 95% CI
- t检验 + Cohen's d 效应量

数据来源: close/output/phase3_results/confinement/
"""

import sys
import io
import json
from pathlib import Path

# 修复 Windows 控制台编码问题
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
    format_pvalue
)

# 路径配置
PHASE3_DIR = CLOSE_ROOT / 'output' / 'phase3_results'
CONFINEMENT_DIR = PHASE3_DIR / 'confinement'
OUT_DIR = SCRIPT_DIR


def bootstrap_mean_ci(data, n_bootstrap=2000, ci=0.95):
    """计算 Bootstrap 95% CI"""
    data = np.asarray(data).flatten()
    data = data[~np.isnan(data)]
    n = len(data)
    if n < 2:
        return np.nan, np.nan, np.nan
    
    rng = np.random.default_rng(42)
    boot_means = np.array([np.mean(rng.choice(data, size=n, replace=True)) 
                           for _ in range(n_bootstrap)])
    
    alpha = 1 - ci
    ci_low = np.percentile(boot_means, alpha / 2 * 100)
    ci_high = np.percentile(boot_means, (1 - alpha / 2) * 100)
    mean = np.mean(data)
    
    return mean, ci_low, ci_high


def cohens_d(group1, group2):
    """计算 Cohen's d 效应量"""
    n1, n2 = len(group1), len(group2)
    var1, var2 = np.var(group1, ddof=1), np.var(group2, ddof=1)
    
    # Pooled standard deviation
    pooled_std = np.sqrt(((n1 - 1) * var1 + (n2 - 1) * var2) / (n1 + n2 - 2))
    
    d = (np.mean(group1) - np.mean(group2)) / pooled_std
    return d


def load_delta_ea_data():
    """加载 ΔEa 数据"""
    delta_ea_csv = CONFINEMENT_DIR / 'delta_ea_by_segment.csv'
    if delta_ea_csv.exists():
        return pd.read_csv(delta_ea_csv)
    
    # 从 Figure 9 数据加载
    fig9_data = Path(__file__).resolve().parent.parent / 'figure9' / 'figure9_data.csv'
    if fig9_data.exists():
        return pd.read_csv(fig9_data)
    
    raise FileNotFoundError("Delta Ea data not found. Please run Figure 9 first.")


def plot_figure10():
    """绘制 Figure 10: 清晰版箱线图"""
    
    print("=" * 60)
    print("Figure 10: Low T vs High T Delta Ea Comparison")
    print("=" * 60)
    
    setup_am_style()
    
    # 加载数据
    df = load_delta_ea_data()
    
    # 温区划分
    low_T = df[df['T_avg_K'] < 230]['delta_Ea'].values
    mid_T = df[(df['T_avg_K'] >= 230) & (df['T_avg_K'] < 270)]['delta_Ea'].values
    high_T = df[df['T_avg_K'] >= 270]['delta_Ea'].values
    
    print(f"  Low T (<230K): n={len(low_T)}")
    print(f"  Mid T (230-270K): n={len(mid_T)}")
    print(f"  High T (>=270K): n={len(high_T)}")
    
    # Bootstrap CI
    low_mean, low_ci_l, low_ci_h = bootstrap_mean_ci(low_T)
    mid_mean, mid_ci_l, mid_ci_h = bootstrap_mean_ci(mid_T)
    high_mean, high_ci_l, high_ci_h = bootstrap_mean_ci(high_T)
    
    # 统计检验 (Low vs High)
    t_stat, t_pvalue = stats.ttest_ind(low_T, high_T)
    welch_stat, welch_pvalue = stats.ttest_ind(low_T, high_T, equal_var=False)
    d_value = cohens_d(low_T, high_T)
    
    # 效应量解释
    if abs(d_value) < 0.2:
        effect_size_interp = 'negligible'
    elif abs(d_value) < 0.5:
        effect_size_interp = 'small'
    elif abs(d_value) < 0.8:
        effect_size_interp = 'medium'
    else:
        effect_size_interp = 'large'
    
    # ==================== 简洁清晰版：箱线图为主体 ====================
    fig, ax = plt.subplots(figsize=(7, 5.5))
    
    # 数据和配置
    box_data = [low_T, mid_T, high_T]
    positions = [1, 2, 3]
    labels = ['Low T (<230 K)', 'Mid T (230-270 K)', 'High T (>=270 K)']
    colors_box = [COLORS['low_temp'], COLORS['mid_temp'], COLORS['high_temp']]
    
    # 1. 先绘制散点（在箱线图后面，作为背景）
    np.random.seed(42)
    for i, (data, pos, color) in enumerate(zip(box_data, positions, colors_box)):
        jitter = np.random.uniform(-0.18, 0.18, len(data))
        ax.scatter(pos + jitter, data, c=color, alpha=0.55, s=30,
                   edgecolors='white', linewidths=0.3, zorder=1)
    
    # 2. 箱线图为主体（视觉焦点）
    bp = ax.boxplot(box_data, positions=positions, widths=0.5,
                    patch_artist=True, showmeans=True,
                    meanprops={'marker': '_', 'markerfacecolor': 'black',
                               'markeredgecolor': 'black', 'markersize': 12,
                               'markeredgewidth': 2},
                    medianprops={'color': 'white', 'linewidth': 2},
                    whiskerprops={'linewidth': 1.5, 'color': '#333333'},
                    capprops={'linewidth': 1.5, 'color': '#333333'},
                    flierprops={'marker': 'o', 'markersize': 5, 
                                'markerfacecolor': 'none', 'markeredgecolor': '#666666',
                                'alpha': 0.6},
                    zorder=3)
    
    for patch, color in zip(bp['boxes'], colors_box):
        patch.set_facecolor(color)
        patch.set_alpha(0.8)
        patch.set_edgecolor('#333333')
        patch.set_linewidth(1.5)
    
    # 3. 零参考线
    ax.axhline(0, color='#888888', linestyle='--', linewidth=1.2, alpha=0.7, zorder=2)
    
    # 4. 显著性标注 (Low vs High)
    y_max = max(max(low_T), max(high_T))
    bracket_y = y_max + 0.06
    bracket_height = 0.03
    
    ax.plot([1, 1, 3, 3], 
            [bracket_y, bracket_y + bracket_height, bracket_y + bracket_height, bracket_y], 
            'k-', linewidth=1.2, zorder=4)
    
    sig_text = '***' if t_pvalue < 0.001 else ('**' if t_pvalue < 0.01 else ('*' if t_pvalue < 0.05 else 'ns'))
    ax.text(2, bracket_y + bracket_height + 0.015, sig_text, 
            ha='center', va='bottom', fontsize=13, fontweight='bold')
    
    # 5. 坐标轴设置
    ax.set_xticks(positions)
    ax.set_xticklabels(labels, fontsize=11)
    ax.set_ylabel(r'$\Delta E_a$ (eV)', fontsize=12)
    ax.set_title(r'$\Delta E_a$ Distribution by Temperature Region', 
                 fontsize=13, fontweight='bold', pad=12)
    
    # Y轴范围
    y_min = min(min(low_T), min(mid_T), min(high_T)) - 0.08
    y_max_plot = bracket_y + bracket_height + 0.08
    ax.set_ylim(y_min, y_max_plot)
    ax.set_xlim(0.5, 3.5)
    
    # 网格
    ax.grid(True, alpha=0.25, axis='y', linestyle='-', linewidth=0.6)
    ax.set_axisbelow(True)
    
    # 6. 样本量标注（简洁，放在 x 轴标签下）
    means = [low_mean, mid_mean, high_mean]
    ci_lows = [low_ci_l, mid_ci_l, high_ci_l]
    ci_highs = [low_ci_h, mid_ci_h, high_ci_h]
    
    # 在每个箱体上方标注 n 和 mean
    for pos, n, mean in zip(positions, [len(low_T), len(mid_T), len(high_T)], means):
        ax.text(pos, y_min + 0.01, f'n={n}', ha='center', va='bottom', 
                fontsize=9, color='#555555')
    
    plt.tight_layout()
    
    # 保存
    save_figure(fig, str(OUT_DIR / 'figure10_temp_boxplot'))
    plt.close(fig)
    
    # 保存统计数据
    stats_df = pd.DataFrame({
        'temperature_region': ['Low T (<230K)', 'Mid T (230-270K)', 'High T (>=270K)'],
        'n': [len(low_T), len(mid_T), len(high_T)],
        'mean': means,
        'std': [np.std(low_T), np.std(mid_T), np.std(high_T)],
        'ci_95_low': ci_lows,
        'ci_95_high': ci_highs
    })
    stats_df.to_csv(OUT_DIR / 'figure10_statistics.csv', index=False, encoding='utf-8-sig')
    
    test_results = {
        'low_vs_high_ttest': {
            't_statistic': float(t_stat),
            'p_value': float(t_pvalue),
            'cohens_d': float(d_value),
            'effect_size': effect_size_interp
        },
        'welch_ttest': {
            't_statistic': float(welch_stat),
            'p_value': float(welch_pvalue)
        }
    }
    with open(OUT_DIR / 'figure10_test_results.json', 'w') as f:
        json.dump(test_results, f, indent=2)
    
    print(f'\nStatistical Test Results:')
    print(f'  t-statistic = {t_stat:.4f}')
    print(f'  p-value = {t_pvalue:.2e}')
    print(f"  Cohen's d = {d_value:.4f} ({effect_size_interp})")
    print(f'  Significant at alpha=0.05: {t_pvalue < 0.05}')
    
    print(f'\nData saved:')
    print(f'  {OUT_DIR / "figure10_statistics.csv"}')
    print(f'  {OUT_DIR / "figure10_test_results.json"}')
    
    print(f'\n[Figure 10 Done]')


if __name__ == '__main__':
    plot_figure10()
