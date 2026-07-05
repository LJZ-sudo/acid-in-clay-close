import glob, os, re

OUT = os.path.join(os.path.dirname(__file__), "_lineA_data_dump.txt")
lines = [f"CWD={os.getcwd()}"]

NEW = glob.glob("V1.0-qianduan-mainline/data/新材料/*")
sample_dirs = sorted(d for d in NEW if os.path.isdir(d))

for d in sample_dirs:
    name = os.path.basename(d)
    txts = glob.glob(d + "/*.txt")
    # parse temperatures from filenames like ..._T-88.0_f0.1_...
    temps = []
    for t in txts:
        m = re.search(r"_T(-?\d+\.?\d*)_", os.path.basename(t))
        if m:
            temps.append(float(m.group(1)))
    trange = f"{min(temps):.0f}..{max(temps):.0f}C  (n_pts={len(set(temps))})" if temps else "n/a"
    lines.append(f"\n#### {name}  files={len(txts)}  T={trange}")
    # dump any 材料制备 / prep / recipe txt
    for t in txts:
        bn = os.path.basename(t)
        if "制备" in bn or "材料" in bn or "recipe" in bn.lower() or "prep" in bn.lower():
            lines.append(f"  --- {bn} ---")
            try:
                lines.append("  " + open(t, encoding="utf-8").read().replace("\n", "\n  "))
            except Exception as e:
                lines.append("  ERR " + repr(e))

# sample raw EIS file header (one lotus + one starch)
sample_files = []
for key in ["藕粉", "淀粉"]:
    cands = [t for d in sample_dirs if key in d for t in glob.glob(d + "/*.txt")
             if "制备" not in os.path.basename(t) and "材料" not in os.path.basename(t)]
    if cands:
        sample_files.append(sorted(cands)[0])
for sf in sample_files:
    lines.append(f"\n===== RAW EIS SAMPLE: {sf} =====")
    try:
        head = open(sf, encoding="utf-8").read().splitlines()[:25]
        lines.append("\n".join(head))
    except Exception as e:
        lines.append("ERR " + repr(e))

open(OUT, "w", encoding="utf-8").write("\n".join(lines))
print("wrote", OUT, "dirs", len(sample_dirs))
