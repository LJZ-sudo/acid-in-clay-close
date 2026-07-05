# -*- coding: utf-8 -*-
"""Extract anchor-temperature conductivities + Ea from the processed new datasets,
in the exact schema needed for (a) Line A experimental_feedback records and
(b) Line B history_db trial objectives.
"""
import json
from pathlib import Path

RESEARCH = (next(_p for _p in Path(__file__).resolve().parents if _p.name == "V1.0-qianduan-mainline").parent / "research")
OUT = RESEARCH          # anchors.json 输出仍在 research 根
DATA = RESEARCH / "data"  # 数据集目录
ANCHORS_K = [299.15, 273.15, 253.15, 233.15, 213.15, 193.15]
IDEAL_EA_LOW_LIMIT_EV = 0.089  # ea_low_excess = max(0, ea_low - this); matches campaign convention


def nearest(ms, targetK, tol=2.5):
    best = None
    for m in ms:
        tk = m.get("temperature_K")
        sig = m.get("conductivity_S_per_cm")
        if tk is None or sig is None:
            continue
        if best is None or abs(tk - targetK) < abs(best[0] - targetK):
            best = (tk, sig)
    if best and abs(best[0] - targetK) <= tol:
        return best[1]
    return None


def summarize(label):
    d = DATA / label
    agg = json.loads((d / "aggregated_results.json").read_text(encoding="utf-8"))
    arr = json.loads((d / "arrhenius_analysis.json").read_text(encoding="utf-8"))
    ms = [m for m in agg.get("measurements", []) if m.get("success")]
    segs = arr.get("segments", [])
    ea_high = segs[0]["Ea_eV"] if segs else None
    ea_low = segs[-1]["Ea_eV"] if len(segs) >= 2 else None
    trans = arr.get("transition_temps_K") or []
    t_break = trans[0] if trans else None
    out = {"label": label, "ea_high_eV": ea_high, "ea_low_eV": ea_low,
           "t_break_K": t_break, "n_seg": arr.get("n_segments")}
    for tK in ANCHORS_K:
        out[f"sigma_{int(round(tK))}k"] = nearest(ms, tK)
    # room-T sigma = warmest measured point
    warm = max(ms, key=lambda m: m.get("temperature_K") or 0)
    out["sigma_room"] = warm.get("conductivity_S_per_cm")
    out["room_T_C"] = warm.get("temperature_C")
    if ea_low is not None:
        out["ea_low_excess_eV"] = max(0.0, ea_low - IDEAL_EA_LOW_LIMIT_EV)
    return out


LABELS = ["lineA_LRS_6.12", "lineA_LRS_6.15_merged",
          "lineA_starch_6.11", "lineA_starch_6.13",
          "lineB_R0.42_6.11", "lineB_R0.28_6.10"]

res = {lab: summarize(lab) for lab in LABELS}
(OUT / "anchors.json").write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
for lab, r in res.items():
    print(f"{lab:24s} ea_high={r['ea_high_eV']:.4f} ea_low={r['ea_low_eV']} "
          f"sig_room={r['sigma_room']:.3e}@{r['room_T_C']}C "
          f"s273={r['sigma_273k']} s253={r['sigma_253k']} s233={r['sigma_233k']} "
          f"s213={r['sigma_213k']} s193={r['sigma_193k']}")
print("\nSaved anchors.json")
