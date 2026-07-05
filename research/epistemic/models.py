# -*- coding: utf-8 -*-
"""竞争温度-传导模型:真实拟合 + 高斯预测分布 + 共享测量噪声。

所有模型在 (T[K], y=lnσ) 空间定义。模型族(GPT「竞争解释」H_i):
  - arrhenius : y = c - b/T                      (params [c, b],   k=2)
  - mott(VRH) : y = c - b*T^(-1/4)               (params [c, b],   k=2)
  - vtf       : y = c - b/(T - T0), T0<min(T)    (params [c,b,T0], k=3)
  - segmented : 分段 Arrhenius(1/T 折线,连续) (params [c,b1,b2,xc], k=4)

预测分布 p(Y|H_i, a):在动作 a(=某温度 T)上 N(μ_i(a;θ̂_i), σ_meas²)。
σ_meas = 测量噪声估计(取最灵活模型 segmented 的残差 sd,代表"非模型失配"的偶然噪声),
诚实标注:它含一部分模型失配,是上界式代理(报告即可,不藏)。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Tuple

import numpy as np
from scipy.optimize import curve_fit


# --------------------------------------------------------------------------- #
# 模型预测函数 μ(T; θ)  以及  Jacobian ∂μ/∂θ(用于 Fisher 信息)
# --------------------------------------------------------------------------- #
def _mu_arrhenius(T, theta):
    c, b = theta
    return c - b / T


def _jac_arrhenius(T, theta):
    return np.vstack([np.ones_like(T), -1.0 / T]).T  # [n,2]


def _mu_mott(T, theta):
    c, b = theta
    return c - b * T ** (-0.25)


def _jac_mott(T, theta):
    return np.vstack([np.ones_like(T), -(T ** (-0.25))]).T


def _mu_vtf(T, theta):
    c, b, T0 = theta
    return c - b / (T - T0)


def _jac_vtf(T, theta):
    c, b, T0 = theta
    d = (T - T0)
    return np.vstack([np.ones_like(T), -1.0 / d, -b / d ** 2]).T


def _mu_segmented(T, theta):
    """分段 Arrhenius:x=1/T,折点 xc。x<=xc(高温)斜率 b1;x>xc(低温)斜率 b2,连续。"""
    c, b1, b2, xc = theta
    x = 1.0 / T
    lo = x <= xc
    y = np.empty_like(x)
    y[lo] = c - b1 * x[lo]
    y[~lo] = c - b1 * xc - b2 * (x[~lo] - xc)
    return y


def _jac_segmented(T, theta):
    c, b1, b2, xc = theta
    x = 1.0 / T
    lo = x <= xc
    dc = np.ones_like(x)
    db1 = np.where(lo, -x, -xc)
    db2 = np.where(lo, 0.0, -(x - xc))
    dxc = np.where(lo, 0.0, -b1 + b2)  # ∂/∂xc of (-b1*xc - b2*(x-xc)) = -b1 + b2
    return np.vstack([dc, db1, db2, dxc]).T


@dataclass
class ModelSpec:
    name: str
    k: int
    mu: Callable[[np.ndarray, np.ndarray], np.ndarray]
    jac: Callable[[np.ndarray, np.ndarray], np.ndarray]
    theta: np.ndarray = field(default=None)        # fitted params
    rss: float = field(default=np.nan)
    resid_sd: float = field(default=np.nan)
    aic: float = field(default=np.nan)
    ok: bool = field(default=False)

    def predict(self, T: np.ndarray) -> np.ndarray:
        return self.mu(np.asarray(T, dtype=float), self.theta)


def _aic(n: int, rss: float, k: int) -> float:
    if rss <= 0 or n <= k + 1:
        return np.inf
    import math
    return n * math.log(rss / n) + 2 * k + (2 * k * (k + 1)) / (n - k - 1)


def _fit_linear(T, y, basis_fn) -> Tuple[np.ndarray, np.ndarray]:
    X = basis_fn(T)
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    return coef, X @ coef


def fit_all(T: np.ndarray, y: np.ndarray) -> Dict[str, ModelSpec]:
    """对真实 (T, y=lnσ) 拟合全部竞争模型,返回 name→ModelSpec(含 θ̂/rss/aic)。"""
    T = np.asarray(T, dtype=float)
    y = np.asarray(y, dtype=float)
    n = len(T)
    specs: Dict[str, ModelSpec] = {}

    # arrhenius
    coef, yp = _fit_linear(T, y, lambda t: np.vstack([np.ones_like(t), -1.0 / t]).T)
    s = ModelSpec("arrhenius", 2, _mu_arrhenius, _jac_arrhenius, theta=coef)
    s.rss = float(np.sum((y - yp) ** 2)); s.resid_sd = float(np.std(y - yp))
    s.aic = _aic(n, s.rss, 2); s.ok = True; specs["arrhenius"] = s

    # mott
    coef, yp = _fit_linear(T, y, lambda t: np.vstack([np.ones_like(t), -(t ** (-0.25))]).T)
    s = ModelSpec("mott", 2, _mu_mott, _jac_mott, theta=coef)
    s.rss = float(np.sum((y - yp) ** 2)); s.resid_sd = float(np.std(y - yp))
    s.aic = _aic(n, s.rss, 2); s.ok = True; specs["mott"] = s

    # vtf
    tmin = float(np.min(T))
    try:
        popt, _ = curve_fit(lambda t, c, b, T0: c - b / (t - T0), T, y,
                            p0=[float(np.max(y)), 500.0, tmin - 50.0],
                            bounds=([-50, 1.0, -2000.0], [50, 1e6, tmin - 1.0]),
                            maxfev=20000)
        yp = _mu_vtf(T, popt)
        s = ModelSpec("vtf", 3, _mu_vtf, _jac_vtf, theta=np.asarray(popt))
        s.rss = float(np.sum((y - yp) ** 2)); s.resid_sd = float(np.std(y - yp))
        s.aic = _aic(n, s.rss, 3); s.ok = True
    except Exception:
        s = ModelSpec("vtf", 3, _mu_vtf, _jac_vtf, theta=np.array([np.max(y), 500.0, tmin - 50.0]))
        s.ok = False
    specs["vtf"] = s

    # segmented(在 1/T 上找折点;初值用中位 x)
    x = 1.0 / T
    try:
        xc0 = float(np.median(x))
        b0 = float((y.max() - y.min()) / (x.max() - x.min() + 1e-9))
        popt, _ = curve_fit(
            lambda t, c, b1, b2, xc: _mu_segmented(t, (c, b1, b2, xc)),
            T, y, p0=[float(np.max(y)), b0, b0 * 2, xc0],
            bounds=([-50, 0.0, 0.0, float(x.min()) + 1e-6],
                    [50, 1e5, 1e5, float(x.max()) - 1e-6]),
            maxfev=30000)
        yp = _mu_segmented(T, popt)
        s = ModelSpec("segmented", 4, _mu_segmented, _jac_segmented, theta=np.asarray(popt))
        s.rss = float(np.sum((y - yp) ** 2)); s.resid_sd = float(np.std(y - yp))
        s.aic = _aic(n, s.rss, 4); s.ok = True
    except Exception:
        s = ModelSpec("segmented", 4, _mu_segmented, _jac_segmented,
                      theta=np.array([np.max(y), 500.0, 1000.0, float(np.median(x))]))
        s.ok = False
    specs["segmented"] = s

    return specs


def measurement_noise_sd(specs: Dict[str, ModelSpec]) -> float:
    """测量噪声代理 = 最灵活且拟合成功的模型残差 sd(优先 segmented>vtf>min)。"""
    for name in ("segmented", "vtf"):
        s = specs.get(name)
        if s is not None and s.ok and np.isfinite(s.resid_sd) and s.resid_sd > 0:
            return float(s.resid_sd)
    sds = [s.resid_sd for s in specs.values() if s.ok and np.isfinite(s.resid_sd)]
    return float(min(sds)) if sds else 0.1


# --------------------------------------------------------------------------- #
# 高斯散度(GPT D_JS):等方差一维高斯的 JS 散度,数值积分(bounded [0,ln2])
# --------------------------------------------------------------------------- #
def js_divergence_gaussian(mu1: float, mu2: float, sigma: float,
                           n_grid: int = 801, span: float = 8.0) -> float:
    """JS(N(mu1,σ²) || N(mu2,σ²)),自然对数,数值积分。返回 [0, ln2]。"""
    if sigma <= 0:
        return float("nan")
    lo = min(mu1, mu2) - span * sigma
    hi = max(mu1, mu2) + span * sigma
    z = np.linspace(lo, hi, n_grid)
    def npdf(m):
        return np.exp(-0.5 * ((z - m) / sigma) ** 2) / (sigma * np.sqrt(2 * np.pi))
    p = npdf(mu1); q = npdf(mu2)
    m = 0.5 * (p + q)
    eps = 1e-300
    def kl(a, b):
        a = np.clip(a, eps, None); b = np.clip(b, eps, None)
        return np.trapz(a * np.log(a / b), z)
    return float(0.5 * kl(p, m) + 0.5 * kl(q, m))


def detectability_index(mu1: float, mu2: float, sigma: float) -> float:
    """d' = |Δμ|/σ(每动作单测量的可分指数,Fisher 风格)。"""
    if sigma <= 0:
        return float("nan")
    return abs(mu1 - mu2) / sigma
