# -*- coding: utf-8 -*-
"""
Figure 3b: Breakpoint Temperature Distribution (Violin Plot)
Updated: Times New Roman Bold, Origin-matching style
"""
import sys, io, os
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
if sys.platform == 'win32':
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass

from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.stats import gaussian_kde

OUT_DIR = Path(__file__).resolve().parent
PAPER_FIG_DIR = OUT_DIR.parent
FIG3_DIR = PAPER_FIG_DIR / "figure3_agent_analysis"

# ── Times New Roman Bold style ──
def setup_style():
    plt.rcParams.update({
        'font.family': 'serif',
        'font.serif': ['Times New Roman', 'DejaVu Serif'],
        'font.size': 12,
        # Note: don't set font.weight globally — breaks STIX math cdot glyph
        'mathtext.fontset': 'stix',
        'axes.labelsize': 14,
        'axes.titlesize': 15,
        'axes.titleweight': 'bold',
        'axes.linewidth': 1.3,
        'axes.labelweight': 'bold',
        'axes.facecolor': 'white',
        'xtick.labelsize': 12,
        'ytick.labelsize': 12,
        'xtick.direction': 'in',
        'ytick.direction': 'in',
        'xtick.major.width': 1.1,
        'ytick.major.width': 1.1,
        'xtick.major.size': 5,
        'ytick.major.size': 5,
        'legend.fontsize': 10,
        'legend.frameon': True,
        'legend.framealpha': 0.95,
        'legend.edgecolor': '#999',
        'grid.alpha': 0.3,
        'grid.linewidth': 0.8,
        'grid.linestyle': ':',
        'grid.color': 'gray',
        'savefig.dpi': 300,
        'savefig.bbox': 'tight',
        'figure.facecolor': 'white',
    })


def plot_violin_manual(ax, data, position, color, width=0.35):
    """Draw manual violin plot."""
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
                         color=color, alpha=0.3, zorder=1)
        ax.plot(position - density, y_range, color=color, linewidth=1.2, alpha=0.8, zorder=2)
        ax.plot(position + density, y_range, color=color, linewidth=1.2, alpha=0.8, zorder=2)
    except Exception:
        pass

    # Jittered scatter
    jitter = np.random.uniform(-0.05, 0.05, size=len(data))
    ax.scatter(position + jitter, data,
               color=color, s=25, alpha=0.5,
               edgecolors='white', linewidths=0.5, zorder=3)

    # Median and quartile lines
    median = np.median(data)
    q1, q3 = np.percentile(data, [25, 75])

    ax.hlines(median, position - width * 0.4, position + width * 0.4,
              color='darkred', linewidth=2.5, zorder=4, alpha=0.9)
    ax.hlines([q1, q3], position - width * 0.2, position + width * 0.2,
              color='black', linewidth=1.5, zorder=4, alpha=0.6)


