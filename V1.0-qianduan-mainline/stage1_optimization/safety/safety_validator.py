"""Stage1 chemistry safety box for acid-in-clay R/N recipe validation."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from canonical_input.campaign_parser import CampaignConfig


@dataclass
class SafetyResult:
    passed: bool
    violations: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "violations": self.violations,
            "warnings": self.warnings,
        }


class SafetyValidator:
    """Independent safety box for acid-in-clay R/N suggestions."""

    def __init__(self, campaign_config: CampaignConfig):
        self.campaign_config = campaign_config

    def validate(
        self,
        parameters: Dict[str, Any],
        physical_features: Dict[str, Any] | None = None,
    ) -> SafetyResult:
        violations: List[Dict[str, Any]] = []
        warnings: List[str] = []

        # Hard campaign bounds remain the primary safety box.
        try:
            self.campaign_config.validate_parameters(parameters)
        except ValueError as exc:
            violations.append({
                "rule_id": "campaign_bounds",
                "message": str(exc),
            })

        r_value = parameters.get("R")
        n_value = parameters.get("N")
        n_cfg = (self.campaign_config.parameters or {}).get("N", {})
        n_low = n_cfg.get("low")
        n_high = n_cfg.get("high")

        if isinstance(n_value, (int, float)):
            if isinstance(n_high, (int, float)) and n_value > n_high * 0.9:
                warnings.append(
                    f"N={n_value:.3g} 接近当前 campaign 上限 {n_high:.3g}，需关注体相酸液、低温冻结或相变风险。"
                )
            if isinstance(n_low, (int, float)) and n_value < n_low * 1.1:
                warnings.append(
                    f"N={n_value:.3g} 接近当前 campaign 下限 {n_low:.3g}，需关注酸水网络不连续和室温电导率不足。"
                )

        if r_value is not None and r_value > 0.9:
            warnings.append(
                "R > 0.9 表示酸/水比很高，需关注游离酸、腐蚀和低温结晶风险。"
            )

        if physical_features:
            ea_high = physical_features.get("ea_high_temp_eV")
            ea_low = physical_features.get("ea_low_temp_eV")
            if (
                isinstance(ea_high, (int, float))
                and isinstance(ea_low, (int, float))
                and ea_high > 0
                and ea_low > 1.5 * ea_high
            ):
                warnings.append(
                    "当前样品低温 Ea 显著高于高温 Ea，下一轮建议应优先降低体相酸液/冻结风险。"
                )

        return SafetyResult(passed=not violations, violations=violations, warnings=warnings)
