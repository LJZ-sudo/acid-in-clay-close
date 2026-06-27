# -*- coding: utf-8 -*-
"""Rb-ACT 核心决策层（在 rb_fitting.fit_all_rb_methods 之上）。

绝不改写 legacy:本模块只**读** `fit_all_rb_methods()` 的输出，叠加后验/弃权/主动建议，
并把不确定度整理成 SciTX C_M 准入信号。legacy 的 `fit_rb_and_conductivity` 完全不动。
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from .features import extract_features, data_quality_uncertainty_dex
from .schema import (
    RbActResult, RbPosterior, ActiveRequest,
    REPORT, REPORT_CONDITIONAL, ABSTAIN,
    EXTEND_FREQ_HIGH, EXTEND_FREQ_LOW, CHANGE_FIXTURE, REMEASURE, ADD_TEMP_POINT,
)

# 复用 legacy 四法（不改写）
_ALG_DIR = Path(__file__).resolve().parents[1] / "modules" / "analysis" / "algorithms"
if str(_ALG_DIR) not in sys.path:
    sys.path.insert(0, str(_ALG_DIR))
import rb_fitting  # noqa: E402

# ---- 决策阈值（集中、可冻结进 configs；与 evidence_admission 的 Rb 阈值对齐）----
ABSTAIN_METHOD_DEX = 0.30      # 可信集方法间分歧 ≥0.30 dex → 弃权（= evidence_admission FAIL 线）
ABSTAIN_TOTAL_DEX = 0.40       # 总不确定度 ≥0.40 dex → 弃权
WARN_TOTAL_DEX = 0.15          # ≥0.15 dex → 降级 CONDITIONAL（= STRONG 线）
ROUGHNESS_REMEASURE = 0.15     # 噪声粗糙度阈值 → 建议重测


def _recommend(features: Dict[str, Any], *, abstaining: bool) -> List[ActiveRequest]:
    reqs: List[ActiveRequest] = []
    if not features.get("valid"):
        reqs.append(ActiveRequest(REMEASURE, "INVALID_SPECTRUM", "谱无法解析，建议重测"))
        return reqs
    if not features.get("has_zero_crossing") and features.get("valley_at_edge"):
        reqs.append(ActiveRequest(
            EXTEND_FREQ_HIGH, "NO_REAL_AXIS_INTERCEPT",
            "高频端未见 Z'' 过零/实轴截距，Rb 靠外推，建议向上扩频"))
    # 仅对"半圆中途被切"(低频相位居中:既非平台<25 也非阻塞尖刺>65)建议向下扩频;
    # 阻塞电极的低频尖刺(相位≈90)是质子导体常态,不建议补测。
    lfp = features.get("low_freq_phase_mean", 0.0)
    if 25.0 < lfp < 65.0:
        reqs.append(ActiveRequest(
            EXTEND_FREQ_LOW, "ARC_CUT_MIDWAY",
            "低频端落在半圆中段（既未平台也非阻塞尖刺），建议向下扩频以消歧"))
    if features.get("hf_inductive"):
        reqs.append(ActiveRequest(
            CHANGE_FIXTURE, "HF_PARASITIC_INDUCTANCE",
            "高频端正相位（寄生电感），建议检查夹具/接线/缩短引线"))
    if features.get("roughness", 0.0) > ROUGHNESS_REMEASURE:
        reqs.append(ActiveRequest(
            REMEASURE, "NOISY_SPECTRUM",
            "谱粗糙度高（噪声大），建议重测或增大积分时间"))
    # 去重（同一 action 只留首条）
    seen = set()
    out: List[ActiveRequest] = []
    for r in reqs:
        if r.action in seen:
            continue
        seen.add(r.action)
        out.append(r)
    return out


def analyze_spectrum(
    frequencies,
    z_real,
    z_imag,
    *,
    thickness_cm: float = 1.0,
    area_cm2: float = 1.0,
    temperature_K: Optional[float] = 298.15,
    fit_params: Optional[Dict[str, Any]] = None,
) -> RbActResult:
    """对单条谱做 Rb-ACT 分析，返回 RbActResult。

    几何缺省为 1.0:Rb 后验与几何无关（σ 只是线性缩放）。real 调用时传真实几何。
    """
    feats = extract_features(frequencies, z_real, z_imag)
    all_res = rb_fitting.fit_all_rb_methods(
        frequencies, z_real, z_imag,
        thickness_cm=thickness_cm, area_cm2=area_cm2,
        temperature_K=temperature_K, fit_params=fit_params,
    )
    legacy = all_res.get("legacy", {}) or {}
    legacy_rb = legacy.get("rb_ohm")
    legacy_method = legacy.get("method")
    methods = all_res.get("methods", {}) or {}
    u_data = data_quality_uncertainty_dex(feats)

    # ---- n_applicable == 0：必弃权 ----
    if not all_res.get("success"):
        post = RbPosterior(
            rb_ohm=None, log10_rb=None, ci95_low_ohm=None, ci95_high_ohm=None,
            sigma_log10_total=float(u_data), u_method_dex=0.0, u_data_dex=float(u_data),
            n_applicable=0, n_credible=0, weights={})
        signals = {
            "rb_method_spread_dex": None, "rb_method_success": False,
            "ecm_fallback": False, "uncertainty_status": "UNKNOWN",
        }
        delta = {
            "legacy_reported": legacy_rb is not None, "rb_act_reported": False,
            "abstain_while_legacy_reported": legacy_rb is not None,
            "delta_log10": None, "method_changed": None,
        }
        return RbActResult(
            decision=ABSTAIN, posterior=post, legacy_rb_ohm=legacy_rb,
            legacy_method=legacy_method,
            abstain_reasons=["NO_APPLICABLE_METHOD", all_res.get("error") or "no_method"],
            active_requests=_recommend(feats, abstaining=True),
            features=feats, admission_signals=signals, delta=delta,
            temperature_K=temperature_K)

    ens = all_res.get("ensemble", {}) or {}
    log10_rb = ens.get("log10_rb")
    rb_ohm = ens.get("rb_ohm")
    u_method = float(ens.get("method_spread_dex") or 0.0)
    sigma_total = float(np.sqrt(u_method ** 2 + u_data ** 2))

    # 可信集权重 + 最优可信方法
    credible = {m: v for m, v in methods.items() if v.get("credible")}
    wsum = sum(max(v.get("fit_quality", 0.0), 1e-6) for v in credible.values()) or 1.0
    weights = {m: max(v.get("fit_quality", 0.0), 1e-6) / wsum for m, v in credible.items()}
    best_credible = max(credible, key=lambda m: credible[m].get("fit_quality", 0.0)) if credible else None
    ecm_fallback = (best_credible == "equivalent_circuit") or (legacy_method == "equivalent_circuit")

    ci_low = ci_high = None
    if log10_rb is not None:
        ci_low = float(10.0 ** (log10_rb - 1.96 * sigma_total))
        ci_high = float(10.0 ** (log10_rb + 1.96 * sigma_total))

    post = RbPosterior(
        rb_ohm=rb_ohm, log10_rb=log10_rb, ci95_low_ohm=ci_low, ci95_high_ohm=ci_high,
        sigma_log10_total=sigma_total, u_method_dex=u_method, u_data_dex=float(u_data),
        n_applicable=int(all_res.get("n_applicable", 0)), n_credible=len(credible),
        weights=weights)

    # ---- 决策 ----
    abstain_reasons: List[str] = []
    if u_method >= ABSTAIN_METHOD_DEX:
        abstain_reasons.append(f"METHOD_DISAGREEMENT_{u_method:.2f}dex")
    if sigma_total >= ABSTAIN_TOTAL_DEX:
        abstain_reasons.append(f"TOTAL_UNCERTAINTY_{sigma_total:.2f}dex")

    if abstain_reasons:
        decision = ABSTAIN
    elif (ecm_fallback or sigma_total >= WARN_TOTAL_DEX
          or feats.get("valley_at_edge") or not feats.get("has_zero_crossing")):
        decision = REPORT_CONDITIONAL
    else:
        decision = REPORT

    signals = {
        "rb_method_spread_dex": u_method,
        "rb_method_success": decision != ABSTAIN,
        "ecm_fallback": bool(ecm_fallback),
        "uncertainty_status": "QUANTIFIED",
    }

    delta: Dict[str, Any] = {
        "legacy_reported": legacy_rb is not None,
        "rb_act_reported": decision != ABSTAIN,
        "abstain_while_legacy_reported": decision == ABSTAIN and legacy_rb is not None,
        "method_changed": (best_credible != legacy_method) if legacy_method else None,
        "delta_log10": None,
        "large_shift": False,
    }
    if legacy_rb and legacy_rb > 0 and log10_rb is not None:
        d = float(log10_rb - np.log10(legacy_rb))
        delta["delta_log10"] = d
        delta["large_shift"] = bool(abs(d) > 0.10)

    return RbActResult(
        decision=decision, posterior=post, legacy_rb_ohm=legacy_rb,
        legacy_method=legacy_method, abstain_reasons=abstain_reasons,
        active_requests=_recommend(feats, abstaining=False),
        features=feats, admission_signals=signals, delta=delta,
        temperature_K=temperature_K)


def analyze_series(spectra: List[Dict[str, Any]]):
    """对一组温度谱做 Rb-ACT，并给出序列级主动建议（ADD_TEMP_POINT）。

    spectra: 每项 dict(frequencies, z_real, z_imag, [thickness_cm, area_cm2, temperature_K])。
    返回 (results: List[RbActResult], series_requests: List[ActiveRequest])。
    """
    results: List[RbActResult] = []
    for s in spectra:
        results.append(analyze_spectrum(
            s["frequencies"], s["z_real"], s["z_imag"],
            thickness_cm=s.get("thickness_cm", 1.0),
            area_cm2=s.get("area_cm2", 1.0),
            temperature_K=s.get("temperature_K", 298.15)))

    series_reqs: List[ActiveRequest] = []
    temps = [r.temperature_K for r in results if r.temperature_K is not None]
    # 弃权点附近建议加测
    abstain_temps = [r.temperature_K for r in results
                     if r.decision == ABSTAIN and r.temperature_K is not None]
    if abstain_temps:
        series_reqs.append(ActiveRequest(
            ADD_TEMP_POINT, "ABSTENTION_CLUSTER",
            f"在弃权温点附近加测以消解歧义: {sorted(set(round(t, 1) for t in abstain_temps))}"))
    # 温度间隔过大处建议插点
    if len(temps) >= 3:
        ts = sorted(temps)
        gaps = [ts[i + 1] - ts[i] for i in range(len(ts) - 1)]
        med = float(np.median(gaps)) if gaps else 0.0
        big = [(ts[i], ts[i + 1]) for i in range(len(gaps)) if med > 0 and gaps[i] > 2.5 * med]
        if big:
            series_reqs.append(ActiveRequest(
                ADD_TEMP_POINT, "SPARSE_TEMPERATURE_GRID",
                f"温度网格在 {big} 处过疏，建议插点（尤其疑似断点区间）"))
    return results, series_reqs
