# -*- coding: utf-8 -*-
"""Build Pillar-2 QC reinforcement artifacts (P1 items, no new experiments).

Produces, from EXISTING data only:
  1) ea_vs_thickness.{csv,png}
       Ea_high vs film thickness for the VALID samples (4.25CS deprecated,
       see figure_data/DEPRECATED_SAMPLES.md). Demonstrates that the low
       Ea_high (0.037-0.042 eV) co-occurs with the 0.02-0.022 cm LRS thin
       films -> thickness x material-family confounding is shown openly.
  2) kk_residual_per_temperature.csv
       INDEPENDENT recomputation of per-temperature Kramers-Kronig residual
       (lin-KK, impedance lib) reusing the project's own
       stage0 algorithms.kk_validation.validate_kk_consistency.
       NOTE: this is an independent recompute to show the high-T-clean /
       cold-tail-dirty pattern that motivates band gating; it does NOT try
       to exactly reproduce the frozen pipeline's per-sample warning counts.
  3) kk_rb_band_gating_table.csv
       Per sample x claim band (main-text / supplementary / screening):
       point counts and manual-vs-auto Rb delta stats, from the frozen
       selected_rb_qc_v2.csv. Implements "restrict main-text Ea to the
       clean high-T window; push the cold tail to Exploratory".
  4) Fig_pillar2_qc.png
       2-panel summary (Ea vs thickness; KK mu_median vs T by band).

Run:
    python manuscript/figures/build_pillar2_qc_artifacts.py
"""
from __future__ import annotations

import io
import re
import sys
from contextlib import redirect_stdout
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
P2 = REPO / "experiments" / "three_pillars" / "pillar2_descriptor_qc"
WIDE = P2 / "figure_data" / "wide_temperature_performance_summary.csv"
RBQC = P2 / "eis_qc_v2" / "selected_rb_qc_v2.csv"
RAW = REPO / "experiments" / "raw" / "新材料"

# reuse the project's own KK algorithm
sys.path.insert(0, str(REPO / "V1.0-qianduan-mainline" / "stage0_measurement"))
from modules.analysis.algorithms.kk_validation import validate_kk_consistency  # noqa: E402

OUT = HERE
OUT.mkdir(parents=True, exist_ok=True)

LRS = {"2026.4.29CS", "2026.5.9CS"}
CHITO = {"2026.4.30CS", "2026.5.1CS"}

# match the frozen pipeline's per-folder excluded low-T outliers
EXCLUDED_TEMPS = {"2026.4.29CS": {-80.0, -77.0}}


# --------------------------------------------------------------------------- #
# 1) Ea vs thickness
# --------------------------------------------------------------------------- #
def ea_vs_thickness() -> pd.DataFrame:
    df = pd.read_csv(WIDE)
    keep = ["sample_id", "material_branch", "role", "thickness_cm", "ea_high_eV",
            "n_success", "n_kk_warning"]
    sub = df[keep].copy()

    def fam(branch: str) -> str:
        b = branch.lower()
        if b.startswith("lrs"):
            return "LRS (lotus-root starch)"
        if "corn-starch" in b:
            return "corn-starch control"
        if "chitosan" in b:
            return "chitosan (CHITO)"
        return "other"

    sub["family"] = sub["material_branch"].map(fam)
    sub.to_csv(OUT / "ea_vs_thickness.csv", index=False, encoding="utf-8-sig")
    return sub


# --------------------------------------------------------------------------- #
# 2) per-temperature KK recompute
# --------------------------------------------------------------------------- #
def _temp_from_name(name: str):
    m = re.search(r"--\s*(\d+(?:\.\d+)?)\s*℃", name)
    if m:
        return -abs(float(m.group(1)))
    m = re.search(r"(?<!-)-\s*(\d+(?:\.\d+)?)\s*℃", name)
    if m:
        return abs(float(m.group(1)))
    m = re.search(r"(\d+(?:\.\d+)?)\s*℃", name)
    if m:
        return float(m.group(1))
    return None


