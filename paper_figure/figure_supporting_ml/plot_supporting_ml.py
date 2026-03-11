# -*- coding: utf-8 -*-
"""
Supporting Information — ML Analysis Figures
Origin-matching style (Times New Roman, white bg).

Generates:
  S1: Feature Correlation Matrix
  S2: Partial Dependence Plots (T, R, N)
  S3: Multi-temperature Ea prediction surfaces (6 panels)
  S4: S60 vs S8 Model Comparison
"""

import sys, io, os, json
import numpy as np
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from pathlib import Path
from scipy import stats

os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
if sys.platform == 'win32':
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass

SCRIPT_DIR = Path(__file__).resolve().parent
PAPER_FIG_DIR = SCRIPT_DIR.parent
CLOSE_DIR = PAPER_FIG_DIR.parent
PHASE3V2_DIR = CLOSE_DIR / "output" / "phase3v2_results"
OUT = SCRIPT_DIR


def setup_origin_style():
    plt.rcParams.update({
        'font.family': 'serif',
        'font.serif': ['Times New Roman', 'DejaVu Serif'],
        'font.size': 11,
        'mathtext.fontset': 'stix',
        'axes.labelsize': 12,
        'axes.titlesize': 13,
        'axes.titleweight': 'bold',
        'axes.linewidth': 1.2,
        'axes.facecolor': 'white',
        'xtick.labelsize': 10,
        'ytick.labelsize': 10,
        'xtick.direction': 'in',
        'ytick.direction': 'in',
        'xtick.major.width': 1.0,
        'ytick.major.width': 1.0,
        'xtick.major.size': 5,
        'ytick.major.size': 5,
        'xtick.minor.visible': False,
        'ytick.minor.visible': False,
        'xtick.top': True,
        'ytick.right': True,
        'legend.fontsize': 9,
        'legend.frameon': True,
        'legend.framealpha': 1.0,
        'legend.edgecolor': 'black',
        'legend.fancybox': False,
        'axes.grid': False,
        'savefig.dpi': 300,
        'savefig.bbox': 'tight',
        'figure.facecolor': 'white',
    })


def save_fig(fig, path_stem, dpi=300):
    fig.savefig(f'{path_stem}.png', dpi=dpi, bbox_inches='tight', facecolor='white')
    fig.savefig(f'{path_stem}.pdf', bbox_inches='tight', facecolor='white')
    print(f'  Saved: {path_stem}.png / .pdf')


# Colors
C_S8   = '#4A7FB5'   # Steel blue
C_S60  = '#CC6666'   # Muted coral
C_LINE = '#8B2500'   # Dark sienna


# ════════════════════════════════════════════════════════════════
# Load & Train Models
# ════════════════════════════════════════════════════════════════
setup_origin_style()

csv_path = PHASE3V2_DIR / "integrated_data.csv"
df = pd.read_csv(csv_path)
s8  = df[(df['material_type'] == 'S8')  & (df['segment'] != 'full_range')].copy()
s60 = df[(df['material_type'] == 'S60') & (df['segment'] != 'full_range')].copy()
s8  = s8.dropna(subset=['R', 'N', 'T_avg_K', 'Ea_eV'])
s60 = s60.dropna(subset=['R', 'T_avg_K', 'Ea_eV'])

print(f"Data loaded: S8={len(s8)}, S60={len(s60)}")

# S60 Baseline model (Ridge + poly) — with outlier removal
from sklearn.linear_model import Ridge
from sklearn.preprocessing import PolynomialFeatures
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import r2_score, mean_squared_error, mean_absolute_error
from sklearn.model_selection import cross_val_score

poly_s60 = PolynomialFeatures(2, include_bias=False)
X60_raw = s60[['R', 'T_avg_K']].values
y60_raw = s60['Ea_eV'].values
X60p_raw = poly_s60.fit_transform(X60_raw)
ridge_tmp = Ridge(alpha=5.0).fit(X60p_raw, y60_raw)

# Outlier removal: residual > 3*MAD
resid = y60_raw - ridge_tmp.predict(X60p_raw)
mad = np.median(np.abs(resid - np.median(resid)))
mask_ok = np.abs(resid - np.median(resid)) < 3 * mad * 1.4826
n_removed = (~mask_ok).sum()
print(f"S60: removed {n_removed} outliers")
X60 = X60_raw[mask_ok]
y60 = y60_raw[mask_ok]
X60p = poly_s60.fit_transform(X60)
ridge_s60 = Ridge(alpha=5.0).fit(X60p, y60)

