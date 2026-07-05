# -*- coding: utf-8 -*-
"""Batch-process the June 2026 new datasets (Line A biopolymers + Line B R0.42/R0.28)
through the canonical stage0 offline pipeline, then emit a compact comparison table.

Run from repo root:
    python research/process_all.py
"""
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = next(_p for _p in Path(__file__).resolve().parents if _p.name == "V1.0-qianduan-mainline").parent
STAGE0 = REPO / "V1.0-qianduan-mainline" / "stage0_measurement"
RESEARCH = REPO / "research"
OUT = RESEARCH / "data"   # 数据集输出目录（lineA_*/lineB_*）

# (label, data_dir relative to repo, thickness_cm, chi_pattern, line)
DATASETS = [
    ("lineA_starch_6.11",      "V1.0-qianduan-mainline/data/新材料/2026.6.11淀粉", 0.0628, "*.txt", "A"),
    ("lineA_LRS_6.12",         "V1.0-qianduan-mainline/data/新材料/2026.6.12藕粉", 0.0737, "*.txt", "A"),
    ("lineA_starch_6.13",      "V1.0-qianduan-mainline/data/新材料/2026.6.13淀粉", 0.0737, "*.txt", "A"),
    # 6.15 藕粉 = same LRS sample #1 (6.13藕粉-1) measured across sessions -> merge whole folder
    ("lineA_LRS_6.15_merged",  "V1.0-qianduan-mainline/data/新材料/2026.6.15藕粉", 0.0701, "*.txt", "A"),
    # additional independent LRS repeats (same material, other pressed pellets); real
    # thickness from each folder's 材料制备.txt (sample #2, #3, #3-rerun)
    ("lineA_LRS_0615_s2",  "V1.0-qianduan-mainline/data/新材料/2026.6.15", 0.0778, "*.txt", "A"),
    ("lineA_LRS_0616_s3",  "V1.0-qianduan-mainline/data/新材料/2026.6.16", 0.0734, "*.txt", "A"),
    ("lineA_LRS_0617_s3b", "V1.0-qianduan-mainline/data/新材料/2026.6.17", 0.0734, "*.txt", "A"),
    ("lineB_R0.42_6.11",   "V1.0-qianduan-mainline/data/ao/2026.6.11R0.42-N1.02", 0.0697, "*.txt", "B"),
    ("lineB_R0.28_6.10",   "V1.0-qianduan-mainline/data/ao/2026.6.10__BO-R0.28-N0.96-w96y-1", 0.0783, "*.txt", "B"),
]


def run_one(label, data_dir, thickness, pattern):
    out_dir = OUT / label
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    cmd = [
        sys.executable, "run_offline.py",
        "--data_dir", str(REPO / data_dir),
        "--material", label,
        "--thickness", str(thickness),
        "--area", "1.96",
        "--output_dir", str(out_dir),
        "--chi_pattern", pattern,
        "--disable_reporting",
    ]
    r = subprocess.run(cmd, cwd=str(STAGE0), env=env,
                       capture_output=True, text=True, encoding="utf-8")
    return out_dir, r.returncode


def summarize(out_dir):
    agg = out_dir / "aggregated_results.json"
    arr = out_dir / "arrhenius_analysis.json"
    s = {"n_success": 0, "n_kk_warn": 0, "sigma_max": None, "T_at_max": None,
         "sigma_273": None, "sigma_253": None, "sigma_233": None,
         "T_low": None, "ea_high": None, "ea_mid": None, "n_seg": None, "trans": None}
    if agg.exists():
        data = json.loads(agg.read_text(encoding="utf-8"))
        ms = [m for m in data.get("measurements", []) if m.get("success")]
        s["n_success"] = len(ms)
        s["n_kk_warn"] = sum(1 for m in ms if m.get("kk_warning"))
        def near(targetK):
            best = None
            for m in ms:
                tk = m.get("temperature_K")
                sig = m.get("conductivity_S_per_cm")
                if tk is None or sig is None:
                    continue
                if best is None or abs(tk - targetK) < abs(best[0] - targetK):
                    best = (tk, sig)
            return best
        if ms:
            mx = max(ms, key=lambda m: (m.get("conductivity_S_per_cm") or 0))
            s["sigma_max"] = mx.get("conductivity_S_per_cm")
            s["T_at_max"] = mx.get("temperature_C")
            lo = min(ms, key=lambda m: (m.get("temperature_K") or 9e9))
            s["T_low"] = lo.get("temperature_C")
            for tgt, key in [(273.15, "sigma_273"), (253.15, "sigma_253"), (233.15, "sigma_233")]:
                b = near(tgt)
                if b and abs(b[0] - tgt) <= 2.0:
                    s[key] = b[1]
    if arr.exists():
        a = json.loads(arr.read_text(encoding="utf-8"))
        s["n_seg"] = a.get("n_segments")
        s["trans"] = a.get("transition_temps_K")
        segs = a.get("segments", [])
        if segs:
            s["ea_high"] = segs[0].get("Ea_eV")
            if len(segs) > 1:
                s["ea_mid"] = segs[1].get("Ea_eV")
    return s


def fmt(x, e=False):
    if x is None:
        return "    -   "
    if e:
        return f"{x:.2e}"
    return f"{x:.4f}"


def main():
    rows = []
    for label, dd, th, pat, line in DATASETS:
        out_dir, rc = run_one(label, dd, th, pat)
        s = summarize(out_dir)
        s["label"] = label
        s["line"] = line
        s["thickness"] = th
        rows.append(s)
        print(f"[{line}] {label:22s} rc={rc} n={s['n_success']:3d} kkw={s['n_kk_warn']:2d} "
              f"sig_max={fmt(s['sigma_max'], True)}@{s['T_at_max']}C  "
              f"ea_high={fmt(s['ea_high'])}eV ea_mid={fmt(s['ea_mid'])}eV "
              f"nseg={s['n_seg']} Tlow={s['T_low']}C")
    # write CSV
    csv = RESEARCH / "new_data_summary.csv"
    cols = ["line", "label", "thickness", "n_success", "n_kk_warn", "sigma_max",
            "T_at_max", "sigma_273", "sigma_253", "sigma_233", "T_low",
            "ea_high", "ea_mid", "n_seg"]
    with open(csv, "w", encoding="utf-8") as f:
        f.write(",".join(cols) + "\n")
        for r in rows:
            f.write(",".join(str(r.get(c)) for c in cols) + "\n")
    print(f"\nSaved: {csv}")


if __name__ == "__main__":
    main()
