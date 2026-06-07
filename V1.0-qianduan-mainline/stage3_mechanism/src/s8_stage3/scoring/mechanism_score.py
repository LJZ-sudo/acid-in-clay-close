"""机理评分：对 MechanismCard 的仲裁结果做量化评分。"""
from __future__ import annotations

from s8_stage3.contracts.mechanism import MechanismCard


def score_mechanism_card(card: MechanismCard) -> dict:
    """对机理仲裁结果的内在一致性进行评分。"""
    confidence_score = card.confidence
    evidence_breadth = min(1.0, len(card.evidence_alignment) / 5)
    literature_breadth = min(1.0, len(card.literature_support) / 3)
    caveat_penalty = 0.05 * min(len(card.caveats), 4)
    has_t_explanation = 1.0 if card.t_arc_t_break_explanation else 0.0

    composite = (
        0.40 * confidence_score
        + 0.20 * evidence_breadth
        + 0.15 * literature_breadth
        + 0.15 * has_t_explanation
        - caveat_penalty
    )
    return {
        "mechanism_label": card.mechanism_label,
        "confidence": card.confidence,
        "composite_score": round(max(0.0, min(1.0, composite)), 3),
        "evidence_breadth": round(evidence_breadth, 3),
        "literature_breadth": round(literature_breadth, 3),
        "has_t_arc_explanation": bool(card.t_arc_t_break_explanation),
    }
