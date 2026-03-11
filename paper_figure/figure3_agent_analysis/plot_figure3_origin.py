# -*- coding: utf-8 -*-
"""
Figure 3c & 3d — Origin-matching style (Times New Roman, white bg, inward ticks).

(c) Confinement Effect: ΔEa vs Temperature
(d) Meyer-Neldel Compensation: ln(σ₀) vs Ea

Matches the user's Origin figure style for consistent publication quality.
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
# Origin Style Configuration
# ════════════════════════════════════════════════════════════════
def setup_origin_style():
    """Configure matplotlib to match Origin Pro plotting style."""
    plt.rcParams.update({
        # Font: Times New Roman
        'font.family': 'serif',
        'font.serif': ['Times New Roman', 'DejaVu Serif'],
        'font.size': 11,
        'mathtext.fontset': 'stix',

        # Axes
        'axes.labelsize': 13,
        'axes.titlesize': 14,
        'axes.titleweight': 'bold',
        'axes.linewidth': 1.2,
        'axes.labelweight': 'normal',
        'axes.facecolor': 'white',

        # Ticks — inward, all 4 sides
        'xtick.labelsize': 11,
        'ytick.labelsize': 11,
        'xtick.direction': 'in',
        'ytick.direction': 'in',
        'xtick.major.width': 1.0,
        'ytick.major.width': 1.0,
        'xtick.major.size': 5,
        'ytick.major.size': 5,
        'xtick.minor.visible': True,
        'ytick.minor.visible': True,
        'xtick.minor.size': 3,
        'ytick.minor.size': 3,
        'xtick.top': True,
        'ytick.right': True,

        # Legend
        'legend.fontsize': 10,
        'legend.frameon': True,
        'legend.framealpha': 1.0,
        'legend.edgecolor': 'black',
        'legend.fancybox': False,

        # Lines
        'lines.linewidth': 1.5,
        'lines.markersize': 5,

        # No grid
        'axes.grid': False,

        # Save
        'savefig.dpi': 300,
        'savefig.bbox': 'tight',
        'savefig.pad_inches': 0.08,
        'figure.facecolor': 'white',
    })


# ─── Colors (muted, academic) ───
C_DATA   = '#4A7FB5'   # Steel blue — data points
C_FIT    = '#8B2500'   # Dark sienna — fit line
C_CI     = '#B0C4DE'   # Light steel blue — CI band
C_REF    = '#666666'   # Dark gray — reference line
C_LOW    = '#4A7FB5'   # Blue — Low T
C_MID    = '#3A9A6B'   # Teal green — Mid T
C_HIGH   = '#CC6666'   # Muted coral — High T


def save_fig(fig, path_stem, dpi=300):
    """Save PNG + PDF."""
    fig.savefig(f'{path_stem}.png', dpi=dpi, bbox_inches='tight', facecolor='white')
    fig.savefig(f'{path_stem}.pdf', bbox_inches='tight', facecolor='white')
    print(f'  Saved: {path_stem}.png')
    print(f'  Saved: {path_stem}.pdf')


# ════════════════════════════════════════════════════════════════
# Load Data
# ════════════════════════════════════════════════════════════════
setup_origin_style()

csv_path = PHASE3V2_DIR / "integrated_data.csv"
df = pd.read_csv(csv_path)
s8_all  = df[(df['material_type'] == 'S8')  & (df['segment'] != 'full_range')].copy()
s60_all = df[(df['material_type'] == 'S60') & (df['segment'] != 'full_range')].copy()

# Load JSON summaries
conf_json = PHASE3V2_DIR / "confinement" / "summary.json"
conf = json.loads(conf_json.read_text(encoding='utf-8'))

mn_json = PHASE3V2_DIR / "meyer_neldel" / "summary.json"
mn = json.loads(mn_json.read_text(encoding='utf-8'))

# ─── Build ΔEa via S60 baseline model ───
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
# (c) Confinement Effect: ΔEa vs Temperature
# ════════════════════════════════════════════════════════════════
print("Generating (c) Confinement Effect: ΔEa vs Temperature ...")

fig_c, ax_c = plt.subplots(figsize=(6, 5), dpi=300)

# Scatter — single color, clean
ax_c.scatter(T_vals, dea_vals, s=30, alpha=0.6, color=C_DATA,
             edgecolors='white', linewidths=0.3, zorder=3, clip_on=True)

# Linear fit
fit_info = conf.get("delta_Ea_vs_T_linear_fit", {})
slope     = fit_info.get("slope_per_K", -0.00215)
intercept = fit_info.get("intercept_eV", 0.614)
r2        = fit_info.get("r_squared", 0.186)

T_range = np.linspace(T_vals.min() - 3, T_vals.max() + 3, 200)
dea_fit = slope * T_range + intercept
ax_c.plot(T_range, dea_fit, '-', color=C_FIT, linewidth=2.0, zorder=4,
          label=f'Linear fit (slope = {slope*1000:.2f} meV/K)')

# 95% CI band
n = len(T_vals)
t_crit = stats.t.ppf(0.975, n - 2)
residuals = dea_vals - (slope * T_vals + intercept)
se_res = np.sqrt(np.sum(residuals**2) / (n - 2))
T_mean = T_vals.mean()
se_fit = se_res * np.sqrt(1/n + (T_range - T_mean)**2 / np.sum((T_vals - T_mean)**2))
ax_c.fill_between(T_range, dea_fit - t_crit*se_fit, dea_fit + t_crit*se_fit,
                  alpha=0.15, color=C_CI, zorder=1, label='95% CI')

# Reference line at ΔEa = 0
ax_c.axhline(0, color=C_REF, linestyle='--', linewidth=1.0, alpha=0.6, zorder=2)

# Zone annotations — clean, no colored backgrounds
zones = {
    'low':  {'label': '<230 K',      'color': C_LOW,  'data': conf.get("low_T_under_230K", {})},
    'mid':  {'label': '230\u2013270 K', 'color': C_MID,  'data': conf.get("mid_T_230_270K", {})},
    'high': {'label': '>270 K',      'color': C_HIGH, 'data': conf.get("high_T_over_270K", {})},
}

y_top = 0.54
for key, info in zones.items():
    zdata = info['data']
    zmean = zdata.get('mean', 0)
    zn    = zdata.get('n', '?')
    if key == 'low':
        xpos = 207
    elif key == 'mid':
        xpos = 250
    else:
        xpos = 282
    ax_c.annotate(
        f'{info["label"]}\n'
        r'$\overline{\Delta E_a}$' + f' = {zmean:.3f} eV\n'
        f'n = {zn}',
        xy=(xpos, y_top), fontsize=8.5, ha='center', va='top',
        color=info['color'], fontweight='bold',
        bbox=dict(boxstyle='round,pad=0.3', facecolor='white',
                  edgecolor='black', alpha=0.9, linewidth=0.6)
    )

# Stats box — clean black border
overall  = conf.get("overall", {})
mean_dea = overall.get("mean", 0.082)
ci_lo    = overall.get("ci_95_low", 0.054)
ci_hi    = overall.get("ci_95_high", 0.110)
ttest    = conf.get("low_vs_high_T_ttest", {})
p_val    = ttest.get("p_value", 1.83e-5)

ax_c.text(0.97, 0.03,
          r'Overall $\overline{\Delta E_a}$' + f' = {mean_dea:.3f} eV\n'
          f'95% CI [{ci_lo:.3f}, {ci_hi:.3f}]\n'
          r'$R^2$' + f' = {r2:.3f}\n'
          f'p = {p_val:.2e}',
          transform=ax_c.transAxes, fontsize=9,
          va='bottom', ha='right',
          bbox=dict(boxstyle='round,pad=0.4', facecolor='white',
                    edgecolor='black', alpha=0.95, linewidth=0.6))

ax_c.set_xlabel('Temperature (K)')
ax_c.set_ylabel(r'$\Delta E_a = E_a$(S8) $-$ $E_a$(S60 pred.) (eV)')
ax_c.set_title(r'Confinement Effect: $\Delta E_a$ vs Temperature')
ax_c.legend(fontsize=9, loc='upper left', framealpha=1.0,
            edgecolor='black', fancybox=False)

# Panel label
ax_c.text(-0.12, 1.03, '(c)', transform=ax_c.transAxes,
          fontsize=16, fontweight='bold', va='bottom')

plt.tight_layout()
save_fig(fig_c, str(OUT / "figure3c_confinement_delta_ea"), dpi=300)
plt.close(fig_c)
print("  Done: (c)")


# ════════════════════════════════════════════════════════════════
# (d) Meyer-Neldel Compensation — S8 only
# ════════════════════════════════════════════════════════════════
print("Generating (d) Meyer-Neldel Compensation ...")

fig_d, ax_d = plt.subplots(figsize=(6, 5), dpi=300)

# S8 data
mask = np.isfinite(s8_all['Ea_eV'].values) & np.isfinite(s8_all['ln_sigma0'].values)
ea_s8  = s8_all['Ea_eV'].values[mask]
ls0_s8 = s8_all['ln_sigma0'].values[mask]

# Scatter
ax_d.scatter(ea_s8, ls0_s8, s=30, alpha=0.55, color=C_DATA,
             edgecolors='white', linewidths=0.3, zorder=3,
             label=r'S8 (Sepiolite + H$_3$PO$_4$)')

# Fit from JSON
s8_mn      = mn.get("S8", {})
mn_slope   = s8_mn.get("slope", 49.87)
mn_inter   = s8_mn.get("intercept", -6.83)
mn_emn     = s8_mn.get("E_MN_eV", 0.0201)
mn_r2      = s8_mn.get("r_squared", 0.981)
T_mn       = mn_emn / 8.617e-5  # eV → K via kB

ea_range = np.linspace(max(ea_s8.min() - 0.05, 0), ea_s8.max() + 0.05, 200)
ls0_fit  = mn_slope * ea_range + mn_inter
ax_d.plot(ea_range, ls0_fit, '-', color=C_FIT, linewidth=2.0, zorder=4,
          label=f'MN fit: slope = {mn_slope:.1f}')

# Stats annotation — clean black border
ax_d.text(0.03, 0.97,
          f'Meyer-Neldel Rule (S8)\n'
          r'$E_{\mathrm{MN}}$' + f' = {mn_emn:.4f} eV\n'
          r'$R^2$' + f' = {mn_r2:.4f}\n'
          f'n = {s8_mn.get("n_points", len(ea_s8))}',
          transform=ax_d.transAxes, fontsize=9.5,
          va='top', ha='left',
          bbox=dict(boxstyle='round,pad=0.4', facecolor='white',
                    edgecolor='black', alpha=0.95, linewidth=0.6))

# TMN annotation — subtle
ax_d.text(0.03, 0.67,
          r'$T_{\mathrm{MN}}$' + f' = {T_mn:.0f} K',
          transform=ax_d.transAxes, fontsize=10, color=C_FIT,
          fontweight='bold',
          bbox=dict(boxstyle='round,pad=0.25', facecolor='white',
                    edgecolor=C_FIT, alpha=0.9, linewidth=0.8))

ax_d.set_xlabel(r'Activation Energy, $E_a$ (eV)')
ax_d.set_ylabel(r'ln($\sigma_0$) (ln S$\cdot$cm$^{-1}$)')
ax_d.set_title(r'Meyer-Neldel Compensation: ln($\sigma_0$) vs $E_a$')
ax_d.legend(fontsize=9, loc='lower right', framealpha=1.0,
            edgecolor='black', fancybox=False)

ax_d.text(-0.12, 1.03, '(d)', transform=ax_d.transAxes,
          fontsize=16, fontweight='bold', va='bottom')

plt.tight_layout()
save_fig(fig_d, str(OUT / "figure3d_meyer_neldel"), dpi=300)
plt.close(fig_d)
print("  Done: (d)")

print("\n=== Figure 3c & 3d (Origin style) generated! ===")
