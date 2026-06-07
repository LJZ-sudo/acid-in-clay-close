"""上游抽象层保护：S03–S07（以及 S09 family 层）应停留在机理/描述符层面，
不应出现具体物种配方级术语（wt%、mol% 具体数值）或单个商品化材料的专名。

设计原则（2025 重构）：
  - 不再硬编码任何具体的"候选答案"物种名（任何具体目标候选词应仅来自 S08 文献池）。
    之前那种黑名单实际上把答案写死在了流程里，属于反模式。
  - 本检查器只做 advisory warning，不 fail pipeline。
  - 真正强制"抽象层"的是各 prompt 的指令；这里只做兜底式软校验。
  - 黑名单仅包含**与本研究主题体系无关的通用工业商品名**，
    用来挡 LLM 凭空拉出教科书式的典型 PEM 品牌（Nafion 等）作为"答案"。

若想加更多模式，请只加"不属于本研究体系、会污染描述符抽象层"的通用词，
不要加任何可能是本流程自然涌现的候选物种名。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

# 通用"商业/教科书品牌"名 —— 上游抽象层不应直接提到的 PEM 产品名
# 这些不是我们的目标候选，只是常见的"LLM 不经证据就脱口而出"的名字
_UPSTREAM_BRAND_BLACKLIST: list[str] = [
    r"\bNafion\b", r"\bAquivion\b", r"\bFlemion\b",
    r"\bSPEEK\b", r"\bSPSU\b",
    # 具体配方级数值（精确到 wt% / mol%） —— 机理层不应精确到配方
    r"\b\d+\s*wt\s*%", r"\b\d+\s*mol\s*%",
]

_COMPILED = [re.compile(p, re.IGNORECASE) for p in _UPSTREAM_BRAND_BLACKLIST]


@dataclass
class LeakageViolation:
    step_id: str
    field_path: str
    matched_term: str
    context: str

    def __repr__(self) -> str:
        return (
            f"LeakageViolation(step={self.step_id}, "
            f"field={self.field_path}, term={self.matched_term!r})"
        )


def check_leakage(step_id: str, data: dict | str) -> list[LeakageViolation]:
    """扫描 data，返回疑似"商业品牌名或具体配方数值"的 advisory 违规列表。

    本函数永不抛错；调用方可以根据需要把结果作为 warning 打日志。
    """
    violations: list[LeakageViolation] = []
    text = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)

    for pat in _COMPILED:
        for m in pat.finditer(text):
            start = max(0, m.start() - 40)
            end = min(len(text), m.end() + 40)
            violations.append(LeakageViolation(
                step_id=step_id,
                field_path="text",
                matched_term=m.group(),
                context=text[start:end],
            ))
    return violations


class LeakageViolationError(RuntimeError):
    """Raised by ``assert_no_leakage(..., strict=True)`` when violations exist.

    Only used on the opt-in hard-enforcement path (Tier 2). The default
    advisory path never raises.
    """

    def __init__(self, step_id: str, violations: list[LeakageViolation]):
        self.step_id = step_id
        self.violations = violations
        terms = ", ".join(sorted({v.matched_term for v in violations}))
        super().__init__(
            f"[no_leakage] step={step_id} found {len(violations)} "
            f"upstream-abstraction violation(s): {terms}"
        )


def assert_no_leakage(
    step_id: str,
    data: dict | str,
    strict: bool = False,
) -> list[LeakageViolation]:
    """Upstream-abstraction leakage gate for S03–S07 (and the S09 family layer).

    NAME CAVEAT (Tier1 note 2026-06-01): despite the ``assert_`` prefix, this is
    ADVISORY BY DEFAULT and does NOT raise. It was historically downgraded to a
    no-op so it could never fail the pipeline. Tier1 keeps that behavior exactly
    but makes the (mis)naming explicit and adds an opt-in strict mode:

      - ``strict=False`` (default): scan only and RETURN the (possibly empty)
        list of violations so callers may log warnings. Never raises. This
        preserves the current pipeline behavior and all frozen results.
      - ``strict=True``: raise :class:`LeakageViolationError` if any violation is
        found. This is the hard-enforcement path reserved for Tier 2 (to be
        enabled per-run into a NEW verification dir). No current caller passes
        ``strict=True``.
    """
    violations = check_leakage(step_id, data)
    if strict and violations:
        raise LeakageViolationError(step_id, violations)
    return violations
