# -*- coding: utf-8 -*-
"""风险-覆盖曲线（M5-C）：替代 v2 恒 HOLD。

恒 HOLD = 永远拒答(coverage=0, risk=0,无意义)。选择性预测的核心是:通过拒答把风险压低,
同时报告覆盖率。给定一组带校准置信度 + 真伪标签的主张,扫阈值 τ:
  coverage(τ) = 自动放行(conf≥τ)比例;risk(τ) = 放行主张中的错误支持率。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


def risk_coverage_curve(
    claims: List[Tuple[float, int]],
    thresholds: Optional[List[float]] = None,
) -> Dict[str, Any]:
    """claims = [(confidence, is_correct)];返回曲线 + 在若干风险目标下的最大覆盖。"""
    if thresholds is None:
        thresholds = [i / 20 for i in range(21)]  # 0..1 step 0.05
    n = len(claims)
    curve = []
    for tau in thresholds:
        released = [(c, ok) for (c, ok) in claims if c >= tau]
        cov = len(released) / n if n else 0.0
        risk = (sum(1 for (_, ok) in released if ok == 0) / len(released)) if released else 0.0
        curve.append({"threshold": round(tau, 3), "coverage": round(cov, 4),
                      "risk": round(risk, 4), "n_released": len(released)})

    def max_cov_at_risk(target: float) -> float:
        best = 0.0
        for p in curve:
            if p["risk"] <= target and p["coverage"] > best:
                best = p["coverage"]
        return best

    return {
        "n_claims": n,
        "curve": curve,
        "max_coverage_at_risk_0.05": round(max_cov_at_risk(0.05), 4),
        "max_coverage_at_risk_0.10": round(max_cov_at_risk(0.10), 4),
        "const_hold_coverage": 0.0,   # 对照:恒 HOLD 覆盖率永远 0
    }
