# -*- coding: utf-8 -*-
"""
Figure 3: Generate 4 individual sub-figures for PPT composition.

(a) Arrhenius 4-segment fit (S8-3-9-3) — copy existing
(b) Violin distribution of breakpoint temperatures — copy existing
(c) Confinement effect: ΔEa vs Temperature — AM-style, consistent with web report
(d) Meyer-Neldel compensation plot — AM-style, S8 only (consistent with web report)

Style: Advanced Materials (AM) journal format
"""

import sys, io, json, os, shutil
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from scipy import stats

os.environ.setdefault('PYTHONIOENCODING', 'utf-8')

# ── Paths ──
SCRIPT_DIR = Path(__file__).resolve().parent
PAPER_FIG_DIR = SCRIPT_DIR.parent
CLOSE_DIR = PAPER_FIG_DIR.parent
OUTPUT_DIR = CLOSE_DIR / "output"
PHASE3V2_DIR = OUTPUT_DIR / "phase3v2_results"

sys.path.insert(0, str(PAPER_FIG_DIR))
from am_style_config import (
    setup_am_style, COLORS, save_figure, add_panel_label, AM_RCPARAMS
)

# ── AM Style ──
setup_am_style()

# ============================================================
# Color Palette
# ============================================================
C_S8 = '#E91E63'
C_S60 = '#2196F3'
C_FIT = '#D32F2F'
C_CI = '#F8BBD0'
C_REF = '#757575'
C_DATA = '#5C8CB8'       # Soft blue, matching web report style
C_HIGH = '#E53935'
C_MID = '#43A047'
C_LOW = '#1E88E5'

OUT = SCRIPT_DIR  # output to same directory

# ============================================================
# (a) Copy existing Arrhenius plot
# ============================================================
src_a = PAPER_FIG_DIR / "figure1_arrhenius_S8-3-9-3_4segments.png"
dst_a = OUT / "figure3a_arrhenius_4seg.png"
if src_a.exists():
    shutil.copy2(str(src_a), str(dst_a))
    print(f"(a) Copied: {dst_a}")
else:
    print(f"(a) WARNING: Source not found: {src_a}")

# Also copy PDF if exists
src_a_pdf = src_a.with_suffix('.pdf')
if src_a_pdf.exists():
    shutil.copy2(str(src_a_pdf), str(dst_a.with_suffix('.pdf')))

# ============================================================
# (b) Copy existing Violin plot
# ============================================================
src_b = PAPER_FIG_DIR / "figure2" / "figure2_violin_distribution.png"
dst_b = OUT / "figure3b_violin_distribution.png"
if src_b.exists():
    shutil.copy2(str(src_b), str(dst_b))
    print(f"(b) Copied: {dst_b}")
else:
    print(f"(b) WARNING: Source not found: {src_b}")

src_b_pdf = (PAPER_FIG_DIR / "figure2" / "figure2_violin_distribution.pdf")
if src_b_pdf.exists():
    shutil.copy2(str(src_b_pdf), str(dst_b.with_suffix('.pdf')))

# ============================================================
# Load data
# ============================================================
csv_path = PHASE3V2_DIR / "integrated_data.csv"
df = pd.read_csv(csv_path)
s8_all = df[(df['material_type'] == 'S8') & (df['segment'] != 'full_range')].copy()
s60_all = df[(df['material_type'] == 'S60') & (df['segment'] != 'full_range')].copy()

# Load confinement summary
conf_json = PHASE3V2_DIR / "confinement" / "summary.json"
conf = json.loads(conf_json.read_text(encoding='utf-8'))

# Load MN summary
mn_json = PHASE3V2_DIR / "meyer_neldel" / "summary.json"
mn = json.loads(mn_json.read_text(encoding='utf-8'))

# ============================================================
# Build ΔEa data (same method as tools.py in phase3-v2.0)
# ============================================================
from sklearn.linear_model import Ridge
from sklearn.preprocessing import PolynomialFeatures

s60_clean = s60_all.dropna(subset=['R', 'T_avg_K', 'Ea_eV'])
X60 = s60_clean[['R', 'T_avg_K']].values
y60 = s60_clean['Ea_eV'].values
poly = PolynomialFeatures(2, include_bias=False)
X60p = poly.fit_transform(X60)
ridge = Ridge(alpha=1.0).fit(X60p, y60)

