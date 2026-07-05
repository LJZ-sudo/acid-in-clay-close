# -*- coding: utf-8 -*-
"""Gap1 —— 阻抗级正问题:机制模型 MechanismModel(GPT「方案三 §6」接口)。

把"σ(T) 层的高斯预测"升级为 GPT 要求的**机制→阻抗谱正问算子** p(Z(ω)|H,a):
每个机制假设实现统一接口(latent_states / admissible_parameters /
impedance_forward_operator / predicted_invariants / predicted_failure_modes /
domain_of_validity),并在拟合**真实 EIS 谱**(frequencies, z_real, z_imag)后给出:
  - 复阻抗残差 + 加权 χ²(数据级证据,不是口号);
  - 物理静态检查:被动性(Re Z>0)、参数可行域、CPE 指数 ∈ (0,1]、(近似)因果/连续性;
  - ECM 参数的 Fisher λ_min 可观测性(把方案一推到谱级)。

竞争机制(质子导体常见等效电路):
  M1 single_bulk     : Rs + (Rb ∥ CPE_b)                    —— 单一体相质子传导(一段弧)
  M2 bulk_electrode  : Rs + (Rb ∥ CPE_b) + CPE_electrode    —— 体相 + 低频电极阻塞("半圆+斜线")
  M3 two_population  : Rs + (R1 ∥ CPE1) + (R2 ∥ CPE2)       —— 受限+界面两类水(双弧)

纯 numpy/scipy;绝不改 legacy;不调 LLM。
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
from scipy.optimize import least_squares

J = 1j


# --------------------------------------------------------------------------- #
# 阻抗基元
# --------------------------------------------------------------------------- #
def _z_cpe(omega: np.ndarray, Q: float, n: float) -> np.ndarray:
    """CPE 阻抗 Z = 1/(Q (jω)^n)。"""
    return 1.0 / (Q * (J * omega) ** n)


def _z_rq(omega: np.ndarray, R: float, Q: float, n: float) -> np.ndarray:
    """R ∥ CPE(去极化半圆):Z = R / (1 + R Q (jω)^n)。"""
    return R / (1.0 + R * Q * (J * omega) ** n)


# --------------------------------------------------------------------------- #
# 机制模型接口(GPT MechanismModel)
# --------------------------------------------------------------------------- #
@dataclass
class MechanismModel:
    name: str
    param_names: List[str]
    forward: Callable[[np.ndarray, np.ndarray], np.ndarray]  # (omega, theta)->Z complex
    bounds_lo: List[float]
    bounds_hi: List[float]
    p0_fn: Callable[[np.ndarray, np.ndarray, np.ndarray], List[float]]  # (f,zr,zi)->theta0
    invariants: Callable[[np.ndarray], Dict[str, Any]] = None
    failure_modes: Callable[[np.ndarray], List[str]] = None

    @property
    def k(self) -> int:
        return len(self.param_names)

    def impedance_forward_operator(self, freq: np.ndarray, theta: np.ndarray) -> np.ndarray:
        omega = 2 * np.pi * np.asarray(freq, dtype=float)
        return self.forward(omega, np.asarray(theta, dtype=float))

    def latent_states(self) -> List[str]:
        return self.param_names

    def admissible_parameters(self) -> Dict[str, Tuple[float, float]]:
        return {p: (lo, hi) for p, lo, hi in zip(self.param_names, self.bounds_lo, self.bounds_hi)}

    def domain_of_validity(self) -> Dict[str, Any]:
        return {"linear_response": True, "passive": True,
                "freq_window_required": "覆盖体相弧特征频率 1/(2πRC)"}

    def predicted_invariants(self, theta: np.ndarray) -> Dict[str, Any]:
        return self.invariants(theta) if self.invariants else {}

    def predicted_failure_modes(self, theta: np.ndarray) -> List[str]:
        return self.failure_modes(theta) if self.failure_modes else []


# ---- M1 single_bulk : Rs + (Rb ∥ CPE_b) ---------------------------------- #
def _fwd_single(omega, th):
    Rs, Rb, Qb, nb = th
    return Rs + _z_rq(omega, Rb, Qb, nb)


def _p0_single(f, zr, zi):
    Rs = max(float(np.min(zr)) * 0.5, 1e-3)
    Rb = max(float(np.max(zr)) - Rs, 1.0)
    # 峰频估 Q:在 -zi 最大处 ω_p,Q ≈ 1/(Rb ω_p^n),n≈0.85
    nb = 0.85
    k = int(np.argmax(-np.asarray(zi)))
    wp = 2 * np.pi * float(f[k]) if f[k] > 0 else 1.0
    Qb = 1.0 / (Rb * wp ** nb + 1e-12)
    return [Rs, Rb, Qb, nb]


def _inv_single(th):
    Rs, Rb, Qb, nb = th
    wp = (1.0 / (Rb * Qb)) ** (1.0 / nb) if Rb * Qb > 0 else float("nan")
    return {"n_arcs": 1, "R_bulk": Rb, "char_freq_Hz": wp / (2 * np.pi),
            "cpe_exponent": nb}


def _fail_single(th):
    out = []
    Rs, Rb, Qb, nb = th
    if not (0 < nb <= 1.05):
        out.append("cpe_exponent_out_of_range")
    if Rb <= 0 or Rs < 0:
        out.append("nonpassive_resistance")
    return out


M1_single = MechanismModel(
    "single_bulk", ["Rs", "Rb", "Qb", "nb"], _fwd_single,
    bounds_lo=[0.0, 1e-3, 1e-15, 0.4], bounds_hi=[1e9, 1e12, 1e3, 1.05],
    p0_fn=_p0_single, invariants=_inv_single, failure_modes=_fail_single)


# ---- M2 bulk_electrode : Rs + (Rb ∥ CPE_b) + CPE_electrode ---------------- #
def _fwd_bulk_elec(omega, th):
    Rs, Rb, Qb, nb, Qe, ne = th
    return Rs + _z_rq(omega, Rb, Qb, nb) + _z_cpe(omega, Qe, ne)


def _p0_bulk_elec(f, zr, zi):
    s = _p0_single(f, zr, zi)
    # 电极 CPE:低频段近线性,ne≈0.5~0.8;用最低频点幅值估 Qe
    flo = float(np.min(f)); wlo = 2 * np.pi * flo if flo > 0 else 1.0
    mag_lo = float(np.hypot(zr[int(np.argmin(f))], zi[int(np.argmin(f))]))
    ne = 0.6
    Qe = 1.0 / (mag_lo * wlo ** ne + 1e-12)
    return s + [Qe, ne]


def _inv_bulk_elec(th):
    base = _inv_single(th[:4]); base["n_arcs"] = 1; base["electrode_tail"] = True
    base["electrode_cpe_exponent"] = th[5]
    return base


M2_bulk_elec = MechanismModel(
    "bulk_electrode", ["Rs", "Rb", "Qb", "nb", "Qe", "ne"], _fwd_bulk_elec,
    bounds_lo=[0.0, 1e-3, 1e-15, 0.4, 1e-15, 0.2],
    bounds_hi=[1e9, 1e12, 1e3, 1.05, 1e3, 1.05],
    p0_fn=_p0_bulk_elec, invariants=_inv_bulk_elec,
    failure_modes=lambda th: _fail_single(th[:4]))


# ---- M3 two_population : Rs + (R1 ∥ CPE1) + (R2 ∥ CPE2) ------------------- #
def _fwd_two(omega, th):
    Rs, R1, Q1, n1, R2, Q2, n2 = th
    return Rs + _z_rq(omega, R1, Q1, n1) + _z_rq(omega, R2, Q2, n2)


def _p0_two(f, zr, zi):
    Rs = max(float(np.min(zr)) * 0.5, 1e-3)
    Rtot = max(float(np.max(zr)) - Rs, 2.0)
    R1 = Rtot * 0.6; R2 = Rtot * 0.4
    n1 = n2 = 0.85
    k = int(np.argmax(-np.asarray(zi)))
    wp = 2 * np.pi * float(f[k]) if f[k] > 0 else 1.0
    Q1 = 1.0 / (R1 * wp ** n1 + 1e-12)
    Q2 = 1.0 / (R2 * (wp / 20) ** n2 + 1e-12)   # 第二弧低频
    return [Rs, R1, Q1, n1, R2, Q2, n2]


def _inv_two(th):
    Rs, R1, Q1, n1, R2, Q2, n2 = th
    w1 = (1.0 / (R1 * Q1)) ** (1.0 / n1) if R1 * Q1 > 0 else float("nan")
    w2 = (1.0 / (R2 * Q2)) ** (1.0 / n2) if R2 * Q2 > 0 else float("nan")
    return {"n_arcs": 2, "R1": R1, "R2": R2,
            "char_freq1_Hz": w1 / (2 * np.pi), "char_freq2_Hz": w2 / (2 * np.pi),
            "freq_separation_decades": abs(np.log10(max(w1, 1e-9) / max(w2, 1e-9)))}


M3_two = MechanismModel(
    "two_population", ["Rs", "R1", "Q1", "n1", "R2", "Q2", "n2"], _fwd_two,
    bounds_lo=[0.0, 1e-3, 1e-15, 0.4, 1e-3, 1e-15, 0.4],
    bounds_hi=[1e9, 1e12, 1e3, 1.05, 1e12, 1e3, 1.05],
    p0_fn=_p0_two, invariants=_inv_two,
    failure_modes=lambda th: (["nonpassive_resistance"] if (th[1] <= 0 or th[4] <= 0) else []))


MECHANISMS: Dict[str, MechanismModel] = {
    "single_bulk": M1_single, "bulk_electrode": M2_bulk_elec, "two_population": M3_two,
}


# --------------------------------------------------------------------------- #
# 拟合真实谱 + 物理检查 + Fisher 可观测性(谱级)
# --------------------------------------------------------------------------- #
@dataclass
class SpectrumFit:
    model: str
    theta: np.ndarray
    chi2: float
    rss: float
    aic: float
    weighted_resid_rms: float
    passive: bool
    failures: List[str]
    invariants: Dict[str, Any]
    lambda_min: float
    condition_number: float
    ok: bool = True


def _complex_residual(model: MechanismModel, theta, freq, zr, zi, weight):
    Z = model.impedance_forward_operator(freq, theta)
    r = np.concatenate([(Z.real - zr) * weight, (Z.imag - zi) * weight])
    return r


def _data_adaptive_bounds(model: MechanismModel, zr, zi):
    """把电阻类参数(名字以 R 开头)的上界收缩到数据尺度,杜绝
    'Rb→∞ 让 R∥CPE 退化成纯 CPE 去拟合电极尾巴' 的非物理简并。
    电阻不可能比实测阻抗实部跨度大 50× 以上。"""
    zr_span = float(np.max(zr) - np.min(zr))
    r_cap = max(50.0 * max(zr_span, 1.0), 1e3)
    lo = list(model.bounds_lo); hi = list(model.bounds_hi)
    for i, name in enumerate(model.param_names):
        if name.startswith("R"):
            hi[i] = min(hi[i], r_cap)
    return lo, hi


def fit_spectrum(model: MechanismModel, freq, zr, zi, *,
                 weighting: str = "modulus") -> SpectrumFit:
    """对真实谱(freq,zr,zi)拟合机制模型。weighting='modulus':1/|Z|(标准 EIS 权重)。"""
    freq = np.asarray(freq, float); zr = np.asarray(zr, float); zi = np.asarray(zi, float)
    mod = np.hypot(zr, zi)
    w = (1.0 / np.clip(mod, 1e-12, None)) if weighting == "modulus" else np.ones_like(mod)
    lo, hi = _data_adaptive_bounds(model, zr, zi)
    theta0 = np.array(model.p0_fn(freq, zr, zi), float)
    theta0 = np.clip(theta0, lo, hi)
    try:
        sol = least_squares(
            lambda th: _complex_residual(model, th, freq, zr, zi, w),
            theta0, bounds=(lo, hi),
            method="trf", max_nfev=20000)
        theta = sol.x
        Z = model.impedance_forward_operator(freq, theta)
        resid_r = np.concatenate([Z.real - zr, Z.imag - zi])
        wresid = np.concatenate([(Z.real - zr) * w, (Z.imag - zi) * w])
        rss = float(np.sum(resid_r ** 2))
        chi2 = float(np.sum(wresid ** 2))
        n = 2 * len(freq); k = model.k
        aic = n * math.log(rss / n) + 2 * k + (2 * k * (k + 1)) / max(n - k - 1, 1) if rss > 0 else -np.inf
        wrms = float(np.sqrt(np.mean(wresid ** 2)))
        # 被动性:整段 Re Z>0
        passive = bool(np.all(Z.real > 0))
        fails = model.predicted_failure_modes(theta)
        inv = model.predicted_invariants(theta)
        # Fisher λ_min(谱级):数值 Jacobian of 复残差 → JᵀJ
        lam_min, cond = _fisher_lambda_min(model, theta, freq, w)
        return SpectrumFit(model.name, theta, chi2, rss, aic, wrms, passive,
                           fails, inv, lam_min, cond, ok=True)
    except Exception:
        return SpectrumFit(model.name, theta0, float("nan"), float("nan"), float("inf"),
                           float("nan"), False, ["fit_failed"], {}, float("nan"),
                           float("inf"), ok=False)


def _fisher_lambda_min(model, theta, freq, w, eps=1e-6):
    """数值 Jacobian → I=JᵀJ(同方差近似),返回 λ_min/cond(参数可观测性)。"""
    omega = 2 * np.pi * np.asarray(freq, float)
    base = model.forward(omega, theta)
    cols = []
    for i in range(len(theta)):
        dth = np.array(theta, float); h = eps * max(abs(theta[i]), 1e-8)
        dth[i] += h
        dZ = (model.forward(omega, dth) - base) / h
        cols.append(np.concatenate([dZ.real * w, dZ.imag * w]))
    Jm = np.vstack(cols).T            # [2n, k]
    FIM = Jm.T @ Jm
    try:
        ev = np.linalg.eigvalsh(FIM)
        ev = np.clip(ev, 0, None)
        lam_min = float(ev[0]); lam_max = float(ev[-1])
        cond = float(lam_max / lam_min) if lam_min > 0 else float("inf")
        return lam_min, cond
    except Exception:
        return float("nan"), float("inf")


def fit_all_mechanisms(freq, zr, zi) -> Dict[str, SpectrumFit]:
    return {name: fit_spectrum(m, freq, zr, zi) for name, m in MECHANISMS.items()}


def aic_weights(fits: Dict[str, SpectrumFit]) -> Dict[str, float]:
    """AIC 权重(机制谱级后验近似):w_i ∝ exp(-ΔAIC/2)。"""
    valid = {n: f.aic for n, f in fits.items() if f.ok and np.isfinite(f.aic)}
    if not valid:
        return {n: float("nan") for n in fits}
    amin = min(valid.values())
    raw = {n: math.exp(-(a - amin) / 2) for n, a in valid.items()}
    s = sum(raw.values())
    out = {n: (raw.get(n, 0.0) / s if s > 0 else 0.0) for n in fits}
    return out
