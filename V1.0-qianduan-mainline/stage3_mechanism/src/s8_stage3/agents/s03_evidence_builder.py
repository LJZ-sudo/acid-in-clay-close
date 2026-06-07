from __future__ import annotations

from pathlib import Path
from typing import Any

from s8_stage3.contracts.evidence import EvidenceBundle, EvidenceCard
from s8_stage3.contracts.seed import Stage3SeedBundle
from s8_stage3.io.writers import write_json


_STRENGTH_TO_CONFIDENCE = {
    "strong": 0.90,
    "moderate": 0.72,
    "weak": 0.55,
    "tentative": 0.35,
}

_LAYER_TO_CLAIM_TYPE = {
    "composition_trend": "observation",
    "temperature_transport": "observation",
    "model_competition": "interpretation",
    "eis_morphology": "observation",
    "mechanism_question": "question",
    "validation_gap": "question",
    "data_quality": "observation",
}


def _stringify_metrics(metrics: dict[str, Any]) -> dict[str, str]:
    return {str(k): "" if v is None else str(v) for k, v in metrics.items()}


def _v2_supporting_metrics(ev: dict) -> dict[str, Any]:
    metrics = ev.get("supporting_metrics")
    if isinstance(metrics, dict):
        return dict(metrics)
    legacy_metrics = ev.get("support_metrics")
    if isinstance(legacy_metrics, dict):
        return dict(legacy_metrics)
    return {}


def _evidence_v2_to_card(ev: dict, idx: int) -> EvidenceCard | None:
    if ev.get("safe_for_stage3") is False:
        return None
    statement = str(
        ev.get("statement")
        or ev.get("claim_text")
        or ev.get("summary")
        or ev.get("title")
        or ""
    ).strip()
    if not statement:
        return None

    evidence_id = str(ev.get("evidence_id") or ev.get("id") or f"EV{idx}")
    layer = str(ev.get("layer") or ev.get("evidence_layer") or "")
    strength = str(ev.get("strength") or ev.get("confidence_label") or "moderate").lower()
    confidence = ev.get("confidence")
    try:
        confidence_f = float(confidence) if confidence is not None else _STRENGTH_TO_CONFIDENCE.get(strength, 0.65)
    except (TypeError, ValueError):
        confidence_f = _STRENGTH_TO_CONFIDENCE.get(strength, 0.65)
    confidence_f = max(0.0, min(1.0, confidence_f))

    metrics = _v2_supporting_metrics(ev)
    metrics.setdefault("v2_evidence_id", evidence_id)
    if layer:
        metrics.setdefault("v2_layer", layer)
    if strength:
        metrics.setdefault("v2_strength", strength)

    return EvidenceCard(
        card_id=f"V2-E{idx}",
        claim_type=_LAYER_TO_CLAIM_TYPE.get(layer, "observation"),
        statement=statement,
        source_sample_ids=[str(x) for x in (ev.get("supporting_sample_ids") or ev.get("sample_ids") or [])],
        support_metrics=_stringify_metrics(metrics),
        counterexamples=[str(x) for x in (ev.get("limitations") or ev.get("counterexamples") or [])],
        language_guardrail=(
            str(ev.get("language_guardrail") or ev.get("usage_policy") or "")
            or "Authoritative Stage2 V2 evidence; do not promote beyond its stated scope."
        ),
        allowed_downstream_use=["hypothesis_generation", "mechanism_arbitration", "claim_audit"],
        confidence=confidence_f,
    )


