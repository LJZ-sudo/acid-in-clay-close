# -*- coding: utf-8 -*-
"""P2 / NC-命门 v2 — Calibrate measurement confidence against TRUE independent-
replication HITS (not the v0 transport self-consistency proxy), plus a calibration
*learning curve* (ECE vs amount of repeat-labeled data).

Why this is the real upgrade the plan (§11) asked for:
  * v0 (repro_and_calibration.py): label = isotonic self-consistency of ONE curve
    -> a within-curve proxy, base rate ~98%.
  * v2 (here): label = whether an INDEPENDENT repeat measurement reproduced sigma(T)
    within a pre-declared physical tolerance. This is a genuine "did the agent's
    pre-experiment confidence predict real reproducibility?" test.

Real data only (reuses repro_and_calibration's REAL per-point features + the real
repro pairs). No fabrication. If the confidence has weak predictive power, that is
reported honestly (it points to "need more repeat pairs", not a fake high number).

Outputs (this folder):
  - repro_hit_report.json         : hit rates, ECE/Brier/AUROC vs independent-replication label
  - repro_hit_calibration.png     : (a) reliability vs replication hit, (b) ECE learning curve
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import roc_auc_score

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
# reuse the REAL per-point feature/label code and the REAL repro pairing (no reimpl)
from repro_and_calibration import per_dataset_points, repro_pair  # noqa: E402

PAIRS = [
    ("lineA_LRS_6.12", "lineA_LRS_6.15_merged", "A_LRS"),
    ("lineA_starch_6.11", "lineA_starch_6.13", "A_starch"),
]
TOL_MAIN = 0.10  # |dlog10 sigma| <= 0.10 dex (~1.26x) => independent-replication HIT
TOL_SENS = 0.15  # sensitivity check (~1.41x)


def build_samples(tol: float) -> list[dict]:
    """Each matched-temperature point becomes one (confidence, replication-hit) sample.

    confidence = pre-experiment confidence from the FIRST run's QC features
    (conf_v0 = naive KK, conf_v1 = physics-aware); both computed by the v0 code.
    label (hit) = the SECOND, independent run reproduced sigma(T) within `tol` dex.
    The two come from different runs -> no leakage.
    """
    samples: list[dict] = []
    for n1, n2, group in PAIRS:
        feats = {round(r["T_C"], 1): r for r in per_dataset_points(n1, group)}
        rep = repro_pair(n1, n2)
        for mp in rep["matched_points"]:
            f = feats.get(round(mp["T1_C"], 1))
            if f is None:
                continue
            samples.append({
                "group": group,
                "T_C": round(mp["T1_C"], 1),
                "dlog10_sigma": mp["dlog10_sigma"],
                "conf_v0_naiveKK": f["conf_v0_naiveKK"],
                "conf_v1_physics": f["conf_v1_physics"],
                "hit": 1 if abs(mp["dlog10_sigma"]) <= tol else 0,
            })
    return samples


def ece_brier_auroc(conf, label, n_bins: int = 5):
    conf = np.asarray(conf, float)
    label = np.asarray(label, float)
    n = len(conf)
    qs = np.quantile(conf, np.linspace(0, 1, n_bins + 1))
    qs[0] -= 1e-9
    ece = 0.0
    bins = []
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


def learning_curve(samples, conf_key, sizes, n_seed: int = 40):
    """ECE on a held-out set after fitting an isotonic calibrator on `size` points.

    This measures CALIBRATION SAMPLE-EFFICIENCY: does the confidence->hit mapping get
    better-calibrated as more repeat-labeled data accrues? It is NOT a claim of online
    agent self-improvement; it is a data-quantity learning curve on real repeat labels.
    """
    X = np.array([s[conf_key] for s in samples])
    y = np.array([s["hit"] for s in samples])
    n = len(X)
    out = []
    for size in sizes:
        if size >= n - 8:  # keep >=8 held-out points
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
            pte = iso.predict(X[te])
            ece, _, _, _ = ece_brier_auroc(pte, y[te])
            eces.append(ece)
        if eces:
            out.append({
                "train_size": size,
                "mean_ECE": float(np.mean(eces)),
                "std_ECE": float(np.std(eces)),
                "n_seed_used": len(eces),
            })
    return out


def main() -> None:
    samples = build_samples(TOL_MAIN)
    n = len(samples)
    hits = sum(s["hit"] for s in samples)
    by_group = {}
    for s in samples:
        g = by_group.setdefault(s["group"], {"n": 0, "hit": 0})
        g["n"] += 1
        g["hit"] += s["hit"]

    conf_v0 = [s["conf_v0_naiveKK"] for s in samples]
    conf_v1 = [s["conf_v1_physics"] for s in samples]
    label = [s["hit"] for s in samples]

    ece0, brier0, auroc0, bins0 = ece_brier_auroc(conf_v0, label)
    ece1, brier1, auroc1, bins1 = ece_brier_auroc(conf_v1, label)

    # sensitivity: rebuild label at a looser tolerance
    samples_sens = build_samples(TOL_SENS)
    hits_sens = sum(s["hit"] for s in samples_sens)
    _, _, auroc1_sens, _ = ece_brier_auroc(
        [s["conf_v1_physics"] for s in samples_sens], [s["hit"] for s in samples_sens])

    sizes = [10, 15, 20, 25, 30, 35, 40, 45, 50]
    lc_v1 = learning_curve(samples, "conf_v1_physics", sizes)
    # uncalibrated baseline ECE (no isotonic, raw conf on full set) for a reference line
    base_ece_v1 = ece1

    report = {
        "label_definition": (
            f"independent-replication HIT = |dlog10 sigma(T)| <= {TOL_MAIN} dex (~1.26x) "
            "between two INDEPENDENT repeat measurements (LRS 6.12 vs 6.15_merged; "
            "starch 6.11 vs 6.13). This REPLACES the v0 within-curve self-consistency proxy."
        ),
        "n_samples": n,
        "n_hit": hits,
        "overall_hit_rate": hits / n if n else None,
        "hit_rate_by_group": {g: v["hit"] / v["n"] for g, v in by_group.items()},
        "tolerance_sensitivity": {
            "tol_main_dex": TOL_MAIN, "hit_rate_main": hits / n if n else None,
            "tol_sens_dex": TOL_SENS, "hit_rate_sens": hits_sens / len(samples_sens),
            "auroc_v1_main": auroc1, "auroc_v1_sens": auroc1_sens,
        },
        "calibration_vs_replication_hit": {
            "conf_v0_naiveKK": {"ECE": ece0, "Brier": brier0, "AUROC": auroc0, "bins": bins0},
            "conf_v1_physics": {"ECE": ece1, "Brier": brier1, "AUROC": auroc1, "bins": bins1},
        },
        "learning_curve_v1_ECE_vs_data": lc_v1,
        "uncalibrated_baseline_ECE_v1": base_ece_v1,
        "honesty_notes": (
            "Label is now a TRUE independent-replication hit (not a self-consistency "
            "proxy). N is small (two repeat pairs, ~%d matched points): metrics are an "
            "estimate, reported with per-bin n. The learning curve is calibration "
            "sample-efficiency on real repeat labels, NOT online agent self-improvement. "
            "If AUROC ~0.5, the honest reading is: current single-curve QC confidence has "
            "limited power to predict cross-run reproducibility -> motivates more repeat "
            "pairs (see experiment list)." % n
        ),
    }
    (HERE / "repro_hit_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    # ---- figure ----
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(11.2, 4.8))
    ax.plot([0, 1], [0, 1], "k--", lw=1, label="perfect")
    for bins, c, mk, name, ece, au in [
        (bins0, "tab:red", "o", "conf_v0 naiveKK", ece0, auroc0),
        (bins1, "tab:blue", "s", "conf_v1 physics", ece1, auroc1),
    ]:
        xs = [b["mean_confidence"] for b in bins]
        ys = [b["observed_hit_rate"] for b in bins]
        au_s = f"{au:.3f}" if au is not None else "n/a"
        ax.plot(xs, ys, mk + "-", color=c, label=f"{name}\n(ECE={ece:.3f}, AUROC={au_s})")
    ax.set_xlabel("Pre-experiment confidence")
    ax.set_ylabel("Observed independent-replication hit rate")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_title(f"(a) Calibration vs TRUE replication hit\n(n={n}, hit rate={hits/n:.2f}, tol={TOL_MAIN}dex)")
    ax.legend(loc="lower right", fontsize=7)

    if lc_v1:
        ts = [r["train_size"] for r in lc_v1]
        me = [r["mean_ECE"] for r in lc_v1]
        se = [r["std_ECE"] for r in lc_v1]
        ax2.errorbar(ts, me, yerr=se, fmt="o-", color="tab:blue", capsize=3, label="isotonic-calibrated ECE")
        ax2.axhline(base_ece_v1, color="0.5", ls=":", label=f"uncalibrated ECE={base_ece_v1:.3f}")
        ax2.set_xlabel("# repeat-labeled training points")
        ax2.set_ylabel("held-out ECE (mean over seeds)")
        ax2.set_title("(b) Calibration learning curve\n(sample-efficiency on real repeats; not online self-improve)")
        ax2.legend(loc="upper right", fontsize=7)
    fig.tight_layout()
    fig.savefig(HERE / "repro_hit_calibration.png", dpi=150)
    plt.close(fig)

    # ---- console (REAL numbers) ----
    print("=== P2 v2: calibration vs TRUE independent-replication hit ===")
    print(f"n_samples={n}  hits={hits}  hit_rate={hits/n:.3f}  (tol={TOL_MAIN} dex)")
    for g, v in by_group.items():
        print(f"  {g}: n={v['n']} hit_rate={v['hit']/v['n']:.3f}")
    print(f"conf_v0 naiveKK : ECE={ece0:.3f} Brier={brier0:.3f} AUROC={auroc0}")
    print(f"conf_v1 physics : ECE={ece1:.3f} Brier={brier1:.3f} AUROC={auroc1}")
    print(f"tol sensitivity : main {TOL_MAIN}->hit {hits/n:.3f} AUROC {auroc1}; "
          f"sens {TOL_SENS}->hit {hits_sens/len(samples_sens):.3f} AUROC {auroc1_sens}")
    print("\nlearning curve (ECE vs #repeat-labeled training points), conf_v1:")
    for r in lc_v1:
        print(f"  size={r['train_size']:3d}  ECE={r['mean_ECE']:.3f}+-{r['std_ECE']:.3f}  "
              f"(seeds={r['n_seed_used']})")
    if lc_v1:
        print(f"  uncalibrated baseline ECE={base_ece_v1:.3f}; "
              f"first={lc_v1[0]['mean_ECE']:.3f} -> last={lc_v1[-1]['mean_ECE']:.3f}")
    print(f"\nSaved -> {HERE}")


if __name__ == "__main__":
    main()
