# -*- coding: utf-8 -*-
"""
Figure 4: Model Comparison — Radar Chart + Bar Chart
Restored original color scheme + Times New Roman Bold + fixed radar labels.
"""

import sys, io, os, json
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
from pathlib import Path

os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
if sys.platform == 'win32':
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass

SCRIPT_DIR = Path(__file__).resolve().parent

# ════════════════════════════════════════════════════════════════
# Style: Original colors + Times New Roman Bold
# ════════════════════════════════════════════════════════════════
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
        'legend.framealpha': 0.9,
        'legend.edgecolor': '#CCCCCC',
        'lines.linewidth': 2.0,
        'grid.alpha': 0.35,
        'grid.linewidth': 0.8,
        'savefig.dpi': 300,
        'savefig.bbox': 'tight',
        'figure.facecolor': 'white',
    })


# ─── ORIGINAL color scheme ───
MODEL_COLORS = {
    "DeepSeek-R1":    "#4CAF50",   # Green
    "Gemini-2.5-Pro": "#FF9800",   # Orange
    "GPT-5.2-Pro":    "#2196F3",   # Blue
    "Qwen":           "#9C27B0",   # Purple
    "Agent-Enhanced":  "#E91E63",  # Pink (highlight)
}

MODEL_ORDER = ["DeepSeek-R1", "Gemini-2.5-Pro", "GPT-5.2-Pro", "Qwen", "Agent-Enhanced"]

# ─── ORIGINAL dimension labels and keys ───
DIM_LABELS = [
    "Data\nUtilization",
    "Mechanistic\nDepth",
    "Scientific\nAccuracy",
    "Completeness",
    "Logical\nCoherence",
    "Novelty &\nPrediction",
    "Presentation",
]
DIM_KEYS = [
    "D3_data_utilization",
    "D2_mechanistic_depth",
    "D1_scientific_accuracy",
    "D4_completeness",
    "D5_logical_coherence",
    "D6_novelty_predictive",
    "D7_presentation",
]
WEIGHTS = [0.15, 0.20, 0.20, 0.15, 0.10, 0.10, 0.10]
WEIGHT_KEYS = [
    "D3_data_utilization", "D2_mechanistic_depth", "D1_scientific_accuracy",
    "D4_completeness", "D5_logical_coherence", "D6_novelty_predictive", "D7_presentation"
]


def compute_total(scores_dict):
    w_map = {"D1_scientific_accuracy": 0.20, "D2_mechanistic_depth": 0.20,
             "D3_data_utilization": 0.15, "D4_completeness": 0.15,
             "D5_logical_coherence": 0.10, "D6_novelty_predictive": 0.10,
             "D7_presentation": 0.10}
    total = sum(scores_dict.get(k, 0) * w for k, w in w_map.items())
    return total * 10


# ════════════════════════════════════════════════════════════════
# Load Scores
# ════════════════════════════════════════════════════════════════
SCORES_FILE = SCRIPT_DIR / "scores.json"
with open(SCORES_FILE, 'r', encoding='utf-8') as f:
    raw = json.load(f)
if "evaluations" in raw:
    SCORES = {ev["model"]: ev["scores"] for ev in raw["evaluations"]}
else:
    SCORES = raw
print(f"Loaded scores from {SCORES_FILE}")

totals = {m: compute_total(SCORES[m]) for m in MODEL_ORDER}


# ════════════════════════════════════════════════════════════════
# Plot
# ════════════════════════════════════════════════════════════════
setup_style()

fig = plt.figure(figsize=(15, 7), dpi=300)

# ─────────── (a) Radar Chart ───────────
# Use more space on the left for the radar to avoid label clipping
ax_radar = fig.add_axes([0.02, 0.05, 0.48, 0.85], polar=True)

N_dim = len(DIM_LABELS)
angles = np.linspace(0, 2 * np.pi, N_dim, endpoint=False).tolist()
angles += angles[:1]

for model in MODEL_ORDER:
    values = [SCORES[model].get(k, 0) for k in DIM_KEYS]
    values += values[:1]
    color = MODEL_COLORS[model]
    is_ours = (model == "Agent-Enhanced")
    lw = 2.5 if is_ours else 1.8
    alpha_fill = 0.15 if is_ours else 0.05
    zorder = 10 if is_ours else 5

    ax_radar.plot(angles, values, 'o-', color=color, linewidth=lw,
                  markersize=4, label=model, zorder=zorder)
    ax_radar.fill(angles, values, alpha=alpha_fill, color=color, zorder=zorder - 1)

