from __future__ import annotations

from pathlib import Path

from s8_stage3.config.prompt_registry import load_prompt
from s8_stage3.contracts.evidence import EvidenceBundle
from s8_stage3.contracts.hypothesis import HypothesisBoard
from s8_stage3.contracts.seed import SystemContext
from s8_stage3.io.writers import write_json
from s8_stage3.llm.prompt_packing import pack_evidence_for_s04


def _normalize_s04_result(raw: dict) -> dict:
    data = dict(raw or {})
    if "hypotheses" not in data:
        for alias in ("hypothesis_board", "hyputhesis_buard", "hyputheses"):
            if alias in data:
                value = data.pop(alias)
                data["hypotheses"] = value.get("hypotheses", value) if isinstance(value, dict) else value
                break
    return data


def run_s04(
    evidence: EvidenceBundle,
    gateway,
    output_dir: Path,
    system_context: SystemContext | None = None,
) -> HypothesisBoard:
    system_prompt = load_prompt("s04_hypothesis_generator")
    packed = pack_evidence_for_s04(
        evidence.model_dump(mode="json"),
        system_context.model_dump(mode="json") if system_context else None,
    )
    raw = gateway.chat_json(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": packed},
        ],
        step="s04_hypothesis_generator",
        output_schema=HypothesisBoard,
    )
    board = HypothesisBoard.model_validate(_normalize_s04_result(raw))

    if len(board.hypotheses) < 3:
        raise RuntimeError(
            f"[S04] Hypothesis generation returned {len(board.hypotheses)} hypotheses; "
            "at least 3 competing mechanisms are required."
        )

    valid_evidence_ids = {card.card_id for card in evidence.evidence_cards}
    invalid_refs: dict[str, dict[str, list[str]]] = {}
    for hyp in board.hypotheses:
        bad_support = [eid for eid in hyp.supporting_evidence_ids if eid and eid not in valid_evidence_ids]
        bad_conflict = [eid for eid in hyp.conflicting_evidence_ids if eid and eid not in valid_evidence_ids]
        if bad_support or bad_conflict:
            invalid_refs[hyp.hypothesis_id] = {
                "invalid_supporting_evidence_ids": bad_support,
                "invalid_conflicting_evidence_ids": bad_conflict,
            }
            hyp.supporting_evidence_ids = [
                eid for eid in hyp.supporting_evidence_ids if eid in valid_evidence_ids
            ]
            hyp.conflicting_evidence_ids = [
                eid for eid in hyp.conflicting_evidence_ids if eid in valid_evidence_ids
            ]

    if invalid_refs:
        write_json(
            output_dir / "02_hypotheses" / "hypothesis_reference_audit.json",
            {
                "valid_evidence_ids": sorted(valid_evidence_ids),
                "invalid_refs": invalid_refs,
                "repair_action": (
                    "Invalid supporting/conflicting evidence ids were pruned before "
                    "downstream arbitration."
                ),
            },
        )

    if not any(hyp.supporting_evidence_ids for hyp in board.hypotheses):
        raise RuntimeError(
            "[S04] No hypothesis retains valid supporting_evidence_ids after evidence "
            "reference audit."
        )

    write_json(output_dir / "02_hypotheses" / "hypothesis_board.json", board)
    return board
