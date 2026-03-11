# -*- coding: utf-8 -*-
"""
Figure 3: 清晰版 - 圆环图（Donut Chart）
更现代、更清晰的视觉呈现
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
    
    # 统计
    s8_counts = [len(s8_df[s8_df['n_segments'] == n]) for n in all_segments]
    s60_counts = [len(s60_df[s60_df['n_segments'] == n]) for n in all_segments]
    
    # 配色方案 - 简洁明快，4段用鲜艳色突出
    colors_segments = {
        2: '#B0BEC5',  # 灰蓝（次要）
        3: '#FFB74D',  # 橙色（中等）
        4: '#E91E63'   # 粉红（主导，与Figure 1一致）
    }
    
    colors_s8 = [colors_segments[n] for n in all_segments]
    colors_s60 = [colors_segments[n] for n in all_segments]
    
    # 创建图形
    plt.rcParams.update(AM_RC)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 5))
    
    # === S8 圆环图 ===
    def make_donut(ax, counts, labels_seg, colors, title, total):
        # 外圈：数据
        wedges, texts, autotexts = ax.pie(
            counts,
            labels=None,  # 不在饼图上直接显示标签
            colors=colors,
            autopct='%1.1f%%',
            startangle=90,
            wedgeprops=dict(width=0.4, edgecolor='white', linewidth=2.5),
            textprops=dict(color='white', fontsize=11, fontweight='bold'),
            pctdistance=0.75
        )
        
        # 中心文字
        ax.text(0, 0, f'{total}\nsamples', 
               ha='center', va='center',
               fontsize=16, fontweight='bold', color='#333333')
        
        # 标题
        ax.set_title(title, fontsize=12, fontweight='bold', pad=15)
        
        return wedges, texts, autotexts
    
    wedges1, texts1, autotexts1 = make_donut(
        ax1, s8_counts, all_segments, colors_s8,
        'S8 (Sepiolite)', len(s8_df)
    )
    
    wedges2, texts2, autotexts2 = make_donut(
        ax2, s60_counts, all_segments, colors_s60,
        'S60 (Montmorillonite)', len(s60_df)
    )
    
    # 创建图例（放在图的下方，共享）
    legend_labels = []
    legend_handles = []
    
    for n, color in colors_segments.items():
        if n in all_segments:
            idx = all_segments.index(n)
            s8_c = s8_counts[idx]
            s60_c = s60_counts[idx]
            
            label = f'{n} segments: S8={s8_c}, S60={s60_c}'
            
            # 如果是4段，加粗显示
            if n == 4:
                label = f'{n} segments (Dominant): S8={s8_c}, S60={s60_c}'
            
            # 创建图例项
            from matplotlib.patches import Patch
            legend_handles.append(Patch(facecolor=color, edgecolor='white', linewidth=1.5))
            legend_labels.append(label)
    
    # 在图的底部添加图例
    fig.legend(legend_handles, legend_labels,
              loc='lower center', ncol=1,
              frameon=True, framealpha=0.95,
              fontsize=10, edgecolor='gray',
              bbox_to_anchor=(0.5, -0.05))
    
    # 添加总标题
    fig.suptitle('Distribution of Arrhenius Segment Counts', 
                 fontsize=13, fontweight='bold', y=0.98)
    
    plt.tight_layout(rect=[0, 0.08, 1, 0.96])
    
    # 保存
    png_path = OUT_DIR / "figure3_segment_distribution.png"
    pdf_path = OUT_DIR / "figure3_segment_distribution.pdf"
    
    fig.savefig(png_path, dpi=300, bbox_inches='tight')
    fig.savefig(pdf_path, bbox_inches='tight')
    plt.close(fig)
    
    print(f"\nFigure saved (Donut Chart):")
    print(f"  {png_path}")
    print(f"  {pdf_path}")
    
    # 打印统计信息
    print(f"\nDistribution Statistics:")
    print(f"{'='*60}")
    for n in all_segments:
        idx = all_segments.index(n)
        s8_c = s8_counts[idx]
        s60_c = s60_counts[idx]
        s8_pct = s8_c / len(s8_df) * 100
        s60_pct = s60_c / len(s60_df) * 100 if len(s60_df) > 0 else 0
        
        marker = " ★" if n == 4 else ""
        print(f"{n} segments{marker}: S8 {s8_c:2d} ({s8_pct:5.1f}%), S60 {s60_c:2d} ({s60_pct:5.1f}%)")

if __name__ == "__main__":
    main()
