"""文献去重：按 DOI / title+year / title+first_author 合并多源结果。

生成可解释的 dedupe_log，不静默丢弃任何条目。
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from s8_stage3.contracts.paper import PaperRecord

logger = logging.getLogger(__name__)


@dataclass
class DedupeLogEntry:
    kept_id: str
    merged_id: str
    reason: str


@dataclass
class DedupeResult:
    records: list[PaperRecord] = field(default_factory=list)
    log: list[DedupeLogEntry] = field(default_factory=list)
    total_input: int = 0
    total_output: int = 0


def deduplicate(
    records: list[PaperRecord],
    log_path: Optional[Path] = None,
) -> DedupeResult:
    """去重并合并多个来源的结果，返回结果和日志。"""
    result = DedupeResult(total_input=len(records))
    seen: dict[str, PaperRecord] = {}

    for rec in records:
        key = rec.dedup_key
        similar = _find_similar_key(seen, key)
        match_key = similar if similar else (key if key in seen else None)

        if match_key:
            existing = seen[match_key]
            seen[match_key] = _merge(existing, rec)
            result.log.append(DedupeLogEntry(
                kept_id=existing.paper_id,
                merged_id=rec.paper_id,
                reason=f"dedup_key match: {match_key[:50]}",
            ))
            logger.debug(f"[Dedup] Merged {rec.paper_id} -> {existing.paper_id}")
        else:
            seen[key] = rec

    result.records = list(seen.values())
    result.total_output = len(result.records)

    if result.log:
        logger.info(
            f"[Dedup] {result.total_input} -> {result.total_output} "
            f"({len(result.log)} merges)"
        )

    if log_path:
        log_data = [
            {"kept": e.kept_id, "merged": e.merged_id, "reason": e.reason}
            for e in result.log
        ]
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(json.dumps(log_data, ensure_ascii=False, indent=2), encoding="utf-8")

    return result


def _find_similar_key(seen: dict[str, PaperRecord], key: str) -> str | None:
    """模糊匹配：title 前 50 字符 + year 相同视为重复。"""
    if key.startswith("titleyear:"):
        prefix = key[:60]
        for k in seen:
            if k.startswith("titleyear:") and k[:60] == prefix:
                return k
    return None


def _merge(a: PaperRecord, b: PaperRecord) -> PaperRecord:
    """保留来源更丰富的字段合并两条记录。"""
    return a.model_copy(update={
        "citation_count": max(a.citation_count, b.citation_count),
        "abstract": a.abstract or b.abstract,
        "pdf_url": a.pdf_url or b.pdf_url,
        "venue": a.venue or b.venue,
        "doi": a.doi or b.doi,
        "relevance_score": max(a.relevance_score, b.relevance_score),
        "matched_queries": list(set(a.matched_queries + b.matched_queries)),
        "source_provider": (
            f"{a.source_provider}+{b.source_provider}"
            if a.source_provider != b.source_provider
            else a.source_provider
        ),
    })
