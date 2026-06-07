from __future__ import annotations

from pathlib import Path

from s8_stage3.config.prompt_registry import load_prompt
from s8_stage3.contracts.evidence import EvidenceBundle
from s8_stage3.contracts.hypothesis import HypothesisBoard
from s8_stage3.contracts.literature import LiteratureSurvey
from s8_stage3.contracts.mechanism import MechanismArbitrationResult
from s8_stage3.contracts.seed import SystemContext
from s8_stage3.io.writers import write_json
from s8_stage3.llm.prompt_packing import pack_for_s06


def _normalize_s06_result(raw: dict) -> dict:
    data = dict(raw or {})
    if "mechanism_card" not in data and "selected_hypothesis_id" in data:
        data = {"mechanism_card": data, "arbitration_method": "direct_mechanism_card"}
    return data


def run_s06(
    evidence: EvidenceBundle,
    mechanism_literature: LiteratureSurvey,
    gateway,
    output_dir: Path,
    *,
    hypothesis_board: HypothesisBoard | None = None,
    system_context: SystemContext | None = None,
) -> MechanismArbitrationResult:
    packed = pack_for_s06(
        evidence.model_dump(mode="json"),
        mechanism_literature.model_dump(mode="json"),
        hypothesis_board.model_dump(mode="json") if hypothesis_board else None,
        system_context.model_dump(mode="json") if system_context else None,
    )
    raw = gateway.chat_json(
        [
            {"role": "system", "content": load_prompt("s06_mechanism_arbiter")},
            {"role": "user", "content": packed},
        ],
        step="s06_mechanism_arbiter",
        output_schema=MechanismArbitrationResult,
    )
    result = MechanismArbitrationResult.model_validate(_normalize_s06_result(raw))

    if hypothesis_board is not None:
        valid_ids = {hyp.hypothesis_id for hyp in hypothesis_board.hypotheses}
        selected = result.mechanism_card.selected_hypothesis_id
        if selected not in valid_ids:
            raise RuntimeError(
                f"[S06] selected_hypothesis_id={selected!r} is not present in S04 hypotheses "
                f"{sorted(valid_ids)}."
            )

    write_json(output_dir / "04_mechanism" / "mechanism_card.json", result)
    return result
