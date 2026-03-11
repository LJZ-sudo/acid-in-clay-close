# -*- coding: utf-8 -*-
"""
Phase 3 Step 2：训练 S60 基准模型与 S8 限域效应模型

- S60：Ea = f(R, T)，纯酸液基线
- S8：Ea = f(R, N, T) + T*N, T*R, R*N 交互项
数据来源：close/output/phase3_results/integrated_data.csv（仅 close 内）
"""

import sys
import json
import pickle
from pathlib import Path
from typing import Dict, Any, Optional

import pandas as pd
import numpy as np
from sklearn.linear_model import Ridge
from sklearn.preprocessing import PolynomialFeatures, StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.model_selection import cross_val_score, KFold
from sklearn.metrics import r2_score, mean_absolute_error
from sklearn.ensemble import GradientBoostingRegressor

CLOSE_ROOT = Path(__file__).resolve().parent.parent
PHASE3_RESULTS_DIR = CLOSE_ROOT / "output" / "phase3_results"
MODELS_DIR = PHASE3_RESULTS_DIR / "models"
DATA_CSV = PHASE3_RESULTS_DIR / "integrated_data.csv"


def train_s60_baseline(df: pd.DataFrame, alpha: float = 5.0, outlier_std: float = 2.0) -> Dict[str, Any]:
    """
    S60 基准模型：Ea = f(R, T_avg_K)，Ridge + 多项式。
    P1 稳健性：先拟合一次，剔除 |residual| > outlier_std*std(residual) 的样本后重拟合；增大 alpha 正则。
    """
    df_s60 = df[df["material_type"] == "S60"].dropna(subset=["R", "T_avg_K", "Ea_eV"]).copy()
    if len(df_s60) < 5:
        return {"success": False, "error": "S60 数据不足", "model": None}

    X = df_s60[["R", "T_avg_K"]].values
    y = df_s60["Ea_eV"].values

    pipe = Pipeline([
        ("poly", PolynomialFeatures(degree=2, include_bias=False)),
        ("scale", StandardScaler()),
        ("ridge", Ridge(alpha=alpha)),
    ])
    pipe.fit(X, y)
    y_pred = pipe.predict(X)
    residuals = y - y_pred
    res_std = np.std(residuals)
    if res_std > 1e-10:
        mask = np.abs(residuals) <= outlier_std * res_std
        n_removed = int((~mask).sum())
        if n_removed > 0 and mask.sum() >= 5:
            X, y = X[mask], y[mask]
            pipe.fit(X, y)
            y_pred = pipe.predict(X)
        else:
            n_removed = 0
    else:
        n_removed = 0

    r2 = r2_score(y, y_pred)
    mae = mean_absolute_error(y, y_pred)
    cv = cross_val_score(pipe, X, y, cv=min(5, len(y)), scoring="r2")
    cv_mean = float(cv.mean())
    cv_std = float(cv.std()) if len(cv) > 1 else 0.0

    return {
        "success": True,
        "model": pipe,
        "n_samples": int(len(y)),
        "n_removed_outliers": n_removed,
        "r2": r2,
        "mae": mae,
        "mae_eV": mae,
        "cv_r2_mean": cv_mean,
        "cv_r2_std": cv_std,
        "ridge_alpha": alpha,
    }


def train_s8_confinement(df: pd.DataFrame) -> Dict[str, Any]:
    """S8 限域模型：Ea = f(R, N, T) + T*N, T*R, R*N"""
    df_s8 = df[df["material_type"] == "S8"].dropna(subset=["R", "N", "T_avg_K", "Ea_eV"]).copy()
    df_s8["N"] = df_s8["N"].fillna(df_s8["N"].mean())
    if len(df_s8) < 5:
        return {"success": False, "error": "S8 数据不足", "model": None}

    df_s8 = df_s8.copy()
    df_s8["T_N"] = df_s8["T_avg_K"] * df_s8["N"]
    df_s8["T_R"] = df_s8["T_avg_K"] * df_s8["R"]
    df_s8["R_N"] = df_s8["R"] * df_s8["N"]
    feats = ["R", "N", "T_avg_K", "T_N", "T_R", "R_N"]
    X = df_s8[feats].values
    y = df_s8["Ea_eV"].values

    model = GradientBoostingRegressor(
        n_estimators=120,
        learning_rate=0.05,
        max_depth=3,
        min_samples_leaf=4,
        random_state=42,
    )
    model.fit(X, y)
    y_pred = model.predict(X)
    r2 = r2_score(y, y_pred)
    mae = mean_absolute_error(y, y_pred)
    cv = cross_val_score(model, X, y, cv=min(5, len(df_s8)), scoring="r2")
    cv_mean = float(cv.mean())
    cv_std = float(cv.std()) if len(cv) > 1 else 0.0

    return {
        "success": True,
        "model": model,
        "feature_names": feats,
        "n_samples": len(df_s8),
        "r2": r2,
        "mae": mae,
        "cv_r2_mean": cv_mean,
        "cv_r2_std": cv_std,
    }


