"""Evidence Table Builder — 将 EvidenceRow 聚合筛选为 CuratedEvidenceTable。

机制侧优先级: 明确温区 > 明确 EIS/Arrhenius > 机制比较 > 限制条件
材料侧优先级: 与 descriptors 强相关 > 有性能数值 > 有工艺/稳定性信息
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from s8_stage3.contracts.evidence_row import EvidenceRow, CuratedEvidenceTable

logger = logging.getLogger(__name__)


def build_mechanism_evidence_table(
    rows: list[EvidenceRow],
    max_rows: int = 30,
) -> CuratedEvidenceTable:
    """构建机理侧证据表。"""
    scored = [(r, _mechanism_priority_score(r)) for r in rows if r.stage_target == "mechanism"]
    scored.sort(key=lambda x: x[1], reverse=True)

    included = []
    excluded = []
    reasons = {}

    for row, score in scored:
        if len(included) < max_rows and score > 0:
            included.append(row)
        else:
            excluded.append(row)
            if score <= 0:
                reasons[row.row_id] = "Low relevance score"
            else:
                reasons[row.row_id] = f"Exceeded max_rows ({max_rows})"

    summary = (
        f"Mechanism evidence table: {len(included)} included, "
        f"{len(excluded)} excluded from {len(rows)} total rows"
    )

    return CuratedEvidenceTable(
        table_id="mechanism_evidence_table",
        stage_target="mechanism",
        included_rows=included,
        excluded_rows=excluded,
        exclusion_reasons=reasons,
        summary=summary,
    )


def build_material_evidence_table(
    rows: list[EvidenceRow],
    descriptor_keywords: list[str] | None = None,
    max_rows: int = 30,
) -> CuratedEvidenceTable:
    """构建材料侧证据表。"""
    scored = [(r, _material_priority_score(r, descriptor_keywords))
              for r in rows if r.stage_target == "materials"]
    scored.sort(key=lambda x: x[1], reverse=True)

    included = []
    excluded = []
    reasons = {}

    for row, score in scored:
        if len(included) < max_rows and score > 0:
            included.append(row)
        else:
            excluded.append(row)
            if score <= 0:
                reasons[row.row_id] = "Low relevance score"
            else:
                reasons[row.row_id] = f"Exceeded max_rows ({max_rows})"

    summary = (
        f"Material evidence table: {len(included)} included, "
        f"{len(excluded)} excluded from {len(rows)} total rows"
    )

    return CuratedEvidenceTable(
        table_id="material_evidence_table",
        stage_target="materials",
        included_rows=included,
        excluded_rows=excluded,
        exclusion_reasons=reasons,
        summary=summary,
    )


def save_evidence_table(table: CuratedEvidenceTable, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{table.table_id}.json"
    path.write_text(table.model_dump_json(indent=2), encoding="utf-8")

    excluded_path = output_dir / f"{table.table_id}_excluded.json"
    excluded_data = {
        "excluded_count": len(table.excluded_rows),
        "reasons": table.exclusion_reasons,
        "row_ids": [r.row_id for r in table.excluded_rows],
    }
    excluded_path.write_text(json.dumps(excluded_data, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"[EvidenceTable] Saved: {path.name} ({len(table.included_rows)} rows)")
    return path


def _mechanism_priority_score(row: EvidenceRow) -> float:
    score = 0.0
    if row.temperature_scope:
        score += 3.0
    if row.eis_scope:
        score += 2.5
    if row.arrhenius_scope:
        score += 2.5
    if row.evidence_type == "mechanism_claim":
        score += 2.0
    if row.evidence_type == "direct_measurement" and row.numeric_payload:
        score += 2.0
    if row.evidence_type == "comparator":
        score += 1.5
    if row.evidence_type == "limitation":
        score += 1.0
    if any("Grotthuss" in t or "Vehicle" in t for t in row.mechanism_tags):
        score += 1.5
    score += row.confidence
    return score


def _material_priority_score(
    row: EvidenceRow,
    descriptor_keywords: list[str] | None = None,
) -> float:
    score = 0.0
    if row.evidence_type == "direct_measurement" and row.numeric_payload:
        score += 3.0
    if row.material_family_tags:
        score += 2.0
    if row.evidence_type == "mechanism_claim":
        score += 1.0
    if row.evidence_type == "limitation":
        score += 0.5
    score += row.confidence

    if descriptor_keywords:
        claim_lower = row.claim_text.lower()
        matches = sum(1 for kw in descriptor_keywords if kw.lower() in claim_lower)
        score += matches * 1.5

    return score
