# -*- coding: utf-8 -*-
"""E1 — 线 B「直接复现地板」分析（凹凸棒土同配方回溯重复）。

输入：三批 R=0.186/N=1.029 宽温 EIS 经 Stage0 离线管线产出的 aggregated_results.json
      （由 stage0_measurement/run_offline.py 生成）。
做两件事：
  1. 复用 stage0_measurement/modules/io_utils/result_bundle.py 的 build_bundle_for_sample
     为每批产出 canonical 的 stage0_result_bundle.json（含 R/N/几何/eis_points/SHA）。
  2. 把每批 log10(sigma) 插值到公共温度网格，两两批次算 |Δlog10σ|，
     分 warm(≥ -20°C)/cold(< -20°C) 报中位与 p90 → 写 LINE_B_LOCAL_DIRECT.json。

诚实边界：这是回溯复现地板（噪声刻画），不声称结构/因果/前瞻发现（EIS-only 硬封顶 C4）。
legacy 零改动：本脚本只读 Stage0 产物 + 调用既有 bundle 聚合函数，不改任何 legacy 算法。
"""
from __future__ import annotations

import json
import math
import shutil
import statistics
import sys
from itertools import combinations
from pathlib import Path
from typing import Dict, List, Optional, Tuple

REPO = next(_p for _p in Path(__file__).resolve().parents if _p.name == "research").parent
STAGE0 = REPO / "V1.0-qianduan-mainline" / "stage0_measurement"
sys.path.insert(0, str(STAGE0))
from modules.io_utils.result_bundle import build_bundle_for_sample, write_bundle  # noqa: E402

OUT = REPO / "V1.0-qianduan-mainline" / "output" / "e1_floor"
BUNDLE_ROOT = REPO / "V1.0-qianduan-mainline" / "output" / "stage0_results"
WARM_CUT_C = -20.0  # warm: T_C >= -20; cold: T_C < -20

# 三批回溯重复（同配方 R=0.186/N=1.029），几何取自各批 材料制备.txt
BATCHES = [
    {"key": "A", "sample_id": "ATP-R0.186-N1.029-batchA-0624",
     "agg_dir": OUT / "batchA_0624-2", "R": 0.186, "N": 1.029, "L_cm": 0.0712, "S_cm2": 1.96,
     "src_folder": r"E:\\固态电解质\\2026.6.24-2"},
    {"key": "B", "sample_id": "ATP-R0.186-N1.029-batchB-0625",
     "agg_dir": OUT / "batchB_0625-3", "R": 0.186, "N": 1.029, "L_cm": 0.0654, "S_cm2": 1.96,
     "src_folder": r"E:\\固态电解质\\2026.6.25-3"},
    {"key": "C", "sample_id": "ATP-R0.186-N1.029-batchC-0626",
     "agg_dir": OUT / "batchC_0626-1", "R": 0.186, "N": 1.029, "L_cm": 0.0564, "S_cm2": 1.96,
     "src_folder": r"E:\\固态电解质\\2026.6.26-1"},
]


def build_bundle(b: dict) -> Path:
    """复用 canonical bundle 聚合器：把单批 run_offline 产物放进 <sample>/scan_main/ 后聚合。"""
    sample_dir = BUNDLE_ROOT / b["sample_id"]
    scan_dir = sample_dir / "scan_main"
    scan_dir.mkdir(parents=True, exist_ok=True)
    for fn in ("aggregated_results.json", "arrhenius_analysis.json", "eis_features.json"):
        src = b["agg_dir"] / fn
        if src.exists():
            shutil.copy2(src, scan_dir / fn)
    bundle = build_bundle_for_sample(
        sample_dir, b["sample_id"],
        rn_info={"R": b["R"], "N": b["N"], "L_cm": b["L_cm"], "S_cm2": b["S_cm2"]},
    )
    return write_bundle(bundle, sample_dir)


def load_sigma_curve(agg_dir: Path) -> List[Tuple[float, float]]:
    """返回 [(T_C, sigma_S_cm)] 仅取 status==OK 且 sigma>0 的点，按 T_C 升序。"""
    agg = json.loads((agg_dir / "aggregated_results.json").read_text(encoding="utf-8"))
    pts: Dict[float, float] = {}
    for m in agg.get("measurements") or []:
        if str(m.get("status")) != "OK" or not m.get("success", True):
            continue
        t = m.get("temperature_C")
        s = m.get("conductivity_S_per_cm")
        if t is None or s is None or s <= 0:
            continue
        pts[round(float(t), 3)] = float(s)  # 同温重测取后者
    return sorted(pts.items())


