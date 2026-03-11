# -*- coding: utf-8 -*-
"""
Phase 3 Step 1：从 close/output/phase1_results 提取 segment 级数据

仅读取 close 内的 phase1 结果，输出 integrated_data.csv 供 step2 使用。
"""

import sys
import json
from pathlib import Path
from typing import List, Dict, Any

import pandas as pd
import numpy as np

# close 根目录
CLOSE_ROOT = Path(__file__).resolve().parent.parent
PHASE1_RESULTS_DIR = CLOSE_ROOT / "output" / "phase1_results"
PHASE3_RESULTS_DIR = CLOSE_ROOT / "output" / "phase3_results"


def load_phase1_results() -> List[Dict[str, Any]]:
    """加载所有 phase1 的 analysis_result.json（仅 close 内）"""
    if not PHASE1_RESULTS_DIR.exists():
        raise FileNotFoundError(f"Phase1 结果目录不存在: {PHASE1_RESULTS_DIR}")

    results = []
    for path in sorted(PHASE1_RESULTS_DIR.glob("*_analysis_result.json")):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            results.append(data)
        except Exception as e:
            print(f"  [WARN] 跳过 {path.name}: {e}")
    return results


def _fallback_whole_range_segment(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """当 arrhenius.segments 为空时，用全温区 T 与 conductivity 做单段 Arrhenius 拟合，生成 1 行（便于 S15 等进入跨材料验证）。"""
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
    # ln(sigma) = ln(sigma0) - Ea/(kB*T)  =>  slope = -Ea/kB, Ea = -slope * kB
    kB_eV = 8.617333e-5
    coeffs = np.polyfit(inv_T, ln_sigma, 1)
    slope = coeffs[0]
    Ea_eV = -slope * kB_eV
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


def extract_segment_rows(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """从单份 analysis_result 提取 segment 级行"""
    sample_id = data.get("sample_id", "unknown")
    material_type = data.get("material_type", "")
    R = data.get("R")
    N = data.get("N")
    arrhenius = data.get("arrhenius") or {}
    segments = arrhenius.get("segments") or []

    if not segments:
        # 无分段时用全温区 fallback（如 S15 等），便于跨材料验证
        return _fallback_whole_range_segment(data)

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


def main():
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    print("=" * 60)
    print("Phase 3 Step 1：数据准备（仅 close/output/phase1_results）")
    print("=" * 60)
    print(f"  输入: {PHASE1_RESULTS_DIR}")
    print(f"  输出: {PHASE3_RESULTS_DIR}")

    all_data = load_phase1_results()
    print(f"\n  加载 {len(all_data)} 个 analysis_result.json")

    all_rows = []
    for data in all_data:
        rows = extract_segment_rows(data)
        all_rows.extend(rows)

    df = pd.DataFrame(all_rows)
    if df.empty:
        print("  [ERROR] 没有提取到任何 segment 数据")
        return 1

    # 过滤无效行
    df = df.dropna(subset=["Ea_eV", "T_avg_K"])
    df = df[df["Ea_eV"] > 0]
    df = df[df["T_avg_K"] > 0]

    PHASE3_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_csv = PHASE3_RESULTS_DIR / "integrated_data.csv"
    df.to_csv(out_csv, index=False, encoding="utf-8-sig")
    print(f"  已写入 {len(df)} 行 -> {out_csv}")

    # 按材料统计
    for mat in sorted(df["material_type"].unique()):
        n = len(df[df["material_type"] == mat])
        n_samp = df[df["material_type"] == mat]["sample_id"].nunique()
        print(f"    {mat}: {n} segments, {n_samp} samples")

    print("\n[Step 1 完成]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
