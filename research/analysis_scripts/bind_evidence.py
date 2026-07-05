# -*- coding: utf-8 -*-
"""Append-only evidence binding:
  (A) add 4 June Line-A prospective validation records to experimental_feedback.json
  (B) add trial 10 (R0.42/N1.02) to history_db_attapulgite.json

Both operations are strictly append: existing entries are preserved verbatim.
Values are read from the canonical stage0 outputs (research/*).
"""
import json
import math
from pathlib import Path

REPO = next(_p for _p in Path(__file__).resolve().parents if _p.name == "research").parent
OUT = REPO / "research"
DATA = OUT / "data"
FEEDBACK = REPO / "V1.0-qianduan-mainline/stage3_mechanism/data/validation/experimental_feedback.json"
HISTORY = REPO / "V1.0-qianduan-mainline/stage1_optimization/campaign_memory/history_db_attapulgite.json"

anchors = json.loads((OUT / "anchors.json").read_text(encoding="utf-8"))


def arr_ea_high(label):
    a = json.loads((DATA / label / "arrhenius_analysis.json").read_text(encoding="utf-8"))
    return a["segments"][0]["Ea_eV"]


# ---------- (A) Line A feedback records ----------
def lineA_record(vid, sample_id, material, label, thickness, lotus, starch,
                 notes):
    r = anchors[label]
    return {
        "validation_id": vid,
        "candidate_id": "PC-a42de8d3b4-05",
        "instance_id": "I4",
        "sample_id": sample_id,
        "material_system": material,
        "validation_timing": "prospective",
        "measured_at": "2026-06-15T00:00:00+08:00",
        "lotus_starch_g": lotus,
        "starch_g": starch,
        "chitosan_g": 0.0,
        "pva_g": 0.333,
        "attapulgite_g": 0.10,
        "h3po4_85wt_g": 2.13,
        "water_g": 46.0,
        "acetic_acid_1wt_g": 0.0,
        "pva_dissolution_temp_C": 85.0,
        "gelatinization_schedule_C": "72C full gelatinization",
        "drying_temp_C": 45.0,
        "seal_pressure_MPa": 0.5,
        "thickness_cm": thickness,
        "electrode_area_cm2": 1.96,
        "sigma_299k_s_cm": r["sigma_299k"],
        "sigma_273k_s_cm": r["sigma_273k"],
        "sigma_253k_s_cm": r["sigma_253k"],
        "sigma_233k_s_cm": r["sigma_233k"],
        "sigma_213k_s_cm": r["sigma_213k"],
        "sigma_193k_s_cm": r["sigma_193k"],
        "ea_high_eV": arr_ea_high(label),
        "ea_low_eV": r["ea_low_eV"],
        "t_break_K": r["t_break_K"],
        "leakage_score": 0.0,
        "notes": notes,
    }


new_records = [
    lineA_record(
        "VAL-LRS-THICK-0612", "BIO-LRS-THICK-0612", "LRS/PVA/attapulgite/H3PO4",
        "lineA_LRS_6.12", 0.0737, 3.0, 0.0,
        "Source folder 2026.6.12藕粉. June thick-film LRS prospective replicate "
        "(frozen registry 2026-06-07, synthesized after). Thick film (0.074 cm, ~3x the "
        "0.022 cm thin film) still shows very low ea_high and high sigma -> cooling resilience "
        "is not a thin-film geometric artifact. Negative low-segment Ea is a cold-tail fitting "
        "artifact, not a mechanism; cold tail kept exploratory."),
    lineA_record(
        "VAL-LRS-THICK-0615", "BIO-LRS-THICK-0615", "LRS/PVA/attapulgite/H3PO4",
        "lineA_LRS_6.15_merged", 0.0701, 3.0, 0.0,
        "Source folder 2026.6.15藕粉 (single sample #1 measured across 6.13/6.14/6.15 sessions, "
        "merged into one RT->-88C curve, 59 points, 0 KK warnings). Thick-film LRS prospective "
        "replicate; ea_high=0.055 eV corroborates 6.12. Negative low-segment Ea is a cold-tail "
        "fitting artifact."),
    lineA_record(
        "VAL-STARCH-0611", "BIO-STARCH-0611", "corn-starch/PVA/attapulgite/H3PO4",
        "lineA_starch_6.11", 0.0628, 0.0, 3.0,
        "Source folder 2026.6.11淀粉. June starch-branch prospective control. Higher ea_high "
        "(0.167 eV) than LRS confirms the agent ranking LRS > starch is reproduced prospectively."),
    lineA_record(
        "VAL-STARCH-0613", "BIO-STARCH-0613", "corn-starch/PVA/attapulgite/H3PO4",
        "lineA_starch_6.13", 0.0737, 0.0, 3.0,
        "Source folder 2026.6.13淀粉. Starch-branch prospective replicate; ea_high=0.112 eV, "
        "above LRS band, reproduces LRS<starch ordering."),
]

