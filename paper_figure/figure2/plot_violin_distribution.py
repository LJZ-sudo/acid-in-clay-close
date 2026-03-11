# -*- coding: utf-8 -*-
"""
Figure 2: 变化点温度分布（小提琴图版本）
清晰展示 BP1/BP2/BP3 的温度分布特征
"""
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.stats import gaussian_kde

OUT_DIR = Path(__file__).resolve().parent

# AM 期刊风格（调大字体）
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

def plot_violin_manual(ax, data, position, color, width=0.35):
    """手动绘制小提琴图"""
    if len(data) < 3:
        # 数据太少，只画散点
        ax.scatter([position] * len(data), data, 
                  color=color, s=40, alpha=0.6, zorder=3)
        return
    
    # 使用KDE估计分布
    try:
        kde = gaussian_kde(data, bw_method='scott')
        y_range = np.linspace(data.min() - 5, data.max() + 5, 100)
        density = kde(y_range)
        
        # 归一化密度到宽度
        density = density / density.max() * width
        
        # 绘制左右对称的小提琴
        ax.fill_betweenx(y_range, position - density, position + density,
                         color=color, alpha=0.3, zorder=1)
        ax.plot(position - density, y_range, color=color, linewidth=1.2, alpha=0.8, zorder=2)
        ax.plot(position + density, y_range, color=color, linewidth=1.2, alpha=0.8, zorder=2)
    except:
        pass
    
    # 叠加数据点（带抖动）
    jitter = np.random.uniform(-0.05, 0.05, size=len(data))
    ax.scatter(position + jitter, data, 
              color=color, s=25, alpha=0.5, 
              edgecolors='white', linewidths=0.5, zorder=3)
    
    # 添加中位数线和四分位数线
    median = np.median(data)
    q1, q3 = np.percentile(data, [25, 75])
    
    ax.hlines(median, position - width*0.4, position + width*0.4,
             color='darkred', linewidth=2.5, zorder=4, alpha=0.9)
    ax.hlines([q1, q3], position - width*0.2, position + width*0.2,
             color='black', linewidth=1.5, zorder=4, alpha=0.6)