# S8 Confinement model — GBR on RAW features (no poly) for better PDP
X8 = s8[['R', 'N', 'T_avg_K']].values
y8 = s8['Ea_eV'].values
gbr_s8 = GradientBoostingRegressor(
    n_estimators=200, max_depth=4, learning_rate=0.1,
    min_samples_split=5, min_samples_leaf=3, subsample=0.8, random_state=42
).fit(X8, y8)

# Also train poly version for prediction surfaces
poly_s8 = PolynomialFeatures(2, include_bias=False)
X8p = poly_s8.fit_transform(X8)
gbr_s8_poly = GradientBoostingRegressor(
    n_estimators=200, max_depth=4, learning_rate=0.1,
    min_samples_split=5, min_samples_leaf=3, subsample=0.8, random_state=42
).fit(X8p, y8)


# ════════════════════════════════════════════════════════════════
# S1: Feature Correlation Matrix
# ════════════════════════════════════════════════════════════════
print("\n--- S1: Feature Correlation Matrix ---")

# Use S8 data with all features
s8_feats = s8[['T_avg_K', 'R', 'N', 'Ea_eV']].copy()
s8_feats.columns = ['T (K)', 'R', 'N', r'$E_a$ (eV)']

corr = s8_feats.corr()

fig_s1, ax = plt.subplots(figsize=(5.5, 4.5), dpi=300)

# Custom diverging colormap
cmap_div = LinearSegmentedColormap.from_list('div',
    ['#2166AC', '#67A9CF', '#D1E5F0', '#FFFFFF',
     '#FDDBC7', '#EF8A62', '#B2182B'], N=256)

im = ax.imshow(corr.values, cmap=cmap_div, vmin=-1, vmax=1, aspect='equal')

# Annotate
for i in range(corr.shape[0]):
    for j in range(corr.shape[1]):
        val = corr.values[i, j]
        color = 'white' if abs(val) > 0.6 else 'black'
        ax.text(j, i, f'{val:.3f}', ha='center', va='center',
                fontsize=11, fontweight='bold', color=color)

ax.set_xticks(range(len(corr.columns)))
ax.set_yticks(range(len(corr.columns)))
ax.set_xticklabels(corr.columns, fontsize=10, rotation=0)
ax.set_yticklabels(corr.columns, fontsize=10)
ax.set_title('Feature Correlation Matrix (S8)', fontweight='bold')

cbar = plt.colorbar(im, ax=ax, shrink=0.85, pad=0.02)
cbar.set_label('Pearson r', fontsize=11)
cbar.ax.tick_params(labelsize=9)

plt.tight_layout()
save_fig(fig_s1, str(OUT / "figS1_correlation_matrix"))
plt.close(fig_s1)


# ════════════════════════════════════════════════════════════════
# S2: Partial Dependence Plots (using sklearn built-in + raw GBR)
# ════════════════════════════════════════════════════════════════
print("\n--- S2: Partial Dependence Plots ---")

from sklearn.inspection import partial_dependence

fig_s2, axes = plt.subplots(1, 3, figsize=(14, 4.5), dpi=300)

feat_indices = [2, 0, 1]  # T_avg_K, R, N (column indices in X8)
feat_labels = ['Temperature (K)', 'R (acid/clay ratio)', 'N (liquid/solid ratio)']
feat_colors = [C_S8, '#5A9A6B', '#C9963A']

