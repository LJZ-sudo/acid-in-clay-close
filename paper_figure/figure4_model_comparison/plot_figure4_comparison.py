# -*- coding: utf-8 -*-
"""
Figure 4: Multi-Model Deep Mechanism Analysis Comparison

Layout: 2 sub-figures (individual files for PPT)
  (a) Radar chart — 7-dimension comparison across 5 models
  (b) Weighted total score bar chart with highlights

Style: Advanced Materials (AM) journal format

Usage:
  1. Run with placeholder data first to check layout.
  2. After receiving LLM judge scores, update SCORES dict below.
  3. Re-run to generate final figures.

  python plot_figure4_comparison.py
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
from am_style_config import setup_am_style, COLORS, save_figure, add_panel_label

setup_am_style()

# ============================================================
# ★★★  SCORES — REPLACE WITH REAL DATA AFTER EVALUATION  ★★★
# ============================================================
# Each model: {D1, D2, D3, D4, D5, D6, D7}
# D1: Scientific Accuracy (20%)
# D2: Mechanistic Depth (20%)
# D3: Data Utilization (15%)
# D4: Completeness (15%)
# D5: Logical Coherence (10%)
# D6: Novelty & Predictive (10%)
# D7: Presentation Quality (10%)

SCORES = {
    "DeepSeek-R1": {
        "D1": 0, "D2": 0, "D3": 0, "D4": 0,
        "D5": 0, "D6": 0, "D7": 0,
        "total": 0,
        "comment": ""
    },
    "Gemini 2.5 Pro": {
        "D1": 0, "D2": 0, "D3": 0, "D4": 0,
        "D5": 0, "D6": 0, "D7": 0,
        "total": 0,
        "comment": ""
    },
    "GPT-5.2 Pro": {
        "D1": 0, "D2": 0, "D3": 0, "D4": 0,
        "D5": 0, "D6": 0, "D7": 0,
        "total": 0,
        "comment": ""
    },
    "Qwen": {
        "D1": 0, "D2": 0, "D3": 0, "D4": 0,
        "D5": 0, "D6": 0, "D7": 0,
        "total": 0,
        "comment": ""
    },
    "Agent-Enhanced\n(GPT-5.2)": {
        "D1": 0, "D2": 0, "D3": 0, "D4": 0,
        "D5": 0, "D6": 0, "D7": 0,
        "total": 0,
        "comment": ""
    },
}

# Alternatively: load from JSON file if it exists
SCORES_JSON = SCRIPT_DIR / "evaluation_scores.json"
if SCORES_JSON.exists():
    with open(SCORES_JSON, 'r', encoding='utf-8') as f:
        loaded = json.load(f)
    # Map loaded data into SCORES
    name_map = {
        "DeepSeek-R1": "DeepSeek-R1",
        "Gemini-2.5-Pro": "Gemini 2.5 Pro",
        "Gemini 2.5 Pro": "Gemini 2.5 Pro",
        "GPT-5.2-Pro": "GPT-5.2 Pro",
        "GPT-5.2 Pro": "GPT-5.2 Pro",
        "Qwen": "Qwen",
        "Agent-Enhanced-GPT-5.2": "Agent-Enhanced\n(GPT-5.2)",
        "Agent-Enhanced (GPT-5.2)": "Agent-Enhanced\n(GPT-5.2)",
    }
    if "evaluations" in loaded:
        for ev in loaded["evaluations"]:
            model_key = name_map.get(ev["model"], ev["model"])
            if model_key in SCORES:
                sc = ev.get("scores", {})
                SCORES[model_key]["D1"] = sc.get("D1_scientific_accuracy", 0)
                SCORES[model_key]["D2"] = sc.get("D2_mechanistic_depth", 0)
                SCORES[model_key]["D3"] = sc.get("D3_data_utilization", 0)
                SCORES[model_key]["D4"] = sc.get("D4_completeness", 0)
                SCORES[model_key]["D5"] = sc.get("D5_logical_coherence", 0)
                SCORES[model_key]["D6"] = sc.get("D6_novelty_predictive", 0)
                SCORES[model_key]["D7"] = sc.get("D7_presentation", 0)
                SCORES[model_key]["total"] = ev.get("weighted_total", 0)
                SCORES[model_key]["comment"] = ev.get("brief_comment", "")
    print(f"Loaded scores from {SCORES_JSON}")

# ============================================================
# Dimension labels and weights
# ============================================================
DIMENSIONS = [
    "Scientific\nAccuracy",
    "Mechanistic\nDepth",
    "Data\nUtilization",
    "Completeness\n& Coverage",
    "Logical\nCoherence",
    "Novelty &\nPredictive",
    "Presentation\nQuality",
]
DIM_KEYS = ["D1", "D2", "D3", "D4", "D5", "D6", "D7"]
WEIGHTS = [0.20, 0.20, 0.15, 0.15, 0.10, 0.10, 0.10]

# ============================================================
# Model colors — AM-compatible distinctive palette
# ============================================================
MODEL_COLORS = {
    "DeepSeek-R1":              "#4CAF50",   # Green
    "Gemini 2.5 Pro":           "#FF9800",   # Orange
    "GPT-5.2 Pro":              "#2196F3",   # Blue
    "Qwen":                     "#9C27B0",   # Purple
    "Agent-Enhanced\n(GPT-5.2)": "#E91E63",  # Pink (our system)
}

MODEL_ORDER = list(SCORES.keys())

# ============================================================
# Helper: compute weighted total if not loaded
# ============================================================
for name, sc in SCORES.items():
    if sc["total"] == 0 and any(sc[k] > 0 for k in DIM_KEYS):
        vals = [sc[k] for k in DIM_KEYS]
        sc["total"] = round(sum(v * w for v, w in zip(vals, WEIGHTS)) * 10, 1)

# Check if we have real data
has_data = any(SCORES[m]["total"] > 0 for m in MODEL_ORDER)
if not has_data:
    print("WARNING: No real scores found. Using placeholder data for layout preview.")
    print(f"  To use real data, save scores as JSON to: {SCORES_JSON}")
    print("  Or edit SCORES dict in this script directly.")
    # Placeholder data for layout testing
    SCORES["DeepSeek-R1"] = {"D1": 8, "D2": 7, "D3": 8, "D4": 8, "D5": 7, "D6": 7, "D7": 7, "total": 74.5, "comment": "placeholder"}
    SCORES["Gemini 2.5 Pro"] = {"D1": 7, "D2": 6, "D3": 5, "D4": 7, "D5": 7, "D6": 6, "D7": 6, "total": 63.5, "comment": "placeholder"}
    SCORES["GPT-5.2 Pro"] = {"D1": 9, "D2": 8, "D3": 8, "D4": 9, "D5": 9, "D6": 8, "D7": 9, "total": 86.0, "comment": "placeholder"}
    SCORES["Qwen"] = {"D1": 7, "D2": 7, "D3": 6, "D4": 8, "D5": 7, "D6": 7, "D7": 8, "total": 71.0, "comment": "placeholder"}
    SCORES["Agent-Enhanced\n(GPT-5.2)"] = {"D1": 9, "D2": 9, "D3": 9, "D4": 9, "D5": 8, "D6": 9, "D7": 9, "total": 89.5, "comment": "placeholder"}

# ============================================================
# (a) Radar Chart
# ============================================================
fig_a, ax_a = plt.subplots(figsize=(7, 7), subplot_kw=dict(polar=True), dpi=300)

N = len(DIMENSIONS)
angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
angles += angles[:1]  # close the polygon

# Set angle labels
ax_a.set_xticks(angles[:-1])
ax_a.set_xticklabels(DIMENSIONS, fontsize=9, fontweight='bold')

# Set radial limits
ax_a.set_ylim(0, 10)
ax_a.set_yticks([2, 4, 6, 8, 10])
ax_a.set_yticklabels(['2', '4', '6', '8', '10'], fontsize=8, color='#666')
ax_a.set_rlabel_position(30)

# Grid styling
ax_a.grid(True, linewidth=0.6, alpha=0.4)
ax_a.spines['polar'].set_linewidth(1.0)

# Plot each model
for model_name in MODEL_ORDER:
    sc = SCORES[model_name]
    values = [sc[k] for k in DIM_KEYS]
    values += values[:1]  # close

    color = MODEL_COLORS[model_name]
    is_agent = "Agent" in model_name

    ax_a.plot(angles, values,
              linewidth=2.5 if is_agent else 1.8,
              linestyle='-',
              color=color,
              label=model_name.replace('\n', ' '),
              zorder=5 if is_agent else 3)
    ax_a.fill(angles, values,
              alpha=0.15 if is_agent else 0.06,
              color=color,
              zorder=4 if is_agent else 2)

    # Mark agent points
    if is_agent:
        ax_a.scatter(angles[:-1], values[:-1], s=40, color=color,
                     edgecolors='white', linewidths=1.0, zorder=6)

ax_a.legend(loc='upper right', bbox_to_anchor=(1.35, 1.12),
            fontsize=8.5, framealpha=0.9, edgecolor='#ddd')

ax_a.set_title('Multi-Dimensional Evaluation Comparison',
               fontsize=13, fontweight='bold', pad=25)

# Panel label
fig_a.text(0.02, 0.96, '(a)', fontsize=16, fontweight='bold',
           transform=fig_a.transFigure)

plt.tight_layout()
save_figure(fig_a, str(SCRIPT_DIR / "figure4a_radar_comparison"), dpi=300)
plt.close(fig_a)
print("(a) Radar chart done.")

# ============================================================
# (b) Weighted Total Score Bar Chart
# ============================================================
fig_b, ax_b = plt.subplots(figsize=(8, 5), dpi=300)

model_names = [m.replace('\n', ' ') for m in MODEL_ORDER]
totals = [SCORES[m]["total"] for m in MODEL_ORDER]
colors_list = [MODEL_COLORS[m] for m in MODEL_ORDER]

# Sort by score for better visualization
sorted_idx = np.argsort(totals)
model_names_sorted = [model_names[i] for i in sorted_idx]
totals_sorted = [totals[i] for i in sorted_idx]
colors_sorted = [colors_list[i] for i in sorted_idx]

y_pos = np.arange(len(model_names_sorted))
bars = ax_b.barh(y_pos, totals_sorted, height=0.6,
                 color=colors_sorted, edgecolor='white', linewidth=1.5,
                 alpha=0.85, zorder=3)

# Highlight the Agent bar
for i, (bar, name) in enumerate(zip(bars, model_names_sorted)):
    if "Agent" in name:
        bar.set_alpha(1.0)
        bar.set_edgecolor('#B71C1C')
        bar.set_linewidth(2.5)
        # Add star marker
        ax_b.annotate('★', xy=(totals_sorted[i] + 1, y_pos[i]),
                       fontsize=16, color='#E91E63', va='center', fontweight='bold')

# Score labels on bars
for i, (bar, total) in enumerate(zip(bars, totals_sorted)):
    ax_b.text(total - 2, y_pos[i], f'{total:.1f}',
              va='center', ha='right', fontsize=11, fontweight='bold',
              color='white')

# Styling
ax_b.set_yticks(y_pos)
ax_b.set_yticklabels(model_names_sorted, fontsize=10, fontweight='500')
ax_b.set_xlabel('Weighted Total Score (0-100)', fontsize=12)
ax_b.set_title('Overall Performance Ranking', fontsize=13, fontweight='bold')
ax_b.set_xlim(0, 105)
ax_b.grid(True, axis='x', alpha=0.25, linewidth=0.6)
ax_b.spines['top'].set_visible(False)
ax_b.spines['right'].set_visible(False)

# Weight legend
weight_text = (
    "Weights: Accuracy 20% · Depth 20% · Data 15%\n"
    "Coverage 15% · Coherence 10% · Novelty 10% · Style 10%"
)
ax_b.text(0.98, 0.02, weight_text, transform=ax_b.transAxes,
          fontsize=7.5, ha='right', va='bottom', color='#888',
          bbox=dict(boxstyle='round,pad=0.3', facecolor='#f5f5f5',
                    edgecolor='#ddd', alpha=0.9))

if not has_data:
    ax_b.text(0.5, 0.5, 'PLACEHOLDER DATA\n(Replace with real scores)',
              transform=ax_b.transAxes, fontsize=14, ha='center', va='center',
              color='red', alpha=0.3, fontweight='bold', rotation=15)

# Panel label
fig_b.text(0.02, 0.96, '(b)', fontsize=16, fontweight='bold',
           transform=fig_b.transFigure)

plt.tight_layout()
save_figure(fig_b, str(SCRIPT_DIR / "figure4b_score_ranking"), dpi=300)
plt.close(fig_b)
print("(b) Score ranking bar chart done.")

# ============================================================
# Save scores summary
# ============================================================
summary_path = SCRIPT_DIR / "scores_summary.md"
with open(summary_path, 'w', encoding='utf-8') as f:
    f.write("# Model Evaluation Scores Summary\n\n")
    f.write("| Model | D1 | D2 | D3 | D4 | D5 | D6 | D7 | Total |\n")
    f.write("|-------|----|----|----|----|----|----|----|---------|\n")
    for m in MODEL_ORDER:
        sc = SCORES[m]
        name = m.replace('\n', ' ')
        f.write(f"| {name} | {sc['D1']} | {sc['D2']} | {sc['D3']} | "
                f"{sc['D4']} | {sc['D5']} | {sc['D6']} | {sc['D7']} | "
                f"**{sc['total']}** |\n")
    f.write("\n**Placeholder** " if not has_data else "\n")
    f.write(f"\nGenerated by plot_figure4_comparison.py\n")

print(f"\nScores summary: {summary_path}")
print(f"\n{'='*60}")
print("Figure 4 generation complete!")
if not has_data:
    print(f"\nNext step: Save real evaluation scores to:")
    print(f"  {SCORES_JSON}")
    print("Then re-run this script to generate final figures.")
print(f"{'='*60}")
