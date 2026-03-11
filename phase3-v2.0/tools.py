# -*- coding: utf-8 -*-
"""
Phase 3 v2.0 工具函数模块

将 Phase 3 各分析步骤包装为可供 Agent 调用的纯函数工具。
每个工具：
  - 接受结构化参数
  - 返回结构化字典结果
  - 不依赖全局状态
  - 可独立调用

工具列表:
  1. tool_explore_data        — 数据探查（Phase 1 结果概览）
  2. tool_prepare_data        — 数据准备（JSON → segment DataFrame）
  3. tool_train_models        — 模型训练（S60 基准 + S8 限域）
  4. tool_confinement         — 限域效应分析（ΔEa + 统计检验）
  5. tool_meyer_neldel        — Meyer-Neldel 补偿效应分析
  6. tool_cross_material      — 跨材料迁移验证
"""

import json
import pickle
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import pandas as pd
import numpy as np
from scipy import stats

# sklearn imports
from sklearn.linear_model import Ridge
from sklearn.preprocessing import PolynomialFeatures, StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.model_selection import cross_val_score
from sklearn.metrics import r2_score, mean_absolute_error
from sklearn.ensemble import GradientBoostingRegressor

# matplotlib (non-interactive)
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


# ============================================================
# 常量
# ============================================================
N_BOOTSTRAP = 2000
CI_LEVEL = 0.95
S8_FEATURES = ["R", "N", "T_avg_K", "T_N", "T_R", "R_N"]


# ============================================================
# 工具 1: 数据探查
# ============================================================

def tool_explore_data(phase1_dir: Path) -> Dict[str, Any]:
    """
    探查 Phase 1 结果，返回数据概览供 Agent 决策。

    Args:
        phase1_dir: Phase 1 结果目录 (含 *_analysis_result.json)

    Returns:
        数据概览字典 {materials, n_samples, n_files, summary_by_material, ...}
    """
    if not phase1_dir.exists():
        return {"success": False, "error": f"目录不存在: {phase1_dir}"}

    json_files = sorted(phase1_dir.glob("*_analysis_result.json"))
    if not json_files:
        return {"success": False, "error": "未找到任何 analysis_result.json"}

    materials = {}
    all_temps = []
    all_Ea = []
    total_segments = 0

    for jf in json_files:
        try:
            data = json.loads(jf.read_text(encoding="utf-8"))
        except Exception:
            continue

        mat = data.get("material_type", "unknown")
        sid = data.get("sample_id", jf.stem)
        segs = data.get("arrhenius", {}).get("segments", [])

        if mat not in materials:
            materials[mat] = {"n_samples": 0, "n_segments": 0, "sample_ids": []}
        materials[mat]["n_samples"] += 1
        materials[mat]["n_segments"] += len(segs)
        materials[mat]["sample_ids"].append(sid)
        total_segments += len(segs)

        temps = data.get("temperatures", [])
        if temps:
            all_temps.extend([t for t in temps if t and t > 0])

        for seg in segs:
            ea = seg.get("Ea_eV")
            if ea and ea > 0:
                all_Ea.append(ea)

    # 判断数据特征
    has_baseline = "S60" in materials
    has_confinement = "S8" in materials
    other_materials = [m for m in materials if m not in ("S8", "S60")]

    return {
        "success": True,
        "n_files": len(json_files),
        "n_materials": len(materials),
        "material_names": sorted(materials.keys()),
        "total_segments": total_segments,
        "summary_by_material": {
            k: {"n_samples": v["n_samples"], "n_segments": v["n_segments"]}
            for k, v in materials.items()
        },
        "temp_range_K": [round(min(all_temps), 1), round(max(all_temps), 1)] if all_temps else None,
        "Ea_range_eV": [round(min(all_Ea), 3), round(max(all_Ea), 3)] if all_Ea else None,
        "has_baseline_material": has_baseline,
        "has_confinement_material": has_confinement,
        "other_materials": other_materials,
        "recommended_analyses": _recommend_analyses(has_baseline, has_confinement, other_materials, total_segments),
    }


