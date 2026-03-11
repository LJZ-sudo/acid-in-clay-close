# -*- coding: utf-8 -*-
"""
Figure 3 V2: 改进的 Arrhenius 分段数分布图
更美观、更清晰的视觉呈现
"""
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

OUT_DIR = Path(__file__).resolve().parent

# AM 期刊风格（与 Figure 1/2 一致）
AM_RC = {
    'font.family': 'sans-serif',
    'font.sans-serif': ['Arial', 'Helvetica', 'DejaVu Sans'],
    'font.size': 10,
    'axes.labelsize': 11,
    'axes.titlesize': 12,
    'xtick.labelsize': 10,
    'ytick.labelsize': 10,
    'legend.fontsize': 9,
    'axes.linewidth': 1.0,
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
    
    # 统计
    s8_counts = [len(s8_df[s8_df['n_segments'] == n]) for n in all_segments]
    s60_counts = [len(s60_df[s60_df['n_segments'] == n]) for n in all_segments]
    
    s8_total = len(s8_df)
    s60_total = len(s60_df)
    
    # 计算百分比
    s8_pcts = [c / s8_total * 100 if s8_total > 0 else 0 for c in s8_counts]
    s60_pcts = [c / s60_total * 100 if s60_total > 0 else 0 for c in s60_counts]
    
    # 绘图
    plt.rcParams.update(AM_RC)
    fig, ax = plt.subplots(figsize=(7, 5))
    
    # 配色 - 使用与Figure 1/2一致的颜色
    color_s8 = '#E91E63'   # 粉红 (与Figure 1的Segment 1一致)
    color_s60 = '#2196F3'  # 蓝色
    
    # 柱状图设置
    x = np.arange(len(all_segments))
    width = 0.38
    
    # 绘制柱状图（添加阴影效果）
    bars1 = ax.bar(x - width/2, s8_counts, width, 
                   label='S8 (Sepiolite)', 
                   color=color_s8, alpha=0.85,
                   edgecolor='white', linewidth=1.5,
                   zorder=3)
    bars2 = ax.bar(x + width/2, s60_counts, width, 
                   label='S60 (Montmorillonite)', 
                   color=color_s60, alpha=0.85,
                   edgecolor='white', linewidth=1.5,
                   zorder=3)
    
    # 在柱子上标注：计数 + 百分比
    def add_value_labels(bars, counts, pcts):
        for bar, count, pct in zip(bars, counts, pcts):
            height = bar.get_height()
            if height > 0:
                # 主标签：计数
                ax.text(bar.get_x() + bar.get_width()/2., height + 0.5,
                       f'{int(count)}',
                       ha='center', va='bottom',
                       fontsize=11, fontweight='bold', color='black')
                # 副标签：百分比
                ax.text(bar.get_x() + bar.get_width()/2., height/2,
                       f'{pct:.0f}%',
                       ha='center', va='center',
                       fontsize=8.5, color='white', fontweight='bold',
                       zorder=4)
    
    add_value_labels(bars1, s8_counts, s8_pcts)
    add_value_labels(bars2, s60_counts, s60_pcts)
    
    # 坐标轴设置
    ax.set_xlabel('Number of Arrhenius Segments', fontsize=11, fontweight='normal')
    ax.set_ylabel('Number of Samples', fontsize=11, fontweight='normal')
    
    # X轴刻度
    ax.set_xticks(x)
    ax.set_xticklabels([f'{n}' for n in all_segments], fontsize=10)
    
    # Y轴范围
    max_count = max(max(s8_counts), max(s60_counts))
    ax.set_ylim(0, max_count * 1.2)
    
    # 网格
    ax.grid(True, axis='y', linestyle=':', alpha=0.35, linewidth=0.8, color='gray', zorder=0)
    ax.set_axisbelow(True)
    
    # 图例（位置优化）
    ax.legend(loc='upper left', frameon=True, framealpha=0.95,
             fontsize=9.5, edgecolor='gray', fancybox=True, shadow=True)
    
    # 添加关键信息标注（突出4段是主导）
    # 找到4段的位置
    if 4 in all_segments:
        idx_4 = all_segments.index(4)
        # 添加高亮背景
        rect = Rectangle((idx_4 - 0.5, 0), 1, ax.get_ylim()[1],
                        facecolor='yellow', alpha=0.12, zorder=1,
                        edgecolor='orange', linewidth=1.5, linestyle='--')
        ax.add_patch(rect)
        
        # 添加文字说明
        ax.text(idx_4, ax.get_ylim()[1] * 0.95,
               'Dominant',
               ha='center', va='top',
               fontsize=9, fontweight='bold', color='#FF6F00',
               bbox=dict(boxstyle='round,pad=0.3', facecolor='white',
                        edgecolor='#FF6F00', linewidth=1.2, alpha=0.9))
    
    # 添加总样本数信息
    info_text = f'Total: {s8_total + s60_total} samples'
    info_text += f'\nS8: {s8_total}  |  S60: {s60_total}'
    
    ax.text(0.98, 0.65, info_text,
           transform=ax.transAxes,
           fontsize=9,
           verticalalignment='top',
           horizontalalignment='right',
           bbox=dict(boxstyle='round,pad=0.5',
                    facecolor='white',
                    edgecolor='gray',
                    linewidth=1.0,
                    alpha=0.95))
    
    plt.tight_layout()
    
    # 保存
    png_path = OUT_DIR / "figure3_segment_distribution.png"
    pdf_path = OUT_DIR / "figure3_segment_distribution.pdf"
    
    fig.savefig(png_path, dpi=300, bbox_inches='tight')
    fig.savefig(pdf_path, bbox_inches='tight')
    plt.close(fig)
    
    print(f"\nFigure saved:")
    print(f"  {png_path}")
    print(f"  {pdf_path}")
    
    # 打印统计信息
    print(f"\nDistribution Statistics:")
    print(f"{'='*60}")
    for n_seg, s8_c, s8_p, s60_c, s60_p in zip(all_segments, s8_counts, s8_pcts, s60_counts, s60_pcts):
        print(f"{n_seg} segments: S8 {s8_c:2d} ({s8_p:5.1f}%), S60 {s60_c:2d} ({s60_p:5.1f}%)")

if __name__ == "__main__":
    main()
