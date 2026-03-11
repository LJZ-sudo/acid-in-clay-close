# -*- coding: utf-8 -*-
"""
Figure 3a: S8-3-9-3 Arrhenius 4-Segment Plot
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
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

SAMPLE_ID = "S8-3-9-3"
RESULTS_DIR = Path(__file__).resolve().parent.parent / "output" / "phase1_results"
OUT_DIR = Path(__file__).resolve().parent
FIG3_DIR = OUT_DIR / "figure3_agent_analysis"

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
        'grid.alpha': 0.4,
        'grid.linewidth': 0.8,
        'grid.linestyle': ':',
        'grid.color': 'gray',
        'savefig.dpi': 300,
        'savefig.bbox': 'tight',
        'figure.facecolor': 'white',
    })


def main():
    setup_style()

    # Read data
    json_path = RESULTS_DIR / f"{SAMPLE_ID}_analysis_result.json"
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    temperatures_K = np.array(data['temperatures'])
    conductivity_S_cm = np.array(data['conductivity_values'])
    segments = data['arrhenius']['segments']

    print(f"Sample: {SAMPLE_ID}")
    print(f"Data points: {len(temperatures_K)}")
    print(f"Temperature range: {temperatures_K.min():.1f} - {temperatures_K.max():.1f} K")
    print(f"Segments: {len(segments)}")

    # Unit conversion
    inv_T = 1000.0 / temperatures_K
    T_C = temperatures_K - 273.15
    conductivity_mS_cm = conductivity_S_cm * 1000.0
    log_sigma = np.log10(conductivity_mS_cm)

    # Prepare fit data
    fit_data = []
    for idx, seg in enumerate(segments, 1):
        Ea_eV = seg['Ea_eV']
        ln_sigma0 = seg['ln_sigma0']
        T_low, T_high = seg['temp_range_K']
        r_squared = seg['r_squared']
        print(f"  Segment {idx}: T=[{T_low:.1f}, {T_high:.1f}] K, Ea={Ea_eV:.3f} eV, R2={r_squared:.4f}")
        fit_data.append({
            'segment': idx, 'Ea_eV': Ea_eV, 'ln_sigma0': ln_sigma0,
            'T_low_K': T_low, 'T_high_K': T_high, 'r_squared': r_squared
        })

    # ── Plot ──
    fig, ax1 = plt.subplots(figsize=(5.6, 4.2))

    # Segment colors (same as original)
    colors_seg = ['#E91E63', '#4CAF50', '#FF9800', '#9C27B0']

    # Data points
    ax1.scatter(inv_T, log_sigma, color='#808080', s=32, zorder=2,
                edgecolors='white', linewidths=0.5, label='Data', alpha=0.5)

    # Fit lines
    x_plot = np.linspace(inv_T.min(), inv_T.max(), 200)
    breakpoints_x = []
    label_positions = []
    y_range = log_sigma.max() - log_sigma.min()

    for idx, seg_info in enumerate(fit_data):
        Ea_eV = seg_info['Ea_eV']
        ln_sigma0 = seg_info['ln_sigma0']
        T_low = seg_info['T_low_K']
        T_high = seg_info['T_high_K']
        r_squared = seg_info['r_squared']

        inv_T_lo = 1000.0 / T_high
        inv_T_hi = 1000.0 / T_low
        x_seg = x_plot[(x_plot >= inv_T_lo) & (x_plot <= inv_T_hi)]
        if len(x_seg) < 2:
            x_seg = np.linspace(inv_T_lo, inv_T_hi, 50)

        kB_eV = 8.617e-5
        ln_sigma_fit = ln_sigma0 - (Ea_eV / (kB_eV * 1000.0)) * x_seg
        log_sigma_fit = (ln_sigma_fit + np.log(1000)) / np.log(10)

        ax1.plot(x_seg, log_sigma_fit, color=colors_seg[idx], linewidth=2.5, zorder=3,
                 label=f'Segment {idx+1} $R^2$={r_squared:.3f}')

        # Label position
        x_label = inv_T_lo + (inv_T_hi - inv_T_lo) * 0.5
        ln_sigma_label = ln_sigma0 - (Ea_eV / (kB_eV * 1000.0)) * x_label
        y_label = (ln_sigma_label + np.log(1000)) / np.log(10)

        base_offsets = [-0.25, -0.35, -0.45, -0.55]
        y_offset = base_offsets[idx] * y_range if idx < len(base_offsets) else -0.3 * y_range
        y_text = y_label + y_offset

        y_min_safe = log_sigma.min() - 0.1 * y_range
        if y_text < y_min_safe:
            y_text = y_min_safe + 0.05 * y_range

        label_positions.append((x_label, y_text, idx))

        if idx < len(fit_data) - 1:
            breakpoints_x.append(inv_T_hi)

    # Adjust overlapping labels
    for i in range(len(label_positions)):
        for j in range(i + 1, len(label_positions)):
            x1, y1, idx1 = label_positions[i]
            x2, y2, idx2 = label_positions[j]
            if abs(x1 - x2) < 0.3:
                if abs(y1 - y2) < 0.3 * y_range:
                    if idx1 < idx2:
                        label_positions[i] = (x1, y1 - 0.1 * y_range, idx1)
                        label_positions[j] = (x2, y2 + 0.1 * y_range, idx2)
                    else:
                        label_positions[i] = (x1, y1 + 0.1 * y_range, idx1)
                        label_positions[j] = (x2, y2 - 0.1 * y_range, idx2)

    # Draw Ea labels
    for x_label, y_text, idx in label_positions:
        seg_info = fit_data[idx]
        Ea_eV = seg_info['Ea_eV']
        text_str = f'$E_a$ = {Ea_eV:.2f} eV'
        bbox_props = dict(boxstyle='round,pad=0.35', facecolor='white',
                         edgecolor=colors_seg[idx], linewidth=1.3, alpha=0.92)
        ax1.text(x_label, y_text, text_str, fontsize=10, ha='center', va='top',
                color=colors_seg[idx], fontweight='bold', bbox=bbox_props, zorder=5)

    # Breakpoint dashed lines
    for bp in breakpoints_x:
        ax1.axvline(x=bp, color='#808080', linestyle='--', linewidth=1.2, zorder=1, alpha=0.7)

    # Axes
    ax1.set_xlabel(r'1000/$T$ (K$^{-1}$)', fontsize=14, fontweight='bold')
    ax1.set_ylabel(r'log $\sigma$ (mS$\cdot$cm$^{-1}$)', fontsize=14, fontweight='bold')

    x_min = np.floor(inv_T.min() * 2) / 2
    x_max = np.ceil(inv_T.max() * 2) / 2
    ax1.set_xlim(x_min, x_max)

    y_margin_top = 0.15 * y_range
    y_margin_bottom = 0.4 * y_range
    ax1.set_ylim(log_sigma.min() - y_margin_bottom, log_sigma.max() + y_margin_top + 0.5)

    x_ticks_bottom = np.arange(x_min, x_max + 0.01, 0.5)
    ax1.set_xticks(x_ticks_bottom)
    ax1.grid(True)
    ax1.legend(loc='lower left', frameon=True, framealpha=0.95, fontsize=10, edgecolor='gray')

    # Top axis (temperature in Celsius)
    ax2 = ax1.twiny()
    ax2.set_xlim(ax1.get_xlim())
    T_K_ticks = 1000.0 / x_ticks_bottom
    T_C_ticks = T_K_ticks - 273.15
    ax2.set_xticks(x_ticks_bottom)
    ax2.set_xticklabels([f'{t:.0f}' for t in T_C_ticks], fontsize=12)
    ax2.set_xlabel(r'$T$ ($\degree$C)', fontsize=14, fontweight='bold')
    ax2.tick_params(direction='in', width=1.1, length=5)

    # Bold tick labels
    for label in ax1.get_xticklabels() + ax1.get_yticklabels():
        label.set_fontweight('bold')
    for label in ax2.get_xticklabels():
        label.set_fontweight('bold')

    # Panel label
    fig.text(0.01, 0.95, '(a)', fontsize=18, fontweight='bold', fontfamily='serif')

    plt.tight_layout()

    # Save to figure3_agent_analysis directory
    for path, dpi_val in [(FIG3_DIR / f"figure3a_arrhenius_4seg.png", 300),
                           (FIG3_DIR / f"figure3a_arrhenius_4seg.pdf", None)]:
        if dpi_val:
            fig.savefig(str(path), dpi=dpi_val, bbox_inches='tight', facecolor='white')
        else:
            fig.savefig(str(path), bbox_inches='tight', facecolor='white')
        print(f"Saved: {path}")

    # Also save to paper_figure root
    for path, dpi_val in [(OUT_DIR / f"figure1_arrhenius_{SAMPLE_ID}_4segments.png", 300),
                           (OUT_DIR / f"figure1_arrhenius_{SAMPLE_ID}_4segments.pdf", None)]:
        if dpi_val:
            fig.savefig(str(path), dpi=dpi_val, bbox_inches='tight', facecolor='white')
        else:
            fig.savefig(str(path), bbox_inches='tight', facecolor='white')
        print(f"Saved: {path}")

    plt.close(fig)
    print("\nDone: Figure 3a (Arrhenius 4-segment) with Times New Roman Bold")

if __name__ == "__main__":
    main()
