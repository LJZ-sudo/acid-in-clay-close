import glob, json, os

OUT = os.path.join(os.path.dirname(__file__), "_arrh_probe.txt")
base = "m6_baseline_ablation/line_a_analysis/stage0_out"
lines = []
target = [d for d in glob.glob(base + "/*") if "藕粉" in d and "6.15" in d]
lines.append("target=" + str(target))
for d in target:
    for fn in ["arrhenius_analysis.json", "aggregated_results.json"]:
        p = os.path.join(d, fn)
        lines.append("\n##### " + fn + " #####")
        if not os.path.exists(p):
            lines.append("MISSING")
            continue
        data = json.load(open(p, encoding="utf-8"))
        if fn.startswith("arr"):
            lines.append(json.dumps(data, ensure_ascii=False, indent=2)[:3500])
        else:
            lines.append("keys=" + str(list(data.keys())))
            lines.append("temperatures_K head=" + str(data.get("temperatures_K", [])[:5]))
            lines.append("conductivities head=" + str(data.get("conductivities", [])[:5]))
            m = data.get("measurements", [])
            if m:
                lines.append("measurement[0] keys=" + str(list(m[0].keys())))
                lines.append("measurement[0]=" + json.dumps(m[0], ensure_ascii=False))
open(OUT, "w", encoding="utf-8").write("\n".join(lines))
print("done", OUT)
