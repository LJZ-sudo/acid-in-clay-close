# -*- coding: utf-8 -*-
"""
Figure 2 V2: 多样品变化点温度分布（改进版）
使用条带图 + 箱线图 + 统计信息，展示真实数据
"""
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

OUT_DIR = Path(__file__).resolve().parent

# AM 期刊风格
AM_RC = {
    'font.family': 'sans-serif',
    'font.sans-serif': ['Arial', 'Helvetica', 'DejaVu Sans'],
    'font.size': 9,
    'axes.labelsize': 10,
    'axes.titlesize': 10,
    'xtick.labelsize': 9,
    'ytick.labelsize': 9,
    'legend.fontsize': 8,
    'axes.linewidth': 1.0,
}

def add_jitter(x, jitter_amount=0.15):
    """添加随机抖动避免点重叠"""
    return x + np.random.uniform(-jitter_amount, jitter_amount, size=len(x))

def main():
    # 读取数据
    csv_path = OUT_DIR / "breakpoints_data.csv"
    df = pd.read_csv(csv_path)
    
    print(f"Loaded {len(df)} breakpoints")
    
    # 分离 S8 和 S60
    s8_df = df[df['material'] == 'S8']
    s60_df = df[df['material'] == 'S60']
    
    # 按变化点序号分组统计
    print("\nBreakpoints by index:")
    for mat in ['S8', 'S60']:
        mat_df = df[df['material'] == mat]
        print(f"\n{mat}:")
        for idx in sorted(mat_df['breakpoint_index'].unique()):
            temps = mat_df[mat_df['breakpoint_index'] == idx]['temperature_K']
            print(f"  BP{idx}: n={len(temps)}, mean={temps.mean():.1f}K, std={temps.std():.1f}K")
    
    # 绘图
    plt.rcParams.update(AM_RC)
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.5), sharey=True)
    
    materials = ['S8', 'S60']
    colors = ['#E91E63', '#2196F3']  # 粉红、蓝色
    material_names = ['S8 (Sepiolite)', 'S60 (Montmorillonite)']
    
    for idx, (ax, mat, color, name) in enumerate(zip(axes, materials, colors, material_names)):
        mat_df = df[df['material'] == mat]
        temps = mat_df['temperature_K'].values
        
        # 1. 绘制所有数据点（条带图，带抖动）
        x_positions = add_jitter(np.ones(len(temps)), jitter_amount=0.25)
        ax.scatter(x_positions, temps, 
                  color=color, s=30, alpha=0.4, 
                  edgecolors='white', linewidths=0.5,
                  zorder=2, label=f'{len(temps)} breakpoints')
        
        # 2. 添加箱线图统计
        bp = ax.boxplot([temps], positions=[1], widths=0.5,
                        patch_artist=True,
                        boxprops=dict(facecolor=color, alpha=0.3, linewidth=1.5, edgecolor=color),
                        whiskerprops=dict(color=color, linewidth=1.5),
                        capprops=dict(color=color, linewidth=1.5),
                        medianprops=dict(color='darkred', linewidth=2),
                        flierprops=dict(marker='o', markerfacecolor='red', markersize=5, alpha=0.5),
                        showmeans=True,
                        meanprops=dict(marker='D', markerfacecolor='orange', markersize=6),
                        zorder=3)
        
        # 3. 高亮 215 K 区域（205-225 K）
        ax.axhspan(205, 225, alpha=0.15, color='orange', zorder=0)
        ax.axhline(y=215, color='orange', linestyle='--', linewidth=1.5, 
                  alpha=0.8, zorder=1, label='215 K')
        
        # 4. 统计信息
        near_215 = mat_df[(mat_df['temperature_K'] >= 205) & (mat_df['temperature_K'] <= 225)]
        n_near_215 = len(near_215)
        pct_near_215 = n_near_215 / len(temps) * 100
        
        stats_text = f'{name}\n'
        stats_text += f'n = {len(temps)} breakpoints\n'
        stats_text += f'Mean: {temps.mean():.1f} K\n'
        stats_text += f'Median: {np.median(temps):.1f} K\n'
        stats_text += f'Range: {temps.min():.1f}-{temps.max():.1f} K\n'
        stats_text += f'\n215 K region:\n'
        stats_text += f'{n_near_215} ({pct_near_215:.1f}%)'
        
        ax.text(0.98, 0.02, stats_text,
               transform=ax.transAxes,
               fontsize=7.5,
               verticalalignment='bottom',
               horizontalalignment='right',
               bbox=dict(boxstyle='round,pad=0.5', 
                        facecolor='white', 
                        edgecolor=color,
                        alpha=0.9,
                        linewidth=1.5))
        
        # 5. 坐标轴设置
        ax.set_xlim(0.3, 1.7)
        ax.set_ylim(195, 290)
        ax.set_xticks([1])
        ax.set_xticklabels([mat])
        ax.set_xlabel('')
        ax.grid(True, axis='y', linestyle=':', alpha=0.3, linewidth=0.8, color='gray')
        
        # 图例
        if idx == 0:
            ax.legend(loc='upper left', frameon=True, framealpha=0.9, 
                     fontsize=7, edgecolor='gray')
    
    # 左侧 Y 轴标签
    axes[0].set_ylabel('Breakpoint Temperature (K)', fontsize=10)
    
    # 总标题
    fig.suptitle('Arrhenius Breakpoint Distribution: S8 vs S60', 
                fontsize=11, fontweight='bold', y=0.98)
    
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    
    # 保存
    fig.savefig(OUT_DIR / "figure2_breakpoints_v2.png", dpi=300, bbox_inches='tight')
    fig.savefig(OUT_DIR / "figure2_breakpoints_v2.pdf", bbox_inches='tight')
    plt.close(fig)
    
    print(f"\n{'='*60}")
    print("Figure saved:")
    print(f"  {OUT_DIR / 'figure2_breakpoints_v2.png'}")
    print(f"  {OUT_DIR / 'figure2_breakpoints_v2.pdf'}")
    print(f"{'='*60}")
    
    # 生成详细统计
    summary_stats = []
    for mat in ['S8', 'S60']:
        mat_df = df[df['material'] == mat]
        temps = mat_df['temperature_K'].values
        near_215 = len(mat_df[(mat_df['temperature_K'] >= 205) & (mat_df['temperature_K'] <= 225)])
        
        summary_stats.append({
            'Material': mat,
            'N_samples': mat_df['sample_id'].nunique(),
            'N_breakpoints': len(temps),
            'Mean_K': temps.mean(),
            'Median_K': np.median(temps),
            'Std_K': temps.std(),
            'Min_K': temps.min(),
            'Max_K': temps.max(),
            'N_near_215K': near_215,
            'Pct_near_215K': near_215 / len(temps) * 100
        })
    
    summary_df = pd.DataFrame(summary_stats)
    summary_csv = OUT_DIR / "figure2_summary_statistics.csv"
    summary_df.to_csv(summary_csv, index=False, float_format='%.2f')
    print(f"\nSummary statistics saved to: {summary_csv}")
    
    print("\nSummary:")
    print(summary_df.to_string(index=False))

if __name__ == "__main__":
    main()