def _recommend_analyses(has_baseline: bool, has_confinement: bool, other_mats: list, n_seg: int) -> List[str]:
    """基于数据特征推荐分析步骤"""
    recs = ["prepare_data"]
    if has_baseline and has_confinement:
        recs.append("train_models")
        recs.append("confinement_analysis")
    if n_seg >= 10:
        recs.append("meyer_neldel")
    if has_confinement and other_mats:
        recs.append("cross_material")
    return recs


# ============================================================
# 工具 2: 数据准备
# ============================================================

def tool_prepare_data(phase1_dir: Path, output_dir: Path) -> Dict[str, Any]:
    """
    从 Phase 1 JSON 提取 segment 级数据，生成 integrated_data.csv。

    Args:
        phase1_dir: Phase 1 结果目录
        output_dir: Phase 3 v2.0 输出目录

    Returns:
        {"success", "n_rows", "n_samples", "csv_path", "stats_by_material"}
    """
    json_files = sorted(phase1_dir.glob("*_analysis_result.json"))
    if not json_files:
        return {"success": False, "error": "未找到 Phase 1 结果"}

    all_rows = []
    for jf in json_files:
        try:
            data = json.loads(jf.read_text(encoding="utf-8"))
        except Exception:
            continue
        rows = _extract_segment_rows(data)
        all_rows.extend(rows)

    df = pd.DataFrame(all_rows)
    if df.empty:
        return {"success": False, "error": "未提取到任何 segment 数据"}

    # 过滤无效行
    df = df.dropna(subset=["Ea_eV", "T_avg_K"])
    df = df[df["Ea_eV"] > 0]
    df = df[df["T_avg_K"] > 0]

    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "integrated_data.csv"
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")

    # 按材料统计
    stats_by_material = {}
    for mat in sorted(df["material_type"].unique()):
        sub = df[df["material_type"] == mat]
        stats_by_material[mat] = {
            "n_segments": len(sub),
            "n_samples": sub["sample_id"].nunique(),
        }

    return {
        "success": True,
        "n_rows": len(df),
        "n_samples": df["sample_id"].nunique(),
        "csv_path": str(csv_path),
        "stats_by_material": stats_by_material,
    }


def _extract_segment_rows(data: Dict) -> List[Dict]:
    """从单个 analysis_result.json 提取 segment 行"""
    sample_id = data.get("sample_id", "unknown")
    material_type = data.get("material_type", "")
    R = data.get("R")
    N = data.get("N")
    arrhenius = data.get("arrhenius") or {}
    segments = arrhenius.get("segments") or []

    if not segments:
        return _fallback_whole_range(data)

    rows = []
    for seg in segments:
        temp_range = seg.get("temp_range_K") or seg.get("T_range_K")
        if isinstance(temp_range, (list, tuple)) and len(temp_range) >= 2:
            t_avg = float(np.mean(temp_range))
        else:
            t_avg = np.nan

        ea = seg.get("Ea_eV") or seg.get("ea_eV") or seg.get("Ea")
        ln_s0 = seg.get("ln_sigma0")
        s0 = seg.get("sigma0_S_per_cm") or seg.get("sigma0")
        if s0 is None and ln_s0 is not None:
            s0 = float(np.exp(ln_s0))
        r2 = seg.get("r_squared") or seg.get("R_squared")
        n_pts = seg.get("n_points") or seg.get("data_points")

        rows.append({
            "sample_id": sample_id,
            "material_type": material_type,
            "R": float(R) if R is not None and not (isinstance(R, float) and np.isnan(R)) else np.nan,
            "N": float(N) if N is not None and not (isinstance(N, float) and np.isnan(N)) else np.nan,
            "T_avg_K": t_avg,
            "Ea_eV": float(ea) if ea is not None else np.nan,
            "ln_sigma0": float(ln_s0) if ln_s0 is not None else np.nan,
            "sigma0_S_per_cm": float(s0) if s0 is not None else np.nan,
            "r_squared": float(r2) if r2 is not None else np.nan,
            "n_points": int(n_pts) if n_pts is not None else None,
            "segment": seg.get("segment"),
        })
    return rows


