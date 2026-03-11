# -*- coding: utf-8 -*-
"""
Figure 3c & 3d — Based on user feedback:
  (c) ΔEa boxplot by temperature zone (instead of scatter)
      — keeps the original figure10 style, adds Times New Roman Bold
  (d) Meyer-Neldel — keeps original style, adds Times New Roman Bold

Key changes from v2:
  - Times New Roman Bold for all axis labels and tick labels
  - (c) uses boxplot instead of scatter (stronger statistical argument)
  - (d) keeps original color scheme but with serif fonts
  - Annotation boxes don't block data points
"""

import sys, io, json, os
import numpy as np
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
from pathlib import Path
from scipy import stats

os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
if sys.platform == 'win32':
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass

# ─── Paths ───
SCRIPT_DIR = Path(__file__).resolve().parent
PAPER_FIG_DIR = SCRIPT_DIR.parent
CLOSE_DIR = PAPER_FIG_DIR.parent
OUTPUT_DIR = CLOSE_DIR / "output"
PHASE3V2_DIR = OUTPUT_DIR / "phase3v2_results"
OUT = SCRIPT_DIR


# ════════════════════════════════════════════════════════════════
# Style: Original look + Times New Roman Bold
# ════════════════════════════════════════════════════════════════
def setup_style():
    plt.rcParams.update({
        # Times New Roman
        'font.family': 'serif',
        'font.serif': ['Times New Roman', 'DejaVu Serif'],
        'font.size': 12,
        # Note: don't set font.weight globally — breaks STIX math cdot glyph
        'mathtext.fontset': 'stix',

        # Axes — bold labels
        'axes.labelsize': 14,
        'axes.titlesize': 15,
        'axes.titleweight': 'bold',
        'axes.linewidth': 1.3,
        'axes.labelweight': 'bold',
        'axes.facecolor': 'white',

        # Ticks — bold, inward
        'xtick.labelsize': 12,
        'ytick.labelsize': 12,
        'xtick.direction': 'in',
        'ytick.direction': 'in',
        'xtick.major.width': 1.1,
        'ytick.major.width': 1.1,
        'xtick.major.size': 5,
        'ytick.major.size': 5,
        'xtick.minor.visible': False,
        'ytick.minor.visible': False,
        'xtick.top': True,
        'ytick.right': True,

        # Legend
        'legend.fontsize': 10,
        'legend.frameon': True,
        'legend.framealpha': 0.9,
        'legend.edgecolor': '#CCCCCC',

        # Lines
        'lines.linewidth': 2.0,
        'lines.markersize': 6,

        # Grid — light
        'axes.grid': True,
        'grid.alpha': 0.25,
        'grid.linewidth': 0.6,

        # Save
        'savefig.dpi': 300,
        'savefig.bbox': 'tight',
        'savefig.pad_inches': 0.08,
        'figure.facecolor': 'white',
    })


# ─── Colors (keeping original palette) ───
C_S8      = '#E91E63'   # Pink — original S8 color
C_S60     = '#2196F3'   # Blue — original S60 color
C_FIT     = '#D32F2F'   # Deep red — fit lines
C_CI      = '#F8BBD0'   # Light pink — CI fill
C_REF     = '#757575'   # Gray — reference
C_DATA    = '#5C8CB8'   # Soft blue — data points
C_LOW     = '#1E88E5'   # Blue — Low T zone
C_MID     = '#43A047'   # Green — Mid T zone
C_HIGH    = '#E53935'   # Red — High T zone


def save_fig(fig, path_stem, dpi=300):
    fig.savefig(f'{path_stem}.png', dpi=dpi, bbox_inches='tight', facecolor='white')
    fig.savefig(f'{path_stem}.pdf', bbox_inches='tight', facecolor='white')
    print(f'  Saved: {path_stem}.png')
    print(f'  Saved: {path_stem}.pdf')


# ════════════════════════════════════════════════════════════════
# Load Data
# ════════════════════════════════════════════════════════════════
setup_style()

csv_path = PHASE3V2_DIR / "integrated_data.csv"
df = pd.read_csv(csv_path)
s8_all  = df[(df['material_type'] == 'S8')  & (df['segment'] != 'full_range')].copy()
s60_all = df[(df['material_type'] == 'S60') & (df['segment'] != 'full_range')].copy()

# Load JSON summaries
conf_json = PHASE3V2_DIR / "confinement" / "summary.json"
conf = json.loads(conf_json.read_text(encoding='utf-8'))
mn_json = PHASE3V2_DIR / "meyer_neldel" / "summary.json"
mn = json.loads(mn_json.read_text(encoding='utf-8'))

