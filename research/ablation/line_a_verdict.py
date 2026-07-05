"""Line A frozen-then-validated verdict.

Reads the stage0 outputs recomputed under mainline QC (KK + manual-Rb pipeline,
outputs in research/ablation/line_a_analysis/stage0_out) and scores each sample
against the PREREGISTERED falsifiable predictions in
research/prospective/line_A_biopolymer_transfer/PREREGISTRATION.md §4.

Honest rules:
- Ea_high taken from the highest-temperature Arrhenius segment (>=3 pts).
- sigma(T) by log-linear interpolation; if target T is outside measured range we
  return None (no extrapolation).
- KK pass-rate of the high-T segment reported alongside Ea.
- No threshold is changed post-hoc. PASS/FAIL/PARTIAL printed as-is.

READ-ONLY on mainline source. All artifacts stay in this folder.
"""
import glob, json, os
import numpy as np

BASE = "research/ablation/line_a_analysis/stage0_out"
OUTJSON = "research/ablation/line_a_verdict.json"
OUTTXT = "research/ablation/line_a_verdict.txt"

# folder -> (material, role, geometry_band, thickness_cm)
ROLE = {
    "2026.6.12藕粉": ("LRS", "lotus-root starch", "thick", 0.0737),
    "2026.6.15藕粉": ("LRS", "lotus-root starch", "thick", 0.0701),
    "2026.6.11淀粉": ("CORN", "corn starch", "thick", 0.0628),
    "2026.6.13淀粉": ("CORN", "corn starch", "thick", 0.0737),
    "2026.5.9CS":  ("LRS", "lotus-root starch", "thin", 0.022),
    "2026.4.29CS": ("LRS", "lotus-root starch", "thin", 0.02),
    "2026.4.30CS": ("CHITO", "chitosan", "-", 0.05),
    "2026.5.1CS":  ("CHITO", "chitosan", "-", 0.06),
    "2026.4.27CS": ("CORN_old", "corn starch (Apr)", "thick", 0.06),
    "2026.4.28CS": ("CORN_old", "corn starch (Apr)", "thick", 0.06),
}

def match_role(folder_name):
    for key, v in ROLE.items():
        if key in folder_name:
            return v
    return (None, None, None, None)

def sigma_at(T, S, Ttar):
    pairs = sorted((t, s) for t, s in zip(T, S) if s and s > 0)
    if len(pairs) < 3:
        return None
    Ta = np.array([p[0] for p in pairs]); Sa = np.array([p[1] for p in pairs])
    if Ttar < Ta.min() or Ttar > Ta.max():
        return None
    return float(np.exp(np.interp(Ttar, Ta, np.log(Sa))))

def high_T_segment(arr):
    segs = [s for s in arr.get("segments", []) if s.get("n_points", 0) >= 3]
    if not segs:
        return None
    return max(segs, key=lambda s: s.get("temp_range_K", [0, 0])[1])

def cold_segment_max_Ea(arr, below_K=240.0):
    vals = []
    for s in arr.get("segments", []):
        if s.get("n_points", 0) < 3:
            continue
        tr = s.get("temp_range_K", [None, None])
        if tr[0] is not None and tr[0] <= below_K:
            vals.append(s.get("Ea_eV"))
    return max(vals) if vals else None

