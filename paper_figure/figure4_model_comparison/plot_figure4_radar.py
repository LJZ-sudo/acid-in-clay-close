# -*- coding: utf-8 -*-
"""
Figure 4: Model Comparison — Radar Chart + Bar Chart

Layout: (a) Radar chart of 7 dimensions  (b) Weighted total bar chart
Style: Advanced Materials (AM) journal format

Usage:
  1. Run with placeholder data:  python plot_figure4_radar.py
  2. After getting real scores, edit SCORES dict below, then re-run.
"""

import sys, os, json
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from pathlib import Path

os.environ.setdefault('PYTHONIOENCODING', 'utf-8')

SCRIPT_DIR = Path(__file__).resolve().parent
PAPER_FIG_DIR = SCRIPT_DIR.parent

sys.path.insert(0, str(PAPER_FIG_DIR))
from am_style_config import setup_am_style, save_figure, add_panel_label

setup_am_style()

# ============================================================
# ★★★  SCORES — 替换为真实评分后重新运行  ★★★
# ============================================================
# 如果存在 scores.json 文件，自动加载；否则使用下方占位数据
SCORES_FILE = SCRIPT_DIR / "scores.json"

# 占位数据 (placeholder) — 等待用户提供真实评分
PLACEHOLDER_SCORES = {
    "DeepSeek-R1": {
        "D1_scientific_accuracy": 7,
        "D2_mechanistic_depth": 7,
        "D3_data_utilization": 7,
        "D4_completeness": 7,
        "D5_logical_coherence": 7,
        "D6_novelty_predictive": 6,
        "D7_presentation": 7,
    },
    "Gemini-2.5-Pro": {
        "D1_scientific_accuracy": 7,
        "D2_mechanistic_depth": 6,
        "D3_data_utilization": 6,
        "D4_completeness": 6,
        "D5_logical_coherence": 6,
        "D6_novelty_predictive": 5,
        "D7_presentation": 6,
    },
    "GPT-5.2-Pro": {
        "D1_scientific_accuracy": 8,
        "D2_mechanistic_depth": 8,
        "D3_data_utilization": 7,
        "D4_completeness": 8,
        "D5_logical_coherence": 8,
        "D6_novelty_predictive": 7,
        "D7_presentation": 8,
    },
    "Qwen": {
        "D1_scientific_accuracy": 7,
        "D2_mechanistic_depth": 7,
        "D3_data_utilization": 6,
        "D4_completeness": 7,
        "D5_logical_coherence": 7,
        "D6_novelty_predictive": 6,
        "D7_presentation": 7,
    },
    "Agent-Enhanced": {
        "D1_scientific_accuracy": 8,
        "D2_mechanistic_depth": 8,
        "D3_data_utilization": 9,
        "D4_completeness": 8,
        "D5_logical_coherence": 8,
        "D6_novelty_predictive": 8,
        "D7_presentation": 8,
    },
}

# ============================================================
# Load scores
# ============================================================
if SCORES_FILE.exists():
    with open(SCORES_FILE, 'r', encoding='utf-8') as f:
        raw = json.load(f)
    # Support both direct dict and {"evaluations": [...]} format
    if "evaluations" in raw:
        SCORES = {}
        for ev in raw["evaluations"]:
            SCORES[ev["model"]] = ev["scores"]
        print(f"Loaded real scores from {SCORES_FILE}")
    else:
        SCORES = raw
        print(f"Loaded real scores from {SCORES_FILE}")
    USE_PLACEHOLDER = False
else:
    SCORES = PLACEHOLDER_SCORES
    USE_PLACEHOLDER = True
    print("Using PLACEHOLDER scores. Replace with real data in scores.json.")

# ============================================================
# Dimension labels and weights
# ============================================================
DIM_LABELS = [
    "Scientific\nAccuracy",
    "Mechanistic\nDepth",
    "Data\nUtilization",
    "Completeness",
    "Logical\nCoherence",
    "Novelty &\nPrediction",
    "Presentation",
]
DIM_KEYS = [
    "D1_scientific_accuracy",
    "D2_mechanistic_depth",
    "D3_data_utilization",
    "D4_completeness",
    "D5_logical_coherence",
    "D6_novelty_predictive",
    "D7_presentation",
]
WEIGHTS = [0.20, 0.20, 0.15, 0.15, 0.10, 0.10, 0.10]

# ============================================================
# Model colors (AM-style, distinctive)
# ============================================================
MODEL_COLORS = {
    "DeepSeek-R1":    "#4CAF50",   # Green
    "Gemini-2.5-Pro": "#FF9800",   # Orange
    "GPT-5.2-Pro":    "#2196F3",   # Blue
    "Qwen":           "#9C27B0",   # Purple
    "Agent-Enhanced":  "#E91E63",  # Pink (highlight)
}

MODEL_ORDER = ["DeepSeek-R1", "Gemini-2.5-Pro", "GPT-5.2-Pro", "Qwen", "Agent-Enhanced"]

# ============================================================
# Compute weighted totals
# ============================================================
def compute_total(scores_dict):
    total = 0
    for key, w in zip(DIM_KEYS, WEIGHTS):
        total += scores_dict.get(key, 0) * w
    return total * 10  # scale to 0-100


totals = {m: compute_total(SCORES[m]) for m in MODEL_ORDER}

