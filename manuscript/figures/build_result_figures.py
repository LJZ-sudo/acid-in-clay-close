# -*- coding: utf-8 -*-
"""Generate the three DATA result figures from REAL project data (no fabrication):

  Fig3_sigma_T.png     wide-temperature sigma(T) for LRS / CHITO / corn-starch
  Fig4_arrhenius.png   panel A: Arrhenius ln(sigmaT) vs 1000/T; panel B: Ea benchmark bar
  Fig6_closed_loop.png panel A: honest BO score trajectory (improvement=0);
                       panel B: (R,N) exploration + frozen MOBO+LLM recipes

Data sources (all real, in-repo):
  three_pillars/pillar2_descriptor_qc/eis_qc_v2/selected_rb_qc_v2.csv
  three_pillars/pillar2_descriptor_qc/figure_data/wide_temperature_performance_summary.csv
  three_pillars/pillar2_descriptor_qc/figure_data/ea_benchmark_table.csv
  V1.0-qianduan-mainline/stage1_optimization/output/attapulgite_aice/closed_loop_metrics.json
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
OUT = Path(__file__).resolve().parent
QC = ROOT / "three_pillars" / "pillar2_descriptor_qc"
SEL = QC / "eis_qc_v2" / "selected_rb_qc_v2.csv"
WIDE = QC / "figure_data" / "wide_temperature_performance_summary.csv"
EABENCH = QC / "figure_data" / "ea_benchmark_table.csv"
CLM = (ROOT / "V1.0-qianduan-mainline" / "stage1_optimization" / "output"
       / "attapulgite_aice" / "closed_loop_metrics.json")

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 10, "axes.linewidth": 0.8,
    "axes.grid": True, "grid.alpha": 0.25, "figure.dpi": 200,
})

# representative samples (headline + boundary + generic-starch control)
SAMPLES = {
    "2026.5.9CS": ("LRS (lotus-root starch)", "#1f77b4", "o"),
    "2026.4.30CS": ("CHITO (chitosan)", "#d62728", "s"),
    "2026.4.27CS": ("corn-starch control", "#2ca02c", "^"),
}


def load_points():
    d = pd.read_csv(SEL)
    d = d[np.isfinite(d["selected_conductivity_s_cm"]) & (d["selected_conductivity_s_cm"] > 0)]
    return d


def fig3_sigma_t(d):
    fig, ax = plt.subplots(figsize=(5.2, 4.0))
    for sid, (label, color, mk) in SAMPLES.items():
        s = d[d.sample_id == sid].sort_values("temperature_C")
        if s.empty:
            continue
        ax.semilogy(s["temperature_C"], s["selected_conductivity_s_cm"],
                    marker=mk, ms=4.5, lw=1.3, color=color, label=label, alpha=0.9)
    ax.axvline(-40, color="gray", ls="--", lw=0.9)
    ax.text(-40, ax.get_ylim()[1], " 233 K", color="gray", va="top", fontsize=8)
    ax.set_xlabel("temperature (\u00b0C)")
    ax.set_ylabel("proton conductivity \u03c3 (S cm$^{-1}$)")
    ax.set_title("Wide-temperature proton conductivity \u03c3(T)")
    ax.legend(fontsize=8, loc="lower right")
    fig.tight_layout()
    fig.savefig(OUT / "Fig3_sigma_T.png")
    plt.close(fig)
    print("[ok] Fig3_sigma_T.png")


def fig4_arrhenius(d):
    wide = pd.read_csv(WIDE).set_index("sample_id")
    fig, axes = plt.subplots(1, 2, figsize=(9.6, 4.0))
    ax = axes[0]
    for sid, (label, color, mk) in SAMPLES.items():
        s = d[d.sample_id == sid].copy()
        if s.empty:
            continue
        s = s[s["temperature_K"] > 0]
        x = 1000.0 / s["temperature_K"]
        y = np.log(s["selected_conductivity_s_cm"] * s["temperature_K"])
        order = np.argsort(x.values)
        ea = wide.loc[sid, "ea_high_eV"] if sid in wide.index else None
        ea_txt = f"  (E$_a^{{high}}$={ea:.3f} eV)" if (ea is not None and np.isfinite(ea) and ea < 1) else "  (E$_a$ = transition)"
        ax.plot(x.values[order], y.values[order], marker=mk, ms=4, lw=1.1,
                color=color, label=label + ea_txt, alpha=0.9)
    ax.set_xlabel("1000 / T (K$^{-1}$)")
    ax.set_ylabel("ln(\u03c3T)  [S cm$^{-1}$ K]")
    ax.set_title("A  Segmented Arrhenius")
    ax.legend(fontsize=7, loc="lower left")

    # panel B: Ea benchmark bar
    eb = pd.read_csv(EABENCH)
    eb = eb[np.isfinite(eb["ea_eV"]) & (eb["ea_eV"] < 1.0)]  # drop CHITO transition pseudo-Ea
    labels = {"THIS-5.9CS": "LRS 5.9CS\n(this work)", "THIS-4.29CS": "LRS 4.29CS\n(this work)",
              "LIT-POP-2020": "POP-2020\n[ref]", "LIT-MFM300CR-2022": "MFM-300(Cr)\n[ref]",
              "LIT-AICE-2022": "AiCE sepiolite\n(mother) [ref]"}
    order = ["THIS-5.9CS", "THIS-4.29CS", "LIT-POP-2020", "LIT-MFM300CR-2022", "LIT-AICE-2022"]
    eb = eb.set_index("entry_id").loc[[e for e in order if e in eb.set_index("entry_id").index]]
    axb = axes[1]
    colors = ["#1f77b4" if e.startswith("THIS") else "#999999" for e in eb.index]
    bars = axb.bar(range(len(eb)), eb["ea_eV"], color=colors, width=0.6)
    axb.set_xticks(range(len(eb)))
    axb.set_xticklabels([labels.get(e, e) for e in eb.index], fontsize=7.5)
    axb.set_ylabel("E$_a^{high}$ (eV)")
    axb.set_title("B  High-temperature E$_a$ comparison")
    for i, v in enumerate(eb["ea_eV"]):
        axb.text(i, v + 0.003, f"{v:.3f}", ha="center", fontsize=7.5)
    fig.tight_layout()
    fig.savefig(OUT / "Fig4_arrhenius.png")
    plt.close(fig)
    print("[ok] Fig4_arrhenius.png")


def fig6_closed_loop():
    m = json.loads(CLM.read_text(encoding="utf-8"))
    prog = m["termination_status"]["progress"]
    traj = prog["score_trajectory"]
    best = m["best_final_score"]
    fig, axes = plt.subplots(1, 2, figsize=(9.6, 4.0))
    ax = axes[0]
    trials = np.arange(1, len(traj) + 1)
    ax.plot(trials, traj, "o-", color="#1f77b4", lw=1.3, ms=5, label="trial combined score")
    ax.axhline(best, color="#d62728", ls="--", lw=1.1, label=f"best = {best:.3f} (trial 1)")
    ax.set_xlabel("trial #")
    ax.set_ylabel("combined objective score")
    ax.set_title(f"A  Closed-loop objective trajectory\n(net improvement = {m['absolute_improvement']:.1f} within budget)")
    ax.legend(fontsize=8, loc="lower right")

    # panel B: (R,N) exploration + frozen MOBO recipes
    axb = axes[1]
    # BO trials we have exact R/N for (from metrics): trial1 + recent_trials
    bo_pts = [(0.186, 1.029, "t1*")]
    for rt in prog.get("recent_trials", []):
        bo_pts.append((rt["R"], rt["N"], f"t{rt['trial_id']}"))
    for R, N, tag in bo_pts:
        axb.scatter(R, N, c="#1f77b4", s=45, zorder=3)
        axb.annotate(tag, (R, N), fontsize=7, xytext=(3, 3), textcoords="offset points")
    # frozen MOBO+LLM official recipes (prospective, pushed)
    mobo = [(0.28, 0.96, "MOBO+LLM r1\n(2026-06-08)"), (0.42, 1.02, "MOBO+LLM r2\n(2026-06-10)")]
    for R, N, tag in mobo:
        axb.scatter(R, N, marker="*", c="#d62728", s=230, edgecolor="k", lw=0.5, zorder=4)
        axb.annotate(tag, (R, N), fontsize=7, color="#d62728", xytext=(5, -12), textcoords="offset points")
    axb.set_xlabel("R (acid ratio param)")
    axb.set_ylabel("N (normalized param)")
    axb.set_title("B  Design space: single-objective trials (blue)\n+ multi-objective BO\u2013LLM recipes (red star)")
    axb.margins(0.18)
    fig.tight_layout()
    fig.savefig(OUT / "Fig6_closed_loop.png")
    plt.close(fig)
    print("[ok] Fig6_closed_loop.png")


def main():
    d = load_points()
    fig3_sigma_t(d)
    fig4_arrhenius(d)
    fig6_closed_loop()
    print("[done] result figures in", OUT)


if __name__ == "__main__":
    main()
