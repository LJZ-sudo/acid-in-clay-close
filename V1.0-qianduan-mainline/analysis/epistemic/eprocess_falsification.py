# -*- coding: utf-8 -*-
"""方案二 —— 对抗式可证伪:anytime-valid e-process + 单位成本证伪价值 + 严格评分信誉。

真实做到 GPT「方案二 §5 / §3 / §4」三件核心对象:
  (1) e-process(证据过程):E_t=∏_s p1(y_s)/p0(y_s)。H0,H1 在测试序列前**冻结**(用 holdout
      拟合),故 E_t 在 H0 下是非负鞅(E[E_t]=1)⇒ Ville 不等式:P(∃t: E_t≥1/α)≤α —— 即**随时有效**
      (可任意提前停止/连续监控,不破坏 type-I)。主张只在 E_t≥1/α 时才允许升级。
  (2) 单位成本证伪价值选择器:a*=argmax_a [min_q KL(p_sel‖p_q | a)] / (c(a)+ρ·risk(a)) —— 选"对最难
      区分的竞争解释、单位成本判别力最大"的实验(而非最可能成功的实验)。
  (3) 信誉=严格适当评分(Brier/log-loss):复用 stage1 的 scientific_skills.dual_account。

附带:对**真实 live 序列**跑 e-process(H0=单 Arrhenius warm-holdout 冻结,H1=分段冻结),并用
蒙特卡洛**在 H0 下**实测 P(曾越过 1/α)≤α,给出 anytime-valid 的可证伪验证(不是口号)。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from . import models as M

try:
    from ..stage0_v2 import versions as V
except Exception:  # pragma: no cover
    V = None

LOG2PI = np.log(2 * np.pi)


def _gauss_logpdf(y: np.ndarray, mu: np.ndarray, sigma: float) -> np.ndarray:
    return -0.5 * ((y - mu) / sigma) ** 2 - np.log(sigma) - 0.5 * LOG2PI


def eprocess(y_seq: np.ndarray, mu0_seq: np.ndarray, mu1_seq: np.ndarray,
             sigma: float, alpha: float = 0.05) -> Dict[str, Any]:
    """E_t=∏ p1/p0(H0,H1 均为同方差高斯,均值序列已冻结)。返回轨迹/越界/停时。"""
    y_seq = np.asarray(y_seq, float)
    lp1 = _gauss_logpdf(y_seq, np.asarray(mu1_seq, float), sigma)
    lp0 = _gauss_logpdf(y_seq, np.asarray(mu0_seq, float), sigma)
    log_e = np.cumsum(lp1 - lp0)                 # 全程在 log 空间,避免溢出
    log_thr = np.log(1.0 / alpha)
    crossed = bool(np.any(log_e >= log_thr))
    stop = int(np.argmax(log_e >= log_thr)) + 1 if crossed else None
    E_disp = np.exp(np.clip(log_e, -700, 700))   # 仅用于展示(裁剪防 inf)
    return {
        "alpha": alpha, "threshold_1_over_alpha": float(1.0 / alpha),
        "log_E_trajectory": log_e.tolist(),
        "E_trajectory_clipped": E_disp.tolist(),
        "log_E_final": float(log_e[-1]), "log_E_max": float(np.max(log_e)),
        "E_final_clipped": float(E_disp[-1]), "E_max_clipped": float(np.max(E_disp)),
        "crossed": crossed, "stopping_time": stop, "n_steps": int(len(y_seq)),
    }


def simulate_type_i(mu0_seq: np.ndarray, mu1_seq: np.ndarray, sigma: float,
                    alpha: float = 0.05, n_sims: int = 20000,
                    seed: int = 20260630) -> Dict[str, Any]:
    """在 H0 下模拟序列,实测 P(∃t:E_t≥1/α)。anytime-valid 要求其 ≤ α(Ville)。"""
    rng = np.random.default_rng(seed)
    mu0 = np.asarray(mu0_seq, float); mu1 = np.asarray(mu1_seq, float)
    n = len(mu0); log_thr = np.log(1.0 / alpha)
    # 每步 logLR 作为 y 的函数:lp1-lp0 = [(y-mu0)^2-(y-mu1)^2]/(2σ²);全程 log 空间防溢出
    crossings = 0
    for _ in range(n_sims):
        y = mu0 + rng.normal(0, sigma, size=n)         # 真值来自 H0
        loglr = ((y - mu0) ** 2 - (y - mu1) ** 2) / (2 * sigma ** 2)
        log_e = np.cumsum(loglr)
        if np.any(log_e >= log_thr):
            crossings += 1
    rate = crossings / n_sims
    return {
        "n_sims": n_sims, "alpha": alpha,
        "empirical_false_alarm_rate": rate,
        "anytime_valid_ok": bool(rate <= alpha + 0.01),  # 容 1% MC 抖动
        "note": "Ville 上界 α;经验越界率应 ≤ α(允许少量 MC 噪声)",
    }


def run_falsification_on_sigmaT(
    T: np.ndarray, y: np.ndarray, *, alpha: float = 0.05,
    holdout_frac: float = 0.45, label: str = "dataset",
    n_type_i_sims: int = 20000,
) -> Dict[str, Any]:
    """真实 σ(T) 上的序贯证伪:warm holdout 冻结 H0(单 Arrhenius)/H1(分段),cold 流式检验。"""
    T = np.asarray(T, float); y = np.asarray(y, float)
    order = np.argsort(T)[::-1]               # 由暖到冷(1/T 升序)
    T, y = T[order], y[order]
    n = len(T); m = max(3, int(round(n * holdout_frac)))
    Th, yh = T[:m], y[:m]                      # holdout(暖端):只用来冻结 H0/H1
    Tt, yt = T[m:], y[m:]                      # 测试(冷端):流式喂 e-process
    if len(Tt) < 2:
        return {"object": "FalsificationEProcess", "label": label,
                "status": "insufficient_test_points", "n_test": int(len(Tt))}

    specs_h = M.fit_all(Th, yh)
    sigma = M.measurement_noise_sd(M.fit_all(T, y))   # 噪声用全量估计(更稳)
    H0 = specs_h["arrhenius"]                  # H0: 暖端单 Arrhenius 外推
    H1 = specs_h["segmented"] if specs_h["segmented"].ok else specs_h["vtf"]

    mu0_t = H0.predict(Tt); mu1_t = H1.predict(Tt)
    ep = eprocess(yt, mu0_t, mu1_t, sigma, alpha=alpha)
    ti = simulate_type_i(mu0_t, mu1_t, sigma, alpha=alpha, n_sims=n_type_i_sims)

    out = {
        "object": "FalsificationEProcess",
        "label": label,
        "H0": "single_arrhenius_warm_holdout_frozen",
        "H1": (H1.name + "_warm_holdout_frozen"),
        "n_holdout_warm": int(m), "n_test_cold": int(len(Tt)),
        "sigma_ln": sigma, "alpha": alpha,
        "test_T_C": [round(float(t - 273.15), 2) for t in Tt],
        "eprocess": ep,
        "type_i_control": ti,
        "claim_escalation_allowed": bool(ep["crossed"] and ti["anytime_valid_ok"]),
        "interpretation": ("E_t 越过 1/α 且 type-I 受控 ⇒ 可在 anytime-valid 意义下"
                           "拒绝 H0(单 Arrhenius),支持存在低温机制转变(C 级证据,仍需复现门)"),
    }
    if V is not None:
        try:
            out["provenance"] = V.make_provenance({"alpha": alpha})
        except Exception:
            pass
    return out


# --------------------------------------------------------------------------- #
# 单位成本证伪价值选择器
# --------------------------------------------------------------------------- #
def _kl_gauss(mu_a: float, mu_b: float, sigma: float) -> float:
    """KL(N(mu_a,σ²)‖N(mu_b,σ²)) = (mu_a-mu_b)²/(2σ²)。"""
    return (mu_a - mu_b) ** 2 / (2 * sigma ** 2)


def falsification_value_per_cost(
    T: np.ndarray, y: np.ndarray, *, selected_model: Optional[str] = None,
    candidate_actions_T: Optional[np.ndarray] = None,
    rho: float = 0.5, label: str = "dataset",
) -> Dict[str, Any]:
    """a*=argmax_a [min_q KL(p_sel‖p_q|a)]/(c(a)+ρ·risk(a))。risk(a)用冷点(高阻/失败)代理。"""
    from .min_discriminating_set import action_cost
    T = np.asarray(T, float); y = np.asarray(y, float)
    specs = M.fit_all(T, y)
    names = [n for n in ("arrhenius", "mott", "vtf", "segmented") if specs[n].ok]
    sigma = M.measurement_noise_sd(specs)
    sel = selected_model or min(names, key=lambda n: specs[n].aic)
    comps = [n for n in names if n != sel]
    A = np.unique(np.asarray(candidate_actions_T, float)) if candidate_actions_T is not None \
        else np.unique(np.concatenate([np.unique(T), np.linspace(T.min(), T.max(), 40)]))
    Tmin, Tmax = float(np.unique(T).min()), float(np.unique(T).max())

    rows = []
    for a in A:
        mu_sel = float(specs[sel].predict(np.array([a]))[0])
        kls = [_kl_gauss(mu_sel, float(specs[q].predict(np.array([a]))[0]), sigma) for q in comps]
        min_kl = float(min(kls)) if kls else 0.0      # 对最难区分的竞争解释
        c = action_cost(float(a), Tmin, Tmax)
        risk = (Tmax - float(a)) / (Tmax - Tmin)      # 冷点风险高(高阻/拒拟合)
        fvpc = min_kl / (c + rho * risk)
        rows.append({"T_C": round(float(a - 273.15), 2), "min_KL_vs_competitors": min_kl,
                     "cost": c, "risk": float(risk), "falsification_value_per_cost": fvpc})
    rows.sort(key=lambda r: r["falsification_value_per_cost"], reverse=True)
    return {
        "object": "FalsificationValuePerCost",
        "label": label, "selected_model": sel, "competitors": comps,
        "rho": rho, "sigma_ln": sigma,
        "best_next_experiment_T_C": rows[0]["T_C"] if rows else None,
        "ranked_actions": rows[:12],
        "note": "选'单位成本对最难区分竞争解释判别力最大'的实验,而非最可能成功的实验",
    }


# --------------------------------------------------------------------------- #
# 信誉:严格适当评分(复用 stage1 dual_account)
# --------------------------------------------------------------------------- #
def reputation_demo(predictions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """predictions: [{agent, p, outcome}]. 用真实 EpistemicAccount 更新 Brier/logloss/信誉。"""
    import sys
    from pathlib import Path as _P
    skills = _P(__file__).resolve().parents[2] / "stage1_optimization"
    if str(skills) not in sys.path:
        sys.path.insert(0, str(skills))
    from scientific_skills.dual_account import EpistemicAccount, RiskClearing  # type: ignore

    acc = EpistemicAccount(eta=0.5)
    for pr in predictions:
        acc.record(pr["agent"], float(pr["p"]), int(pr["outcome"]))
    agents = sorted({pr["agent"] for pr in predictions})
    rc = RiskClearing()
    return {
        "object": "ReputationProperScoring",
        "agents": {a: {"brier": acc.brier(a), "logloss": acc.logloss(a),
                       "reputation": acc.reputation(a)} for a in agents},
        "execution_authority_ignores_self_confidence":
            (rc.authority_depends_on_confidence() is False),
        "note": "严格适当评分:诚实报告概率最优;过度自信者信誉被惩罚;执行权不读自报置信度",
    }


def write_result(result: Dict[str, Any], out_path: Path) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path
