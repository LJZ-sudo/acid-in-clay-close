# -*- coding: utf-8 -*-
"""
Figure 3: Arrhenius 分段数分布
展示 S8 和 S60 样品的分段数统计
"""
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

OUT_DIR = Path(__file__).resolve().parent

# AM 期刊风格（与 Figure 1/2 一致）
AM_RC = {
    'font.family': 'sans-serif',
    'font.sans-serif': ['Arial', 'Helvetica', 'DejaVu Sans'],
    'font.size': 10,
    'axes.labelsize': 12,
    'axes.titlesize': 13,
    'xtick.labelsize': 11,
    'ytick.labelsize': 10,
    'legend.fontsize': 10,
    'axes.linewidth': 1.2,
}

def main():
    # 读取数据
    csv_path = OUT_DIR / "segment_counts_data.csv"
    df = pd.read_csv(csv_path)
    
    print(f"Loaded {len(df)} samples\n")
    
    # 过滤掉分段数为0或1的样品（拟合失败或质量差）
    df_plot = df[df['n_segments'] >= 2].copy()
    
    print(f"After filtering (n_segments >= 2): {len(df_plot)} samples")
    print(f"  S8:  {len(df_plot[df_plot['material']=='S8'])} samples")
    print(f"  S60: {len(df_plot[df_plot['material']=='S60'])} samples\n")
    
    # 统计每种材料的分段数分布
    s8_df = df_plot[df_plot['material'] == 'S8']
    s60_df = df_plot[df_plot['material'] == 'S60']
    
    # 获取分段数范围
    all_segments = sorted(df_plot['n_segments'].unique())
    
    # 统计
    s8_counts = [len(s8_df[s8_df['n_segments'] == n]) for n in all_segments]
    s60_counts = [len(s60_df[s60_df['n_segments'] == n]) for n in all_segments]
    
    # 绘图
    plt.rcParams.update(AM_RC)
    fig, ax = plt.subplots(figsize=(8, 6))
    
    # 配色（与 Figure 2 一致）
    color_s8 = '#E91E63'   # 粉红
    color_s60 = '#2196F3'  # 蓝色
    
    # 柱状图设置
    x = np.arange(len(all_segments))
    width = 0.35
    
    # 绘制柱状图
    bars1 = ax.bar(x - width/2, s8_counts, width, 
                   label='S8 (Sepiolite)', 
                   color=color_s8, alpha=0.8,
                   edgecolor='white', linewidth=1.2)
    bars2 = ax.bar(x + width/2, s60_counts, width, 
                   label='S60 (Montmorillonite)', 
                   color=color_s60, alpha=0.8,
                   edgecolor='white', linewidth=1.2)
    
    # 在柱子上标注数量
    def add_value_labels(bars):
        for bar in bars:
            height = bar.get_height()
            if height > 0:
                ax.text(bar.get_x() + bar.get_width()/2., height,
                       f'{int(height)}',
                       ha='center', va='bottom',
                       fontsize=10, fontweight='bold')
    
    add_value_labels(bars1)
    add_value_labels(bars2)
    
    # 坐标轴设置
    ax.set_xlabel('Number of Arrhenius Segments', fontsize=12, fontweight='bold')
    ax.set_ylabel('Number of Samples', fontsize=12, fontweight='bold')
    ax.set_title('Distribution of Arrhenius Segment Counts', 
                fontsize=13, fontweight='bold', pad=15)
    
    # X轴刻度
    ax.set_xticks(x)
    ax.set_xticklabels([str(n) for n in all_segments])
    
    # Y轴范围
    max_count = max(max(s8_counts), max(s60_counts))
    ax.set_ylim(0, max_count * 1.15)
    
    # 网格
    ax.grid(True, axis='y', linestyle=':', alpha=0.3, linewidth=0.8, color='gray')
    ax.set_axisbelow(True)
    
    # 图例
    ax.legend(loc='upper left', frameon=True, framealpha=0.95,
             fontsize=10, edgecolor='gray')
    
    # 添加统计信息框
    s8_total = len(s8_df)
    s60_total = len(s60_df)
    total = s8_total + s60_total
    
    # 计算主要分段数
    s8_mode = s8_df['n_segments'].mode()[0] if len(s8_df) > 0 else 0
    s60_mode = s60_df['n_segments'].mode()[0] if len(s60_df) > 0 else 0
    
    s8_mode_count = len(s8_df[s8_df['n_segments'] == s8_mode])
    s60_mode_count = len(s60_df[s60_df['n_segments'] == s60_mode])
    
    stats_text = f'Total: {total} samples\n'
    stats_text += f'S8:  {s8_total} samples (dominant: {s8_mode} seg, {s8_mode_count}/{s8_total})\n'
    stats_text += f'S60: {s60_total} samples (dominant: {s60_mode} seg, {s60_mode_count}/{s60_total})'
    
    ax.text(0.98, 0.98, stats_text,
           transform=ax.transAxes,
           fontsize=9,
           verticalalignment='top',
           horizontalalignment='right',
           bbox=dict(boxstyle='round,pad=0.5',
                    facecolor='white',
                    edgecolor='gray',
                    alpha=0.95))
    
    plt.tight_layout()
    
    # 保存
    png_path = OUT_DIR / "figure3_segment_distribution.png"
    pdf_path = OUT_DIR / "figure3_segment_distribution.pdf"
    
    fig.savefig(png_path, dpi=300, bbox_inches='tight')
    fig.savefig(pdf_path, bbox_inches='tight')
    plt.close(fig)
    
    print(f"\n{'='*70}")
    print("Figure saved:")
    print(f"  {png_path}")
    print(f"  {pdf_path}")
    print(f"{'='*70}")
    
    # 打印统计信息
    print(f"\nDistribution Statistics:")
    print(f"{'='*70}")
    for n_seg in all_segments:
        s8_n = len(s8_df[s8_df['n_segments'] == n_seg])
        s60_n = len(s60_df[s60_df['n_segments'] == n_seg])
        s8_pct = s8_n / s8_total * 100 if s8_total > 0 else 0
        s60_pct = s60_n / s60_total * 100 if s60_total > 0 else 0
        print(f"{n_seg} segments: S8 {s8_n:2d} ({s8_pct:5.1f}%), S60 {s60_n:2d} ({s60_pct:5.1f}%)")
    
    # 生成详细统计CSV（包含百分比）
    detailed_stats = []
    for n_seg in range(2, 5):  # 2, 3, 4 segments
        s8_n = len(s8_df[s8_df['n_segments'] == n_seg])
        s60_n = len(s60_df[s60_df['n_segments'] == n_seg])
        s8_pct = s8_n / s8_total * 100 if s8_total > 0 else 0
        s60_pct = s60_n / s60_total * 100 if s60_total > 0 else 0
        
        detailed_stats.append({
            'N_Segments': n_seg,
            'S8_Count': s8_n,
            'S8_Percentage': s8_pct,
            'S60_Count': s60_n,
            'S60_Percentage': s60_pct,
            'Total_Count': s8_n + s60_n
        })
    
    stats_df = pd.DataFrame(detailed_stats)
    stats_csv = OUT_DIR / "figure3_detailed_statistics.csv"
    stats_df.to_csv(stats_csv, index=False, float_format='%.2f')
    print(f"\nDetailed statistics saved to: {stats_csv}")

if __name__ == "__main__":
    main()
