# -*- coding: utf-8 -*-
"""measurement_txn 真门控（ESAS-OS 2.0 / §10.4 真实落地）。

把 `entered_bo`(逐点准入裁决)从"只记事件"升级为"真门控":据每点 admission 把测量集
切成 **committed**(entered_bo=True,可进 BO/Arrhenius)与 **rejected**(深冷/坏点等),
并据此过滤 Stage0 bundle 的 eis_points,让下游 BO 只吃被准入的点。

纯函数 + fail-safe:schema 不符就原样返回、绝不抛回主回路。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


def build_committed_view(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """rows: [{step_idx, T_C, entered_bo, admissions}] → committed/rejected 视图。"""
    committed, rejected = [], []
    for r in rows:
        (committed if r.get("entered_bo") else rejected).append(r)
    return {
        "n_total": len(rows),
        "n_committed": len(committed),
        "n_rejected": len(rejected),
        "committed_T_C": [r.get("T_C") for r in committed],
        "rejected_T_C": [r.get("T_C") for r in rejected],
        "committed": committed,
        "rejected": rejected,
    }


def _ep_temp_C(ep: Dict[str, Any]) -> Optional[float]:
    """从一个 eis_point 取摄氏温度,兼容 T_C / T_K / temperature_C / temperature_K。"""
    for k in ("T_C", "temperature_C"):
        v = ep.get(k)
        if isinstance(v, (int, float)):
            return float(v)
    for k in ("T_K", "temperature_K"):
        v = ep.get(k)
        if isinstance(v, (int, float)):
            return float(v) - 273.15
    return None


def filter_bundle_eis_points(
    bundle: Dict[str, Any],
    rejected_T_C: List[float],
    *,
    tol_C: float = 0.6,
) -> Dict[str, Any]:
    """据 rejected 温度过滤 bundle 的 eis_points(真门控:被拒点不进下游 BO)。
    返回 {bundle, n_before, n_after, n_dropped, dropped_T_C}。schema 不符 → 原样返回。"""
    eps = bundle.get("eis_points")
    if not isinstance(eps, list) or not rejected_T_C:
        return {"bundle": bundle, "n_before": len(eps) if isinstance(eps, list) else 0,
                "n_after": len(eps) if isinstance(eps, list) else 0,
                "n_dropped": 0, "dropped_T_C": []}
    rej = [float(t) for t in rejected_T_C if isinstance(t, (int, float))]
    kept, dropped = [], []
    for ep in eps:
        t = _ep_temp_C(ep) if isinstance(ep, dict) else None
        if t is not None and any(abs(t - rt) <= tol_C for rt in rej):
            dropped.append(t)
        else:
            kept.append(ep)
    new_bundle = dict(bundle)
    new_bundle["eis_points"] = kept
    new_bundle["_commit_gate"] = {
        "applied": True, "n_before": len(eps), "n_after": len(kept),
        "n_dropped": len(dropped), "dropped_T_C": dropped, "tol_C": tol_C,
    }
    return {"bundle": new_bundle, "n_before": len(eps), "n_after": len(kept),
            "n_dropped": len(dropped), "dropped_T_C": dropped}
