# -*- coding: utf-8 -*-
"""P0/P2 v3 — FULL reproducibility + replication-hit calibration over ALL real repeats.

Earlier passes used only 2 repeat pairs (LRS 6.12 vs 6.15, starch 6.11 vs 6.13).
The user pointed out (correctly) that many more independent repeats of the SAME
materials were already measured but never processed/aggregated here. This script
consolidates EVERY available real, stage0-processed repeat:

  * LRS  (lotus-root starch, identical recipe, independently pressed/measured):
        0429CS, 0509CS, 6.12, 6.15_merged(s1), 0615_s2, 0616_s3, 0617_s3b   -> 7 repeats
  * starch:  0427CS, 0428CS, 6.11, 6.13                                       -> 4 repeats
  * CHITO :  0430CS, 0501CS                                                   -> 2 repeats (boundary)

All inputs are canonical stage0 `aggregated_results.json` / `arrhenius_analysis.json`
(the CS ones were produced by research/ablation/line_a_analysis and copied here
verbatim; the 6.15/6.16/6.17 ones were just produced by run_offline.py with the REAL
membrane thickness from each folder's 材料制备.txt). Nothing is fabricated; quantities
that cannot be computed are left null.

Honesty / data-quality flags baked in:
  * ALL thicknesses are documented in each folder's prep file (材料制备.txt for the June
    sets, 材料制备过程.txt for the April "CS" sets) and used verbatim. The two April LRS
    (0429CS=0.020, 0509CS=0.022 cm) are genuinely ~3.5x thinner than the five later June
    LRS (0.070-0.078 cm); the thickness is CORRECT (not a fallback), so their sigma is
    correct too. They are KEPT as legitimate repeats. We additionally report the later
    June "standardized-thickness" batch (~0.07 cm) separately: it reproduces somewhat
    tighter, i.e. a fabrication-consistency effect, NOT a data-quality exclusion.
  * Replication "hit" is a TRUE independent-replication test (leave-one-out consensus
    across repeats), not a within-curve self-consistency proxy.

Outputs (this folder):
  - repro_full_report.json        : per-group pairwise offset/scatter (by T band) + Ea spread
  - repro_full_calibration.png    : (a) LRS sigma(T) overlay, (b) reliability vs replication hit,
                                    (c) hit-rate vs temperature, (d) ECE learning curve
"""
from __future__ import annotations

import json
import math
import sys
from itertools import combinations
from pathlib import Path

import numpy as np
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import roc_auc_score

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
NDA = HERE.parents[2] / "research"
sys.path.insert(0, str(HERE))
from repro_and_calibration import ok_points, per_dataset_points, _load, _valid_segment_eas  # noqa: E402

# logical name -> (group, thickness_cm, june_standardized_batch)
# thickness for EVERY sample is read from its folder prep file (材料制备.txt for June,
# 材料制备过程.txt for April CS); the boolean marks the later June ~0.07cm standardized-
# fabrication batch (True) vs the early April batch (False) -- it is NOT a documented/
# undocumented flag (all are documented).
REGISTRY = {
    # --- LRS (藕粉), one material, 7 independent measurements ---
    "lineA_LRS_0429CS":      ("LRS", 0.020, False),   # April, thin pellet (documented 0.02)
    "lineA_LRS_0509CS":      ("LRS", 0.022, False),   # April, thin pellet (documented 0.022)
    "lineA_LRS_6.12":        ("LRS", 0.0737, True),
    "lineA_LRS_6.15_merged": ("LRS", 0.0701, True),
    "lineA_LRS_0615_s2":     ("LRS", 0.0778, True),
    "lineA_LRS_0616_s3":     ("LRS", 0.0734, True),
    "lineA_LRS_0617_s3b":    ("LRS", 0.0734, True),
    # --- starch (淀粉), one material, 4 measurements ---
    "lineA_starch_0427CS":   ("starch", 0.060, False),  # April
    "lineA_starch_0428CS":   ("starch", 0.060, False),  # April
    "lineA_starch_6.11":     ("starch", 0.0628, True),
    "lineA_starch_6.13":     ("starch", 0.0737, True),
    # --- chitosan (壳聚糖), one material, 2 measurements (boundary/negative class) ---
    "lineA_CHITO_0430CS":    ("CHITO", 0.050, False),  # April (no June batch)
    "lineA_CHITO_0501CS":    ("CHITO", 0.060, False),  # April (no June batch)
}
GROUPS = ["LRS", "starch", "CHITO"]