s8_clean = s8_all.dropna(subset=['R', 'T_avg_K', 'Ea_eV'])
X8 = s8_clean[['R', 'T_avg_K']].values
X8p = poly.transform(X8)
s8_pred = ridge.predict(X8p)

T_vals = s8_clean['T_avg_K'].values
dea_vals = s8_clean['Ea_eV'].values - s8_pred

# ============================================================
# (c) Confinement Effect: ΔEa vs Temperature — AM style
# ============================================================
fig_c, ax_c = plt.subplots(figsize=(6, 4.5), dpi=300)

# Scatter
ax_c.scatter(T_vals, dea_vals, s=35, alpha=0.55, color=C_DATA,
             edgecolors='white', linewidths=0.4, zorder=3)

# Linear fit (from JSON for consistency)
fit_info = conf.get("delta_Ea_vs_T_linear_fit", {})
slope = fit_info.get("slope_per_K", -0.00215)
intercept = fit_info.get("intercept_eV", 0.614)
r2 = fit_info.get("r_squared", 0.186)

T_range = np.linspace(T_vals.min() - 2, T_vals.max() + 2, 200)
dea_fit = slope * T_range + intercept
ax_c.plot(T_range, dea_fit, '-', color=C_FIT, linewidth=2.5, zorder=4,
          label=f'Linear fit: slope = {slope*1000:.2f} meV/K')

# 95% CI band
n = len(T_vals)
t_crit = stats.t.ppf(0.975, n - 2)
residuals = dea_vals - (slope * T_vals + intercept)
se_res = np.sqrt(np.sum(residuals**2) / (n - 2))
T_mean = T_vals.mean()
se_fit = se_res * np.sqrt(1/n + (T_range - T_mean)**2 / np.sum((T_vals - T_mean)**2))
ax_c.fill_between(T_range, dea_fit - t_crit*se_fit, dea_fit + t_crit*se_fit,
                  alpha=0.12, color=C_S8, zorder=1, label='95% CI')

# Reference line
ax_c.axhline(0, color=C_REF, linestyle='--', linewidth=1.0, alpha=0.5, zorder=2)

# Zone annotations with actual data
zones = {
    'low':  {'label': '<230 K',     'color': C_LOW,  'data': conf.get("low_T_under_230K", {})},
    'mid':  {'label': '230\u2013270 K', 'color': C_MID,  'data': conf.get("mid_T_230_270K", {})},
    'high': {'label': '>270 K',     'color': C_HIGH, 'data': conf.get("high_T_over_270K", {})},
}

# Light zone shading
ax_c.axvspan(T_vals.min() - 5, 230, alpha=0.04, color=C_LOW, zorder=0)
ax_c.axvspan(230, 270, alpha=0.04, color=C_MID, zorder=0)
ax_c.axvspan(270, T_vals.max() + 5, alpha=0.04, color=C_HIGH, zorder=0)

# Zone labels at top
y_top = ax_c.get_ylim()[1] * 0.92 if ax_c.get_ylim()[1] > 0.3 else 0.52
for key, info in zones.items():
    zdata = info['data']
    zmean = zdata.get('mean', 0)
    zn = zdata.get('n', '?')
    zci_lo = zdata.get('ci_95_low', zmean)
    zci_hi = zdata.get('ci_95_high', zmean)
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
        xy=(xpos, y_top), fontsize=7.5, ha='center', va='top',
        color=info['color'], fontweight='bold',
        bbox=dict(boxstyle='round,pad=0.25', facecolor='white',
                  edgecolor=info['color'], alpha=0.85, linewidth=1.0)
    )

# Stats box
overall = conf.get("overall", {})
mean_dea = overall.get("mean", 0.082)
ci_lo = overall.get("ci_95_low", 0.054)
ci_hi = overall.get("ci_95_high", 0.110)
ttest = conf.get("low_vs_high_T_ttest", {})
p_val = ttest.get("p_value", 1.83e-5)

ax_c.text(0.97, 0.03,
          r'Overall $\overline{\Delta E_a}$' + f' = {mean_dea:.3f} eV\n'
          f'95% CI [{ci_lo:.3f}, {ci_hi:.3f}]\n'
          r'$R^2$' + f' = {r2:.3f}\n'
          f'p = {p_val:.2e}',
          transform=ax_c.transAxes, fontsize=8,
          va='bottom', ha='right',
          bbox=dict(boxstyle='round,pad=0.35', facecolor='#FFF9C4',
                    edgecolor='#FBC02D', alpha=0.9, linewidth=1.0))

