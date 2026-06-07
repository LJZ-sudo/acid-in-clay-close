"""按"轮"持久化 closed-loop 实验记录 (P-Stage1-A)。

每轮闭环 = 一次 OptimizationOrchestrator.run_optimization_loop()，记录：
    1. round_NNN_suggestion.json
        - source_mode (replay / virtual_oracle / real)
        - optimizer_suggestion (BO 推荐)
        - llm_adjusted_recipe (LLM 修正后的最终推荐)
        - safety_box (R/N 安全约束结果)
        - suggestion_hash (sha256 of canonical payload)
    2. round_NNN_stage0_result.json
        - 本轮消费的 Stage0 指标 (sigma, ea_high/low, ...)
        - measured_after_suggestion_hash (上一轮 suggestion_hash, 链式校验)
        - validity_flags
    3. round_NNN_decision_trace.json
        - rationale_summary, assumptions, risk_flags, expected_failure_modes,
          decision_basis  (避免保存完整 chain-of-thought)
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

ROUND_DIR_NAME = "closed_loop_rounds"
ROUND_FILENAME_RE = re.compile(r"^round_(\d{3,})_suggestion\.json$")


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class RoundSuggestion(BaseModel):
    round_id: int
    created_at: str
    campaign_name: str
    source_mode: str  # replay / virtual_oracle / real
    source_tag: str = "S8"
    optimizer_suggestion: Dict[str, Any] = Field(default_factory=dict)
    llm_adjusted_recipe: Dict[str, Any] = Field(default_factory=dict)
    optimizer_vs_llm_delta: Dict[str, Any] = Field(default_factory=dict)
    safety_box: Dict[str, Any] = Field(default_factory=dict)
    objective_target: Optional[str] = None
    objective_goal: Optional[str] = None
    objective_formula: Optional[str] = None
    suggestion_hash: str
    bo_provenance: Optional[Dict[str, Any]] = None
    prompt_metadata: Optional[Dict[str, Any]] = None
    llm_model_info: Optional[Dict[str, Any]] = None


class RoundStage0Result(BaseModel):
    round_id: int
    created_at: str
    sample_id: Optional[str] = None
    measured_after_suggestion_hash: Optional[str] = None
    parser_mode: str = "legacy"  # legacy | bundle
    stage0_bundle_path: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)
    metrics: Dict[str, Any] = Field(default_factory=dict)
    physical_features: Dict[str, Any] = Field(default_factory=dict)
    validity_flags: List[str] = Field(default_factory=list)


class RoundDecisionTrace(BaseModel):
    round_id: int
    created_at: str
    rationale_summary: str = ""
    assumptions: List[str] = Field(default_factory=list)
    risk_flags: List[str] = Field(default_factory=list)
    expected_failure_modes: List[str] = Field(default_factory=list)
    decision_basis: List[str] = Field(default_factory=list)
    confidence_score: Optional[float] = None
    physical_constraints_checked: Optional[bool] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str)


def _hash(payload: Any) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _next_round_id(rounds_dir: Path) -> int:
    if not rounds_dir.exists():
        return 1
    ids = []
    for p in rounds_dir.glob("round_*_suggestion.json"):
        m = ROUND_FILENAME_RE.match(p.name)
        if m:
            ids.append(int(m.group(1)))
    return (max(ids) + 1) if ids else 1


def _previous_suggestion_hash(rounds_dir: Path, current_round_id: int) -> Optional[str]:
    """链式校验：上一轮的 suggestion_hash."""
    if current_round_id <= 1 or not rounds_dir.exists():
        return None
    prev_path = rounds_dir / f"round_{current_round_id - 1:03d}_suggestion.json"
    if not prev_path.exists():
        return None
    try:
        return json.loads(prev_path.read_text(encoding="utf-8")).get("suggestion_hash")
    except (json.JSONDecodeError, OSError):
        return None


def _split_rationale(reasoning: str, warnings: List[str]) -> Dict[str, Any]:
    """从 LLM recipe 的自由文本字段抽取结构化 rationale 摘要。

    避免保留完整 chain-of-thought。仅切出第一段做 rationale_summary。
    """
    summary = (reasoning or "").strip()
    summary = re.split(r"\n{2,}", summary, maxsplit=1)[0]
    summary = summary[:600]

    risk_flags = list(warnings or [])
    return {
        "rationale_summary": summary,
        "assumptions": [],
        "risk_flags": risk_flags,
        "expected_failure_modes": [],
        "decision_basis": [],
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class RoundLogger:
    """每完成一轮 closed-loop 调用 ``write_all`` 即可。"""

    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir)
        self.rounds_dir = self.output_dir / ROUND_DIR_NAME
        self.rounds_dir.mkdir(parents=True, exist_ok=True)

    def write_all(
        self,
        *,
        campaign_name: str,
        source_mode: str,
        source_tag: str,
        optimizer_suggestion: Dict[str, Any],
        recipe_dict: Dict[str, Any],
        optimizer_vs_llm_delta: Dict[str, Any],
        safety_box: Dict[str, Any],
        objective_target: Optional[str],
        objective_goal: Optional[str],
        objective_formula: Optional[str],
        bo_provenance: Optional[Dict[str, Any]],
        prompt_metadata: Optional[Dict[str, Any]],
        llm_model_info: Optional[Dict[str, Any]],
        sample_id: Optional[str],
        parser_mode: str,
        stage0_bundle_path: Optional[str],
        stage0_parameters: Dict[str, Any],
        stage0_metrics: Dict[str, Any],
        stage0_physical_features: Dict[str, Any],
        stage0_validity_flags: List[str],
    ) -> Tuple[int, Path, Path, Path]:
        """落盘三件套并返回 (round_id, suggestion_path, stage0_path, trace_path)."""

        round_id = _next_round_id(self.rounds_dir)
        prev_hash = _previous_suggestion_hash(self.rounds_dir, round_id)

        llm_adjusted = recipe_dict.get("recommended_parameters", {})
        suggestion_payload = {
            "round_id": round_id,
            "campaign_name": campaign_name,
            "source_mode": source_mode,
            "source_tag": source_tag,
            "optimizer_suggestion": optimizer_suggestion,
            "llm_adjusted_recipe": llm_adjusted,
            "objective_target": objective_target,
            "objective_goal": objective_goal,
            "objective_formula": objective_formula,
            "safety_box": safety_box,
        }
        suggestion_hash = _hash(suggestion_payload)

        suggestion = RoundSuggestion(
            round_id=round_id,
            created_at=_utcnow(),
            campaign_name=campaign_name,
            source_mode=source_mode,
            source_tag=source_tag,
            optimizer_suggestion=optimizer_suggestion,
            llm_adjusted_recipe=llm_adjusted,
            optimizer_vs_llm_delta=optimizer_vs_llm_delta,
            safety_box=safety_box,
            objective_target=objective_target,
            objective_goal=objective_goal,
            objective_formula=objective_formula,
            suggestion_hash=suggestion_hash,
            bo_provenance=bo_provenance,
            prompt_metadata=prompt_metadata,
            llm_model_info=llm_model_info,
        )

        stage0_result = RoundStage0Result(
            round_id=round_id,
            created_at=_utcnow(),
            sample_id=sample_id,
            measured_after_suggestion_hash=prev_hash,
            parser_mode=parser_mode,
            stage0_bundle_path=stage0_bundle_path,
            parameters=stage0_parameters,
            metrics=stage0_metrics,
            physical_features=stage0_physical_features,
            validity_flags=stage0_validity_flags,
        )

        trace_payload = _split_rationale(
            reasoning=recipe_dict.get("reasoning", ""),
            warnings=recipe_dict.get("warnings", []) or [],
        )
        trace = RoundDecisionTrace(
            round_id=round_id,
            created_at=_utcnow(),
            rationale_summary=trace_payload["rationale_summary"],
            assumptions=trace_payload["assumptions"],
            risk_flags=trace_payload["risk_flags"],
            expected_failure_modes=trace_payload["expected_failure_modes"],
            decision_basis=trace_payload["decision_basis"],
            confidence_score=recipe_dict.get("confidence_score"),
            physical_constraints_checked=recipe_dict.get("physical_constraints_checked"),
        )

        suggestion_path = self.rounds_dir / f"round_{round_id:03d}_suggestion.json"
        stage0_path = self.rounds_dir / f"round_{round_id:03d}_stage0_result.json"
        trace_path = self.rounds_dir / f"round_{round_id:03d}_decision_trace.json"

        suggestion_path.write_text(suggestion.model_dump_json(indent=2), encoding="utf-8")
        stage0_path.write_text(stage0_result.model_dump_json(indent=2), encoding="utf-8")
        trace_path.write_text(trace.model_dump_json(indent=2), encoding="utf-8")

        return round_id, suggestion_path, stage0_path, trace_path