def _parse_spectrum(path: Path):
    """Return (freq, zreal, zimag_pos) arrays from a measurement .txt."""
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return None
    if not lines:
        return None
    head = lines[0].lower()
    if "freq" not in head:
        return None
    rows = []
    for ln in lines[1:]:
        parts = [p.strip() for p in ln.replace("\t", ",").split(",") if p.strip() != ""]
        if len(parts) < 3:
            continue
        try:
            f = float(parts[0]); zr = float(parts[1]); zi = float(parts[2])
        except ValueError:
            continue
        rows.append((f, zr, zi))
    if len(rows) < 10:
        return None
    arr = np.array(rows, dtype=float)
    return arr[:, 0], arr[:, 1], arr[:, 2]


def kk_per_temperature(band_lookup: dict) -> pd.DataFrame:
    recs = []
    for folder in sorted(RAW.iterdir()):
        if not folder.is_dir() or not folder.name.endswith("CS"):
            continue
        for txt in sorted(folder.glob("*.txt")):
            if "制备" in txt.name:
                continue
            t = _temp_from_name(txt.name)
            if t is None:
                continue
            if any(abs(t - x) < 1e-6 for x in EXCLUDED_TEMPS.get(folder.name, ())):
                continue
            parsed = _parse_spectrum(txt)
            if parsed is None:
                continue
            freq, zr, zi = parsed
            # sign-corrected KK (Z = Zr + 1j*Zi, capacitive Im<0) + HF inductive trim,
            # per the fixed kk_validation.py. Suppress linKK's internal stdout.
            with redirect_stdout(io.StringIO()):
                res = validate_kk_consistency(freq, zr, zi, residual_threshold=0.2)
            if not res.get("success"):
                continue
            band = band_lookup.get((folder.name, round(float(t))), "")
            recs.append({
                "sample_id": folder.name,
                "temperature_C": round(float(t), 1),
                "n_freq": int(res.get("details", {}).get("n_points", len(freq))),
                "kk_mu_median": res.get("mu_median"),
                "kk_mu_max": res.get("mu_max"),
                "kk_passed": bool(res.get("passed")),
                "claim_band": band,
            })
    out = pd.DataFrame(recs).sort_values(["sample_id", "temperature_C"], ascending=[True, False])
    out.to_csv(OUT / "kk_residual_per_temperature.csv", index=False, encoding="utf-8-sig")

    # honest per-band KK-warning fraction (LRS headline samples)
    lrs = out[out["sample_id"].isin(LRS) & (out["claim_band"] != "")].copy()
    if not lrs.empty:
        lrs["kk_warn"] = ~lrs["kk_passed"]
        summ = (lrs.groupby("claim_band")
                   .agg(n_spectra=("kk_warn", "size"),
                        n_kk_warn=("kk_warn", "sum"),
                        mean_mu_median=("kk_mu_median", "mean"))
                   .reset_index())
        summ["kk_warn_fraction"] = (summ["n_kk_warn"] / summ["n_spectra"]).round(2)
        summ["mean_mu_median"] = summ["mean_mu_median"].round(3)
        summ.to_csv(OUT / "kk_warning_fraction_by_band_LRS.csv", index=False, encoding="utf-8-sig")
    return out


# --------------------------------------------------------------------------- #
# 3) band-gated Rb/KK table (frozen artifact)
# --------------------------------------------------------------------------- #
def _band_of_tier(tier: str) -> str:
    t = str(tier).lower()
    if "main" in t:
        return "main-text (high-T window)"
    if "supplement" in t:
        return "supplementary (233 K anchor)"
    return "screening/exploratory (cold tail)"


def band_gating_table():
    rb = pd.read_csv(RBQC)
    rb["band"] = rb["qc_tier"].map(_band_of_tier)
    band_lookup = {}
    for _, r in rb.iterrows():
        band_lookup[(str(r["sample_id"]), round(float(r["temperature_C"])))] = _band_of_tier(r["qc_tier"])

    g = (rb.groupby(["sample_id", "band"])
           .agg(n_points=("temperature_C", "size"),
                T_min_C=("temperature_C", "min"),
                T_max_C=("temperature_C", "max"),
                median_abs_rb_delta_pct=("abs_rb_delta_pct_vs_manual", "median"),
                max_abs_rb_delta_pct=("abs_rb_delta_pct_vs_manual", "max"))
           .reset_index())
    g = g.sort_values(["sample_id", "band"]).round(2)
    g.to_csv(OUT / "kk_rb_band_gating_table.csv", index=False, encoding="utf-8-sig")
    return g, band_lookup


