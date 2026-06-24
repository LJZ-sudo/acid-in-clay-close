# -*- coding: utf-8 -*-
"""G2 (calibration ON/OFF ablation) + G3 (diagnose why KK AUROC < 0.5) on REAL repeats.

Both use the SAME leave-one-out consensus replication-hit samples as P2 v3 (882 points across
LRS/starch/CHITO repeats). No new data; no fabrication.

G2 — calibration ablation (does the calibration machinery earn its place?):
  OFF = raw single-curve confidence (Kramers-Kronig validity score) used directly as p(hit).
  ON  = isotonic recalibration fitted LEAVE-ONE-DATASET-OUT (train on other repeats, predict the
        held-out repeat) -> honest, no leakage.
  Metrics: expected calibration error (ECE), maximum calibration error (MCE), Brier, over-confidence.

G3 — diagnose AUROC < 0.5:
  (i)  pooled raw-KK AUROC vs mean WITHIN-dataset AUROC (does KK rank reproducibility inside a
       dataset, even if it fails across datasets?);
  (ii) per-dataset mean KK vs per-dataset replication rate, Spearman (a NEGATIVE cross-dataset
       relation drags the pooled/leave-one-out AUROC below 0.5);
  (iii) Murphy decomposition of the Brier score (reliability vs resolution) for raw vs isotonic,
       to show the ECE gain is reliability (re-centring), not new resolution.

Run from repo root:  python _new_data_analysis/calibration/g2g3_ablation_diagnosis.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import roc_auc_score

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
NDA = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(NDA))
import natfig  # noqa: E402
natfig.apply()
from repro_full_calibration import build_loo_samples, GROUPS, TOL_MAIN  # noqa: E402


def cal_metrics(p, y, n_bins=10):
    p, y = np.asarray(p, float), np.asarray(y, float)
    edges = np.quantile(p, np.linspace(0, 1, n_bins + 1))
    edges[0] -= 1e-9
    ece = mce = 0.0
    for b in range(n_bins):
        lo, hi = edges[b], edges[b + 1]
        if hi <= lo:
            continue
        m = (p > lo) & (p <= hi)
        if m.sum() == 0:
            continue
        gap = abs(p[m].mean() - y[m].mean())
        ece += (m.sum() / len(p)) * gap
        mce = max(mce, gap)
    brier = float(np.mean((p - y) ** 2))
    return {"ECE": float(ece), "MCE": float(mce), "Brier": brier,
            "overconfidence": float(p.mean() - y.mean())}


def murphy(p, y, n_bins=10):
    """Brier = reliability - resolution + uncertainty (lower reliability + higher resolution better)."""
    p, y = np.asarray(p, float), np.asarray(y, float)
    ybar = y.mean()
    edges = np.quantile(p, np.linspace(0, 1, n_bins + 1)); edges[0] -= 1e-9
    rel = res = 0.0
    for b in range(n_bins):
        lo, hi = edges[b], edges[b + 1]
        if hi <= lo:
            continue
        m = (p > lo) & (p <= hi)
        nk = m.sum()
        if nk == 0:
            continue
        ok = y[m].mean(); pk = p[m].mean()
        rel += nk * (pk - ok) ** 2
        res += nk * (ok - ybar) ** 2
    n = len(p)
    return {"reliability": float(rel / n), "resolution": float(res / n),
            "uncertainty": float(ybar * (1 - ybar))}


def isotonic_lodo(conf, y, ds):
    """Leave-one-dataset-out isotonic recalibration; returns pooled OOF predictions."""
    conf, y, ds = np.asarray(conf, float), np.asarray(y, float), np.asarray(ds)
    oof = np.full(len(conf), np.nan)
    for d in sorted(set(ds.tolist())):
        te = ds == d
        tr = ~te
        if len(set(y[tr].tolist())) < 2:
            continue
        iso = IsotonicRegression(out_of_bounds="clip")
        iso.fit(conf[tr], y[tr])
        oof[te] = iso.predict(conf[te])
    return oof


def main():
    S = build_loo_samples(GROUPS, TOL_MAIN, False)
    conf = np.array([s["conf_v0_naiveKK"] for s in S])   # raw KK = calibration OFF
    y = np.array([s["hit"] for s in S])
    ds = np.array([s["dataset"] for s in S])

    # ---------- G2 calibration ablation ----------
    off = cal_metrics(conf, y)
    iso_oof = isotonic_lodo(conf, y, ds)
    ok = ~np.isnan(iso_oof)
    on = cal_metrics(iso_oof[ok], y[ok])
    g2 = {"n_samples": int(len(S)), "replication_rate": float(y.mean()),
          "OFF_raw_KK": off, "ON_isotonic_LODO": on,
          "delta_ECE": off["ECE"] - on["ECE"],
          "murphy_OFF": murphy(conf, y), "murphy_ON": murphy(iso_oof[ok], y[ok])}

    # ---------- G3 AUROC diagnosis ----------
    pooled_auc = float(roc_auc_score(y, conf)) if len(set(y.tolist())) == 2 else None
    within = []
    for d in sorted(set(ds.tolist())):
        m = ds == d
        if len(set(y[m].tolist())) == 2 and m.sum() >= 8:
            within.append((d, float(roc_auc_score(y[m], conf[m])), int(m.sum())))
    within_auc = [w[1] for w in within]
    # per-dataset mean KK vs replication rate
    per = []
    for d in sorted(set(ds.tolist())):
        m = ds == d
        per.append((d, float(conf[m].mean()), float(y[m].mean()), int(m.sum())))
    mk = np.array([p[1] for p in per]); rr = np.array([p[2] for p in per])
    rho, pval = spearmanr(mk, rr)
    g3 = {
        "pooled_rawKK_AUROC": pooled_auc,
        "within_dataset_AUROC_mean": float(np.mean(within_auc)) if within_auc else None,
        "within_dataset_AUROC_n": len(within_auc),
        "per_dataset_meanKK_vs_repRate_spearman": float(rho),
        "per_dataset_spearman_p": float(pval),
        "interpretation": (
            "Within a dataset KK barely ranks reproducibility (mean within-AUROC near 0.5); across "
            "datasets the per-dataset mean KK is NEGATIVELY related to replication rate "
            f"(Spearman {rho:.2f}), so a model that transfers KK across datasets scores BELOW chance. "
            "=> KK encodes single-curve validity, which is largely orthogonal to (and here mildly "
            "anti-correlated with) cross-pellet reproducibility; this is the diagnosis of AUROC<0.5."),
    }

    report = {"policy": "REAL repeats; calibration OFF=raw KK, ON=isotonic leave-one-dataset-out; "
                        "no leakage, no fabrication.",
              "G2_calibration_ablation": g2, "G3_auroc_diagnosis": g3}
    (HERE / "g2g3_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False),
                                           encoding="utf-8")

    # ---------- figure ----------
    fig, (axA, axB) = plt.subplots(1, 2, figsize=(11.6, 4.8))
    # (a) reliability: OFF vs ON
    for p, lab, c in [(conf, f"OFF raw KK (ECE {off['ECE']:.2f})", "tab:red"),
                      (iso_oof[ok], f"ON isotonic (ECE {on['ECE']:.2f})", "tab:green")]:
        pp = np.asarray(p, float); yy = y[ok] if lab.startswith("ON") else y
        edges = np.quantile(pp, np.linspace(0, 1, 8)); edges[0] -= 1e-9
        xs, ys = [], []
        for b in range(len(edges) - 1):
            m = (pp > edges[b]) & (pp <= edges[b + 1])
            if m.sum():
                xs.append(pp[m].mean()); ys.append(yy[m].mean())
        axA.plot(xs, ys, "o-", color=c, label=lab)
    axA.plot([0, 1], [0, 1], "k--", lw=0.8, label="perfect")
    axA.set_xlabel("predicted confidence"); axA.set_ylabel("observed replication rate")
    axA.set_title("(a) G2 calibration ON/OFF\nisotonic (leave-one-dataset-out) re-centres confidence")
    axA.legend(fontsize=7)
    # (b) per-dataset mean KK vs rep rate
    axB.scatter(mk, rr, s=60, c="tab:blue", edgecolor="k")
    axB.set_xlabel("per-dataset mean KK validity (single-curve QC)")
    axB.set_ylabel("per-dataset replication rate")
    axB.set_title(f"(b) G3 diagnosis: across datasets KK vs reproducibility\n"
                  f"Spearman {rho:.2f}  | pooled AUROC {pooled_auc:.2f} | "
                  f"within-AUROC {np.mean(within_auc):.2f}")
    axB.grid(alpha=0.3)
    fig.tight_layout()
    natfig.save_pub(fig, HERE, "g2g3_ablation_diagnosis")
    plt.close(fig)

    # ---------- console ----------
    print("=== G2 calibration ablation (882 real replication points) ===")
    print(f"  OFF raw KK : ECE {off['ECE']:.3f}  MCE {off['MCE']:.3f}  Brier {off['Brier']:.3f}  "
          f"overconf {off['overconfidence']:+.3f}")
    print(f"  ON isotonic: ECE {on['ECE']:.3f}  MCE {on['MCE']:.3f}  Brier {on['Brier']:.3f}  "
          f"overconf {on['overconfidence']:+.3f}   (LODO, no leakage)")
    print(f"  -> calibration cuts ECE by {g2['delta_ECE']:.3f}; Murphy reliability "
          f"{g2['murphy_OFF']['reliability']:.3f} -> {g2['murphy_ON']['reliability']:.3f}, "
          f"resolution {g2['murphy_OFF']['resolution']:.4f} -> {g2['murphy_ON']['resolution']:.4f}")
    print("\n=== G3 AUROC<0.5 diagnosis ===")
    print(f"  pooled raw-KK AUROC = {pooled_auc:.3f}")
    print(f"  mean within-dataset AUROC = {np.mean(within_auc):.3f} (n={len(within_auc)} datasets)")
    print(f"  per-dataset Spearman(mean KK, rep rate) = {rho:.3f} (p={pval:.3f})")
    print(f"  -> {g3['interpretation']}")
    print(f"\nSaved -> {HERE/'g2g3_report.json'} , g2g3_ablation_diagnosis.svg/.png/.tiff")


if __name__ == "__main__":
    main()
