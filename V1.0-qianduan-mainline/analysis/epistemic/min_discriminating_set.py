# -*- coding: utf-8 -*-
"""方案三 —— 证明携带编译器的核心:最小判别实验集 + 编译失败→等价类。

真实做到 GPT「方案三 §4 / §5」:给竞争模型 H 与可执行动作集 A(真实可测温度锚点),
求最小成本实验子集 S* ⊆ A,使**每一对可区分模型**都被 S* 中某动作以 D_JS≥δ 分开:

    S* = argmin_{S⊆A} Σ_{a∈S} c(a)
    s.t. ∀ i≠j(可分对): max_{a∈S} D_JS(p_i(·|a), p_j(·|a)) ≥ δ

本质 = 加权集合覆盖 / hitting set(NP 完全;此处 universe(对数)≤6,用 bitmask DP 求**精确**最优,
并与贪心对照报告近似比)。若某对在整个 A 上都无法分开 → **编译失败**,输出不可辨识等价类
+ 需要的新能力(来自 observability_certificate)。成本模型:冷点更贵(平衡慢/高阻 EIS 慢),显式声明。
"""
from __future__ import annotations

import json
from itertools import combinations
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from . import models as M
from .observability_certificate import _required_capability

try:
    from ..stage0_v2 import versions as V
except Exception:  # pragma: no cover
    V = None


def action_cost(T_K: float, T_min: float, T_max: float,
                base: float = 1.0, cold_penalty: float = 3.0) -> float:
    """真实成本代理:c(T)=base + cold_penalty*(Tmax-T)/(Tmax-Tmin)。冷点最贵(≈base+penalty)。"""
    if T_max <= T_min:
        return base
    frac_cold = (T_max - T_K) / (T_max - T_min)
    return float(base + cold_penalty * max(0.0, min(1.0, frac_cold)))


def _min_cost_set_cover(universe: List[int], cover_of: Dict[int, set],
                        cost: Dict[int, float]) -> Tuple[List[int], float]:
    """精确最小成本集合覆盖(universe 为 pair 索引;bitmask DP)。返回 (actions, cost)。"""
    if not universe:
        return [], 0.0
    idx = {p: b for b, p in enumerate(universe)}
    full = (1 << len(universe)) - 1
    # 每个动作覆盖的 pair bitmask
    amask: Dict[int, int] = {}
    for a, pairs in cover_of.items():
        m = 0
        for p in pairs:
            if p in idx:
                m |= (1 << idx[p])
        if m:
            amask[a] = m
    INF = float("inf")
    dp = {0: (0.0, [])}  # mask -> (cost, actions)
    # Dijkstra-ish over masks
    import heapq
    pq = [(0.0, 0, [])]
    best = {0: 0.0}
    while pq:
        c, mask, acts = heapq.heappop(pq)
        if mask == full:
            return acts, c
        if c > best.get(mask, INF):
            continue
        for a, m in amask.items():
            nm = mask | m
            if nm == mask:
                continue
            nc = c + cost[a]
            if nc < best.get(nm, INF):
                best[nm] = nc
                heapq.heappush(pq, (nc, nm, acts + [a]))
    return [], INF  # 不可覆盖(有不可分对)


def _greedy_set_cover(universe: List[int], cover_of: Dict[int, set],
                      cost: Dict[int, float]) -> Tuple[List[int], float]:
    uncovered = set(universe)
    chosen, total = [], 0.0
    cov = {a: (set(ps) & uncovered) for a, ps in cover_of.items()}
    while uncovered:
        best_a, best_ratio = None, float("inf")
        for a, ps in cover_of.items():
            new = set(ps) & uncovered
            if not new:
                continue
            ratio = cost[a] / len(new)
            if ratio < best_ratio:
                best_ratio, best_a = ratio, a
        if best_a is None:
            break  # 剩余不可覆盖
        chosen.append(best_a)
        total += cost[best_a]
        uncovered -= set(cover_of[best_a])
    return chosen, (total if not uncovered else float("inf"))


