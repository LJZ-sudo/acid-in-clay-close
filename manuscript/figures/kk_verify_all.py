# -*- coding: utf-8 -*-
"""Full verification (read-only, no pipeline changes): for every CS sample and
every temperature spectrum, recompute lin-KK mu_median under
  (a) current pipeline convention  Z = Zr - 1j*Zi
  (b) sign-corrected               Z = Zr + 1j*Zi
  (c) sign-corrected + trim HF inductive tail (Im(Z)>0) and nonphysical Zr<=0
and count how many spectra exceed the 0.2 warning threshold under each.

This tells us whether the high KK-warning counts are a sign-convention artifact
across ALL samples (LRS, corn-starch, chitosan), not just 5.9CS.
"""
from __future__ import annotations

import io
import re
from contextlib import redirect_stdout
from pathlib import Path

import numpy as np
from impedance.validation import linKK

REPO = Path(__file__).resolve().parent.parent.parent
RAW = REPO / "V1.0-qianduan-mainline" / "data" / "新材料"
THRESH = 0.2
EXCLUDED = {"2026.4.29CS": {-80.0, -77.0}}


def temp_from_name(name: str):
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
    if len(rows) < 10:
        return None
    a = np.array(rows, float)
    return a[:, 0], a[:, 1], a[:, 2]


def mu(freq, Z):
    if len(freq) < 10:
        return float("nan")
    try:
        with redirect_stdout(io.StringIO()):
            M, m, Zf, rr, ri = linKK(freq, Z, c=0.5, max_M=100, fit_type="complex")
        return float(np.median(np.concatenate([np.abs(rr), np.abs(ri)])))
    except Exception:
        return float("nan")


def family(folder: str) -> str:
    return {"2026.4.25CS": "LRS(thick,deprecated)", "2026.4.27CS": "corn-starch",
            "2026.4.28CS": "corn-starch", "2026.4.29CS": "LRS(thin)",
            "2026.4.30CS": "chitosan", "2026.5.1CS": "chitosan",
            "2026.5.9CS": "LRS(headline)"}.get(folder, folder)


def main():
    print(f"{'sample':<13}{'family':<22}{'n':>4} | warnings(mu>0.2)  "
          f"{'(a)cur':>7}{'(b)sign':>8}{'(c)trim':>8}   {'medMu_a':>8}{'medMu_b':>8}")
    grand = {"a": 0, "b": 0, "c": 0, "n": 0}
    for folder in sorted(RAW.iterdir()):
        if not folder.is_dir() or not folder.name.endswith("CS"):
            continue
        mus = {"a": [], "b": [], "c": []}
        for txt in sorted(folder.glob("*.txt")):
            if "制备" in txt.name:
                continue
            t = temp_from_name(txt.name)
            if t is None or any(abs(t - x) < 1e-6 for x in EXCLUDED.get(folder.name, ())):
                continue
            p = parse(txt)
            if p is None:
                continue
            freq, zr, zi = p
            mus["a"].append(mu(freq, zr - 1j * zi))
            mus["b"].append(mu(freq, zr + 1j * zi))
            m_d = (zi < 0) & (zr > 0)
            mus["c"].append(mu(freq[m_d], (zr + 1j * zi)[m_d]) if m_d.sum() >= 10 else np.nan)
        n = len(mus["a"])
        if n == 0:
            continue
        wa = int(np.nansum(np.array(mus["a"]) >= THRESH))
        wb = int(np.nansum(np.array(mus["b"]) >= THRESH))
        wc = int(np.nansum(np.array(mus["c"]) >= THRESH))
        ma = np.nanmedian(mus["a"]); mb = np.nanmedian(mus["b"])
        print(f"{folder.name:<13}{family(folder.name):<22}{n:>4} | "
              f"{wa:>7}{wb:>8}{wc:>8}   {ma:>8.3f}{mb:>8.3f}")
        grand["a"] += wa; grand["b"] += wb; grand["c"] += wc; grand["n"] += n
    print("-" * 86)
    print(f"{'TOTAL':<35}{grand['n']:>4} | {grand['a']:>7}{grand['b']:>8}{grand['c']:>8}")
    print("\nthreshold mu_median>=0.2 => KK warning. "
          "(a)=current pipeline sign, (b)=sign-corrected, (c)=corrected+trim inductive/neg-real.")


if __name__ == "__main__":
    main()
