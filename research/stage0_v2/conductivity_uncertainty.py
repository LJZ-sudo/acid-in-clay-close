# -*- coding: utf-8 -*-
"""M2-2 — Stage0 电导率带不确定度输出 + combined_score 分布。

把"单值 σ"升级为 `ConductivityEstimate`:
  log10σ = log10(t) - log10(Rb) - log10(A)
  Var(log10σ) = Var(log10 t) + Var(log10 Rb) + Var(log10 A)
其中:
  - Var(log10 Rb) 用 M1-1 可信集方法间方差(真实、已算;可选叠加频率子采样 bootstrap);
  - 几何(t, A)不确定度:本数据集未携带 → 诚实标 UNKNOWN,**不默认 0**;
    故 uncertainty_scope = RB_AND_METHOD(只含 Rb+方法,不含几何)。
combined_score 经 Monte Carlo 把 log10σ_room 与 Ea 不确定度一起传播成分布。
绝不改 legacy;输出 *_v2。
"""
from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from . import versions as V
from . import raw_loader as rl

sys.path.insert(0, str(V.MAINLINE_ROOT / "stage0_measurement"))
from modules.analysis.algorithms.rb_fitting import fit_all_rb_methods, get_default_fit_params  # noqa: E402

# Ea 地板(eV):来自 M2-1 BETWEEN_SPECIMEN ea_high sd;作为 combined_score MC 的 Ea 不确定度
EA_HIGH_FLOOR_SD_EV = 0.019


@dataclass
class ConductivityEstimate:
    temperature_C: Optional[float]
    temperature_K: Optional[float]
    log10_sigma_mean: Optional[float]
    log10_sigma_sd: Optional[float]
    ci95: Optional[List[float]]
    variance_components: Dict[str, Any] = field(default_factory=dict)
    method: str = "method_ensemble"
    uncertainty_scope: str = "RB_AND_METHOD"   # RB_ONLY|RB_AND_METHOD|TOTAL_KNOWN|PARTIAL

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _geom_ratio(points: List[Dict[str, Any]]) -> float:
    vals = [p["conductivity_legacy"] * p["rb_ohm_legacy"] for p in points
            if p.get("conductivity_legacy") and p.get("rb_ohm_legacy")]
    return float(np.median(vals)) if vals else 1.0


def estimate_point(point: Dict[str, Any], geom_ratio: float) -> ConductivityEstimate:
    """单温点 ConductivityEstimate(几何 UNKNOWN → 只传 Rb+方法不确定度)。"""
    fp = get_default_fit_params()
    res = fit_all_rb_methods(point["freq"], point["z_real"], point["z_imag"],
                             thickness_cm=geom_ratio, area_cm2=1.0,
                             temperature_K=point["temperature_K"], fit_params=fp)
    ens = res.get("ensemble", {})
    log10_rb = ens.get("log10_rb")
    spread = ens.get("method_spread_dex")  # 可信集方法间 sd(dex)= Var(log10 Rb)^0.5
    if log10_rb is None:
        return ConductivityEstimate(
            temperature_C=point.get("temperature_C"), temperature_K=point.get("temperature_K"),
            log10_sigma_mean=None, log10_sigma_sd=None, ci95=None,
            variance_components={"reason": "no applicable Rb method"},
            uncertainty_scope="PARTIAL")
    # log10σ = log10(t/A) - log10(Rb);t/A 视为已知常数(其不确定度 UNKNOWN,不计入)
    log10_sigma = math.log10(geom_ratio) - log10_rb
    var_rb = float(spread) ** 2 if spread is not None else 0.0
    sd = math.sqrt(var_rb)
    ci = [log10_sigma - 1.96 * sd, log10_sigma + 1.96 * sd] if sd > 0 else [log10_sigma, log10_sigma]
    return ConductivityEstimate(
        temperature_C=point.get("temperature_C"),
        temperature_K=point.get("temperature_K"),
        log10_sigma_mean=float(log10_sigma),
        log10_sigma_sd=float(sd),
        ci95=[float(ci[0]), float(ci[1])],
        variance_components={
            "var_log10_rb_method": var_rb,
            "var_log10_thickness": "UNKNOWN",
            "var_log10_area": "UNKNOWN",
            "n_credible_methods": ens.get("n_credible"),
        },
        uncertainty_scope="RB_AND_METHOD",
    )


def _room_temp_estimate(estimates: List[ConductivityEstimate]) -> Optional[ConductivityEstimate]:
    cand = [e for e in estimates if e.temperature_C is not None and e.log10_sigma_mean is not None]
    if not cand:
        return None
    return min(cand, key=lambda e: abs(e.temperature_C - 25.0))