for idx, (fi, label, col) in enumerate(zip(feat_indices, feat_labels, feat_colors)):
    ax = axes[idx]

    # Compute PDP using sklearn (raw-feature GBR)
    pdp_result = partial_dependence(gbr_s8, X8, features=[fi], kind='average',
                                     grid_resolution=100)
    grid_vals = pdp_result['grid_values'][0]
    pdp_avg   = pdp_result['average'][0]

    # Also compute ICE for std band
    pdp_ice = partial_dependence(gbr_s8, X8, features=[fi], kind='individual',
                                  grid_resolution=100)
    ice_curves = pdp_ice['individual'][0]  # shape: (n_samples, n_grid)
    pdp_std = ice_curves.std(axis=0)

    ax.plot(grid_vals, pdp_avg, '-', color=col, linewidth=2.2, zorder=3)
    ax.fill_between(grid_vals, pdp_avg - pdp_std, pdp_avg + pdp_std,
                    alpha=0.12, color=col, zorder=1, label=r'$\pm$1 SD (ICE)')

    # Data rug at bottom
    actual_vals = X8[:, fi]
    y_lo = ax.get_ylim()[0] if ax.get_ylim()[0] != 0 else pdp_avg.min() - 0.03
    ax.set_ylim(bottom=pdp_avg.min() - 0.08)  # ensure space for rug
    y_rug = ax.get_ylim()[0] + 0.005
    ax.plot(actual_vals, np.full_like(actual_vals, y_rug),
            '|', color='black', alpha=0.4, markersize=5, zorder=2)

    ax.set_xlabel(label)
    if idx == 0:
        ax.set_ylabel(r'Partial Dependence of $E_a$ (eV)')
    ax.set_title(f'PDP: {feat_labels[idx].split("(")[0].strip()}', fontweight='bold')
    ax.legend(fontsize=8, loc='upper right', framealpha=1.0, edgecolor='black', fancybox=False)

    # Panel label
    ax.text(-0.12, 1.05, f'({chr(97+idx)})', transform=ax.transAxes,
            fontsize=14, fontweight='bold', va='bottom')

plt.tight_layout()
save_fig(fig_s2, str(OUT / "figS2_partial_dependence"))
plt.close(fig_s2)


# ════════════════════════════════════════════════════════════════
# S3: Multi-temperature Ea Prediction Surfaces (2x3 grid)
# ════════════════════════════════════════════════════════════════
print("\n--- S3: Multi-temperature Ea Prediction Surfaces ---")

temperatures = [190, 210, 230, 250, 270, 290]
R_grid = np.linspace(0.0, 1.05, 150)
N_grid = np.linspace(1.0, 7.1, 150)
RR, NN = np.meshgrid(R_grid, N_grid)

cmap_colors = ['#08306B', '#2171B5', '#6BAED6', '#C6DBEF',
               '#FFFFCC', '#FED976', '#FD8D3C', '#E31A1C', '#800026']
cmap_ea = LinearSegmentedColormap.from_list('ea_cmap', cmap_colors, N=256)

# Compute all surfaces for consistent color range
all_preds = []
for T_fix in temperatures:
    X_g = np.column_stack([RR.ravel(), NN.ravel(), np.full(RR.size, T_fix)])
    X_gp = poly_s8.transform(X_g)
    pred = gbr_s8_poly.predict(X_gp).reshape(RR.shape)
    all_preds.append(pred)

vmin = min(p.min() for p in all_preds)
vmax = max(p.max() for p in all_preds)

fig_s3, axes = plt.subplots(2, 3, figsize=(15, 9), dpi=300)

