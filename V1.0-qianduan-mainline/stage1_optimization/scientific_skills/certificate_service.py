# -*- coding: utf-8 -*-
"""三层证书服务（WP2-c / PC-Skills）。

GPT-3 指出:现有证书更像 Schema,`validator_results` 由外部喂(可手填 True)。本服务让证书
**由真实检查产生**,绝不手填:
  - 形式层(formal)：合同自洽性——validators 非空、pre/postconditions 不矛盾、适用域良构。
  - 统计层(statistical)：认证域内历史成功率/QC 通过率的 **Wilson 95% 置信下界**;样本少 → 区间宽
    → provisional + 窄包络 + 低自主等级(**不伪装高置信**,docx 风险条目)。
  - 计量层(metrological)：校准在有效期、分析版本钉住、测量不确定度已量化。

输出 validator_results 供 registry.certify 消费(三层全过才发证);并给 risk_estimate /
risk_upper_bound(喂双账户 RiskClearing)与 recommended_autonomy。
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .contracts import ScientificSkillContract


def wilson_lower_bound(n_success: int, n_total: int, z: float = 1.96) -> float:
    """成功率的 Wilson 95% 置信下界(纯数学,无 scipy);n_total=0 返回 0.0。"""
    if n_total <= 0:
        return 0.0
    p = n_success / n_total
    denom = 1 + z * z / n_total
    centre = p + z * z / (2 * n_total)
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * n_total)) / n_total)
    return max(0.0, (centre - margin) / denom)


@dataclass
class CertificationReport:
    skill_id: str
    version: str
    formal: Dict[str, Any]
    statistical: Dict[str, Any]
    metrological: Dict[str, Any]
    validator_results: Dict[str, bool]
    risk_estimate: float
    risk_upper_bound: float
    provisional: bool
    recommended_autonomy: str
    reasons: List[str] = field(default_factory=list)

    @property
    def all_layers_pass(self) -> bool:
        return bool(self.formal["ok"] and self.statistical["ok"] and self.metrological["ok"])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "skill_id": self.skill_id, "version": self.version,
            "formal": self.formal, "statistical": self.statistical,
            "metrological": self.metrological, "validator_results": self.validator_results,
            "risk_estimate": self.risk_estimate, "risk_upper_bound": self.risk_upper_bound,
            "provisional": self.provisional, "recommended_autonomy": self.recommended_autonomy,
            "reasons": self.reasons,
        }


def _check_formal(contract: ScientificSkillContract) -> Dict[str, Any]:
    checks: Dict[str, bool] = {}
    checks["has_validators"] = len(contract.validators) > 0
    checks["pre_post_disjoint"] = not (set(contract.preconditions) & set(contract.postconditions))
    checks["has_postconditions"] = len(contract.postconditions) > 0
    # 适用域良构:每个区间 [lo,hi] 且 lo<=hi
    dom_ok = True
    for _k, dom in (contract.applicability_domain or {}).items():
        if isinstance(dom, (list, tuple)) and len(dom) == 2 and all(isinstance(d, (int, float)) for d in dom):
            if dom[0] > dom[1]:
                dom_ok = False
    checks["domain_well_formed"] = dom_ok
    return {"ok": all(checks.values()), "checks": checks}


def _check_statistical(
    n_success: int, n_total: int, min_pass_rate: float, min_n: int,
) -> Dict[str, Any]:
    p_lower = wilson_lower_bound(n_success, n_total)
    p_hat = (n_success / n_total) if n_total else 0.0
    provisional = n_total < min_n
    # 通过条件:置信下界达标(样本少 → 下界自然低 → 易判 provisional/不过,诚实)
    ok = (n_total > 0) and (p_lower >= min_pass_rate)
    return {"ok": bool(ok), "n_total": n_total, "n_success": n_success,
            "p_hat": round(p_hat, 4), "p_lower_95": round(p_lower, 4),
            "min_pass_rate": min_pass_rate, "provisional": provisional}


def _check_metrological(meta: Dict[str, Any]) -> Dict[str, Any]:
    checks = {
        "calibration_valid": bool(meta.get("calibration_valid", False)),
        "analysis_version_pinned": bool(meta.get("analysis_version")),
        "uncertainty_quantified": meta.get("uncertainty_status") in ("QUANTIFIED", "PARTIAL"),
    }
    return {"ok": all(checks.values()), "checks": checks}


def certify_skill(
    contract: ScientificSkillContract,
    *,
    history: Optional[Dict[str, int]] = None,     # {"n_success": k, "n_total": n}
    metrology: Optional[Dict[str, Any]] = None,
    min_pass_rate: float = 0.8,
    min_n: int = 5,
) -> CertificationReport:
    """对一个 Skill 跑形式/统计/计量三层检查,产出 validator_results 与风险界。"""
    history = history or {"n_success": 0, "n_total": 0}
    metrology = metrology or {}
    reasons: List[str] = []

    formal = _check_formal(contract)
    statistical = _check_statistical(
        int(history.get("n_success", 0)), int(history.get("n_total", 0)), min_pass_rate, min_n)
    metrological = _check_metrological(metrology)

    all_ok = formal["ok"] and statistical["ok"] and metrological["ok"]
    provisional = statistical["provisional"] or not all_ok

    # 风险:统计层失败率 → 估计/上界(供 RiskClearing)
    p_lower = statistical["p_lower_95"]
    p_hat = statistical["p_hat"]
    risk_estimate = round(1.0 - p_hat, 4)
    risk_upper_bound = round(1.0 - p_lower, 4)        # 失败率上界 = 1 - 成功率下界

    # validator_results:三层全过才把合同里每个 validator 记 True(证书由检查产生,不可手填)
    validator_results = {v: bool(all_ok) for v in contract.validators}

    # 推荐自主等级:全过且非 provisional → 可 CANARY/AUTONOMOUS;否则 SHADOW
    if all_ok and not statistical["provisional"]:
        recommended_autonomy = "CANARY"
    elif formal["ok"] and metrological["ok"]:
        recommended_autonomy = "SHADOW"
        reasons.append("PROVISIONAL_OR_WEAK_STATISTICS_NARROW_ENVELOPE")
    else:
        recommended_autonomy = "DRAFT"
        reasons.append("FORMAL_OR_METROLOGICAL_FAILED")

    if not formal["ok"]:
        reasons.append("FORMAL_FAILED")
    if not statistical["ok"]:
        reasons.append(f"STATISTICAL_LOWER_BOUND_{p_lower}_LT_{min_pass_rate}")
    if not metrological["ok"]:
        reasons.append("METROLOGICAL_FAILED")

    return CertificationReport(
        skill_id=contract.skill_id, version=contract.version,
        formal=formal, statistical=statistical, metrological=metrological,
        validator_results=validator_results,
        risk_estimate=risk_estimate, risk_upper_bound=risk_upper_bound,
        provisional=provisional, recommended_autonomy=recommended_autonomy, reasons=reasons)
