# -*- coding: utf-8 -*-
"""
Phase 3 Step 3：限域效应分析 ΔEa = Ea(S8) − Ea(S60 预测)

- 计算 ΔEa 并按温区统计
- P0：为 mean ΔEa 补充 bootstrap 95% CI；低温 vs 高温 显著性检验；ΔEa(T) 线性拟合的斜率/截距标准误或 CI
使用 close 内 step2 训练的模型，仅基于 close/output/phase3_results 数据。
"""

import sys
import json
import pickle
from pathlib import Path
from typing import Dict, Any, Tuple

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy import stats

CLOSE_ROOT = Path(__file__).resolve().parent.parent
PHASE3_RESULTS_DIR = CLOSE_ROOT / "output" / "phase3_results"
MODELS_DIR = PHASE3_RESULTS_DIR / "models"
CONFINEMENT_DIR = PHASE3_RESULTS_DIR / "confinement"
DATA_CSV = PHASE3_RESULTS_DIR / "integrated_data.csv"

N_BOOTSTRAP = 2000
CI_LEVEL = 0.95


def bootstrap_mean_ci(data: np.ndarray, n_bootstrap: int = N_BOOTSTRAP, ci: float = CI_LEVEL) -> Tuple[float, float, float]:
    """Bootstrap 95% CI for mean."""
    data = np.asarray(data).flatten()
    data = data[~np.isnan(data)]
    n = len(data)
    if n < 2:
        mean = float(np.mean(data)) if n else np.nan
        return mean, np.nan, np.nan
    rng = np.random.default_rng(42)
    boot_means = [float(np.mean(rng.choice(data, size=n, replace=True))) for _ in range(n_bootstrap)]
    boot_means = np.array(boot_means)
    alpha = 1 - ci
    ci_low = float(np.percentile(boot_means, alpha / 2 * 100))
    ci_high = float(np.percentile(boot_means, (1 - alpha / 2) * 100))
    mean = float(np.mean(data))
    return mean, ci_low, ci_high


def load_models():
    """加载 S60 与 S8 模型"""
    with open(MODELS_DIR / "s60_baseline.pkl", "rb") as f:
        s60_data = pickle.load(f)
    pipe = s60_data["pipeline"]
    def predict_bulk(R, T):
        return float(pipe.predict(np.array([[R, T]]))[0])

    with open(MODELS_DIR / "s8_confinement.pkl", "rb") as f:
        s8_data = pickle.load(f)
    model = s8_data["model"]
    feats = s8_data["feature_names"]

    def predict_s8(R, N, T):
        T_N, T_R, R_N = T * N, T * R, R * N
        x = np.array([[R, N, T, T_N, T_R, R_N]])
        return float(model.predict(x)[0])

    return predict_bulk, predict_s8