def _fallback_whole_range(data: Dict) -> List[Dict]:
    """无分段时用全温区 Arrhenius 拟合生成 1 行"""
    sample_id = data.get("sample_id", "unknown")
    material_type = data.get("material_type", "")
    R = data.get("R")
    N = data.get("N")
    temps = data.get("temperatures") or []
    cond = data.get("conductivity_values") or []
    if not temps or not cond or len(temps) != len(cond) or len(temps) < 3:
        return []
    temps = np.array(temps, dtype=float)
    cond = np.array(cond, dtype=float)
    valid = (temps > 0) & (cond > 0)
    if valid.sum() < 3:
        return []
    inv_T = 1.0 / temps[valid]
    ln_sigma = np.log(cond[valid])
    kB_eV = 8.617333e-5
    coeffs = np.polyfit(inv_T, ln_sigma, 1)
    Ea_eV = -coeffs[0] * kB_eV
    ln_sigma0 = coeffs[1]
    if Ea_eV <= 0 or not np.isfinite(Ea_eV):
        return []
    return [{
        "sample_id": sample_id,
        "material_type": material_type,
        "R": float(R) if R is not None and not (isinstance(R, float) and np.isnan(R)) else np.nan,
        "N": float(N) if N is not None and not (isinstance(N, float) and np.isnan(N)) else np.nan,
        "T_avg_K": float(np.mean(temps[valid])),
        "Ea_eV": float(Ea_eV),
        "ln_sigma0": float(ln_sigma0),
        "sigma0_S_per_cm": float(np.exp(ln_sigma0)),
        "r_squared": np.nan,
        "n_points": int(valid.sum()),
        "segment": "full_range",
    }]


# ============================================================
# 工具 3: 模型训练
# ============================================================

