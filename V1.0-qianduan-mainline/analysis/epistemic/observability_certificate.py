# -*- coding: utf-8 -*-
"""方案一 —— 可知性驱动:Fisher 可观测性 + 机制等价类 + 不可辨识性证书。

真实做到 GPT「方案一」三件核心对象(全部在真实 σ(T) 上算,无仿真占位):
  (1) Fisher 信息可观测性 O(H)=λ_min(I_FIM):I_FIM=JᵀJ/σ²,λ_min 小=某参数方向不可观测;
  (2) 机制实验等价关系 H_i ~_A H_j ⇔ sup_{a∈A} D_JS(p_i(·|a),p_j(·|a)) < δ → 连通分量=等价类;
  (3) 不可辨识性证书:对不可分对,给出"在当前传感器/噪声/动作集下不可区分",并算出
      打破等价**最少需要哪类新能力**(降噪 / 扩温窗 —— 真实反事实重算 sup JS 是否越过 δ)。

输出 *_observability_certificate.json,带 provenance;绝不改 legacy。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from . import models as M

try:
    from ..stage0_v2 import versions as V  # provenance(可选)
except Exception:  # pragma: no cover
    V = None


# --------------------------------------------------------------------------- #
# Fisher 可观测性
# --------------------------------------------------------------------------- #
def fisher_observability(spec: M.ModelSpec, T: np.ndarray, sigma: float) -> Dict[str, Any]:
    """I_FIM = JᵀJ/σ²;返回 λ_min/λ_max/cond + 最差可观测参数方向。"""
    if not spec.ok or sigma <= 0:
        return {"ok": False}
    J = spec.jac(np.asarray(T, dtype=float), spec.theta)      # [n,k]
    FIM = (J.T @ J) / (sigma ** 2)
    evals, evecs = np.linalg.eigh(FIM)
    evals = np.clip(evals, 0.0, None)
    lam_min = float(evals[0]); lam_max = float(evals[-1])
    cond = float(lam_max / lam_min) if lam_min > 0 else float("inf")
    worst_dir = evecs[:, 0].tolist()
    return {
        "ok": True, "k": spec.k,
        "lambda_min": lam_min, "lambda_max": lam_max,
        "condition_number": cond,
        "worst_observable_direction": worst_dir,   # 该参数线性组合最难被实验约束
        "fim_eigenvalues": evals.tolist(),
        "param_std_upper": (1.0 / np.sqrt(evals[0])) if evals[0] > 0 else None,  # 最差方向后验 sd 下界
    }


# --------------------------------------------------------------------------- #
# 机制等价类(sup over actions 的 JS)
# --------------------------------------------------------------------------- #
def _pair_separation(si: M.ModelSpec, sj: M.ModelSpec, actions_T: np.ndarray,
                     sigma: float) -> Tuple[float, float]:
    """返回 (sup_a JS, 取得 sup 的温度 a*)。"""
    mu_i = si.predict(actions_T); mu_j = sj.predict(actions_T)
    best_js, best_a = -1.0, float("nan")
    for a, m1, m2 in zip(actions_T, mu_i, mu_j):
        js = M.js_divergence_gaussian(float(m1), float(m2), sigma)
        if np.isfinite(js) and js > best_js:
            best_js, best_a = js, float(a)
    return best_js, best_a


class _UnionFind:
    def __init__(self, items): self.p = {x: x for x in items}
    def find(self, x):
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]; x = self.p[x]
        return x
    def union(self, a, b): self.p[self.find(a)] = self.find(b)


def build_certificate(
    T: np.ndarray, y: np.ndarray, *,
    delta: float = 0.05,            # JS 阈值(自然对数;>=δ 视为可区分)
    label: str = "dataset",
    extend_K: float = 40.0,         # 反事实:扩温窗 ±extend_K
    noise_div: float = 3.0,         # 反事实:复测平均降噪因子(sd/√n,n≈9→3)
) -> Dict[str, Any]:
    """对真实 (T,lnσ) 产出不可辨识性证书。"""
    T = np.asarray(T, dtype=float); y = np.asarray(y, dtype=float)
    specs = M.fit_all(T, y)
    names = [n for n in ("arrhenius", "mott", "vtf", "segmented") if specs[n].ok]
    sigma = M.measurement_noise_sd(specs)

    # 当前可用动作集 A = 实测温度 ∪ 窗内密栅(对真实可执行实验的近似)
    A = np.unique(np.concatenate([T, np.linspace(T.min(), T.max(), 60)]))

    # Fisher 可观测性(逐模型)
    obs = {n: fisher_observability(specs[n], T, sigma) for n in names}

    # 逐对 sup JS
    pairs: List[Dict[str, Any]] = []
    uf = _UnionFind(names)
    for ii in range(len(names)):
        for jj in range(ii + 1, len(names)):
            ni, nj = names[ii], names[jj]
            sup_js, a_star = _pair_separation(specs[ni], specs[nj], A, sigma)
            distinguishable = bool(sup_js >= delta)
            entry = {
                "pair": [ni, nj], "sup_JS": sup_js, "best_action_T_K": a_star,
                "best_action_T_C": (a_star - 273.15) if np.isfinite(a_star) else None,
                "distinguishable": distinguishable,
            }
            if not distinguishable:
                uf.union(ni, nj)
                # 反事实:打破等价最少需要哪类新能力(真实重算 sup JS)
                req = _required_capability(specs[ni], specs[nj], T, sigma,
                                           delta, extend_K, noise_div)
                entry["required_new_capability"] = req
            pairs.append(entry)

    # 等价类(连通分量)
    classes: Dict[str, List[str]] = {}
    for n in names:
        classes.setdefault(uf.find(n), []).append(n)
    eq_classes = sorted([sorted(v) for v in classes.values()], key=len, reverse=True)

    n_unident = sum(1 for p in pairs if not p["distinguishable"])
    if n_unident == 0:
        verdict = "all_pairs_distinguishable_under_current_design"
    elif all(len(c) == 1 for c in eq_classes):
        verdict = "all_pairs_distinguishable_under_current_design"
    else:
        verdict = "design_conditional_unidentifiability"

    cert: Dict[str, Any] = {
        "object": "UnidentifiabilityCertificate",
        "label": label,
        "n_points": int(len(T)),
        "T_range_C": [float(T.min() - 273.15), float(T.max() - 273.15)],
        "measurement_noise_sd_ln": sigma,
        "noise_sd_note": "代理:最灵活模型(segmented/vtf)残差 sd,含部分模型失配,为上界式",
        "js_delta_threshold": delta,
        "models": names,
        "fisher_observability": obs,
        "pairwise": pairs,
        "equivalence_classes": eq_classes,
        "n_distinguishable_pairs": sum(1 for p in pairs if p["distinguishable"]),
        "n_unidentifiable_pairs": n_unident,
        "verdict": verdict,
        "aic_best_model": min(names, key=lambda n: specs[n].aic),
    }
    if V is not None:
        try:
            cert["provenance"] = V.make_provenance({"delta": delta})
        except Exception:
            pass
    return cert


def _required_capability(si: M.ModelSpec, sj: M.ModelSpec, T: np.ndarray,
                         sigma: float, delta: float, extend_K: float,
                         noise_div: float) -> Dict[str, Any]:
    """反事实重算:哪类干预能把 sup JS 抬过 δ(真实计算,不是口号)。"""
    options: List[Dict[str, Any]] = []

    # (a) 降噪(复测平均 sd/noise_div)
    A_now = np.unique(np.concatenate([T, np.linspace(T.min(), T.max(), 60)]))
    sup_lownoise, a1 = _pair_separation(si, sj, A_now, sigma / noise_div)
    options.append({
        "capability": f"reduce_noise_x{noise_div:g}_via_replication",
        "achieved_sup_JS": sup_lownoise, "breaks_equivalence": bool(sup_lownoise >= delta),
        "best_action_T_C": (a1 - 273.15) if np.isfinite(a1) else None,
    })

    # (b) 扩温窗(±extend_K,在现有传感器同噪声下)
    A_ext = np.linspace(T.min() - extend_K, T.max() + extend_K, 120)
    sup_ext, a2 = _pair_separation(si, sj, A_ext, sigma)
    options.append({
        "capability": f"extend_temperature_window_pm{extend_K:g}K",
        "achieved_sup_JS": sup_ext, "breaks_equivalence": bool(sup_ext >= delta),
        "best_action_T_C": (a2 - 273.15) if np.isfinite(a2) else None,
    })

    # (c) 降噪 + 扩窗
    sup_both, a3 = _pair_separation(si, sj, A_ext, sigma / noise_div)
    options.append({
        "capability": f"reduce_noise_x{noise_div:g}_AND_extend_window",
        "achieved_sup_JS": sup_both, "breaks_equivalence": bool(sup_both >= delta),
        "best_action_T_C": (a3 - 273.15) if np.isfinite(a3) else None,
    })

    feasible = [o for o in options if o["breaks_equivalence"]]
    return {
        "options": options,
        "any_feasible": bool(feasible),
        "cheapest_feasible": (sorted(feasible, key=lambda o: o["achieved_sup_JS"], reverse=True)[0]["capability"]
                              if feasible else None),
        "note": ("增加同类同噪声实验无法打破(需上述能力之一)" if not feasible
                 else "存在可打破等价的新能力"),
    }


def write_certificate(cert: Dict[str, Any], out_path: Path) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(cert, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path
