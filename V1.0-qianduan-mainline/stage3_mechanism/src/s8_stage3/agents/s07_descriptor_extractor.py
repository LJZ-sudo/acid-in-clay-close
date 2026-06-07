from __future__ import annotations

from pathlib import Path

from s8_stage3.config.prompt_registry import load_prompt
from s8_stage3.contracts.descriptor import DescriptorSheet
from s8_stage3.contracts.mechanism import MechanismArbitrationResult
from s8_stage3.io.writers import write_json
from s8_stage3.llm.prompt_packing import pack_mechanism_for_s07


_PRIORITY_ALIAS = {
    "p1": "critical",
    "p2": "important",
    "p3": "optional",
    "must-have": "critical",
    "nice-to-have": "optional",
    "high": "critical",
    "medium": "important",
    "low": "optional",
}


def _normalize_s07_result(raw: dict) -> dict:
    data = dict(raw or {})
    if "descriptors" not in data:
        for alias in ("mechanism_descriptors", "descriptor_sheet"):
            if alias in data:
                value = data.pop(alias)
                data["descriptors"] = value.get("descriptors", value) if isinstance(value, dict) else value
                break
    for desc in data.get("descriptors") or []:
        if isinstance(desc, dict):
            priority = str(desc.get("priority") or "").strip().lower()
            if priority in _PRIORITY_ALIAS:
                desc["priority"] = _PRIORITY_ALIAS[priority]
    return data


def run_s07(
    arbitration: MechanismArbitrationResult,
    gateway,
    output_dir: Path,
) -> DescriptorSheet:
    raw = gateway.chat_json(
        [
            {"role": "system", "content": load_prompt("s07_descriptor_extractor")},
            {"role": "user", "content": pack_mechanism_for_s07(arbitration.mechanism_card.model_dump(mode="json"))},
        ],
        step="s07_descriptor_extractor",
        output_schema=DescriptorSheet,
    )
    sheet = DescriptorSheet.model_validate(_normalize_s07_result(raw))
    if len(sheet.descriptors) < 3:
        raise RuntimeError(
            f"[S07] Descriptor extraction returned {len(sheet.descriptors)} descriptors; "
            "at least 3 are required."
        )
    write_json(output_dir / "05_descriptors" / "descriptor_sheet.json", sheet)
    return sheet
