"""Claim Auditor 合同 (P-Stage3-J / S14)。

自动生成论文可写 claim 层级（claim ladder），并检测过度声明。
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


ClaimLevel = Literal[
    "closed_loop_source_system",
    "mechanism_discovery",      # DEPRECATED 命名(M2-5/G6):字段名暗示"发现机理"超额。
    "mechanism_consistency",    # 首选命名:EIS-only 仅能到"机理一致/相容",封顶 C4。
    "llm_transfer_candidate",
    "prospective_validation",
    "retrospective_validation",
    "unsupported",
]

# M2-5 / G6:命名降温映射(legacy → 首选)。两者语义等价、同封顶 C4;新代码用右侧。
CLAIM_LEVEL_PREFERRED = {
    "mechanism_discovery": "mechanism_consistency",
}

# C0–C5 conclusion-gate level (EIS-only is hard-capped at C4; C5 = structure/causal
# is forbidden for transport-only evidence). See THREE_INNOVATIONS §8.
CLevel = Literal["C0", "C1", "C2", "C3", "C4", "C5"]

# Four-state verdict replacing the binary is_supported for downstream consumers.
ClaimStatus = Literal["supported", "refuted", "inconclusive", "invalid"]


class ClaimLadderItem(BaseModel):
    claim_level: ClaimLevel
    allowed_claim: str = ""
    required_evidence: list[str] = Field(default_factory=list)
    current_evidence_status: str = ""
    forbidden_overclaim: str = ""
    caveats: list[str] = Field(default_factory=list)
    is_supported: bool = False
    # --- C0–C5 + four-state alignment (additive 2026-06-21; all default to
    #     None/empty so existing serialisation, is_supported and the frozen
    #     publication_blockers=[] are preserved). See THREE_INNOVATIONS §8. ---
    claim_level_c: Optional[CLevel] = None
    status: Optional[ClaimStatus] = None
    agent_confidence: Optional[float] = None  # pre-experiment confidence (P3: from calibrated agent)
    alternatives: list[str] = Field(default_factory=list)  # competing explanations (P3: critic-generated)
    falsifier: str = ""  # what observation would refute this claim
    applicability_domain: str = ""


class ClaimAuditReport(BaseModel):
    step_id: str = Field(default="s14_claim_audit")
    run_id: str = Field(default="")
    discovery_mode: str = ""
    final_audit: bool = False
    claim_ladder: list[ClaimLadderItem] = Field(default_factory=list)
    publication_blockers: list[str] = Field(default_factory=list)
    recommended_wording: list[str] = Field(default_factory=list)
    inputs_digest: dict[str, str] = Field(default_factory=dict)
