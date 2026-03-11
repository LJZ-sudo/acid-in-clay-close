# -*- coding: utf-8 -*-
"""
Ea Prediction Surface at T=210K — ML model prediction heatmap.

Trains a GradientBoostingRegressor on S8 data, then generates
a smooth prediction surface over (R, N) grid at fixed T=210K.

Origin-matching style (Times New Roman, white bg).
"""

import sys, io, os
import numpy as np
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from pathlib import Path

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
        'axes.labelsize': 13,
        'axes.titlesize': 14,
        'axes.titleweight': 'bold',
        'axes.linewidth': 1.2,
        'axes.facecolor': 'white',
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
        'legend.fontsize': 10,
        'legend.frameon': True,
        'legend.framealpha': 1.0,
        'legend.edgecolor': 'black',
        'legend.fancybox': False,
        'axes.grid': False,
        'savefig.dpi': 300,
        'savefig.bbox': 'tight',
        'figure.facecolor': 'white',
    })


# ════════════════════════════════════════════════════════════════
# Load & Train
# ════════════════════════════════════════════════════════════════
setup_origin_style()

csv_path = PHASE3V2_DIR / "integrated_data.csv"
df = pd.read_csv(csv_path)
s8 = df[(df['material_type'] == 'S8') & (df['segment'] != 'full_range')].copy()
s8 = s8.dropna(subset=['R', 'N', 'T_avg_K', 'Ea_eV'])

print(f"S8 data: {len(s8)} samples")
print(f"  R range:  {s8['R'].min():.3f} - {s8['R'].max():.3f}")
print(f"  N range:  {s8['N'].min():.3f} - {s8['N'].max():.3f}")
print(f"  T range:  {s8['T_avg_K'].min():.1f} - {s8['T_avg_K'].max():.1f} K")
print(f"  Ea range: {s8['Ea_eV'].min():.3f} - {s8['Ea_eV'].max():.3f} eV")

# Features: R, N, T + interactions
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.preprocessing import PolynomialFeatures
from sklearn.model_selection import cross_val_score

features = ['R', 'N', 'T_avg_K']
X = s8[features].values
y = s8['Ea_eV'].values

# Add interaction features
poly = PolynomialFeatures(2, include_bias=False, interaction_only=False)
Xp = poly.fit_transform(X)

# Train GBR model
gbr = GradientBoostingRegressor(
    n_estimators=200,
    max_depth=4,
    learning_rate=0.1,
    min_samples_split=5,
    min_samples_leaf=3,
    subsample=0.8,
    random_state=42
)
gbr.fit(Xp, y)

# Evaluate
from sklearn.metrics import r2_score, mean_squared_error
y_pred = gbr.predict(Xp)
r2_train = r2_score(y, y_pred)
rmse_train = np.sqrt(mean_squared_error(y, y_pred))
print(f"\nModel: GBR (n_estimators=200, max_depth=4)")
print(f"  Train R2:   {r2_train:.4f}")
print(f"  Train RMSE: {rmse_train:.4f} eV")

# CV score
cv_scores = cross_val_score(gbr, Xp, y, cv=5, scoring='r2')
print(f"  CV R2:      {cv_scores.mean():.4f} +/- {cv_scores.std():.4f}")


# ════════════════════════════════════════════════════════════════
# Prediction Surface at T=210K
# ════════════════════════════════════════════════════════════════
T_fixed = 210.0  # K

R_grid = np.linspace(0.0, 1.05, 200)
N_grid = np.linspace(1.0, 7.1, 200)
RR, NN = np.meshgrid(R_grid, N_grid)

# Build prediction input
X_grid = np.column_stack([
    RR.ravel(),
    NN.ravel(),
    np.full(RR.size, T_fixed)
])
X_grid_poly = poly.transform(X_grid)
Ea_pred = gbr.predict(X_grid_poly).reshape(RR.shape)

print(f"\nPrediction surface at T={T_fixed}K:")
print(f"  Ea range: {Ea_pred.min():.3f} - {Ea_pred.max():.3f} eV")


