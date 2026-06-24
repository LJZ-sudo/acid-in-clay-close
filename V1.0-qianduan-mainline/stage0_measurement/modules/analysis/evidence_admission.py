# -*- coding: utf-8 -*-
"""证据准入策略（M1-4）。

把 Stage0 单一 status 拆成多维状态，并按"用途"分级（诊断/敏感性/主分析/BO/主张）。
核心不变量：**KK 失败 / QA 失败 / Rb 方法严重不一致的谱，绝不进入 BO 训练与科学主张**，
但可保留用于故障诊断（不删数据）。`objective_valid` 必须由本策略派生，禁止下游自行推断。

纯函数 + configs/evidence_admission_v2.yaml 单一真相源。不改写 legacy 管线，供 v2 与
新代码调用；与 Stage1 现有的 objective_valid 闸（state0_parser）互补。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

_THIS = Path(__file__).resolve()
MAINLINE_ROOT = _THIS.parents[3]                       # V1.0-qianduan-mainline/
POLICY_YAML = MAINLINE_ROOT / "configs" / "evidence_admission_v2.yaml"

_POLICY_CACHE: Optional[Dict[str, Any]] = None


def load_policy() -> Dict[str, Any]:
    global _POLICY_CACHE
    if _POLICY_CACHE is None:
        import yaml
        _POLICY_CACHE = yaml.safe_load(POLICY_YAML.read_text(encoding="utf-8")) or {}
    return _POLICY_CACHE


@dataclass
class EvidenceStatus:
    qa_status: str                  # PASS | FAIL
    kk_status: str                  # PASS | WARN | FAIL | NOT_TESTABLE
    rb_extractability: str          # STRONG | WEAK | FAIL
    uncertainty_status: str         # QUANTIFIED | PARTIAL | UNKNOWN
    scientific_admissibility: str   # PRIMARY | SENSITIVITY_ONLY | DIAGNOSTIC_ONLY | REJECTED
    state_key: str                  # qa_fail | kk_fail | rb_disagree | kk_warn_rb_ok | clean
    usage: Dict[str, Any]           # diagnostic / arrhenius_primary / bo_training / scientific_claim
    objective_valid: bool
    variance_multiplier: float = 1.0
    reason_codes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "qa_status": self.qa_status,
            "kk_status": self.kk_status,
            "rb_extractability": self.rb_extractability,
            "uncertainty_status": self.uncertainty_status,
            "scientific_admissibility": self.scientific_admissibility,
            "state_key": self.state_key,
            "usage": self.usage,
            "objective_valid": self.objective_valid,
            "variance_multiplier": self.variance_multiplier,
            "reason_codes": self.reason_codes,
        }


def assess_admissibility(
    *,
    qa_failed: bool,
    kk_mu_median: Optional[float],
    rb_method_spread_dex: Optional[float] = None,
    uncertainty_status: str = "PARTIAL",
    kk_testable: bool = True,
    policy: Optional[Dict[str, Any]] = None,
) -> EvidenceStatus:
    """对单个测点判定证据准入。

    Args:
        qa_failed: QA 一票否决是否触发（data_quality fatal）。
        kk_mu_median: KK 中位数残差（None 且 kk_testable=False → NOT_TESTABLE）。
        rb_method_spread_dex: M1-1 可信集方法间 log10(Rb) 标准差（None=未评估）。
        uncertainty_status: QUANTIFIED | PARTIAL | UNKNOWN（几何不确定度未知则 UNKNOWN）。
        kk_testable: 频率窗等是否足以做 KK（否则 NOT_TESTABLE）。
    """
    pol = policy or load_policy()
    kk_cfg = pol.get("kk", {})
    rb_cfg = pol.get("rb_extractability", {})
    matrix = pol.get("admission_matrix", {})

    reasons: List[str] = []

    # --- QA ---
    qa_status = "FAIL" if qa_failed else "PASS"
    if qa_failed:
        reasons.append("QA_FATAL")

    # --- KK ---
    kk_thr = float(kk_cfg.get("mu_median_threshold", 0.20))
    kk_fail_thr = float(kk_cfg.get("mu_median_fail", 0.50))
    if not kk_testable or kk_mu_median is None:
        kk_status = "NOT_TESTABLE"
    elif kk_mu_median >= kk_fail_thr:
        kk_status = "FAIL"; reasons.append("KK_INCONSISTENT")
    elif kk_mu_median >= kk_thr:
        kk_status = "WARN"; reasons.append("KK_WARNING")
    else:
        kk_status = "PASS"

    # --- Rb 可提取性（方法间一致性）---
    strong = float(rb_cfg.get("method_spread_strong_dex", 0.15))
    weak = float(rb_cfg.get("method_spread_weak_dex", 0.30))
    if rb_method_spread_dex is None:
        rb_extr = "WEAK"  # 未评估保守记 WEAK（不阻断诊断，但不当主证据）
        reasons.append("RB_SPREAD_NOT_ASSESSED")
    elif rb_method_spread_dex < strong:
        rb_extr = "STRONG"
    elif rb_method_spread_dex < weak:
        rb_extr = "WEAK"; reasons.append("RB_METHOD_WEAK")
    else:
        rb_extr = "FAIL"; reasons.append("RB_METHOD_DISAGREEMENT")

    # --- 状态键（优先级：QA > KK FAIL > Rb 严重不一致 > KK WARN > clean）---
    var_mult = 1.0
    if qa_failed:
        state = "qa_fail"
    elif kk_status == "FAIL":
        state = "kk_fail"
    elif rb_extr == "FAIL":
        state = "rb_disagree"
    elif kk_status == "WARN":
        state = "kk_warn_rb_ok"
        var_mult = float(kk_cfg.get("warn_variance_multiplier", 2.0))
    else:
        state = "clean"

    usage = dict(matrix.get(state, {}))

    # --- scientific_admissibility ---
    if state in ("qa_fail", "kk_fail"):
        sci = "DIAGNOSTIC_ONLY"
    elif state in ("rb_disagree", "kk_warn_rb_ok"):
        sci = "SENSITIVITY_ONLY"
    else:
        sci = "PRIMARY"

    # --- objective_valid（策略派生，非下游自行推断）---
    objective_valid = (sci == "PRIMARY") and (uncertainty_status in ("QUANTIFIED", "PARTIAL"))

    return EvidenceStatus(
        qa_status=qa_status,
        kk_status=kk_status,
        rb_extractability=rb_extr,
        uncertainty_status=uncertainty_status,
        scientific_admissibility=sci,
        state_key=state,
        usage=usage,
        objective_valid=objective_valid,
        variance_multiplier=var_mult,
        reason_codes=reasons,
    )


def can_enter_bo(status: EvidenceStatus) -> bool:
    """是否允许进入 BO 训练（含 variance_inflated 也算允许，但需膨胀方差）。"""
    cell = status.usage.get("bo_training", False)
    return cell is True or cell == "variance_inflated"


def can_enter_claim(status: EvidenceStatus) -> bool:
    return status.usage.get("scientific_claim", False) is True


if __name__ == "__main__":
    import json
    cases = [
        dict(qa_failed=True, kk_mu_median=0.01),
        dict(qa_failed=False, kk_mu_median=0.6),
        dict(qa_failed=False, kk_mu_median=0.25, rb_method_spread_dex=0.05),
        dict(qa_failed=False, kk_mu_median=0.05, rb_method_spread_dex=0.5),
        dict(qa_failed=False, kk_mu_median=0.05, rb_method_spread_dex=0.02, uncertainty_status="QUANTIFIED"),
    ]
    for c in cases:
        s = assess_admissibility(**c)
        print(c, "->", json.dumps(s.to_dict(), ensure_ascii=False))