def main():
    # 读取数据
    csv_path = OUT_DIR / "breakpoints_data.csv"
    df = pd.read_csv(csv_path)
    
    print(f"Loaded {len(df)} breakpoints\n")
    
    # 筛选前3个变化点
    df_plot = df[df['breakpoint_index'] <= 3].copy()
    
    # 统计信息
    print("="*70)
    print("Breakpoint Temperature Distribution Statistics")
    print("="*70)
    for bp_idx in [1, 2, 3]:
        print(f"\nBP{bp_idx}:")
        for mat in ['S8', 'S60']:
            temps = df_plot[(df_plot['material'] == mat) & 
                           (df_plot['breakpoint_index'] == bp_idx)]['temperature_K'].values
            if len(temps) > 0:
                print(f"  {mat:3s}: n={len(temps):2d}, "
                      f"range=[{temps.min():5.1f}, {temps.max():5.1f}] K, "
                      f"mean={temps.mean():6.1f} K, "
                      f"median={np.median(temps):6.1f} K, "
                      f"std={temps.std():4.1f} K")
    
    # 绘图
    plt.rcParams.update(AM_RC)
    fig, ax = plt.subplots(figsize=(9, 6))
    
    # 配色
    color_s8 = '#E91E63'   # 粉红
    color_s60 = '#2196F3'  # 蓝色
    
    # X轴位置
    bp_positions = {
        1: {'S8': 1, 'S60': 1.4},
        2: {'S8': 2.5, 'S60': 2.9},
        3: {'S8': 4, 'S60': 4.4}
    }
    
    # 绘制每个变化点的分布
    for bp_idx in [1, 2, 3]:
        for mat, color in [('S8', color_s8), ('S60', color_s60)]:
            temps = df_plot[(df_plot['material'] == mat) & 
                           (df_plot['breakpoint_index'] == bp_idx)]['temperature_K'].values
            
            if len(temps) > 0:
                position = bp_positions[bp_idx][mat]
                plot_violin_manual(ax, temps, position, color, width=0.35)
    
    # 坐标轴设置（去除n标注）
    ax.set_xlim(0.4, 5.0)
    ax.set_ylim(195, 295)
    
    # X轴刻度和标签（简化，只保留BP1/BP2/BP3）
    ax.set_xticks([1.2, 2.7, 4.2])
    ax.set_xticklabels(['BP1', 'BP2', 'BP3'])
    ax.set_xlabel('Arrhenius Breakpoint Index', fontsize=12, fontweight='bold')
    
    # Y轴
    ax.set_ylabel('Temperature (K)', fontsize=12, fontweight='bold')
    
    # 网格
    ax.grid(True, axis='y', linestyle=':', alpha=0.3, linewidth=0.8, color='gray')
    ax.set_axisbelow(True)
    
    # 添加BP分隔线
    for x in [1.95, 3.45]:
        ax.axvline(x, color='gray', linestyle='--', linewidth=1, alpha=0.3, zorder=0)
    
    # 图例（增大字体）
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor=color_s8, alpha=0.6, label='S8 (Sepiolite)'),
        Patch(facecolor=color_s60, alpha=0.6, label='S60 (Montmorillonite)')
    ]
    ax.legend(handles=legend_elements, loc='upper right', 
             frameon=True, framealpha=0.95, fontsize=10, 
             edgecolor='gray', fancybox=False)
    
    # 标题（增大字体）
    ax.set_title('Temperature Distribution of Arrhenius Breakpoints',
                fontsize=13, fontweight='bold', pad=15)
    
    # 添加统计摘要文本框（去除n，增大字体）
    stats_lines = []
    for bp_idx in [1, 2, 3]:
        s8_temps = df_plot[(df_plot['material'] == 'S8') & 
                          (df_plot['breakpoint_index'] == bp_idx)]['temperature_K'].values
        s60_temps = df_plot[(df_plot['material'] == 'S60') & 
                           (df_plot['breakpoint_index'] == bp_idx)]['temperature_K'].values
        
        if len(s8_temps) > 0 and len(s60_temps) > 0:
            stats_lines.append(f'BP{bp_idx}: S8 {s8_temps.mean():.0f}±{s8_temps.std():.0f} K, '
                             f'S60 {s60_temps.mean():.0f}±{s60_temps.std():.0f} K')
    
    stats_text = '\n'.join(stats_lines)
    ax.text(0.02, 0.02, stats_text,
           transform=ax.transAxes,
           fontsize=8.5,
           verticalalignment='bottom',
           bbox=dict(boxstyle='round,pad=0.5',
                    facecolor='white',
                    edgecolor='gray',
                    alpha=0.9))
    
    plt.tight_layout()
    
    # 保存
    png_path = OUT_DIR / "figure2_violin_distribution.png"
    pdf_path = OUT_DIR / "figure2_violin_distribution.pdf"
    
    fig.savefig(png_path, dpi=300, bbox_inches='tight')
    fig.savefig(pdf_path, bbox_inches='tight')
    plt.close(fig)
    
    print(f"\n{'='*70}")
    print("Figure saved:")
    print(f"  {png_path}")
    print(f"  {pdf_path}")
    print(f"{'='*70}")
    
    # 生成详细统计CSV
    stats_data = []
    for bp_idx in [1, 2, 3]:
        for mat in ['S8', 'S60']:
            temps = df_plot[(df_plot['material'] == mat) & 
                           (df_plot['breakpoint_index'] == bp_idx)]['temperature_K'].values
            if len(temps) > 0:
                stats_data.append({
                    'BP_Index': bp_idx,
                    'Material': mat,
                    'N': len(temps),
                    'Min_K': temps.min(),
                    'Q1_K': np.percentile(temps, 25),
                    'Median_K': np.median(temps),
                    'Mean_K': temps.mean(),
                    'Q3_K': np.percentile(temps, 75),
                    'Max_K': temps.max(),
                    'Std_K': temps.std(),
                    'Range_K': temps.max() - temps.min()
                })
    
    stats_df = pd.DataFrame(stats_data)
    stats_csv = OUT_DIR / "figure2_violin_statistics.csv"
    stats_df.to_csv(stats_csv, index=False, float_format='%.2f')
    print(f"\nStatistics saved to: {stats_csv}")
    
    # 打印分布特征
    print(f"\n{'='*70}")
    print("Distribution Characteristics:")
    print(f"{'='*70}")
    for bp_idx in [1, 2, 3]:
        print(f"\nBP{bp_idx}:")
        s8_temps = df_plot[(df_plot['material'] == 'S8') & 
                          (df_plot['breakpoint_index'] == bp_idx)]['temperature_K'].values
        s60_temps = df_plot[(df_plot['material'] == 'S60') & 
                           (df_plot['breakpoint_index'] == bp_idx)]['temperature_K'].values
        
        if len(s8_temps) > 0:
            print(f"  S8  Distribution: {s8_temps.min():.1f} - {s8_temps.max():.1f} K "
                  f"(span: {s8_temps.max()-s8_temps.min():.1f} K)")
        if len(s60_temps) > 0:
            print(f"  S60 Distribution: {s60_temps.min():.1f} - {s60_temps.max():.1f} K "
                  f"(span: {s60_temps.max()-s60_temps.min():.1f} K)")

if __name__ == "__main__":
    main()
