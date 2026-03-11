# -*- coding: utf-8 -*-
"""
Merge two reviewer score files into a single averaged scores.json.
Also prints a comparison table and flags large discrepancies.
"""
import json
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent

# Load both evaluations
ds_raw = json.loads((SCRIPT_DIR / "deepseek_scores.json").read_text(encoding='utf-8'))
gpt_raw = json.loads((SCRIPT_DIR / "GPT5.2_scores.json").read_text(encoding='utf-8'))

# Normalize model names
NAME_MAP = {
    "DeepSeek-R1": "DeepSeek-R1",
    "Gemini-2.5-Pro": "Gemini-2.5-Pro",
    "Gemini 2.5 Pro": "Gemini-2.5-Pro",
    "GPT-5.2-Pro": "GPT-5.2-Pro",
    "GPT-5.2 Pro": "GPT-5.2-Pro",
    "Qwen": "Qwen",
    "Qwen (Deep Research)": "Qwen",
    "Agent-Enhanced": "Agent-Enhanced",
    "Agent-Enhanced (ReAct Agent with GPT-5.2)": "Agent-Enhanced",
    "Agent-Enhanced (GPT-5.2)": "Agent-Enhanced",
}

DIM_KEYS = [
    "D1_scientific_accuracy", "D2_mechanistic_depth", "D3_data_utilization",
    "D4_completeness", "D5_logical_coherence", "D6_novelty_predictive",
    "D7_presentation",
]
DIM_SHORT = ["D1", "D2", "D3", "D4", "D5", "D6", "D7"]
WEIGHTS = [0.20, 0.20, 0.15, 0.15, 0.10, 0.10, 0.10]
MODEL_ORDER = ["DeepSeek-R1", "Gemini-2.5-Pro", "GPT-5.2-Pro", "Qwen", "Agent-Enhanced"]


def parse_evals(raw):
    out = {}
    for ev in raw["evaluations"]:
        name = NAME_MAP.get(ev["model"], ev["model"])
        out[name] = ev["scores"]
    return out


ds_scores = parse_evals(ds_raw)
gpt_scores = parse_evals(gpt_raw)

# Print comparison
print("=" * 88)
print("REVIEWER COMPARISON")
print("=" * 88)
print(f"{'Model':<18} {'Dim':>5}  {'DeepSeek':>9} {'GPT-5.2':>9} {'Delta':>6} {'Average':>8}")
print("-" * 88)

merged = {}
discrepancies = []

for model in MODEL_ORDER:
    ds = ds_scores.get(model, {})
    gp = gpt_scores.get(model, {})
    avg_scores = {}

    for i, key in enumerate(DIM_KEYS):
        d_val = ds.get(key, 0)
        g_val = gp.get(key, 0)
        avg = round((d_val + g_val) / 2, 1)
        avg_scores[key] = avg
        delta = abs(d_val - g_val)
        flag = " ***" if delta > 2 else ""
        if delta > 2:
            discrepancies.append((model, DIM_SHORT[i], d_val, g_val, delta))
        print(f"{model:<18} {DIM_SHORT[i]:>5}  {d_val:>9} {g_val:>9} {delta:>6}{flag}")

    # Compute weighted total
    wtotal = sum(avg_scores[k] * w for k, w in zip(DIM_KEYS, WEIGHTS)) * 10
    avg_scores["_weighted_total"] = round(wtotal, 1)
    merged[model] = avg_scores
    print(f"{'':<18} {'TOTAL':>5}  {'':<9} {'':<9} {'':<6} {wtotal:>8.1f}")
    print()

# Flag discrepancies
if discrepancies:
    print("\nWARNING: Large discrepancies (delta > 2):")
    for m, d, dv, gv, delta in discrepancies:
        print(f"  {m} / {d}: DeepSeek={dv}, GPT={gv}, delta={delta}")
else:
    print("\nNo large discrepancies (all deltas <= 2).")

# Build output JSON in the format expected by plot_figure4_radar.py
output = {"evaluations": []}
for model in MODEL_ORDER:
    scores = {k: merged[model][k] for k in DIM_KEYS}
    output["evaluations"].append({
        "model": model,
        "scores": scores,
        "weighted_total": merged[model]["_weighted_total"],
        "brief_comment": f"Averaged from DeepSeek-R1 and GPT-5.2 Pro evaluations"
    })

out_path = SCRIPT_DIR / "scores.json"
out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding='utf-8')
print(f"\nSaved merged scores to: {out_path}")

# Print final summary
print("\n" + "=" * 78)
print("FINAL AVERAGED SCORES")
print("=" * 78)
print(f"{'Model':<18} {'D1':>5} {'D2':>5} {'D3':>5} {'D4':>5} {'D5':>5} {'D6':>5} {'D7':>5} {'Total':>7}")
print("-" * 78)
for model in sorted(MODEL_ORDER, key=lambda m: -merged[m]["_weighted_total"]):
    s = merged[model]
    vals = [s[k] for k in DIM_KEYS]
    print(f"{model:<18} {vals[0]:>5.1f} {vals[1]:>5.1f} {vals[2]:>5.1f} {vals[3]:>5.1f} {vals[4]:>5.1f} {vals[5]:>5.1f} {vals[6]:>5.1f} {s['_weighted_total']:>7.1f}")
print("=" * 78)
