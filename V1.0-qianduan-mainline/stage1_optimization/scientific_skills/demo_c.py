# -*- coding: utf-8 -*-
"""🅲 Demo C（M5-C Tier S 解锁演示）— 可认证 Skills + 双账户 + 风险-覆盖。

把 6 个真实确定性模块登记为带合同的 Skill,认证其一(eis-point-analysis),验证:
  ① 控制面只调 VALIDATED + 域内 → 证书外/未认证调用被拒;
  ② 组合兼容 post⊨pre(合法链通过、断链被拒);
  ③ 双账户分离:自报置信度不改变执行权;
  ④ 风险-覆盖曲线非平凡(coverage>0 受控风险)替代恒 HOLD。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict

_THIS = Path(__file__).resolve()
STAGE1 = _THIS.parents[1]
if str(STAGE1) not in sys.path:
    sys.path.insert(0, str(STAGE1))

from scientific_skills.contracts import ScientificSkillContract, Lifecycle  # noqa: E402
from scientific_skills.registry import SkillRegistry  # noqa: E402
from scientific_skills.dual_account import EpistemicAccount, RiskClearing  # noqa: E402
from scientific_skills.risk_coverage import risk_coverage_curve  # noqa: E402

REPO_ROOT = _THIS.parents[3]
OUT_DIR = REPO_ROOT / "experiments" / "scientific_skills"


def build_registry() -> SkillRegistry:
    reg = SkillRegistry()
    reg.register(ScientificSkillContract(
        skill_id="eis-point-analysis", version="2.0.0",
        applicability_domain={"temperature_C": [-90.0, 30.0]},
        preconditions=[], postconditions=["sigma_per_point", "kk_per_point"],
        failure_modes=["qa_fatal", "kk_fail", "rb_method_disagreement"],
        validators=["rb_method_invariance", "evidence_admission", "synthetic_fpr"],
        required_evidence_level="PRIMARY", autonomy_level="AUTONOMOUS"))
    reg.register(ScientificSkillContract(
        skill_id="arrhenius-sequence-analysis", version="2.0.0",
        preconditions=["sigma_per_point"], postconditions=["ea_segments", "transition_temps"],
        validators=["breakpoint_bootstrap", "no_monotonic_delete"], autonomy_level="AUTONOMOUS"))
    reg.register(ScientificSkillContract(
        skill_id="objective-extraction", version="2.0.0",
        preconditions=["sigma_per_point", "ea_segments"],
        postconditions=["combined_score", "primary_evidence"],
        validators=["objective_registry_hash"], autonomy_level="AUTONOMOUS"))
    reg.register(ScientificSkillContract(
        skill_id="mobo-recommendation", version="2.0.0",
        applicability_domain={"R": [0.0, 1.04], "N": [0.5, 1.3]},
        preconditions=["combined_score"], postconditions=["next_recipe_topk"],
        validators=["noise_aware_replay"], autonomy_level="CANARY"))
    reg.register(ScientificSkillContract(
        skill_id="llm-strategy-adviser", version="1.0.0",
        preconditions=["next_recipe_topk"], postconditions=["selected_recipe"],
        validators=["policy_ablation_baseline"], autonomy_level="ADVISORY"))  # 仅建议
    reg.register(ScientificSkillContract(
        skill_id="claim-audit", version="2.0.0",
        preconditions=["combined_score", "primary_evidence"], postconditions=["claim_ladder"],
        validators=["claim_guardrails"], autonomy_level="AUTONOMOUS"))
    return reg


def run() -> Dict[str, Any]:
    reg = build_registry()

    # ② 认证 eis-point-analysis(validators 全过 → VALIDATED + 证书)
    ok, cert = reg.certify(
        "eis-point-analysis",
        validator_results={"rb_method_invariance": True, "evidence_admission": True,
                           "synthetic_fpr": True},
        risk_estimate=0.04, risk_upper_bound=0.10, code_hash="demo")
    certified = ok and reg.state("eis-point-analysis") == Lifecycle.VALIDATED

    # ① 控制面准入
    in_domain_ok, r1 = reg.can_execute("eis-point-analysis", {"temperature_C": -30.0})
    out_of_domain, r2 = reg.can_execute("eis-point-analysis", {"temperature_C": 100.0})  # 证书外
    not_validated, r3 = reg.can_execute("llm-strategy-adviser", {})  # DRAFT,未认证
    control_plane_ok = (in_domain_ok and not out_of_domain and not not_validated)

    # ③ 组合兼容
    valid_chain, vdet = reg.check_composition(
        ["eis-point-analysis", "arrhenius-sequence-analysis", "objective-extraction", "mobo-recommendation"])
    broken_chain, bdet = reg.check_composition(["objective-extraction", "mobo-recommendation"])
    composition_ok = (valid_chain and not broken_chain)

    # ④ 双账户分离:自报置信度不改变执行权
    rc = RiskClearing(r_max=0.2)
    dual_account_separated = not rc.authority_depends_on_confidence()
    # 认知账户:过度自信的 agent 信誉被严格评分惩罚(示例)
    epi = EpistemicAccount()
    for _ in range(20):
        epi.record("overconfident", 0.99, 0)   # 总说 0.99 却错
        epi.record("calibrated", 0.55, 0)       # 诚实报中等置信
    overconfident_penalized = epi.brier("overconfident") > epi.brier("calibrated")

    # ⑤ 风险-覆盖曲线(替代恒 HOLD):一组带校准置信度+真伪的主张
    claims = [(0.95, 1), (0.92, 1), (0.90, 1), (0.85, 1), (0.80, 0),
              (0.70, 1), (0.65, 0), (0.55, 0), (0.50, 1), (0.40, 0),
              (0.95, 1), (0.30, 0)]
    rcurve = risk_coverage_curve(claims)
    risk_coverage_nontrivial = rcurve["max_coverage_at_risk_0.10"] > 0.0

    result = {
        "demo": "C - certified scientific skills + dual-account governance",
        "certified_skill": cert.to_dict() if cert else None,
        "checks": {
            "skill_certified_validated": certified,
            "control_plane_only_validated_and_in_domain": control_plane_ok,
            "out_of_cert_reject_reason": r2,
            "not_validated_reject_reason": r3,
            "composition_post_models_pre": composition_ok,
            "broken_chain_missing": [d for d in bdet if not d["ok"]],
            "dual_account_separated_confidence_not_authority": dual_account_separated,
            "overconfident_agent_penalized": overconfident_penalized,
            "risk_coverage_nontrivial_vs_const_hold": risk_coverage_nontrivial,
        },
        "risk_coverage": rcurve,
        "acceptance_pass": bool(
            certified and control_plane_ok and composition_ok
            and dual_account_separated and overconfident_penalized and risk_coverage_nontrivial),
    }
    return result


def write_report() -> Dict[str, Any]:
    res = run()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "demo_c_skill_certification_report.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    return res


if __name__ == "__main__":
    res = write_report()
    print("Demo C acceptance_pass:", res["acceptance_pass"])
    for k, v in res["checks"].items():
        print(f"  {k}: {v}")
    print(f"  risk-coverage: max_cov@risk0.10={res['risk_coverage']['max_coverage_at_risk_0.10']} "
          f"(const-HOLD coverage={res['risk_coverage']['const_hold_coverage']})")
