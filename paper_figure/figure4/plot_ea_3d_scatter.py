# -*- coding: utf-8 -*-
"""
Figure 4: Ea 3D散点图
X=R值, Y=N值, Z=Ea (eV)
更适合稀疏数据的可视化
"""
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

OUT_DIR = Path(__file__).resolve().parent

# AM 期刊风格
AM_RC = {
    'font.family': 'sans-serif',
    'font.sans-serif': ['Arial', 'Helvetica', 'DejaVu Sans'],
    'font.size': 10,
    'axes.labelsize': 11,
    'axes.titlesize': 12,
}

def plot_3d_scatter(material='S8'):
    """
    为单个材料绘制3D散点图（高温和低温）
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
    print(f"Plotting {material} 3D Scatter: {len(df_mat)} samples")
    
    # 创建图形（更紧凑的布局）
    plt.rcParams.update(AM_RC)
    fig = plt.figure(figsize=(14, 6))
    
    # === 高温段3D散点图 ===
    ax1 = fig.add_subplot(121, projection='3d')
    
    # 数据
    x = df_mat['R'].values
    y = df_mat['N'].values
    z = df_mat['Ea_high_temp'].values
    
    # 颜色映射（用Ea值来着色）
    scatter1 = ax1.scatter(x, y, z, 
                          c=z, cmap='RdYlBu_r',  # 红→黄→蓝（反转）
                          s=200, alpha=0.8,
                          edgecolors='black', linewidths=1.5,
                          depthshade=True)
    
    # 添加从底部到点的垂直线
    for xi, yi, zi in zip(x, y, z):
        ax1.plot([xi, xi], [yi, yi], [0, zi], 
                'gray', alpha=0.3, linewidth=1, linestyle='--')
    
    ax1.set_xlabel('R value', fontsize=11, labelpad=10)
    ax1.set_ylabel('N value', fontsize=11, labelpad=10)
    ax1.set_zlabel('$E_a$ (eV)', fontsize=11, labelpad=10)
    ax1.set_title(f'{material} - High Temperature\n(1st Segment)', 
                  fontsize=12, fontweight='bold', pad=15)
    
    # 设置视角
    ax1.view_init(elev=20, azim=45)
    
    # 颜色条
    cbar1 = fig.colorbar(scatter1, ax=ax1, shrink=0.6, pad=0.1)
    cbar1.set_label('$E_a$ (eV)', fontsize=10)
    
    # 网格
    ax1.grid(True, alpha=0.3)
    
    # === 低温段3D散点图 ===
    ax2 = fig.add_subplot(122, projection='3d')
    
    z_low = df_mat['Ea_low_temp'].values
    
    scatter2 = ax2.scatter(x, y, z_low,
                          c=z_low, cmap='RdYlBu_r',
                          s=200, alpha=0.8,
                          edgecolors='black', linewidths=1.5,
                          depthshade=True)
    
    # 垂直线
    for xi, yi, zi in zip(x, y, z_low):
        ax2.plot([xi, xi], [yi, yi], [0, zi],
                'gray', alpha=0.3, linewidth=1, linestyle='--')
    
    ax2.set_xlabel('R value', fontsize=11, labelpad=10)
    ax2.set_ylabel('N value', fontsize=11, labelpad=10)
    ax2.set_zlabel('$E_a$ (eV)', fontsize=11, labelpad=10)
    ax2.set_title(f'{material} - Low Temperature\n(Last Segment)',
                  fontsize=12, fontweight='bold', pad=15)
    
    ax2.view_init(elev=20, azim=45)
    
    cbar2 = fig.colorbar(scatter2, ax=ax2, shrink=0.6, pad=0.1)
    cbar2.set_label('$E_a$ (eV)', fontsize=10)
    
    ax2.grid(True, alpha=0.3)
    
    # 总标题
    material_name = 'Sepiolite' if material == 'S8' else 'Montmorillonite'
    fig.suptitle(f'Activation Energy ($E_a$) Distribution - {material} ({material_name})',
                 fontsize=13, fontweight='bold', y=0.97)
    
    # 添加样本数信息
    fig.text(0.5, 0.02, f'Total samples: {len(df_mat)}', 
            ha='center', fontsize=9, style='italic', color='#555555')
    
    plt.tight_layout(rect=[0, 0.04, 1, 0.95])
    
    # 保存
    png_path = OUT_DIR / f"figure4_ea_3d_scatter_{material}.png"
    pdf_path = OUT_DIR / f"figure4_ea_3d_scatter_{material}.pdf"
    
    fig.savefig(png_path, dpi=300, bbox_inches='tight')
    fig.savefig(pdf_path, bbox_inches='tight')
    plt.close(fig)
    
    print(f"\nFigure saved (3D Scatter):")
    print(f"  {png_path}")
    print(f"  {pdf_path}")

def main():
    print("Generating 3D Scatter Plots...")
    
    # 绘制S8
    plot_3d_scatter('S8')
    
    # 绘制S60
    plot_3d_scatter('S60')
    
    print(f"\n{'='*70}")
    print("All 3D scatter plots generated successfully!")
    print(f"{'='*70}")

if __name__ == "__main__":
    main()