# ─── Build ΔEa ───
from sklearn.linear_model import Ridge
from sklearn.preprocessing import PolynomialFeatures

s60_clean = s60_all.dropna(subset=['R', 'T_avg_K', 'Ea_eV'])
X60 = s60_clean[['R', 'T_avg_K']].values
y60 = s60_clean['Ea_eV'].values
poly = PolynomialFeatures(2, include_bias=False)
X60p = poly.fit_transform(X60)
ridge = Ridge(alpha=5.0).fit(X60p, y60)

s8_clean = s8_all.dropna(subset=['R', 'T_avg_K', 'Ea_eV'])
X8  = s8_clean[['R', 'T_avg_K']].values
X8p = poly.transform(X8)
s8_pred = ridge.predict(X8p)

T_vals   = s8_clean['T_avg_K'].values
dea_vals = s8_clean['Ea_eV'].values - s8_pred


# ════════════════════════════════════════════════════════════════
# (c) ΔEa Boxplot by Temperature Region
#     — Based on original figure10 style + Times New Roman Bold
# ════════════════════════════════════════════════════════════════
print("Generating (c) ΔEa Boxplot by Temperature Region ...")

fig_c, ax_c = plt.subplots(figsize=(6, 5.5), dpi=300)

# Assign temperature zones
zones = []
zone_data = {'Low T (<230 K)': [], 'Mid T (230-270 K)': [], 'High T (>=270 K)': []}
for t, dea in zip(T_vals, dea_vals):
    if t < 230:
        zones.append('Low T (<230 K)')
        zone_data['Low T (<230 K)'].append(dea)
    elif t < 270:
        zones.append('Mid T (230-270 K)')
        zone_data['Mid T (230-270 K)'].append(dea)
    else:
        zones.append('High T (>=270 K)')
        zone_data['High T (>=270 K)'].append(dea)

zone_order  = ['Low T (<230 K)', 'Mid T (230-270 K)', 'High T (>=270 K)']
zone_colors = [C_LOW, C_MID, C_HIGH]
positions   = [1, 2, 3]

for i, (zname, col) in enumerate(zip(zone_order, zone_colors)):
    data = np.array(zone_data[zname])
    bp = ax_c.boxplot(
        [data], positions=[positions[i]], widths=0.55,
        patch_artist=True, showmeans=True,
        meanprops=dict(marker='_', markeredgecolor='black',
                       markerfacecolor='black', markersize=12, markeredgewidth=2),
        medianprops=dict(color='white', linewidth=2.0),
        boxprops=dict(facecolor=col, alpha=0.55, edgecolor='black', linewidth=1.0),
        whiskerprops=dict(color='black', linewidth=1.0),
        capprops=dict(color='black', linewidth=1.0),
        flierprops=dict(marker='o', markerfacecolor='none', markersize=5,
                        markeredgecolor='gray', alpha=0.6)
    )

    # Jitter scatter overlay
    rng = np.random.default_rng(42 + i)
    jitter = rng.uniform(-0.15, 0.15, len(data))
    ax_c.scatter(
        np.full_like(data, positions[i]) + jitter, data,
        s=20, alpha=0.5, color=col, edgecolors='none', zorder=2
    )

    # (n= labels added after ylim is set)

# Significance bracket (Low T vs High T)
low_data  = np.array(zone_data[zone_order[0]])
high_data = np.array(zone_data[zone_order[2]])
t_stat, p_val_lr = stats.ttest_ind(low_data, high_data)

# Use the p from the JSON if available
ttest_info = conf.get("low_vs_high_T_ttest", {})
p_val = ttest_info.get("p_value", p_val_lr)

bracket_y = 0.60
ax_c.plot([1, 1, 3, 3], [bracket_y - 0.01, bracket_y, bracket_y, bracket_y - 0.01],
          'k-', linewidth=1.2)
sig_stars = '***' if p_val < 0.001 else ('**' if p_val < 0.01 else ('*' if p_val < 0.05 else 'ns'))
ax_c.text(2, bracket_y + 0.005, f'{sig_stars}\np = {p_val:.1e}', ha='center', va='bottom',
          fontsize=10, fontweight='bold')

# Reference line at ΔEa = 0
ax_c.axhline(0, color='#999999', linestyle='--', linewidth=1.0, alpha=0.5, zorder=1)

# Set ylim to leave room at bottom for n= labels
ax_c.set_ylim(-0.30, 0.68)

# n= labels at fixed bottom position
for i, zname in enumerate(zone_order):
    n = len(zone_data[zname])
    ax_c.text(positions[i], -0.26, f'n={n}', ha='center', va='top',
              fontsize=10, color='#555', fontweight='bold')