TOL_MAIN = 0.10   # |dlog10 sigma| <= 0.10 dex (~1.26x) => independent-replication HIT
TOL_SENS = 0.15
T_SPLIT = -20.0   # warm (>= -20C) vs cold (< -20C) reproducibility split


def names_in(group: str, jun_batch_only: bool = False) -> list[str]:
    out = []
    for n, (g, _th, doc) in REGISTRY.items():
        if g != group:
            continue
        if jun_batch_only and not doc:
            continue
        if (NDA / "data" / n / "aggregated_results.json").exists():
            out.append(n)
    return out


def sigma_curve(name: str) -> dict[float, float]:
    """T_C(rounded) -> log10 sigma, averaging duplicate temps."""
    pts = ok_points(_load(name, "aggregated_results.json"))
    by_t: dict[float, list[float]] = {}
    for p in pts:
        by_t.setdefault(round(p["temperature_C"]), []).append(
            math.log10(p["conductivity_S_per_cm"]))
    return {t: float(np.mean(v)) for t, v in by_t.items()}


# --------------------------------------------------------------------------- #
# A. pairwise reproducibility (offset + scatter), by temperature band
# --------------------------------------------------------------------------- #
def pairwise_repro(group: str, jun_batch_only: bool) -> dict:
    names = names_in(group, jun_batch_only)
    curves = {n: sigma_curve(n) for n in names}
    all_d, warm_d, cold_d = [], [], []
    pair_rows = []
    for a, b in combinations(names, 2):
        ca, cb = curves[a], curves[b]
        common = sorted(set(ca) & set(cb))
        ds = []
        for t in common:
            d = ca[t] - cb[t]
            ds.append(d)
            all_d.append(abs(d))
            (warm_d if t >= T_SPLIT else cold_d).append(abs(d))
        if ds:
            ds = np.array(ds)
            pair_rows.append({
                "pair": [a, b], "n_common_T": len(ds),
                "offset_mean_dex": float(ds.mean()),
                "scatter_std_dex": float(ds.std(ddof=1)) if len(ds) > 1 else None,
                "absmax_dex": float(np.abs(ds).max()),
            })
    def _stat(arr):
        a = np.array(arr)
        return {"n": int(a.size),
                "median_abs_dex": float(np.median(a)) if a.size else None,
                "p90_abs_dex": float(np.percentile(a, 90)) if a.size else None,
                "sigma_ratio_median_x": float(10 ** np.median(a)) if a.size else None}
    return {
        "n_repeats": len(names), "repeats": names,
        "n_pairs": len(pair_rows),
        "abs_dlog10_all": _stat(all_d),
        "abs_dlog10_warm_geT-20C": _stat(warm_d),
        "abs_dlog10_cold_ltT-20C": _stat(cold_d),
        "pairs": pair_rows,
    }


