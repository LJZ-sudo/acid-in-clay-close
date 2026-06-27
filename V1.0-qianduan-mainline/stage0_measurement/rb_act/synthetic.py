# -*- coding: utf-8 -*-
"""合成 EIS 谱（已知 Rb）用于 Rb-ACT 验证。

模型:R(RC) + 串联寄生电感 L
    Z(ω) = Rb + Rct/(1 + jω·Rct·Cdl) + jωL
高频极限 Z→Rb(实轴),故 **Rb_true = Rb 参数**(可用于覆盖率/误差验证)。
寄生电感使高频端 Z'' 由负转正,在 Z'≈Rb 处过零(模拟真实 EIS 的高频实轴截距)。

约定与 rb_fitting 一致:Z'' 容抗为负、感抗为正。
"""
from __future__ import annotations

from typing import Any, Dict, List

import numpy as np


def randles_spectrum(
    rb_ohm: float,
    rct_ohm: float,
    cdl_farad: float,
    *,
    f_min_hz: float = 1.0,
    f_max_hz: float = 1.0e6,
    n_points: int = 41,
    l_henry: float = 0.0,
    noise_frac: float = 0.0,
    seed: int = 0,
):
    """生成一条 R(RC)+L 谱。返回 (freq, z_real, z_imag)。"""
    f = np.logspace(np.log10(f_max_hz), np.log10(f_min_hz), n_points)  # 高→低
    w = 2.0 * np.pi * f
    z_arc = rct_ohm / (1.0 + 1j * w * rct_ohm * cdl_farad)
    z = rb_ohm + z_arc + 1j * w * l_henry
    zr = z.real.copy()
    zi = z.imag.copy()
    if noise_frac > 0.0:
        rng = np.random.default_rng(seed)
        scale = noise_frac * np.abs(z)
        zr = zr + rng.normal(0.0, 1.0, size=zr.shape) * scale
        zi = zi + rng.normal(0.0, 1.0, size=zi.shape) * scale
    # 返回升序频率（与下游约定一致）
    order = np.argsort(f)
    return f[order], zr[order], zi[order]


def blocking_spectrum(
    rb_ohm: float,
    c_blocking_farad: float,
    *,
    f_min_hz: float = 1.0,
    f_max_hz: float = 4.0e5,
    n_points: int = 41,
    l_henry: float = 1.0e-6,
    noise_frac: float = 0.0,
    seed: int = 0,
):
    """阻塞电极模型 Z(ω) = Rb + jωL - j/(ωC)（质子导体常见:体相电阻 + 低频阻塞尖刺）。

    Z' ≡ Rb（与频率无关）→ 四法应一致收敛到 Rb;高频 ωL 与低频 1/(ωC) 在
    ω=1/√(LC) 处使 Z'' 过零，正好锚定 Z'=Rb。Rb_true = Rb 参数。
    """
    f = np.logspace(np.log10(f_max_hz), np.log10(f_min_hz), n_points)
    w = 2.0 * np.pi * f
    z = rb_ohm + 1j * (w * l_henry - 1.0 / (w * c_blocking_farad))
    zr = z.real.copy()
    zi = z.imag.copy()
    if noise_frac > 0.0:
        rng = np.random.default_rng(seed)
        scale = noise_frac * np.abs(z)
        zr = zr + rng.normal(0.0, 1.0, size=zr.shape) * scale
        zi = zi + rng.normal(0.0, 1.0, size=zi.shape) * scale
    order = np.argsort(f)
    return f[order], zr[order], zi[order]


def make_case(label: str, rb_ohm: float, *, model: str = "randles", **kw) -> Dict[str, Any]:
    gen = blocking_spectrum if model == "blocking" else randles_spectrum
    f, zr, zi = gen(rb_ohm, **kw)
    return {
        "label": label, "rb_true_ohm": float(rb_ohm), "log10_rb_true": float(np.log10(rb_ohm)),
        "frequencies": f, "z_real": zr, "z_imag": zi,
        "thickness_cm": 0.1, "area_cm2": 1.0,
        "temperature_K": kw.get("temperature_K", 298.15),
    }


def synthetic_suite() -> List[Dict[str, Any]]:
    """覆盖"干净 / 截断 / 噪声 / 寄生 / 深冷 / 方法分歧"的可验证用例集。

    每个用例带 `expect`(REPORT/REPORT_CONDITIONAL/ABSTAIN 的预期集合)与可选 `expect_action`。
    干净/噪声/寄生/深冷用阻塞电极模型(Z'≡Rb,四法应一致收敛);方法分歧用全半圆
    (四法在 Rb 与 Rb+Rct 间分裂 → 应弃权)。
    """
    cases: List[Dict[str, Any]] = []

    # 1) 干净阻塞电极:四法一致收敛 Rb → REPORT
    c = make_case("clean_blocking", 120.0, model="blocking",
                  c_blocking_farad=1e-6, l_henry=1e-6, f_min_hz=1.0, f_max_hz=4.0e5)
    c["expect"] = {"REPORT", "REPORT_CONDITIONAL"}
    cases.append(c)

    # 2) 截断高频(无过零、谷底在端点):Rb 无高频锚点 → 建议向上扩频
    c = make_case("truncated_high", 120.0, model="randles", l_henry=0.0, rct_ohm=800.0,
                  cdl_farad=2e-7, f_min_hz=50.0, f_max_hz=2.0e4, n_points=31)
    c["expect"] = {"REPORT_CONDITIONAL", "ABSTAIN"}
    c["expect_action"] = "EXTEND_FREQ_HIGH"
    cases.append(c)

    # 3) 强噪声阻塞电极 → 粗糙度高,降级/弃权并建议重测
    c = make_case("noisy", 120.0, model="blocking", c_blocking_farad=1e-6, l_henry=1e-6,
                  f_min_hz=1.0, f_max_hz=4.0e5, noise_frac=0.45, seed=7)
    c["expect"] = {"REPORT_CONDITIONAL", "ABSTAIN"}
    c["expect_action"] = "REMEASURE"
    cases.append(c)

    # 4) 强寄生电感阻塞电极 → 高频正相位,建议换夹具
    c = make_case("parasitic", 120.0, model="blocking", c_blocking_farad=1e-6, l_henry=2e-5,
                  f_min_hz=1.0, f_max_hz=4.0e5)
    c["expect"] = {"REPORT", "REPORT_CONDITIONAL"}
    c["expect_action"] = "CHANGE_FIXTURE"
    cases.append(c)

    # 5) 深冷高阻(大 Rb)阻塞电极（L 调大使高频过零落在 4e5 Hz 窗内）
    c = make_case("deep_cold_highR", 5.0e4, model="blocking", c_blocking_farad=2e-8,
                  l_henry=1e-4, f_min_hz=1.0, f_max_hz=4.0e5)
    c["expect"] = {"REPORT", "REPORT_CONDITIONAL"}
    cases.append(c)

    # 6) 全半圆:四法在 Rb 与 Rb+Rct 间分裂 → 方法分歧 → 弃权
    c = make_case("full_arc_disagree", 120.0, model="randles", rct_ohm=800.0,
                  cdl_farad=2e-7, f_min_hz=10.0, f_max_hz=1.0e6, n_points=41, l_henry=0.0)
    c["expect"] = {"ABSTAIN"}
    cases.append(c)

    return cases