def main() -> int:
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    print("=" * 60)
    print("Phase 3 Step 2：训练 S60 基准模型与 S8 限域模型")
    print("=" * 60)
    if not DATA_CSV.exists():
        print(f"  [ERROR] 请先运行 step1_data_preparation.py，生成 {DATA_CSV}")
        return 1

    df = pd.read_csv(DATA_CSV)
    print(f"  数据: {len(df)} segments")

    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    # S60
    print("\n  [S60 基准模型]")
    s60_result = train_s60_baseline(df)
    if not s60_result["success"]:
        print(f"    {s60_result.get('error', '失败')}")
    else:
        print(f"    n={s60_result['n_samples']}, R²={s60_result['r2']:.4f}, CV R²={s60_result['cv_r2_mean']:.4f}±{s60_result['cv_r2_std']:.4f}, MAE={s60_result['mae']:.4f} eV, removed_outliers={s60_result.get('n_removed_outliers', 0)}")
        with open(MODELS_DIR / "s60_baseline.pkl", "wb") as f:
            pickle.dump({"pipeline": s60_result["model"]}, f)
        print(f"    已保存 -> {MODELS_DIR / 's60_baseline.pkl'}")

    # S8
    print("\n  [S8 限域效应模型]")
    s8_result = train_s8_confinement(df)
    if not s8_result["success"]:
        print(f"    {s8_result.get('error', '失败')}")
    else:
        print(f"    n={s8_result['n_samples']}, R²={s8_result['r2']:.4f}, CV R²={s8_result['cv_r2_mean']:.4f}±{s8_result['cv_r2_std']:.4f}")
        with open(MODELS_DIR / "s8_confinement.pkl", "wb") as f:
            pickle.dump({
                "model": s8_result["model"],
                "feature_names": s8_result["feature_names"],
            }, f)
        print(f"    已保存 -> {MODELS_DIR / 's8_confinement.pkl'}")

    # 计算 ΔEa 统计（S8 段用 S60 预测得到 Ea_bulk，再算 ΔEa）
    metrics = {
        "s60": {
            "r2": s60_result.get("r2"), "cv_r2_mean": s60_result.get("cv_r2_mean"), "cv_r2_std": s60_result.get("cv_r2_std"),
            "n": s60_result.get("n_samples"), "mae_eV": s60_result.get("mae"), "n_removed_outliers": s60_result.get("n_removed_outliers", 0), "ridge_alpha": s60_result.get("ridge_alpha", 1.0),
        } if s60_result.get("success") else {},
        "s8": {"r2": s8_result.get("r2"), "cv_r2_mean": s8_result.get("cv_r2_mean"), "n": s8_result.get("n_samples")} if s8_result.get("success") else {},
    }
    if s60_result.get("success") and s8_result.get("success"):
        df_s8 = df[df["material_type"] == "S8"].dropna(subset=["R", "N", "T_avg_K", "Ea_eV"]).copy()
        df_s8["N"] = df_s8["N"].fillna(df_s8["N"].mean())
        pipe_s60 = s60_result["model"]
        ea_bulk = np.array([float(pipe_s60.predict(np.array([[r, t]]))[0]) for r, t in zip(df_s8["R"], df_s8["T_avg_K"])])
        delta_ea = df_s8["Ea_eV"].values - ea_bulk
        metrics["delta_Ea"] = {"mean": float(np.mean(delta_ea)), "std": float(np.std(delta_ea)), "min": float(np.min(delta_ea)), "max": float(np.max(delta_ea))}

    with open(MODELS_DIR / "metrics.json", "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2, ensure_ascii=False)
    print(f"\n  已保存 -> {MODELS_DIR / 'metrics.json'}")

    print("\n[Step 2 完成]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