# --------------------------------------------------------------------------- #
# B. activation-energy spread across repeats (resolves the "6.5x" question)
# --------------------------------------------------------------------------- #
def ea_spread(group: str, jun_batch_only: bool) -> dict:
    names = names_in(group, jun_batch_only)
    highs, lows = [], []
    per = {}
    for n in names:
        eas = _valid_segment_eas(_load(n, "arrhenius_analysis.json"))
        hi = eas[0] if len(eas) >= 1 else None
        lo = eas[1] if len(eas) >= 2 else None
        per[n] = {"ea_high_eV": hi, "ea_low_activated_eV": lo}
        if hi is not None:
            highs.append(hi)
        if lo is not None:
            lows.append(lo)
    def _s(arr):
        a = np.array(arr)
        if a.size == 0:
            return {"n": 0}
        return {"n": int(a.size), "mean_eV": float(a.mean()),
                "std_eV": float(a.std(ddof=1)) if a.size > 1 else None,
                "min_eV": float(a.min()), "max_eV": float(a.max()),
                "max_over_min": float(a.max() / a.min()) if a.min() > 0 else None}
    return {"per_repeat": per, "ea_high_summary": _s(highs), "ea_low_summary": _s(lows)}


# --------------------------------------------------------------------------- #
# C. leave-one-out consensus replication-hit calibration
# --------------------------------------------------------------------------- #
def build_loo_samples(groups: list[str], tol: float, jun_batch_only: bool,
                      min_repeats_at_T: int = 3) -> list[dict]:
    """One sample per measured point: hit = point reproduces the consensus (median of
    the OTHER repeats at that T, +-1C) within `tol` dex. confidence = that point's
    conf_v1_physics (QC-based). Requires >= min_repeats_at_T repeats at the T."""
    samples = []
    for group in groups:
        names = names_in(group, jun_batch_only)
        curves = {n: sigma_curve(n) for n in names}
        feats = {n: {round(r["T_C"]): r for r in per_dataset_points(n, group)} for n in names}
        # union of integer temps
        temps = sorted({t for c in curves.values() for t in c})
        for t in temps:
            present = [n for n in names if any(abs(tt - t) <= 1 for tt in curves[n])]
            # value of each present dataset at ~t
            def val(n):
                cands = [(abs(tt - t), curves[n][tt]) for tt in curves[n] if abs(tt - t) <= 1]
                return min(cands, key=lambda x: x[0])[1] if cands else None
            vals = {n: val(n) for n in present}
            vals = {n: v for n, v in vals.items() if v is not None}
            if len(vals) < min_repeats_at_T:
                continue
            for n, v in vals.items():
                others = [vv for m, vv in vals.items() if m != n]
                consensus = float(np.median(others))
                d = abs(v - consensus)
                f = feats[n].get(t) or feats[n].get(round(t))
                if f is None:
                    # nearest feature within 1C
                    near = [(abs(tt - t), feats[n][tt]) for tt in feats[n] if abs(tt - t) <= 1]
                    f = min(near, key=lambda x: x[0])[1] if near else None
                if f is None:
                    continue
                samples.append({
                    "group": group, "dataset": n, "T_C": t,
                    "dlog10_vs_consensus": float(v - consensus),
                    "conf_v0_naiveKK": f["conf_v0_naiveKK"],
                    "conf_v1_physics": f["conf_v1_physics"],
                    "hit": 1 if d <= tol else 0,
                })
    return samples


def ece_brier_auroc(conf, label, n_bins: int = 5):
    conf = np.asarray(conf, float)
    label = np.asarray(label, float)
    n = len(conf)
    if n == 0:
        return None, None, None, []
    qs = np.quantile(conf, np.linspace(0, 1, n_bins + 1))
    qs[0] -= 1e-9
    ece, bins = 0.0, []
    for b in range(n_bins):
        lo, hi = qs[b], qs[b + 1]
        if hi <= lo:
            continue
        m = (conf > lo) & (conf <= hi)
        if m.sum() == 0:
            continue
        mc, ml = float(conf[m].mean()), float(label[m].mean())
        ece += (m.sum() / n) * abs(mc - ml)
        bins.append({"n": int(m.sum()), "mean_confidence": mc, "observed_hit_rate": ml})
    brier = float(np.mean((conf - label) ** 2))
    try:
        auroc = float(roc_auc_score(label, conf)) if len(set(label.tolist())) == 2 else None
    except ValueError:
        auroc = None
    return float(ece), brier, auroc, bins


