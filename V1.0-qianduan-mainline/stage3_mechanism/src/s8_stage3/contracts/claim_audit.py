"""Claim Auditor 合同 (P-Stage3-J / S14)。

自动生成论文可写 claim 层级（claim ladder），并检测过度声明。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


ClaimLevel = Literal[
    "closed_loop_source_system",
    "mechanism_discovery",
    "llm_transfer_candidate",
    "prospective_validation",
    "retrospective_validation",
    "unsupported",
]


class ClaimLadderItem(BaseModel):
    claim_level: ClaimLevel
    allowed_claim: str = ""
    required_evidence: list[str] = Field(default_factory=list)
    current_evidence_status: str = ""
    forbidden_overclaim: str = ""
    caveats: list[str] = Field(default_factory=list)
    is_supported: bool = False


class ClaimAuditReport(BaseModel):
    step_id: str = Field(default="s14_claim_audit")
    run_id: str = Field(default="")
    discovery_mode: str = ""
    final_audit: bool = False
    claim_ladder: list[ClaimLadderItem] = Field(default_factory=list)
    publication_blockers: list[str] = Field(default_factory=list)
    recommended_wording: list[str] = Field(default_factory=list)
    inputs_digest: dict[str, str] = Field(default_factory=dict)