for i, (T_fix, pred) in enumerate(zip(temperatures, all_preds)):
    ax = axes[i // 3, i % 3]
    levels = np.linspace(vmin, vmax, 25)
    cf = ax.contourf(RR, NN, pred, levels=levels, cmap=cmap_ea, extend='both')
    ax.contour(RR, NN, pred, levels=8, colors='black', linewidths=0.2, alpha=0.3)

    ax.set_xlabel('R (acid/clay ratio)', fontsize=10)
    ax.set_ylabel('N (liquid/solid ratio)', fontsize=10)
    ax.set_title(f'T = {T_fix} K', fontweight='bold', fontsize=12)

    # Panel label
    ax.text(-0.12, 1.05, f'({chr(97+i)})', transform=ax.transAxes,
            fontsize=13, fontweight='bold', va='bottom')

# Shared colorbar
fig_s3.subplots_adjust(right=0.92, hspace=0.3, wspace=0.28)
cbar_ax = fig_s3.add_axes([0.94, 0.15, 0.02, 0.7])
cbar = fig_s3.colorbar(cf, cax=cbar_ax)
cbar.set_label(r'$E_a$ (eV)', fontsize=12)
cbar.ax.tick_params(labelsize=10)

fig_s3.suptitle(r'$E_a$ Prediction Surfaces at Different Temperatures',
                fontsize=14, fontweight='bold', y=0.98)

save_fig(fig_s3, str(OUT / "figS3_multi_temp_surfaces"))
plt.close(fig_s3)


# ════════════════════════════════════════════════════════════════
# S4: S60 vs S8 Model Comparison
# ════════════════════════════════════════════════════════════════
print("\n--- S4: S60 vs S8 Model Comparison ---")

# S60 metrics
y60_pred = ridge_s60.predict(X60p)
r2_s60   = r2_score(y60, y60_pred)
rmse_s60 = np.sqrt(mean_squared_error(y60, y60_pred))
mae_s60  = mean_absolute_error(y60, y60_pred)
cv_s60   = cross_val_score(ridge_s60, X60p, y60, cv=5, scoring='r2')

# S8 metrics (use raw-feature GBR for honest metrics)
y8_pred = gbr_s8.predict(X8)
r2_s8   = r2_score(y8, y8_pred)
rmse_s8 = np.sqrt(mean_squared_error(y8, y8_pred))
mae_s8  = mean_absolute_error(y8, y8_pred)
cv_s8   = cross_val_score(gbr_s8, X8, y8, cv=5, scoring='r2')

fig_s4, axes = plt.subplots(1, 2, figsize=(11, 5), dpi=300)

# (a) S60 pred vs obs
ax_a = axes[0]
ax_a.scatter(y60, y60_pred, s=35, alpha=0.6, color=C_S60,
             edgecolors='white', linewidths=0.3, zorder=3)
lim = [0, max(y60.max(), y60_pred.max()) * 1.1]
ax_a.plot(lim, lim, '--', color='#888888', linewidth=1.2, zorder=2)
ax_a.set_xlim(lim)
ax_a.set_ylim(lim)
ax_a.set_xlabel(r'$E_a$ actual (eV)')
ax_a.set_ylabel(r'$E_a$ predicted (eV)')
ax_a.set_title('S60 Baseline Model')
ax_a.set_aspect('equal')
ax_a.text(0.05, 0.95,
          f'R$^2$ = {r2_s60:.3f}\n'
          f'RMSE = {rmse_s60:.3f} eV\n'
          f'n = {len(y60)}',
          transform=ax_a.transAxes, fontsize=10, va='top',
          bbox=dict(boxstyle='round,pad=0.4', facecolor='white',
                    edgecolor='black', linewidth=0.6))
ax_a.text(-0.15, 1.05, '(a)', transform=ax_a.transAxes,
          fontsize=14, fontweight='bold', va='bottom')

# (b) S8 pred vs obs
ax_b = axes[1]
y8_pred = gbr_s8.predict(X8)  # re-predict with raw GBR
ax_b.scatter(y8, y8_pred, s=35, alpha=0.6, color=C_S8,
             edgecolors='white', linewidths=0.3, zorder=3)
lim = [0, max(y8.max(), y8_pred.max()) * 1.1]
ax_b.plot(lim, lim, '--', color='#888888', linewidth=1.2, zorder=2)
ax_b.set_xlim(lim)
ax_b.set_ylim(lim)
ax_b.set_xlabel(r'$E_a$ actual (eV)')
ax_b.set_ylabel(r'$E_a$ predicted (eV)')
ax_b.set_title('S8 Confinement Model')
ax_b.set_aspect('equal')
ax_b.text(0.05, 0.95,
          f'R$^2$ = {r2_s8:.3f}\n'
          f'RMSE = {rmse_s8:.3f} eV\n'
          f'n = {len(y8)}',
          transform=ax_b.transAxes, fontsize=10, va='top',
          bbox=dict(boxstyle='round,pad=0.4', facecolor='white',
                    edgecolor='black', linewidth=0.6))
ax_b.text(-0.15, 1.05, '(b)', transform=ax_b.transAxes,
          fontsize=14, fontweight='bold', va='bottom')

plt.tight_layout()
save_fig(fig_s4, str(OUT / "figS4_model_comparison_pred_obs"))
plt.close(fig_s4)


# ════════════════════════════════════════════════════════════════
# S5: Confinement Effect ΔEa Boxplot by Temperature Zone
#     (matching user's Image 2(c) style)
# ════════════════════════════════════════════════════════════════
print("\n--- S5: Confinement Effect ΔEa Boxplot ---")

# Compute ΔEa
X8_baseline = s8[['R', 'T_avg_K']].values
X8_baseline_poly = poly_s60.transform(X8_baseline)
s60_pred_for_s8 = ridge_s60.predict(X8_baseline_poly)
dea = s8['Ea_eV'].values - s60_pred_for_s8
T_vals = s8['T_avg_K'].values

# Assign temperature zones
zones = []
for t in T_vals:
    if t < 230:
        zones.append('Low T\n(<230K)')
    elif t < 270:
        zones.append('Mid T\n(230-270K)')
    else:
        zones.append('High T\n(>270K)')

zone_order = ['Low T\n(<230K)', 'Mid T\n(230-270K)', 'High T\n(>270K)']
zone_colors = [C_S8, '#3A9A6B', C_S60]  # Blue, Teal, Coral

fig_s5, ax = plt.subplots(figsize=(6, 5), dpi=300)

# Prepare data by zone
zone_data = {z: dea[np.array(zones) == z] for z in zone_order}

positions = [0, 1, 2]
for i, (z, col) in enumerate(zip(zone_order, zone_colors)):
    data = zone_data[z]
    bp = ax.boxplot([data], positions=[positions[i]], widths=0.5,
                    patch_artist=True, showmeans=True,
                    meanprops=dict(marker='_', markeredgecolor='black', markerfacecolor='black', markersize=10),
                    medianprops=dict(color='white', linewidth=1.5),
                    boxprops=dict(facecolor=col, alpha=0.6, edgecolor='black', linewidth=0.8),
                    whiskerprops=dict(color='black', linewidth=0.8),
                    capprops=dict(color='black', linewidth=0.8),
                    flierprops=dict(marker='o', markerfacecolor=col, markersize=4, alpha=0.5,
                                    markeredgecolor='none'))
    # Jitter scatter
    jitter = np.random.default_rng(42).uniform(-0.12, 0.12, len(data))
    ax.scatter(np.full_like(data, positions[i]) + jitter, data,
               s=18, alpha=0.5, color=col, edgecolors='none', zorder=2)

# P-value bracket (Low T vs High T)
low_data  = zone_data[zone_order[0]]
high_data = zone_data[zone_order[2]]
t_stat, p_val = stats.ttest_ind(low_data, high_data)

y_max = max(dea.max(), 0.6)
bracket_y = y_max * 1.0
ax.plot([0, 0, 2, 2], [bracket_y - 0.01, bracket_y, bracket_y, bracket_y - 0.01],
        'k-', linewidth=1.0)
sig = '***' if p_val < 0.001 else ('**' if p_val < 0.01 else ('*' if p_val < 0.05 else 'ns'))
ax.text(1, bracket_y + 0.01, f'{sig}\np = {p_val:.1e}', ha='center', va='bottom',
        fontsize=9, fontweight='bold')

# Reference line
ax.axhline(0, color='#888888', linestyle='--', linewidth=0.8, alpha=0.6)

ax.set_xticks(positions)
ax.set_xticklabels(zone_order, fontsize=11)
ax.set_ylabel(r'$\Delta E_a$ (eV)', fontsize=12)
ax.set_title(r'Confinement Effect $\Delta E_a$', fontweight='bold')

plt.tight_layout()
save_fig(fig_s5, str(OUT / "figS5_confinement_boxplot"))
plt.close(fig_s5)


# ════════════════════════════════════════════════════════════════
# Summary
# ════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("SUPPORTING FIGURES GENERATED (Origin style)")
print("=" * 60)
print("  S1: Feature Correlation Matrix")
print("  S2: Partial Dependence Plots (T, R, N)")
print("  S3: Multi-temperature Ea Prediction Surfaces")
print("  S4: S60 vs S8 Model Comparison (pred vs obs)")
print("  S5: Confinement Effect ΔEa Boxplot")
print("=" * 60)

# Print model metrics summary
print("\n--- Model Metrics ---")
print(f"S60 Baseline:    R2={r2_s60:.4f}, RMSE={rmse_s60:.4f}, MAE={mae_s60:.4f}, CV_R2={cv_s60.mean():.4f}+/-{cv_s60.std():.4f}, n={len(y60)} (after outlier removal)")
print(f"S8 Confinement:  R2={r2_s8:.4f}, RMSE={rmse_s8:.4f}, MAE={mae_s8:.4f}, CV_R2={cv_s8.mean():.4f}+/-{cv_s8.std():.4f}, n={len(y8)} (raw features GBR)")
print("\nAll done!")
