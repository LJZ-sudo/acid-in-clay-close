"""可认证 Scientific Skills + 双账户认知博弈(M5-C / B3)。

把"程序说明包"升级为带**物理适用域、前后置条件、失效模式、验证器、冻结证书、动态权限**的
可认证科学合同;控制面**只许调 VALIDATED**;组合需 `post(S_i) ⊨ pre(S_{i+1})`。
双账户:认知账户(Brier/log-loss 严格适当评分)与执行账户(风险清算)**分离**——
Agent 不能因"更自信"直接获得更多执行权。主张治理用 risk-coverage 曲线替代恒 HOLD。
"""
from .contracts import ScientificSkillContract, SkillCertificate, Lifecycle  # noqa: F401
from .registry import SkillRegistry  # noqa: F401
from .dual_account import EpistemicAccount, ExecutionAccount, RiskClearing  # noqa: F401
from .risk_coverage import risk_coverage_curve  # noqa: F401
# WP2:6 真实 EIS Skill + 三层证书 + runtime + 漂移/撤销
from .skills_eis import (  # noqa: F401
    build_eis_skill_chain, EIS_SKILL_CHAIN_ORDER, ENVIRONMENTAL_CAPABILITIES,
)
from .certificate_service import certify_skill, wilson_lower_bound, CertificationReport  # noqa: F401
from .runtime import (  # noqa: F401
    decide_execution, build_evidence_bundle, check_chain_executable, EvidenceBundle,
    ALLOW, SHADOW, HUMAN_APPROVAL, REJECT,
)
from .drift import detect_drift, DriftAction, DriftAssessment  # noqa: F401
from .revocation import revoke_skill, RevocationImpactRequest  # noqa: F401
