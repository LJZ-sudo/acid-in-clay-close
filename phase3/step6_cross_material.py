# -*- coding: utf-8 -*-
"""
Phase 3 Step 6：跨材料验证（P2）

用已训练的 S8 限域模型预测非 S8 材料（S6/S13/S14/S16/S95/S96/S97）的 Ea，
计算 α = Ea_实际 / Ea_预测，按材料报告 mean(α)、std(α)、n、MAE，用于讨论限域模型迁移性。
"""

import sys
import json
import pickle
from pathlib import Path
from typing import Dict, Any, List

import pandas as pd
import numpy as np

CLOSE_ROOT = Path(__file__).resolve().parent.parent
PHASE3_RESULTS_DIR = CLOSE_ROOT / "output" / "phase3_results"
MODELS_DIR = PHASE3_RESULTS_DIR / "models"
DATA_CSV = PHASE3_RESULTS_DIR / "integrated_data.csv"
CROSS_MATERIAL_DIR = PHASE3_RESULTS_DIR / "cross_material"

# S8 模型特征与训练时一致
S8_FEATURES = ["R", "N", "T_avg_K", "T_N", "T_R", "R_N"]


def load_s8_model() -> tuple:
    """加载 S8 模型与特征名。返回 (model, feature_names)。"""
    pkl_path = MODELS_DIR / "s8_confinement.pkl"
    if not pkl_path.exists():
        raise FileNotFoundError(f"S8 模型不存在: {pkl_path}，请先运行 step2_train_models.py")
    with open(pkl_path, "rb") as f:
        obj = pickle.load(f)
    model = obj["model"]
    feature_names = obj.get("feature_names", S8_FEATURES)
    return model, feature_names


def build_s8_features(df: pd.DataFrame) -> np.ndarray:
    """构建 S8 模型输入特征：R, N, T_avg_K, T_N, T_R, R_N。"""
    df = df.copy()
    df["T_N"] = df["T_avg_K"] * df["N"]
    df["T_R"] = df["T_avg_K"] * df["R"]
    df["R_N"] = df["R"] * df["N"]
    return df[S8_FEATURES].values


def main() -> int:
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    print("=" * 60)
    print("Phase 3 Step 6：跨材料验证（S8 模型迁移）")
    print("=" * 60)

    if not DATA_CSV.exists():
        print(f"  [ERROR] 请先运行 step1_data_preparation.py，生成 {DATA_CSV}")
        return 1

    df = pd.read_csv(DATA_CSV)
    model, feature_names = load_s8_model()

    # 非 S8、非 S60 的材料（限域/粘土类，有 R、N）
    other_materials = [m for m in df["material_type"].unique() if m not in ("S8", "S60")]
    if not other_materials:
        print("  无除 S8/S60 外的材料，跳过跨材料验证。")
        CROSS_MATERIAL_DIR.mkdir(parents=True, exist_ok=True)
        with open(CROSS_MATERIAL_DIR / "summary.json", "w", encoding="utf-8") as f:
            json.dump({"materials": [], "message": "无跨材料数据"}, f, indent=2, ensure_ascii=False)
        return 0

    # 每个材料：需有 R, N, T_avg_K, Ea_eV
    required = ["R", "N", "T_avg_K", "Ea_eV"]
    results_by_material: Dict[str, Dict[str, Any]] = {}
    detail_rows: List[Dict[str, Any]] = []

    for mat in sorted(other_materials):
        sub = df[df["material_type"] == mat].dropna(subset=required).copy()
        sub = sub[sub["Ea_eV"] > 0]
        if len(sub) < 1:
            continue
        # 补 N 缺失（若存在）
        sub["N"] = sub["N"].fillna(sub["N"].mean())
        X = build_s8_features(sub)
        Ea_actual = sub["Ea_eV"].values
        Ea_pred = model.predict(X)
        # 避免除零
        valid = Ea_pred > 1e-6
        if not np.any(valid):
            continue
        alpha = np.where(valid, Ea_actual / Ea_pred, np.nan)
        alpha = alpha[valid]
        Ea_act_v = Ea_actual[valid]
        Ea_pr_v = Ea_pred[valid]
        sub_v = sub[valid].reset_index(drop=True)
        mae = float(np.mean(np.abs(Ea_act_v - Ea_pr_v)))
        results_by_material[mat] = {
            "n": int(len(alpha)),
            "mean_alpha": float(np.mean(alpha)),
            "std_alpha": float(np.std(alpha)) if len(alpha) > 1 else 0.0,
            "mae_eV": mae,
            "mean_Ea_actual": float(np.mean(Ea_act_v)),
            "mean_Ea_pred": float(np.mean(Ea_pr_v)),
        }
        for i in range(len(sub_v)):
            row = sub_v.iloc[i]
            detail_rows.append({
                "material_type": mat,
                "sample_id": row.get("sample_id", ""),
                "T_avg_K": row["T_avg_K"],
                "Ea_actual_eV": Ea_act_v[i],
                "Ea_pred_eV": Ea_pr_v[i],
                "alpha": alpha[i],
            })

    CROSS_MATERIAL_DIR.mkdir(parents=True, exist_ok=True)
    summary = {
        "description": "S8 限域模型在非 S8 材料上的迁移：α = Ea_实际 / Ea_预测，α≈1 表示预测与实测接近",
        "materials": results_by_material,
        "overall": {},
    }
    if results_by_material:
        all_alpha = []
        for m in results_by_material.values():
            # 用 mean_alpha 代表该材料（若需全量可再从 detail 算）
            all_alpha.extend([m["mean_alpha"]] * m["n"])
        summary["overall"] = {
            "n_segments": sum(m["n"] for m in results_by_material.values()),
            "mean_alpha_weighted": float(np.mean(all_alpha)),
            "std_alpha_across_materials": float(np.std(list(m["mean_alpha"] for m in results_by_material.values()))) if len(results_by_material) > 1 else 0.0,
        }

    with open(CROSS_MATERIAL_DIR / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    if detail_rows:
        pd.DataFrame(detail_rows).to_csv(CROSS_MATERIAL_DIR / "cross_material_details.csv", index=False, encoding="utf-8")

    # 控制台输出
    for mat in sorted(results_by_material.keys()):
        r = results_by_material[mat]
        print(f"  {mat}: n={r['n']}, mean(α)={r['mean_alpha']:.4f}, std(α)={r['std_alpha']:.4f}, MAE={r['mae_eV']:.4f} eV")
    if summary.get("overall"):
        print(f"  整体: n_segments={summary['overall']['n_segments']}, mean_alpha(加权)={summary['overall']['mean_alpha_weighted']:.4f}")

    print(f"\n  已保存 -> {CROSS_MATERIAL_DIR / 'summary.json'}, {CROSS_MATERIAL_DIR / 'cross_material_details.csv'}")
    print("\n[Step 6 完成]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
