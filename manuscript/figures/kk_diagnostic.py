# -*- coding: utf-8 -*-
"""Diagnostic: is the high-T KK 'warning' an artifact of sign convention and/or
the high-frequency inductive tail, rather than bad data?

For selected 5.9CS spectra (main-text window + cold tail) we recompute the
impedance lin-KK residual under:
  (a) current pipeline convention:  Z = Zr - 1j*Zi    (kk_validation.py)
  (b) sign-corrected:               Z = Zr + 1j*Zi
  (c) sign-corrected + trim HF inductive tail (drop points with Im(Z) > 0)
  (d) (c) + drop nonphysical Zr<=0 points
We report mu_median (the metric used by the gate, threshold 0.2) and the
fraction of inductive / negative-real points.
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
from impedance.validation import linKK

REPO = Path(__file__).resolve().parent.parent.parent
RAW = REPO / "V1.0-qianduan-mainline" / "data" / "新材料" / "2026.5.9CS"

TARGETS = {
    "+18C main": "18℃",
    "0C main": "0℃-",
    "-21C main": "-21℃",
    "-30C main": "-30℃",
    "-45C supp": "-45℃",
    "-60C cold": "-60℃",
    "-75C cold": "-75℃",
}


def parse(path: Path):
    rows = []
    for ln in path.read_text(encoding="utf-8", errors="ignore").splitlines()[1:]:
        parts = [p for p in ln.replace("\t", ",").split(",") if p.strip()]
        if len(parts) < 3:
            continue
        try:
            f, zr, zi = float(parts[0]), float(parts[1]), float(parts[2])
        except ValueError:
            continue
        rows.append((f, zr, zi))
    a = np.array(rows, float)
    return a[:, 0], a[:, 1], a[:, 2]


def mu_median(freq, Z):
    try:
        M, mu, Zf, rr, ri = linKK(freq, Z, c=0.5, max_M=100, fit_type="complex")
        res = np.concatenate([np.abs(rr), np.abs(ri)])
        return float(np.median(res)), int(M)
    except Exception as e:
        return float("nan"), -1


def find_file(token: str):
    # token like "18℃" (positive) -> filename has "-18℃"? careful with sign.
    cands = sorted(RAW.glob("*.txt"))
    for p in cands:
        if "制备" in p.name:
            continue
        if token in p.name:
            # avoid matching -18 when looking for 18: ensure not preceded by extra '-'
            return p
    return None


def main():
    print(f"{'spectrum':<12}{'n':>4}{'%ind':>6}{'%negRe':>7}"
          f"{'(a)Zr-jZi':>11}{'(b)Zr+jZi':>11}{'(c)+trimInd':>12}{'(d)+trimNeg':>12}")
    for label, token in TARGETS.items():
        # build a robust regex: token may be like '0℃-' to disambiguate
        p = None
        for cand in sorted(RAW.glob("*.txt")):
            if "制备" in cand.name:
                continue
            name = cand.name
            if token == "18℃" and re.search(r"(?<!-)-18℃|[^-\d]18℃|-4-18℃", name):
                # 18C positive: file 'LRS-...-4-18℃-1.txt' (single hyphen before 18)
                if "-18℃" in name and "--18" not in name and "AO3-4-18" in name:
                    p = cand; break
            elif token == "0℃-":
                if "-0℃-" in name:
                    p = cand; break
            elif token in ("-21℃", "-30℃", "-45℃", "-60℃", "-75℃"):
                if ("-" + token.lstrip("-")) in name and ("--" + token.lstrip("-") in name or "4--" + token.lstrip("-") in name):
                    p = cand; break
        if p is None:
            # fallback simple contains
            for cand in sorted(RAW.glob("*.txt")):
                if "制备" not in cand.name and token.strip("-") + "℃" in cand.name:
                    p = cand
        if p is None:
            print(f"{label:<12}  (file not found for token {token})")
            continue

        freq, zr, zi = parse(p)
        n = len(freq)
        # file Zi: capacitive arc is negative -> Im(Z) true. inductive = Zi>0.
        pct_ind = 100.0 * np.mean(zi > 0)
        pct_negre = 100.0 * np.mean(zr <= 0)

        a, _ = mu_median(freq, zr - 1j * zi)
        b, _ = mu_median(freq, zr + 1j * zi)
        # (c) sign corrected + drop inductive (Im>0) points
        m_cap = zi < 0
        c = mu_median(freq[m_cap], (zr + 1j * zi)[m_cap])[0] if m_cap.sum() >= 10 else float("nan")
        # (d) also drop nonphysical negative real
        m_d = (zi < 0) & (zr > 0)
        d = mu_median(freq[m_d], (zr + 1j * zi)[m_d])[0] if m_d.sum() >= 10 else float("nan")

        print(f"{label:<12}{n:>4}{pct_ind:>6.0f}{pct_negre:>7.0f}"
              f"{a:>11.3f}{b:>11.3f}{c:>12.3f}{d:>12.3f}")

    print("\nthreshold = 0.20 (mu_median below = KK pass). "
          "Lower is better. %ind = inductive (Im(Z)>0) fraction.")


if __name__ == "__main__":
    main()
