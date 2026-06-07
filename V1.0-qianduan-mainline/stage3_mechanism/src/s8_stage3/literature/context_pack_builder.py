"""Context Pack Builder — 从 CuratedEvidenceTable 生成下游最小上下文包。

每个 pack 只保留最相关的 evidence rows，不允许无差别喂全部内容。
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from pathlib import Path

from s8_stage3.contracts.context_pack import ContextPack
from s8_stage3.contracts.evidence_row import CuratedEvidenceTable, EvidenceRow

logger = logging.getLogger(__name__)


def build_context_pack(
    table: CuratedEvidenceTable,
    target_step: str,
    max_rows: int = 15,
) -> ContextPack:
    """从证据表生成一个 step 的 context pack。"""
    rows = table.included_rows
    selected = _select_for_step(rows, target_step, max_rows)
    excluded_ids = [r.row_id for r in rows if r not in selected]

    support_counter: Counter[str] = Counter()
    weaken_counter: Counter[str] = Counter()
    unknowns: list[str] = []

    for r in selected:
        # paper-level axes may be repeated across multiple rows from the same
        # paper; dedupe per paper so one paper's vote is counted once per axis.
        row_supports = set(r.supports or [])
        row_weakens = set(r.weakens or [])
        support_counter.update(row_supports)
        weaken_counter.update(row_weakens)
        if r.evidence_type == "limitation":
            unknowns.append(r.claim_text[:100])

    # Keep the top items with their frequencies encoded as "axis:value (xN)" for
    # downstream visibility, so the caller can see which positions dominate.
    def _fmt(counter: Counter[str], top_k: int = 5) -> list[str]:
        return [f"{k} (x{n})" if n > 1 else k for k, n in counter.most_common(top_k)]

    supports = _fmt(support_counter)
    weakens = _fmt(weaken_counter)

    summary_parts = []
    n_mech = sum(1 for r in selected if r.evidence_type == "mechanism_claim")
    n_meas = sum(1 for r in selected if r.evidence_type == "direct_measurement")
    n_lim = sum(1 for r in selected if r.evidence_type == "limitation")
    if n_mech:
        summary_parts.append(f"{n_mech} mechanism claims")
    if n_meas:
        summary_parts.append(f"{n_meas} measurements")
    if n_lim:
        summary_parts.append(f"{n_lim} limitations/caveats")
    summary = f"Context for {target_step}: {', '.join(summary_parts) or 'no evidence'}"

    return ContextPack(
        pack_id=f"ctx-{target_step}",
        stage_target=target_step,
        included_row_ids=[r.row_id for r in selected],
        excluded_row_ids=excluded_ids,
        summary=summary,
        key_supports=supports,
        key_weakens=weakens,
        key_unknowns=unknowns[:5],
        usage_notes=[
            "Evidence rows are sorted by relevance to this step",
            "Each row traces to a specific paper_id",
        ],
    )


def build_all_context_packs(
    mechanism_table: CuratedEvidenceTable | None,
    material_table: CuratedEvidenceTable | None,
) -> dict[str, ContextPack]:
    """生成所有下游 step 需要的 context packs。"""
    packs = {}

    if mechanism_table:
        packs["s05"] = build_context_pack(mechanism_table, "s05", max_rows=10)
        packs["s06"] = build_context_pack(mechanism_table, "s06", max_rows=15)

    if material_table:
        packs["s08"] = build_context_pack(material_table, "s08", max_rows=10)
        packs["s09"] = build_context_pack(material_table, "s09", max_rows=12)
        packs["s10"] = build_context_pack(material_table, "s10", max_rows=8)

    return packs


def save_context_packs(packs: dict[str, ContextPack], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for step, pack in packs.items():
        path = output_dir / f"{pack.pack_id}.json"
        path.write_text(pack.model_dump_json(indent=2), encoding="utf-8")
    logger.info(f"[ContextPacks] Saved {len(packs)} packs to {output_dir}")


def load_context_pack(pack_path: Path) -> ContextPack | None:
    if not pack_path.exists():
        return None
    try:
        return ContextPack(**json.loads(pack_path.read_text(encoding="utf-8")))
    except Exception as e:
        logger.warning(f"[ContextPacks] Load error: {e}")
        return None


def format_context_for_llm(pack: ContextPack, evidence_rows: list[EvidenceRow]) -> str:
    """将 context pack 格式化为 LLM 可消费的文本。"""
    row_map = {r.row_id: r for r in evidence_rows}
    lines = [f"## Literature Evidence Context ({pack.stage_target})", ""]
    lines.append(pack.summary)
    lines.append("")

    for rid in pack.included_row_ids:
        row = row_map.get(rid)
        if not row:
            continue
        prefix = f"[{row.paper_id}|{row.evidence_type}]"
        lines.append(f"- {prefix} {row.claim_text}")

    if pack.key_unknowns:
        lines.append("\n### Caveats/Unknowns")
        for u in pack.key_unknowns:
            lines.append(f"- {u}")

    return "\n".join(lines)


def _select_for_step(
    rows: list[EvidenceRow],
    target_step: str,
    max_rows: int,
) -> list[EvidenceRow]:
    """根据 step 类型选择最相关的 rows。"""
    if target_step in ("s05", "s06"):
        priority = {
            "mechanism_claim": 4,
            "direct_measurement": 3,
            "comparator": 2,
            "limitation": 1,
            "context": 0,
        }
    elif target_step in ("s08", "s09"):
        priority = {
            "direct_measurement": 4,
            "mechanism_claim": 2,
            "comparator": 3,
            "limitation": 1,
            "context": 0,
        }
    else:
        priority = {
            "direct_measurement": 3,
            "mechanism_claim": 3,
            "comparator": 2,
            "limitation": 2,
            "context": 1,
        }

    scored = sorted(
        rows,
        key=lambda r: (priority.get(r.evidence_type, 0), r.confidence),
        reverse=True,
    )
    return scored[:max_rows]
