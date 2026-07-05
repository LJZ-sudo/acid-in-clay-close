# -*- coding: utf-8 -*-
"""敏感性 / 消融作业服务（M1-8）。

把 /api/jobs/threshold_sweep 与 /api/jobs/ablation 从 placeholder 接到 **真实** v2 产物:
  - threshold_sweep ← 转变对"Rb 方法 / KK 阈值 / 管线假阳性"的稳健性
        (rb_invariance + breakpoint_uncertainty + synthetic_validation 三个 v2 摘要)
  - ablation        ← Rb 提取策略消融(legacy/fixed_plateau/fixed_zero_crossing/ensemble)
        + 稳健回归消融(全点/稳健/留一)

只读 `research/*/...summary_v2.json` 等产物,绝不重跑重计算、绝不伪造;
产物缺失时返回 generated=False + 生成命令提示(诚实)。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

# services/ -> backend_api/ -> mainline root -> repo root
MAINLINE_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = MAINLINE_ROOT.parent
NDA = REPO_ROOT / "experiments"


def _read_json(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _missing(job: str, needed: List[str], cmds: List[str]) -> Dict[str, Any]:
    return {
        "ok": True,
        "job": job,
        "generated": False,
        "message": f"{job} 依赖的 v2 产物尚未生成;请先运行下列命令再调用本接口。",
        "missing_artifacts": needed,
        "generate_commands": cmds,
        "results": [],
    }


def run_threshold_sweep(payload: Optional[dict] = None) -> Dict[str, Any]:
    """转变对 Rb 方法 / KK 阈值 / 管线假阳性的稳健性汇总(G2 阈值/方法敏感性)。"""
    rb = _read_json(NDA / "results" / "rb_invariance" / "rb_invariance_summary_v2.json")
    bp = _read_json(NDA / "results" / "breakpoint_uncertainty" / "breakpoint_uncertainty_summary_v2.json")
    syn = _read_json(NDA / "results" / "synthetic_validation" / "synthetic_validation_summary_v2.json")

    if rb is None and bp is None and syn is None:
        return _missing(
            "threshold_sweep",
            ["rb_invariance_summary_v2.json", "breakpoint_uncertainty_summary_v2.json",
             "synthetic_validation_summary_v2.json"],
            ["python -m analysis.stage0_v2.rb_method_invariance --kind lineA",
             "python -m analysis.stage0_v2.breakpoint_uncertainty --n_boot 150",
             "python -m analysis.stage0_v2.synthetic_validation --n_draws 80"],
        )

    # 以数据集为行,合并三类敏感性
    rows: Dict[str, Dict[str, Any]] = {}
    for d in (rb or {}).get("datasets", []):
        rows.setdefault(d["dataset"], {})["rb_routing_artifact_risk"] = d.get("routing_artifact_risk")
        rows[d["dataset"]]["rb_method_spread_dex_median"] = d.get("method_spread_dex_median")
    for d in (bp or {}).get("datasets", []):
        r = rows.setdefault(d["dataset"], {})
        r["p_any_break"] = d.get("p_any_break")
        r["breakpoint_ci95_K"] = d.get("breakpoint_ci95_K")
        r["breakpoint_practical_identifiability"] = d.get("practical_identifiability")
    for d in (syn or {}).get("datasets", []):
        r = rows.setdefault(d["dataset"], {})
        r["pipeline_fpr_break"] = d.get("fpr_break")
        r["synthetic_interpretation"] = d.get("interpretation")

    results = [{"dataset": k, **v} for k, v in sorted(rows.items())]
    risk_counts = (rb or {}).get("risk_counts", {})
    return {
        "ok": True,
        "job": "threshold_sweep",
        "generated": True,
        "message": "转变对 Rb 提取方法 / KK 阈值 / 管线假阳性的稳健性(只读 v2 真实产物)。",
        "provenance": {
            "rb_invariance": (rb or {}).get("provenance"),
            "breakpoint": (bp or {}).get("provenance"),
            "synthetic": (syn or {}).get("provenance"),
        },
        "summary": {
            "rb_routing_risk_counts": risk_counts,
            "n_datasets": len(results),
        },
        "results": results,
    }


def run_ablation(payload: Optional[dict] = None) -> Dict[str, Any]:
    """Rb 提取策略消融(4 轨迹)+ 稳健回归消融(全点/稳健/留一)。"""
    rb_dir = NDA / "results" / "rb_invariance"
    rob_dir = NDA / "results" / "arrhenius_robust"
    per_files = sorted(rb_dir.glob("*_rb_invariance_v2.json")) if rb_dir.exists() else []

    if not per_files:
        return _missing(
            "ablation",
            ["rb_invariance/*_rb_invariance_v2.json", "arrhenius_robust/*_robust_v2.json"],
            ["python -m analysis.stage0_v2.rb_method_invariance --kind lineA",
             "python -m analysis.stage0_v2.arrhenius_robust --kind lineA"],
        )

    results: List[Dict[str, Any]] = []
    for f in per_files:
        d = _read_json(f) or {}
        traj = d.get("trajectories", {})
        ds = d.get("dataset", f.stem)
        # Rb 策略消融:各轨迹的分段/是否转变
        rb_ablation = {
            k: {"n_segments": v.get("n_segments"), "has_transition": v.get("has_transition")}
            for k, v in traj.items()
        }
        # 稳健回归消融
        rob = _read_json(rob_dir / f"{ds}_robust_v2.json") or {}
        loo = rob.get("leave_one_point_out", {})
        rob_ablation = {
            "n_segments_all_points": (rob.get("all_admissible_points") or {}).get("n_segments"),
            "loo_fraction_preserving": loo.get("fraction_preserving_n_segments"),
            "loo_fraction_with_transition": loo.get("fraction_with_transition"),
            "robust_vs_ols_ea_delta_eV": (rob.get("robust_regression") or {}).get("ea_eV_abs_delta"),
        }
        results.append({
            "dataset": ds,
            "routing_artifact_risk": (d.get("transition_invariance") or {}).get("routing_artifact_risk"),
            "rb_strategy_ablation": rb_ablation,
            "robust_regression_ablation": rob_ablation,
        })

    return {
        "ok": True,
        "job": "ablation",
        "generated": True,
        "message": "Rb 提取策略消融(legacy/fixed_plateau/fixed_zero_crossing/ensemble)+ 稳健回归消融(全点/稳健/留一)。",
        "summary": {"n_datasets": len(results)},
        "results": results,
    }
