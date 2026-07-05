# -*- coding: utf-8 -*-
"""Publication-quality result figures from the canonical stage0 outputs.

Reads research/<label>/{aggregated_results,arrhenius_analysis}.json
(Arrhenius model is ln(sigma) vs 1000/T; segment slope/intercept are in that space)
and emits two figures into manuscript/figures/:

  Fig_lineA_arrhenius.png  -- Line A biopolymer transfer (prospective):
       (a) Arrhenius ln(sigma) vs 1000/T for LRS x2 (thick films) vs starch x2,
           with high-T segment fits; (b) Ea_high bar (LRS < starch, ranking reproduced).
  Fig_lineB_arrhenius.png  -- Line B MOBO+LLM closed loop (prospective execution):
       (a) Arrhenius for R0.28 (round 1) and R0.42 (round 2);
           (b) campaign combined_score per trial (new prospective rounds vs incumbent best).

Run from repo root:  python research/plot_results.py
"""
import json
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

REPO = next(_p for _p in Path(__file__).resolve().parents if _p.name == "research").parent
OUT = REPO / "research" / "data"
FIGDIR = REPO / "manuscript" / "figures"
FIGDIR.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
    "font.size": 9,
    "axes.linewidth": 0.9,
    "axes.labelsize": 10,
    "axes.titlesize": 10,
    "xtick.direction": "in",
    "ytick.direction": "in",
    "xtick.major.size": 3.5,
    "ytick.major.size": 3.5,
    "legend.frameon": False,
    "legend.fontsize": 8,
    "savefig.dpi": 300,
})


def load(label):
    agg = json.loads((OUT / label / "aggregated_results.json").read_text(encoding="utf-8"))
    arr = json.loads((OUT / label / "arrhenius_analysis.json").read_text(encoding="utf-8"))
    ms = [m for m in agg["measurements"] if m.get("success")
          and m.get("conductivity_S_per_cm")]
    pts = sorted(((m["temperature_K"], m["conductivity_S_per_cm"]) for m in ms),
                 key=lambda x: x[0])
    return pts, arr


def arrhenius_panel(ax, datasets):
    """datasets: list of dict(label, pts, arr, color, marker)."""
    for d in datasets:
        x = [1000.0 / T for T, s in d["pts"]]
        y = [math.log(s) for T, s in d["pts"]]
        ax.scatter(x, y, s=16, facecolors="none", edgecolors=d["color"],
                   linewidths=1.0, marker=d["marker"], label=d["label"], zorder=3)
        # high-T segment fit (segment 0)
        seg = d["arr"]["segments"][0]
        tr = seg["temp_range_K"]
        xs = [1000.0 / tr[1], 1000.0 / tr[0]]
        ys = [seg["slope"] * xv + seg["intercept"] for xv in xs]
        ax.plot(xs, ys, "-", color=d["color"], linewidth=1.4, zorder=2)
    ax.set_xlabel(r"1000 / $T$  (K$^{-1}$)")
    ax.set_ylabel(r"ln[$\sigma$ / (S cm$^{-1}$)]")
    ax.legend(loc="lower left")


def secondary_temp_axis(ax):
    """Add a top axis labelled in deg C for a few reference temps."""
    ax2 = ax.twiny()
    ax2.set_xlim(ax.get_xlim())
    ticks_C = [25, 0, -30, -60, -90]
    locs, labs = [], []
    lo, hi = ax.get_xlim()
    for tc in ticks_C:
        xv = 1000.0 / (tc + 273.15)
        if min(lo, hi) <= xv <= max(lo, hi):
            locs.append(xv)
            labs.append(f"{tc}")
    ax2.set_xticks(locs)
    ax2.set_xticklabels(labs)
    ax2.set_xlabel(r"$T$  ($^{\circ}$C)", fontsize=9)
    ax2.tick_params(direction="in")


