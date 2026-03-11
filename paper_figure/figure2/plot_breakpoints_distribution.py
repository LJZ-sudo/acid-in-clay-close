# -*- coding: utf-8 -*-
"""
Figure 2: 多样品变化点温度分布直方图
S8 和 S60 样品的 Arrhenius 变化点温度分布
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
    'font.size': 9,
    'axes.labelsize': 10,
    'axes.titlesize': 10,
    'xtick.labelsize': 9,
    'ytick.labelsize': 9,
    'legend.fontsize': 8,
    'axes.linewidth': 1.0,
}

def main():
    # 读取数据
    csv_path = OUT_DIR / "breakpoints_data.csv"
    df = pd.read_csv(csv_path)
    
    print(f"Loaded {len(df)} breakpoints")
    print(f"Materials: {df['material'].unique()}")
    
    # 分离 S8 和 S60
    s8_temps = df[df['material'] == 'S8']['temperature_K'].values
    s60_temps = df[df['material'] == 'S60']['temperature_K'].values
    all_temps = df['temperature_K'].values
    
    print(f"\nS8: {len(s8_temps)} breakpoints")
    print(f"S60: {len(s60_temps)} breakpoints")
    print(f"Total: {len(all_temps)} breakpoints")
    
    # 绘图
    plt.rcParams.update(AM_RC)
    fig, ax = plt.subplots(figsize=(6, 4.5))
    
    # 设置 bins（温度范围 180-280 K）
    bins = np.arange(180, 285, 5)  # 每 5 K 一个 bin
    
    # 绘制叠加直方图
    ax.hist([s8_temps, s60_temps], bins=bins, 
            label=['S8 (Sepiolite)', 'S60 (Montmorillonite)'],
            color=['#E91E63', '#2196F3'],  # 粉红和蓝色
            alpha=0.7,
            edgecolor='black',
            linewidth=0.8)
    
    # 高亮 215 K 附近的区域（205-225 K）
    ax.axvspan(205, 225, alpha=0.15, color='orange', zorder=0, 
               label='215 K region')
    
    # 添加垂直虚线标记 215 K
    ax.axvline(x=215, color='orange', linestyle='--', linewidth=1.5, 
               alpha=0.8, label='215 K')
    
    # 坐标轴设置
    ax.set_xlabel('Temperature (K)', fontsize=10)
    ax.set_ylabel('Count', fontsize=10)
    ax.set_xlim(180, 280)
    
    # 网格
    ax.grid(True, linestyle=':', alpha=0.3, linewidth=0.8, color='gray')
    
    # 图例
    ax.legend(loc='upper right', frameon=True, framealpha=0.95, 
              fontsize=8, edgecolor='gray')
    
    # 标注样品数量
    text_str = f'Total: {len(all_temps)} breakpoints\nS8: {len(s8_temps)}, S60: {len(s60_temps)}'
    ax.text(0.02, 0.98, text_str, transform=ax.transAxes,
            fontsize=8, verticalalignment='top',
            bbox=dict(boxstyle='round,pad=0.5', facecolor='white', 
                     edgecolor='gray', alpha=0.9))
    
    # 标注 215 K 附近的数量
    near_215 = len(df[(df['temperature_K'] >= 205) & (df['temperature_K'] <= 225)])
    ax.text(215, ax.get_ylim()[1] * 0.85, 
            f'{near_215} breakpoints\n(205-225 K)',
            ha='center', fontsize=7.5, color='#FF6F00',
            bbox=dict(boxstyle='round,pad=0.3', facecolor='white', 
                     edgecolor='orange', linewidth=1, alpha=0.9))
    
    plt.tight_layout()
    
    # 保存图像
    fig.savefig(OUT_DIR / "figure2_breakpoints_distribution.png", dpi=300, bbox_inches='tight')
    fig.savefig(OUT_DIR / "figure2_breakpoints_distribution.pdf", bbox_inches='tight')
    plt.close(fig)
    
    print(f"\nFigure saved to: {OUT_DIR / 'figure2_breakpoints_distribution.png'}")
    
    # 生成统计 CSV
    stats_data = []
    
    # 按温度区间统计
    for i in range(len(bins) - 1):
        T_low, T_high = bins[i], bins[i+1]
        s8_count = len(s8_temps[(s8_temps >= T_low) & (s8_temps < T_high)])
        s60_count = len(s60_temps[(s60_temps >= T_low) & (s60_temps < T_high)])
        total_count = s8_count + s60_count
        
        stats_data.append({
            'T_range_K': f'{T_low}-{T_high}',
            'T_center_K': (T_low + T_high) / 2,
            'S8_count': s8_count,
            'S60_count': s60_count,
            'Total_count': total_count
        })
    
    stats_df = pd.DataFrame(stats_data)
    stats_csv = OUT_DIR / "figure2_distribution_stats.csv"
    stats_df.to_csv(stats_csv, index=False)
    print(f"Statistics saved to: {stats_csv}")
    
    # 打印关键统计
    print(f"\n{'='*60}")
    print("Key Statistics:")
    print(f"{'='*60}")
    print(f"Peak region (highest count):")
    peak_bin = stats_df.loc[stats_df['Total_count'].idxmax()]
    print(f"  {peak_bin['T_range_K']} K: {peak_bin['Total_count']} breakpoints")
    
    print(f"\n215 K region (205-225 K):")
    region_215 = stats_df[(stats_df['T_center_K'] >= 205) & (stats_df['T_center_K'] <= 225)]
    print(f"  Total: {region_215['Total_count'].sum()} breakpoints")
    print(f"  S8: {region_215['S8_count'].sum()}")
    print(f"  S60: {region_215['S60_count'].sum()}")

if __name__ == "__main__":
    main()
