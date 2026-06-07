"""Query Packet Builder — 生成供人工检索的结构化查询包。

从 hypothesis_board (S05) 或 descriptor_sheet (S08) 生成 QueryPacket，
输出 JSON + 人类可读 Markdown 两种格式。不做实际联网搜索。
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from s8_stage3.contracts.query_packet import QueryPacket, QuerySpec

logger = logging.getLogger(__name__)


def build_mechanism_query_packet(
    hypothesis_board: dict,
    seed_context: dict | None = None,
    packet_id: str = "QP-S05-001",
) -> QueryPacket:
    """从假说板生成机理侧检索包。"""
    hypotheses = hypothesis_board.get("hypotheses", [])
    queries: list[QuerySpec] = []
    idx = 0

    for h in hypotheses:
        label = h.get("mechanism_label", "")
        if not label:
            continue
        keywords = _extract_keywords(label, max_kw=5)
        if not keywords:
            continue
        idx += 1
        queries.append(QuerySpec(
            query_id=f"QM{idx:02d}",
            intent=f"寻找支持/反驳假说 '{label[:60]}' 的文献",
            query_text=f'"{keywords}" proton conduction mechanism',
            query_type="google_scholar",
            include_terms=keywords.split()[:3] + ["proton", "conductivity"],
            exclude_terms=["battery", "fuel cell membrane"],
            year_hint="2010-2026",
            notes="建议查看 Cited by 链，关注 EIS + Arrhenius 方法论文",
        ))

    queries.extend(_mechanism_generic_queries(start_idx=idx))

    focus = "酸性水凝胶/黏土复合体系中质子传导机理的温度依赖性"
    if hypotheses:
        labels = [h.get("mechanism_label", "") for h in hypotheses[:3]]
        focus = f"验证以下机理假说: {'; '.join(labels)}"

    return QueryPacket(
        packet_id=packet_id,
        stage_target="s05_mechanism",
        focus_question=focus,
        search_queries=queries,
        screening_notes=[
            "优先保留: 有明确温区划分和 Ea 数据的论文",
            "优先保留: 对比了 Grotthuss vs Vehicle 机制的论文",
            "优先保留: 含 EIS 形貌分析（Nyquist / Bode）的论文",
            "排除: 纯燃料电池膜性能测试（无机理讨论）",
            "排除: 纯计算/MD模拟（无实验验证）",
        ],
        stop_rule="连续 10 篇论文标题/摘要均不相关时停止检索",
        generated_from={
            "source": "hypothesis_board",
            "n_hypotheses": len(hypotheses),
        },
        created_at=datetime.now(timezone.utc).isoformat(),
    )


def build_material_query_packet(
    descriptor_sheet: dict,
    packet_id: str = "QP-S08-001",
) -> QueryPacket:
    """从描述符表生成材料侧检索包。"""
    descriptors = descriptor_sheet.get("descriptors", [])
    queries: list[QuerySpec] = []
    idx = 0

    for d in descriptors:
        desc_text = d.get("descriptor_text", "")
        features = d.get("required_material_features", [])
        if not desc_text and not features:
            continue
        idx += 1
        kw_source = " ".join(features[:3]) if features else desc_text[:50]
        queries.append(QuerySpec(
            query_id=f"QT{idx:02d}",
            intent=f"寻找满足描述符 '{desc_text[:40]}' 的材料家族文献",
            query_text=f'"{kw_source}" ionic conductivity membrane',
            query_type="google_scholar",
            include_terms=(features[:3] if features else kw_source.split()[:3]) + ["proton"],
            exclude_terms=["Nafion", "SPEEK", "fuel cell"],
            year_hint="2015-2026",
            notes="关注 family 级别: 多糖类/黏土类/复合凝胶类，不要具体配方",
        ))

    queries.extend(_material_generic_queries(start_idx=idx))

    return QueryPacket(
        packet_id=packet_id,
        stage_target="s08_materials",
        focus_question="寻找满足机理描述符的候选材料家族及其质子传导性能文献",
        search_queries=queries,
        screening_notes=[
            "优先保留: 有电导率数据（S/cm）的论文",
            "优先保留: 有温度范围和稳定性信息的论文",
            "优先保留: 天然高分子/黏土/水凝胶类材料",
            "排除: 纯商用膜（Nafion, SPEEK）的优化研究",
            "排除: 纯电池极片材料",
        ],
        stop_rule="每个材料家族至少找到 3 篇相关论文，或连续 8 篇不相关时停止",
        generated_from={
            "source": "descriptor_sheet",
            "n_descriptors": len(descriptors),
        },
        created_at=datetime.now(timezone.utc).isoformat(),
    )


def _mechanism_generic_queries(start_idx: int) -> list[QuerySpec]:
    """机理侧通用检索词。"""
    generics = [
        ("proton transport mechanism polymer hydrogel temperature dependent",
         "酸性高分子水凝胶中质子传输机制的温度依赖性综述"),
        ("Grotthuss vehicle proton hopping activation energy polymer",
         "Grotthuss 与 Vehicle 机制的区分方法"),
        ("EIS Nyquist proton conductor activation energy Arrhenius",
         "EIS + Arrhenius 分析在质子导体中的应用"),
        ("acid clay composite proton conduction wide temperature",
         "酸-黏土复合体系的宽温区质子传导"),
        ("hydrogen bond network proton hopping water channel polymer",
         "氢键网络与质子跳跃的水通道结构"),
    ]
    specs = []
    for i, (qt, intent) in enumerate(generics):
        specs.append(QuerySpec(
            query_id=f"QM{start_idx + i + 1:02d}",
            intent=intent,
            query_text=qt,
            query_type="google_scholar",
            include_terms=qt.split()[:4],
            exclude_terms=["battery", "lithium"],
            year_hint="2010-2026",
        ))
    return specs


def _material_generic_queries(start_idx: int) -> list[QuerySpec]:
    """材料侧通用检索词。"""
    generics = [
        ("polysaccharide proton exchange membrane conductivity",
         "多糖基质子交换膜的电导率文献"),
        ("clay polymer composite ionic conductivity review",
         "黏土-高分子复合材料离子电导率综述"),
        ("starch phosphoric acid proton conductor",
         "淀粉/磷酸复合质子导体"),
        ("natural polymer hydrogel ionic conductivity temperature",
         "天然高分子水凝胶的离子电导率温度特性"),
    ]
    specs = []
    for i, (qt, intent) in enumerate(generics):
        specs.append(QuerySpec(
            query_id=f"QT{start_idx + i + 1:02d}",
            intent=intent,
            query_text=qt,
            query_type="google_scholar",
            include_terms=qt.split()[:4],
            exclude_terms=["Nafion", "fuel cell"],
            year_hint="2015-2026",
        ))
    return specs


def _extract_keywords(text: str, max_kw: int = 5) -> str:
    stop_words = {"a", "an", "the", "and", "or", "of", "in", "at", "to", "with", "via", "by", "for", "is", "are"}
    words = re.findall(r"\b[a-zA-Z]+\b", text)
    keywords = [w for w in words if w.lower() not in stop_words and len(w) > 2]
    return " ".join(keywords[:max_kw])


def save_query_packet(packet: QueryPacket, output_dir: Path) -> tuple[Path, Path]:
    """保存 JSON + Markdown 两种格式。"""
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{packet.packet_id}.json"
    md_path = output_dir / f"{packet.packet_id}.md"

    json_path.write_text(
        packet.model_dump_json(indent=2),
        encoding="utf-8",
    )

    md_lines = [
        f"# Query Packet: {packet.packet_id}",
        f"\n**Stage Target:** {packet.stage_target}",
        f"\n**Focus Question:** {packet.focus_question}",
        f"\n**Created:** {packet.created_at}",
        f"\n**Stop Rule:** {packet.stop_rule}",
        "\n## Search Queries\n",
    ]
    for q in packet.search_queries:
        md_lines.append(f"### {q.query_id}: {q.intent}")
        md_lines.append(f"- **Query:** `{q.query_text}`")
        md_lines.append(f"- **Type:** {q.query_type}")
        if q.include_terms:
            md_lines.append(f"- **Include:** {', '.join(q.include_terms)}")
        if q.exclude_terms:
            md_lines.append(f"- **Exclude:** {', '.join(q.exclude_terms)}")
        if q.year_hint:
            md_lines.append(f"- **Years:** {q.year_hint}")
        if q.notes:
            md_lines.append(f"- **Notes:** {q.notes}")
        md_lines.append("")

    md_lines.append("## Screening Notes\n")
    for note in packet.screening_notes:
        md_lines.append(f"- {note}")

    md_path.write_text("\n".join(md_lines), encoding="utf-8")
    logger.info(f"[QueryPacket] Saved: {json_path.name} + {md_path.name}")
    return json_path, md_path