ax_c.set_xticks(positions)
ax_c.set_xticklabels(zone_order, fontsize=12, fontweight='bold')
ax_c.set_ylabel(r'$\Delta E_a$ (eV)', fontsize=14, fontweight='bold')
ax_c.set_title(r'$\Delta E_a$ Distribution by Temperature Region',
               fontsize=15, fontweight='bold')

# Bold tick labels
for label in ax_c.get_xticklabels() + ax_c.get_yticklabels():
    label.set_fontweight('bold')

# Panel label
ax_c.text(-0.10, 1.02, '(c)', transform=ax_c.transAxes,
          fontsize=18, fontweight='bold', va='bottom',
          fontfamily='serif')

plt.tight_layout()
save_fig(fig_c, str(OUT / "figure3c_confinement_delta_ea"), dpi=300)
plt.close(fig_c)
print("  Done: (c) Boxplot")


# ════════════════════════════════════════════════════════════════
# (d) Meyer-Neldel — Original style + Times New Roman Bold
# ════════════════════════════════════════════════════════════════
print("Generating (d) Meyer-Neldel Compensation ...")

fig_d, ax_d = plt.subplots(figsize=(6, 5.5), dpi=300)

# S8 data
mask = np.isfinite(s8_all['Ea_eV'].values) & np.isfinite(s8_all['ln_sigma0'].values)
ea_s8  = s8_all['Ea_eV'].values[mask]
ls0_s8 = s8_all['ln_sigma0'].values[mask]

# Scatter — original soft blue color
ax_d.scatter(ea_s8, ls0_s8, s=40, alpha=0.55, color=C_DATA,
             edgecolors='white', linewidths=0.4, zorder=3,
             label=r'S8 (Sepiolite + H$_3$PO$_4$)')

# Fit from JSON
s8_mn    = mn.get("S8", {})
mn_slope = s8_mn.get("slope", 49.87)
mn_inter = s8_mn.get("intercept", -6.83)
mn_emn   = s8_mn.get("E_MN_eV", 0.0201)
mn_r2    = s8_mn.get("r_squared", 0.981)
T_mn     = mn_emn / 8.617e-5  # eV → K

ea_range = np.linspace(max(ea_s8.min() - 0.05, 0), ea_s8.max() + 0.05, 200)
ls0_fit  = mn_slope * ea_range + mn_inter
ax_d.plot(ea_range, ls0_fit, '-', color=C_FIT, linewidth=2.5, zorder=4,
          label=f'MN fit: slope = {mn_slope:.1f}')

# Stats box — top left, clean
ax_d.text(0.03, 0.97,
          f'Meyer-Neldel Rule (S8)\n'
          r'$E_{\mathrm{MN}}$' + f' = {mn_emn:.4f} eV\n'
          r'$R^2$' + f' = {mn_r2:.4f}\n'
          f'n = {s8_mn.get("n_points", len(ea_s8))}',
          transform=ax_d.transAxes, fontsize=10,
          va='top', ha='left',
          bbox=dict(boxstyle='round,pad=0.35', facecolor='white',
                    edgecolor='#BDBDBD', alpha=0.9, linewidth=1.0))

# TMN annotation — placed below stats box, not too flashy
ax_d.text(0.03, 0.68,
          r'$T_{\mathrm{MN}}$' + f' = {T_mn:.0f} K',
          transform=ax_d.transAxes, fontsize=10, color=C_FIT,
          fontweight='bold',
          bbox=dict(boxstyle='round,pad=0.2', facecolor='#FFEBEE',
                    edgecolor=C_FIT, alpha=0.8))

ax_d.set_xlabel(r'Activation Energy, $E_a$ (eV)', fontsize=14, fontweight='bold')
ax_d.set_ylabel(r'ln($\sigma_0$) (ln S$\cdot$cm$^{-1}$)', fontsize=14, fontweight='bold')
ax_d.set_title(r'Meyer-Neldel Compensation: ln($\sigma_0$) vs $E_a$',
               fontsize=15, fontweight='bold')
ax_d.legend(fontsize=10, loc='lower right', framealpha=0.9)

# Bold tick labels
for label in ax_d.get_xticklabels() + ax_d.get_yticklabels():
    label.set_fontweight('bold')

# Panel label
ax_d.text(-0.10, 1.02, '(d)', transform=ax_d.transAxes,
          fontsize=18, fontweight='bold', va='bottom',
          fontfamily='serif')

plt.tight_layout()
save_fig(fig_d, str(OUT / "figure3d_meyer_neldel"), dpi=300)
plt.close(fig_d)
print("  Done: (d) Meyer-Neldel")

print("\n=== Figure 3c (boxplot) & 3d (Meyer-Neldel) v3 generated! ===")