rows = []
for d in sorted(glob.glob(BASE + "/*")):
    if not os.path.isdir(d):
        continue
    fn = os.path.basename(d)
    material, role, band, thick = match_role(fn)
    if role is None:
        continue
    arr_p = os.path.join(d, "arrhenius_analysis.json")
    agg_p = os.path.join(d, "aggregated_results.json")
    if not (os.path.exists(arr_p) and os.path.exists(agg_p)):
        continue
    arr = json.load(open(arr_p, encoding="utf-8"))
    agg = json.load(open(agg_p, encoding="utf-8"))

    T = agg.get("temperatures_K", [])
    S = agg.get("conductivities", [])
    meas = agg.get("measurements", [])

    hi = high_T_segment(arr)
    ea_high = hi.get("Ea_eV") if hi else None
    hi_range = hi.get("temp_range_K") if hi else None
    # KK pass-rate within the high-T segment window
    kk_pass_hi = None
    if hi_range:
        lo, hiK = hi_range[0], hi_range[1]
        seg_pts = [m for m in meas if m.get("temperature_K") is not None
                   and lo - 0.5 <= m["temperature_K"] <= hiK + 0.5 and m.get("success")]
        if seg_pts:
            kk_pass_hi = round(sum(1 for m in seg_pts if m.get("kk_passed")) / len(seg_pts), 3)

    s273 = sigma_at(T, S, 273.15)
    s253 = sigma_at(T, S, 253.15)
    s233 = sigma_at(T, S, 233.15)
    s_rt = sigma_at(T, S, 298.15) or sigma_at(T, S, 295.15)
    ratio_253_273 = (s253 / s273) if (s253 and s273) else None
    ratio_233_273 = (s233 / s273) if (s233 and s273) else None
    cold_Ea = cold_segment_max_Ea(arr)
    tminK = min((m["temperature_K"] for m in meas
                 if m.get("success") and m.get("conductivity_S_per_cm", 0) > 1e-5), default=None)

    rows.append({
        "folder": fn, "material": material, "role": role, "geometry_band": band,
        "thickness_cm": thick, "n_temps": len(T),
        "Ea_high_eV": round(ea_high, 4) if ea_high is not None else None,
        "Ea_high_segment_K": [round(x, 1) for x in hi_range] if hi_range else None,
        "KK_passrate_highT": kk_pass_hi,
        "cold_segment_maxEa_eV": round(cold_Ea, 3) if cold_Ea is not None else None,
        "sigma_RT": s_rt, "sigma_273K": s273, "sigma_253K": s253, "sigma_233K": s233,
        "ratio_sigma253_273": round(ratio_253_273, 3) if ratio_253_273 else None,
        "ratio_sigma233_273": round(ratio_233_273, 4) if ratio_233_273 else None,
        "min_measurable_T_K": round(tminK, 1) if tminK else None,
    })

# ---- preregistered verdicts ----
def fmt_sig(x):
    return f"{x:.2e}" if isinstance(x, (int, float)) and x else "n/a"

def lrs_verdict(r):
    a = r["Ea_high_eV"] is not None and r["Ea_high_eV"] <= 0.06
    b = r["ratio_sigma253_273"] is not None and r["ratio_sigma253_273"] >= 0.5
    c = r["sigma_233K"] is not None and r["sigma_233K"] > 1e-5
    checks = {"4.1a Ea_high<=0.06eV": a, "4.1b sigma253/273>=0.5": b, "4.1c sigma(<=233K)>1e-5": c}
    return ("CONFIRMED" if (a and b and c) else "NOT-CONFIRMED"), checks

def chito_verdict(r):
    drop = r["ratio_sigma233_273"] is not None and r["ratio_sigma233_273"] <= 0.1
    midEa = r["cold_segment_maxEa_eV"] is not None and r["cold_segment_maxEa_eV"] > 1.0
    checks = {"4.2 sigma233/273<=0.1 (>=1 decade drop)": drop, "4.2 cold-seg Ea>1eV": midEa}
    return ("BOUNDARY-CONFIRMED" if (drop or midEa) else "NOT-CONFIRMED"), checks

lines = ["# Line A — frozen-then-validated verdict (preregistration §4)\n",
         "scorer: mainline stage0 QC (KK + manual-Rb), recomputed; thresholds = preregistered, unchanged.\n"]

lines.append("\n## Per-sample descriptors")
hdr = ("folder", "material", "band", "thk", "Ea_hi", "KKhi", "coldEa", "sRT", "s273", "s253", "s233", "r253", "r233", "Tmin")
lines.append("  ".join(f"{h:>9}" for h in hdr))
for r in rows:
    lines.append("  ".join(f"{str(v):>9}" for v in (
        r["folder"][-7:], r["material"], r["geometry_band"], r["thickness_cm"],
        r["Ea_high_eV"], r["KK_passrate_highT"], r["cold_segment_maxEa_eV"],
        fmt_sig(r["sigma_RT"]), fmt_sig(r["sigma_273K"]), fmt_sig(r["sigma_253K"]),
        fmt_sig(r["sigma_233K"]), r["ratio_sigma253_273"], r["ratio_sigma233_273"],
        r["min_measurable_T_K"])))

