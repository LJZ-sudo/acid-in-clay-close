# -*- coding: utf-8 -*-
"""
Figure 7: 特征重要性分析 (Feature Importance / SHAP)

展示 S8 限域效应模型的特征重要性：
- Figure 7a: GBR 特征重要性条形图
- Figure 7b: Permutation Importance 条形图

特征包括：T (温度), R (比例), N (水分子数), T*N, T*R, R*N 交互项

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
from matplotlib.colors import LinearSegmentedColormap

# 显式路径配置，便于 standalone 使用
SCRIPT_DIR = Path(__file__).resolve().parent
PAPER_FIG_DIR = SCRIPT_DIR.parent
CLOSE_ROOT = PAPER_FIG_DIR.parent
if str(PAPER_FIG_DIR) not in sys.path:
    sys.path.insert(0, str(PAPER_FIG_DIR))
from am_style_config import (
    setup_am_style, COLORS, save_figure, add_panel_label,
    get_diverging_cmap
)

# 路径配置
PHASE3_DIR = CLOSE_ROOT / 'output' / 'phase3_results'
OUT_DIR = SCRIPT_DIR


# 特征显示名称映射 (使用 LaTeX 格式显示下标)
FEATURE_DISPLAY_NAMES = {
    'R': 'R (Acid ratio)',
    'N': r'N ($\mathregular{H_2O}$ molecules)',
    'T_avg_K': 'T (Temperature)',
    'T_N': r'T $\times$ N',
    'T_R': r'T $\times$ R',
    'R_N': r'R $\times$ N'
}

# 特征颜色
FEATURE_COLORS = {
    'R': '#4CAF50',           # 绿色
    'N': '#2196F3',           # 蓝色
    'T_avg_K': '#E91E63',     # 粉红
    'T_N': '#9C27B0',         # 紫色
    'T_R': '#FF9800',         # 橙色
    'R_N': '#00BCD4'          # 青色
}


def load_model_and_data():
    """加载模型和数据"""
    # 加载模型
    with open(PHASE3_DIR / 'models' / 's8_confinement.pkl', 'rb') as f:
        model_data = pickle.load(f)
    model = model_data['model']
    feature_names = model_data['feature_names']
    
    # 加载数据
    df = pd.read_csv(PHASE3_DIR / 'integrated_data.csv')
    df_s8 = df[df['material_type'] == 'S8'].dropna(subset=['R', 'N', 'T_avg_K', 'Ea_eV']).copy()
    df_s8['N'] = df_s8['N'].fillna(df_s8['N'].mean())
    df_s8['T_N'] = df_s8['T_avg_K'] * df_s8['N']
    df_s8['T_R'] = df_s8['T_avg_K'] * df_s8['R']
    df_s8['R_N'] = df_s8['R'] * df_s8['N']
    
    X = df_s8[feature_names].values
    y = df_s8['Ea_eV'].values
    
    return model, feature_names, X, y, df_s8


def compute_permutation_importance(model, X, y, feature_names, n_repeats=30):
    """计算置换重要性 (Permutation Importance)"""
    from sklearn.inspection import permutation_importance
    
    result = permutation_importance(model, X, y, 
                                    n_repeats=n_repeats, 
                                    random_state=42,
                                    scoring='r2')
    
    importance_df = pd.DataFrame({
        'feature': feature_names,
        'importance_mean': result.importances_mean,
        'importance_std': result.importances_std
    }).sort_values('importance_mean', ascending=True)
    
    return importance_df


def plot_figure7a(feature_names, gbr_importance):
    """绘制 Figure 7a: GBR Feature Importance"""
    
    print("Generating Figure 7a: GBR Feature Importance...")
    setup_am_style()
    
    # 准备数据
    imp_df = pd.DataFrame({
        'feature': feature_names,
        'importance': gbr_importance
    }).sort_values('importance', ascending=True)
    
    # 创建图形
    fig, ax = plt.subplots(figsize=(6, 5))
    
    # 颜色列表
    colors = [FEATURE_COLORS.get(f, '#666666') for f in imp_df['feature']]
    
    # 水平条形图
    y_pos = np.arange(len(imp_df))
    bars = ax.barh(y_pos, imp_df['importance'], 
                   color=colors, alpha=0.8,
                   edgecolor='white', linewidth=1)
    
    # 在条形末端显示数值
    for i, (bar, val) in enumerate(zip(bars, imp_df['importance'])):
        ax.text(bar.get_width() + 0.01, bar.get_y() + bar.get_height()/2,
                f'{val:.3f}', va='center', fontsize=10)
    
    # 设置 Y 轴标签
    display_names = [FEATURE_DISPLAY_NAMES.get(f, f) for f in imp_df['feature']]
    ax.set_yticks(y_pos)
    ax.set_yticklabels(display_names, fontsize=11)
    
    ax.set_xlabel('Feature Importance (Gini)', fontsize=12)
    ax.set_title('GBR Feature Importance\n(S8 Confined Model)', fontsize=13, fontweight='bold')
    ax.set_xlim(0, imp_df['importance'].max() * 1.25)
    ax.grid(True, alpha=0.35, axis='x')
    
    plt.tight_layout()
    
    # 保存
    save_figure(fig, str(OUT_DIR / 'figure7a_gbr_importance'))
    plt.close(fig)
    
    return imp_df


def plot_figure7b(perm_imp):
    """绘制 Figure 7b: Permutation Importance"""
    
    print("Generating Figure 7b: Permutation Importance...")
    setup_am_style()
    
    # 创建图形
    fig, ax = plt.subplots(figsize=(6, 5))
    
    # 准备数据
    perm_df = perm_imp.copy()
    colors_perm = [FEATURE_COLORS.get(f, '#666666') for f in perm_df['feature']]
    
    # 水平条形图带误差棒
    y_pos = np.arange(len(perm_df))
    bars = ax.barh(y_pos, perm_df['importance_mean'],
                   xerr=perm_df['importance_std'],
                   color=colors_perm, alpha=0.8,
                   edgecolor='white', linewidth=1,
                   capsize=4, error_kw={'linewidth': 1.5})
    
    # 在条形末端显示数值
    for i, (bar, val, err) in enumerate(zip(bars, perm_df['importance_mean'], perm_df['importance_std'])):
        ax.text(bar.get_width() + err + 0.01, bar.get_y() + bar.get_height()/2,
                f'{val:.3f}', va='center', fontsize=10)
    
    # 设置 Y 轴标签
    display_names = [FEATURE_DISPLAY_NAMES.get(f, f) for f in perm_df['feature']]
    ax.set_yticks(y_pos)
    ax.set_yticklabels(display_names, fontsize=11)
    
    ax.set_xlabel('Permutation Importance (Delta R²)', fontsize=12)
    ax.set_title('Permutation Importance\n(30 repeats)', fontsize=13, fontweight='bold')
    ax.axvline(0, color=COLORS['reference'], linestyle='--', linewidth=1)
    ax.grid(True, alpha=0.35, axis='x')
    
    # 关键发现注释
    main_feature = perm_df.iloc[-1]['feature']
    main_imp = perm_df.iloc[-1]['importance_mean']
    note_text = (
        f'Key finding:\n'
        f'{FEATURE_DISPLAY_NAMES.get(main_feature, main_feature)}\n'
        f'dominates ({main_imp:.1%} of R²)'
    )
    ax.text(0.95, 0.05, note_text, transform=ax.transAxes,
            fontsize=10, verticalalignment='bottom', horizontalalignment='right',
            bbox=dict(boxstyle='round,pad=0.4', facecolor='#FFF9C4',
                     edgecolor='#FBC02D', alpha=0.9))
    
    plt.tight_layout()
    
    # 保存
    save_figure(fig, str(OUT_DIR / 'figure7b_permutation_importance'))
    plt.close(fig)


def plot_figure7():
    """绘制 Figure 7: 特征重要性"""
    
    print("=" * 60)
    print("Figure 7: Feature Importance Analysis")
    print("=" * 60)
    
    # 加载数据
    model, feature_names, X, y, df_s8 = load_model_and_data()
    
    # 获取特征重要性 (GBR 内置)
    gbr_importance = model.feature_importances_
    
    # 计算置换重要性
    print("Computing permutation importance...")
    perm_imp = compute_permutation_importance(model, X, y, feature_names)
    
    # 生成两张独立的图
    imp_df = plot_figure7a(feature_names, gbr_importance)
    plot_figure7b(perm_imp)
    
    # 保存数据
    imp_df_out = pd.DataFrame({
        'feature': feature_names,
        'display_name': [FEATURE_DISPLAY_NAMES.get(f, f) for f in feature_names],
        'gbr_importance': gbr_importance
    })
    imp_df_out = imp_df_out.merge(perm_imp, on='feature')
    imp_df_out.to_csv(OUT_DIR / 'figure7_importance_data.csv', index=False, encoding='utf-8-sig')
    print(f'Data saved: {OUT_DIR / "figure7_importance_data.csv"}')
    
    print(f'\nFeature Importance Ranking (GBR):')
    for _, row in imp_df.iterrows():
        print(f'  {FEATURE_DISPLAY_NAMES.get(row["feature"], row["feature"])}: {row["importance"]:.4f}')
    
    print(f'\n[Figure 7 完成]')


def plot_shap_if_available():
    """尝试绘制 SHAP 图 (如果 shap 包可用)"""
    try:
        import shap
        print("\nSHAP package available, generating SHAP plots...")
        
        model, feature_names, X, y, df_s8 = load_model_and_data()
        
        # 创建 SHAP explainer
        explainer = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(X)
        
        # SHAP 摘要图
        setup_am_style()
        fig, ax = plt.subplots(figsize=(8, 5))
        
        display_names = [FEATURE_DISPLAY_NAMES.get(f, f) for f in feature_names]
        
        shap.summary_plot(shap_values, X, 
                         feature_names=display_names,
                         show=False, plot_size=(8, 5))
        
        plt.title('SHAP Feature Summary (S8 Confined Model)', fontsize=12, fontweight='bold')
        plt.tight_layout()
        
        save_figure(plt.gcf(), str(OUT_DIR / 'figure7_shap_summary'))
        plt.close()
        
        print(f'SHAP plot saved: {OUT_DIR / "figure7_shap_summary"}')
        
    except ImportError:
        print("\nNote: SHAP package not installed. Skipping SHAP analysis.")
        print("Install with: pip install shap")


if __name__ == '__main__':
    plot_figure7()
    plot_shap_if_available()
