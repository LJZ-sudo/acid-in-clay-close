"""Self-critic loop for the Stage 3 agent (Tier 3 / v2 capability).

A :class:`Critic` runs a set of rules over a piece of generated text and reports
issues; :meth:`Critic.refine` drives a bounded produce -> critique -> revise
loop. Built-in rules reuse the existing claim / EIS guardrails so the critic
catches overclaiming, but rules are plain callables so callers can add their
own. This is advisory tooling: it never fabricates content, it only flags text.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Optional, Sequence, Tuple

# A rule takes the candidate text and returns a list of issue strings (empty = ok).
CritiqueRule = Callable[[str], List[str]]


@dataclass
class Critique:
    ok: bool
    issues: List[str] = field(default_factory=list)
    round: int = 0


class Critic:
    def __init__(self, rules: Sequence[CritiqueRule]):
        self._rules: List[CritiqueRule] = list(rules)

    def review(self, text: str, *, round: int = 0) -> Critique:
        issues: List[str] = []
        for rule in self._rules:
            try:
                issues.extend(rule(text) or [])
            except Exception as exc:  # pragma: no cover - a broken rule must not crash the loop
                issues.append(f"rule_error: {exc}")
        return Critique(ok=not issues, issues=issues, round=round)

    def refine(
        self,
        produce: Callable[[Optional[Critique]], str],
        *,
        max_rounds: int = 3,
    ) -> Tuple[str, List[Critique]]:
        """Bounded produce/critique/revise loop.

        ``produce`` receives the previous :class:`Critique` (``None`` on the
        first round) and must return a new candidate text. The loop stops as
        soon as a critique is clean or ``max_rounds`` is reached.
        """
        history: List[Critique] = []
        last: Optional[Critique] = None
        text = ""
        for r in range(max(1, max_rounds)):
            text = produce(last)
            last = self.review(text, round=r)
            history.append(last)
            if last.ok:
                break
        return text, history


# --------------------------------------------------------------------------- #
# Built-in rules
# --------------------------------------------------------------------------- #
def nonempty_rule(text: str) -> List[str]:
    return [] if str(text).strip() else ["empty_output"]


def overclaim_rule(text: str) -> List[str]:
    """Flag absolute/overclaiming language via the existing claim guardrails."""
    from s8_stage3.validation.claim_guardrails import check_eis_claims

    violations = check_eis_claims("critic", text)
    return [f"overclaim: {v.pattern}" for v in violations]


def eis_overclaim_rule(text: str) -> List[str]:
    """Flag absolute EIS-mechanism claims via the EIS guardrail."""
    from s8_stage3.preprocess.eis_guardrails import check_eis_absolute_claims

    findings = check_eis_absolute_claims(text)
    return [f"eis_overclaim: {f}" for f in findings]


def default_claim_critic() -> Critic:
    """A critic preloaded with the non-empty + overclaim + EIS-overclaim rules."""
    return Critic([nonempty_rule, overclaim_rule, eis_overclaim_rule])
