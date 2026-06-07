"""文献查询构建器：从 Stage3 上游结构化对象生成搜索词。"""

from __future__ import annotations

import re


def build_mechanism_queries(hypothesis_board: dict) -> list[str]:
    """从假说层生成机理侧搜索词（不含具体材料名）。"""
    queries: list[str] = []
    for h in hypothesis_board.get("hypotheses", []):
        label = h.get("mechanism_label", "")
        if label:
            # 提取关键词，去除长句
            keywords = _extract_mechanism_keywords(label)
            if keywords:
                queries.append(keywords)

    # 通用机理相关词
    queries.extend([
        "proton transport mechanism acid hydrogel temperature",
        "Grotthuss proton hopping polymer membrane conductivity",
        "H-bond network proton conduction wide temperature range",
    ])
    return list(dict.fromkeys(queries))  # 去重保序


def build_material_queries(descriptor_sheet: dict) -> list[str]:
    """从描述符层生成材料侧搜索词（family 级别）。"""
    queries: list[str] = []
    for d in descriptor_sheet.get("descriptors", []):
        text = d.get("descriptor_text", "")
        features = d.get("required_material_features", [])
        if features:
            q = " ".join(features[:3]) + " proton conducting membrane"
            queries.append(q)
        elif text:
            # 取描述符前 60 个字符
            queries.append(text[:60] + " proton conductor")

    # S08 允许 family 级材料类名
    queries.extend([
        "polysaccharide proton exchange membrane conductivity",
        "clay polymer composite proton conduction",
        "starch phosphoric acid composite ionic conductivity",
    ])
    return list(dict.fromkeys(queries))


def _extract_mechanism_keywords(text: str) -> str:
    """从机理标签提取 3-5 个关键词，用于搜索。"""
    # 去除常见噪声词
    stop_words = {"a", "an", "the", "and", "or", "of", "in", "at", "to", "with", "via"}
    words = re.findall(r"\b[a-zA-Z]+\b", text)
    keywords = [w for w in words if w.lower() not in stop_words and len(w) > 3]
    return " ".join(keywords[:6])
