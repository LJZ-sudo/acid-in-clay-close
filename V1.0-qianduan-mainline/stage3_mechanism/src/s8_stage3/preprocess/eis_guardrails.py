"""EIS 护栏：确保 EIS 相关字段仅作启发式表述，不被当成等效电路唯一解。

本模块提供 EIS 免责声明生成与 EIS 措辞合规检查。
"""
from __future__ import annotations

import re

EIS_DISCLAIMER = (
    "`arc_visible`、Nyquist 比值、`semicircle_*` 等来自启发式算法，"
    "仅用于 EIS 形貌分层与趋势提示，不等同于等效电路唯一解，"
    "也不等同于通过 Kramers–Kronig 检验后的物理判定。"
    "凡涉及圆弧/半圆/界面过程的表述，均应理解为"
    "“与……一致 / 提示 / 倾向于”，而非“证明存在……”。"
)

_ABSOLUTE_EIS_PATTERNS = [
    r"EIS\s+(proves?|shows?|confirms?|establishes?)\b",
    r"等效电路(已确定|唯一|证明|确认)",
    r"semicircle\s+proves?\b",
    r"grain\s+boundary\s+is\s+confirmed\b",
]
_COMPILED = [re.compile(p, re.IGNORECASE) for p in _ABSOLUTE_EIS_PATTERNS]


def get_eis_disclaimer() -> str:
    return EIS_DISCLAIMER


def check_eis_absolute_claims(text: str) -> list[str]:
    """返回违规 EIS 声明列表（空列表 = 合规）。"""
    violations = []
    for pat in _COMPILED:
        for m in pat.finditer(text):
            start = max(0, m.start() - 40)
            end = min(len(text), m.end() + 40)
            violations.append(f"Pattern `{pat.pattern}` matched: ...{text[start:end]}...")
    return violations
