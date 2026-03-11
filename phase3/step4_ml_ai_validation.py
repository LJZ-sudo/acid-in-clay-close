# -*- coding: utf-8 -*-
"""
Phase 3 Step 4：ML 与 AI 报告交叉验证（方案 B：区间对照）

不强调“单点最优”，改为比较 AI 推荐区间内 vs 区间外的 segments 平均 Ea，
并做统计检验（t 检验 + 可选 bootstrap）。R/N 区间优先从 S8 深度报告解析，
解析失败时使用内置 fallback。
"""

import re
import sys
import json
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

import pandas as pd
import numpy as np
from scipy import stats

CLOSE_ROOT = Path(__file__).resolve().parent.parent
PHASE3_RESULTS_DIR = CLOSE_ROOT / "output" / "phase3_results"
DATA_CSV = PHASE3_RESULTS_DIR / "integrated_data.csv"
DEEP_REPORT_PATH = CLOSE_ROOT / "output" / "deep_analysis" / "S8_deep_mechanism_analysis.md"

# 内置 fallback：仅当报告不存在或解析失败时使用
AI_OPTIMAL_FALLBACK = {
    "high_temp": {"T_note": "T>250K", "R": [0.3, 0.5], "N": [4.5, 5.5]},
    "low_temp": {"T_note": "T<200K", "R": [0.6, 0.8], "N": [3.5, 4.5]},
    "wide_range": {"R": [0.4, 0.5], "N": [4.0, 5.0]},
}


def _parse_r_n_line(line: str) -> Optional[Tuple[List[float], List[float]]]:
    """解析单行 'R = x ± dx，N = a ± da' 或 '**R = x ± dx，N = a ± da**'，返回 (R_range, N_range) 或 None。"""
    # 匹配 R = 0.35 ± 0.05，N = 4.0 ± 0.5（允许全角逗号、空格）
    m = re.search(r"R\s*=\s*([\d.]+)\s*±\s*([\d.]+)\s*[，,]\s*N\s*=\s*([\d.]+)\s*±\s*([\d.]+)", line)
    if not m:
        return None
    r_center, r_delta, n_center, n_delta = float(m.group(1)), float(m.group(2)), float(m.group(3)), float(m.group(4))
    return ([r_center - r_delta, r_center + r_delta], [n_center - n_delta, n_center + n_delta])


def parse_ai_optimal_from_report(report_path: Path) -> Optional[Dict[str, Any]]:
    """
    从 S8_deep_mechanism_analysis.md 第四部分解析高温/低温 R、N 推荐区间。
    报告格式：4.1 高温区 ... **R = 0.35 ± 0.05，N = 4.0 ± 0.5**；4.2 低温区 ... **R = 0.6 ± 0.1，N = 2.5 ± 0.5**
    返回与 AI_OPTIMAL 同结构的 dict，若解析不全则返回 None。
    """
    if not report_path.exists():
        return None
    text = report_path.read_text(encoding="utf-8")
    lines = text.split("\n")
    high_r, high_n = None, None
    low_r, low_n = None, None
    in_high = in_low = False
    for i, line in enumerate(lines):
        if "4.1" in line and "高温" in line:
            in_high, in_low = True, False
        if "4.2" in line and "低温" in line:
            in_high, in_low = False, True
        if "4.3" in line:
            in_high, in_low = False, False
        parsed = _parse_r_n_line(line)
        if parsed:
            r_range, n_range = parsed
            if in_high and high_r is None:
                high_r, high_n = r_range, n_range
            elif in_low and low_r is None:
                low_r, low_n = r_range, n_range
    if high_r is None or high_n is None or low_r is None or low_n is None:
        return None
    return {
        "high_temp": {"T_note": "T>250K", "R": high_r, "N": high_n},
        "low_temp": {"T_note": "T<200K", "R": low_r, "N": low_n},
        "wide_range": {"R": [0.4, 0.5], "N": [4.0, 5.0]},
    }


def get_ai_optimal() -> Tuple[Dict[str, Any], str]:
    """返回 (AI_OPTIMAL dict, report_source 描述)。优先从报告解析。"""
    parsed = parse_ai_optimal_from_report(DEEP_REPORT_PATH)
    if parsed is not None:
        return parsed, "S8_deep_mechanism_analysis.md（从报告第四部分解析 R/N 区间）"
    return AI_OPTIMAL_FALLBACK.copy(), "（报告不存在或解析失败，使用内置 fallback）"


def in_range(val: float, rng: List[float]) -> bool:
    return rng[0] <= val <= rng[1]


