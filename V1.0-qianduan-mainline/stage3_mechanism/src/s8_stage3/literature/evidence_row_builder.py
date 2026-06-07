"""Evidence Row Builder — 从 PaperCard 拆出逐条 EvidenceRow。

一条 row 只承载一个核心 claim。不允许把整段 paper summary 塞进一条 row。

Confidence 规则（SDL §14.5）：
  confidence = base_weight × relevance_score
其中 base_weight 反映证据类型的先验可靠度，relevance_score 来自
PaperCard.relevance_judgement（若缺失则取 1.0）。

Mechanism tags 规则（SDL §14.4）：
  关键词命中同时做否定前瞻；命中 "not grotthuss" 这类表达时，tag 被
  移入 anti_tags（通过 EvidenceRow.weakens 字段承载，见注释）。
"""

from __future__ import annotations

import logging
import re

from s8_stage3.contracts.paper_card import PaperCard
from s8_stage3.contracts.evidence_row import EvidenceRow

logger = logging.getLogger(__name__)

_COUNTER = 0

# 各类证据类型的 confidence 基权重（经验值，作为 relevance 的先验上界）
_BASE_CONFIDENCE = {
    "mechanism_claim": 0.60,
    "direct_measurement_numeric": 0.80,
    "direct_measurement_eis": 0.50,
    "direct_measurement_arrhenius": 0.70,
    "limitation": 0.50,
}

# 机理标签关键词（lower-case regex；使用 \b 保证词边界）
_MECH_PATTERNS: list[tuple[str, str]] = [
    ("Grotthuss", r"\bgrotthuss\b|\bproton\s+hopping\b"),
    ("Vehicle", r"\bvehicular?\b|\bvehicle\s+mechanism\b"),
    ("H-bond_network", r"\bhydrogen\s+bond\b|\bh[\-\s]?bond\b"),
    ("Arrhenius", r"\barrhenius\b|\bactivation\s+energy\b"),
    ("VTF", r"\bvtf\b|\bvogel[\-\s]?(?:tammann|fulcher)\b|\bvogel[\-\s]?fulcher\b"),
]

# 否定前导词（出现在关键词前 ~30 字符内视为否定）
_NEGATION_RE = re.compile(
    r"\b(no|not|non|without|absence\s+of|against|rules?\s+out|inconsistent\s+with)\b",
    re.IGNORECASE,
)


def _next_row_id() -> str:
    global _COUNTER
    _COUNTER += 1
    return f"ER-{_COUNTER:04d}"


def reset_counter() -> None:
    global _COUNTER
    _COUNTER = 0


def _relevance_score(card: PaperCard) -> float:
    """取 PaperCard.relevance_judgement.score，缺失或非法时回退 1.0。"""
    rj = card.relevance_judgement or {}
    score = rj.get("score")
    try:
        f = float(score)
        if 0.0 <= f <= 1.0:
            return f
    except (TypeError, ValueError):
        pass
    return 1.0


def _adjust(base_key: str, relevance: float) -> float:
    """按 SDL §14.5 计算最终 confidence。"""
    base = _BASE_CONFIDENCE.get(base_key, 0.5)
    return round(max(0.0, min(1.0, base * relevance)), 3)


def _infer_mechanism_tags(text: str) -> tuple[list[str], list[str]]:
    """返回 (positive_tags, negative_tags)。

    negative_tags 表示文本明确否定该机理（e.g. "not Grotthuss"），
    这些会映射到 EvidenceRow.weakens 字段。
    """
    pos: list[str] = []
    neg: list[str] = []
    lower = text.lower()
    for tag, pattern in _MECH_PATTERNS:
        for m in re.finditer(pattern, lower):
            window_start = max(0, m.start() - 30)
            preceding = lower[window_start:m.start()]
            if _NEGATION_RE.search(preceding):
                if tag not in neg:
                    neg.append(tag)
            else:
                if tag not in pos:
                    pos.append(tag)
    return pos, neg


