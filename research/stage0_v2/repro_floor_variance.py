# -*- coding: utf-8 -*-
"""M2-1 / G8 — 复现地板:从一个数字 → 带 scope 的层级方差模型 + 概率化可区分性。

把 0.245–0.32 dex 这种"混合方差单数"拆成有适用域(scope)的方差:
  - BETWEEN_SPECIMEN: LRS 独立膜片间的 room-T log10σ 散布(全体重复)
  - CROSS_BATCH: 4月薄片(~0.02cm) vs 6月标准化(~0.07cm)的批次/厚度敏感性
  - CROSS_SYSTEM_PROXY: 上述 LRS 地板作为凹凸棒土(线B)的代理,显式标注

并把"候选差 < 地板"的二值判定改成概率 `P(|Δ| > δ_meaningful)`。
绝不改 legacy;输出 *_v2。纯统计(无 pwlf)。
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from . import versions as V

# LRS 独立重复分组(同一藕粉材料、多次独立压片/测量)
LRS_ALL = [
    "lineA_LRS_0429CS", "lineA_LRS_0509CS", "lineA_LRS_6.12", "lineA_LRS_6.15_merged",
    "lineA_LRS_0615_s2", "lineA_LRS_0616_s3", "lineA_LRS_0617_s3b",
]
LRS_APRIL_THIN = ["lineA_LRS_0429CS", "lineA_LRS_0509CS"]      # ~0.02cm 薄片
LRS_JUNE_STD = ["lineA_LRS_6.12", "lineA_LRS_6.15_merged",
                "lineA_LRS_0615_s2", "lineA_LRS_0616_s3", "lineA_LRS_0617_s3b"]  # ~0.07cm


def _room_temp_log10_sigma(aggregated_json: Path, target_C: float = 25.0,
                           tol_C: float = 15.0) -> Optional[float]:
    data = json.loads(aggregated_json.read_text(encoding="utf-8"))
    best = None; best_d = 1e9
    for m in data.get("measurements", []) or []:
        if not m.get("success"):
            continue
        tc = m.get("temperature_C"); sg = m.get("conductivity_S_per_cm")
        if tc is None or sg is None or sg <= 0:
            continue
        d = abs(tc - target_C)
        if d < best_d:
            best_d = d; best = sg
    if best is None or best_d > tol_C:
        return None
    return math.log10(best)


def _ea_high(ds_dir: Path) -> Optional[float]:
    fp = ds_dir / "arrhenius_analysis.json"
    if not fp.exists():
        return None
    d = json.loads(fp.read_text(encoding="utf-8"))
    segs = d.get("segments") or []
    if not segs:
        return None
    # 主导段 = temp_range 上界最高
    def t_hi(s):
        tr = s.get("temp_range_K") or [0, 0]
        return tr[1] if len(tr) >= 2 else 0
    dom = max(segs, key=t_hi)
    ea = dom.get("Ea_eV")
    return float(ea) if ea is not None else None


def _collect(names: List[str]) -> Dict[str, Dict[str, Optional[float]]]:
    out = {}
    for n in names:
        ds = V.NDA_ROOT / n
        agg = ds / "aggregated_results.json"
        if not agg.exists():
            continue
        out[n] = {
            "log10_sigma_room": _room_temp_log10_sigma(agg),
            "ea_high_eV": _ea_high(ds),
        }
    return out


def _sd_with_ci(values: List[float], n_boot: int = 2000, seed: int = 20260622
                ) -> Dict[str, Any]:
    vals = np.array([v for v in values if v is not None], float)
    if len(vals) < 2:
        return {"n": int(len(vals)), "sd": None, "ci95": None, "mean": None}
    rng = np.random.default_rng(seed)
    boot = [float(np.std(rng.choice(vals, size=len(vals), replace=True), ddof=1))
            for _ in range(n_boot)]
    return {
        "n": int(len(vals)),
        "mean": float(np.mean(vals)),
        "sd": float(np.std(vals, ddof=1)),
        "ci95": [float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))],
    }


def _floor_entry(metric_id: str, scope: str, values: List[float],
                 datasets: List[str], applicable_materials: List[str]) -> Dict[str, Any]:
    stat = _sd_with_ci(values)
    return {
        "metric_id": metric_id,
        "scope": scope,
        "sd_dex": stat["sd"],
        "ci95": stat["ci95"],
        "mean": stat["mean"],
        "n": stat["n"],
        "source_datasets": datasets,
        "applicable_materials": applicable_materials,
    }


def prob_meaningful_difference(delta: float, floor_sd: float,
                               delta_meaningful: Optional[float] = None) -> Dict[str, float]:
    """把"差 < 地板"二值判定 → 概率。

    模型:真实差 Δ ~ N(observed_delta, scale),scale = sqrt(2)·floor_sd(两独立片之差)。
    δ_meaningful 是"实际有意义的最小差"(默认取地板 sd 本身:小于单片复现散布就不算有意义)。
      - P(|Δ| > δ_meaningful): 候选确有意义优于/劣于的概率
      - P(|Δ| ≤ δ_meaningful): 与地板不可区分(诚实 null 的概率版)
    """
    from math import erf, sqrt
    scale = math.sqrt(2.0) * floor_sd if floor_sd and floor_sd > 0 else 1e-9
    if delta_meaningful is None:
        delta_meaningful = float(floor_sd)

    def _cdf(z):
        return 0.5 * (1 + erf(z / sqrt(2)))

    # P(|Δ| < δ_m) with Δ ~ N(delta, scale)
    p_within = _cdf((delta_meaningful - delta) / scale) - _cdf((-delta_meaningful - delta) / scale)
    p_within = max(0.0, min(1.0, p_within))
    return {
        "observed_delta": float(delta),
        "floor_sd_dex": float(floor_sd),
        "diff_scale_dex": float(scale),
        "delta_meaningful": float(delta_meaningful),
        "p_abs_delta_gt_meaningful": float(1.0 - p_within),
        "p_indistinguishable": float(p_within),
    }


def run(out_subdir: str = "repro_floor_v2") -> Dict[str, Any]:
    out_dir = V.NDA_ROOT / out_subdir
    out_dir.mkdir(parents=True, exist_ok=True)

    allv = _collect(LRS_ALL)
    april = _collect(LRS_APRIL_THIN)
    june = _collect(LRS_JUNE_STD)

    def vals(coll, key):
        return [d[key] for d in coll.values() if d.get(key) is not None]

    floors: List[Dict[str, Any]] = []
    for metric in ("log10_sigma_room", "ea_high_eV"):
        floors.append(_floor_entry(metric, "BETWEEN_SPECIMEN", vals(allv, metric),
                                   list(allv.keys()), ["LRS"]))
        floors.append(_floor_entry(metric, "BETWEEN_SPECIMEN_JUNE_STD", vals(june, metric),
                                   list(june.keys()), ["LRS"]))
        floors.append(_floor_entry(metric, "BETWEEN_SPECIMEN_APRIL_THIN", vals(april, metric),
                                   list(april.keys()), ["LRS"]))

    # CROSS_BATCH:4月 vs 6月 room-T log10σ 均值差(批次/厚度敏感性)
    a_mean = np.mean(vals(april, "log10_sigma_room")) if vals(april, "log10_sigma_room") else None
    j_mean = np.mean(vals(june, "log10_sigma_room")) if vals(june, "log10_sigma_room") else None
    cross_batch = {
        "metric_id": "log10_sigma_room",
        "scope": "CROSS_BATCH",
        "april_thin_mean": float(a_mean) if a_mean is not None else None,
        "june_std_mean": float(j_mean) if j_mean is not None else None,
        "batch_mean_diff_dex": float(j_mean - a_mean) if (a_mean is not None and j_mean is not None) else None,
        "note": "4月薄片(~0.02cm) vs 6月标准化(~0.07cm);差异含厚度/接触/几何混杂",
    }

    # 线B 代理地板:用 BETWEEN_SPECIMEN(全体)的 log10σ SD 作为凹凸棒土代理(显式标注)
    between_all = next(f for f in floors
                       if f["metric_id"] == "log10_sigma_room" and f["scope"] == "BETWEEN_SPECIMEN")
    proxy = dict(between_all)
    proxy["scope"] = "CROSS_SYSTEM_PROXY"
    proxy["applicable_materials"] = ["attapulgite(line B) — PROXY from LRS"]
    proxy["caveat"] = "LRS 地板代理凹凸棒土;G1 实测后应替换为 LINE_B_LOCAL_DIRECT"

    # 概率化可区分性示例:线B top-2 combined_score 差(从 history 读)
    prob_demo = _line_b_top2_probability(between_all.get("sd_dex"))

    result = {
        "provenance": V.make_provenance(),
        "floors": floors + [cross_batch, proxy],
        "line_b_distinguishability_demo": prob_demo,
        "per_dataset": {"all": allv, "april_thin": april, "june_std": june},
    }
    (out_dir / "repro_floor_variance_v2.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def _line_b_top2_probability(floor_sd_log10sigma: Optional[float]) -> Dict[str, Any]:
    """读线B history,取 combined_score top-2,用 room-T log10σ 地板近似传播到
    combined_score 尺度,给出 top-2 是否可区分的概率(示例)。"""
    hist = (V.MAINLINE_ROOT / "stage1_optimization" / "campaign_memory"
            / "history_db_attapulgite.json")
    if not hist.exists() or floor_sd_log10sigma is None:
        return {"available": False}
    trials = json.loads(hist.read_text(encoding="utf-8-sig"))["trials"]
    cs = sorted([t["objectives"].get("combined_score") for t in trials
                 if t["objectives"].get("combined_score") is not None], reverse=True)
    if len(cs) < 2:
        return {"available": False}
    delta = cs[0] - cs[1]
    # combined_score = log10σ - 3·Ea_high - 0.5·excess;此处保守只用 log10σ 地板传播
    # (Ea 项的地板会进一步放大 scale,使"可区分"更难,故这是乐观下界)
    # δ_meaningful 取 log10σ 地板 sd(小于单片复现散布即视为不可区分)
    prob = prob_meaningful_difference(delta, floor_sd_log10sigma, delta_meaningful=None)
    return {
        "available": True,
        "top1_combined_score": cs[0],
        "top2_combined_score": cs[1],
        "delta": delta,
        "floor_basis": "log10_sigma_room BETWEEN_SPECIMEN sd (lower-bound; Ea floor would widen)",
        **prob,
    }


if __name__ == "__main__":
    r = run()
    print("Reproducibility floors (v2, scoped):")
    for f in r["floors"]:
        if "sd_dex" in f:
            print(f"  {f['metric_id']:18s} [{f['scope']:28s}] n={f['n']} "
                  f"sd={f['sd_dex']} ci95={f.get('ci95')}")
        else:
            print(f"  {f['metric_id']:18s} [{f['scope']:28s}] {f.get('batch_mean_diff_dex')}")
    d = r["line_b_distinguishability_demo"]
    if d.get("available"):
        print(f"\nLine-B top-2 combined_score Δ={d['delta']:.3f} "
              f"P(indistinguishable)={d['p_indistinguishable']:.2f}")
