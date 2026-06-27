# -*- coding: utf-8 -*-
"""Rb-ACT 谱质量特征提取（纯函数，无副作用）。

这些是**分析置信度**特征，不是材料学量:它们刻画"这条谱本身能多大程度上支撑一个
可信的 Rb"。用途:
  (a) 把"数据质量"折算成 log10(Rb) 区间的膨胀量 u_data_dex;
  (b) 触发主动测量建议(扩频/换夹具/重测);
  (c) 配合方法间分歧共同决定是否 ABSTAIN。

约定:freq 升序、Z'' 采用 `arctan2(zimag, zreal)` 物理相位（与 rb_fitting 一致）。
"""
from __future__ import annotations

from typing import Any, Dict

import numpy as np
from scipy.signal import savgol_filter


def _relative_noise(zr: np.ndarray, zi: np.ndarray) -> float:
    """局部相对噪声(对大动态范围鲁棒):平滑残差 / 局部 |Z|。

    用 Savitzky–Golay 平滑 Z'、Z''，残差按局部 |Z| 归一化后取中位数。光滑谱(即便低频
    阻塞尖刺导致 |Z| 跨数量级)残差≈0;真噪声给出 ≈ 相对噪声幅度。
    """
    n = len(zr)
    if n < 7:
        return 0.0
    win = min(9, n if n % 2 == 1 else n - 1)
    if win < 5:
        return 0.0
    try:
        s_zr = savgol_filter(zr, window_length=win, polyorder=2)
        s_zi = savgol_filter(zi, window_length=win, polyorder=2)
    except Exception:  # noqa: BLE001
        return 0.0
    resid = np.sqrt((zr - s_zr) ** 2 + (zi - s_zi) ** 2)
    scale = np.sqrt(s_zr ** 2 + s_zi ** 2) + 1e-9
    return float(np.median(resid / scale))


def extract_features(frequencies, z_real, z_imag) -> Dict[str, Any]:
    """从单条 EIS 谱抽取质量特征。失败时返回 {'valid': False, 'reason': ...}。"""
    try:
        f = np.asarray(frequencies, dtype=float)
        zr = np.asarray(z_real, dtype=float)
        zi = np.asarray(z_imag, dtype=float)
    except Exception as e:  # noqa: BLE001
        return {"valid": False, "reason": f"input_error:{e}"}

    if len(f) != len(zr) or len(f) != len(zi) or len(f) < 5:
        return {"valid": False, "reason": "insufficient_or_mismatched"}

    order = np.argsort(f)
    f, zr, zi = f[order], zr[order], zi[order]

    fmin, fmax = float(f[0]), float(f[-1])
    freq_decades = float(np.log10(fmax / fmin)) if fmin > 0 and fmax > 0 else 0.0

    # 过零点:Z'' 由负(容抗)变正(感抗) —— Rb 在测量窗内有锚点
    has_zero_crossing = bool(np.any((zi[:-1] < 0) & (zi[1:] > 0)))

    # 谷底:最接近实轴的点（|Z''| 最小）及其相对位置/深度
    abs_zi = np.abs(zi)
    zi_max = float(np.max(abs_zi)) if np.max(abs_zi) > 0 else 1.0
    valley_idx = int(np.argmin(abs_zi))
    valley_ratio = float(abs_zi[valley_idx] / zi_max)          # 越小越靠近实轴(好)
    # 谷底在数组端点 → Rb 靠外推，不确定
    valley_at_edge = bool(valley_idx <= 0 or valley_idx >= len(f) - 1)

    # 相位（物理相位，度）
    phase = np.degrees(np.arctan2(zi, zr))
    n_edge = max(1, min(5, len(f) // 4))
    low_freq_phase_mean = float(np.mean(np.abs(phase[:n_edge])))     # 低频接近 0 → 已平台
    high_freq_phase = float(np.mean(phase[-n_edge:]))               # 高频正相位 → 寄生电感

    # 高频寄生电感:高频端 Z'' 明显为正
    hf_inductive = bool(high_freq_phase > 5.0 and np.any(zi[-n_edge:] > 0))

    # 噪声粗糙度:平滑残差 / 局部 |Z|（对低频阻塞尖刺的大动态范围鲁棒）
    zmag = np.sqrt(zr ** 2 + zi ** 2)
    roughness = _relative_noise(zr, zi)

    return {
        "valid": True,
        "n_points": int(len(f)),
        "freq_min_hz": fmin,
        "freq_max_hz": fmax,
        "freq_decades": freq_decades,
        "has_zero_crossing": has_zero_crossing,
        "valley_ratio": valley_ratio,
        "valley_at_edge": valley_at_edge,
        "low_freq_phase_mean": low_freq_phase_mean,
        "high_freq_phase": high_freq_phase,
        "hf_inductive": hf_inductive,
        "roughness": roughness,
        "z_magnitude_mean": float(np.mean(zmag)),
    }


# ---- 数据质量 → 不确定度膨胀（dex），透明、可解释 ----------------------------
# 每一项都是"该缺陷给 log10(Rb) 带来多少额外不确定度"的保守工程估计；阈值集中在此，
# 便于冻结进 configs。绝不是材料学常数。
# 注意:这些只刻画 **Rb（高频实轴截距）提取置信度**;低频是平台还是阻塞尖刺
# (质子导体常见)都不算 Rb 提取缺陷,故不纳入 u_data。
_DQ_BASE_DEX = 0.02
_DQ_NO_ANCHOR_DEX = 0.12            # 无过零点且谷底在端点 → Rb 无高频锚点(外推)
_DQ_VALLEY_AT_EDGE_DEX = 0.06       # 谷底在端点 → 半圆残缺
_DQ_NARROW_BAND_DEX = 0.08          # 频宽 < 2 decade
_DQ_HIGH_VALLEY_DEX = 0.08          # 谷底离实轴远(valley_ratio 大)
_DQ_NOISE_SCALE_DEX = 0.5           # roughness 线性折算系数


def data_quality_uncertainty_dex(features: Dict[str, Any]) -> float:
    """把谱质量缺陷折算成 log10(Rb) 不确定度（dex）。纯函数。"""
    if not features.get("valid"):
        return 0.5
    u = _DQ_BASE_DEX
    no_zc = not features.get("has_zero_crossing")
    at_edge = bool(features.get("valley_at_edge"))
    if no_zc and at_edge:
        u += _DQ_NO_ANCHOR_DEX
    elif at_edge:
        u += _DQ_VALLEY_AT_EDGE_DEX
    if features.get("freq_decades", 99) < 2.0:
        u += _DQ_NARROW_BAND_DEX
    if features.get("valley_ratio", 0.0) > 0.3:
        u += _DQ_HIGH_VALLEY_DEX
    u += _DQ_NOISE_SCALE_DEX * float(features.get("roughness", 0.0))
    return float(min(u, 0.6))