# Customize radar
ax_radar.set_xticks(angles[:-1])
ax_radar.set_xticklabels(DIM_LABELS, fontsize=11, fontweight='bold')

# Push labels outward so they don't overlap with the chart
ax_radar.tick_params(axis='x', pad=18)

ax_radar.set_ylim(0, 10)
ax_radar.set_yticks([2, 4, 6, 8, 10])
ax_radar.set_yticklabels(['2', '4', '6', '8', '10'], fontsize=10, color='#666')
ax_radar.set_rlabel_position(30)

# Grid styling
ax_radar.spines['polar'].set_color('#ddd')
ax_radar.grid(color='#ddd', linewidth=0.6)

# Legend — placed at the top center of the figure
handles, labels = ax_radar.get_legend_handles_labels()
fig.legend(handles, labels, loc='upper center',
           bbox_to_anchor=(0.50, 0.99), ncol=5,
           fontsize=10, framealpha=0.9, edgecolor='#ccc',
           handlelength=1.5, columnspacing=1.0)

ax_radar.set_title('Multi-Dimensional Evaluation', fontsize=15,
                    fontweight='bold', pad=25)
fig.text(0.01, 0.92, '(a)', fontsize=18, fontweight='bold', fontfamily='serif')

# ─────────── (b) Bar Chart ───────────
ax_bar = fig.add_axes([0.56, 0.12, 0.41, 0.78])

models_sorted = sorted(MODEL_ORDER, key=lambda m: totals[m], reverse=True)
bars_y = range(len(models_sorted))
bar_values = [totals[m] for m in models_sorted]
bar_colors = [MODEL_COLORS[m] for m in models_sorted]

bars = ax_bar.barh(bars_y, bar_values, color=bar_colors, height=0.6,
                   edgecolor='white', linewidth=1.5, zorder=3)

# Highlight Agent-Enhanced bar
for i, m in enumerate(models_sorted):
    if m == "Agent-Enhanced":
        bars[i].set_edgecolor('#E91E63')
        bars[i].set_linewidth(2.5)

# Value labels
for i, (m, v) in enumerate(zip(models_sorted, bar_values)):
    ax_bar.text(v + 0.8, i, f'{v:.1f}', va='center', ha='left',
                fontsize=12, fontweight='bold', color=MODEL_COLORS[m])

# Display names
display_names = {
    "DeepSeek-R1": "DeepSeek-R1",
    "Gemini-2.5-Pro": "Gemini 2.5 Pro",
    "GPT-5.2-Pro": "GPT-5.2 Pro",
    "Qwen": "Qwen",
    "Agent-Enhanced": "Agent-Enhanced\n(Ours)",
}
ax_bar.set_yticks(list(bars_y))
ax_bar.set_yticklabels([display_names.get(m, m) for m in models_sorted],
                       fontsize=12, fontweight='bold')
ax_bar.set_xlabel('Weighted Total Score (0\u2013100)', fontsize=14, fontweight='bold')
ax_bar.set_title('Overall Performance Ranking', fontsize=15, fontweight='bold')
ax_bar.set_xlim(0, max(bar_values) + 12)
ax_bar.grid(axis='x', alpha=0.25, linewidth=0.6)
ax_bar.invert_yaxis()

# Bold tick labels
for label in ax_bar.get_xticklabels() + ax_bar.get_yticklabels():
    label.set_fontweight('bold')

# Weight annotation
weight_text = (
    "Weights: Accuracy 20%, Depth 20%,\n"
    "Data 15%, Complete 15%, Logic 10%,\n"
    "Novelty 10%, Presentation 10%"
)
ax_bar.text(0.98, 0.03, weight_text, transform=ax_bar.transAxes,
            fontsize=9, ha='right', va='bottom',
            bbox=dict(boxstyle='round,pad=0.3', facecolor='#f5f5f5',
                      edgecolor='#ccc', alpha=0.9))

fig.text(0.54, 0.92, '(b)', fontsize=18, fontweight='bold', fontfamily='serif')

# Save
out_path = str(SCRIPT_DIR / "figure4_model_comparison")
fig.savefig(f'{out_path}.png', dpi=300, bbox_inches='tight', facecolor='white')
fig.savefig(f'{out_path}.pdf', bbox_inches='tight', facecolor='white')
print(f'Saved: {out_path}.png')
print(f'Saved: {out_path}.pdf')
plt.close(fig)

# Summary
print("\n" + "=" * 50)
for m in models_sorted:
    print(f"  {m:<20} {totals[m]:>6.1f}")
print("=" * 50)
print("Done!")
