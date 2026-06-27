# -*- coding: utf-8 -*-
"""Rb-ACT 离线 shadow 运行 + 合成验证（R0 接入门:只观察，不影响任何产物）。

- `shadow_run(spectra)`:对一批谱并行跑 legacy(集成) 与 Rb-ACT，产 `delta_report`
  (翻转计数 / 弃权计数 / 最大 log10 偏移 / 逐条对照)。legacy 值原样保留，绝不覆盖。
- `validate_synthetic(suite)`:在已知 Rb 的合成谱上量化点估误差、95% 区间覆盖率、
  弃权命中、主动建议命中——对应 `OPTIMIZATION_EXECUTION_PLAN §10.6` 的 Rb-ACT 验收项。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np

from .schema import ABSTAIN
from .synthetic import randles_spectrum, blocking_spectrum, synthetic_suite
from .skill import analyze_spectrum


def shadow_run(spectra: List[Dict[str, Any]]) -> Dict[str, Any]:
    """对一批谱做 legacy↔Rb-ACT 双跑，返回 delta_report。

    spectra: 每项 dict(frequencies, z_real, z_imag, [thickness_cm, area_cm2, temperature_K, label])。
    """
    items: List[Dict[str, Any]] = []
    n_abstain = n_report = n_conditional = 0
    n_flip_method = n_large_shift = n_abstain_vs_legacy = 0
    max_abs_delta = 0.0

    for s in spectra:
        r = analyze_spectrum(
            s["frequencies"], s["z_real"], s["z_imag"],
            thickness_cm=s.get("thickness_cm", 1.0),
            area_cm2=s.get("area_cm2", 1.0),
            temperature_K=s.get("temperature_K", 298.15))
        if r.decision == ABSTAIN:
            n_abstain += 1
        elif r.decision == "REPORT_CONDITIONAL":
            n_conditional += 1
        else:
            n_report += 1
        d = r.delta or {}
        if d.get("method_changed"):
            n_flip_method += 1
        if d.get("large_shift"):
            n_large_shift += 1
        if d.get("abstain_while_legacy_reported"):
            n_abstain_vs_legacy += 1
        if d.get("delta_log10") is not None:
            max_abs_delta = max(max_abs_delta, abs(d["delta_log10"]))
        items.append({
            "label": s.get("label"),
            "temperature_K": r.temperature_K,
            "decision": r.decision,
            "rb_act_rb_ohm": r.posterior.rb_ohm,
            "legacy_rb_ohm": r.legacy_rb_ohm,
            "sigma_log10_total": r.posterior.sigma_log10_total,
            "delta_log10": d.get("delta_log10"),
            "active_requests": [a.action for a in r.active_requests],
            "abstain_reasons": r.abstain_reasons,
        })

    return {
        "n_total": len(spectra),
        "n_report": n_report,
        "n_conditional": n_conditional,
        "n_abstain": n_abstain,
        "n_flip_method": n_flip_method,
        "n_large_shift": n_large_shift,
        "n_abstain_while_legacy_reported": n_abstain_vs_legacy,
        "max_abs_delta_log10": max_abs_delta,
        "items": items,
        "note": "R0 shadow: legacy 值原样保留，Rb-ACT 仅观察，不影响任何产物。",
    }


def validate_synthetic(
    suite: Optional[List[Dict[str, Any]]] = None,
    *,
    coverage_n: int = 60,
) -> Dict[str, Any]:
    """合成验证:点估误差 / 95% 区间覆盖率 / 弃权命中 / 主动建议命中。"""
    suite = suite if suite is not None else synthetic_suite()

    per_case: List[Dict[str, Any]] = []
    point_log10_errors: List[float] = []
    for c in suite:
        r = analyze_spectrum(
            c["frequencies"], c["z_real"], c["z_imag"],
            thickness_cm=c.get("thickness_cm", 1.0), area_cm2=c.get("area_cm2", 1.0),
            temperature_K=c.get("temperature_K", 298.15))
        log10_true = c["log10_rb_true"]
        err = (abs(r.posterior.log10_rb - log10_true)
               if r.posterior.log10_rb is not None else None)
        if err is not None:
            point_log10_errors.append(err)
        expect = c.get("expect")
        actions = [a.action for a in r.active_requests]
        per_case.append({
            "label": c["label"],
            "rb_true_ohm": c["rb_true_ohm"],
            "decision": r.decision,
            "expect": sorted(expect) if expect else None,
            "decision_in_expect": (r.decision in expect) if expect else None,
            "rb_act_rb_ohm": r.posterior.rb_ohm,
            "log10_error": err,
            "active_requests": actions,
            "expect_action": c.get("expect_action"),
            "expect_action_hit": (c["expect_action"] in actions) if c.get("expect_action") else None,
        })

    # --- 覆盖率:对阻塞电极基线做 coverage_n 次噪声实现，看 95% CI 是否覆盖真值 ---
    covered = reported = 0
    rb_true = 120.0
    for i in range(coverage_n):
        f, zr, zi = blocking_spectrum(
            rb_true, c_blocking_farad=1e-6, f_min_hz=1.0, f_max_hz=4.0e5,
            n_points=41, l_henry=1e-6, noise_frac=0.05, seed=1000 + i)
        r = analyze_spectrum(f, zr, zi, thickness_cm=0.1, area_cm2=1.0)
        if r.posterior.ci95_low_ohm is None or r.decision == ABSTAIN:
            continue
        reported += 1
        if r.posterior.ci95_low_ohm <= rb_true <= r.posterior.ci95_high_ohm:
            covered += 1
    coverage = (covered / reported) if reported else None

    return {
        "n_cases": len(suite),
        "median_point_log10_error": float(np.median(point_log10_errors)) if point_log10_errors else None,
        "max_point_log10_error": float(np.max(point_log10_errors)) if point_log10_errors else None,
        "coverage_95ci": coverage,
        "coverage_reported": reported,
        "coverage_n": coverage_n,
        "per_case": per_case,
    }
