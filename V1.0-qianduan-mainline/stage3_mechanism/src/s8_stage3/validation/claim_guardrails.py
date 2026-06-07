"""声明护栏：防止 EIS 等高风险声明被误用为强结论。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

_ABSOLUTE_CLAIM_PATTERNS: list[str] = [
    r"proves?\b", r"证明", r"唯一说明", r"confirms?\b", r"establishes?\b",
    r"conclusively\b", r"definitively\b", r"unambiguously\b",
    r"等效电路已确定", r"EIS 已证明", r"EIS proves?\b",
]
_COMPILED = [re.compile(p, re.IGNORECASE) for p in _ABSOLUTE_CLAIM_PATTERNS]


@dataclass
class ClaimViolation:
    step_id: str
    pattern: str
    context: str

    def __init__(self, step_id: str, pattern: str, context: str):
        self.step_id = step_id
        self.pattern = pattern
        self.context = context

    def __repr__(self) -> str:
        return f"ClaimViolation(step={self.step_id}, pattern={self.pattern!r})"


def check_eis_claims(step_id: str, data: dict | str) -> list[ClaimViolation]:
    violations: list[ClaimViolation] = []
    text = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
    for pat in _COMPILED:
        for m in pat.finditer(text):
            start = max(0, m.start() - 60)
            end = min(len(text), m.end() + 60)
            violations.append(ClaimViolation(
                step_id=step_id,
                pattern=pat.pattern,
                context=text[start:end],
            ))
    return violations


def assert_no_absolute_claims(step_id: str, data: dict | str) -> None:
    violations = check_eis_claims(step_id, data)
    if violations:
        msgs = [str(v) for v in violations[:3]]
        raise ValueError(f"[ClaimGuardrails] {step_id} 含绝对声明: {msgs}")
