from __future__ import annotations

from pathlib import Path

from s8_stage3.config.prompt_registry import load_prompt
from s8_stage3.contracts.design_principle import TransferableDesignPrincipleSet
from s8_stage3.contracts.evidence import EvidenceBundle
from s8_stage3.contracts.mechanism import MechanismArbitrationResult
from s8_stage3.io.writers import write_json


def _pack_prompt(arbitration: MechanismArbitrationResult, evidence: EvidenceBundle) -> str:
    mech = arbitration.mechanism_card
    lines = [
        "Winning mechanism:",
        f"selected_hypothesis_id: {mech.selected_hypothesis_id}",
        f"mechanism_label: {mech.mechanism_label}",
        f"justification: {mech.justification[:800]}",
        f"t_arc_t_break_explanation: {mech.t_arc_t_break_explanation[:400]}",
        f"eis_evolution_explanation: {mech.eis_evolution_explanation[:400]}",
        "",
        "EvidenceCards (S03):",
    ]
    for card in evidence.evidence_cards[:30]:
        lines.append(f"  [{card.card_id}] {card.statement[:280]} (confidence={card.confidence})")
    lines.append("")
    lines.append("Return the JSON object described in the system prompt.")
    return "\n".join(lines)


def _normalize_s06b_result(raw: dict) -> dict:
    data = dict(raw or {})
    if "principles" not in data:
        for alias in ("transferable_design_principles", "design_principles"):
            if alias in data:
                data["principles"] = data.pop(alias)
                break
    return data


def run_s06b(
    arbitration: MechanismArbitrationResult,
    evidence: EvidenceBundle,
    gateway,
    output_dir: Path,
    system_context=None,
) -> TransferableDesignPrincipleSet:
    raw = gateway.chat_json(
        [
            {"role": "system", "content": load_prompt("s06b_design_principle_extractor")},
            {"role": "user", "content": _pack_prompt(arbitration, evidence)},
        ],
        step="s06b_design_principle_extractor",
        output_schema=TransferableDesignPrincipleSet,
    )
    principles = TransferableDesignPrincipleSet.model_validate(_normalize_s06b_result(raw))
    if len(principles.principles) < 3:
        raise RuntimeError(
            f"[S06b] Only {len(principles.principles)} design principles returned; "
            "at least 3 are required."
        )
    write_json(output_dir / "04b_design_principles" / "design_principles.json", principles)
    return principles
