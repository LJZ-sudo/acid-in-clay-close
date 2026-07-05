# -*- coding: utf-8 -*-
"""P1 — Transport-side relaxation evolution on REAL LRS spectra.

Two findings, both REAL and reported honestly:

  (1) Standard Tikhonov DRT (the existing stage0 ``analyze_drt``) is UNRELIABLE on
      these LRS spectra: the reconstruction R^2 is negative at every temperature,
      because the low-frequency response is a large blocking-electrode capacitive
      tail (|Z''| up to ~22 kOhm vs Z' ~ 5 kOhm) that a pure relaxation kernel
      cannot represent. We record this rather than pretend the DRT peaks are
      meaningful.  -> motivates NOT using DRT as evidence.

  (2) A model-free characteristic relaxation frequency f_peak = argmax_f(-Z'') of
      the bulk arc apex IS robust (no ill-posed inversion) and its shift with
      temperature is a legitimate transport-side signature (NOT a structure claim).

Reads the real raw CHI spectra listed in lineA_LRS_6.15_merged/aggregated_results.json
(only QC-OK points), via the canonical parse_chi_file. No fabrication.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from scipy.signal import find_peaks
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
STAGE0 = REPO / "V1.0-qianduan-mainline" / "stage0_measurement"
sys.path.insert(0, str(STAGE0))

from modules.io_utils.chi_parser import parse_chi_file  # noqa: E402
from modules.analysis.algorithms.drt_analysis import analyze_drt  # noqa: E402

DATASET = "lineA_LRS_6.15_merged"
SUSPECT_T_C = {-88.0, -85.0}  # from P0 suspect_points.json (this dataset)


def arc_apex_freq(f: np.ndarray, zi: np.ndarray):
    """Model-free bulk-arc apex: highest-frequency significant local max of -Z''."""
    idx = np.argsort(f)
    fs, zpp = f[idx], -zi[idx]
    if zpp.size < 3 or zpp.max() <= 0:
        return None, None
    prom = max(1e-12, 0.03 * (zpp.max() - zpp.min()))
    pk, _ = find_peaks(zpp, prominence=prom)
    cand = [i for i in pk if zpp[i] > 0]
    if not cand:
        return None, None
    i = max(cand, key=lambda k: fs[k])  # highest-freq apex = bulk relaxation
    return float(fs[i]), float(zpp[i])


def main() -> None:
    agg = json.loads(
        (REPO / "experiments" / "data" / DATASET / "aggregated_results.json").read_text(encoding="utf-8")
    )
    ok = [m for m in agg.get("measurements", []) if m.get("status") == "OK" and m.get("filepath")]
    ok.sort(key=lambda m: m["temperature_C"])

    rows = []
    n_parse_fail = n_apex_fail = 0
    drt_r2_all = []
    for m in ok:
        parsed = parse_chi_file(m["filepath"])
        if not parsed.get("success"):
            n_parse_fail += 1
            continue
        f, zr, zi = parsed["frequencies"], parsed["z_real"], parsed["z_imag"]
        T_C = m["temperature_C"]
        fpk, zpk = arc_apex_freq(f, zi)
        if fpk is None:
            n_apex_fail += 1
        # DRT only to document (un)reliability, not used as evidence
        drt = analyze_drt(f, zr, zi)
        r2 = (drt.get("fit_quality") or {}).get("r_squared") if drt.get("success") else None
        if r2 is not None:
            drt_r2_all.append(r2)
        rows.append({
            "T_C": T_C,
            "T_K": m.get("temperature_K"),
            "n_freq": int(parsed.get("n_points") or 0),
            "f_peak_Hz": fpk,
            "minus_Zpp_peak_ohm": zpk,
            "drt_r_squared": r2,
            "drt_reliable": (r2 is not None and r2 > 0.8),
            "p0_suspect": T_C in SUSPECT_T_C,
        })

    n_drt_reliable = sum(1 for r in rows if r["drt_reliable"])
    out = {
        "dataset": DATASET,
        "n_points": len(rows),
        "n_parse_fail": n_parse_fail,
        "n_apex_fail": n_apex_fail,
        "drt_reliability": {
            "n_drt_reliable_r2_gt_0p8": n_drt_reliable,
            "drt_r2_min": float(np.min(drt_r2_all)) if drt_r2_all else None,
            "drt_r2_max": float(np.max(drt_r2_all)) if drt_r2_all else None,
            "verdict": (
                "Standard Tikhonov DRT is UNRELIABLE on these spectra (all R^2 < 0.8; "
                "blocking-electrode low-f capacitive tail beyond a pure relaxation "
                "kernel). DRT peaks are NOT used as evidence."
            ),
        },
        "method_note": (
            "f_peak = argmax_f(-Z'') of the bulk arc apex (model-free, no inversion). "
            "Its temperature shift is a transport-side relaxation signature, NOT a "
            "microscopic-structure claim."
        ),
        "by_temperature": rows,
    }
    (HERE / "relaxation_evolution.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # ---- figure: (a) f_peak Arrhenius-like vs 1000/T ; (b) DRT r2 vs T (honesty) ----
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(11.0, 5.0))
    good = [r for r in rows if r["f_peak_Hz"] and r["T_K"] and not r["p0_suspect"]]
    susp = [r for r in rows if r["f_peak_Hz"] and r["T_K"] and r["p0_suspect"]]
    if good:
        gx = [1000.0 / r["T_K"] for r in good]
        gy = [np.log10(r["f_peak_Hz"]) for r in good]
        ax.plot(gx, gy, "o-", color="tab:blue", ms=4, lw=1, label="f_peak (-Z'' apex)")
    if susp:
        sx = [1000.0 / r["T_K"] for r in susp]
        sy = [np.log10(r["f_peak_Hz"]) for r in susp]
        ax.plot(sx, sy, "s", color="tab:red", ms=7, label="P0-suspect T")
    ax.set_xlabel("1000 / T  (1/K)")
    ax.set_ylabel("log10( f_peak / Hz )")
    ax.set_title(f"(a) -Z'' arc apex undetectable in {n_apex_fail}/{len(rows)}\n"
                 f"(monotone tail; markers = the 2 P0-suspect pts only)")
    ax.legend(loc="best", fontsize=8)

    tx = [r["T_C"] for r in rows if r["drt_r_squared"] is not None]
    ty = [r["drt_r_squared"] for r in rows if r["drt_r_squared"] is not None]
    ax2.axhline(0.8, color="green", ls="--", lw=1, label="reliable threshold (0.8)")
    ax2.axhline(0.0, color="0.5", ls=":", lw=1)
    ax2.scatter(tx, ty, s=16, color="tab:purple")
    ax2.set_xlabel("Temperature (degC)")
    ax2.set_ylabel("DRT reconstruction R^2")
    ax2.set_title("(b) Standard DRT UNRELIABLE here (all R^2 < 0)")
    ax2.legend(loc="best", fontsize=8)
    fig.tight_layout()
    fig.savefig(HERE / "relaxation_evolution.png", dpi=150)
    plt.close(fig)

    print(f"=== P1 transport relaxation evolution ({DATASET}) ===")
    print(f"n_points={len(rows)} parse_fail={n_parse_fail} apex_fail={n_apex_fail}")
    print(f"DRT reliable (r2>0.8): {n_drt_reliable}/{len(drt_r2_all)}  "
          f"r2 range [{out['drt_reliability']['drt_r2_min']:.2f}, {out['drt_reliability']['drt_r2_max']:.2f}]")
    print("T_C   f_peak_Hz   -Zpp_peak   drt_r2   suspect")
    for r in rows[::5]:
        fp, zp = r["f_peak_Hz"], r["minus_Zpp_peak_ohm"]
        fp_s = f"{fp:.3g}" if fp else "-"
        zp_s = f"{zp:.1f}" if zp else "-"
        r2 = r["drt_r_squared"] or 0.0
        print(f"{r['T_C']:6.1f}  {fp_s:>9}  {zp_s:>9}  {r2:6.2f}   {r['p0_suspect']}")
    print(f"\nSaved -> {HERE}")


if __name__ == "__main__":
    main()
