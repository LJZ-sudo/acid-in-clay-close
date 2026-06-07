"""统一证据强度判定规则 (P-Stage2-A)。"""

from __future__ import annotations

from typing import Iterable, Literal, Optional

EvidenceStrength = Literal["strong", "moderate", "weak", "tentative"]


def assign_strength(
    n_samples: int,
    method_quality: str = "medium",
    p_value: Optional[float] = None,
    bootstrap_ci: Optional[Iterable[float]] = None,
    limitations: Optional[Iterable[str]] = None,
) -> EvidenceStrength:
    """根据样品数 / 方法质量 / 显著性 / CI / 局限项决定证据强度。

    method_quality: "high" | "medium" | "low"
    """

    method_quality = (method_quality or "medium").lower()
    n_lim = len(list(limitations)) if limitations else 0

    if (
        n_samples >= 20
        and method_quality == "high"
        and p_value is not None
        and p_value < 0.01
        and n_lim <= 1
    ):
        return "strong"

    if n_samples >= 10 and method_quality in {"high", "medium"} and n_lim <= 2:
        return "moderate"

    if n_samples >= 5:
        return "weak"

    return "tentative"


def confidence_from_strength(strength: EvidenceStrength) -> float:
    """提供一个与 V1 兼容的 confidence 数值。"""
    return {
        "strong": 0.90,
        "moderate": 0.72,
        "weak": 0.55,
        "tentative": 0.35,
    }.get(strength, 0.35)