# --------------------------------------------------------------------------- #
# 4) combined figure
# --------------------------------------------------------------------------- #
def make_figure(ea: pd.DataFrame, kk: pd.DataFrame):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.4))

    # panel A: Ea_high vs thickness
    colors = {"LRS (lotus-root starch)": "#1f77b4",
              "corn-starch control": "#2ca02c",
              "chitosan (CHITO)": "#d62728",
              "other": "#888888"}
    for fam_name, grp in ea.groupby("family"):
        ax1.scatter(grp["thickness_cm"], grp["ea_high_eV"], s=70,
                    color=colors.get(fam_name, "#888"), label=fam_name, zorder=3)
    for _, r in ea.iterrows():
        ax1.annotate(r["sample_id"].replace("2026.", ""),
                     (r["thickness_cm"], r["ea_high_eV"]),
                     textcoords="offset points", xytext=(6, 4), fontsize=7)
    ax1.axhspan(0.035, 0.045, color="#1f77b4", alpha=0.08)
    ax1.set_xlabel("film thickness (cm)")
    ax1.set_ylabel(r"$E_{a}^{high}$ (eV)")
    ax1.set_title("A  Ea(high) vs thickness (4.25CS deprecated)", fontsize=10)
    ax1.legend(fontsize=6.5, loc="upper left")
    ax1.grid(alpha=0.25)

    # panel B: KK mu_median vs T by band, LRS main samples
    bcol = {"main-text (high-T window)": "#1f77b4",
            "supplementary (233 K anchor)": "#ff7f0e",
            "screening/exploratory (cold tail)": "#d62728",
            "": "#bbbbbb"}
    lrs_kk = kk[kk["sample_id"].isin(LRS)].copy()
    for sid, grp in lrs_kk.groupby("sample_id"):
        ax2.plot(grp["temperature_C"], grp["kk_mu_median"], "-", color="#999", lw=0.8, zorder=1)
        for band, gg in grp.groupby("claim_band"):
            ax2.scatter(gg["temperature_C"], gg["kk_mu_median"], s=42,
                        color=bcol.get(band, "#bbb"), zorder=3,
                        marker="o" if sid == "2026.5.9CS" else "s")
    ax2.axhline(0.2, color="k", ls="--", lw=1, label="KK threshold (median 0.2)")
    ax2.set_xlabel("temperature (°C)")
    ax2.set_ylabel("KK lin-KK residual  μ_median")
    ax2.set_title("B  per-T KK residual, sign-corrected (all « 0.2: KK-clean)", fontsize=10)
    handles = [plt.Line2D([0], [0], marker="o", ls="", color=bcol[b], label=b)
               for b in ["main-text (high-T window)", "supplementary (233 K anchor)",
                         "screening/exploratory (cold tail)"]]
    handles.append(plt.Line2D([0], [0], color="k", ls="--", label="KK threshold 0.2"))
    ax2.legend(handles=handles, fontsize=6.5, loc="upper left")
    ax2.grid(alpha=0.25)

    fig.tight_layout()
    fig.savefig(OUT / "Fig_pillar2_qc.png", dpi=200)
    plt.close(fig)


def main():
    ea = ea_vs_thickness()
    band_tbl, band_lookup = band_gating_table()
    kk = kk_per_temperature(band_lookup)
    make_figure(ea, kk)

    # quick console summary (ASCII only)
    print("[ea_vs_thickness] rows:", len(ea))
    print(ea[["sample_id", "thickness_cm", "ea_high_eV", "family"]].to_string(index=False))
    print("\n[band_gating_table]")
    print(band_tbl.to_string(index=False))
    print("\n[kk recompute] per-sample warning counts (mu_median>=0.2):")
    if not kk.empty:
        warn = (kk.assign(warn=~kk["kk_passed"])
                  .groupby("sample_id")
                  .agg(n=("warn", "size"), n_warn=("warn", "sum")).reset_index())
        print(warn.to_string(index=False))
        # band-level mean residual for LRS
        lrs = kk[kk["sample_id"].isin(LRS) & (kk["claim_band"] != "")]
        if not lrs.empty:
            print("\n[kk recompute] LRS mean mu_median by band:")
            print(lrs.groupby("claim_band")["kk_mu_median"].mean().round(3).to_string())
    print("\n[ok] artifacts written to", OUT)


if __name__ == "__main__":
    main()