def main() -> int:
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    print("=" * 60)
    print("Phase 3 Step 3：限域效应分析 ΔEa（含不确定性）")
    print("=" * 60)

    if not DATA_CSV.exists() or not (MODELS_DIR / "s60_baseline.pkl").exists():
        print("  [ERROR] 请先运行 step1 和 step2")
        return 1

    df = pd.read_csv(DATA_CSV)
    df_s8 = df[df["material_type"] == "S8"].dropna(subset=["R", "N", "T_avg_K", "Ea_eV"]).copy()
    df_s8["N"] = df_s8["N"].fillna(df_s8["N"].mean())
    if df_s8.empty:
        print("  [ERROR] 无 S8 数据")
        return 1

    predict_bulk, _ = load_models()
    ea_bulk = np.array([predict_bulk(r, t) for r, t in zip(df_s8["R"], df_s8["T_avg_K"])])
    df_s8 = df_s8.copy()
    df_s8["Ea_bulk"] = ea_bulk
    df_s8["delta_Ea"] = df_s8["Ea_eV"] - df_s8["Ea_bulk"]

    CONFINEMENT_DIR.mkdir(parents=True, exist_ok=True)
    out_csv = CONFINEMENT_DIR / "delta_ea_by_segment.csv"
    df_s8.to_csv(out_csv, index=False, encoding="utf-8-sig")
    print(f"  已写入 {out_csv} ({len(df_s8)} 行)")

    # 温区划分
    low_T = df_s8[df_s8["T_avg_K"] < 230]
    mid_T = df_s8[(df_s8["T_avg_K"] >= 230) & (df_s8["T_avg_K"] < 270)]
    high_T = df_s8[df_s8["T_avg_K"] >= 270]

    # Bootstrap 95% CI for mean ΔEa
    def add_ci(name: str, data: pd.Series) -> Dict[str, Any]:
        if len(data) < 2:
            return {"mean": float(data.mean()), "n": len(data), "ci_95_low": None, "ci_95_high": None}
        mean, ci_low, ci_high = bootstrap_mean_ci(data.values)
        return {"mean": mean, "std": float(data.std()), "n": len(data), "ci_95_low": ci_low, "ci_95_high": ci_high}

    overall = add_ci("overall", df_s8["delta_Ea"])
    low_T_summary = add_ci("low_T", low_T["delta_Ea"]) if len(low_T) >= 2 else {"mean": float(low_T["delta_Ea"].mean()), "n": len(low_T), "ci_95_low": None, "ci_95_high": None}
    mid_T_summary = add_ci("mid_T", mid_T["delta_Ea"]) if len(mid_T) >= 2 else {"mean": float(mid_T["delta_Ea"].mean()), "n": len(mid_T), "ci_95_low": None, "ci_95_high": None}
    high_T_summary = add_ci("high_T", high_T["delta_Ea"]) if len(high_T) >= 2 else {"mean": float(high_T["delta_Ea"].mean()), "n": len(high_T), "ci_95_low": None, "ci_95_high": None}

    # 低温 vs 高温 mean ΔEa 显著性检验（t 检验）
    low_high_ttest = None
    if len(low_T) >= 2 and len(high_T) >= 2:
        t_stat, p_value = stats.ttest_ind(low_T["delta_Ea"], high_T["delta_Ea"])
        low_high_ttest = {"t_statistic": float(t_stat), "p_value": float(p_value), "significant_005": bool(p_value < 0.05)}

    # ΔEa(T) 线性拟合：ΔEa = slope * T + intercept，给出斜率/截距及标准误
    T_arr = df_s8["T_avg_K"].values
    dEa_arr = df_s8["delta_Ea"].values
    slope, intercept = np.polyfit(T_arr, dEa_arr, 1)
    # 标准误：用 scipy.stats.linregress
    lr = stats.linregress(T_arr, dEa_arr)
    slope_se = getattr(lr, "stderr", None) or np.nan
    intercept_se = getattr(lr, "intercept_stderr", None) if hasattr(lr, "intercept_stderr") else np.nan
    r_squared_fit = lr.rvalue ** 2 if getattr(lr, "rvalue", None) is not None else np.nan
    # Bootstrap CI for slope and intercept
    rng = np.random.default_rng(42)
    slopes_boot, intercepts_boot = [], []
    for _ in range(N_BOOTSTRAP):
        idx = rng.integers(0, len(T_arr), size=len(T_arr))
        s, i = np.polyfit(T_arr[idx], dEa_arr[idx], 1)
        slopes_boot.append(s)
        intercepts_boot.append(i)
    slope_ci = (float(np.percentile(slopes_boot, 2.5)), float(np.percentile(slopes_boot, 97.5)))
    intercept_ci = (float(np.percentile(intercepts_boot, 2.5)), float(np.percentile(intercepts_boot, 97.5)))

    summary = {
        "overall": overall,
        "low_T_under_230K": low_T_summary,
        "mid_T_230_270K": mid_T_summary,
        "high_T_over_270K": high_T_summary,
        "low_vs_high_T_ttest": low_high_ttest,
        "delta_Ea_vs_T_linear_fit": {
            "slope_per_K": float(slope),
            "intercept_eV": float(intercept),
            "slope_se": float(slope_se) if not np.isnan(slope_se) else None,
            "slope_ci_95": slope_ci,
            "intercept_ci_95": intercept_ci,
            "r_squared": float(r_squared_fit) if not np.isnan(r_squared_fit) else None,
        },
    }
    with open(CONFINEMENT_DIR / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"  已写入 {CONFINEMENT_DIR / 'summary.json'}")

    print(f"  ΔEa 整体: mean={overall['mean']:.4f} eV, 95%CI=[{overall.get('ci_95_low') or '—'}, {overall.get('ci_95_high') or '—'}]")
    if low_T_summary.get("n", 0) >= 2:
        print(f"  低温 (<230K): mean ΔEa={low_T_summary['mean']:.4f} eV, 95%CI=[{low_T_summary.get('ci_95_low')}, {low_T_summary.get('ci_95_high')}], n={low_T_summary['n']}")
    if high_T_summary.get("n", 0) >= 2:
        print(f"  高温 (>270K): mean ΔEa={high_T_summary['mean']:.4f} eV, 95%CI=[{high_T_summary.get('ci_95_low')}, {high_T_summary.get('ci_95_high')}], n={high_T_summary['n']}")
    if low_high_ttest:
        print(f"  低温 vs 高温 ΔEa: t={low_high_ttest['t_statistic']:.3f}, p={low_high_ttest['p_value']:.4f}, significant(p<0.05)={low_high_ttest['significant_005']}")
    print(f"  ΔEa(T) 线性: slope={slope:.6f} eV/K, intercept={intercept:.3f} eV, slope_95%CI=[{slope_ci[0]:.6f}, {slope_ci[1]:.6f}]")

    # 图：ΔEa vs T
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.scatter(df_s8["T_avg_K"], df_s8["delta_Ea"], alpha=0.6, s=25, c="steelblue", edgecolors="none")
    T_line = np.linspace(df_s8["T_avg_K"].min(), df_s8["T_avg_K"].max(), 100)
    ax.plot(T_line, np.poly1d([slope, intercept])(T_line), "r-", lw=2, label=f"Linear fit Delta_Ea={slope:.4f}T+{intercept:.3f}")
    ax.axhline(0, color="gray", ls="--", alpha=0.7)
    ax.set_xlabel("T_avg (K)", fontsize=11)
    ax.set_ylabel("Delta_Ea = Ea(S8) - Ea(S60 pred) (eV)", fontsize=11)
    ax.set_title("Confinement Delta_Ea vs T (close Phase3)", fontsize=12, fontweight="bold")
    ax.legend(loc="best", fontsize=9)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plot_path = CONFINEMENT_DIR / "delta_ea_plot.png"
    plt.savefig(plot_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  已保存 -> {plot_path}")

    print("\n[Step 3 完成]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
