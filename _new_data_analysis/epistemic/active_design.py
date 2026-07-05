# -*- coding: utf-8 -*-
"""Gap2 —— 可知性驱动的内层主动实验设计(自主选"下一个测温点")。

把方案一/二/三从"收尾(post-sweep)"推进到"驱动内层下一步":给定已测 (T, lnσ),
对每个候选下一温度,计算**单位成本的期望机制判别价值**(competing models 的预测分布
在该温度上的后验加权两两 JS 散度 / 动作成本),返回 argmax —— 即"现在最该去测哪个温度
才能最快把竞争机制分开"。这是 Box–Hill / BALD 风格的最优判别设计,落到真实 σ(T) 上。

纯 numpy/scipy;不改 legacy;不调 LLM(LLM 角色在 Gap3 的证伪市场里)。
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np

from . import models as M


def aic_posterior(specs: Dict[str, "M.ModelSpec"]) -> Dict[str, float]:
    """AIC 权重 ≈ 模型后验 p(H_i|data)。"""
    valid = {n: s.aic for n, s in specs.items() if s.ok and np.isfinite(s.aic)}
    if not valid:
        return {n: float("nan") for n in specs}
    amin = min(valid.values())
    raw = {n: math.exp(-(a - amin) / 2) for n, a in valid.items()}
    z = sum(raw.values())
    return {n: (raw.get(n, 0.0) / z if z > 0 else 0.0) for n in specs}


def action_cost(T_K: float, *, T_ref: float = 298.15) -> float:
    """动作成本:越冷越贵(制冷/平衡时间);与 min_discriminating_set 口径一致。"""
    dT = max(T_ref - float(T_K), 0.0)
    return 1.0 + 0.04 * dT


@dataclass
class DesignChoice:
    next_T_K: float
    value_per_cost: float
    raw_value: float
    cost: float
    posterior: Dict[str, float]
    n_competing: int
    ranking: List[tuple]            # [(T_K, value_per_cost), ...] desc
    sigma_meas: float
    rationale: str


def expected_discrimination(specs, posterior, T_cand, sigma) -> float:
    """候选温度 T_cand 的期望判别价值:
       V(a) = Σ_{i<j} w_i w_j · JS(N(μ_i(a),σ²) ‖ N(μ_j(a),σ²))。
    只计入后验权重非零的"仍在竞争"模型,直接复用 models.js_divergence_gaussian。"""
    names = [n for n in specs if specs[n].ok and posterior.get(n, 0) > 1e-3]
    if len(names) < 2:
        return 0.0
    Tc = np.array([float(T_cand)])
    mu = {n: float(specs[n].predict(Tc)[0]) for n in names}
    v = 0.0
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = names[i], names[j]
            js = M.js_divergence_gaussian(mu[a], mu[b], sigma)
            if np.isfinite(js):
                v += posterior[a] * posterior[b] * js
    return float(v)


def select_next_temperature(
    T_obs, y_obs, candidate_T_K, *,
    T_ref: float = 298.15,
    min_points: int = 4,
) -> Optional[DesignChoice]:
    """给定已测 (T_obs[K], y_obs=lnσ) 与候选温度集,返回最优"下一个测温点"。
    数据不足(< min_points)→ None(交回均匀扫/burn-in,诚实不臆测)。"""
    T_obs = np.asarray(T_obs, float); y_obs = np.asarray(y_obs, float)
    cands = [float(t) for t in candidate_T_K if np.isfinite(t)]
    if len(T_obs) < min_points or not cands:
        return None
    specs = M.fit_all(T_obs, y_obs)
    if not any(s.ok for s in specs.values()):
        return None
    posterior = aic_posterior(specs)
    sigma = M.measurement_noise_sd(specs)
    n_comp = sum(1 for n in specs if specs[n].ok and posterior.get(n, 0) > 1e-3)

    scored = []
    for Tc in cands:
        val = expected_discrimination(specs, posterior, Tc, sigma)
        cost = action_cost(Tc, T_ref=T_ref)
        scored.append((Tc, val / cost, val, cost))
    scored.sort(key=lambda r: r[1], reverse=True)
    best = scored[0]
    ranking = [(round(t, 2), round(vpc, 5)) for (t, vpc, _, _) in scored]
    rationale = (
        f"{n_comp} 个机制仍在竞争(后验:" +
        ", ".join(f"{n}={posterior[n]:.2f}" for n in posterior if posterior[n] > 1e-3) +
        f");在 T={best[0]:.1f}K 处后验加权预测分歧/成本最大 → 最快判别。"
    )
    return DesignChoice(
        next_T_K=best[0], value_per_cost=best[1], raw_value=best[2], cost=best[3],
        posterior=posterior, n_competing=n_comp, ranking=ranking,
        sigma_meas=sigma, rationale=rationale,
    )