# ════════════════════════════════════════════════════════════════
# Plot — Origin style, matching user's Image 2(d)
# ════════════════════════════════════════════════════════════════
fig, ax = plt.subplots(figsize=(7, 5.5), dpi=300)

# Custom colormap: blue (low Ea) → yellow → red (high Ea)
cmap_colors = ['#08306B', '#2171B5', '#6BAED6', '#C6DBEF',
               '#FFFFCC', '#FED976', '#FD8D3C', '#E31A1C', '#800026']
cmap = LinearSegmentedColormap.from_list('ea_cmap', cmap_colors, N=256)

# Filled contour
levels = np.linspace(Ea_pred.min(), Ea_pred.max(), 30)
cf = ax.contourf(RR, NN, Ea_pred, levels=levels, cmap=cmap, extend='both')

# Contour lines
cl = ax.contour(RR, NN, Ea_pred, levels=np.linspace(Ea_pred.min(), Ea_pred.max(), 10),
                colors='black', linewidths=0.3, alpha=0.4)

# Colorbar
cbar = plt.colorbar(cf, ax=ax, shrink=0.9, pad=0.02)
cbar.set_label(r'$E_a$ (eV)', fontsize=12)
cbar.ax.tick_params(labelsize=10)

# Mark actual data points (S8 samples near T=210K)
T_tol = 15  # K tolerance for nearby data
nearby = s8[(s8['T_avg_K'] >= T_fixed - T_tol) & (s8['T_avg_K'] <= T_fixed + T_tol)]
if len(nearby) > 0:
    ax.scatter(nearby['R'].values, nearby['N'].values,
               c='white', s=25, edgecolors='black', linewidths=0.8,
               zorder=5, alpha=0.9, label=f'Data ({T_fixed:.0f}' + r'$\pm$' + f'{T_tol}K, n={len(nearby)})')

# Mark optimal regions (low Ea zones) with dashed boxes
# Find regions where Ea < threshold
threshold_low = np.percentile(Ea_pred, 15)
# Draw dashed rectangles around low-Ea regions
from matplotlib.patches import Rectangle

# Identify low-Ea clusters
low_mask = Ea_pred < threshold_low
# Find bounding boxes of connected low-Ea regions
from scipy import ndimage
labeled, n_features = ndimage.label(low_mask)
print(f"  Found {n_features} low-Ea optimal region(s)")

for region_id in range(1, min(n_features + 1, 4)):  # max 3 boxes
    ys, xs = np.where(labeled == region_id)
    if len(xs) < 20:  # skip tiny regions
        continue
    r_min, r_max = R_grid[xs.min()], R_grid[xs.max()]
    n_min, n_max = N_grid[ys.min()], N_grid[ys.max()]
    # Add padding
    pad_r = (r_max - r_min) * 0.08
    pad_n = (n_max - n_min) * 0.08
    rect = Rectangle(
        (r_min - pad_r, n_min - pad_n),
        (r_max - r_min) + 2*pad_r,
        (n_max - n_min) + 2*pad_n,
        linewidth=1.8, edgecolor='black', facecolor='none',
        linestyle='--', zorder=6
    )
    ax.add_patch(rect)

# Labels
ax.set_xlabel(r'R (acid/clay molar ratio)', fontsize=13)
ax.set_ylabel(r'N (liquid/solid ratio)', fontsize=13)
ax.set_title(f'$E_a$ Prediction (T = {T_fixed:.0f} K)', fontsize=14, fontweight='bold')

if len(nearby) > 0:
    ax.legend(fontsize=9, loc='upper right', framealpha=1.0,
              edgecolor='black', fancybox=False)

# Panel label
ax.text(-0.12, 1.03, '(d)', transform=ax.transAxes,
        fontsize=16, fontweight='bold', va='bottom')

plt.tight_layout()
out_path = str(OUT / "figure_ea_prediction_T210K")
fig.savefig(f'{out_path}.png', dpi=300, bbox_inches='tight', facecolor='white')
fig.savefig(f'{out_path}.pdf', bbox_inches='tight', facecolor='white')
print(f'\nSaved: {out_path}.png')
print(f'Saved: {out_path}.pdf')
plt.close(fig)

print("\n=== Ea Prediction Surface (T=210K) generated! ===")