def main():
    setup_style()

    # Read data
    csv_path = OUT_DIR / "breakpoints_data.csv"
    df = pd.read_csv(csv_path)
    print(f"Loaded {len(df)} breakpoints")

    df_plot = df[df['breakpoint_index'] <= 3].copy()

    # Statistics
    print("\n" + "=" * 60)
    print("Breakpoint Temperature Distribution")
    print("=" * 60)
    for bp_idx in [1, 2, 3]:
        print(f"\nBP{bp_idx}:")
        for mat in ['S8', 'S60']:
            temps = df_plot[(df_plot['material'] == mat) &
                            (df_plot['breakpoint_index'] == bp_idx)]['temperature_K'].values
            if len(temps) > 0:
                print(f"  {mat:3s}: n={len(temps):2d}, "
                      f"mean={temps.mean():.1f} +/- {temps.std():.1f} K, "
                      f"range=[{temps.min():.1f}, {temps.max():.1f}]")

    # ── Plot ──
    fig, ax = plt.subplots(figsize=(9, 6))

    color_s8 = '#E91E63'
    color_s60 = '#2196F3'

    bp_positions = {
        1: {'S8': 1, 'S60': 1.4},
        2: {'S8': 2.5, 'S60': 2.9},
        3: {'S8': 4, 'S60': 4.4}
    }

    for bp_idx in [1, 2, 3]:
        for mat, color in [('S8', color_s8), ('S60', color_s60)]:
            temps = df_plot[(df_plot['material'] == mat) &
                            (df_plot['breakpoint_index'] == bp_idx)]['temperature_K'].values
            if len(temps) > 0:
                position = bp_positions[bp_idx][mat]
                plot_violin_manual(ax, temps, position, color, width=0.35)

    # Axis
    ax.set_xlim(0.4, 5.0)
    ax.set_ylim(195, 295)
    ax.set_xticks([1.2, 2.7, 4.2])
    ax.set_xticklabels(['BP1', 'BP2', 'BP3'], fontsize=12, fontweight='bold')
    ax.set_xlabel('Arrhenius Breakpoint Index', fontsize=14, fontweight='bold')
    ax.set_ylabel('Temperature (K)', fontsize=14, fontweight='bold')

    # Grid
    ax.grid(True, axis='y')
    ax.set_axisbelow(True)

    # BP separators
    for x in [1.95, 3.45]:
        ax.axvline(x, color='gray', linestyle='--', linewidth=1, alpha=0.3, zorder=0)

    # Legend
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor=color_s8, alpha=0.6, label='S8 (Sepiolite)'),
        Patch(facecolor=color_s60, alpha=0.6, label='S60 (Montmorillonite)')
    ]
    ax.legend(handles=legend_elements, loc='upper right',
              frameon=True, framealpha=0.95, fontsize=10,
              edgecolor='gray', fancybox=False)

    # Title
    ax.set_title('Temperature Distribution of Arrhenius Breakpoints',
                 fontsize=15, fontweight='bold', pad=15)

    # Stats text box
    stats_lines = []
    for bp_idx in [1, 2, 3]:
        s8_temps = df_plot[(df_plot['material'] == 'S8') &
                           (df_plot['breakpoint_index'] == bp_idx)]['temperature_K'].values
        s60_temps = df_plot[(df_plot['material'] == 'S60') &
                            (df_plot['breakpoint_index'] == bp_idx)]['temperature_K'].values
        if len(s8_temps) > 0 and len(s60_temps) > 0:
            stats_lines.append(
                f'BP{bp_idx}: S8 {s8_temps.mean():.0f}\u00b1{s8_temps.std():.0f} K, '
                f'S60 {s60_temps.mean():.0f}\u00b1{s60_temps.std():.0f} K'
            )

    stats_text = '\n'.join(stats_lines)
    ax.text(0.02, 0.02, stats_text,
            transform=ax.transAxes, fontsize=10,
            verticalalignment='bottom',
            bbox=dict(boxstyle='round,pad=0.5', facecolor='white',
                      edgecolor='gray', alpha=0.9))

    # Bold tick labels
    for label in ax.get_xticklabels() + ax.get_yticklabels():
        label.set_fontweight('bold')

    # Panel label
    fig.text(0.01, 0.95, '(b)', fontsize=18, fontweight='bold', fontfamily='serif')

    plt.tight_layout()

    # Save
    for path in [FIG3_DIR / "figure3b_violin_distribution.png",
                 FIG3_DIR / "figure3b_violin_distribution.pdf"]:
        if str(path).endswith('.png'):
            fig.savefig(str(path), dpi=300, bbox_inches='tight', facecolor='white')
        else:
            fig.savefig(str(path), bbox_inches='tight', facecolor='white')
        print(f"Saved: {path}")

    # Also save to figure2 directory
    for path in [OUT_DIR / "figure2_violin_distribution.png",
                 OUT_DIR / "figure2_violin_distribution.pdf"]:
        if str(path).endswith('.png'):
            fig.savefig(str(path), dpi=300, bbox_inches='tight', facecolor='white')
        else:
            fig.savefig(str(path), bbox_inches='tight', facecolor='white')
        print(f"Saved: {path}")

    plt.close(fig)
    print("\nDone: Figure 3b (Violin distribution) with Times New Roman Bold")


if __name__ == "__main__":
    main()