def build_min_discriminating_set(
    T: np.ndarray, y: np.ndarray, *,
    delta: float = 0.05, label: str = "dataset",
    candidate_actions_T: Optional[np.ndarray] = None,
) -> Dict[str, Any]:
    """对真实 (T,lnσ) 求最小判别实验集。candidate_actions 缺省=实测温度锚点(真实可执行菜单)。"""
    T = np.asarray(T, dtype=float); y = np.asarray(y, dtype=float)
    specs = M.fit_all(T, y)
    names = [n for n in ("arrhenius", "mott", "vtf", "segmented") if specs[n].ok]
    sigma = M.measurement_noise_sd(specs)
    A = np.unique(np.asarray(candidate_actions_T, dtype=float)) if candidate_actions_T is not None \
        else np.unique(T)
    Tmin, Tmax = float(np.unique(T).min()), float(np.unique(T).max())

    model_pairs = list(combinations(names, 2))
    pair_idx = {pr: i for i, pr in enumerate(model_pairs)}

    # 每个动作分开了哪些对(per-action JS >= delta)
    cover_of: Dict[int, set] = {}
    cost: Dict[int, float] = {}
    action_T: Dict[int, float] = {}
    per_action_js: Dict[int, Dict[str, float]] = {}
    for ai, a in enumerate(A):
        covered = set()
        js_map = {}
        for pr in model_pairs:
            ni, nj = pr
            m1 = float(specs[ni].predict(np.array([a]))[0])
            m2 = float(specs[nj].predict(np.array([a]))[0])
            js = M.js_divergence_gaussian(m1, m2, sigma)
            js_map[f"{ni}|{nj}"] = js
            if np.isfinite(js) and js >= delta:
                covered.add(pair_idx[pr])
        cover_of[ai] = covered
        cost[ai] = action_cost(float(a), Tmin, Tmax)
        action_T[ai] = float(a)
        per_action_js[ai] = js_map

    # 哪些对在整个 A 上可分 / 不可分
    separable, unsep = [], []
    for pr, pi in pair_idx.items():
        if any(pi in cover_of[ai] for ai in cover_of):
            separable.append(pi)
        else:
            unsep.append(pr)

    universe = separable
    exact_acts, exact_cost = _min_cost_set_cover(universe, cover_of, cost)
    greedy_acts, greedy_cost = _greedy_set_cover(universe, cover_of, cost)

    result: Dict[str, Any] = {
        "object": "MinimalDiscriminatingExperimentSet",
        "label": label,
        "models": names,
        "n_model_pairs": len(model_pairs),
        "measurement_noise_sd_ln": sigma,
        "js_delta_threshold": delta,
        "n_candidate_actions": int(len(A)),
        "cost_model": "c(T)=1 + 3*(Tmax-T)/(Tmax-Tmin)  (冷点最贵≈4x,平衡慢/高阻EIS慢)",
        "n_separable_pairs": len(separable),
        "n_unidentifiable_pairs": len(unsep),
    }

    if unsep:
        # 编译失败:输出不可辨识等价类 + 需要的新能力
        comp = {"status": "compilation_failed",
                "reason": "存在模型对在当前传感器/噪声/动作集下无法以 JS>=δ 区分",
                "unidentifiable_pairs": []}
        for pr in unsep:
            ni, nj = pr
            req = _required_capability(specs[ni], specs[nj], T, sigma, delta,
                                       extend_K=40.0, noise_div=3.0)
            comp["unidentifiable_pairs"].append({
                "pair": [ni, nj], "required_new_capability": req,
            })
        result["compilation"] = comp
    else:
        result["compilation"] = {"status": "ok",
                                 "reason": "全部可分对都能被最小实验集分开"}

    # 最小实验集(即便有不可分对,也给可分部分的最小集)
    sel_T_exact = sorted(action_T[a] for a in exact_acts)
    result["minimal_set"] = {
        "exact_optimal": {
            "action_T_K": sel_T_exact,
            "action_T_C": [round(t - 273.15, 2) for t in sel_T_exact],
            "n_actions": len(exact_acts), "total_cost": exact_cost,
        },
        "greedy": {
            "n_actions": len(greedy_acts),
            "total_cost": greedy_cost,
            "approx_ratio_vs_exact": (greedy_cost / exact_cost
                                      if exact_cost not in (0.0, float("inf")) else None),
        },
        "per_pair_separating_action": _per_pair_best_action(
            model_pairs, exact_acts, action_T, per_action_js, delta),
    }
    if V is not None:
        try:
            result["provenance"] = V.make_provenance({"delta": delta})
        except Exception:
            pass
    return result


def _per_pair_best_action(model_pairs, chosen_actions, action_T, per_action_js, delta):
    out = []
    for pr in model_pairs:
        ni, nj = pr; key = f"{ni}|{nj}"
        best_a, best_js = None, -1.0
        for a in chosen_actions:
            js = per_action_js[a].get(key, float("nan"))
            if np.isfinite(js) and js >= delta and js > best_js:
                best_js, best_a = js, action_T[a]
        out.append({
            "pair": [ni, nj],
            "separated_by_T_C": (round(best_a - 273.15, 2) if best_a is not None else None),
            "JS_at_action": (best_js if best_a is not None else None),
        })
    return out


def write_result(result: Dict[str, Any], out_path: Path) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path