def interval_comparison(
    df_s8: pd.DataFrame,
    zone_name: str,
    t_min: float,
    t_max: float,
    r_range: List[float],
    n_range: List[float],
    n_bootstrap: int = 2000,
    ci: float = 0.95,
) -> Dict[str, Any]:
    """
    方案 B：比较 AI 推荐区间内 vs 区间外的 segments 的 mean(Ea)。
    低 Ea = 更好传导，故若 mean_Ea_in <= mean_Ea_out 则“区间内不劣于区间外”。
    """
    zone = df_s8[(df_s8["T_avg_K"] >= t_min) & (df_s8["T_avg_K"] < t_max)]
    if len(zone) < 4:
        return {"verdict": "SKIP", "reason": "该温区 segment 不足"}

    mask_in = (
        zone["R"].between(r_range[0], r_range[1]) &
        zone["N"].between(n_range[0], n_range[1])
    )
    ea_in = zone.loc[mask_in, "Ea_eV"].values
    ea_out = zone.loc[~mask_in, "Ea_eV"].values

    n_in, n_out = len(ea_in), len(ea_out)
    if n_in < 2 or n_out < 2:
        return {
            "verdict": "SKIP",
            "reason": f"区间内 n={n_in} 或区间外 n={n_out} 不足",
            "n_in": n_in,
            "n_out": n_out,
        }

    mean_in = float(np.mean(ea_in))
    mean_out = float(np.mean(ea_out))
    std_in = float(np.std(ea_in, ddof=1)) if n_in > 1 else 0.0
    std_out = float(np.std(ea_out, ddof=1)) if n_out > 1 else 0.0

    # t 检验：H0 为 mean_in == mean_out
    t_stat, p_value = stats.ttest_ind(ea_in, ea_out)
    p_value = float(p_value) if not np.isnan(p_value) else 1.0

    # Bootstrap 95% CI for mean_in - mean_out (差值)
    rng = np.random.default_rng(42)
    diff_boot = []
    for _ in range(n_bootstrap):
        s_in = rng.choice(ea_in, size=n_in, replace=True)
        s_out = rng.choice(ea_out, size=n_out, replace=True)
        diff_boot.append(np.mean(s_in) - np.mean(s_out))
    diff_boot = np.array(diff_boot)
    alpha = 1 - ci
    ci_low = float(np.percentile(diff_boot, alpha / 2 * 100))
    ci_high = float(np.percentile(diff_boot, (1 - alpha / 2) * 100))
    diff_mean = float(np.mean(ea_in) - np.mean(ea_out))

    # 判定：低 Ea 更好。若 mean_in < mean_out 则区间内更好；若差异不显著则“无显著差异”
    if p_value < 0.05:
        if diff_mean < 0:
            verdict = "IN_RANGE_BETTER"  # 区间内 Ea 更低，更好
        else:
            verdict = "OUT_RANGE_BETTER"  # 区间外更好
    else:
        verdict = "NO_SIGNIFICANT_DIFFERENCE"

    return {
        "verdict": verdict,
        "mean_Ea_in_range": mean_in,
        "mean_Ea_out_range": mean_out,
        "std_in": std_in,
        "std_out": std_out,
        "n_in": n_in,
        "n_out": n_out,
        "diff_mean": diff_mean,
        "diff_ci_95": [ci_low, ci_high],
        "t_statistic": float(t_stat) if not np.isnan(t_stat) else None,
        "p_value": p_value,
        "ai_R_range": r_range,
        "ai_N_range": n_range,
    }


def main() -> int:
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    print("=" * 60)
    print("Phase 3 Step 4：ML 与 AI 报告交叉验证（方案 B：区间对照）")
    print("=" * 60)

    if not DATA_CSV.exists():
        print("  [ERROR] 请先运行 step1")
        return 1

    df = pd.read_csv(DATA_CSV)
    df_s8 = df[df["material_type"] == "S8"].dropna(subset=["R", "N", "T_avg_K", "Ea_eV"]).copy()
    df_s8["N"] = df_s8["N"].fillna(df_s8["N"].mean())

    AI_OPTIMAL, report_source = get_ai_optimal()
    print(f"  [区间来源] {report_source}")

    validation = {
        "data_source": str(DATA_CSV),
        "report_source": report_source,
        "method": "interval_comparison",
        "ai_optimal": AI_OPTIMAL,
        "validation": {},
    }

    zones_config = [
        ("high_temp", 270, 400, AI_OPTIMAL["high_temp"]["R"], AI_OPTIMAL["high_temp"]["N"]),
        ("low_temp", 0, 230, AI_OPTIMAL["low_temp"]["R"], AI_OPTIMAL["low_temp"]["N"]),
    ]
    for zone_name, t_min, t_max, r_range, n_range in zones_config:
        validation["validation"][zone_name] = interval_comparison(
            df_s8, zone_name, t_min, t_max, r_range, n_range
        )

    out_path = PHASE3_RESULTS_DIR / "ml_ai_validation.json"
    PHASE3_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(validation, f, indent=2, ensure_ascii=False)
    print(f"  已写入 {out_path}")

    print("\n  [区间对照结果]")
    for zone, v in validation["validation"].items():
        if v.get("verdict") == "SKIP":
            print(f"    {zone}: {v.get('reason', 'SKIP')}")
        else:
            print(f"    {zone}: 区间内 mean(Ea)={v['mean_Ea_in_range']:.4f} (n={v['n_in']}), "
                  f"区间外 mean(Ea)={v['mean_Ea_out_range']:.4f} (n={v['n_out']}), "
                  f"diff_95%CI=[{v['diff_ci_95'][0]:.4f}, {v['diff_ci_95'][1]:.4f}], p={v['p_value']:.4f} -> {v['verdict']}")

    print("\n[Step 4 完成]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
