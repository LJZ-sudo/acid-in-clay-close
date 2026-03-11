# -*- coding: utf-8 -*-
"""
Figure 8: 交叉验证稳定性分析 (CV Stability)

展示模型的交叉验证稳定性：
- Figure 8a: K-Fold CV 分数分布 (箱线图 + 散点)
- Figure 8b: Learning Curve (训练集大小 vs 得分)

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
from sklearn.model_selection import (
    cross_val_score, KFold, learning_curve, 
    cross_val_predict
)
from sklearn.ensemble import GradientBoostingRegressor

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
    
    # S60 数据
    df_s60 = df[df['material_type'] == 'S60'].dropna(subset=['R', 'T_avg_K', 'Ea_eV']).copy()
    X_s60 = df_s60[['R', 'T_avg_K']].values
    y_s60 = df_s60['Ea_eV'].values
    
    # S8 数据
    df_s8 = df[df['material_type'] == 'S8'].dropna(subset=['R', 'N', 'T_avg_K', 'Ea_eV']).copy()
    df_s8['N'] = df_s8['N'].fillna(df_s8['N'].mean())
    df_s8['T_N'] = df_s8['T_avg_K'] * df_s8['N']
    df_s8['T_R'] = df_s8['T_avg_K'] * df_s8['R']
    df_s8['R_N'] = df_s8['R'] * df_s8['N']
    feature_names = ['R', 'N', 'T_avg_K', 'T_N', 'T_R', 'R_N']
    X_s8 = df_s8[feature_names].values
    y_s8 = df_s8['Ea_eV'].values
    
    return X_s60, y_s60, X_s8, y_s8


def plot_figure8a(cv_scores_s60, cv_scores_s8, n_splits):
    """绘制 Figure 8a: CV Score Distribution"""
    
    print("Generating Figure 8a: CV Score Distribution...")
    setup_am_style()
    
    fig, ax = plt.subplots(figsize=(5.5, 5))
    
    # 箱线图数据
    cv_data = [cv_scores_s60, cv_scores_s8]
    positions = [1, 2]
    labels = ['S60 Baseline', 'S8 Confined']
    colors_box = [COLORS['S60'], COLORS['S8']]
    
    # 箱线图
    bp = ax.boxplot(cv_data, positions=positions, widths=0.5,
                    patch_artist=True, showmeans=True,
                    meanprops={'marker': 'D', 'markerfacecolor': 'white',
                              'markeredgecolor': 'black', 'markersize': 8})
    
    # 设置颜色
    for patch, color in zip(bp['boxes'], colors_box):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)
    
    # 添加散点（jittered）
    for i, (data, pos, color) in enumerate(zip(cv_data, positions, colors_box)):
        jitter = np.random.uniform(-0.1, 0.1, len(data))
        ax.scatter(pos + jitter, data, c=color, alpha=0.8, s=100, 
                  edgecolors='white', linewidths=1.5, zorder=3)
    
    # 标注均值和标准差
    for i, (data, pos) in enumerate(zip(cv_data, positions)):
        mean_val = data.mean()
        std_val = data.std()
        ax.text(pos, data.max() + 0.03, f'μ={mean_val:.3f}\nσ={std_val:.3f}',
                ha='center', va='bottom', fontsize=10)
    
    ax.set_xticks(positions)
    ax.set_xticklabels(labels, fontsize=12)
    ax.set_ylabel('R² Score', fontsize=12)
    ax.set_title(f'{n_splits}-Fold CV Score Distribution', fontsize=13, fontweight='bold')
    ax.set_ylim(min(min(cv_scores_s60), min(cv_scores_s8)) - 0.1,
               max(max(cv_scores_s60), max(cv_scores_s8)) + 0.15)
    ax.grid(True, alpha=0.35, axis='y')
    ax.axhline(0.8, color=COLORS['reference'], linestyle='--', linewidth=1, alpha=0.5)
    ax.text(2.5, 0.8, 'Good fit', va='bottom', fontsize=9, color=COLORS['reference'])
    
    plt.tight_layout()
    
    # 保存
    save_figure(fig, str(OUT_DIR / 'figure8a_cv_distribution'))
    plt.close(fig)


def plot_figure8b(train_sizes_s60, train_scores_s60, test_scores_s60,
                 train_sizes_s8, train_scores_s8, test_scores_s8):
    """绘制 Figure 8b: Learning Curves"""
    
    print("Generating Figure 8b: Learning Curves...")
    setup_am_style()
    
    fig, ax = plt.subplots(figsize=(6, 5))
    
    # S60 学习曲线
    train_mean_s60 = train_scores_s60.mean(axis=1)
    train_std_s60 = train_scores_s60.std(axis=1)
    test_mean_s60 = test_scores_s60.mean(axis=1)
    test_std_s60 = test_scores_s60.std(axis=1)
    
    ax.fill_between(train_sizes_s60, train_mean_s60 - train_std_s60,
                    train_mean_s60 + train_std_s60, alpha=0.15, color=COLORS['S60'])
    ax.fill_between(train_sizes_s60, test_mean_s60 - test_std_s60,
                    test_mean_s60 + test_std_s60, alpha=0.15, color=COLORS['S60'])
    ax.plot(train_sizes_s60, train_mean_s60, 'o--', color=COLORS['S60'],
            label='S60 Training', alpha=0.7)
    ax.plot(train_sizes_s60, test_mean_s60, 'o-', color=COLORS['S60'],
            label='S60 Validation', linewidth=2)
    
    # S8 学习曲线
    train_mean_s8 = train_scores_s8.mean(axis=1)
    train_std_s8 = train_scores_s8.std(axis=1)
    test_mean_s8 = test_scores_s8.mean(axis=1)
    test_std_s8 = test_scores_s8.std(axis=1)
    
    ax.fill_between(train_sizes_s8, train_mean_s8 - train_std_s8,
                    train_mean_s8 + train_std_s8, alpha=0.15, color=COLORS['S8'])
    ax.fill_between(train_sizes_s8, test_mean_s8 - test_std_s8,
                    test_mean_s8 + test_std_s8, alpha=0.15, color=COLORS['S8'])
    ax.plot(train_sizes_s8, train_mean_s8, 's--', color=COLORS['S8'],
            label='S8 Training', alpha=0.7)
    ax.plot(train_sizes_s8, test_mean_s8, 's-', color=COLORS['S8'],
            label='S8 Validation', linewidth=2)
    
    ax.set_xlabel('Training Set Size', fontsize=12)
    ax.set_ylabel('R² Score', fontsize=12)
    ax.set_title('Learning Curves', fontsize=13, fontweight='bold')
    ax.legend(loc='lower right', fontsize=10, ncol=2)
    ax.grid(True, alpha=0.35)
    ax.set_ylim(0, 1.05)
    
    # 诊断文本
    gap_s60 = train_mean_s60[-1] - test_mean_s60[-1]
    gap_s8 = train_mean_s8[-1] - test_mean_s8[-1]
    diag_text = (
        f'Train-Val Gap:\n'
        f'S60: {gap_s60:.3f}\n'
        f'S8: {gap_s8:.3f}'
    )
    bias_variance = 'Low variance' if gap_s8 < 0.1 else 'Some overfitting'
    ax.text(0.05, 0.05, diag_text + f'\n({bias_variance})', transform=ax.transAxes,
            fontsize=10, verticalalignment='bottom',
            bbox=dict(boxstyle='round,pad=0.4', facecolor='white',
                     edgecolor='#CCCCCC', alpha=0.9))
    
    plt.tight_layout()
    
    # 保存
    save_figure(fig, str(OUT_DIR / 'figure8b_learning_curves'))
    plt.close(fig)
    
    return train_mean_s60, test_mean_s60, train_mean_s8, test_mean_s8


def plot_figure8():
    """绘制 Figure 8: CV 稳定性分析"""
    
    print("=" * 60)
    print("Figure 8: Cross-Validation Stability")
    print("=" * 60)
    
    # 加载数据
    X_s60, y_s60, X_s8, y_s8 = load_data()
    
    # 定义模型
    from sklearn.linear_model import Ridge
    from sklearn.preprocessing import PolynomialFeatures, StandardScaler
    from sklearn.pipeline import Pipeline
    
    model_s60 = Pipeline([
        ('poly', PolynomialFeatures(degree=2, include_bias=False)),
        ('scale', StandardScaler()),
        ('ridge', Ridge(alpha=5.0))
    ])
    
    model_s8 = GradientBoostingRegressor(
        n_estimators=120, learning_rate=0.05, max_depth=3,
        min_samples_leaf=4, random_state=42
    )
    
    # ==================== CV Scores ====================
    print("Computing CV scores...")
    n_splits = 5
    kf = KFold(n_splits=n_splits, shuffle=True, random_state=42)
    
    cv_scores_s60 = cross_val_score(model_s60, X_s60, y_s60, cv=kf, scoring='r2')
    cv_scores_s8 = cross_val_score(model_s8, X_s8, y_s8, cv=kf, scoring='r2')
    
    print(f"  S60 CV R^2: {cv_scores_s60.mean():.4f} +/- {cv_scores_s60.std():.4f}")
    print(f"  S8 CV R^2: {cv_scores_s8.mean():.4f} +/- {cv_scores_s8.std():.4f}")
    
    # ==================== Learning Curves ====================
    print("Computing learning curves...")
    train_sizes = np.linspace(0.2, 1.0, 5)
    
    train_sizes_s60, train_scores_s60, test_scores_s60 = learning_curve(
        model_s60, X_s60, y_s60, train_sizes=train_sizes, cv=kf,
        scoring='r2', random_state=42
    )
    
    train_sizes_s8, train_scores_s8, test_scores_s8 = learning_curve(
        model_s8, X_s8, y_s8, train_sizes=train_sizes, cv=kf,
        scoring='r2', random_state=42
    )
    
    # 生成两张独立的图
    plot_figure8a(cv_scores_s60, cv_scores_s8, n_splits)
    plot_figure8b(train_sizes_s60, train_scores_s60, test_scores_s60,
                 train_sizes_s8, train_scores_s8, test_scores_s8)
    
    # 保存数据
    cv_data_df = pd.DataFrame({
        'fold': list(range(1, n_splits + 1)) * 2,
        'model': ['S60 Baseline'] * n_splits + ['S8 Confined'] * n_splits,
        'cv_r2_score': list(cv_scores_s60) + list(cv_scores_s8)
    })
    cv_data_df.to_csv(OUT_DIR / 'figure8_cv_scores.csv', index=False, encoding='utf-8-sig')
    
    # 计算学习曲线统计量
    train_mean_s60 = train_scores_s60.mean(axis=1)
    train_std_s60 = train_scores_s60.std(axis=1)
    test_mean_s60 = test_scores_s60.mean(axis=1)
    test_std_s60 = test_scores_s60.std(axis=1)
    train_mean_s8 = train_scores_s8.mean(axis=1)
    train_std_s8 = train_scores_s8.std(axis=1)
    test_mean_s8 = test_scores_s8.mean(axis=1)
    test_std_s8 = test_scores_s8.std(axis=1)
    
    learning_curve_df = pd.DataFrame({
        'train_size': list(train_sizes_s60) + list(train_sizes_s8),
        'model': ['S60'] * len(train_sizes_s60) + ['S8'] * len(train_sizes_s8),
        'train_score_mean': list(train_mean_s60) + list(train_mean_s8),
        'train_score_std': list(train_std_s60) + list(train_std_s8),
        'test_score_mean': list(test_mean_s60) + list(test_mean_s8),
        'test_score_std': list(test_std_s60) + list(test_std_s8)
    })
    learning_curve_df.to_csv(OUT_DIR / 'figure8_learning_curve.csv', index=False, encoding='utf-8-sig')
    
    print(f'\nData saved:')
    print(f'  {OUT_DIR / "figure8_cv_scores.csv"}')
    print(f'  {OUT_DIR / "figure8_learning_curve.csv"}')
    
    print(f'\n[Figure 8 Done]')


if __name__ == '__main__':
    plot_figure8()
