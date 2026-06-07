"""引用护栏：防止文献卡片被过度引用或引用不存在的来源。"""
from __future__ import annotations

import re


def check_citation_existence(
    cited_ids: list[str],
    available_card_ids: set[str],
) -> list[str]:
    """返回引用了不存在卡片 ID 的违规列表。"""
    violations = []
    for cid in cited_ids:
        if cid not in available_card_ids:
            violations.append(f"Cited card_id '{cid}' not found in available literature cards.")
    return violations


def check_overcitation(
    text: str,
    max_same_citation: int = 5,
) -> list[str]:
    """检查单条引用是否出现超过 max_same_citation 次（提示可能过度依赖单一来源）。"""
    # 匹配 [ML1], [MAT2] 等模式
    pattern = re.compile(r"\[([A-Z0-9]+)\]")
    counts: dict[str, int] = {}
    for m in pattern.finditer(text):
        cid = m.group(1)
        counts[cid] = counts.get(cid, 0) + 1

    warnings = []
    for cid, cnt in counts.items():
        if cnt > max_same_citation:
            warnings.append(
                f"Citation '{cid}' appears {cnt} times; possible overcitation."
            )
    return warnings
