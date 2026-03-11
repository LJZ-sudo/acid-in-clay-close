# -*- coding: utf-8 -*-
"""
Figure 4: Model Comparison — Individual sub-figures
  (a) Radar Chart — Multi-Dimensional Evaluation
  (b) Bar Chart — Overall Performance Ranking
Generates separate PNG/PDF for each, easy to combine in PPT.
"""

import sys, io, os, json
import numpy as np
import matplotlib
matplotlib.use('Agg')
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
# Unified Style (same as Figure 3)
# ════════════════════════════════════════════════════════════════
def setup_style():
    plt.rcParams.update({
        'font.family': 'serif',
        'font.serif': ['Times New Roman', 'DejaVu Serif'],
        'font.size': 12,
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


def save_fig(fig, path_stem):
    fig.savefig(f'{path_stem}.png', dpi=300, bbox_inches='tight', facecolor='white')
    fig.savefig(f'{path_stem}.pdf', bbox_inches='tight', facecolor='white')
    print(f'  Saved: {path_stem}.png')
    print(f'  Saved: {path_stem}.pdf')


# ─── Colors ───
MODEL_COLORS = {
    "DeepSeek-R1":    "#4CAF50",
    "Gemini-2.5-Pro": "#FF9800",
    "GPT-5.2-Pro":    "#2196F3",
    "Qwen":           "#9C27B0",
    "Agent-Enhanced":  "#E91E63",
}
MODEL_ORDER = ["DeepSeek-R1", "Gemini-2.5-Pro", "GPT-5.2-Pro", "Qwen", "Agent-Enhanced"]

DIM_LABELS = [
    "Data\nUtilization", "Mechanistic\nDepth", "Scientific\nAccuracy",
    "Completeness", "Logical\nCoherence", "Novelty &\nPrediction", "Presentation",
]
DIM_KEYS = [
    "D3_data_utilization", "D2_mechanistic_depth", "D1_scientific_accuracy",
    "D4_completeness", "D5_logical_coherence", "D6_novelty_predictive", "D7_presentation",
]


def compute_total(scores_dict):
    w_map = {"D1_scientific_accuracy": 0.20, "D2_mechanistic_depth": 0.20,
             "D3_data_utilization": 0.15, "D4_completeness": 0.15,
             "D5_logical_coherence": 0.10, "D6_novelty_predictive": 0.10,
             "D7_presentation": 0.10}
    return sum(scores_dict.get(k, 0) * w for k, w in w_map.items()) * 10


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
models_sorted = sorted(MODEL_ORDER, key=lambda m: totals[m], reverse=True)

setup_style()


# ════════════════════════════════════════════════════════════════
# (a) Radar Chart — Individual
# ════════════════════════════════════════════════════════════════
print("Generating (a) Radar Chart ...")

fig_a, ax_r = plt.subplots(figsize=(8, 8), dpi=300, subplot_kw=dict(polar=True))

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

    ax_r.plot(angles, values, 'o-', color=color, linewidth=lw,
              markersize=5, label=model, zorder=zorder)
    ax_r.fill(angles, values, alpha=alpha_fill, color=color, zorder=zorder - 1)

ax_r.set_xticks(angles[:-1])
ax_r.set_xticklabels(DIM_LABELS, fontsize=14, fontweight='bold')
ax_r.tick_params(axis='x', pad=28)

ax_r.set_ylim(0, 10)
ax_r.set_yticks([2, 4, 6, 8, 10])
ax_r.set_yticklabels(['2', '4', '6', '8', '10'], fontsize=10, fontweight='bold', color='#666')
ax_r.set_rlabel_position(30)

ax_r.spines['polar'].set_color('#ddd')
ax_r.grid(color='#ddd', linewidth=0.6)

ax_r.legend(loc='upper right', bbox_to_anchor=(1.25, 1.10),
            fontsize=10, framealpha=0.9, edgecolor='#ccc')

ax_r.set_title('Multi-Dimensional Evaluation', fontsize=15,
                fontweight='bold', pad=25)

fig_a.text(0.02, 0.95, '(a)', fontsize=18, fontweight='bold', fontfamily='serif')

plt.tight_layout()
save_fig(fig_a, str(SCRIPT_DIR / "figure4a_radar"))
plt.close(fig_a)
print("  Done: (a) Radar Chart")


# ════════════════════════════════════════════════════════════════
# (b) Bar Chart — Individual
# ════════════════════════════════════════════════════════════════
print("Generating (b) Bar Chart ...")

fig_b, ax_b = plt.subplots(figsize=(8, 5), dpi=300)

bars_y = range(len(models_sorted))
bar_values = [totals[m] for m in models_sorted]
bar_colors = [MODEL_COLORS[m] for m in models_sorted]

bars = ax_b.barh(bars_y, bar_values, color=bar_colors, height=0.6,
                 edgecolor='white', linewidth=1.5, zorder=3)

# Highlight Agent-Enhanced
for i, m in enumerate(models_sorted):
    if m == "Agent-Enhanced":
        bars[i].set_edgecolor('#E91E63')
        bars[i].set_linewidth(2.5)

# Value labels
for i, (m, v) in enumerate(zip(models_sorted, bar_values)):
    ax_b.text(v + 0.8, i, f'{v:.1f}', va='center', ha='left',
              fontsize=12, fontweight='bold', color=MODEL_COLORS[m])

# Display names
display_names = {
    "DeepSeek-R1": "DeepSeek-R1",
    "Gemini-2.5-Pro": "Gemini 2.5 Pro",
    "GPT-5.2-Pro": "GPT-5.2 Pro",
    "Qwen": "Qwen",
    "Agent-Enhanced": "Agent-Enhanced\n(Ours)",
}
ax_b.set_yticks(list(bars_y))
ax_b.set_yticklabels([display_names.get(m, m) for m in models_sorted],
                     fontsize=12, fontweight='bold')
ax_b.set_xlabel('Weighted Total Score (0\u2013100)', fontsize=14, fontweight='bold')
ax_b.set_title('Overall Performance Ranking', fontsize=15, fontweight='bold')
ax_b.set_xlim(0, max(bar_values) + 12)
ax_b.grid(axis='x', alpha=0.25, linewidth=0.6)
ax_b.invert_yaxis()

# Bold tick labels
for label in ax_b.get_xticklabels() + ax_b.get_yticklabels():
    label.set_fontweight('bold')

# Weight annotation
weight_text = (
    "Weights: Accuracy 20%, Depth 20%,\n"
    "Data 15%, Complete 15%, Logic 10%,\n"
    "Novelty 10%, Presentation 10%"
)
ax_b.text(0.98, 0.03, weight_text, transform=ax_b.transAxes,
          fontsize=10, ha='right', va='bottom', fontweight='bold',
          bbox=dict(boxstyle='round,pad=0.3', facecolor='#f5f5f5',
                    edgecolor='#ccc', alpha=0.9))

fig_b.text(0.02, 0.95, '(b)', fontsize=18, fontweight='bold', fontfamily='serif')

plt.tight_layout()
save_fig(fig_b, str(SCRIPT_DIR / "figure4b_bar"))
plt.close(fig_b)
print("  Done: (b) Bar Chart")


# ════════════════════════════════════════════════════════════════
# Summary
# ════════════════════════════════════════════════════════════════
print("\n" + "=" * 50)
print("Model Ranking:")
for m in models_sorted:
    print(f"  {m:<20} {totals[m]:>6.1f}")
print("=" * 50)
print("\n=== Figure 4a & 4b individual images generated! ===")
