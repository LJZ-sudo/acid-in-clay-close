# -*- coding: utf-8 -*-
"""
Phase 3：Meyer-Neldel 分析

ln(σ₀) = ln(σ₀₀) + Ea / E_MN  =>  线性回归 ln_sigma0 ~ Ea_eV，斜率 = 1/E_MN，故 E_MN = 1/slope。
数据来源：close/output/phase3_results/integrated_data.csv。
"""

import sys
import json
from pathlib import Path
from typing import Dict, Any, List, Optional

import pandas as pd
import numpy as np
from scipy import stats
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

CLOSE_ROOT = Path(__file__).resolve().parent.parent
PHASE3_RESULTS_DIR = CLOSE_ROOT / "output" / "phase3_results"
DATA_CSV = PHASE3_RESULTS_DIR / "integrated_data.csv"
MN_DIR = PHASE3_RESULTS_DIR / "meyer_neldel"


def fit_meyer_neldel(df: pd.DataFrame, material: str = "S8", min_points: int = 5) -> Optional[Dict[str, Any]]:
    """
    ln_sigma0 = a + Ea/E_MN  =>  线性回归 ln_sigma0 ~ Ea_eV。
    斜率 = 1/E_MN，故 E_MN_eV = 1/slope（若 slope <= 0 则 E_MN 无效）。
    """
    sub = df.dropna(subset=["Ea_eV", "ln_sigma0"]).copy()
    sub = sub[sub["Ea_eV"] > 0]
    if material != "all":
        sub = sub[sub["material_type"] == material]
    if len(sub) < min_points:
        return None
    x = sub["Ea_eV"].values
    y = sub["ln_sigma0"].values
    lr = stats.linregress(x, y)
    slope = lr.slope
    intercept = lr.intercept
    r2 = lr.rvalue ** 2
    p_value = lr.pvalue
    stderr_slope = lr.stderr
    if slope > 0:
        E_MN_eV = 1.0 / slope
        E_MN_se = float(stderr_slope / (slope ** 2)) if stderr_slope and slope else None
    else:
        E_MN_eV = np.nan
        E_MN_se = None
    return {
        "material": material,
        "n_points": len(sub),
        "slope": float(slope),
        "intercept": float(intercept),
        "E_MN_eV": float(E_MN_eV) if not np.isnan(E_MN_eV) else None,
        "E_MN_se": E_MN_se,
        "r_squared": float(r2),
        "p_value": float(p_value),
        "interpretation": "ln(sigma0) = a + Ea/E_MN; E_MN = 1/slope (compensation effect)" if slope > 0 else "slope<=0, E_MN not defined",
    }


def main() -> int:
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    print("=" * 60)
    print("Phase 3：Meyer-Neldel 分析")
    print("=" * 60)

    if not DATA_CSV.exists():
        print("  [ERROR] 请先运行 step1")
        return 1

    df = pd.read_csv(DATA_CSV)
    df = df.dropna(subset=["Ea_eV", "ln_sigma0"])
    df = df[df["Ea_eV"] > 0]
    if df.empty:
        print("  [ERROR] 无有效 Ea_eV / ln_sigma0 数据")
        return 1

    MN_DIR.mkdir(parents=True, exist_ok=True)
    results = {}

    # S8 全体
    r_s8 = fit_meyer_neldel(df, material="S8")
    if r_s8:
        results["S8"] = r_s8
        print(f"  [S8] n={r_s8['n_points']}, E_MN={r_s8['E_MN_eV']:.3f} eV, R²={r_s8['r_squared']:.4f}, p={r_s8['p_value']:.4f}")

    # S60 全体
    r_s60 = fit_meyer_neldel(df, material="S60")
    if r_s60:
        results["S60"] = r_s60
        print(f"  [S60] n={r_s60['n_points']}, E_MN={r_s60['E_MN_eV']:.3f} eV, R²={r_s60['r_squared']:.4f}, p={r_s60['p_value']:.4f}")

    # S8 按温区：高 T >= 270K，低 T < 230K
    s8 = df[df["material_type"] == "S8"].copy()
    if len(s8) >= 10:
        high = s8[s8["T_avg_K"] >= 270]
        low = s8[s8["T_avg_K"] < 230]
        r_high = fit_meyer_neldel(high, material="S8", min_points=3)
        r_low = fit_meyer_neldel(low, material="S8", min_points=3)
        if r_high:
            results["S8_high_T"] = r_high
            print(f"  [S8 高温] n={r_high['n_points']}, E_MN={r_high['E_MN_eV']:.3f} eV, R²={r_high['r_squared']:.4f}")
        if r_low:
            results["S8_low_T"] = r_low
            print(f"  [S8 低温] n={r_low['n_points']}, E_MN={r_low['E_MN_eV']:.3f} eV, R²={r_low['r_squared']:.4f}")

    with open(MN_DIR / "summary.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"  已写入 {MN_DIR / 'summary.json'}")

    # 图：S8 ln_sigma0 vs Ea
    s8_plot = df[df["material_type"] == "S8"]
    if len(s8_plot) >= 5:
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.scatter(s8_plot["Ea_eV"], s8_plot["ln_sigma0"], alpha=0.6, s=25, c="steelblue")
        x = s8_plot["Ea_eV"].values
        y = s8_plot["ln_sigma0"].values
        slope, intercept = np.polyfit(x, y, 1)
        x_line = np.linspace(x.min(), x.max(), 100)
        ax.plot(x_line, slope * x_line + intercept, "r-", lw=2, label=f"Linear: slope={slope:.3f}, E_MN={1/slope:.2f} eV")
        ax.set_xlabel("Ea (eV)", fontsize=11)
        ax.set_ylabel("ln(sigma0) (S/cm)", fontsize=11)
        ax.set_title("Meyer-Neldel: ln(sigma0) vs Ea (S8, close Phase3)", fontsize=12, fontweight="bold")
        ax.legend(loc="best")
        ax.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(MN_DIR / "meyer_neldel_s8.png", dpi=150, bbox_inches="tight")
        plt.close()
        print(f"  已保存 -> {MN_DIR / 'meyer_neldel_s8.png'}")

    print("\n[Meyer-Neldel 完成]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