fb = json.loads(FEEDBACK.read_text(encoding="utf-8"))
existing_ids = {r["validation_id"] for r in fb["validation_records"]}
added = []
for rec in new_records:
    if rec["validation_id"] in existing_ids:
        continue
    fb["validation_records"].append(rec)
    added.append(rec["validation_id"])
fb.setdefault("append_log", []).append({
    "appended_at": "2026-06-15",
    "added_records": added,
    "note": "June 2026 Line-A prospective batch (thick-film LRS x2 + starch control x2). "
            "Append-only; frozen registry untouched. Source: research stage0 outputs."
})
FEEDBACK.write_text(json.dumps(fb, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"[A] experimental_feedback.json: appended {added} (total {len(fb['validation_records'])} records)")


# ---------- (B) Line B history_db trial 10 ----------
rb = anchors["lineB_R0.42_6.11"]
sigma_room = rb["sigma_room"]
ea_high = arr_ea_high("lineB_R0.42_6.11")
ea_low = rb["ea_low_eV"]
ea_low_excess = max(0.0, ea_low - 0.089)
combined = math.log10(sigma_room) - 3.0 * ea_high - 0.5 * ea_low_excess

hist = json.loads(HISTORY.read_text(encoding="utf-8"))
have = {t["parameters"]["R"] for t in hist["trials"]}
if 0.42 not in have:
    hist["trials"].append({
        "trial_id": 10,
        "timestamp": "2026-06-11T00:00:00",
        "parameters": {"R": 0.42, "N": 1.02},
        "objectives": {
            "conductivity_room_temp_S_cm": sigma_room,
            "ea_high_temp_eV": ea_high,
            "ea_low_temp_eV": ea_low,
            "n_segments": 3.0,
            "ea_low_excess_eV": ea_low_excess,
            "combined_score": combined,
        },
        "metadata": {
            "sample_id": "BO-R0.42-N1.02-ljjo-2",
            "source": "stage0_measurement",
            "source_mode": "real",
            "source_tag": "attapulgite_aice",
            "campaign_slug": "attapulgite_aice_campaign",
            "ao_folder": "2026.6.11R0.42-N1.02",
            "roomT_C_actual": rb["room_T_C"],
            "thickness_cm": 0.0697,
            "formula_version": "v2.combined_score=log10(sigma_room)-3.0*Ea_high-0.5*ea_low_excess_eV",
            "prospective": True,
            "freeze_commit": "367e16a",
            "frozen_at": "2026-06-10T09:55:54+08:00",
            "round": 2,
            "note": "Line B round-2 prospective MOBO+LLM recipe (raw MOBO R=0.245/N=0.923 -> LLM gpt-5.4 final R=0.42/N=1.02). "
                    "Frozen+pushed 2026-06-10, synthesized 2026-06-11 (measured-after-freeze). "
                    "Does NOT beat campaign best (trial 1 R0.186/N1.029, score -1.94); honest prospective execution, not a discovery.",
        },
    })
    HISTORY.write_text(json.dumps(hist, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[B] history_db: appended trial 10 R0.42/N1.02 "
          f"sigma_room={sigma_room:.4e} ea_high={ea_high:.4f} "
          f"ea_low_excess={ea_low_excess:.4f} combined_score={combined:.4f}")
    # context: best so far
    best = max(hist["trials"], key=lambda t: t["objectives"]["combined_score"])
    print(f"    campaign best remains trial {best['trial_id']} "
          f"R{best['parameters']['R']}/N{best['parameters']['N']} "
          f"score={best['objectives']['combined_score']:.4f}")
else:
    print("[B] R0.42 already present, skipped.")