ax_c.set_xlabel('Temperature (K)', fontsize=12)
ax_c.set_ylabel(r'$\Delta E_a$ = $E_a$(S8) $-$ $E_a$(S60 pred.) (eV)', fontsize=11)
ax_c.set_title('Confinement Effect: $\\Delta E_a$ vs Temperature', fontsize=13, fontweight='bold')
ax_c.legend(fontsize=9, loc='upper left', framealpha=0.9)
ax_c.grid(True, alpha=0.25, linewidth=0.6)

# Panel label
add_panel_label(ax_c, 'c', x=-0.12, y=1.03, fontsize=16)

plt.tight_layout()
save_figure(fig_c, str(OUT / "figure3c_confinement_delta_ea"), dpi=300)
plt.close(fig_c)
print("(c) Done: Confinement ΔEa plot")

# ============================================================
# (d) Meyer-Neldel Compensation — AM style, S8 only (matching web report)
# ============================================================
fig_d, ax_d = plt.subplots(figsize=(6, 4.5), dpi=300)

# S8 data
ea_s8 = s8_all['Ea_eV'].dropna().values
ls0_s8 = s8_all['ln_sigma0'].dropna().values
# Align arrays
mask = np.isfinite(s8_all['Ea_eV'].values) & np.isfinite(s8_all['ln_sigma0'].values)
ea_s8 = s8_all['Ea_eV'].values[mask]
ls0_s8 = s8_all['ln_sigma0'].values[mask]

# Scatter S8
ax_d.scatter(ea_s8, ls0_s8, s=40, alpha=0.55, color=C_DATA,
             edgecolors='white', linewidths=0.4, zorder=3,
             label=r'S8 (Sepiolite + H$_3$PO$_4$)')

# Fit from JSON (for consistency with web report)
s8_mn = mn.get("S8", {})
mn_slope = s8_mn.get("slope", 49.87)
mn_intercept = s8_mn.get("intercept", -6.83)
mn_emn = s8_mn.get("E_MN_eV", 0.0201)
mn_r2 = s8_mn.get("r_squared", 0.981)

ea_range = np.linspace(max(ea_s8.min() - 0.05, 0), ea_s8.max() + 0.05, 200)
ls0_fit = mn_slope * ea_range + mn_intercept
ax_d.plot(ea_range, ls0_fit, '-', color=C_FIT, linewidth=2.5, zorder=4,
          label=f'MN fit: slope = {mn_slope:.1f}')

# Stats annotation
ax_d.text(0.03, 0.97,
          f'Meyer-Neldel Rule (S8)\n'
          r'$E_{MN}$' + f' = {mn_emn:.4f} eV\n'
          r'$R^2$' + f' = {mn_r2:.4f}\n'
          f'n = {s8_mn.get("n_points", len(ea_s8))}',
          transform=ax_d.transAxes, fontsize=9,
          va='top', ha='left',
          bbox=dict(boxstyle='round,pad=0.35', facecolor='white',
                    edgecolor='#BDBDBD', alpha=0.9, linewidth=1.0))

# Meyer-Neldel temperature annotation
T_mn = mn_emn / 8.617e-5  # eV to K via kB
ax_d.text(0.03, 0.68,
          r'$T_{MN}$' + f' = {T_mn:.0f} K',
          transform=ax_d.transAxes, fontsize=9, color=C_FIT,
          fontweight='bold',
          bbox=dict(boxstyle='round,pad=0.2', facecolor='#FFEBEE',
                    edgecolor=C_FIT, alpha=0.8))

ax_d.set_xlabel(r'Activation Energy, $E_a$ (eV)', fontsize=12)
ax_d.set_ylabel(r'ln($\sigma_0$) (ln S$\cdot$cm$^{-1}$)', fontsize=11)
ax_d.set_title(r'Meyer-Neldel Compensation: ln($\sigma_0$) vs $E_a$', fontsize=13, fontweight='bold')
ax_d.legend(fontsize=9, loc='lower right', framealpha=0.9)
ax_d.grid(True, alpha=0.25, linewidth=0.6)

add_panel_label(ax_d, 'd', x=-0.12, y=1.03, fontsize=16)

plt.tight_layout()
save_figure(fig_d, str(OUT / "figure3d_meyer_neldel"), dpi=300)
plt.close(fig_d)
print("(d) Done: Meyer-Neldel plot")

print("\n=== All 4 individual figures for Figure 3 generated! ===")