def learning_curve(samples, conf_key, sizes, n_seed: int = 60):
    X = np.array([s[conf_key] for s in samples])
    y = np.array([s["hit"] for s in samples])
    n = len(X)
    out = []
    for size in sizes:
        if size >= n - 10:
            continue
        eces = []
        for seed in range(n_seed):
            rng = np.random.default_rng(seed)
            idx = rng.permutation(n)
            tr, te = idx[:size], idx[size:]
            if len(set(y[tr].tolist())) < 2:
                continue
            iso = IsotonicRegression(out_of_bounds="clip")
            iso.fit(X[tr], y[tr])
            ece, _, _, _ = ece_brier_auroc(iso.predict(X[te]), y[te])
            if ece is not None:
                eces.append(ece)
        if eces:
            out.append({"train_size": size, "mean_ECE": float(np.mean(eces)),
                        "std_ECE": float(np.std(eces)), "n_seed_used": len(eces)})
    return out


def hit_rate_by_T(samples, edges=(-80, -40, -20, 0, 30)) -> list[dict]:
    out = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = [s for s in samples if lo <= s["T_C"] < hi]
        if m:
            out.append({"T_band_C": f"[{lo},{hi})", "n": len(m),
                        "hit_rate": float(np.mean([s["hit"] for s in m]))})
    return out