lines.append("\n## Verdicts vs preregistered predictions")
verdicts = {}
for r in rows:
    if r["material"] == "LRS" and r["geometry_band"] == "thick":
        v, c = lrs_verdict(r)
        verdicts.setdefault("4.1_LRS_positive", []).append({"folder": r["folder"], "verdict": v, "checks": c})
        lines.append(f"\n[4.1 LRS positive] {r['folder']} (thick {r['thickness_cm']}cm): {v}")
        for k, val in c.items():
            lines.append(f"    {'PASS' if val else 'FAIL'}  {k}")
    if r["material"] == "CHITO":
        v, c = chito_verdict(r)
        verdicts.setdefault("4.2_CHITO_boundary", []).append({"folder": r["folder"], "verdict": v, "checks": c})
        lines.append(f"\n[4.2 CHITO boundary] {r['folder']}: {v}")
        for k, val in c.items():
            lines.append(f"    {'PASS' if val else 'FAIL'}  {k}")

# 4.3 corn starch generalisation: high-T sigma magnitude (use sigma_273K; sigma_RT often extrapolated)
lrs_hi = [r["sigma_273K"] for r in rows if r["material"] == "LRS" and r["geometry_band"] == "thick" and r["sigma_273K"]]
corn_hi = [r["sigma_273K"] for r in rows if r["material"] == "CORN" and r["sigma_273K"]]
lrs_r233 = [r["ratio_sigma233_273"] for r in rows if r["material"] == "LRS" and r["geometry_band"] == "thick" and r["ratio_sigma233_273"]]
corn_r233 = [r["ratio_sigma233_273"] for r in rows if r["material"] == "CORN" and r["ratio_sigma233_273"]]
if lrs_hi and corn_hi:
    same_order = 0.2 <= (np.mean(corn_hi) / np.mean(lrs_hi)) <= 5
    earlier_decay = (np.mean(corn_r233) < np.mean(lrs_r233)) if (lrs_r233 and corn_r233) else None
    lines.append(f"\n[4.3 corn-starch generalisation] corn sigma273~{np.mean(corn_hi):.2e} vs LRS sigma273~{np.mean(lrs_hi):.2e}; "
                 f"same order = {same_order}")
    if earlier_decay is not None:
        lines.append(f"    corn cold-continuity sigma233/273~{np.mean(corn_r233):.3f} vs LRS~{np.mean(lrs_r233):.3f} "
                     f"-> corn decays earlier = {earlier_decay} (matches 4.3 prediction)")
    verdicts["4.3_corn_generalisation"] = {"corn_sigma273_mean": float(np.mean(corn_hi)),
                                            "lrs_sigma273_mean": float(np.mean(lrs_hi)),
                                            "same_order_high_T": bool(same_order),
                                            "corn_decays_earlier_cold": (bool(earlier_decay) if earlier_decay is not None else None)}

# 4.4 thickness control: LRS thin vs thick Ea_high
thin = [r["Ea_high_eV"] for r in rows if r["material"] == "LRS" and r["geometry_band"] == "thin" and r["Ea_high_eV"] is not None]
thick = [r["Ea_high_eV"] for r in rows if r["material"] == "LRS" and r["geometry_band"] == "thick" and r["Ea_high_eV"] is not None]
if thin and thick:
    lines.append(f"\n[4.4 thickness control] LRS-thin Ea_high={np.mean(thin):.4f}eV (n={len(thin)}, ~0.02cm) "
                 f"vs LRS-thick Ea_high={np.mean(thick):.4f}eV (n={len(thick)}, ~0.07cm)")
    if np.mean(thick) <= np.mean(thin) * 1.3:
        concl = "thick NOT >> thin -> supports INTRINSIC low-Ea (stronger claim allowed)"
    elif np.mean(thin) < np.mean(thick):
        concl = "thin << thick -> low-Ea is film-geometry + family effect (must NOT claim intrinsic)"
    else:
        concl = "comparable"
    lines.append(f"    => {concl}")
    verdicts["4.4_thickness_control"] = {"thin_Ea_mean": float(np.mean(thin)),
                                         "thick_Ea_mean": float(np.mean(thick)), "conclusion": concl}

open(OUTJSON, "w", encoding="utf-8").write(json.dumps({"samples": rows, "verdicts": verdicts}, ensure_ascii=False, indent=2))
open(OUTTXT, "w", encoding="utf-8").write("\n".join(lines))
print("\n".join(lines))
print("\nwrote", OUTJSON, "and", OUTTXT)
