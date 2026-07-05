# -*- coding: utf-8 -*-
"""Rb-ACT R2→R3 噪声桥（ESAS-OS 2.0 / §10.3 真实落地）。

R2:Rb-ACT 只做 shadow 双跑(|Δlog10 Rb| / 未解释翻转),legacy 采纳、不影响优化器。
R3:把 Rb-ACT 后验的**计量不确定度** `sigma_log10_total`(dex)直接转成噪声感知 GP 的
**逐观测方差** `objective_variance`(= train_Yvar),写进 trial.metadata 并标注
`noise_source=RB_ACT_METROLOGICAL_DIRECT` —— 让 BO 真正"知道每个点测得多准"。

映射:目标在 log10σ 域,σ ∝ 1/Rb ⇒ log10σ 的不确定度 = log10Rb 的不确定度(同 dex)。
故 Var(objective) = max(u_dex, floor_dex)²(floor 防 0 方差致 GP 病态)。

纯函数 + IO 极小 + fail-safe(读不到/坏文件 → None,绝不抛回主回路)。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

RBACT_NOISE_SOURCE = "RB_ACT_METROLOGICAL_DIRECT"
_NOISE_FILE = "rbact_noise.json"


def variance_from_u_dex(u_dex: float, floor_dex: float = 0.02) -> float:
    """Rb-ACT 计量不确定度(dex)→ 噪声感知 GP 逐观测方差(log10σ 域)。"""
    u = max(float(u_dex), float(floor_dex))
    return u * u


def build_train_Yvar(u_dex_list: List[float], floor_dex: float = 0.02) -> List[float]:
    """逐点 u_dex → 逐观测方差向量(供 GP alpha / train_Yvar)。"""
    return [variance_from_u_dex(u, floor_dex) for u in u_dex_list]


def stamp_metadata(metadata: Dict[str, Any], u_dex: Optional[float],
                   floor_dex: float = 0.02) -> Dict[str, Any]:
    """把 Rb-ACT 计量不确定度写进 trial.metadata:objective_variance + noise_source。
    u_dex 为 None → 原样返回(优化器回落 default_obs_variance,诚实标 PROXY)。"""
    if u_dex is None:
        return metadata
    metadata = dict(metadata)
    metadata["objective_variance"] = variance_from_u_dex(u_dex, floor_dex)
    metadata["noise_source"] = RBACT_NOISE_SOURCE
    metadata["rbact_u_total_dex"] = float(u_dex)
    return metadata


def write_rbact_noise(bundle_dir, u_dex_median: float, n_points: int,
                      u_dex_max: Optional[float] = None) -> Optional[str]:
    """把本配方的代表性 Rb-ACT 计量不确定度落到 bundle 目录旁,供 Stage1 摄取。"""
    try:
        p = Path(bundle_dir) / _NOISE_FILE
        p.write_text(json.dumps({
            "rbact_u_total_dex_median": float(u_dex_median),
            "rbact_u_total_dex_max": (float(u_dex_max) if u_dex_max is not None else None),
            "n_points": int(n_points),
            "noise_source": RBACT_NOISE_SOURCE,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(p)
    except Exception:  # noqa: BLE001
        return None


def load_rbact_noise(bundle_dir) -> Optional[float]:
    """从 bundle 目录读回代表性 Rb-ACT 计量不确定度(median dex);读不到 → None。"""
    try:
        p = Path(bundle_dir) / _NOISE_FILE
        if not p.exists():
            return None
        d = json.loads(p.read_text(encoding="utf-8"))
        v = d.get("rbact_u_total_dex_median")
        return float(v) if isinstance(v, (int, float)) else None
    except Exception:  # noqa: BLE001
        return None
