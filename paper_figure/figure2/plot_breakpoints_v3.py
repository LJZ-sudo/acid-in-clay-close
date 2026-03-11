# -*- coding: utf-8 -*-
"""
Figure 2 V3: 按变化点序号分组的温度分布
更符合物理规律：BP1（高温段边界）、BP2（中温段边界）、BP3（低温段边界）
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

def add_jitter(arr, amount=0.15):
    """添加抖动"""
    return arr + np.random.uniform(-amount, amount, size=len(arr))

def main():
    # 读取数据
    csv_path = OUT_DIR / "breakpoints_data.csv"
    df = pd.read_csv(csv_path)
    
    print(f"Loaded {len(df)} breakpoints\n")
    
    # 筛选前 3 个变化点（大部分样品有 3 个）
    df_plot = df[df['breakpoint_index'] <= 3].copy()
    
    # 绘图
    plt.rcParams.update(AM_RC)
    fig, ax = plt.subplots(figsize=(8, 5))
    
    # 配色
    colors_s8 = ['#E91E63', '#E91E63', '#E91E63']  # S8 统一粉红
    colors_s60 = ['#2196F3', '#2196F3', '#2196F3']  # S60 统一蓝色
    
    # X 轴位置
    positions = {
        'S8': {1: 1, 2: 2, 3: 3},
        'S60': {1: 1.3, 2: 2.3, 3: 3.3}
    }
    
    # 绘制每个组的数据
    for mat, color_base in [('S8', '#E91E63'), ('S60', '#2196F3')]:
        mat_df = df_plot[df_plot['material'] == mat]
        
        for bp_idx in [1, 2, 3]:
            bp_data = mat_df[mat_df['breakpoint_index'] == bp_idx]['temperature_K'].values
            
            if len(bp_data) == 0:
                continue
            
            x_pos = positions[mat][bp_idx]
            
            # 绘制数据点（带抖动）
            x_jitter = add_jitter(np.full(len(bp_data), x_pos), amount=0.08)
            label = mat if bp_idx == 1 else None  # 只在第一个组添加图例
            ax.scatter(x_jitter, bp_data,
                      color=color_base, s=35, alpha=0.5,
                      edgecolors='white', linewidths=0.5,
                      zorder=2, label=label)
            
            # 添加均值线
            mean_val = bp_data.mean()
            ax.hlines(mean_val, x_pos - 0.12, x_pos + 0.12,
                     color=color_base, linewidth=2.5, zorder=3, alpha=0.8)
            
            # 添加误差棒（标准差）
            std_val = bp_data.std()
            ax.errorbar(x_pos, mean_val, yerr=std_val,
                       fmt='none', ecolor=color_base, 
                       linewidth=1.5, capsize=4, capthick=1.5,
                       alpha=0.6, zorder=3)
            
            # 标注数量
            ax.text(x_pos, 290, f'n={len(bp_data)}',
                   ha='center', va='bottom', fontsize=7,
                   color=color_base, fontweight='bold')
    
    # 高亮 215 K 区域
    ax.axhspan(205, 225, alpha=0.12, color='orange', zorder=0,
              label='215 K region (±10 K)')
    ax.axhline(y=215, color='orange', linestyle='--', linewidth=1.8,
              alpha=0.7, zorder=1)
    
    # 坐标轴设置
    ax.set_xlim(0.5, 3.8)
    ax.set_ylim(195, 295)
    
    # X 轴刻度
    ax.set_xticks([1.15, 2.15, 3.15])
    ax.set_xticklabels(['BP1\n(High-T boundary)', 
                        'BP2\n(Mid-T boundary)', 
                        'BP3\n(Low-T boundary)'],
                       fontsize=9)
    ax.set_xlabel('Breakpoint Index (Segment Boundary)', fontsize=10, fontweight='bold')
    
    # Y 轴
    ax.set_ylabel('Temperature (K)', fontsize=10, fontweight='bold')
    
    # 网格
    ax.grid(True, axis='y', linestyle=':', alpha=0.3, linewidth=0.8, color='gray')
    
    # 图例
    ax.legend(loc='upper right', frameon=True, framealpha=0.95,
             fontsize=8.5, edgecolor='gray', ncol=1)
    
    # 标题
    ax.set_title('Arrhenius Breakpoint Distribution by Segment Boundary',
                fontsize=11, fontweight='bold', pad=15)
    
    # 添加统计文本框
    stats_text = 'Statistics:\n'
    stats_text += f'S8:  n={len(df[df["material"]=="S8"])} breakpoints\n'
    stats_text += f'S60: n={len(df[df["material"]=="S60"])} breakpoints\n'
    stats_text += f'\n215 K region: {len(df[(df["temperature_K"]>=205) & (df["temperature_K"]<=225)])} total'
    
    ax.text(0.02, 0.98, stats_text,
           transform=ax.transAxes,
           fontsize=7.5,
           verticalalignment='top',
           bbox=dict(boxstyle='round,pad=0.5',
                    facecolor='white',
                    edgecolor='gray',
                    alpha=0.9))
    
    plt.tight_layout()
    
    # 保存
    fig.savefig(OUT_DIR / "figure2_breakpoints_by_index.png", dpi=300, bbox_inches='tight')
    fig.savefig(OUT_DIR / "figure2_breakpoints_by_index.pdf", bbox_inches='tight')
    plt.close(fig)
    
    print(f"Figure saved:")
    print(f"  {OUT_DIR / 'figure2_breakpoints_by_index.png'}")
    print(f"  {OUT_DIR / 'figure2_breakpoints_by_index.pdf'}")
    
    # 统计分析
    print(f"\n{'='*70}")
    print("Breakpoint Statistics by Index:")
    print(f"{'='*70}")
    
    for bp_idx in [1, 2, 3]:
        print(f"\nBreakpoint {bp_idx}:")
        for mat in ['S8', 'S60']:
            temps = df_plot[(df_plot['material'] == mat) & 
                           (df_plot['breakpoint_index'] == bp_idx)]['temperature_K'].values
            if len(temps) > 0:
                near_215 = len(temps[(temps >= 205) & (temps <= 225)])
                print(f"  {mat:3s}: n={len(temps):2d}, "
                      f"mean={temps.mean():6.1f}K ± {temps.std():4.1f}K, "
                      f"range=[{temps.min():5.1f}, {temps.max():5.1f}], "
                      f"near_215K: {near_215} ({near_215/len(temps)*100:.1f}%)")
    
    # 生成CSV统计
    stats_data = []
    for bp_idx in [1, 2, 3]:
        for mat in ['S8', 'S60']:
            temps = df_plot[(df_plot['material'] == mat) & 
                           (df_plot['breakpoint_index'] == bp_idx)]['temperature_K'].values
            if len(temps) > 0:
                near_215 = len(temps[(temps >= 205) & (temps <= 225)])
                stats_data.append({
                    'Breakpoint_Index': bp_idx,
                    'Material': mat,
                    'N': len(temps),
                    'Mean_K': temps.mean(),
                    'Std_K': temps.std(),
                    'Median_K': np.median(temps),
                    'Min_K': temps.min(),
                    'Max_K': temps.max(),
                    'N_near_215K': near_215,
                    'Pct_near_215K': near_215 / len(temps) * 100
                })
    
    stats_df = pd.DataFrame(stats_data)
    stats_csv = OUT_DIR / "figure2_by_index_statistics.csv"
    stats_df.to_csv(stats_csv, index=False, float_format='%.2f')
    print(f"\nStatistics saved to: {stats_csv}")

if __name__ == "__main__":
    main()
