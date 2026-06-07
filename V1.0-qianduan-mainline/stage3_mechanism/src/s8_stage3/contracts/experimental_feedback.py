"""Stage3 experimental feedback contract.

This artifact binds transfer-validation experiments back to the frozen S12
registry through S13. It is intentionally separate from the attapulgite Stage1
BO history and must not be used as optimisation training data.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator

from s8_stage3.contracts.validation import ValidationRecord


class ExperimentalFeedback(BaseModel):
    schema_version: str = Field(default="0.1.0")
    artifact_type: str = Field(default="stage3_experimental_feedback")
    created_at: str = Field(default="")
    source_system: str = Field(default="transfer_validation")
    source_mode: str = Field(default="real")
    validation_records: list[ValidationRecord] = Field(default_factory=list)
    input_hashes: dict[str, str] = Field(default_factory=dict)
    provenance: dict[str, Any] = Field(default_factory=dict)
    notes: str = Field(default="")

    @model_validator(mode="after")
    def validate_feedback_contract(self) -> "ExperimentalFeedback":
        if self.schema_version != "0.1.0":
            raise ValueError("experimental_feedback schema_version must be 0.1.0")
        if self.artifact_type != "stage3_experimental_feedback":
            raise ValueError(
                "experimental_feedback artifact_type must be stage3_experimental_feedback"
            )
        if not self.created_at:
            raise ValueError("experimental_feedback created_at is required")
        if not self.validation_records:
            raise ValueError("experimental_feedback validation_records must not be empty")
        for idx, rec in enumerate(self.validation_records):
            prefix = f"validation_records[{idx}]"
            if not rec.validation_id:
                raise ValueError(f"{prefix}.validation_id is required")
            if not (rec.candidate_id or rec.instance_id):
                raise ValueError(f"{prefix} requires candidate_id or instance_id")
            if not rec.sample_id:
                raise ValueError(f"{prefix}.sample_id is required")
            if rec.validation_timing not in {
                "prospective",
                "retrospective",
                "unknown",
            }:
                raise ValueError(f"{prefix}.validation_timing is invalid")
        return self