def main() -> None:
    report = {"policy": (
        "ALL real repeats; CS sets from m6 stage0; 6.15/6.16/6.17 freshly run_offline'd; "
        "EVERY thickness read from the folder prep file (材料制备.txt / 材料制备过程.txt), "
        "no fabrication. Headline = all repeats; 'jun_standardized_batch' = later June "
        "~0.07cm batch reported separately (fabrication-consistency, not an exclusion)."),
        "TOL_MAIN_dex": TOL_MAIN, "T_split_C": T_SPLIT}

    # ---- A. reproducibility (all + June standardized batch) ----
    report["reproducibility"] = {}
    for g in GROUPS:
        report["reproducibility"][g] = {
            "all_repeats": pairwise_repro(g, jun_batch_only=False),
            "jun_standardized_batch": pairwise_repro(g, jun_batch_only=True),
        }

    # ---- B. Ea spread ----
    report["ea_spread"] = {g: {
        "all_repeats": ea_spread(g, False),
        "jun_standardized_batch": ea_spread(g, True),
    } for g in GROUPS}

    # ---- C. replication-hit calibration (LRS+starch have >=3 repeats) ----
    sm_all = build_loo_samples(["LRS", "starch"], TOL_MAIN, jun_batch_only=False)
    sm_doc = build_loo_samples(["LRS", "starch"], TOL_MAIN, jun_batch_only=True)
    sm_sens = build_loo_samples(["LRS", "starch"], TOL_SENS, jun_batch_only=False)

    def cal_block(samples):
        if not samples:
            return {"n": 0}
        c0 = [s["conf_v0_naiveKK"] for s in samples]
        c1 = [s["conf_v1_physics"] for s in samples]
        lab = [s["hit"] for s in samples]
        e0, b0, a0, bins0 = ece_brier_auroc(c0, lab)
        e1, b1, a1, bins1 = ece_brier_auroc(c1, lab)
        return {
            "n": len(samples), "n_hit": int(sum(lab)),
            "overall_hit_rate": float(np.mean(lab)),
            "hit_rate_by_group": {g: float(np.mean([s["hit"] for s in samples if s["group"] == g]))
                                  for g in {s["group"] for s in samples}},
            "hit_rate_by_T": hit_rate_by_T(samples),
            "conf_v0_naiveKK": {"ECE": e0, "Brier": b0, "AUROC": a0, "bins": bins0},
            "conf_v1_physics": {"ECE": e1, "Brier": b1, "AUROC": a1, "bins": bins1},
        }

    report["replication_hit_calibration"] = {
        "all_repeats": cal_block(sm_all),
        "jun_standardized_batch": cal_block(sm_doc),
        "tolerance_sensitivity": {
            "tol_main": TOL_MAIN, "hit_rate_main": float(np.mean([s["hit"] for s in sm_all])) if sm_all else None,
            "tol_sens": TOL_SENS, "hit_rate_sens": float(np.mean([s["hit"] for s in sm_sens])) if sm_sens else None,
        },
        "learning_curve_v1_all": learning_curve(sm_all, "conf_v1_physics",
                                                [20, 40, 60, 80, 100, 120, 140, 160]),
    }
    report["n_loo_samples_all"] = len(sm_all)
    report["n_loo_samples_jun_standardized"] = len(sm_doc)

    (HERE / "repro_full_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    # ---- figure ----
    fig, axes = plt.subplots(2, 2, figsize=(12.5, 9.5))
    axA, axB, axC, axD = axes.ravel()

    # (a) LRS sigma(T) overlay
    for n in names_in("LRS", False):
        c = sigma_curve(n)
        ts = sorted(c)
        jun = REGISTRY[n][2]
        axA.plot([1000.0 / (t + 273.15) for t in ts], [c[t] for t in ts],
                 ("o-" if jun else "x--"), ms=3, lw=1,
                 label=n.replace("lineA_LRS_", "") + ("" if jun else " (Apr thin)"))
    axA.set_xlabel("1000/T (1/K)")
    axA.set_ylabel("log10 sigma (S/cm)")
    axA.set_title("(a) 7 LRS repeats overlay (x-- = April thin ~0.02cm pellet)")
    axA.legend(fontsize=6, ncol=2)

    # (b) reliability vs replication hit (all)
    cal = report["replication_hit_calibration"]["all_repeats"]
    axB.plot([0, 1], [0, 1], "k--", lw=1, label="perfect")
    for key, c, mk in [("conf_v0_naiveKK", "tab:red", "o"), ("conf_v1_physics", "tab:blue", "s")]:
        bins = cal[key]["bins"]
        au = cal[key]["AUROC"]
        au_s = f"{au:.3f}" if au is not None else "n/a"
        axB.plot([b["mean_confidence"] for b in bins], [b["observed_hit_rate"] for b in bins],
                 mk + "-", color=c, label=f"{key}\n(ECE={cal[key]['ECE']:.3f}, AUROC={au_s})")
    axB.set_xlabel("Pre-experiment confidence")
    axB.set_ylabel("Observed replication-hit rate")
    axB.set_xlim(0, 1)
    axB.set_ylim(0, 1)
    axB.set_title(f"(b) Calibration vs LOO-consensus hit\n(n={cal['n']}, hit={cal['overall_hit_rate']:.2f}, tol={TOL_MAIN}dex)")
    axB.legend(loc="lower right", fontsize=7)

    # (c) hit rate vs temperature
    hb = cal["hit_rate_by_T"]
    axC.bar([h["T_band_C"] for h in hb], [h["hit_rate"] for h in hb],
            color="tab:green", edgecolor="k")
    for i, h in enumerate(hb):
        axC.text(i, h["hit_rate"] + 0.02, f"{h['hit_rate']:.2f}\nn={h['n']}", ha="center", fontsize=8)
    axC.set_ylabel("replication-hit rate")
    axC.set_ylim(0, 1.05)
    axC.set_title("(c) Reproducibility is temperature-dependent")

    # (d) learning curve
    lc = report["replication_hit_calibration"]["learning_curve_v1_all"]
    if lc:
        ts = [r["train_size"] for r in lc]
        me = [r["mean_ECE"] for r in lc]
        se = [r["std_ECE"] for r in lc]
        axD.errorbar(ts, me, yerr=se, fmt="o-", color="tab:blue", capsize=3, label="isotonic-calibrated ECE")
        axD.axhline(cal["conf_v1_physics"]["ECE"], color="0.5", ls=":",
                    label=f"uncalibrated ECE={cal['conf_v1_physics']['ECE']:.3f}")
        axD.set_xlabel("# repeat-labeled training points")
        axD.set_ylabel("held-out ECE (mean over seeds)")
        axD.set_title("(d) Calibration learning curve (sample-efficiency)")
        axD.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(HERE / "repro_full_calibration.png", dpi=150)
    plt.close(fig)

    # ---- console (REAL numbers) ----
    print("=== FULL reproducibility (ALL real repeats) ===")
    for g in GROUPS:
        a = report["reproducibility"][g]["all_repeats"]
        d = report["reproducibility"][g]["jun_standardized_batch"]
        print(f"\n[{g}] repeats(all)={a['n_repeats']} pairs={a['n_pairs']}  "
              f"repeats(Jun-std)={d['n_repeats']}")
        for lab, blk in [("ALL    ", a), ("Jun-std", d)]:
            s = blk["abs_dlog10_all"]; w = blk["abs_dlog10_warm_geT-20C"]; c = blk["abs_dlog10_cold_ltT-20C"]
            if s["n"]:
                print(f"   {lab}|dlog10s| median={s['median_abs_dex']:.3f} (x{s['sigma_ratio_median_x']:.2f}) "
                      f"p90={s['p90_abs_dex']:.3f} | warm med={w['median_abs_dex']} cold med={c['median_abs_dex']}")
        eh = report["ea_spread"][g]["all_repeats"]["ea_high_summary"]
        el = report["ea_spread"][g]["all_repeats"]["ea_low_summary"]
        if eh.get("n"):
            print(f"   Ea_high n={eh['n']} mean={eh['mean_eV']:.3f} std={eh.get('std_eV')} "
                  f"range=[{eh['min_eV']:.3f},{eh['max_eV']:.3f}] max/min={eh.get('max_over_min')}")
        if el.get("n"):
            print(f"   Ea_low  n={el['n']} mean={el['mean_eV']:.3f} std={el.get('std_eV')} "
                  f"range=[{el['min_eV']:.3f},{el['max_eV']:.3f}] max/min={el.get('max_over_min')}")

    print("\n=== Replication-hit calibration (LOO consensus, LRS+starch) ===")
    for tag in ["all_repeats", "jun_standardized_batch"]:
        c = report["replication_hit_calibration"][tag]
        if c.get("n"):
            print(f"[{tag}] n={c['n']} hit_rate={c['overall_hit_rate']:.3f}  "
                  f"v0 AUROC={c['conf_v0_naiveKK']['AUROC']} ECE={c['conf_v0_naiveKK']['ECE']:.3f} | "
                  f"v1 AUROC={c['conf_v1_physics']['AUROC']} ECE={c['conf_v1_physics']['ECE']:.3f}")
            print(f"     hit by T: " + "  ".join(f"{h['T_band_C']}:{h['hit_rate']:.2f}(n{h['n']})"
                                                 for h in c["hit_rate_by_T"]))
    ts = report["replication_hit_calibration"]["tolerance_sensitivity"]
    print(f"tolerance: {ts['tol_main']}dex->hit {ts['hit_rate_main']:.3f}; "
          f"{ts['tol_sens']}dex->hit {ts['hit_rate_sens']:.3f}")
    lc = report["replication_hit_calibration"]["learning_curve_v1_all"]
    if lc:
        print(f"learning curve: first(size={lc[0]['train_size']})={lc[0]['mean_ECE']:.3f} "
              f"-> last(size={lc[-1]['train_size']})={lc[-1]['mean_ECE']:.3f} "
              f"(uncal={cal['conf_v1_physics']['ECE']:.3f})")
    print(f"\nSaved -> {HERE}/repro_full_report.json + repro_full_calibration.png")


if __name__ == "__main__":
    main()
