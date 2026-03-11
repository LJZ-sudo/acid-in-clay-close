# -*- coding: utf-8 -*-
"""
Figure 4: Ea热力图
横轴: R值, 纵轴: N值, 色标: Ea (eV)
分高温段和低温段，S8和S60各两张子图
"""
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import seaborn as sns

OUT_DIR = Path(__file__).resolve().parent

# AM 期刊风格
AM_RC = {
    'font.family': 'sans-serif',
    'font.sans-serif': ['Arial', 'Helvetica', 'DejaVu Sans'],
    'font.size': 10,
    'axes.labelsize': 11,
    'axes.titlesize': 12,
    'xtick.labelsize': 9,
    'ytick.labelsize': 9,
    'legend.fontsize': 9,
}

def create_heatmap_matrix(df_material, temp_region):
    """
    为特定材料和温区创建热力图矩阵
    """
    # 选择Ea列
    ea_col = 'Ea_high_temp' if temp_region == 'high' else 'Ea_low_temp'
    
    # 创建pivot table
    pivot = df_material.pivot_table(
        values=ea_col,
        index='N',
        columns='R',
        aggfunc='mean'  # 如果有重复，取平均
    )
    
    return pivot

def plot_ea_heatmaps(material='S8'):
    """
    为单个材料绘制高温和低温两个热力图
    """
    # 读取数据
    csv_path = OUT_DIR / "ea_heatmap_data.csv"
    df = pd.read_csv(csv_path)
    
    # 筛选特定材料
    df_mat = df[df['material'] == material].copy()
    
    if len(df_mat) == 0:
        print(f"No data found for {material}")
        return
    
    print(f"\n{'='*70}")
    print(f"Plotting {material}: {len(df_mat)} samples")
    print(f"N range: {df_mat['N'].min()} - {df_mat['N'].max()}")
    print(f"R range: {df_mat['R'].min()} - {df_mat['R'].max()}")
    
    # 创建图形
    plt.rcParams.update(AM_RC)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    
    # 自定义颜色映射（从蓝色（低Ea）到红色（高Ea））
    # 使用与科学论文常用的颜色方案
    colors = ['#2166AC', '#4393C3', '#92C5DE', '#D1E5F0', 
              '#FDDBC7', '#F4A582', '#D6604D', '#B2182B']
    n_bins = 100
    cmap = LinearSegmentedColormap.from_list('ea_cmap', colors, N=n_bins)
    
    # === 高温段热力图 ===
    pivot_high = create_heatmap_matrix(df_mat, 'high')
    
    # 绘制热力图
    im1 = ax1.imshow(pivot_high.values, 
                     cmap=cmap, 
                     aspect='auto',
                     interpolation='nearest',
                     origin='lower')
    
    # 设置刻度
    ax1.set_xticks(np.arange(len(pivot_high.columns)))
    ax1.set_yticks(np.arange(len(pivot_high.index)))
    ax1.set_xticklabels(pivot_high.columns)
    ax1.set_yticklabels(pivot_high.index)
    
    # 在每个格子中标注Ea值
    for i in range(len(pivot_high.index)):
        for j in range(len(pivot_high.columns)):
            value = pivot_high.values[i, j]
            if not np.isnan(value):
                text_color = 'white' if value > pivot_high.values[~np.isnan(pivot_high.values)].mean() else 'black'
                ax1.text(j, i, f'{value:.2f}',
                        ha='center', va='center',
                        fontsize=8, color=text_color, fontweight='bold')
    
    ax1.set_xlabel('R value', fontsize=11, fontweight='normal')
    ax1.set_ylabel('N value', fontsize=11, fontweight='normal')
    ax1.set_title(f'{material} - High Temperature Region\n(1st Segment)', 
                  fontsize=12, fontweight='bold', pad=10)
    
    # 颜色条
    cbar1 = plt.colorbar(im1, ax=ax1, fraction=0.046, pad=0.04)
    cbar1.set_label('$E_a$ (eV)', fontsize=10, fontweight='normal')
    
    # === 低温段热力图 ===
    pivot_low = create_heatmap_matrix(df_mat, 'low')
    
    im2 = ax2.imshow(pivot_low.values,
                     cmap=cmap,
                     aspect='auto',
                     interpolation='nearest',
                     origin='lower')
    
    ax2.set_xticks(np.arange(len(pivot_low.columns)))
    ax2.set_yticks(np.arange(len(pivot_low.index)))
    ax2.set_xticklabels(pivot_low.columns)
    ax2.set_yticklabels(pivot_low.index)
    
    # 标注Ea值
    for i in range(len(pivot_low.index)):
        for j in range(len(pivot_low.columns)):
            value = pivot_low.values[i, j]
            if not np.isnan(value):
                text_color = 'white' if value > pivot_low.values[~np.isnan(pivot_low.values)].mean() else 'black'
                ax2.text(j, i, f'{value:.2f}',
                        ha='center', va='center',
                        fontsize=8, color=text_color, fontweight='bold')
    
    ax2.set_xlabel('R value', fontsize=11, fontweight='normal')
    ax2.set_ylabel('N value', fontsize=11, fontweight='normal')
    ax2.set_title(f'{material} - Low Temperature Region\n(Last Segment)', 
                  fontsize=12, fontweight='bold', pad=10)
    
    cbar2 = plt.colorbar(im2, ax=ax2, fraction=0.046, pad=0.04)
    cbar2.set_label('$E_a$ (eV)', fontsize=10, fontweight='normal')
    
    # 总标题
    material_name = 'Sepiolite' if material == 'S8' else 'Montmorillonite'
    fig.suptitle(f'Activation Energy ($E_a$) Distribution - {material} ({material_name})', 
                 fontsize=13, fontweight='bold', y=0.98)
    
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    
    # 保存
    png_path = OUT_DIR / f"figure4_ea_heatmap_{material}.png"
    pdf_path = OUT_DIR / f"figure4_ea_heatmap_{material}.pdf"
    
    fig.savefig(png_path, dpi=300, bbox_inches='tight')
    fig.savefig(pdf_path, bbox_inches='tight')
    plt.close(fig)
    
    print(f"\nFigure saved:")
    print(f"  {png_path}")
    print(f"  {pdf_path}")
    
    # 统计信息
    print(f"\nEa statistics:")
    print(f"  High-temp: {df_mat['Ea_high_temp'].min():.3f} - {df_mat['Ea_high_temp'].max():.3f} eV")
    print(f"  Low-temp:  {df_mat['Ea_low_temp'].min():.3f} - {df_mat['Ea_low_temp'].max():.3f} eV")

def main():
    print("Generating Ea heatmaps...")
    
    # 绘制S8
    plot_ea_heatmaps('S8')
    
    # 绘制S60
    plot_ea_heatmaps('S60')
    
    print(f"\n{'='*70}")
    print("All heatmaps generated successfully!")
    print(f"{'='*70}")

if __name__ == "__main__":
    main()
