# -*- coding: utf-8 -*-
"""独立证据根去重（WP3-b / E-Mem）。

GPT-3:多个 Agent 引用同一文献会被错误计成多份证据。本模块按 docx §5.3 判定"什么构成独立证据根":
  独立实验            → 根,键 = physical_effect_id + sample_batch_id
  文献中的独立实验    → 根,键 = DOI(+ study/experiment locator)
  分析结果            → 非根(证据变换,键 = source_evidence_ids + analysis_version)
  Agent 发言 / 摘要   → 非根
  多 Agent 重复引用同一文献 → 只计一个根(normalized_root_id 相同)
据此,证据强度按**独立根数**计,不按"提及次数/Agent 票数"。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


class RootKind:
    INDEPENDENT_EXPERIMENT = "independent_experiment"
    LITERATURE_EXPERIMENT = "literature_experiment"
    ANALYSIS_RESULT = "analysis_result"      # 非根
    AGENT_STATEMENT = "agent_statement"      # 非根
    SUMMARY = "summary"                      # 非根
    INDEPENDENT_KINDS = frozenset({INDEPENDENT_EXPERIMENT, LITERATURE_EXPERIMENT})


@dataclass
class EvidenceSource:
    kind: str
    # 实验:physical_effect_id + sample_batch_id;文献:doi + locator;分析:source_ids + analysis_version
    physical_effect_id: Optional[str] = None
    sample_batch_id: Optional[str] = None
    doi: Optional[str] = None
    locator: Optional[str] = None
    source_evidence_ids: List[str] = field(default_factory=list)
    analysis_version: Optional[str] = None
    cited_by_agent: Optional[str] = None

    def is_independent_root(self) -> bool:
        return self.kind in RootKind.INDEPENDENT_KINDS


def normalize_root(src: EvidenceSource) -> Optional[str]:
    """返回归一化独立根 id;非独立根返回 None(不计入证据强度)。"""
    if src.kind == RootKind.INDEPENDENT_EXPERIMENT:
        if src.physical_effect_id and src.sample_batch_id:
            return f"exp::{src.physical_effect_id}::{src.sample_batch_id}"
        return None
    if src.kind == RootKind.LITERATURE_EXPERIMENT:
        if src.doi:
            return f"lit::{src.doi.strip().lower()}::{(src.locator or '').strip().lower()}"
        return None
    return None   # analysis_result / agent_statement / summary 均非根


def count_independent_roots(sources: List[EvidenceSource]) -> int:
    """去重后的独立证据根数(多 Agent 引同一 DOI 只计一根)。"""
    roots: Set[str] = set()
    for s in sources:
        rid = normalize_root(s)
        if rid is not None:
            roots.add(rid)
    return len(roots)


def dedup_sources(sources: List[EvidenceSource]) -> Dict[str, Any]:
    """返回 {independent_roots: [...], n_independent, n_non_root, duplicates_collapsed}。"""
    roots: Dict[str, int] = {}
    non_root = 0
    for s in sources:
        rid = normalize_root(s)
        if rid is None:
            non_root += 1
        else:
            roots[rid] = roots.get(rid, 0) + 1
    duplicates_collapsed = sum(v - 1 for v in roots.values())   # 同根多次引用被折叠的次数
    return {
        "independent_roots": sorted(roots.keys()),
        "n_independent": len(roots),
        "n_non_root": non_root,
        "duplicates_collapsed": duplicates_collapsed,
    }
