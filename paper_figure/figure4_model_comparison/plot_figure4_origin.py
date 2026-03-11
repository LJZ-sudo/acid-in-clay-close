# -*- coding: utf-8 -*-
"""
Figure 4: Model Comparison — Radar Chart + Bar Chart
Origin-matching style (Times New Roman, white bg, academic colors).
"""

import sys, io, os, json
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
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
# Origin Style
# ════════════════════════════════════════════════════════════════
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
        'legend.fontsize': 9,
        'legend.frameon': True,
        'legend.framealpha': 1.0,
        'legend.edgecolor': 'black',
        'legend.fancybox': False,
        'lines.linewidth': 1.5,
        'axes.grid': False,
        'savefig.dpi': 300,
        'savefig.bbox': 'tight',
        'figure.facecolor': 'white',
    })


# ─── Colors — muted academic palette ───
MODEL_COLORS = {
    "Agent-Enhanced":  '#4A7FB5',  # Steel blue (highlight — ours)
    "GPT-5.2-Pro":     '#CC6666',  # Muted coral
    "DeepSeek-R1":     '#5A9A6B',  # Muted green
    "Qwen":            '#8B6BAE',  # Muted purple
    "Gemini-2.5-Pro":  '#C9963A',  # Muted gold
}

MODEL_ORDER = ["Agent-Enhanced", "GPT-5.2-Pro", "DeepSeek-R1", "Qwen", "Gemini-2.5-Pro"]

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
WEIGHTS = {
    "D1_scientific_accuracy": 0.20,
    "D2_mechanistic_depth": 0.20,
    "D3_data_utilization": 0.15,
    "D4_completeness": 0.15,
    "D5_logical_coherence": 0.10,
    "D6_novelty_predictive": 0.10,
    "D7_presentation": 0.10,
}


def compute_total(scores_dict):
    total = 0
    for key, w in WEIGHTS.items():
        total += scores_dict.get(key, 0) * w
    return total * 10  # scale to 0-100


# ════════════════════════════════════════════════════════════════
# Load Scores
# ════════════════════════════════════════════════════════════════
SCORES_FILE = SCRIPT_DIR / "scores.json"
if SCORES_FILE.exists():
    with open(SCORES_FILE, 'r', encoding='utf-8') as f:
        raw = json.load(f)
    if "evaluations" in raw:
        SCORES = {ev["model"]: ev["scores"] for ev in raw["evaluations"]}
    else:
        SCORES = raw
    print(f"Loaded scores from {SCORES_FILE}")
else:
    raise FileNotFoundError(f"scores.json not found at {SCORES_FILE}")

totals = {m: compute_total(SCORES[m]) for m in MODEL_ORDER}


# ════════════════════════════════════════════════════════════════
# Plot
# ════════════════════════════════════════════════════════════════
setup_origin_style()

fig = plt.figure(figsize=(14, 5.5), dpi=300)

# ───────────── (a) Radar Chart ─────────────
ax_radar = fig.add_subplot(121, polar=True)

N_dim = len(DIM_LABELS)
angles = np.linspace(0, 2 * np.pi, N_dim, endpoint=False).tolist()
angles += angles[:1]

for model in MODEL_ORDER:
    values = [SCORES[model].get(k, 0) for k in DIM_KEYS]
    values += values[:1]
    color = MODEL_COLORS[model]
    is_ours = (model == "Agent-Enhanced")
    lw = 2.5 if is_ours else 1.5
    alpha_fill = 0.18 if is_ours else 0.04
    marker = 'o' if is_ours else 's'
    ms = 5 if is_ours else 3
    zorder = 10 if is_ours else 5

    ax_radar.plot(angles, values, marker + '-', color=color, linewidth=lw,
                  markersize=ms, label=model, zorder=zorder, markeredgecolor='white',
                  markeredgewidth=0.3)
    ax_radar.fill(angles, values, alpha=alpha_fill, color=color, zorder=zorder - 1)

