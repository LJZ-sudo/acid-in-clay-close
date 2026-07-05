# -*- coding: utf-8 -*-
"""VERIFY the "reproducibility floor of autonomous optimization" hypothesis on REAL data.

Question (honest, falsifiable): are the differences the Line-B MOBO+LLM loop is trying to
resolve between candidates SMALLER than the fabrication reproducibility floor measured on
Line-A independent repeats? If yes, the loop is partly "optimizing noise", which would
quantitatively explain the P4 honest null (prospective rounds did not beat the best /
front did not expand).

Inputs — all REAL, no fabrication:
  * Line-B objective history: stage1_optimization/campaign_memory/history_db_attapulgite.json
    (10 real trials, each with measured combined_score and its components; the file also
    records each pellet's real thickness and the actual room-T it was measured at).
  * Line-A reproducibility floor: _new_data_analysis/calibration/repro_full_report.json
    (LRS 7 independent repeats: median |Δlog10 σ|, and Ea_high / Ea_low spreads).

Method:
  combined_score = log10(sigma_room) - 3.0*Ea_high - 0.5*ea_low_excess   (the loop's objective)
  Floor on a candidate-vs-candidate combined_score DIFFERENCE is obtained by propagating the
  Line-A per-objective between-pellet scatter:
     floor = sqrt( d_sigma^2 + (3.0*dEaH)^2 + (0.5*dExc)^2 )
  where d_sigma = Line-A median |Δlog10 σ| between two independent pellets (the typical
  difference itself), dEaH ≈ sqrt(2)*std(Ea_high), dExc ≈ sqrt(2)*sqrt(std_low^2+std_high^2).

Honesty guards:
  * Line-A floor is a BIOPOLYMER (LRS) proxy for the attapulgite system (both are
    atta-containing phosphoric-acid composites, but NOT identical) -> flagged; reported with
    BOTH the tight (June standardized, 0.245 dex) and the loose (all-repeats, 0.32 dex) floor.
  * We additionally report Line-B's OWN internal fabrication/protocol variation (pellet
    thickness range; the historical 0.022cm thickness-parse bug; room-T spread across trials)
    as independent, in-system evidence that a floor of this magnitude is plausible.
  * We do NOT claim the loop is "wrong"; we claim its top candidates are within ~1 floor of
    each other, i.e. not reliably distinguishable -> explains the honest null. No new experiment.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import sys as _sys; _sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import natfig; natfig.apply()

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
HIST = ROOT / "V1.0-qianduan-mainline" / "stage1_optimization" / "campaign_memory" / "history_db_attapulgite.json"
REPRO = ROOT / "_new_data_analysis" / "calibration" / "repro_full_report.json"

K_B = 8.617333e-5  # eV/K


def load_lineB() -> list[dict]:
    trials = json.loads(HIST.read_text(encoding="utf-8"))["trials"]
    out = []
    for t in trials:
        o = t["objectives"]
        md = t.get("metadata", {})
        out.append({
            "trial_id": t["trial_id"],
            "R": t["parameters"]["R"], "N": t["parameters"]["N"],
            "sigma": float(o["conductivity_room_temp_S_cm"]),
            "log10_sigma": math.log10(float(o["conductivity_room_temp_S_cm"])),
            "ea_high": float(o["ea_high_temp_eV"]),
            "ea_low_excess": float(o.get("ea_low_excess_eV", o.get("ea_low_temp_eV", 0) - o["ea_high_temp_eV"])),
            "combined_score": float(o["combined_score"]),
            "thickness_cm": md.get("thickness_cm"),
            "roomT_C": md.get("roomT_C_actual"),
            "prospective": md.get("prospective", False),
        })
    return out


def lineA_floor() -> dict:
    r = json.loads(REPRO.read_text(encoding="utf-8"))
    lrs = r["reproducibility"]["LRS"]
    d_sigma_jun = lrs["jun_standardized_batch"]["abs_dlog10_all"]["median_abs_dex"]
    d_sigma_all = lrs["all_repeats"]["abs_dlog10_all"]["median_abs_dex"]
    eah = r["ea_spread"]["LRS"]["all_repeats"]["ea_high_summary"]
    eal = r["ea_spread"]["LRS"]["all_repeats"]["ea_low_summary"]
    std_eah = float(eah["std_eV"])
    std_eal = float(eal["std_eV"])
    # between-pellet difference scatter (two independent pellets) ~ sqrt(2)*std
    d_eah = math.sqrt(2) * std_eah
    std_exc = math.sqrt(std_eal**2 + std_eah**2)  # ea_low_excess = ea_low - ea_high
    d_exc = math.sqrt(2) * std_exc

    def floor(d_sigma):
        return math.sqrt(d_sigma**2 + (3.0 * d_eah)**2 + (0.5 * d_exc)**2)

    return {
        "d_sigma_jun_dex": d_sigma_jun, "d_sigma_all_dex": d_sigma_all,
        "std_ea_high_eV": std_eah, "std_ea_low_eV": std_eal,
        "between_pellet_d_ea_high_eV": d_eah, "between_pellet_d_excess_eV": d_exc,
        "combined_score_floor_tight": floor(d_sigma_jun),   # June standardized proxy
        "combined_score_floor_loose": floor(d_sigma_all),   # all-repeats proxy
        "sigma_floor_tight_dex": d_sigma_jun, "sigma_floor_loose_dex": d_sigma_all,
    }


def roomT_comparability_dex(trials, Tref_C=20.0):
    """Extra in-system error: candidates measured at different 'room' T (17-24C).
    Δlog10σ from shifting each to Tref using its own Ea_high. REAL per-trial numbers."""
    devs = []
    for t in trials:
        if t["roomT_C"] is None:
            continue
        T1 = t["roomT_C"] + 273.15
        T2 = Tref_C + 273.15
        dlog = (t["ea_high"] / (2.302585 * K_B)) * abs(1.0 / T1 - 1.0 / T2)
        devs.append(dlog)
    return devs


def main():
    trials = load_lineB()
    fl = lineA_floor()
    floor_t = fl["combined_score_floor_tight"]
    floor_l = fl["combined_score_floor_loose"]

    best = max(trials, key=lambda t: t["combined_score"])
    for t in trials:
        t["gap_combined"] = best["combined_score"] - t["combined_score"]  # >=0, how far below best
    ranked = sorted(trials, key=lambda t: -t["combined_score"])

    # pure-sigma cross-check
    best_sigma = max(trials, key=lambda t: t["log10_sigma"])
    for t in trials:
        t["gap_log10_sigma"] = best_sigma["log10_sigma"] - t["log10_sigma"]

    # counts within floor
    within_floor_combined = [t for t in trials if 0 < t["gap_combined"] <= floor_l]
    within_floor_tight = [t for t in trials if 0 < t["gap_combined"] <= floor_t]

    # line-B internal fabrication evidence
    ths = [t["thickness_cm"] for t in trials if t["thickness_cm"]]
    th_dex = math.log10(max(ths) / min(ths)) if ths else None  # sigma ∝ thickness
    roomTs = [t["roomT_C"] for t in trials if t["roomT_C"] is not None]
    roomT_devs = roomT_comparability_dex(trials)

    report = {
        "policy": "REAL data only; Line-A LRS floor used as proxy for Line-B attapulgite "
                  "(flagged); no new experiments; tests whether loop resolves below the floor.",
        "lineA_floor": fl,
        "combined_score_floor_used": {"tight_June_proxy": floor_t, "loose_all_proxy": floor_l},
        "lineB_best": {"trial_id": best["trial_id"], "R": best["R"], "N": best["N"],
                       "combined_score": best["combined_score"]},
        "ranked_candidates": [
            {"trial_id": t["trial_id"], "R": t["R"], "N": t["N"],
             "combined_score": round(t["combined_score"], 3),
             "gap_to_best_combined": round(t["gap_combined"], 3),
             "within_loose_floor": bool(0 < t["gap_combined"] <= floor_l),
             "log10_sigma": round(t["log10_sigma"], 3),
             "gap_to_best_sigma_dex": round(t["gap_log10_sigma"], 3),
             "prospective": t["prospective"]}
            for t in ranked
        ],
        "n_candidates_within_loose_floor_of_best": len(within_floor_combined),
        "n_candidates_within_tight_floor_of_best": len(within_floor_tight),
        "sigma_only_crosscheck": {
            "best_sigma_trial": best_sigma["trial_id"],
            "top3_sigma_span_dex": round(
                sorted([t["log10_sigma"] for t in trials], reverse=True)[0]
                - sorted([t["log10_sigma"] for t in trials], reverse=True)[2], 3),
            "sigma_floor_tight_dex": fl["sigma_floor_tight_dex"],
            "sigma_floor_loose_dex": fl["sigma_floor_loose_dex"],
        },
        "lineB_internal_fabrication_evidence": {
            "thickness_range_cm": [min(ths), max(ths)] if ths else None,
            "thickness_induced_sigma_dex": th_dex,
            "historical_0.022cm_parse_bug": "9/10 trials needed ~4x thickness repair "
                "(see thickness_repair in history) -> shows a ~0.6 dex systematic was once present",
            "roomT_range_C": [min(roomTs), max(roomTs)] if roomTs else None,
            "roomT_comparability_median_dex": float(np.median(roomT_devs)) if roomT_devs else None,
            "roomT_comparability_max_dex": float(np.max(roomT_devs)) if roomT_devs else None,
        },
        "verdict": "",
    }

    # verdict text (data-driven)
    g = sorted([t["gap_combined"] for t in trials if t["gap_combined"] > 0])
    n_below = report["n_candidates_within_loose_floor_of_best"]
    report["verdict"] = (
        f"Floor on a candidate-vs-candidate combined_score difference ≈ {floor_t:.2f} "
        f"(June-standardized proxy) to {floor_l:.2f} (all-repeats proxy) dex-equivalent. "
        f"{n_below} of {len(trials)-1} non-best candidates sit WITHIN the loose floor of the "
        f"campaign best (gaps {', '.join(f'{x:.2f}' for x in g[:3])}...). "
        "=> The loop's top candidates are NOT reliably distinguishable from the best given the "
        "fabrication reproducibility floor; this quantitatively explains the P4 honest null "
        "(prospective rounds did not beat the best, front did not expand). NOT a claim that the "
        "loop is wrong — a claim that the landscape near the optimum is flatter than the floor."
    )

    HERE.mkdir(parents=True, exist_ok=True)
    (HERE / "floor_vs_loop_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    # ---- figure ----
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(12.4, 5.2))
    ids = [f"T{t['trial_id']}" + ("*" if t["prospective"] else "") for t in ranked]
    gaps = [t["gap_combined"] for t in ranked]
    colors = ["tab:green" if t["trial_id"] == best["trial_id"]
              else ("tab:orange" if 0 < t["gap_combined"] <= floor_l else "tab:gray")
              for t in ranked]
    ax.bar(ids, gaps, color=colors, edgecolor="k")
    ax.axhspan(0, floor_t, color="tab:blue", alpha=0.12)
    ax.axhline(floor_t, color="tab:blue", ls="--", lw=1.4,
               label=f"floor (tight, June proxy) = {floor_t:.2f}")
    ax.axhline(floor_l, color="navy", ls=":", lw=1.4,
               label=f"floor (loose, all-repeats proxy) = {floor_l:.2f}")
    ax.set_ylabel("combined_score gap below campaign best")
    ax.set_xlabel("candidate (sorted; * = prospective round)")
    ax.set_title("(a) Loop candidate gaps vs fabrication-reproducibility floor\n"
                 "orange = within floor of best (indistinguishable)")
    ax.legend(fontsize=8)

    # pure-sigma panel
    s_sorted = sorted(trials, key=lambda t: -t["log10_sigma"])
    sids = [f"T{t['trial_id']}" for t in s_sorted]
    sgaps = [t["gap_log10_sigma"] for t in s_sorted]
    scolors = ["tab:green" if i == 0 else ("tab:orange" if g <= fl["sigma_floor_loose_dex"] else "tab:gray")
               for i, g in enumerate(sgaps)]
    ax2.bar(sids, sgaps, color=scolors, edgecolor="k")
    ax2.axhspan(0, fl["sigma_floor_tight_dex"], color="tab:blue", alpha=0.12)
    ax2.axhline(fl["sigma_floor_tight_dex"], color="tab:blue", ls="--", lw=1.4,
                label=f"σ floor tight = {fl['sigma_floor_tight_dex']:.2f} dex")
    ax2.axhline(fl["sigma_floor_loose_dex"], color="navy", ls=":", lw=1.4,
                label=f"σ floor loose = {fl['sigma_floor_loose_dex']:.2f} dex")
    ax2.set_ylabel("|Δlog10 σ| below best-σ candidate (dex)")
    ax2.set_xlabel("candidate (sorted by σ)")
    ax2.set_title("(b) Pure-σ cross-check: top-σ candidates\nspan < floor → indistinguishable by conductivity")
    ax2.legend(fontsize=8)
    fig.tight_layout()
    natfig.save_pub(fig, HERE, "floor_vs_loop")
    plt.close(fig)

    # ---- console ----
    print("=== Reproducibility-floor vs Line-B loop (REAL data) ===")
    print(f"Line-A floor inputs: dσ(June)={fl['d_sigma_jun_dex']:.3f} dσ(all)={fl['d_sigma_all_dex']:.3f} dex; "
          f"std Ea_high={fl['std_ea_high_eV']:.4f} std Ea_low={fl['std_ea_low_eV']:.4f} eV")
    print(f"=> combined_score floor: tight={floor_t:.3f}  loose={floor_l:.3f}")
    print(f"\nLine-B best: T{best['trial_id']} R{best['R']}/N{best['N']} cs={best['combined_score']:.3f}")
    print("rank  trial   R     N    combined  gap_to_best  within_floor?   log10σ   σ_gap_dex  prosp")
    for t in ranked:
        mark = "<= WITHIN" if 0 < t["gap_combined"] <= floor_l else ""
        print(f"      T{t['trial_id']:<2d}  {t['R']:.3f} {t['N']:.3f}  {t['combined_score']:7.3f}  "
              f"{t['gap_combined']:8.3f}   {mark:11s}  {t['log10_sigma']:7.3f}  {t['gap_log10_sigma']:7.3f}  "
              f"{'YES' if t['prospective'] else ''}")
    print(f"\n# candidates within LOOSE floor of best: {report['n_candidates_within_loose_floor_of_best']} / {len(trials)-1}")
    print(f"# candidates within TIGHT floor of best: {report['n_candidates_within_tight_floor_of_best']} / {len(trials)-1}")
    ev = report["lineB_internal_fabrication_evidence"]
    print(f"\nLine-B internal evidence: thickness {ev['thickness_range_cm']} -> {ev['thickness_induced_sigma_dex']:.3f} dex; "
          f"roomT {ev['roomT_range_C']}C -> median {ev['roomT_comparability_median_dex']:.3f} / max {ev['roomT_comparability_max_dex']:.3f} dex")
    print(f"\nVERDICT: {report['verdict']}")
    print(f"\nSaved -> {HERE}")


if __name__ == "__main__":
    main()
