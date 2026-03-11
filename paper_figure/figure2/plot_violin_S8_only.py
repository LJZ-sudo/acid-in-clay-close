# -*- coding: utf-8 -*-
"""
Figure 2 (S8 only): Arrhenius 变化点温度分布 - 仅 S8 限域材料
输出: figure2_violin_distribution_S8_only.png/pdf, figure2_violin_S8_data.csv
"""
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.stats import gaussian_kde

OUT_DIR = Path(__file__).resolve().parent

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


def plot_violin_manual(ax, data, position, color, width=0.4):
    """手动绘制小提琴图"""
    if len(data) < 3:
        ax.scatter([position] * len(data), data,
                   color=color, s=40, alpha=0.6, zorder=3)
        return

    try:
        kde = gaussian_kde(data, bw_method='scott')
        y_range = np.linspace(data.min() - 5, data.max() + 5, 100)
        density = kde(y_range)
        density = density / density.max() * width

        ax.fill_betweenx(y_range, position - density, position + density,
                        color=color, alpha=0.35, zorder=1)
        ax.plot(position - density, y_range, color=color, linewidth=1.2, alpha=0.85, zorder=2)
        ax.plot(position + density, y_range, color=color, linewidth=1.2, alpha=0.85, zorder=2)
    except Exception:
        pass

    np.random.seed(42)
    jitter = np.random.uniform(-0.06, 0.06, size=len(data))
    ax.scatter(position + jitter, data,
               color=color, s=28, alpha=0.55,
               edgecolors='white', linewidths=0.5, zorder=3)

    median = np.median(data)
    q1, q3 = np.percentile(data, [25, 75])
    ax.hlines(median, position - width * 0.45, position + width * 0.45,
             color='darkred', linewidth=2.5, zorder=4, alpha=0.9)
    ax.hlines([q1, q3], position - width * 0.25, position + width * 0.25,
             color='black', linewidth=1.5, zorder=4, alpha=0.6)


def main():
    csv_path = OUT_DIR / "breakpoints_data.csv"
    df = pd.read_csv(csv_path)

    # 仅保留 S8
    df_s8 = df[df['material'] == 'S8'].copy()
    df_plot = df_s8[df_s8['breakpoint_index'] <= 3].copy()

    print(f"Loaded {len(df)} breakpoints, S8 only: {len(df_plot)}\n")

    # 保存 S8 数据到 CSV
    out_csv = OUT_DIR / "figure2_violin_S8_data.csv"
    df_plot.to_csv(out_csv, index=False, float_format='%.4f')
    print(f"S8 data saved: {out_csv}\n")

    # 统计
    print("=" * 60)
    print("S8 Breakpoint Temperature Distribution")
    print("=" * 60)
    for bp_idx in [1, 2, 3]:
        temps = df_plot[df_plot['breakpoint_index'] == bp_idx]['temperature_K'].values
        if len(temps) > 0:
            print(f"  BP{bp_idx}: n={len(temps):2d}, "
                  f"mean={temps.mean():6.1f} K, std={temps.std():4.1f} K, "
                  f"range=[{temps.min():5.1f}, {temps.max():5.1f}] K")

    # 绘图
    plt.rcParams.update(AM_RC)
    fig, ax = plt.subplots(figsize=(7, 5.5))

    color_s8 = '#E91E63'
    positions = {1: 1, 2: 2, 3: 3}
    width = 0.4

    for bp_idx in [1, 2, 3]:
        temps = df_plot[df_plot['breakpoint_index'] == bp_idx]['temperature_K'].values
        if len(temps) > 0:
            plot_violin_manual(ax, temps, positions[bp_idx], color_s8, width=width)

    ax.set_xlim(0.4, 3.6)
    ax.set_ylim(195, 295)
    ax.set_xticks([1, 2, 3])
    ax.set_xticklabels(['BP1', 'BP2', 'BP3'])
    ax.set_xlabel('Arrhenius Breakpoint Index', fontsize=12, fontweight='bold')
    ax.set_ylabel('Temperature (K)', fontsize=12, fontweight='bold')
    ax.grid(True, axis='y', linestyle=':', alpha=0.3, linewidth=0.8, color='gray')
    ax.set_axisbelow(True)

    from matplotlib.patches import Patch
    legend_elements = [Patch(facecolor=color_s8, alpha=0.6, label='S8 (Sepiolite)')]
    ax.legend(handles=legend_elements, loc='upper right',
             frameon=True, framealpha=0.95, fontsize=10,
             edgecolor='gray', fancybox=False)

    ax.set_title('Temperature Distribution of Arrhenius Breakpoints (S8)', fontsize=13, fontweight='bold', pad=15)

    stats_lines = []
    for bp_idx in [1, 2, 3]:
        temps = df_plot[df_plot['breakpoint_index'] == bp_idx]['temperature_K'].values
        if len(temps) > 0:
            stats_lines.append(f'BP{bp_idx}: {temps.mean():.0f} +/- {temps.std():.0f} K (n={len(temps)})')
    stats_text = '\n'.join(stats_lines)
    ax.text(0.02, 0.02, stats_text,
            transform=ax.transAxes, fontsize=9,
            verticalalignment='bottom',
            bbox=dict(boxstyle='round,pad=0.5', facecolor='white', edgecolor='gray', alpha=0.9))

    plt.tight_layout()

    png_path = OUT_DIR / "figure2_violin_distribution_S8_only.png"
    pdf_path = OUT_DIR / "figure2_violin_distribution_S8_only.pdf"
    fig.savefig(png_path, dpi=300, bbox_inches='tight')
    fig.savefig(pdf_path, bbox_inches='tight')
    plt.close(fig)

    print(f"\nFigure saved:")
    print(f"  {png_path}")
    print(f"  {pdf_path}")
    print(f"Data saved: {out_csv}")


if __name__ == "__main__":
    main()
