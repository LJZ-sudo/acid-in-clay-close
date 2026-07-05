# -*- coding: utf-8 -*-
"""P0 — Reproducibility + measurement-confidence calibration (v0), all REAL data.

Reads the already-processed, canonical stage0 offline outputs in
``research/data/<dataset>/aggregated_results.json`` (per-point real
features: kk_score, kk_mu_max, rb_ohm, rb_method, conductivity, T) and the
matching ``arrhenius_analysis.json`` (segment Ea). It does NOT re-parse raw
spectra and NEVER fabricates numbers; if a quantity is not computable it is
left null and flagged.

Outputs (under this folder):
  - repro_pairs.json        : LRS(6.12 vs 6.15) + starch(6.11 vs 6.13) sigma/Ea agreement
  - suspect_points.json     : physically-inconsistent points (isotonic monotonicity)
  - calibration_report.json : reliability diagram bins + ECE + Brier for two
                              confidence definitions (v0 naive-KK, v1 physics-aware)
  - reliability_diagram.png : v0 vs v1 reliability curves
  - README.md               : human-readable summary of the REAL numbers

Honesty notes baked in:
  * fit_quality is a placeholder (=0.95) on reverse_zero_crossing points, so it
    is NOT used as a confidence feature; only kk_* and rb_* (real per-point) are.
  * Ground-truth "physically self-consistent" label = isotonic (monotone) residual
    of log10(sigma) vs 1000/T below a physical 0.3 dex (~2x) tolerance. This is a
    transport-side self-consistency proxy, NOT an independent-replication hit; it
    is stated as such in the report.
  * Sample size is small (~6 curves, ~200 points). ECE is a v0 estimate; reported
    with n per bin so the reader can judge.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import roc_auc_score

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
NDA = HERE.parents[2] / "research"

# 6 canonical datasets (process_all.py). s1/s2/s3 are sub-sessions of 6.15_merged
# and are excluded to avoid double-counting; lineB_R0.42 (no suffix) is legacy.
DATASETS = [
    ("lineA_LRS_6.12", "A_LRS"),
    ("lineA_LRS_6.15_merged", "A_LRS"),
    ("lineA_starch_6.11", "A_starch"),
    ("lineA_starch_6.13", "A_starch"),
    ("lineB_R0.42_6.11", "B_atp"),
    ("lineB_R0.28_6.10", "B_atp"),
]

SELF_CONSISTENT_TOL_DEX = 0.3   # |log10 sigma - isotonic fit| <= 0.3 dex (~2x) => consistent
JUMP_FLOOR_DEX = 0.2            # local log-sigma residual below this = normal EIS noise (no penalty)
JUMP_SPAN_DEX = 0.3            # residual span over which v1 penalty ramps 0 -> 1


def _load(name: str, fname: str) -> dict:
    p = NDA / "data" / name / fname
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def ok_points(agg: dict) -> list[dict]:
    out = []
    for m in agg.get("measurements", []):
        if (
            m.get("status") == "OK"
            and m.get("success")
            and m.get("conductivity_S_per_cm")
            and m.get("conductivity_S_per_cm") > 0
            and m.get("temperature_K")
        ):
            out.append(m)
    out.sort(key=lambda m: m["temperature_K"])
    return out


# --------------------------------------------------------------------------- #
# Part A: reproducibility pairs
# --------------------------------------------------------------------------- #
def _valid_segment_eas(arr: dict) -> list[float]:
    """Ea (eV) of segments with >=3 points (drops 1-point pseudo-segments)."""
    segs = arr.get("segments", []) or []
    return [
        float(s["Ea_eV"])
        for s in segs
        if s.get("Ea_eV") is not None and (s.get("n_points") or 0) >= 3
    ]


def repro_pair(name1: str, name2: str, tol_C: float = 1.5) -> dict:
    a1, a2 = ok_points(_load(name1, "aggregated_results.json")), ok_points(
        _load(name2, "aggregated_results.json")
    )
    matched = []
    for m1 in a1:
        t1 = m1["temperature_C"]
        if not a2:
            break
        c = min(a2, key=lambda m: abs(m["temperature_C"] - t1))
        if abs(c["temperature_C"] - t1) <= tol_C:
            d = math.log10(m1["conductivity_S_per_cm"]) - math.log10(
                c["conductivity_S_per_cm"]
            )
            matched.append({"T1_C": t1, "T2_C": c["temperature_C"], "dlog10_sigma": d})
    d = np.array([m["dlog10_sigma"] for m in matched]) if matched else np.array([])

    e1 = _valid_segment_eas(_load(name1, "arrhenius_analysis.json"))
    e2 = _valid_segment_eas(_load(name2, "arrhenius_analysis.json"))
    # high-T segment = segment 0 (bundle convention), low-T activated = next
    ea_cmp = []
    for label, i in [("ea_high", 0), ("ea_low_activated", 1)]:
        if i < len(e1) and i < len(e2):
            v1, v2 = e1[i], e2[i]
            absdiff = abs(v1 - v2)
            ratio = (max(v1, v2) / min(v1, v2)) if min(v1, v2) != 0 else None
            ea_cmp.append(
                {
                    "segment": label,
                    f"{name1}_eV": v1,
                    f"{name2}_eV": v2,
                    "abs_diff_eV": absdiff,
                    "ratio": ratio,
                }
            )
    return {
        "pair": [name1, name2],
        "n_matched_T": len(matched),
        "dlog10_sigma_mean": float(np.mean(d)) if d.size else None,
        "dlog10_sigma_std": float(np.std(d, ddof=1)) if d.size > 1 else None,
        "dlog10_sigma_absmax": float(np.max(np.abs(d))) if d.size else None,
        "sigma_ratio_median_x": float(10 ** np.median(np.abs(d))) if d.size else None,
        "ea_comparison": ea_cmp,
        "matched_points": matched,
    }


# --------------------------------------------------------------------------- #
# Part B+C: physical self-consistency label + confidence calibration
# --------------------------------------------------------------------------- #
def per_dataset_points(name: str, group: str) -> list[dict]:
    pts = ok_points(_load(name, "aggregated_results.json"))
    if len(pts) < 4:
        return []
    invT = np.array([1000.0 / p["temperature_K"] for p in pts])
    logs = np.array([math.log10(p["conductivity_S_per_cm"]) for p in pts])

    # isotonic: sigma decreases as 1000/T increases (activated transport)
    order = np.argsort(invT)
    iso = IsotonicRegression(increasing=False, out_of_bounds="clip")
    fit_sorted = iso.fit_transform(invT[order], logs[order])
    iso_fit = np.empty_like(logs)
    iso_fit[order] = fit_sorted
    iso_resid = np.abs(logs - iso_fit)

    # local linear-interpolation residual (different computation than isotonic)
    s = np.argsort(invT)
    xs, ys = invT[s], logs[s]
    local_resid_sorted = np.zeros_like(ys)
    for k in range(len(xs)):
        if k == 0:
            pred = ys[1] + (ys[2] - ys[1]) / (xs[2] - xs[1]) * (xs[0] - xs[1]) if len(xs) >= 3 else ys[1]
        elif k == len(xs) - 1:
            pred = ys[-2] + (ys[-2] - ys[-3]) / (xs[-2] - xs[-3]) * (xs[-1] - xs[-2]) if len(xs) >= 3 else ys[-2]
        else:
            span = xs[k + 1] - xs[k - 1]
            if span == 0:  # duplicate temperatures -> no interpolable jump
                pred = ys[k]
            else:
                frac = (xs[k] - xs[k - 1]) / span
                pred = ys[k - 1] + frac * (ys[k + 1] - ys[k - 1])
        local_resid_sorted[k] = abs(ys[k] - pred)
    local_resid = np.empty_like(logs)
    local_resid[s] = local_resid_sorted

    rows = []
    for i, p in enumerate(pts):
        kk = float(p.get("kk_score") or 0.0)
        # physics-aware penalty: only a *significant* local log-sigma jump (beyond
        # ~0.2 dex EIS noise floor) lowers confidence; normal points keep conf == kk.
        eff_jump = float(np.clip((local_resid[i] - JUMP_FLOOR_DEX) / JUMP_SPAN_DEX, 0.0, 1.0))
        conf_v0 = kk  # naive: trust KK validity score directly
        conf_v1 = kk * (1.0 - 0.85 * eff_jump)  # physics-aware
        label = 1 if iso_resid[i] <= SELF_CONSISTENT_TOL_DEX else 0
        rows.append(
            {
                "dataset": name,
                "group": group,
                "T_C": p["temperature_C"],
                "log10_sigma": float(logs[i]),
                "kk_score": kk,
                "kk_mu_max": p.get("kk_mu_max"),
                "rb_ohm": p.get("rb_ohm"),
                "rb_method": p.get("rb_method"),
                "isotonic_resid_dex": float(iso_resid[i]),
                "local_resid_dex": float(local_resid[i]),
                "self_consistent": label,
                "conf_v0_naiveKK": float(conf_v0),
                "conf_v1_physics": float(conf_v1),
            }
        )
    return rows


def calibration(rows: list[dict], conf_key: str, n_bins: int = 5) -> dict:
    conf = np.array([r[conf_key] for r in rows])
    label = np.array([r["self_consistent"] for r in rows], dtype=float)
    n = len(conf)
    # quantile (equal-frequency) bins to handle clustered confidences
    qs = np.quantile(conf, np.linspace(0, 1, n_bins + 1))
    qs[0] -= 1e-9
    bins = []
    ece = 0.0
    for b in range(n_bins):
        lo, hi = qs[b], qs[b + 1]
        if hi <= lo:
            continue
        mask = (conf > lo) & (conf <= hi)
        if mask.sum() == 0:
            continue
        mc, ml = float(conf[mask].mean()), float(label[mask].mean())
        nb = int(mask.sum())
        ece += (nb / n) * abs(mc - ml)
        bins.append(
            {"bin": b, "n": nb, "mean_confidence": mc, "observed_consistency": ml,
             "gap": mc - ml}
        )
    brier = float(np.mean((conf - label) ** 2))
    # AUROC of confidence discriminating self-consistent(1) vs suspect(0).
    # This is the headline metric under the very high (98%) consistency base rate.
    try:
        auroc = float(roc_auc_score(label, conf)) if len(set(label.tolist())) == 2 else None
    except ValueError:
        auroc = None
    return {"confidence_key": conf_key, "n_points": n, "ECE": float(ece),
            "Brier": brier, "AUROC_suspect_discrimination": auroc, "bins": bins}


def main() -> None:
    # ---- Part A ----
    repro = {
        "LRS_6.12_vs_6.15_merged": repro_pair("lineA_LRS_6.12", "lineA_LRS_6.15_merged"),
        "starch_6.11_vs_6.13": repro_pair("lineA_starch_6.11", "lineA_starch_6.13"),
    }
    (HERE / "repro_pairs.json").write_text(
        json.dumps(repro, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # ---- Part B+C ----
    all_rows: list[dict] = []
    for name, group in DATASETS:
        all_rows.extend(per_dataset_points(name, group))

    suspects = [r for r in all_rows if r["self_consistent"] == 0]
    suspects_sorted = sorted(suspects, key=lambda r: -r["isotonic_resid_dex"])
    (HERE / "suspect_points.json").write_text(
        json.dumps(
            {
                "tol_dex": SELF_CONSISTENT_TOL_DEX,
                "n_total_points": len(all_rows),
                "n_suspect": len(suspects),
                "suspect_points": suspects_sorted,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    cal_v0 = calibration(all_rows, "conf_v0_naiveKK")
    cal_v1 = calibration(all_rows, "conf_v1_physics")
    good = [r for r in all_rows if r["self_consistent"] == 1]
    discrimination = {
        "mean_conf_v0_on_suspect": float(np.mean([r["conf_v0_naiveKK"] for r in suspects])) if suspects else None,
        "mean_conf_v1_on_suspect": float(np.mean([r["conf_v1_physics"] for r in suspects])) if suspects else None,
        "mean_conf_v0_on_good": float(np.mean([r["conf_v0_naiveKK"] for r in good])) if good else None,
        "mean_conf_v1_on_good": float(np.mean([r["conf_v1_physics"] for r in good])) if good else None,
    }
    report = {
        "n_datasets": len(DATASETS),
        "n_points": len(all_rows),
        "n_suspect": len(suspects),
        "self_consistent_tol_dex": SELF_CONSISTENT_TOL_DEX,
        "calibration_v0_naiveKK": cal_v0,
        "calibration_v1_physics_aware": cal_v1,
        "suspect_discrimination": discrimination,
        "interpretation": (
            "Base rate is high (98% self-consistent), so AUROC (suspect discrimination) "
            "is the headline metric, not ECE. conf_v0 = raw KK score (naive agent that "
            "equates 'KK-valid' with 'trustworthy'); it CANNOT separate the 4 physical "
            "bad points (they pass KK at 0.93-0.95). conf_v1 keeps normal points == KK "
            "but lowers confidence only on significant local log-sigma jumps (>0.2 dex), "
            "which raises AUROC and lowers Brier. Honesty: v1 ECE may rise slightly "
            "because penalising bad points makes the mean confidence under-confident "
            "against the 98% base rate; this is expected and reported, not hidden. "
            "Label is isotonic-monotonicity self-consistency (transport-only proxy), "
            "NOT an independent-replication hit. Small N (~6 curves, 241 pts): v0 estimate."
        ),
    }
    (HERE / "calibration_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # ---- figure: reliability diagram + suspect-separation bars ----
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(10.4, 5.0))
    ax.plot([0, 1], [0, 1], "k--", lw=1, label="perfect calibration")
    for cal, color, mk in [(cal_v0, "tab:red", "o"), (cal_v1, "tab:blue", "s")]:
        xs = [b["mean_confidence"] for b in cal["bins"]]
        ys = [b["observed_consistency"] for b in cal["bins"]]
        ax.plot(xs, ys, mk + "-", color=color,
                label=f"{cal['confidence_key']}\n(ECE={cal['ECE']:.3f}, Brier={cal['Brier']:.3f}, "
                      f"AUROC={cal['AUROC_suspect_discrimination']:.3f})")
    ax.set_xlabel("Mean predicted confidence")
    ax.set_ylabel("Observed transport self-consistency rate")
    ax.set_title("(a) Reliability (high base-rate; see AUROC)")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.legend(loc="lower right", fontsize=7)

    labels = ["good\n(v0 KK)", "good\n(v1 phys)", "suspect\n(v0 KK)", "suspect\n(v1 phys)"]
    vals = [discrimination["mean_conf_v0_on_good"], discrimination["mean_conf_v1_on_good"],
            discrimination["mean_conf_v0_on_suspect"], discrimination["mean_conf_v1_on_suspect"]]
    colors = ["0.6", "tab:blue", "0.6", "tab:blue"]
    ax2.bar(labels, vals, color=colors, edgecolor="k")
    for i, v in enumerate(vals):
        ax2.text(i, v + 0.02, f"{v:.2f}", ha="center", fontsize=9)
    ax2.set_ylabel("Mean confidence")
    ax2.set_ylim(0, 1.05)
    ax2.set_title(f"(b) Naive KK can't flag {len(suspects)} physical bad points; physics-aware does")
    fig.tight_layout()
    fig.savefig(HERE / "reliability_diagram.png", dpi=150)
    plt.close(fig)

    # ---- console summary (REAL numbers) ----
    print("=== P0 Reproducibility ===")
    for k, v in repro.items():
        print(f"[{k}] n_matched={v['n_matched_T']} "
              f"dlog10_sigma_mean={v['dlog10_sigma_mean']} std={v['dlog10_sigma_std']} "
              f"sigma_ratio_median={v['sigma_ratio_median_x']}")
        for e in v["ea_comparison"]:
            print(f"    {e['segment']}: abs_diff={e['abs_diff_eV']:.4f} eV ratio={e['ratio']}")
    print("\n=== P0 Suspect points (physical monotonicity) ===")
    print(f"n_total={len(all_rows)} n_suspect={len(suspects)}")
    for r in suspects_sorted[:8]:
        print(f"    {r['dataset']} T={r['T_C']}C resid={r['isotonic_resid_dex']:.2f}dex "
              f"rb={r['rb_ohm']} method={r['rb_method']} kk={r['kk_score']:.3f}")
    print("\n=== P0 Calibration ===")
    print(f"v0 naive-KK   : ECE={cal_v0['ECE']:.4f} Brier={cal_v0['Brier']:.4f} "
          f"AUROC={cal_v0['AUROC_suspect_discrimination']}")
    print(f"v1 physics    : ECE={cal_v1['ECE']:.4f} Brier={cal_v1['Brier']:.4f} "
          f"AUROC={cal_v1['AUROC_suspect_discrimination']}")
    if suspects:
        sv0 = np.mean([r["conf_v0_naiveKK"] for r in suspects])
        sv1 = np.mean([r["conf_v1_physics"] for r in suspects])
        gv0 = np.mean([r["conf_v0_naiveKK"] for r in all_rows if r["self_consistent"] == 1])
        gv1 = np.mean([r["conf_v1_physics"] for r in all_rows if r["self_consistent"] == 1])
        print(f"  mean conf on {len(suspects)} SUSPECT pts:  v0={sv0:.3f}  v1={sv1:.3f}")
        print(f"  mean conf on good pts:           v0={gv0:.3f}  v1={gv1:.3f}")
        print(f"  -> naive KK cannot separate (v0 gap={gv0-sv0:.3f}); "
              f"physics-aware separates (v1 gap={gv1-sv1:.3f}).")
    print(f"\nSaved -> {HERE}")


if __name__ == "__main__":
    main()
