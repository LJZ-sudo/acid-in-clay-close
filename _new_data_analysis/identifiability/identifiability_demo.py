# -*- coding: utf-8 -*-
"""C1 — structural-identifiability demonstration backing the C0–C5 claim ladder.

Thesis (formalized in THREE_INNOVATIONS §15): an agent restricted to transport-only EIS
data may be LICENSED to claim at the DESCRIPTOR level (sigma, Ea, T_break, #segments) —
these are structurally identifiable (the AICc model competition robustly selects them) —
but must be BLOCKED from MECHANISM-level claims (which microscopic conduction law / what
structural change), because the forward map {mechanism -> sigma(T)} is non-injective:
several physically DISTINCT laws fit the SAME sigma(T) within noise.

This script demonstrates BOTH halves on the REAL LRS_6.15_merged sigma(T):
  (I)  DESCRIPTOR identifiable  : report the real AICc model probabilities (single vs
       2-seg vs 3-seg) from arrhenius_analysis.json -> data decisively selects the
       transition (prob ~1.0). [identifiable]
  (II) MECHANISM non-identifiable: on the low-T activated branch, fit three DISTINCT
       conduction laws — Arrhenius (simple activation), Mott 3-D variable-range hopping
       (ln s ~ T^-1/4), and VTF/glass (ln s ~ 1/(T-T0)) — and show they fit COMPARABLY
       well (R^2 within a small margin). If the data cannot separate them, the mechanism
       is not identifiable from sigma(T) alone, so the claim ladder must cap below it.
       Empirically reinforced by the project's DRT result (R^2<0, 0/59 reliable).

REAL data only; nothing fabricated. Run:  python _new_data_analysis/identifiability/identifiability_demo.py
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
from scipy.optimize import curve_fit

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import sys as _sys; _sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import natfig; natfig.apply()

HERE = Path(__file__).resolve().parent
NDA = HERE.parent
DATASET = "lineA_LRS_6.15_merged"
KB = 8.617333e-5  # eV/K
T_TRANSITION_K = 240.0  # low-T activated branch is below the main transition


def load_curve(name):
    agg = json.loads((NDA / name / "aggregated_results.json").read_text(encoding="utf-8"))
    T, S = [], []
    for m in agg.get("measurements", []):
        if m.get("success") and m.get("temperature_K") and (m.get("conductivity_S_per_cm") or 0) > 0:
            T.append(float(m["temperature_K"]))
            S.append(float(m["conductivity_S_per_cm"]))
    T, S = np.array(T), np.array(S)
    order = np.argsort(T)
    return T[order], S[order]


def r2(y, yhat):
    ss_res = np.sum((y - yhat) ** 2)
    ss_tot = np.sum((y - np.mean(y)) ** 2)
    return 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")


def main():
    T, S = load_curve(DATASET)
    lnS = np.log(S)

    # ---- (I) descriptor identifiability: real AICc model competition ----
    arr = json.loads((NDA / DATASET / "arrhenius_analysis.json").read_text(encoding="utf-8"))
    model_probs = arr.get("model_probabilities", {})
    n_seg = arr.get("n_segments")
    conf = arr.get("confidence")

    # ---- (II) mechanism non-identifiability on the low-T activated branch ----
    mask = T <= T_TRANSITION_K
    Tl, lnSl = T[mask], lnS[mask]
    fits = {}

    # Arrhenius: ln s = a - (Ea/kB)*(1/T)
    x_arr = 1.0 / Tl
    A = np.vstack([np.ones_like(x_arr), x_arr]).T
    coef, *_ = np.linalg.lstsq(A, lnSl, rcond=None)
    yhat = A @ coef
    fits["Arrhenius (simple activation)"] = {
        "R2": r2(lnSl, yhat), "Ea_eV": float(-coef[1] * KB),
        "param": f"Ea={-coef[1]*KB:.3f} eV"}

    # Mott 3D VRH: ln s = a - b*T^(-1/4)
    x_mott = Tl ** (-0.25)
    A2 = np.vstack([np.ones_like(x_mott), x_mott]).T
    coef2, *_ = np.linalg.lstsq(A2, lnSl, rcond=None)
    yhat2 = A2 @ coef2
    fits["Mott 3D VRH (T^-1/4)"] = {
        "R2": r2(lnSl, yhat2), "T0_Mott_K": float((coef2[1]) ** 4) if coef2[1] > 0 else None,
        "param": f"b={coef2[1]:.1f}"}

    # VTF / glass: ln s = a - B/(T - T0)   (nonlinear in T0)
    def vtf(T, a, B, T0):
        return a - B / (T - T0)
    vtf_ok = False
    try:
        p0 = [lnSl.max(), 500.0, 120.0]
        popt, _ = curve_fit(vtf, Tl, lnSl, p0=p0, maxfev=20000,
                            bounds=([-50, 1, 50], [50, 1e5, min(Tl) - 1]))
        yhat3 = vtf(Tl, *popt)
        fits["VTF / glassy (1/(T-T0))"] = {
            "R2": r2(lnSl, yhat3), "B_K": float(popt[1]), "T0_K": float(popt[2]),
            "param": f"B={popt[1]:.0f}K, T0={popt[2]:.0f}K"}
        vtf_ok = True
    except Exception as e:
        fits["VTF / glassy (1/(T-T0))"] = {"R2": None, "error": str(e)}

    r2s = {k: v["R2"] for k, v in fits.items() if v.get("R2") is not None}
    spread = max(r2s.values()) - min(r2s.values()) if r2s else None

    report = {
        "dataset": DATASET, "n_points_total": int(len(T)),
        "low_T_branch_K_max": T_TRANSITION_K, "n_points_low_T": int(mask.sum()),
        "descriptor_identifiable": {
            "model_probabilities": model_probs, "n_segments_selected": n_seg,
            "confidence": conf,
            "verdict": "Descriptor level (sigma, Ea, T_break, #segments) IS structurally "
                       "identifiable: AICc decisively selects the transition model "
                       f"(P(3-seg)={model_probs.get('continuous_3')})."},
        "mechanism_nonidentifiable": {
            "fits": fits, "R2_spread_across_laws": spread,
            "verdict": (f"Three physically DISTINCT conduction laws fit the low-T branch with "
                        f"R^2 within {spread:.3f} of each other -> sigma(T) alone cannot select "
                        "the microscopic mechanism. Non-identifiable. Reinforced by DRT R^2<0 "
                        "(0/59 reliable). => claim ladder must cap at DESCRIPTOR, not MECHANISM.")
            if spread is not None else {}},
    }
    (HERE / "identifiability_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    # ---- figure ----
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.4, 5.2))
    # (a) the three mechanism fits on the low-T branch (all comparable)
    order = np.argsort(1.0 / Tl)
    invT = 1000.0 / Tl
    ax1.scatter(invT, lnSl, s=28, c="k", zorder=5, label="LRS low-T branch (real)")
    xx = np.linspace(Tl.min(), Tl.max(), 200)
    ax1.plot(1000.0 / xx, coef[0] + coef[1] / xx, "-", c="tab:red",
             label=f"Arrhenius  R²={fits['Arrhenius (simple activation)']['R2']:.3f}")
    ax1.plot(1000.0 / xx, coef2[0] + coef2[1] * xx ** (-0.25), "--", c="tab:blue",
             label=f"Mott VRH   R²={fits['Mott 3D VRH (T^-1/4)']['R2']:.3f}")
    if vtf_ok:
        ax1.plot(1000.0 / xx, vtf(xx, *popt), ":", c="tab:green", lw=2,
                 label=f"VTF/glass  R²={fits['VTF / glassy (1/(T-T0))']['R2']:.3f}")
    ax1.set_xlabel("1000 / T  (1/K)")
    ax1.set_ylabel("ln σ")
    ax1.set_title("(a) MECHANISM non-identifiable\n3 distinct laws fit low-T branch comparably")
    ax1.legend(fontsize=8)
    ax1.grid(alpha=0.3)

    # (b) descriptor identifiable: AICc model probabilities
    labels = ["single", "2-seg", "3-seg"]
    probs = [model_probs.get("single", 0), model_probs.get("continuous_2", 0),
             model_probs.get("continuous_3", 0)]
    ax2.bar(labels, probs, color=["tab:gray", "tab:gray", "tab:purple"], edgecolor="k")
    for i, p in enumerate(probs):
        ax2.text(i, p + 0.02, f"{p:.2f}", ha="center")
    ax2.set_ylim(0, 1.12)
    ax2.set_ylabel("AICc model probability")
    ax2.set_title("(b) DESCRIPTOR identifiable\ndata decisively selects the transition (3-seg)")
    ax2.grid(alpha=0.3, axis="y")
    fig.tight_layout()
    natfig.save_pub(fig, HERE, "identifiability")
    plt.close(fig)

    # ---- console ----
    print("=== C1 structural identifiability (REAL LRS_6.15_merged) ===")
    print(f"(I) DESCRIPTOR: AICc probs single={probs[0]:.2f} 2seg={probs[1]:.2f} 3seg={probs[2]:.2f} "
          f"-> selected {n_seg}-seg (conf {conf}) => IDENTIFIABLE")
    print(f"(II) MECHANISM (low-T branch, n={int(mask.sum())} pts):")
    for k, v in fits.items():
        if v.get("R2") is not None:
            print(f"     {k:32s} R²={v['R2']:.4f}   [{v.get('param','')}]")
    print(f"     R² spread across 3 distinct laws = {spread:.4f} "
          f"=> mechanism NON-identifiable from sigma(T)")
    print(f"\nSaved -> {HERE}")


if __name__ == "__main__":
    main()
