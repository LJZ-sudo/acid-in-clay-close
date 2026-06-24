# -*- coding: utf-8 -*-
"""按用途/主张分级的准入引擎（WP1 / SciTX 2.0）。

GPT-3 指出当前 C_M 是"全局布尔",C_E 未绑定具体主张。本模块把它们升级为:
  - C_M(intended_use)：同一条谱对"存观察 / 估单点 / 判断点 / 比模型 / 更新 BO / 机制一致性"
    的计量资格不同 —— 分级矩阵 U1–U6(docx §4.6 结构)。
  - C_E(claim_id, max_level)：证据能否支持某条具体主张,以及最高可达等级(EIS-only 封顶 C4)。

**诚实边界**:本模块只编码"哪类证据门控哪种用途"的**结构**,消费的是上游已算的布尔/准入信号
(M1-1 Rb 方法间一致性、M1-2 合成 FPR、M1-4 证据准入、M1-7 可辨识性、数据集独立性);
**不臆造任何材料学数值阈值**。缺少更高阶证据时,对应用途保守判 REJECT/CONDITIONAL。
底层复用 M1-4 evidence_admission.assess_admissibility。
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

# 复用 M1-4 证据准入(与 commit_controller 同样的接入方式)
_ANALYSIS_DIR = Path(__file__).resolve().parents[2] / "stage0_measurement" / "modules" / "analysis"
if str(_ANALYSIS_DIR) not in sys.path:
    sys.path.insert(0, str(_ANALYSIS_DIR))


class IntendedUse:
    """EIS 证据的六类用途(docx §4.6)。"""
    PRESERVE_OBSERVATION = "U1"        # 保存描述性观察
    ESTIMATE_POINT_CONDUCTIVITY = "U2" # 估单点 Rb/电导
    ESTIMATE_BREAKPOINT = "U3"         # 估温度断点
    COMPARE_TRANSPORT_MODELS = "U4"    # 比 Arrhenius/Mott/VTF 经验模型
    UPDATE_BO = "U5"                   # 更新 BO
    MECHANISTIC_CONSISTENCY = "U6"     # 支持机制一致性主张
    ALL = [PRESERVE_OBSERVATION, ESTIMATE_POINT_CONDUCTIVITY, ESTIMATE_BREAKPOINT,
           COMPARE_TRANSPORT_MODELS, UPDATE_BO, MECHANISTIC_CONSISTENCY]


# 每种用途在 EIS-only 下的主张等级上限(硬封顶 C4,不声称结构/因果)。
USE_MAX_CLAIM_LEVEL: Dict[str, str] = {
    IntendedUse.PRESERVE_OBSERVATION: "C1",
    IntendedUse.ESTIMATE_POINT_CONDUCTIVITY: "C1",
    IntendedUse.UPDATE_BO: "C2",
    IntendedUse.ESTIMATE_BREAKPOINT: "C3",
    IntendedUse.COMPARE_TRANSPORT_MODELS: "C3",
    IntendedUse.MECHANISTIC_CONSISTENCY: "C4",
}

ADMIT = "ADMIT"
CONDITIONAL = "CONDITIONAL"
REJECT = "REJECT"
CONTESTED = "CONTESTED"          # 物理/分析冲突(如断点与 Rb 方法切换重合),需人工裁决


@dataclass
class UseAdmission:
    intended_use: str
    status: str                  # ADMIT | CONDITIONAL | REJECT | CONTESTED
    max_claim_level: str         # C0..C4
    reason_codes: List[str] = field(default_factory=list)

    def admitted(self) -> bool:
        return self.status in (ADMIT, CONDITIONAL)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intended_use": self.intended_use,
            "status": self.status,
            "max_claim_level": self.max_claim_level,
            "reason_codes": list(self.reason_codes),
        }


def _base_admission(signals: Dict[str, Any]):
    """调 M1-4 算底层证据状态(qa/kk/rb/uncertainty/scientific_admissibility)。"""
    import evidence_admission as EA
    return EA.assess_admissibility(
        qa_failed=bool(signals.get("qa_failed", False)),
        kk_mu_median=signals.get("kk_mu_median"),
        rb_method_spread_dex=signals.get("rb_method_spread_dex"),
        uncertainty_status=signals.get("uncertainty_status", "PARTIAL"),
        kk_testable=bool(signals.get("kk_testable", True)),
    )


def assess_use(
    intended_use: str,
    signals: Dict[str, Any],
    base: Optional[Any] = None,
) -> UseAdmission:
    """判定单条谱对某个 intended_use 的计量准入。

    signals 约定(全部可选,缺省保守):
      底层(M1-4):  qa_failed, kk_mu_median, rb_method_spread_dex, uncertainty_status, kk_testable
      U2:          geometry_valid(几何有效), rb_method_success, ecm_fallback(等效电路兜底/边界命中)
      U3:          n_series_points, method_routing_sensitivity_passed, synthetic_fpr_passed,
                   breakpoint_matches_method_switch
      U4:          model_comparison_ok, identifiable
      U5:          (用 objective_valid + scientific_admissibility==PRIMARY)
      U6:          independent_support(独立批次/反例), alternatives_present(替代解释显式存在)
    """
    if intended_use not in USE_MAX_CLAIM_LEVEL:
        raise ValueError(f"unknown intended_use '{intended_use}'; known: {IntendedUse.ALL}")
    base = base if base is not None else _base_admission(signals)
    reasons: List[str] = []
    cap = USE_MAX_CLAIM_LEVEL[intended_use]

    qa = base.qa_status
    kk = base.kk_status
    rb = base.rb_extractability
    sci = base.scientific_admissibility
    unc = base.uncertainty_status

    # ---- U1 保存描述性观察:QA 非致命即可(KK 警告允许但标记)----
    if intended_use == IntendedUse.PRESERVE_OBSERVATION:
        if qa == "FAIL":
            return UseAdmission(intended_use, REJECT, "C0", ["QA_FATAL"])
        if kk == "WARN":
            reasons.append("KK_WARN_FLAGGED")
        return UseAdmission(intended_use, ADMIT, cap, reasons or ["OK"])

    # 所有 U2+ 都要求 U1 先通过
    u1 = assess_use(IntendedUse.PRESERVE_OBSERVATION, signals, base)
    if not u1.admitted():
        return UseAdmission(intended_use, REJECT, "C0", ["U1_NOT_ADMITTED"] + u1.reason_codes)

    # ---- U2 估单点 Rb/电导 ----
    if intended_use == IntendedUse.ESTIMATE_POINT_CONDUCTIVITY:
        if rb == "FAIL":
            return UseAdmission(intended_use, REJECT, "C0", ["RB_METHOD_DISAGREEMENT"])
        if not signals.get("rb_method_success", True):
            return UseAdmission(intended_use, REJECT, "C0", ["RB_EXTRACTION_FAILED"])
        if signals.get("geometry_valid", True) is False:
            return UseAdmission(intended_use, REJECT, "C0", ["GEOMETRY_INVALID"])
        if signals.get("ecm_fallback", False) or rb == "WEAK" or unc == "UNKNOWN":
            reasons.append("DOWNGRADE_ECM_OR_WEAK_OR_UNKNOWN_UNC")
            return UseAdmission(intended_use, CONDITIONAL, cap, reasons)
        return UseAdmission(intended_use, ADMIT, cap, ["OK"])

    # U3/U4 需要 U2 通过(逐点电导可估)
    if intended_use in (IntendedUse.ESTIMATE_BREAKPOINT, IntendedUse.COMPARE_TRANSPORT_MODELS):
        u2 = assess_use(IntendedUse.ESTIMATE_POINT_CONDUCTIVITY, signals, base)
        if not u2.admitted():
            return UseAdmission(intended_use, REJECT, "C0", ["U2_NOT_ADMITTED"] + u2.reason_codes)

    # ---- U3 估温度断点 ----
    if intended_use == IntendedUse.ESTIMATE_BREAKPOINT:
        if int(signals.get("n_series_points", 0)) < 8:
            return UseAdmission(intended_use, REJECT, "C0", ["INSUFFICIENT_SERIES_POINTS"])
        # 断点与 Rb 方法切换温区重合 → CONTESTED(可能是算法伪影)
        if signals.get("breakpoint_matches_method_switch", False):
            return UseAdmission(intended_use, CONTESTED, "C0", ["BREAKPOINT_COINCIDES_RB_METHOD_SWITCH"])
        if not signals.get("method_routing_sensitivity_passed", False):
            reasons.append("METHOD_ROUTING_SENSITIVITY_NOT_PASSED")
        if not signals.get("synthetic_fpr_passed", False):
            reasons.append("SYNTHETIC_FPR_NOT_PASSED")
        if reasons:
            return UseAdmission(intended_use, CONDITIONAL, cap, reasons)
        return UseAdmission(intended_use, ADMIT, cap, ["OK"])

    # ---- U4 比模型(Arrhenius/Mott/VTF)----
    if intended_use == IntendedUse.COMPARE_TRANSPORT_MODELS:
        u3 = assess_use(IntendedUse.ESTIMATE_BREAKPOINT, signals, base)
        if u3.status == REJECT:
            return UseAdmission(intended_use, REJECT, "C0", ["U3_REJECTED"] + u3.reason_codes)
        if not signals.get("model_comparison_ok", False):
            reasons.append("MODEL_COMPARISON_NOT_DONE")
        if signals.get("identifiable", False) is False:
            # 不可辨识 → 只能报模型等价/描述符,降级
            reasons.append("NON_IDENTIFIABLE_MODEL_EQUIVALENCE_ONLY")
            return UseAdmission(intended_use, CONDITIONAL, cap, reasons)
        if reasons:
            return UseAdmission(intended_use, CONDITIONAL, cap, reasons)
        return UseAdmission(intended_use, ADMIT, cap, ["OK"])

    # ---- U5 更新 BO ----
    if intended_use == IntendedUse.UPDATE_BO:
        if sci != "PRIMARY":
            return UseAdmission(intended_use, REJECT, "C0",
                                [f"NOT_PRIMARY_ADMISSIBLE:{sci}"])
        if not base.objective_valid:
            return UseAdmission(intended_use, REJECT, "C0", ["OBJECTIVE_INVALID"])
        return UseAdmission(intended_use, ADMIT, cap, ["OK"])

    # ---- U6 机制一致性主张 ----
    if intended_use == IntendedUse.MECHANISTIC_CONSISTENCY:
        u3 = assess_use(IntendedUse.ESTIMATE_BREAKPOINT, signals, base)
        u4 = assess_use(IntendedUse.COMPARE_TRANSPORT_MODELS, signals, base)
        if not (u3.admitted() or u4.admitted()):
            return UseAdmission(intended_use, REJECT, "C0", ["NEITHER_U3_NOR_U4_ADMITTED"])
        if not signals.get("independent_support", False):
            return UseAdmission(intended_use, REJECT, "C0", ["NO_INDEPENDENT_SUPPORT"])
        if not signals.get("alternatives_present", False):
            # 没有显式替代解释 → 不允许机制一致性主张(防过度声称)
            return UseAdmission(intended_use, REJECT, "C0", ["NO_EXPLICIT_ALTERNATIVES"])
        return UseAdmission(intended_use, CONDITIONAL, cap, ["EIS_ONLY_CAP_C4"])

    raise AssertionError("unreachable")


def assess_all_uses(signals: Dict[str, Any]) -> Dict[str, UseAdmission]:
    """对一条谱一次性给出 U1–U6 全部用途的准入。"""
    base = _base_admission(signals)
    return {u: assess_use(u, signals, base) for u in IntendedUse.ALL}


# ---- C_E：绑定具体主张的证据准入(WP1-b)---------------------------------------

_C_ORDER = ["C0", "C1", "C2", "C3", "C4", "C5"]
EIS_HARD_CAP = "C4"          # EIS-only 硬封顶,绝不出 C5(结构/因果)


def _cmin(a: str, b: str) -> str:
    return a if _C_ORDER.index(a) <= _C_ORDER.index(b) else b


@dataclass
class ClaimAdmission:
    evidence_id: str
    claim_id: str
    intended_use: str
    requested_level: str
    cm_status: str               # 支撑该主张的用途准入(C_M)
    ce_status: str               # ADMIT | REJECT(是否允许支持该主张到 requested_level)
    granted_level: str           # 该证据对此主张/用途实际可达的最高等级
    reason_codes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "claim_id": self.claim_id,
            "intended_use": self.intended_use,
            "requested_level": self.requested_level,
            "cm_status": self.cm_status,
            "ce_status": self.ce_status,
            "granted_level": self.granted_level,
            "reason_codes": list(self.reason_codes),
        }


def assess_claim_admission(
    *,
    evidence_id: str,
    claim_id: str,
    intended_use: str,
    requested_level: str,
    signals: Dict[str, Any],
    base: Optional[Any] = None,
) -> ClaimAdmission:
    """证据能否支持某条具体主张到 requested_level(C_E 绑定主张)。

    规则:① 支撑该主张的 intended_use 必须计量准入(C_M);② 该用途的可达等级 ∩ EIS 硬封顶 C4
    决定 granted_level;③ requested_level 超过 granted → 过度声称,REJECT。
    CONTESTED 用途(如断点与方法切换重合)不得支持任何主张。
    """
    if requested_level not in _C_ORDER:
        raise ValueError(f"unknown claim level '{requested_level}'; known: {_C_ORDER}")
    base = base if base is not None else _base_admission(signals)
    use_adm = assess_use(intended_use, signals, base)
    reasons: List[str] = list(use_adm.reason_codes)
    cap = _cmin(use_adm.max_claim_level, EIS_HARD_CAP)

    if use_adm.status == CONTESTED:
        return ClaimAdmission(evidence_id, claim_id, intended_use, requested_level,
                              cm_status=CONTESTED, ce_status=REJECT, granted_level="C0",
                              reason_codes=reasons + ["USE_CONTESTED"])
    if not use_adm.admitted():
        return ClaimAdmission(evidence_id, claim_id, intended_use, requested_level,
                              cm_status=use_adm.status, ce_status=REJECT, granted_level="C0",
                              reason_codes=reasons + ["CM_NOT_ADMITTED"])
    if _C_ORDER.index(requested_level) > _C_ORDER.index(cap):
        return ClaimAdmission(evidence_id, claim_id, intended_use, requested_level,
                              cm_status=use_adm.status, ce_status=REJECT, granted_level=cap,
                              reason_codes=reasons + [f"OVERCLAIM_REQUESTED_{requested_level}_GT_CAP_{cap}"])
    return ClaimAdmission(evidence_id, claim_id, intended_use, requested_level,
                          cm_status=use_adm.status, ce_status=ADMIT,
                          granted_level=requested_level, reason_codes=reasons or ["OK"])


if __name__ == "__main__":
    import json
    clean = dict(qa_failed=False, kk_mu_median=0.05, rb_method_spread_dex=0.02,
                 uncertainty_status="QUANTIFIED", geometry_valid=True, rb_method_success=True,
                 n_series_points=37, method_routing_sensitivity_passed=True,
                 synthetic_fpr_passed=True, model_comparison_ok=True, identifiable=False,
                 independent_support=True, alternatives_present=True)
    for u, a in assess_all_uses(clean).items():
        print(u, "->", json.dumps(a.to_dict(), ensure_ascii=False))
