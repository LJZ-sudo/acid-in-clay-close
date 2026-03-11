# -*- coding: utf-8 -*-
"""
Figure 3: 双饼图 - Arrhenius 分段数分布
更直观地展示S8和S60样品的分段数比例关系
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
    'legend.fontsize': 9.5,
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
    
    # 统计S8
    s8_counts = [len(s8_df[s8_df['n_segments'] == n]) for n in all_segments]
    s8_labels = [f'{n} seg' for n in all_segments]
    
    # 统计S60
    s60_counts = [len(s60_df[s60_df['n_segments'] == n]) for n in all_segments]
    s60_labels = [f'{n} seg' for n in all_segments]
    
    # 配色方案（使用渐变色，4段用最鲜艳的颜色突出）
    # 2段=浅色, 3段=中等, 4段=鲜艳（突出主导）
    colors_base = ['#FFB6C1', '#FFA07A', '#FF6347']  # 粉红系渐变
    colors_s8 = []
    colors_s60 = []
    
    for n in all_segments:
        if n == 2:
            colors_s8.append('#FFCDD2')  # 浅粉
            colors_s60.append('#BBDEFB')  # 浅蓝
        elif n == 3:
            colors_s8.append('#EF9A9A')  # 中粉
            colors_s60.append('#90CAF9')  # 中蓝
        elif n == 4:
            colors_s8.append('#E91E63')  # 鲜艳粉红（与Figure 1一致）
            colors_s60.append('#2196F3')  # 鲜艳蓝色
    
    # 突出4段（explode效果）
    explode_s8 = [0.1 if n == 4 else 0 for n in all_segments]
    explode_s60 = [0.1 if n == 4 else 0 for n in all_segments]
    
    # 创建图形
    plt.rcParams.update(AM_RC)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5.5))
    
    # === S8 饼图 ===
    def autopct_format(pct, allvals):
        absolute = int(np.round(pct/100.*np.sum(allvals)))
        return f'{absolute}\n({pct:.1f}%)'
    
    wedges1, texts1, autotexts1 = ax1.pie(
        s8_counts,
        labels=s8_labels,
        colors=colors_s8,
        autopct=lambda pct: autopct_format(pct, s8_counts),
        startangle=90,
        explode=explode_s8,
        wedgeprops=dict(edgecolor='white', linewidth=2, antialiased=True),
        textprops=dict(color='black', fontsize=10, fontweight='normal'),
        shadow=False
    )
    
    # 设置百分比文字样式（白色粗体）
    for autotext in autotexts1:
        autotext.set_color('white')
        autotext.set_fontweight('bold')
        autotext.set_fontsize(10)
    
    ax1.set_title(f'S8 (Sepiolite)\nTotal: {len(s8_df)} samples', 
                  fontsize=12, fontweight='bold', pad=15)
    
    # === S60 饼图 ===
    wedges2, texts2, autotexts2 = ax2.pie(
        s60_counts,
        labels=s60_labels,
        colors=colors_s60,
        autopct=lambda pct: autopct_format(pct, s60_counts),
        startangle=90,
        explode=explode_s60,
        wedgeprops=dict(edgecolor='white', linewidth=2, antialiased=True),
        textprops=dict(color='black', fontsize=10, fontweight='normal'),
        shadow=False
    )
    
    # 设置百分比文字样式
    for autotext in autotexts2:
        autotext.set_color('white')
        autotext.set_fontweight('bold')
        autotext.set_fontsize(10)
    
    ax2.set_title(f'S60 (Montmorillonite)\nTotal: {len(s60_df)} samples', 
                  fontsize=12, fontweight='bold', pad=15)
    
    # 添加总标题
    fig.suptitle('Distribution of Arrhenius Segment Counts', 
                 fontsize=13, fontweight='bold', y=0.98)
    
    # 添加注释说明
    note_text = 'Note: 4 segments is the dominant pattern for both materials'
    fig.text(0.5, 0.02, note_text, 
             ha='center', fontsize=9.5, style='italic', color='#555555')
    
    plt.tight_layout(rect=[0, 0.04, 1, 0.96])
    
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
    print("S8 (Sepiolite):")
    for n, count in zip(all_segments, s8_counts):
        pct = count / len(s8_df) * 100
        print(f"  {n} segments: {count:2d} ({pct:5.1f}%)")
    
    print("\nS60 (Montmorillonite):")
    for n, count in zip(all_segments, s60_counts):
        pct = count / len(s60_df) * 100
        print(f"  {n} segments: {count:2d} ({pct:5.1f}%)")
    
    print(f"\nKey finding: 4 segments is dominant")
    print(f"  S8:  {s8_counts[all_segments.index(4)]}/{len(s8_df)} = {s8_counts[all_segments.index(4)]/len(s8_df)*100:.1f}%")
    print(f"  S60: {s60_counts[all_segments.index(4)]}/{len(s60_df)} = {s60_counts[all_segments.index(4)]/len(s60_df)*100:.1f}%")

if __name__ == "__main__":
    main()
