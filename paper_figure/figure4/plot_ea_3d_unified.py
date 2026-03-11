# -*- coding: utf-8 -*-
"""
Figure 4: 统一的3D Ea图
X = R值, Y = N值, Z = T（温度），颜色 = Ea
每个材料只需一张图，显示所有segment的数据
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

def plot_3d_unified(material='S8'):
    """
    为单个材料绘制统一的3D图
    X=R, Y=N, Z=T, 颜色=Ea
    """
    # 读取数据
    csv_path = OUT_DIR / "all_segments_data.csv"
    df = pd.read_csv(csv_path)
    
    # 筛选特定材料
    df_mat = df[df['material'] == material].copy()
    
    if len(df_mat) == 0:
        print(f"No data found for {material}")
        return
    
    print(f"\n{'='*70}")
    print(f"Plotting {material} Unified 3D: {len(df_mat)} segment data points")
    print(f"From {df_mat['sample_id'].nunique()} samples")
    
    # 创建图形
    plt.rcParams.update(AM_RC)
    fig = plt.figure(figsize=(10, 8))
    ax = fig.add_subplot(111, projection='3d')
    
    # 数据
    x = df_mat['R'].values
    y = df_mat['N'].values
    z = df_mat['T_mid_K'].values
    colors = df_mat['Ea_eV'].values
    
    # 颜色映射（红→黄→蓝，红=高Ea，蓝=低Ea）
    scatter = ax.scatter(x, y, z,
                        c=colors, cmap='RdYlBu_r',
                        s=120, alpha=0.8,
                        edgecolors='black', linewidths=1.0,
                        depthshade=True)
    
    # 添加从底部到点的垂直线（可选，可能会很密集）
    # 如果数据点太多，可以注释掉
    if len(df_mat) < 100:  # 只在数据点<100时显示垂直线
        for xi, yi, zi in zip(x, y, z):
            ax.plot([xi, xi], [yi, yi], [z.min(), zi],
                   'gray', alpha=0.15, linewidth=0.5, linestyle=':')
    
    # 坐标轴标签
    ax.set_xlabel('R value', fontsize=12, labelpad=12, fontweight='normal')
    ax.set_ylabel('N value', fontsize=12, labelpad=12, fontweight='normal')
    ax.set_zlabel('Temperature (K)', fontsize=12, labelpad=12, fontweight='normal')
    
    # 标题
    material_name = 'Sepiolite' if material == 'S8' else 'Montmorillonite'
    ax.set_title(f'{material} ({material_name})\n$E_a$ Distribution in N-R-T Space',
                fontsize=13, fontweight='bold', pad=20)
    
    # 设置视角
    ax.view_init(elev=25, azim=45)
    
    # 颜色条
    cbar = fig.colorbar(scatter, ax=ax, shrink=0.6, pad=0.12)
    cbar.set_label('Activation Energy $E_a$ (eV)', 
                  fontsize=11, fontweight='normal')
    
    # 网格
    ax.grid(True, alpha=0.25, linewidth=0.5)
    
    # 设置背景颜色
    ax.xaxis.pane.fill = False
    ax.yaxis.pane.fill = False
    ax.zaxis.pane.fill = False
    
    # 添加统计信息
    info_text = f'Samples: {df_mat["sample_id"].nunique()}\n'
    info_text += f'Segments: {len(df_mat)}\n'
    info_text += f'T: {z.min():.0f}-{z.max():.0f} K\n'
    info_text += f'$E_a$: {colors.min():.2f}-{colors.max():.2f} eV'
    
    fig.text(0.02, 0.98, info_text,
            transform=fig.transFigure,
            fontsize=9, verticalalignment='top',
            bbox=dict(boxstyle='round,pad=0.5', facecolor='white',
                     edgecolor='gray', alpha=0.9))
    
    plt.tight_layout()
    
    # 保存
    png_path = OUT_DIR / f"figure4_ea_3d_unified_{material}.png"
    pdf_path = OUT_DIR / f"figure4_ea_3d_unified_{material}.pdf"
    
    fig.savefig(png_path, dpi=300, bbox_inches='tight')
    fig.savefig(pdf_path, bbox_inches='tight')
    plt.close(fig)
    
    print(f"\nFigure saved (Unified 3D):")
    print(f"  {png_path}")
    print(f"  {pdf_path}")
    
    # 统计信息
    print(f"\nData statistics:")
    print(f"  Samples: {df_mat['sample_id'].nunique()}")
    print(f"  Segments: {len(df_mat)}")
    print(f"  R range: {x.min():.0f} - {x.max():.0f}")
    print(f"  N range: {y.min():.0f} - {y.max():.0f}")
    print(f"  T range: {z.min():.1f} - {z.max():.1f} K")
    print(f"  Ea range: {colors.min():.3f} - {colors.max():.3f} eV")

def main():
    print("Generating Unified 3D Ea Plots...")
    
    # 绘制S8
    plot_3d_unified('S8')
    
    # 绘制S60
    plot_3d_unified('S60')
    
    print(f"\n{'='*70}")
    print("All unified 3D plots generated successfully!")
    print("Now each material has ONE 3D plot showing all segments!")
    print(f"{'='*70}")

if __name__ == "__main__":
    main()
