# -*- coding: utf-8 -*-
"""B2 — reproducibility-aware confidence (first pass, REAL data, leave-one-dataset-out).

Question (honest): single-curve QC confidence (KK-based) predicts cross-pellet
independent-replication HIT only at AUROC ~0.55 (see repro_full_report.json §C). Does
adding REPRODUCIBILITY-AWARE features available at measurement time —— |Rb| magnitude,
temperature, within-curve local residual, sigma level, KK mu_max, Rb-extraction method ——
let a simple model predict cross-pellet reproducibility better?

Method (no leakage):
  * Samples = the SAME leave-one-out consensus replication-hit points as P2 v3
    (a point HITS if it reproduces the median of the OTHER repeats at that T within tol dex).
  * Models, each scored by LEAVE-ONE-DATASET-OUT pooled out-of-fold AUROC:
       M0  conf_v1_physics            (existing KK-physics scalar; baseline)
       M1  logistic(kk_score)         (KK only)
       M2  logistic(kk, log10|Rb|, T) (+ reproducibility-aware Rb magnitude & temperature)
       M3  logistic(full)             (+ local_resid, log10 sigma, kk_mu_max, rb_method 1-hot)
  * Honest: leave-one-dataset-out = train on all-but-one repeat, predict the held-out one;
    pool predictions -> one AUROC. Reports BOTH all-repeats and June-standardized subsets.
    No fabrication; everything derived from canonical stage0 outputs.

Run from repo root:  python research/calibration/repro_aware_confidence.py
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import roc_auc_score

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import sys as _sys; _sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import natfig; natfig.apply()

HERE = Path(__file__).resolve().parent
NDA = HERE.parents[2] / "research"
sys.path.insert(0, str(HERE))
from repro_and_calibration import _load, ok_points, per_dataset_points  # noqa: E402
from repro_full_calibration import REGISTRY, names_in, sigma_curve, GROUPS, TOL_MAIN  # noqa: E402

RB_METHODS = ["reverse_zero_crossing", "reverse_valley", "lowf_real", "min_imag"]


def build_samples_with_features(groups, tol, jun_batch_only, min_repeats_at_T=3):
    """Leave-one-out consensus replication-hit samples carrying full feature vectors."""
    samples = []
    for group in groups:
        names = names_in(group, jun_batch_only)
        curves = {n: sigma_curve(n) for n in names}
        feats = {n: {round(r["T_C"]): r for r in per_dataset_points(n, group)} for n in names}
        temps = sorted({t for c in curves.values() for t in c})
        for t in temps:
            def val(n):
                cands = [(abs(tt - t), curves[n][tt]) for tt in curves[n] if abs(tt - t) <= 1]
                return min(cands, key=lambda x: x[0])[1] if cands else None
            vals = {n: val(n) for n in names}
            vals = {n: v for n, v in vals.items() if v is not None}
            if len(vals) < min_repeats_at_T:
                continue
            for n, v in vals.items():
                others = [vv for m, vv in vals.items() if m != n]
                consensus = float(np.median(others))
                d = abs(v - consensus)
                f = feats[n].get(t)
                if f is None:
                    near = [(abs(tt - t), feats[n][tt]) for tt in feats[n] if abs(tt - t) <= 1]
                    f = min(near, key=lambda x: x[0])[1] if near else None
                if f is None:
                    continue
                rb = f.get("rb_ohm")
                samples.append({
                    "group": group, "dataset": n, "T_C": float(t),
                    "hit": 1 if d <= tol else 0,
                    "conf_v1_physics": float(f["conf_v1_physics"]),
                    "kk_score": float(f.get("kk_score") or 0.0),
                    "kk_mu_max": f.get("kk_mu_max"),
                    "log10_abs_rb": math.log10(abs(rb)) if rb else None,
                    "local_resid_dex": float(f.get("local_resid_dex") or 0.0),
                    "log10_sigma": float(f.get("log10_sigma") or 0.0),
                    "rb_method": f.get("rb_method"),
                })
    return samples


def featurize(samples, keys, mu_max_imp, rb_imp, onehot=False):
    X = []
    for s in samples:
        row = []
        for k in keys:
            if k == "kk_mu_max":
                row.append(float(s["kk_mu_max"]) if s["kk_mu_max"] is not None else mu_max_imp)
            elif k == "log10_abs_rb":
                row.append(s["log10_abs_rb"] if s["log10_abs_rb"] is not None else rb_imp)
            else:
                row.append(float(s[k]))
        if onehot:
            for meth in RB_METHODS:
                row.append(1.0 if s["rb_method"] == meth else 0.0)
        X.append(row)
    return np.array(X, float)


def loo_dataset_auroc(samples, keys, onehot=False):
    """Pooled out-of-fold AUROC under leave-one-DATASET-out logistic regression."""
    y = np.array([s["hit"] for s in samples])
    datasets = sorted({s["dataset"] for s in samples})
    mu_vals = [s["kk_mu_max"] for s in samples if s["kk_mu_max"] is not None]
    rb_vals = [s["log10_abs_rb"] for s in samples if s["log10_abs_rb"] is not None]
    mu_imp = float(np.median(mu_vals)) if mu_vals else 0.0
    rb_imp = float(np.median(rb_vals)) if rb_vals else 0.0
    X = featurize(samples, keys, mu_imp, rb_imp, onehot)
    ds_arr = np.array([s["dataset"] for s in samples])
    oof = np.full(len(samples), np.nan)
    for d in datasets:
        te = ds_arr == d
        tr = ~te
        if len(set(y[tr].tolist())) < 2 or te.sum() == 0:
            continue
        sc = StandardScaler().fit(X[tr])
        clf = LogisticRegression(max_iter=2000, C=1.0)
        clf.fit(sc.transform(X[tr]), y[tr])
        oof[te] = clf.predict_proba(sc.transform(X[te]))[:, 1]
    ok = ~np.isnan(oof)
    if len(set(y[ok].tolist())) < 2:
        return None, oof, y, ok
    return float(roc_auc_score(y[ok], oof[ok])), oof, y, ok


def main():
    out = {}
    fig, axes = plt.subplots(1, 2, figsize=(12.4, 5.0))
    for col, (tag, jun) in enumerate([("all_repeats", False), ("june_std", True)]):
        S = build_samples_with_features(GROUPS, TOL_MAIN, jun)
        y = np.array([s["hit"] for s in S])
        base = float(roc_auc_score(y, [s["conf_v1_physics"] for s in S])) if len(set(y.tolist())) == 2 else None
        m1, _, _, _ = loo_dataset_auroc(S, ["kk_score"])
        m2, _, _, _ = loo_dataset_auroc(S, ["kk_score", "log10_abs_rb", "T_C"])
        m3, oof3, y3, ok3 = loo_dataset_auroc(
            S, ["kk_score", "log10_abs_rb", "T_C", "local_resid_dex", "log10_sigma", "kk_mu_max"],
            onehot=True)
        res = {
            "n_samples": len(S), "hit_rate": float(y.mean()),
            "M0_conf_v1_physics_AUROC": base,
            "M1_kk_only_AUROC_looDS": m1,
            "M2_plus_Rb_T_AUROC_looDS": m2,
            "M3_full_AUROC_looDS": m3,
        }
        out[tag] = res
        print(f"[{tag}] n={len(S)} hit_rate={y.mean():.3f}")
        print(f"   M0 conf_v1 (KK-physics, in-sample) AUROC = {base:.3f}")
        print(f"   M1 kk_only            (loo-dataset) AUROC = {m1}")
        print(f"   M2 +Rb magnitude + T  (loo-dataset) AUROC = {m2}")
        print(f"   M3 full repro-aware   (loo-dataset) AUROC = {m3}")

        ax = axes[col]
        labels = ["M0\nKK-phys", "M1\nKK", "M2\n+Rb,T", "M3\nfull"]
        vals = [base or 0, m1 or 0, m2 or 0, m3 or 0]
        colors = ["tab:gray", "tab:gray", "tab:orange", "tab:green"]
        ax.bar(labels, vals, color=colors, edgecolor="k")
        ax.axhline(0.5, color="red", ls="--", lw=1, label="random (0.5)")
        for i, v in enumerate(vals):
            ax.text(i, v + 0.008, f"{v:.3f}", ha="center", fontsize=9)
        ax.set_ylim(0.25, max(0.72, max(vals) + 0.08))
        ax.set_ylabel("AUROC (predict cross-pellet replication hit)")
        ax.set_title(f"({'a' if col == 0 else 'b'}) {tag}  (n={len(S)}, hit={y.mean():.2f})\n"
                     "leave-one-dataset-out; orange/green = reproducibility-aware")
        ax.legend(fontsize=8)
    fig.tight_layout()
    natfig.save_pub(fig, HERE, "repro_aware_auroc")
    plt.close(fig)

    (HERE / "repro_aware_report.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved -> {HERE/'repro_aware_report.json'} , {HERE/'repro_aware_auroc.png'}")

    # honest verdict
    a = out["all_repeats"]
    delta = (a["M3_full_AUROC_looDS"] or 0) - (a["M0_conf_v1_physics_AUROC"] or 0)
    print(f"\nVERDICT (all_repeats): KK-only baseline AUROC≈{a['M0_conf_v1_physics_AUROC']:.2f}; "
          f"full reproducibility-aware (loo-dataset) AUROC≈{a['M3_full_AUROC_looDS']:.2f} "
          f"(Δ={delta:+.2f}). " +
          ("Rb+T features add real predictive power." if delta >= 0.05 else
           "Rb+T features add only marginal predictive power -> reproducibility floor is "
           "largely fabrication-driven & not predictable from a single curve (consistent with §11.3)."))


if __name__ == "__main__":
    main()
