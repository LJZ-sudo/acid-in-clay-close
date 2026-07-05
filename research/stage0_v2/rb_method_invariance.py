# -*- coding: utf-8 -*-
"""M1-1 / G2 — Rb 方法不变性。

对每个 lineA 数据集:
  1. 逐温点跑 `fit_all_rb_methods`(四法并行 + 方法间一致性 + 频率子采样 bootstrap SD);
  2. 构造 4 条固定策略轨迹:legacy_routed / fixed_plateau / fixed_zero_crossing / method_ensemble;
  3. 每条轨迹跑 Arrhenius(analyze_arrhenius)→ 看"转变(分段/断点)"是否方法不变;
  4. 给出 routing_artifact_risk(low/medium/high)与方法不变性门结论。

目的:证明所谓"亚零度传输转变"不是 legacy 温区方法切换造成的算法伪影。
绝不改写 legacy 产物;输出一律 *_v2 + delta_report。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from . import versions as V
from . import raw_loader as rl

sys.path.insert(0, str(V.MAINLINE_ROOT / "stage0_measurement"))
from modules.analysis.algorithms.rb_fitting import (  # noqa: E402
    fit_all_rb_methods, get_default_fit_params,
    _preprocess_and_analyze, _method_reverse_zero_crossing,
    _method_reverse_valley, _method_low_freq_plateau, _method_equivalent_circuit,
)
from modules.analysis.algorithms.arrhenius import analyze_arrhenius  # noqa: E402

_POLICY = None


def _policy() -> Dict[str, Any]:
    global _POLICY
    if _POLICY is None:
        _POLICY = V.load_config("rb_method_policy")
    return _POLICY


_METHOD_FUNCS = {
    "reverse_zero_crossing": lambda f, zr, zis, zir, ph, fp: _method_reverse_zero_crossing(f, zr, zir, fp),
    "reverse_valley": lambda f, zr, zis, zir, ph, fp: _method_reverse_valley(f, zr, zis, fp),
    "low_freq_plateau": lambda f, zr, zis, zir, ph, fp: _method_low_freq_plateau(f, zr, ph, fp),
    "equivalent_circuit": lambda f, zr, zis, zir, ph, fp: _method_equivalent_circuit(f, zr, zis, fp),
}


def _single_method_rb(freq, z_real, z_imag, method: str, fit_params) -> Optional[float]:
    """强制用指定方法在单谱上提 Rb(适用则返回 Rb,否则 None)。"""
    prep = _preprocess_and_analyze(np.asarray(freq, float), np.asarray(z_real, float),
                                   np.asarray(z_imag, float), fit_params)
    if not prep.get("success"):
        return None
    res = _METHOD_FUNCS[method](
        prep["freq_filtered"], prep["zreal_filtered"], prep["zimag_smooth"],
        prep["zimag_raw"], prep["phase"], fit_params,
    )
    if res.get("success") and res.get("rb_ohm") and res["rb_ohm"] > 0:
        return float(res["rb_ohm"])
    return None


def _bootstrap_method_sd(
    freq, z_real, z_imag, method: str, fit_params,
    n_boot: int = 120, drop_frac: float = 0.10, seed: int = 20260622,
) -> Tuple[Optional[float], float]:
    """频率子采样 bootstrap → 单方法 log10(Rb) 标准差 + 成功率。"""
    rng = np.random.default_rng(seed)
    n = len(freq)
    keep = max(5, int(round(n * (1.0 - drop_frac))))
    logs: List[float] = []
    succ = 0
    for _ in range(n_boot):
        idx = np.sort(rng.choice(n, size=keep, replace=False))
        rb = _single_method_rb(np.asarray(freq)[idx], np.asarray(z_real)[idx],
                               np.asarray(z_imag)[idx], method, fit_params)
        if rb is not None and rb > 0:
            logs.append(float(np.log10(rb)))
            succ += 1
    sd = float(np.std(logs)) if len(logs) > 1 else None
    return sd, succ / n_boot if n_boot else 0.0


def per_point_methods(point: Dict[str, Any], geom_ratio: float,
                      n_boot: int = 0) -> Dict[str, Any]:
    """单温点:四法并行 + 可选 bootstrap SD。geom_ratio = thickness/area。"""
    fp = get_default_fit_params()
    res = fit_all_rb_methods(point["freq"], point["z_real"], point["z_imag"],
                             thickness_cm=geom_ratio, area_cm2=1.0,
                             temperature_K=point["temperature_K"], fit_params=fp)
    if n_boot > 0:
        for name, m in res["methods"].items():
            if m["applicable"]:
                sd, rate = _bootstrap_method_sd(point["freq"], point["z_real"],
                                                point["z_imag"], name, fp, n_boot=n_boot)
                m["log10_rb_sd"] = sd
                m["bootstrap_success_rate"] = rate
    return res


def _geom_ratio(points: List[Dict[str, Any]]) -> float:
    """t/A = median(σ_legacy · Rb_legacy);用于把 Rb 轨迹换算到与 legacy 同尺度的 σ。"""
    vals = [p["conductivity_legacy"] * p["rb_ohm_legacy"]
            for p in points
            if p.get("conductivity_legacy") and p.get("rb_ohm_legacy")]
    return float(np.median(vals)) if vals else 1.0


def _arrhenius_of(traj: List[Tuple[float, float]]) -> Dict[str, Any]:
    """traj = [(T_K, sigma)] → analyze_arrhenius 摘要。"""
    traj = [(T, s) for T, s in traj if T and s and T > 0 and s > 0]
    if len(traj) < 5:
        return {"success": False, "n_points": len(traj), "error": "insufficient points"}
    T = np.array([t for t, _ in traj], float)
    s = np.array([s for _, s in traj], float)
    x = 1000.0 / T
    y = np.log(s)
    r = analyze_arrhenius(x, y, min_segment_points=3)
    if not r.get("success"):
        return {"success": False, "n_points": len(traj), "error": r.get("error")}
    return {
        "success": True,
        "n_points": len(traj),
        "n_segments": r.get("n_segments"),
        "has_transition": bool(r.get("has_transition")),
        "best_model_type": r.get("best_model_type"),
        "confidence": r.get("confidence"),
        "transition_temps_K": r.get("transition_temps_K") or [],
        "ea_eV": [seg.get("Ea_eV") for seg in r.get("segments", [])],
    }


def assess_dataset(ds_dir: Path, n_boot: int = 0) -> Dict[str, Any]:
    points = rl.load_dataset_points(ds_dir / "aggregated_results.json")
    # 只用 legacy 认定成功且 σ>0 的点（与 live arrhenius 重建口径一致）
    pts = [p for p in points if p.get("success_legacy") and p.get("conductivity_legacy", 0) > 0]
    geom = _geom_ratio(pts)
    fp = get_default_fit_params()

    point_rows: List[Dict[str, Any]] = []
    # 四条轨迹的 (T_K, sigma)
    traj_legacy: List[Tuple[float, float]] = []
    traj_plateau: List[Tuple[float, float]] = []
    traj_zero: List[Tuple[float, float]] = []
    traj_ens: List[Tuple[float, float]] = []

    spreads = []
    for p in pts:
        m = per_point_methods(p, geom, n_boot=n_boot)
        T = p["temperature_K"]
        # legacy 轨迹直接用 aggregated 的 rb/σ
        traj_legacy.append((T, p["conductivity_legacy"]))
        # ensemble
        if m["ensemble"]["conductivity_s_per_cm"]:
            traj_ens.append((T, m["ensemble"]["conductivity_s_per_cm"]))
            spreads.append(m["ensemble"]["method_spread_dex"])
        # 固定策略
        rb_plateau = _single_method_rb(p["freq"], p["z_real"], p["z_imag"], "low_freq_plateau", fp)
        if rb_plateau:
            traj_plateau.append((T, geom / rb_plateau))
        rb_zero = _single_method_rb(p["freq"], p["z_real"], p["z_imag"], "reverse_zero_crossing", fp)
        if rb_zero:
            traj_zero.append((T, geom / rb_zero))

        point_rows.append({
            "temperature_C": p["temperature_C"],
            "temperature_K": T,
            "legacy_method": p["rb_method_legacy"],
            "legacy_rb_ohm": p["rb_ohm_legacy"],
            "ensemble_rb_ohm": m["ensemble"]["rb_ohm"],
            "method_spread_dex": m["ensemble"]["method_spread_dex"],
            "rb_range_dex": m["ensemble"]["rb_range_dex"],
            "applicable_methods": m["applicable_methods"],
            "methods": m["methods"],
        })

    trajectories = {
        "legacy_routed": _arrhenius_of(traj_legacy),
        "fixed_plateau": _arrhenius_of(traj_plateau),
        "fixed_zero_crossing": _arrhenius_of(traj_zero),
        "method_ensemble": _arrhenius_of(traj_ens),
    }

    verdict = _invariance_verdict(trajectories)
    pol = _policy()
    spreads_valid = [s for s in spreads if s is not None]

    # 与 legacy arrhenius_analysis.json 直接对照(M0 纪律:legacy 只读,只比不改)
    legacy_arr = _load_legacy_arrhenius(ds_dir)
    v2_ens = trajectories["method_ensemble"]
    legacy_delta = {
        "legacy_n_segments": legacy_arr.get("n_segments"),
        "legacy_transition_temps_K": legacy_arr.get("transition_temps_K"),
        "v2_ensemble_n_segments": v2_ens.get("n_segments"),
        "v2_ensemble_transition_temps_K": v2_ens.get("transition_temps_K"),
        "segments_match": legacy_arr.get("n_segments") == v2_ens.get("n_segments"),
    }

    return {
        "dataset": ds_dir.name,
        "provenance": V.make_provenance({"geom_ratio_t_over_A": geom, "n_boot": n_boot}),
        "n_points": len(pts),
        "method_spread_dex_median": float(np.median(spreads_valid)) if spreads_valid else None,
        "method_spread_dex_max": float(np.max(spreads_valid)) if spreads_valid else None,
        "spread_warn_threshold": pol.get("method_spread_warn_dex"),
        "spread_high_threshold": pol.get("method_spread_high_dex"),
        "trajectories": trajectories,
        "transition_invariance": verdict,
        "legacy_delta": legacy_delta,
        "points": point_rows,
    }


def _load_legacy_arrhenius(ds_dir: Path) -> Dict[str, Any]:
    fp = ds_dir / "arrhenius_analysis.json"
    if not fp.exists():
        return {}
    try:
        d = json.loads(fp.read_text(encoding="utf-8"))
        return {
            "n_segments": d.get("n_segments"),
            "transition_temps_K": d.get("transition_temps_K") or [],
            "best_model_type": d.get("best_model_type"),
        }
    except Exception:
        return {}


def _invariance_verdict(trajectories: Dict[str, Any]) -> Dict[str, Any]:
    """方法不变性门:看转变(分段)在多少条固定策略下成立 + 断点是否重叠。"""
    fixed_keys = ["legacy_routed", "fixed_plateau", "fixed_zero_crossing", "method_ensemble"]
    has_trans = {k: bool(trajectories[k].get("has_transition")) for k in fixed_keys
                 if trajectories[k].get("success")}
    n_ok = sum(1 for v in has_trans.values() if v)
    n_total = len(has_trans)

    # 断点集合(只取有转变的轨迹的首个断点)
    bps = []
    for k, v in trajectories.items():
        if v.get("success") and v.get("transition_temps_K"):
            bps.append(v["transition_temps_K"][0])
    bp_spread_K = float(np.max(bps) - np.min(bps)) if len(bps) > 1 else 0.0

    if n_total == 0:
        risk = "unknown"
    elif n_ok == n_total and bp_spread_K <= 8.0:
        risk = "low"            # 所有固定策略都给转变,断点高度重叠
    elif n_ok == 0:
        risk = "low"            # 都没转变 → 一致(无伪转变)
    elif n_ok == 1 and trajectories.get("legacy_routed", {}).get("has_transition"):
        risk = "high"           # 只有 legacy 路由给转变,疑似温区切换伪影
    else:
        risk = "medium"

    verdict_map = {
        "low": "method-invariant (transition robust to Rb extraction strategy or consistently absent)",
        "medium": "method-dependent low-temperature curvature; report as sensitive to Rb strategy",
        "high": "transition appears only under legacy routing; likely routing artifact",
        "unknown": "insufficient trajectories to judge",
    }
    return {
        "routing_artifact_risk": risk,
        "verdict": verdict_map[risk],
        "n_trajectories_with_transition": n_ok,
        "n_trajectories_assessed": n_total,
        "transition_by_trajectory": has_trans,
        "breakpoint_spread_K": bp_spread_K,
    }


def run_all(kind: str = "lineA", n_boot: int = 0, out_subdir: str = "rb_invariance") -> Dict[str, Any]:
    out_dir = V.RESULTS_ROOT / out_subdir
    out_dir.mkdir(parents=True, exist_ok=True)
    datasets = rl.discover_datasets(kind)
    summary_rows = []
    for ds in datasets:
        res = assess_dataset(ds, n_boot=n_boot)
        (out_dir / f"{ds.name}_rb_invariance_v2.json").write_text(
            json.dumps(res, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")
        summary_rows.append({
            "dataset": res["dataset"],
            "n_points": res["n_points"],
            "method_spread_dex_median": res["method_spread_dex_median"],
            "method_spread_dex_max": res["method_spread_dex_max"],
            "routing_artifact_risk": res["transition_invariance"]["routing_artifact_risk"],
            "n_traj_with_transition": res["transition_invariance"]["n_trajectories_with_transition"],
            "n_traj_assessed": res["transition_invariance"]["n_trajectories_assessed"],
            "breakpoint_spread_K": res["transition_invariance"]["breakpoint_spread_K"],
        })
    summary = {
        "provenance": V.make_provenance({"kind": kind, "n_boot": n_boot}),
        "n_datasets": len(datasets),
        "risk_counts": _count_risks(summary_rows),
        "datasets": summary_rows,
    }
    (out_dir / "rb_invariance_summary_v2.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")
    return summary


def _count_risks(rows: List[Dict[str, Any]]) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for r in rows:
        out[r["routing_artifact_risk"]] = out.get(r["routing_artifact_risk"], 0) + 1
    return out


def _json_default(o):
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    return str(o)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="M1-1 Rb 方法不变性 (G2)")
    ap.add_argument("--kind", default="lineA")
    ap.add_argument("--n_boot", type=int, default=0, help="频率子采样 bootstrap 次数(0=跳过)")
    args = ap.parse_args()
    s = run_all(kind=args.kind, n_boot=args.n_boot)
    print(json.dumps(s["risk_counts"], ensure_ascii=False), "over", s["n_datasets"], "datasets")
    for r in s["datasets"]:
        print(f"  {r['dataset']:28s} risk={r['routing_artifact_risk']:7s} "
              f"spread_med={r['method_spread_dex_median']} "
              f"trans={r['n_traj_with_transition']}/{r['n_traj_assessed']} bp_spreadK={r['breakpoint_spread_K']}")
