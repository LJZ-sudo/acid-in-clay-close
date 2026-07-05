# -*- coding: utf-8 -*-
"""B1 — cross-sample transition-regularity table + figure over ALL processed datasets.

WHY: the old new_data_summary.csv had only 6/13 datasets and NO transition-temperature
(T_break) column. P1's "tunable / universal sub-zero transition" claim needs the full set.
This script reads EVERY real stage0 output folder (canonical aggregated_results.json +
arrhenius_analysis.json), extracts the REAL transition temperature + two-segment Ea +
sigma(T), and emits an honest extended table + a regularity figure. Nothing fabricated;
datasets without a clean wide-temp transition are KEPT but flagged (has_transition=False).

T_break convention: the MAIN transition = transition_temps_K[0] (separates the high-T
near-athermal segment 0 from the low-T activated segment 1). A 1-point segment-2 tail
(common pwlf artifact at the coldest point) is ignored for Ea but noted.

Run from repo root:  python research/regularity/build_regularity.py
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# nature-figure publication defaults: Arial sans-serif, top/right spines off, frameless
# legend, editable SVG text (svg.fonttype='none'); legible final-size fonts.
plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans", "Liberation Sans"],
    "svg.fonttype": "none",
    "font.size": 9, "axes.titlesize": 9, "axes.labelsize": 9,
    "xtick.labelsize": 8, "ytick.labelsize": 8, "legend.fontsize": 8,
    "axes.spines.right": False, "axes.spines.top": False, "legend.frameon": False,
    "savefig.dpi": 600, "figure.dpi": 150,
})

HERE = Path(__file__).resolve().parent
NDA = HERE.parents[2] / "research"


def save_publication(fig, stem):
    """nature-figure export: SVG (primary, editable text) + PNG 300/600 + TIFF 600."""
    fig.savefig(HERE / f"{stem}.svg", bbox_inches="tight")          # primary, editable vector
    fig.savefig(HERE / f"{stem}.png", dpi=300, bbox_inches="tight")  # preview raster
    fig.savefig(HERE / f"{stem}_600dpi.png", dpi=600, bbox_inches="tight")
    try:
        fig.savefig(HERE / f"{stem}.tiff", dpi=600, pil_kwargs={"compression": "tiff_lzw"})
    except Exception as e:  # Pillow missing -> 600-dpi PNG is still submission-usable
        print(f"  (TIFF skipped: {e}; use {stem}_600dpi.png)")

# label -> (material, line, R, N, thickness_cm, batch)  ; R/N only meaningful for line B
# 13 canonical line-A repeats (same as repro_full REGISTRY) + 2 line-B prospective points.
REGISTRY = [
    # LRS (lotus-root starch) x7
    ("lineA_LRS_0429CS",      "LRS",    "A", None, None, 0.020,  "Apr-thin"),
    ("lineA_LRS_0509CS",      "LRS",    "A", None, None, 0.022,  "Apr-thin"),
    ("lineA_LRS_6.12",        "LRS",    "A", None, None, 0.0737, "Jun-std"),
    ("lineA_LRS_6.15_merged", "LRS",    "A", None, None, 0.0701, "Jun-std"),
    ("lineA_LRS_0615_s2",     "LRS",    "A", None, None, 0.0778, "Jun-std"),
    ("lineA_LRS_0616_s3",     "LRS",    "A", None, None, 0.0734, "Jun-std"),
    ("lineA_LRS_0617_s3b",    "LRS",    "A", None, None, 0.0734, "Jun-std"),
    # starch x4
    ("lineA_starch_0427CS",   "starch", "A", None, None, 0.060,  "Apr"),
    ("lineA_starch_0428CS",   "starch", "A", None, None, 0.060,  "Apr"),
    ("lineA_starch_6.11",     "starch", "A", None, None, 0.0628, "Jun"),
    ("lineA_starch_6.13",     "starch", "A", None, None, 0.0737, "Jun"),
    # chitosan x2 (boundary / negative class)
    ("lineA_CHITO_0430CS",    "CHITO",  "A", None, None, 0.050,  "Apr"),
    ("lineA_CHITO_0501CS",    "CHITO",  "A", None, None, 0.060,  "Apr"),
    # line B attapulgite (R/N varied) — prospective points
    ("lineB_R0.28_6.10",      "ATP",    "B", 0.28, 0.96, 0.0783, "prosp"),
    ("lineB_R0.42_6.11",      "ATP",    "B", 0.42, 1.02, 0.0697, "prosp"),
]

MIN_SEG_PTS = 4  # a segment must have >= this many points to count as a real Arrhenius segment


def near_sigma(ms, targetK, tol=2.0):
    best = None
    for m in ms:
        tk, sig = m.get("temperature_K"), m.get("conductivity_S_per_cm")
        if tk is None or sig is None:
            continue
        if best is None or abs(tk - targetK) < abs(best[0] - targetK):
            best = (tk, sig)
    if best and abs(best[0] - targetK) <= tol:
        return best[1]
    return None


def extract(label):
    folder = NDA / "data" / label
    agg = folder / "aggregated_results.json"
    arr = folder / "arrhenius_analysis.json"
    r = {"n_pts": 0, "T_hi_C": None, "T_lo_C": None, "sigma_max": None, "T_at_max_C": None,
         "sigma_273": None, "sigma_253": None, "sigma_233": None,
         "n_seg": None, "confidence": None, "T_break_C": None,
         "ea_high": None, "ea_low": None, "seg0_npts": None, "seg1_npts": None,
         "has_transition": False, "seg_tail_artifact": False}
    if agg.exists():
        ms = [m for m in json.loads(agg.read_text(encoding="utf-8")).get("measurements", [])
              if m.get("success")]
        r["n_pts"] = len(ms)
        if ms:
            tks = [m["temperature_K"] for m in ms if m.get("temperature_K") is not None]
            r["T_hi_C"] = max(tks) - 273.15
            r["T_lo_C"] = min(tks) - 273.15
            mx = max(ms, key=lambda m: (m.get("conductivity_S_per_cm") or 0))
            r["sigma_max"] = mx.get("conductivity_S_per_cm")
            r["T_at_max_C"] = mx.get("temperature_C")
            r["sigma_273"] = near_sigma(ms, 273.15)
            r["sigma_253"] = near_sigma(ms, 253.15)
            r["sigma_233"] = near_sigma(ms, 233.15)
    if arr.exists():
        a = json.loads(arr.read_text(encoding="utf-8"))
        r["n_seg"] = a.get("n_segments")
        r["confidence"] = a.get("confidence")
        segs = a.get("segments", [])
        trans = a.get("transition_temps_K") or []
        # main two segments = seg0 (high-T) and seg1 (low-T); seg2 (if 1-pt) is a tail artifact
        if segs:
            r["ea_high"] = segs[0].get("Ea_eV")
            r["seg0_npts"] = segs[0].get("n_points")
        if len(segs) > 1:
            r["ea_low"] = segs[1].get("Ea_eV")
            r["seg1_npts"] = segs[1].get("n_points")
        if len(segs) > 2 and (segs[2].get("n_points") or 0) <= 2:
            r["seg_tail_artifact"] = True
        # main transition temperature
        if trans:
            r["T_break_C"] = trans[0] - 273.15
        # "real transition" = two main segments each with enough points
        if (r["seg0_npts"] or 0) >= MIN_SEG_PTS and (r["seg1_npts"] or 0) >= MIN_SEG_PTS:
            r["has_transition"] = True
    return r


def main():
    rows = []
    for (label, mat, line, R, N, th, batch) in REGISTRY:
        r = extract(label)
        r.update({"label": label, "material": mat, "line": line, "R": R, "N": N,
                  "thickness": th, "batch": batch})
        rows.append(r)

    # ---- console verification dump ----
    print("=== B1 cross-sample regularity (REAL data, all processed datasets) ===")
    hdr = (f"{'label':24s} {'mat':6s} {'batch':9s} {'n':>3s} {'Trange_C':>14s} "
           f"{'nseg':>4s} {'conf':>5s} {'Tbreak_C':>9s} {'Ea_hi':>7s} {'Ea_lo':>7s} "
           f"{'s0/s1':>7s} {'trans?':>6s}")
    print(hdr)
    for r in rows:
        tr = (f"{r['T_lo_C']:.0f}..{r['T_hi_C']:.0f}" if r['T_hi_C'] is not None else "-")
        tb = f"{r['T_break_C']:.1f}" if r['T_break_C'] is not None else "-"
        eh = f"{r['ea_high']:.3f}" if r['ea_high'] is not None else "-"
        el = f"{r['ea_low']:.3f}" if r['ea_low'] is not None else "-"
        s01 = f"{r['seg0_npts']}/{r['seg1_npts']}" if r['seg0_npts'] else "-"
        flag = "YES" if r["has_transition"] else "no"
        art = "*tail" if r["seg_tail_artifact"] else ""
        print(f"{r['label']:24s} {r['material']:6s} {r['batch']:9s} {r['n_pts']:3d} "
              f"{tr:>14s} {str(r['n_seg']):>4s} {str(r['confidence']):>5s} {tb:>9s} "
              f"{eh:>7s} {el:>7s} {s01:>7s} {flag:>6s} {art}")

    # ---- write extended CSV ----
    cols = ["line", "label", "material", "batch", "R", "N", "thickness", "n_pts",
            "T_hi_C", "T_lo_C", "sigma_max", "T_at_max_C", "sigma_273", "sigma_253",
            "sigma_233", "n_seg", "confidence", "T_break_C", "ea_high", "ea_low",
            "seg0_npts", "seg1_npts", "has_transition", "seg_tail_artifact"]
    csv = HERE / "regularity_table.csv"
    with open(csv, "w", encoding="utf-8") as f:
        f.write(",".join(cols) + "\n")
        for r in rows:
            f.write(",".join(str(r.get(c)) for c in cols) + "\n")
    print(f"\nSaved table -> {csv}")

    # ---- figure: regularity over datasets WITH a real transition ----
    trans_rows = [r for r in rows if r["has_transition"]]
    colors = {"LRS": "tab:red", "starch": "tab:green", "CHITO": "tab:blue", "ATP": "tab:orange"}

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.6, 5.2))

    # (a) Ea_high vs Ea_low, colored by material — the "transition sharpness" map
    for mat in ["LRS", "starch", "CHITO", "ATP"]:
        xs = [r["ea_high"] for r in trans_rows if r["material"] == mat]
        ys = [r["ea_low"] for r in trans_rows if r["material"] == mat]
        if xs:
            ax1.scatter(xs, ys, s=90, c=colors[mat], edgecolor="k", label=f"{mat} (n={len(xs)})", zorder=3)
    lim = 0.05
    ax1.plot([0, 0.8], [0, 0.8], "k--", lw=0.8, alpha=0.5, label="Ea_low = Ea_high")
    ax1.set_xlabel("high-T segment Ea (eV)  [near-athermal end]")
    ax1.set_ylabel("low-T segment Ea (eV)  [activated end]")
    ax1.set_title("(a) Transition-sharpness map\nupper-left = sharp (LRS); lower = mild (starch)")
    ax1.legend(fontsize=8)
    ax1.grid(alpha=0.3)

    # (b) T_break per dataset, grouped by material
    trans_rows_sorted = sorted(trans_rows, key=lambda r: (r["material"], r["T_break_C"]))
    labels = [r["label"].replace("lineA_", "").replace("lineB_", "") for r in trans_rows_sorted]
    tbs = [r["T_break_C"] for r in trans_rows_sorted]
    cs = [colors[r["material"]] for r in trans_rows_sorted]
    ax2.barh(range(len(labels)), tbs, color=cs, edgecolor="k")
    ax2.set_yticks(range(len(labels)))
    ax2.set_yticklabels(labels, fontsize=7)
    ax2.axvline(0, color="gray", lw=0.8)
    ax2.set_xlabel("main transition temperature T_break (°C)")
    ax2.set_title("(b) Sub-zero transition temperature across samples\n(all below 0 °C)")
    ax2.grid(alpha=0.3, axis="x")
    fig.tight_layout()
    save_publication(fig, "regularity")
    plt.close(fig)
    print(f"Saved figure -> {HERE / 'regularity.png'} (+ 600dpi PNG/TIFF)")
    print(f"\n# datasets total={len(rows)}  with real transition={len(trans_rows)}")
    for mat in ["LRS", "starch", "CHITO", "ATP"]:
        sub = [r for r in trans_rows if r["material"] == mat]
        if sub:
            eh = np.mean([r["ea_high"] for r in sub]); el = np.mean([r["ea_low"] for r in sub])
            tb = np.mean([r["T_break_C"] for r in sub])
            print(f"  {mat:6s}: n={len(sub)}  mean Ea_high={eh:.3f}  Ea_low={el:.3f}  T_break={tb:.1f}C")


if __name__ == "__main__":
    main()
