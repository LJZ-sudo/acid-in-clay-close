"""证据评分：对 EvidenceBundle 中每张卡片进行量化评分。"""
from __future__ import annotations

from s8_stage3.contracts.evidence import EvidenceBundle, EvidenceCard


def score_evidence_card(card: EvidenceCard) -> float:
    """返回 0-1 之间的证据质量分。"""
    base = card.confidence
    # 观察型证据权重最高，解释型次之，问题型最低
    type_weight = {"observation": 1.0, "interpretation": 0.7, "question": 0.4}
    w = type_weight.get(card.claim_type, 0.7)
    # 有反例则降权
    penalty = 0.1 * min(len(card.counterexamples), 3)
    return max(0.0, min(1.0, base * w - penalty))


def score_evidence_bundle(bundle: EvidenceBundle) -> dict:
    """返回整体证据质量摘要。"""
    if not bundle.evidence_cards:
        return {"mean_score": 0.0, "n_cards": 0, "high_confidence_count": 0}
    scores = [score_evidence_card(c) for c in bundle.evidence_cards]
    return {
        "mean_score": round(sum(scores) / len(scores), 3),
        "n_cards": len(scores),
        "high_confidence_count": sum(1 for s in scores if s >= 0.7),
        "per_card": [
            {"card_id": c.card_id, "score": round(s, 3)}
            for c, s in zip(bundle.evidence_cards, scores)
        ],
    }