def _axes_to_supports(axes: dict) -> list[str]:
    """将 {axis: value} 展开为 ['axis:value'] 字符串列表，供下游聚合。"""
    out = []
    if isinstance(axes, dict):
        for k, v in axes.items():
            if k and v:
                out.append(f"{k}:{v}")
    return out


def extract_evidence_rows(card: PaperCard) -> list[EvidenceRow]:
    """从单张 PaperCard 提取所有 EvidenceRow。"""
    rows: list[EvidenceRow] = []
    paper_id = card.paper_id
    target = card.stage_target
    relevance = _relevance_score(card)

    card_supports = _axes_to_supports(card.supports_axes)
    card_conflicts = _axes_to_supports(card.conflicts_axes)

    trace = card.trace_spans[0].text_snippet[:100] if card.trace_spans else ""

    for finding in card.mechanism_relevant_findings:
        if not finding.strip():
            continue
        pos_tags, neg_tags = _infer_mechanism_tags(finding)
        rows.append(EvidenceRow(
            row_id=_next_row_id(),
            paper_id=paper_id,
            stage_target=target,
            evidence_type="mechanism_claim",
            claim_text=finding,
            normalized_claim=finding.strip(),
            mechanism_tags=pos_tags,
            supports=list(card_supports),
            weakens=(
                [f"mechanism:{t}" for t in neg_tags] + list(card_conflicts)
            ),
            confidence=_adjust("mechanism_claim", relevance),
            trace_ref=trace,
        ))

    for nf in card.numerical_findings:
        metric = nf.get("metric", "")
        value = nf.get("value", "")
        unit = nf.get("unit", "")
        conditions = nf.get("conditions", "")
        if not metric:
            continue
        claim = f"{metric} = {value} {unit}" + (f" ({conditions})" if conditions else "")
        rows.append(EvidenceRow(
            row_id=_next_row_id(),
            paper_id=paper_id,
            stage_target=target,
            evidence_type="direct_measurement",
            claim_text=claim,
            normalized_claim=claim,
            numeric_payload=nf,
            supports=list(card_supports),
            weakens=list(card_conflicts),
            confidence=_adjust("direct_measurement_numeric", relevance),
            trace_ref=trace,
        ))

    for finding in card.eis_shape_findings:
        if not finding.strip():
            continue
        rows.append(EvidenceRow(
            row_id=_next_row_id(),
            paper_id=paper_id,
            stage_target=target,
            evidence_type="direct_measurement",
            claim_text=finding,
            normalized_claim=finding.strip(),
            eis_scope="EIS morphology",
            supports=list(card_supports),
            weakens=list(card_conflicts),
            confidence=_adjust("direct_measurement_eis", relevance),
            trace_ref=trace,
        ))

    for finding in card.arrhenius_vtf_findings:
        if not finding.strip():
            continue
        pos_tags, neg_tags = _infer_mechanism_tags(finding)
        rows.append(EvidenceRow(
            row_id=_next_row_id(),
            paper_id=paper_id,
            stage_target=target,
            evidence_type="direct_measurement",
            claim_text=finding,
            normalized_claim=finding.strip(),
            arrhenius_scope="Arrhenius/VTF",
            mechanism_tags=pos_tags,
            supports=list(card_supports),
            weakens=(
                [f"mechanism:{t}" for t in neg_tags] + list(card_conflicts)
            ),
            confidence=_adjust("direct_measurement_arrhenius", relevance),
            trace_ref=trace,
        ))

    for lim in card.limitations:
        if not lim.strip():
            continue
        rows.append(EvidenceRow(
            row_id=_next_row_id(),
            paper_id=paper_id,
            stage_target=target,
            evidence_type="limitation",
            claim_text=lim,
            normalized_claim=lim.strip(),
            confidence=_adjust("limitation", relevance),
            trace_ref=trace,
        ))

    logger.info(f"[EvidenceRows] {paper_id}: {len(rows)} rows extracted (relevance={relevance})")
    return rows


def extract_rows_from_cards(cards: list[PaperCard]) -> list[EvidenceRow]:
    """批量提取。"""
    all_rows = []
    for card in cards:
        all_rows.extend(extract_evidence_rows(card))
    return all_rows
