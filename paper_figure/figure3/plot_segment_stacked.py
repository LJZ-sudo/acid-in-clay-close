# -*- coding: utf-8 -*-
"""
Figure 3: 百分比堆叠柱状图
最清晰地对比S8和S60的分段数分布差异
"""
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

OUT_DIR = Path(__file__).resolve().parent

# AM 期刊风格
AM_RC = {
    'font.family': 'sans-serif',
    'font.sans-serif': ['Arial', 'Helvetica', 'DejaVu Sans'],
    'font.size': 10,
    'axes.labelsize': 11,
    'axes.titlesize': 12,
    'legend.fontsize': 10,
}

def main():
    # 读取数据
    csv_path = OUT_DIR / "segment_counts_data.csv"
    df = pd.read_csv(csv_path)
    
    # 过滤掉分段数为0或1的样品
    df_plot = df[df['n_segments'] >= 2].copy()
    
    print(f"Valid samples: {len(df_plot)}")
    
    # 统计每种材料的分段数分布
    s8_df = df_plot[df_plot['material'] == 'S8']
    s60_df = df_plot[df_plot['material'] == 'S60']
    
    # 获取分段数范围
    all_segments = sorted(df_plot['n_segments'].unique())
    
    # 统计并计算百分比
    s8_counts = np.array([len(s8_df[s8_df['n_segments'] == n]) for n in all_segments])
    s60_counts = np.array([len(s60_df[s60_df['n_segments'] == n]) for n in all_segments])
    
    s8_pcts = s8_counts / len(s8_df) * 100
    s60_pcts = s60_counts / len(s60_df) * 100 if len(s60_df) > 0 else np.zeros_like(s60_counts)
    
    # 配色方案 - 使用Figure 1的原始颜色
    # 与Figure 1的Segment颜色对应：2段=绿，3段=橙，4段=粉
    colors_segments = {
        2: '#4CAF50',  # 绿色（Figure 1 Segment 2）
        3: '#FF9800',  # 橙色（Figure 1 Segment 3）
        4: '#E91E63'   # 粉红（Figure 1 Segment 1，主导色）
    }
    
    colors = [colors_segments[n] for n in all_segments]
    
    # 创建图形
    plt.rcParams.update(AM_RC)
    fig, ax = plt.subplots(figsize=(8, 6))
    
    # 数据准备
    materials = [f'S8 (Sepiolite)\nn = {len(s8_df)}', 
                 f'S60 (Montmorillonite)\nn = {len(s60_df)}']
    x = np.arange(len(materials))
    width = 0.65
    
    # 绘制堆叠柱状图
    bottom_s8 = 0
    bottom_s60 = 0
    
    for i, n_seg in enumerate(all_segments):
        s8_pct = s8_pcts[i]
        s60_pct = s60_pcts[i]
        
        # S8柱子
        bar1 = ax.bar(0, s8_pct, width, bottom=bottom_s8,
                     label=f'{n_seg} segments' if i == 0 else '',
                     color=colors[i], edgecolor='white', linewidth=2,
                     alpha=0.75)
        
        # S60柱子
        bar2 = ax.bar(1, s60_pct, width, bottom=bottom_s60,
                     color=colors[i], edgecolor='white', linewidth=2,
                     alpha=0.75)
        
        # 标注百分比和计数
        if s8_pct > 5:  # 只标注大于5%的
            ax.text(0, bottom_s8 + s8_pct/2, 
                   f'{n_seg} seg\n{int(s8_counts[i])} ({s8_pct:.1f}%)',
                   ha='center', va='center',
                   fontsize=10, fontweight='bold', color='white')
        
        if s60_pct > 5:
            ax.text(1, bottom_s60 + s60_pct/2,
                   f'{n_seg} seg\n{int(s60_counts[i])} ({s60_pct:.1f}%)',
                   ha='center', va='center',
                   fontsize=10, fontweight='bold', color='white')
        
        bottom_s8 += s8_pct
        bottom_s60 += s60_pct
    
    # 图例
    legend_elements = []
    for n_seg, color in colors_segments.items():
        if n_seg in all_segments:
            from matplotlib.patches import Patch
            label = f'{n_seg} segments'
            if n_seg == 4:
                label += ' (Dominant)'
            legend_elements.append(Patch(facecolor=color, edgecolor='white', 
                                        linewidth=1.5, label=label))
    
    ax.legend(handles=legend_elements, loc='upper right', 
             frameon=True, framealpha=0.95, fontsize=10,
             edgecolor='gray', fancybox=True)
    
    # 坐标轴设置
    ax.set_ylabel('Percentage of Samples (%)', fontsize=11, fontweight='normal')
    ax.set_title('Distribution of Arrhenius Segment Counts', 
                fontsize=12, fontweight='bold', pad=15)
    
    ax.set_xticks(x)
    ax.set_xticklabels(materials, fontsize=11)
    ax.set_ylim(0, 100)
    ax.set_yticks(np.arange(0, 101, 20))
    
    # 网格
    ax.grid(True, axis='y', linestyle=':', alpha=0.35, linewidth=0.8, color='gray', zorder=0)
    ax.set_axisbelow(True)
    
    plt.tight_layout()
    
    # 保存
    png_path = OUT_DIR / "figure3_segment_stacked.png"
    pdf_path = OUT_DIR / "figure3_segment_stacked.pdf"
    
    fig.savefig(png_path, dpi=300, bbox_inches='tight')
    fig.savefig(pdf_path, bbox_inches='tight')
    plt.close(fig)
    
    print(f"\nFigure saved (Stacked Bar Chart):")
    print(f"  {png_path}")
    print(f"  {pdf_path}")
    
    # 打印统计信息
    print(f"\nDistribution Statistics:")
    print(f"{'='*60}")
    for i, n in enumerate(all_segments):
        marker = " (DOMINANT)" if n == 4 else ""
        print(f"{n} segments{marker}:")
        print(f"  S8:  {int(s8_counts[i]):2d} ({s8_pcts[i]:5.1f}%)")
        print(f"  S60: {int(s60_counts[i]):2d} ({s60_pcts[i]:5.1f}%)")

if __name__ == "__main__":
    main()