def tool_train_models(csv_path: Path, output_dir: Path) -> Dict[str, Any]:
    """
    训练 S60 基准模型和 S8 限域模型。

    Args:
        csv_path: integrated_data.csv 路径
        output_dir: 输出目录 (模型 pkl + metrics.json)

    Returns:
        {"success", "s60_metrics", "s8_metrics", "delta_Ea_stats", "models_dir"}
    """
    df = pd.read_csv(csv_path)
    models_dir = output_dir / "models"
    models_dir.mkdir(parents=True, exist_ok=True)

    # ---- S60 基准模型 ----
    s60_result = _train_s60_baseline(df)
    if s60_result["success"]:
        with open(models_dir / "s60_baseline.pkl", "wb") as f:
            pickle.dump({"pipeline": s60_result["model"]}, f)

    # ---- S8 限域模型 ----
    s8_result = _train_s8_confinement(df)
    if s8_result["success"]:
        with open(models_dir / "s8_confinement.pkl", "wb") as f:
            pickle.dump({"model": s8_result["model"], "feature_names": s8_result["feature_names"]}, f)

    # ---- ΔEa 统计 ----
    delta_Ea_stats = {}
    if s60_result["success"] and s8_result["success"]:
        df_s8 = df[df["material_type"] == "S8"].dropna(subset=["R", "N", "T_avg_K", "Ea_eV"]).copy()
        df_s8["N"] = df_s8["N"].fillna(df_s8["N"].mean())
        pipe = s60_result["model"]
        ea_bulk = np.array([float(pipe.predict(np.array([[r, t]]))[0])
                            for r, t in zip(df_s8["R"], df_s8["T_avg_K"])])
        delta = df_s8["Ea_eV"].values - ea_bulk
        delta_Ea_stats = {
            "mean": float(np.mean(delta)), "std": float(np.std(delta)),
            "min": float(np.min(delta)), "max": float(np.max(delta)),
        }

    # 保存 metrics
    metrics = {
        "s60": {k: v for k, v in s60_result.items() if k not in ("model", "success")} if s60_result["success"] else {},
        "s8": {k: v for k, v in s8_result.items() if k not in ("model", "feature_names", "success")} if s8_result["success"] else {},
        "delta_Ea": delta_Ea_stats,
    }
    with open(models_dir / "metrics.json", "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2, ensure_ascii=False)

    return {
        "success": s60_result["success"] and s8_result["success"],
        "s60_metrics": metrics["s60"],
        "s8_metrics": metrics["s8"],
        "delta_Ea_stats": delta_Ea_stats,
        "models_dir": str(models_dir),
    }


def _train_s60_baseline(df: pd.DataFrame, alpha: float = 5.0, outlier_std: float = 2.0) -> Dict[str, Any]:
    """S60 基准模型: Ea = f(R, T)"""
    df_s60 = df[df["material_type"] == "S60"].dropna(subset=["R", "T_avg_K", "Ea_eV"]).copy()
    if len(df_s60) < 5:
        return {"success": False, "error": "S60 数据不足"}

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
    n_removed = 0
    if res_std > 1e-10:
        mask = np.abs(residuals) <= outlier_std * res_std
        n_removed = int((~mask).sum())
        if n_removed > 0 and mask.sum() >= 5:
            X, y = X[mask], y[mask]
            pipe.fit(X, y)
            y_pred = pipe.predict(X)

    r2 = r2_score(y, y_pred)
    mae = mean_absolute_error(y, y_pred)
    cv = cross_val_score(pipe, X, y, cv=min(5, len(y)), scoring="r2")

    return {
        "success": True,
        "model": pipe,
        "n_samples": int(len(y)),
        "n_removed_outliers": n_removed,
        "r2": float(r2),
        "mae_eV": float(mae),
        "cv_r2_mean": float(cv.mean()),
        "cv_r2_std": float(cv.std()) if len(cv) > 1 else 0.0,
        "ridge_alpha": alpha,
    }


def _train_s8_confinement(df: pd.DataFrame) -> Dict[str, Any]:
    """S8 限域模型: Ea = f(R, N, T) + interactions"""
    df_s8 = df[df["material_type"] == "S8"].dropna(subset=["R", "N", "T_avg_K", "Ea_eV"]).copy()
    df_s8["N"] = df_s8["N"].fillna(df_s8["N"].mean())
    if len(df_s8) < 5:
        return {"success": False, "error": "S8 数据不足"}

    df_s8 = df_s8.copy()
    df_s8["T_N"] = df_s8["T_avg_K"] * df_s8["N"]
    df_s8["T_R"] = df_s8["T_avg_K"] * df_s8["R"]
    df_s8["R_N"] = df_s8["R"] * df_s8["N"]
    feats = S8_FEATURES
    X = df_s8[feats].values
    y = df_s8["Ea_eV"].values

    model = GradientBoostingRegressor(
        n_estimators=120, learning_rate=0.05, max_depth=3,
        min_samples_leaf=4, random_state=42,
    )
    model.fit(X, y)
    y_pred = model.predict(X)
    r2 = r2_score(y, y_pred)
    mae = mean_absolute_error(y, y_pred)
    cv = cross_val_score(model, X, y, cv=min(5, len(df_s8)), scoring="r2")

    return {
        "success": True,
        "model": model,
        "feature_names": feats,
        "n_samples": len(df_s8),
        "r2": float(r2),
        "mae_eV": float(mae),
        "cv_r2_mean": float(cv.mean()),
        "cv_r2_std": float(cv.std()) if len(cv) > 1 else 0.0,
    }


# ============================================================
# 工具 4: 限域效应分析
# ============================================================

def tool_confinement(csv_path: Path, models_dir: Path, output_dir: Path,
                     T_low: float = 230.0, T_high: float = 270.0) -> Dict[str, Any]:
    """
    限域效应分析: ΔEa = Ea(S8 实际) - Ea(S60 预测)

    Args:
        csv_path:    integrated_data.csv
        models_dir:  包含 s60_baseline.pkl 的目录
        output_dir:  输出目录
        T_low / T_high: 温区划分温度

    Returns:
        {"success", "overall", "by_temperature_zone", "ttest", "linear_fit"}
    """
    df = pd.read_csv(csv_path)
    s60_pkl = models_dir / "s60_baseline.pkl"
    if not s60_pkl.exists():
        return {"success": False, "error": "S60 模型不存在，请先运行 train_models"}

    with open(s60_pkl, "rb") as f:
        pipe = pickle.load(f)["pipeline"]

    df_s8 = df[df["material_type"] == "S8"].dropna(subset=["R", "N", "T_avg_K", "Ea_eV"]).copy()
    df_s8["N"] = df_s8["N"].fillna(df_s8["N"].mean())
    if df_s8.empty:
        return {"success": False, "error": "无 S8 数据"}

    ea_bulk = np.array([float(pipe.predict(np.array([[r, t]]))[0])
                        for r, t in zip(df_s8["R"], df_s8["T_avg_K"])])
    df_s8 = df_s8.copy()
    df_s8["Ea_bulk"] = ea_bulk
    df_s8["delta_Ea"] = df_s8["Ea_eV"] - df_s8["Ea_bulk"]

    # 保存明细
    conf_dir = output_dir / "confinement"
    conf_dir.mkdir(parents=True, exist_ok=True)
    df_s8.to_csv(conf_dir / "delta_ea_by_segment.csv", index=False, encoding="utf-8-sig")

    # 温区统计
    low_T = df_s8[df_s8["T_avg_K"] < T_low]
    mid_T = df_s8[(df_s8["T_avg_K"] >= T_low) & (df_s8["T_avg_K"] < T_high)]
    high_T = df_s8[df_s8["T_avg_K"] >= T_high]

    overall = _bootstrap_ci(df_s8["delta_Ea"].values)
    low_T_s = _bootstrap_ci(low_T["delta_Ea"].values) if len(low_T) >= 2 else _simple_stats(low_T["delta_Ea"])
    mid_T_s = _bootstrap_ci(mid_T["delta_Ea"].values) if len(mid_T) >= 2 else _simple_stats(mid_T["delta_Ea"])
    high_T_s = _bootstrap_ci(high_T["delta_Ea"].values) if len(high_T) >= 2 else _simple_stats(high_T["delta_Ea"])

    # t 检验
    ttest = None
    if len(low_T) >= 2 and len(high_T) >= 2:
        t_stat, p_val = stats.ttest_ind(low_T["delta_Ea"], high_T["delta_Ea"])
        ttest = {"t_statistic": float(t_stat), "p_value": float(p_val), "significant_005": bool(p_val < 0.05)}

    # ΔEa(T) 线性拟合 + bootstrap CI
    T_arr = df_s8["T_avg_K"].values
    dEa_arr = df_s8["delta_Ea"].values
    lr = stats.linregress(T_arr, dEa_arr)
    rng = np.random.default_rng(42)
    slopes_b, intercepts_b = [], []
    for _ in range(N_BOOTSTRAP):
        idx = rng.integers(0, len(T_arr), size=len(T_arr))
        s, i = np.polyfit(T_arr[idx], dEa_arr[idx], 1)
        slopes_b.append(s)
        intercepts_b.append(i)
    slope_ci = (float(np.percentile(slopes_b, 2.5)), float(np.percentile(slopes_b, 97.5)))
    intercept_ci = (float(np.percentile(intercepts_b, 2.5)), float(np.percentile(intercepts_b, 97.5)))

    linear_fit = {
        "slope_per_K": float(lr.slope),
        "intercept_eV": float(lr.intercept),
        "slope_ci_95": slope_ci,
        "intercept_ci_95": intercept_ci,
        "r_squared": float(lr.rvalue ** 2),
    }

    summary = {
        "overall": overall,
        "low_T_under_230K": low_T_s,
        "mid_T_230_270K": mid_T_s,
        "high_T_over_270K": high_T_s,
        "low_vs_high_T_ttest": ttest,
        "delta_Ea_vs_T_linear_fit": linear_fit,
    }
    with open(conf_dir / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    # 绘图
    _plot_confinement(df_s8, lr.slope, lr.intercept, conf_dir / "delta_ea_plot.png")

    return {"success": True, **summary}


# ============================================================
# 工具 5: Meyer-Neldel 分析
# ============================================================

def tool_meyer_neldel(csv_path: Path, output_dir: Path,
                      materials: List[str] = None) -> Dict[str, Any]:
    """
    Meyer-Neldel 补偿效应: ln(σ₀) = a + Ea / E_MN

    Args:
        csv_path:   integrated_data.csv
        output_dir: 输出目录
        materials:  要分析的材料列表，默认 ["S8", "S60"]

    Returns:
        {"success", "results": {material: {E_MN_eV, r_squared, ...}}}
    """
    if materials is None:
        materials = ["S8", "S60"]

    df = pd.read_csv(csv_path)
    df = df.dropna(subset=["Ea_eV", "ln_sigma0"])
    df = df[df["Ea_eV"] > 0]
    if df.empty:
        return {"success": False, "error": "无有效 Ea / ln_sigma0 数据"}

    mn_dir = output_dir / "meyer_neldel"
    mn_dir.mkdir(parents=True, exist_ok=True)
    results = {}

    for mat in materials:
        r = _fit_meyer_neldel(df, material=mat)
        if r:
            results[mat] = r

    # S8 按温区
    s8 = df[df["material_type"] == "S8"].copy()
    if len(s8) >= 10:
        high = s8[s8["T_avg_K"] >= 270]
        low = s8[s8["T_avg_K"] < 230]
        r_high = _fit_meyer_neldel(high, material="S8", min_points=3)
        r_low = _fit_meyer_neldel(low, material="S8", min_points=3)
        if r_high:
            results["S8_high_T"] = r_high
        if r_low:
            results["S8_low_T"] = r_low

    with open(mn_dir / "summary.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # 绘图
    _plot_meyer_neldel(df, mn_dir / "meyer_neldel_s8.png")

    return {"success": True, "results": results}


def _fit_meyer_neldel(df: pd.DataFrame, material: str = "S8", min_points: int = 5):
    """拟合 Meyer-Neldel 关系"""
    sub = df.dropna(subset=["Ea_eV", "ln_sigma0"]).copy()
    sub = sub[sub["Ea_eV"] > 0]
    if material != "all":
        sub = sub[sub["material_type"] == material]
    if len(sub) < min_points:
        return None
    x = sub["Ea_eV"].values
    y = sub["ln_sigma0"].values
    lr = stats.linregress(x, y)
    if lr.slope > 0:
        E_MN = 1.0 / lr.slope
        E_MN_se = float(lr.stderr / (lr.slope ** 2)) if lr.stderr else None
    else:
        E_MN = None
        E_MN_se = None
    return {
        "material": material,
        "n_points": len(sub),
        "slope": float(lr.slope),
        "intercept": float(lr.intercept),
        "E_MN_eV": float(E_MN) if E_MN is not None else None,
        "E_MN_se": E_MN_se,
        "r_squared": float(lr.rvalue ** 2),
        "p_value": float(lr.pvalue),
    }


# ============================================================
# 工具 6: 跨材料验证
# ============================================================

def tool_cross_material(csv_path: Path, models_dir: Path, output_dir: Path) -> Dict[str, Any]:
    """
    跨材料迁移验证: 用 S8 模型预测其他材料的 Ea

    Returns:
        {"success", "by_material": {mat: {n, mean_alpha, ...}}, "overall"}
    """
    df = pd.read_csv(csv_path)
    s8_pkl = models_dir / "s8_confinement.pkl"
    if not s8_pkl.exists():
        return {"success": False, "error": "S8 模型不存在"}

    with open(s8_pkl, "rb") as f:
        obj = pickle.load(f)
    model = obj["model"]

    other_materials = [m for m in df["material_type"].unique() if m not in ("S8", "S60")]
    if not other_materials:
        return {"success": True, "by_material": {}, "overall": {"message": "无跨材料数据"}}

    cross_dir = output_dir / "cross_material"
    cross_dir.mkdir(parents=True, exist_ok=True)

    required = ["R", "N", "T_avg_K", "Ea_eV"]
    results_by_mat = {}
    detail_rows = []

    for mat in sorted(other_materials):
        sub = df[df["material_type"] == mat].dropna(subset=required).copy()
        sub = sub[sub["Ea_eV"] > 0]
        if len(sub) < 1:
            continue
        sub["N"] = sub["N"].fillna(sub["N"].mean())
        sub_c = sub.copy()
        sub_c["T_N"] = sub_c["T_avg_K"] * sub_c["N"]
        sub_c["T_R"] = sub_c["T_avg_K"] * sub_c["R"]
        sub_c["R_N"] = sub_c["R"] * sub_c["N"]
        X = sub_c[S8_FEATURES].values
        Ea_actual = sub["Ea_eV"].values
        Ea_pred = model.predict(X)

        valid = Ea_pred > 1e-6
        if not np.any(valid):
            continue
        alpha = np.where(valid, Ea_actual / Ea_pred, np.nan)[valid]
        Ea_act_v = Ea_actual[valid]
        Ea_pr_v = Ea_pred[valid]
        mae = float(np.mean(np.abs(Ea_act_v - Ea_pr_v)))

        results_by_mat[mat] = {
            "n": int(len(alpha)),
            "mean_alpha": float(np.mean(alpha)),
            "std_alpha": float(np.std(alpha)) if len(alpha) > 1 else 0.0,
            "mae_eV": mae,
        }

        sub_v = sub[valid].reset_index(drop=True)
        for i in range(len(sub_v)):
            detail_rows.append({
                "material_type": mat,
                "sample_id": sub_v.iloc[i].get("sample_id", ""),
                "T_avg_K": sub_v.iloc[i]["T_avg_K"],
                "Ea_actual_eV": float(Ea_act_v[i]),
                "Ea_pred_eV": float(Ea_pr_v[i]),
                "alpha": float(alpha[i]),
            })

    if detail_rows:
        pd.DataFrame(detail_rows).to_csv(cross_dir / "cross_material_details.csv", index=False, encoding="utf-8")

    overall = {}
    if results_by_mat:
        all_n = sum(m["n"] for m in results_by_mat.values())
        weighted_alpha = sum(m["mean_alpha"] * m["n"] for m in results_by_mat.values()) / all_n if all_n > 0 else 0
        overall = {"n_segments": all_n, "mean_alpha_weighted": float(weighted_alpha)}

    summary = {"materials": results_by_mat, "overall": overall}
    with open(cross_dir / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    return {"success": True, "by_material": results_by_mat, "overall": overall}


# ============================================================
# 辅助函数
# ============================================================

def _bootstrap_ci(data: np.ndarray) -> Dict[str, Any]:
    """Bootstrap 95% CI for mean"""
    data = np.asarray(data).flatten()
    data = data[~np.isnan(data)]
    n = len(data)
    if n < 2:
        m = float(np.mean(data)) if n else np.nan
        return {"mean": m, "std": 0.0, "n": n, "ci_95_low": None, "ci_95_high": None}
    rng = np.random.default_rng(42)
    boot = np.array([float(np.mean(rng.choice(data, size=n, replace=True))) for _ in range(N_BOOTSTRAP)])
    return {
        "mean": float(np.mean(data)),
        "std": float(np.std(data)),
        "n": n,
        "ci_95_low": float(np.percentile(boot, 2.5)),
        "ci_95_high": float(np.percentile(boot, 97.5)),
    }


def _simple_stats(series: pd.Series) -> Dict[str, Any]:
    """简单统计（数据不足时）"""
    vals = series.dropna().values
    return {
        "mean": float(np.mean(vals)) if len(vals) else None,
        "std": float(np.std(vals)) if len(vals) > 1 else 0.0,
        "n": len(vals),
        "ci_95_low": None,
        "ci_95_high": None,
    }


def _plot_confinement(df_s8: pd.DataFrame, slope: float, intercept: float, save_path: Path):
    """绘制 ΔEa vs T 图"""
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.scatter(df_s8["T_avg_K"], df_s8["delta_Ea"], alpha=0.6, s=25, c="steelblue", edgecolors="none")
    T_line = np.linspace(df_s8["T_avg_K"].min(), df_s8["T_avg_K"].max(), 100)
    ax.plot(T_line, slope * T_line + intercept, "r-", lw=2,
            label=f"Linear: slope={slope:.4f} eV/K")
    ax.axhline(0, color="gray", ls="--", alpha=0.7)
    ax.set_xlabel("T_avg (K)", fontsize=11)
    ax.set_ylabel(r"$\Delta E_a$ = $E_a$(S8) - $E_a$(S60 pred) (eV)", fontsize=11)
    ax.set_title("Confinement Effect: ΔEa vs Temperature", fontsize=12, fontweight="bold")
    ax.legend(loc="best", fontsize=9)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close()


def _plot_meyer_neldel(df: pd.DataFrame, save_path: Path):
    """绘制 Meyer-Neldel 图"""
    s8 = df[df["material_type"] == "S8"].dropna(subset=["Ea_eV", "ln_sigma0"])
    if len(s8) < 5:
        return
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.scatter(s8["Ea_eV"], s8["ln_sigma0"], alpha=0.6, s=25, c="steelblue")
    x = s8["Ea_eV"].values
    y = s8["ln_sigma0"].values
    slope, intercept = np.polyfit(x, y, 1)
    x_line = np.linspace(x.min(), x.max(), 100)
    ax.plot(x_line, slope * x_line + intercept, "r-", lw=2,
            label=f"slope={slope:.1f}, E_MN={1/slope:.3f} eV" if slope > 0 else f"slope={slope:.1f}")
    ax.set_xlabel("Ea (eV)", fontsize=11)
    ax.set_ylabel("ln(σ₀) (S/cm)", fontsize=11)
    ax.set_title("Meyer-Neldel: ln(σ₀) vs Ea (S8)", fontsize=12, fontweight="bold")
    ax.legend(loc="best")
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close()


# ============================================================
# 工具注册表（供 Agent 使用）
# ============================================================

TOOL_REGISTRY = {
    "explore_data": {
        "function": tool_explore_data,
        "description": "探查 Phase 1 数据，返回材料分布、样品数、温度/Ea 范围，推荐分析步骤",
        "requires": [],
    },
    "prepare_data": {
        "function": tool_prepare_data,
        "description": "从 Phase 1 JSON 提取 segment 数据，生成 integrated_data.csv",
        "requires": [],
    },
    "train_models": {
        "function": tool_train_models,
        "description": "训练 S60 基准模型 (Ridge) 和 S8 限域模型 (GBR)，计算 ΔEa 统计",
        "requires": ["prepare_data"],
    },
    "confinement_analysis": {
        "function": tool_confinement,
        "description": "计算限域效应 ΔEa，按温区统计 + bootstrap CI + t 检验 + 线性拟合",
        "requires": ["train_models"],
    },
    "meyer_neldel": {
        "function": tool_meyer_neldel,
        "description": "Meyer-Neldel 补偿效应分析: ln(σ₀) vs Ea 线性拟合，计算 E_MN",
        "requires": ["prepare_data"],
    },
    "cross_material": {
        "function": tool_cross_material,
        "description": "用 S8 模型预测其他材料 Ea，计算 α = Ea_实际/Ea_预测，评估迁移性",
        "requires": ["train_models"],
    },
}