# ============================================================
# (a) Radar Chart
# ============================================================
fig = plt.figure(figsize=(14, 6), dpi=300)

ax_radar = fig.add_subplot(121, polar=True)

N = len(DIM_LABELS)
angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
angles += angles[:1]  # close the polygon

# Plot each model
for model in MODEL_ORDER:
    values = [SCORES[model].get(k, 0) for k in DIM_KEYS]
    values += values[:1]
    color = MODEL_COLORS[model]
    lw = 2.5 if model == "Agent-Enhanced" else 1.8
    alpha_fill = 0.15 if model == "Agent-Enhanced" else 0.05
    zorder = 10 if model == "Agent-Enhanced" else 5

    ax_radar.plot(angles, values, 'o-', color=color, linewidth=lw,
                  markersize=4, label=model, zorder=zorder)
    ax_radar.fill(angles, values, alpha=alpha_fill, color=color, zorder=zorder - 1)

# Customize radar
ax_radar.set_xticks(angles[:-1])
ax_radar.set_xticklabels(DIM_LABELS, fontsize=8, fontweight='bold')
ax_radar.set_ylim(0, 10)
ax_radar.set_yticks([2, 4, 6, 8, 10])
ax_radar.set_yticklabels(['2', '4', '6', '8', '10'], fontsize=7, color='#666')
ax_radar.set_rlabel_position(30)

# Grid styling
ax_radar.spines['polar'].set_color('#ddd')
ax_radar.grid(color='#ddd', linewidth=0.6)

# Legend
ax_radar.legend(loc='upper right', bbox_to_anchor=(1.35, 1.15),
                fontsize=8, framealpha=0.9, edgecolor='#ccc')

# Panel label
ax_radar.set_title('Multi-Dimensional Evaluation', fontsize=12,
                    fontweight='bold', pad=20)
fig.text(0.02, 0.95, '(a)', fontsize=16, fontweight='bold')

# ============================================================
# (b) Weighted Total Bar Chart
# ============================================================
ax_bar = fig.add_subplot(122)

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
    label = f'{v:.1f}'
    ax_bar.text(v + 0.8, i, label, va='center', ha='left',
                fontsize=10, fontweight='bold', color=MODEL_COLORS[m])

# Display names
display_names = {
    "DeepSeek-R1": "DeepSeek-R1",
    "Gemini-2.5-Pro": "Gemini 2.5 Pro",
    "GPT-5.2-Pro": "GPT-5.2 Pro",
    "Qwen": "Qwen",
    "Agent-Enhanced": "Agent-Enhanced\n(Ours)",
}
ax_bar.set_yticks(bars_y)
ax_bar.set_yticklabels([display_names.get(m, m) for m in models_sorted],
                       fontsize=9, fontweight='bold')
ax_bar.set_xlabel('Weighted Total Score (0\u2013100)', fontsize=11)
ax_bar.set_title('Overall Performance Ranking', fontsize=12, fontweight='bold')
ax_bar.set_xlim(0, max(bar_values) + 12)
ax_bar.grid(axis='x', alpha=0.25, linewidth=0.6)
ax_bar.invert_yaxis()

# Add weight legend as text
weight_text = (
    "Weights: Accuracy 20%, Depth 20%,\n"
    "Data 15%, Complete 15%, Logic 10%,\n"
    "Novelty 10%, Presentation 10%"
)
ax_bar.text(0.98, 0.02, weight_text, transform=ax_bar.transAxes,
            fontsize=7, ha='right', va='bottom',
            bbox=dict(boxstyle='round,pad=0.3', facecolor='#f5f5f5',
                      edgecolor='#ccc', alpha=0.9))

fig.text(0.48, 0.95, '(b)', fontsize=16, fontweight='bold')

# Placeholder watermark
if USE_PLACEHOLDER:
    fig.text(0.5, 0.5, 'PLACEHOLDER DATA\nReplace with real scores',
             ha='center', va='center', fontsize=28, color='red',
             alpha=0.15, fontweight='bold', rotation=30,
             transform=fig.transFigure)

plt.tight_layout(rect=[0.02, 0.02, 0.98, 0.93])
save_figure(fig, str(SCRIPT_DIR / "figure4_model_comparison"), dpi=300)
plt.close(fig)

# ============================================================
# Print summary table
# ============================================================
print("\n" + "=" * 70)
print("MODEL COMPARISON SUMMARY")
print("=" * 70)
print(f"{'Model':<20} {'D1':>4} {'D2':>4} {'D3':>4} {'D4':>4} {'D5':>4} {'D6':>4} {'D7':>4} {'Total':>7}")
print("-" * 70)
for m in models_sorted:
    s = SCORES[m]
    vals = [s.get(k, 0) for k in DIM_KEYS]
    print(f"{m:<20} {vals[0]:>4} {vals[1]:>4} {vals[2]:>4} {vals[3]:>4} {vals[4]:>4} {vals[5]:>4} {vals[6]:>4} {totals[m]:>7.1f}")
print("=" * 70)
if USE_PLACEHOLDER:
    print("\n⚠  These are PLACEHOLDER scores. To use real scores:")
    print(f"   1. Save your scores as: {SCORES_FILE}")
    print("   2. Re-run this script.")
print("\nDone!")