def _derived_cards(seed: Stage3SeedBundle, start: int) -> list[EvidenceCard]:
    cards: list[EvidenceCard] = []
    counter = start

    wide_range_segments = [s for s in seed.seed_segments if s.is_wide_range]
    if wide_range_segments:
        counter += 1
        cards.append(
            EvidenceCard(
                card_id=f"E{counter}",
                claim_type="observation",
                statement=(
                    "Conductivity was measured over a wide temperature span in "
                    f"{len(wide_range_segments)} fitted segments."
                ),
                source_sample_ids=sorted({s.sample_id for s in wide_range_segments}),
                support_metrics={"wide_range_segment_count": str(len(wide_range_segments))},
                language_guardrail="Wide-temperature coverage is observational; it is not a mechanism proof.",
                allowed_downstream_use=["hypothesis_generation", "mechanism_arbitration"],
                confidence=0.85,
            )
        )

    sample_segment_counts: dict[str, int] = {}
    all_ea: list[float] = []
    for seg in seed.seed_segments:
        sample_segment_counts[seg.sample_id] = sample_segment_counts.get(seg.sample_id, 0) + 1
        if seg.representative_ea is not None:
            all_ea.append(float(seg.representative_ea))
    multi_segment_samples = [sid for sid, count in sample_segment_counts.items() if count > 1]
    if multi_segment_samples:
        counter += 1
        cards.append(
            EvidenceCard(
                card_id=f"E{counter}",
                claim_type="observation",
                statement=(
                    "Multiple fitted transport regimes were detected in "
                    f"{len(multi_segment_samples)} samples."
                ),
                source_sample_ids=multi_segment_samples,
                support_metrics={
                    "multi_segment_sample_count": str(len(multi_segment_samples)),
                    "ea_range_ev": f"{min(all_ea):.3f}-{max(all_ea):.3f}" if all_ea else "N/A",
                },
                language_guardrail="Multiple regimes constrain hypotheses but do not uniquely identify transport type.",
                allowed_downstream_use=["hypothesis_generation", "mechanism_arbitration"],
                confidence=0.80,
            )
        )

    t_arc_before_break = [
        s
        for s in seed.seed_sample_summaries
        if s.t_arc_k is not None and s.t_break_k is not None and s.t_arc_k < s.t_break_k
    ]
    if t_arc_before_break:
        diffs = [float(s.t_break_k - s.t_arc_k) for s in t_arc_before_break]
        counter += 1
        cards.append(
            EvidenceCard(
                card_id=f"E{counter}",
                claim_type="observation",
                statement=(
                    f"T_arc is below T_break in {len(t_arc_before_break)} samples "
                    f"(mean offset {sum(diffs) / len(diffs):.1f} K)."
                ),
                source_sample_ids=[s.sample_id for s in t_arc_before_break],
                support_metrics={
                    "t_arc_lt_t_break_count": str(len(t_arc_before_break)),
                    "avg_t_diff_K": f"{sum(diffs) / len(diffs):.1f}",
                },
                language_guardrail="T_arc and T_break probe different observables; EIS is heuristic.",
                allowed_downstream_use=["mechanism_arbitration", "descriptor_extraction"],
                confidence=0.75,
            )
        )

    for hint in [h for h in seed.seed_atlas_hints if h.claim_level == "observation"][:3]:
        counter += 1
        cards.append(
            EvidenceCard(
                card_id=f"E{counter}",
                claim_type="observation",
                statement=hint.statement,
                support_metrics=_stringify_metrics(hint.support_metrics),
                language_guardrail="Stage2 atlas hint; contextual use only.",
                allowed_downstream_use=["hypothesis_generation"],
                confidence=max(0.0, min(1.0, hint.confidence * 0.8)),
            )
        )

    counter += 1
    cards.append(
        EvidenceCard(
            card_id=f"E{counter}",
            claim_type="observation",
            statement=(
                "EIS measurements provide heuristic impedance-shape information only; "
                "equivalent-circuit morphology is not uniquely determined."
            ),
            support_metrics={},
            language_guardrail="EIS is heuristic only and must not be used as stand-alone mechanism proof.",
            allowed_downstream_use=["mechanism_arbitration", "claim_audit"],
            confidence=1.0,
        )
    )
    return cards


def run_s03(
    seed: Stage3SeedBundle,
    output_dir: Path,
    *,
    strict_real_input: bool = False,
) -> EvidenceBundle:
    cards: list[EvidenceCard] = []
    v2_used = 0
    v2_skipped = 0

    if seed.stage2_seed_v2 is not None:
        for idx, ev in enumerate(seed.stage2_seed_v2.get("evidence_units") or [], start=1):
            card = _evidence_v2_to_card(ev, idx)
            if card is None:
                v2_skipped += 1
                continue
            cards.append(card)
            v2_used += 1
    elif strict_real_input:
        raise RuntimeError("[S03] strict real input requires authoritative Stage2 V2 evidence")

    if strict_real_input and v2_used == 0:
        raise RuntimeError("[S03] strict real input produced zero usable Stage2 V2 evidence cards")

    # Keep supplemental cards on the historical E1/E2/... namespace so mock
    # S04 fixtures and cached prompt contracts remain compatible. Authoritative
    # V2 cards use the separate V2-E* namespace, so there is no collision.
    derived = _derived_cards(seed, 0)
    cards.extend(derived)

    bundle = EvidenceBundle(
        step_id="s03_evidence",
        evidence_cards=cards,
        summary_notes=(
            f"Extracted {len(cards)} evidence cards from {len(seed.seed_sample_summaries)} samples "
            f"(authoritative_v2_cards={v2_used}; "
            f"derived_supplement_cards={len(derived)}; "
            f"skipped_v2_units={v2_skipped})."
        ),
    )
    write_json(output_dir / "01_evidence" / "evidence_cards.json", bundle)
    return bundle