ax_radar.set_xticks(angles[:-1])
ax_radar.set_xticklabels(DIM_LABELS, fontsize=8.5, fontweight='bold')
ax_radar.set_ylim(0, 10)
ax_radar.set_yticks([2, 4, 6, 8, 10])
ax_radar.set_yticklabels(['2', '4', '6', '8', '10'], fontsize=7, color='#555')
ax_radar.set_rlabel_position(30)

# Grid styling — subtle
ax_radar.spines['polar'].set_color('#bbb')
ax_radar.spines['polar'].set_linewidth(0.8)
ax_radar.grid(color='#ccc', linewidth=0.5)

# Legend
ax_radar.legend(loc='upper right', bbox_to_anchor=(1.38, 1.12),
                fontsize=8.5, framealpha=1.0, edgecolor='black',
                fancybox=False, handlelength=1.5)

ax_radar.set_title('Multi-Dimensional Evaluation', fontsize=12,
                    fontweight='bold', pad=22)
fig.text(0.02, 0.95, '(a)', fontsize=16, fontweight='bold',
         fontfamily='serif')

# ───────────── (b) Bar Chart ─────────────
ax_bar = fig.add_subplot(122)

models_sorted = sorted(MODEL_ORDER, key=lambda m: totals[m], reverse=True)
bars_y = range(len(models_sorted))
bar_values = [totals[m] for m in models_sorted]
bar_colors = [MODEL_COLORS[m] for m in models_sorted]

bars = ax_bar.barh(bars_y, bar_values, color=bar_colors, height=0.55,
                   edgecolor='black', linewidth=0.6, zorder=3)

# Highlight Agent-Enhanced
for i, m in enumerate(models_sorted):
    if m == "Agent-Enhanced":
        bars[i].set_edgecolor('#2C4A6E')
        bars[i].set_linewidth(1.5)

# Value labels
for i, (m, v) in enumerate(zip(models_sorted, bar_values)):
    ax_bar.text(v + 1.0, i, f'{v:.1f}', va='center', ha='left',
                fontsize=10, fontweight='bold', color=MODEL_COLORS[m])

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
                       fontsize=10, fontweight='bold')
ax_bar.set_xlabel('Weighted Total Score (0\u2013100)', fontsize=11)
ax_bar.set_title('Overall Performance Ranking', fontsize=12, fontweight='bold')
ax_bar.set_xlim(0, max(bar_values) + 12)
ax_bar.invert_yaxis()

# Subtle grid on x
ax_bar.xaxis.grid(True, alpha=0.2, linewidth=0.5, color='#aaa')
ax_bar.set_axisbelow(True)

# Weight annotation
weight_text = (
    "Weights: Accuracy 20%, Depth 20%,\n"
    "Data 15%, Complete 15%, Logic 10%,\n"
    "Novelty 10%, Presentation 10%"
)
ax_bar.text(0.98, 0.03, weight_text, transform=ax_bar.transAxes,
            fontsize=7.5, ha='right', va='bottom',
            bbox=dict(boxstyle='round,pad=0.3', facecolor='white',
                      edgecolor='black', alpha=0.95, linewidth=0.5))

fig.text(0.49, 0.95, '(b)', fontsize=16, fontweight='bold',
         fontfamily='serif')

plt.tight_layout(rect=[0.02, 0.02, 0.98, 0.93])

# Save
out_path = str(SCRIPT_DIR / "figure4_model_comparison")
fig.savefig(f'{out_path}.png', dpi=300, bbox_inches='tight', facecolor='white')
fig.savefig(f'{out_path}.pdf', bbox_inches='tight', facecolor='white')
print(f'Saved: {out_path}.png')
print(f'Saved: {out_path}.pdf')
plt.close(fig)

# Print summary
print("\n" + "=" * 70)
print("MODEL COMPARISON SUMMARY (Origin style)")
print("=" * 70)
print(f"{'Model':<20} {'Score':>7}")
print("-" * 30)
for m in models_sorted:
    print(f"{m:<20} {totals[m]:>7.1f}")
print("=" * 70)
print("Done!")