def interp_log10(curve: List[Tuple[float, float]], grid: List[float]) -> Dict[float, Optional[float]]:
    """线性插值 log10(sigma) vs T_C 到给定网格；网格点超出该批量程则记 None（不外推）。"""
    xs = [t for t, _ in curve]
    ys = [math.log10(s) for _, s in curve]
    out: Dict[float, Optional[float]] = {}
    for g in grid:
        if g < xs[0] or g > xs[-1]:
            out[g] = None
            continue
        # 找区间线性插值
        for i in range(len(xs) - 1):
            if xs[i] <= g <= xs[i + 1]:
                x0, x1, y0, y1 = xs[i], xs[i + 1], ys[i], ys[i + 1]
                out[g] = y0 if x1 == x0 else y0 + (y1 - y0) * (g - x0) / (x1 - x0)
                break
    return out


def summarize(vals: List[float]) -> Dict[str, float]:
    if not vals:
        return {"n": 0}
    s = sorted(vals)
    def pct(p):
        if len(s) == 1:
            return s[0]
        k = p * (len(s) - 1)
        lo = int(math.floor(k)); hi = int(math.ceil(k))
        return s[lo] + (s[hi] - s[lo]) * (k - lo)
    return {
        "n": len(s),
        "median": statistics.median(s),
        "p90": pct(0.90),
        "max": s[-1],
        "mean": statistics.fmean(s),
    }


def main() -> int:
    # 1) 产 canonical bundles
    bundle_paths = {}
    for b in BATCHES:
        bp = build_bundle(b)
        bundle_paths[b["key"]] = str(bp)
        print(f"[bundle] {b['key']} -> {bp}")

    # 2) 载入三批 sigma 曲线
    curves = {b["key"]: load_sigma_curve(b["agg_dir"]) for b in BATCHES}
    for k, c in curves.items():
        print(f"[curve] batch {k}: {len(c)} OK points, T range {c[0][0]}..{c[-1][0]} C")

    # 公共温度网格：各批量程交集，步长 3°C
    lo = max(c[0][0] for c in curves.values())
    hi = min(c[-1][0] for c in curves.values())
    grid = [round(lo + 3 * i, 3) for i in range(int((hi - lo) // 3) + 1)]
    interp = {k: interp_log10(c, grid) for k, c in curves.items()}

    # 3) 两两批次 |Δlog10σ|
    warm_diffs: List[float] = []
    cold_diffs: List[float] = []
    per_grid = []
    for g in grid:
        row = {"T_C": g}
        pair_d = []
        for k1, k2 in combinations(curves.keys(), 2):
            v1, v2 = interp[k1][g], interp[k2][g]
            if v1 is None or v2 is None:
                continue
            d = abs(v1 - v2)
            pair_d.append({"pair": f"{k1}-{k2}", "abs_dlog10": d})
            (warm_diffs if g >= WARM_CUT_C else cold_diffs).append(d)
        row["pairs"] = pair_d
        per_grid.append(row)

    floor = {
        "id": "LINE_B_LOCAL_DIRECT",
        "supersedes": "CROSS_SYSTEM_PROXY (biopolymer LRS proxy, 0.262 dex)",
        "nature": "retrospective same-recipe reproducibility floor (EIS-only, C4 cap)",
        "recipe": {"R": 0.186, "N": 1.029},
        "n_independent_pellets": len(BATCHES),
        "batches": [{"key": b["key"], "sample_id": b["sample_id"], "L_cm": b["L_cm"],
                     "S_cm2": b["S_cm2"], "src_folder": b["src_folder"]} for b in BATCHES],
        "warm_cut_C": WARM_CUT_C,
        "grid_C": [grid[0], grid[-1], 3],
        "metric": "pairwise |Δlog10(sigma)| at matched (interpolated) temperatures",
        "warm": summarize(warm_diffs),
        "cold": summarize(cold_diffs),
        "bundle_paths": bundle_paths,
    }
    out_path = OUT / "LINE_B_LOCAL_DIRECT.json"
    out_path.write_text(json.dumps({"floor": floor, "per_grid": per_grid}, indent=2, ensure_ascii=False),
                        encoding="utf-8")

    print("\n===== LINE_B_LOCAL_DIRECT (直接复现地板) =====")
    print(f"  独立重复片数: {floor['n_independent_pellets']}  配方 R=0.186/N=1.029")
    print(f"  公共温度网格: {grid[0]}..{grid[-1]} C, step 3")
    w, c = floor["warm"], floor["cold"]
    print(f"  WARM (T>= {WARM_CUT_C}C): n={w['n']} median|Δlog10σ|={w.get('median',float('nan')):.4f} p90={w.get('p90',float('nan')):.4f} dex")
    print(f"  COLD (T<  {WARM_CUT_C}C): n={c['n']} median|Δlog10σ|={c.get('median',float('nan')):.4f} p90={c.get('p90',float('nan')):.4f} dex")
    print(f"  vs 代理地板 0.262 dex（生物聚合物 LRS）")
    print(f"  写出: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
