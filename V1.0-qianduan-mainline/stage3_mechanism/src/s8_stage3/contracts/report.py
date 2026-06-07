"""报告合同 — Step 11 Report Compiler。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ReportSection(BaseModel):
    section_id: str = Field(...)
    title: str = Field(...)
    content: str = Field(...)
    subsections: list["ReportSection"] = Field(default_factory=list)


class AuditTrail(BaseModel):
    step_id: str = Field(...)
    status: str = Field("")
    notes: str = Field("")


class Stage3Report(BaseModel):
    """Stage3 最终报告。"""

    step_id: str = Field(default="s11_report")
    title: str = Field("Stage 3 Mechanism & Materials Report")
    sections: list[ReportSection] = Field(default_factory=list)
    top_candidates_summary: list[dict] = Field(default_factory=list)
    eis_disclaimer: str = Field(
        "EIS morphology is heuristic only and does not uniquely determine mechanism."
    )
    audit_trail: list[AuditTrail] = Field(default_factory=list)