# ---------------- Figure A: Line A ----------------
def fig_lineA():
    LRS = "#1f6f8b"; LRS2 = "#2aa198"
    ST = "#d9731a"; ST2 = "#c2410c"
    specs = [
        ("lineA_LRS_6.12", "LRS thick #1 (0.074 cm)", LRS, "o", "LRS"),
        ("lineA_LRS_6.15_merged", "LRS thick #2 (0.070 cm)", LRS2, "s", "LRS"),
        ("lineA_starch_6.11", "Starch ctrl #1 (0.063 cm)", ST, "^", "Starch"),
        ("lineA_starch_6.13", "Starch ctrl #2 (0.074 cm)", ST2, "D", "Starch"),
    ]
    datasets = []
    for label, disp, color, marker, group in specs:
        pts, arr = load(label)
        datasets.append({"label": disp, "pts": pts, "arr": arr,
                         "color": color, "marker": marker, "group": group,
                         "ea": arr["segments"][0]["Ea_eV"]})

    fig, (axA, axB) = plt.subplots(1, 2, figsize=(7.4, 3.3),
                                   gridspec_kw={"width_ratios": [1.55, 1.0]})
    arrhenius_panel(axA, datasets)
    secondary_temp_axis(axA)
    axA.text(-0.16, 1.16, "a", transform=axA.transAxes, fontsize=13, fontweight="bold")

    # Panel B: Ea_high bars
    names = [d["label"].split(" (")[0] for d in datasets]
    eas = [d["ea"] for d in datasets]
    cols = [d["color"] for d in datasets]
    xpos = range(len(datasets))
    axB.bar(xpos, eas, color=cols, width=0.62, edgecolor="black", linewidth=0.6)
    for i, e in enumerate(eas):
        axB.text(i, e + 0.004, f"{e:.3f}", ha="center", va="bottom", fontsize=8)
    axB.set_xticks(list(xpos))
    axB.set_xticklabels(names, rotation=30, ha="right", fontsize=7.5)
    axB.set_ylabel(r"$E_{\mathrm{a,high}}$  (eV)")
    axB.set_ylim(0, max(eas) * 1.28)
    # bracket annotation: LRS < starch
    axB.axhspan(0, 0.06, color="#1f6f8b", alpha=0.06)
    axB.text(0.5, max(eas) * 1.18, "LRS band", color=LRS, fontsize=7.5, ha="center")
    axB.text(2.5, max(eas) * 1.18, "Starch band", color=ST2, fontsize=7.5, ha="center")
    axB.text(-0.22, 1.16, "b", transform=axB.transAxes, fontsize=13, fontweight="bold")

    fig.suptitle("Line A · evidence-constrained biopolymer transfer (native prospective, 2026-06)",
                 fontsize=9.5, y=1.02)
    fig.tight_layout()
    out = FIGDIR / "Fig_lineA_arrhenius.png"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(f"[A] wrote {out}  Ea_high: " +
          ", ".join(f"{d['label'].split(' (')[0]}={d['ea']:.3f}" for d in datasets))


# ---------------- Figure B: Line B ----------------
def fig_lineB():
    C28 = "#3b6ea5"; C42 = "#b5651d"
    specs = [
        ("lineB_R0.28_6.10", "R=0.28 / N=0.96  (MOBO+LLM round 1)", C28, "o"),
        ("lineB_R0.42_6.11", "R=0.42 / N=1.02  (MOBO+LLM round 2)", C42, "s"),
    ]
    datasets = []
    for label, disp, color, marker in specs:
        pts, arr = load(label)
        datasets.append({"label": disp, "pts": pts, "arr": arr,
                         "color": color, "marker": marker})

    fig, (axA, axB) = plt.subplots(1, 2, figsize=(7.6, 3.3),
                                   gridspec_kw={"width_ratios": [1.25, 1.3]})
    arrhenius_panel(axA, datasets)
    secondary_temp_axis(axA)
    axA.text(-0.18, 1.16, "a", transform=axA.transAxes, fontsize=13, fontweight="bold")

    # Panel B: campaign combined_score per trial
    hist = json.loads((REPO / "V1.0-qianduan-mainline" / "stage1_optimization" /
                       "campaign_memory" / "history_db_attapulgite.json").read_text(encoding="utf-8"))
    trials = sorted(hist["trials"], key=lambda t: t["trial_id"])
    ids = [t["trial_id"] for t in trials]
    scores = [t["objectives"]["combined_score"] for t in trials]
    prospective_ids = {9, 10}  # new MOBO+LLM prospective rounds
    best = max(trials, key=lambda t: t["objectives"]["combined_score"])
    cols = []
    for t in trials:
        if t["trial_id"] == best["trial_id"]:
            cols.append("#2e7d32")          # incumbent best
        elif t["trial_id"] in prospective_ids:
            cols.append("#b5651d")          # new prospective
        else:
            cols.append("#b0b8c0")          # historical retrospective
    axB.bar(range(len(ids)), scores, color=cols, width=0.7,
            edgecolor="black", linewidth=0.5)
    axB.axhline(best["objectives"]["combined_score"], ls="--", lw=1.0,
                color="#2e7d32")
    axB.text(len(ids) - 0.5, best["objectives"]["combined_score"] + 0.04,
             f"incumbent best (trial {best['trial_id']})", color="#2e7d32",
             ha="right", va="bottom", fontsize=7.5)
    axB.set_xticks(range(len(ids)))
    axB.set_xticklabels([f"T{i}" for i in ids], fontsize=7.5)
    axB.set_xlabel("campaign trial")
    axB.set_ylabel("combined score  (higher = better)")
    axB.set_ylim(min(scores) * 1.08, max(scores) * 0.55)
    # legend proxies
    from matplotlib.patches import Patch
    axB.legend(handles=[
        Patch(fc="#2e7d32", ec="black", label="incumbent best"),
        Patch(fc="#b5651d", ec="black", label="new prospective (R1/R2)"),
        Patch(fc="#b0b8c0", ec="black", label="historical (retrospective)"),
    ], loc="lower left", fontsize=7)
    axB.text(-0.2, 1.16, "b", transform=axB.transAxes, fontsize=13, fontweight="bold")

    fig.suptitle("Line B · physics/QC-gated MOBO+LLM closed loop "
                 "(honest prospective execution, no net improvement)",
                 fontsize=9.5, y=1.02)
    fig.tight_layout()
    out = FIGDIR / "Fig_lineB_arrhenius.png"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(f"[B] wrote {out}  new prospective trials 9/10 below incumbent best "
          f"(trial {best['trial_id']}, score={best['objectives']['combined_score']:.3f})")


if __name__ == "__main__":
    fig_lineA()
    fig_lineB()
    print("done")