def combined_score_distribution(
    log10_sigma_room_mean: float, log10_sigma_room_sd: float,
    ea_high_mean: float, ea_low_excess_mean: float,
    ea_high_sd: float = EA_HIGH_FLOOR_SD_EV, n_mc: int = 20000, seed: int = 20260622,
) -> Dict[str, Any]:
    """combined_score = log10σ - 3·Ea_high - 0.5·ea_low_excess,MC 传播不确定度。

    ea_low_excess 的不确定度用 ea_high_sd 近似(同量级),保守。
    """
    rng = np.random.default_rng(seed)
    s = rng.normal(log10_sigma_room_mean, max(log10_sigma_room_sd, 1e-9), n_mc)
    eh = rng.normal(ea_high_mean, max(ea_high_sd, 1e-9), n_mc)
    ex = np.clip(rng.normal(ea_low_excess_mean, max(ea_high_sd, 1e-9), n_mc), 0.0, None)
    cs = s - 3.0 * eh - 0.5 * ex
    return {
        "combined_score_mean": float(np.mean(cs)),
        "combined_score_sd": float(np.std(cs)),
        "combined_score_ci95": [float(np.percentile(cs, 2.5)), float(np.percentile(cs, 97.5))],
        "n_mc": n_mc,
        "inputs": {
            "log10_sigma_room_mean": log10_sigma_room_mean,
            "log10_sigma_room_sd": log10_sigma_room_sd,
            "ea_high_mean": ea_high_mean, "ea_high_sd": ea_high_sd,
            "ea_low_excess_mean": ea_low_excess_mean,
        },
    }


def _ea_from_arrhenius(ds_dir: Path) -> Tuple[Optional[float], Optional[float]]:
    fp = ds_dir / "arrhenius_analysis.json"
    if not fp.exists():
        return None, None
    d = json.loads(fp.read_text(encoding="utf-8"))
    segs = d.get("segments") or []
    if not segs:
        return None, None
    def t_hi(s):
        tr = s.get("temp_range_K") or [0, 0]
        return tr[1] if len(tr) >= 2 else 0
    def t_lo(s):
        tr = s.get("temp_range_K") or [0, 0]
        return tr[0] if len(tr) >= 1 else 0
    ea_high = max(segs, key=t_hi).get("Ea_eV")
    ea_low = min(segs, key=t_lo).get("Ea_eV")
    if ea_high is None:
        return None, None
    excess = max(0.0, (ea_low or 0.0) - 1.5 * ea_high)
    return float(ea_high), float(excess)


def assess_dataset(ds_dir: Path) -> Dict[str, Any]:
    pts = rl.load_dataset_points(ds_dir / "aggregated_results.json")
    pts = [p for p in pts if p.get("success_legacy") and p.get("conductivity_legacy", 0) > 0]
    geom = _geom_ratio(pts)
    estimates = [estimate_point(p, geom) for p in pts]
    room = _room_temp_estimate(estimates)

    cs_dist = None
    if room and room.log10_sigma_sd is not None:
        ea_high, excess = _ea_from_arrhenius(ds_dir)
        if ea_high is not None:
            cs_dist = combined_score_distribution(
                room.log10_sigma_mean, room.log10_sigma_sd, ea_high, excess)

    return {
        "dataset": ds_dir.name,
        "provenance": V.make_provenance({"geom_ratio_t_over_A": geom,
                                         "geometry_uncertainty_status": "UNKNOWN"}),
        "n_points": len(estimates),
        "room_temp_estimate": room.to_dict() if room else None,
        "combined_score_distribution": cs_dist,
        "points": [e.to_dict() for e in estimates],
    }


def run(kind: str = "lineA", out_subdir: str = "conductivity_uncertainty") -> Dict[str, Any]:
    out_dir = V.NDA_ROOT / out_subdir
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    datasets = rl.discover_datasets(kind)
    for ds in datasets:
        res = assess_dataset(ds)
        (out_dir / f"{ds.name}_uncertainty_v2.json").write_text(
            json.dumps(res, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        room = res.get("room_temp_estimate")
        cs = res.get("combined_score_distribution")
        rows.append({
            "dataset": res["dataset"],
            "n_points": res["n_points"],
            "room_log10_sigma_mean": room.get("log10_sigma_mean") if room else None,
            "room_log10_sigma_sd": room.get("log10_sigma_sd") if room else None,
            "combined_score_mean": cs.get("combined_score_mean") if cs else None,
            "combined_score_sd": cs.get("combined_score_sd") if cs else None,
        })
    summary = {"provenance": V.make_provenance({"kind": kind, "geometry_uncertainty": "UNKNOWN"}),
               "n_datasets": len(datasets), "datasets": rows}
    (out_dir / "conductivity_uncertainty_summary_v2.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return summary


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="M2-2 Stage0 带不确定度输出")
    ap.add_argument("--kind", default="lineA")
    args = ap.parse_args()
    s = run(kind=args.kind)
    for r in s["datasets"]:
        print(f"  {r['dataset']:24s} n={r['n_points']:2d} "
              f"log10σ_room={r['room_log10_sigma_mean']}±{r['room_log10_sigma_sd']} "
              f"cs={r['combined_score_mean']}±{r['combined_score_sd']}")
