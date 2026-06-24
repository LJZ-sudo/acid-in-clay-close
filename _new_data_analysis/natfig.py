# -*- coding: utf-8 -*-
"""Shared nature-figure publication style + export (Python / matplotlib backend).

apply()   -> sets Arial / top-right spines off / frameless legend / editable-SVG rcParams
save_pub() -> writes SVG (primary, editable text) + PNG 300 + PNG 600 + TIFF 600 (LZW)

Used by the data-figure builders so every panel shares one journal style and exports the
SVG that Digital Discovery / Nature-family submission expects. Data only; no fabrication.
"""
from pathlib import Path
import matplotlib.pyplot as plt


def apply():
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans", "Liberation Sans"],
        "svg.fonttype": "none",
        "font.size": 9, "axes.titlesize": 9, "axes.labelsize": 9,
        "xtick.labelsize": 8, "ytick.labelsize": 8, "legend.fontsize": 8,
        "axes.spines.right": False, "axes.spines.top": False, "legend.frameon": False,
        "savefig.dpi": 600, "figure.dpi": 150,
    })


def save_pub(fig, out_dir, stem):
    out = Path(out_dir)
    fig.savefig(out / f"{stem}.svg", bbox_inches="tight")             # primary, editable vector
    fig.savefig(out / f"{stem}.png", dpi=300, bbox_inches="tight")    # preview raster
    fig.savefig(out / f"{stem}_600dpi.png", dpi=600, bbox_inches="tight")
    try:
        fig.savefig(out / f"{stem}.tiff", dpi=600, pil_kwargs={"compression": "tiff_lzw"})
    except Exception as e:
        print(f"  (TIFF skipped: {e}; use {stem}_600dpi.png)")
