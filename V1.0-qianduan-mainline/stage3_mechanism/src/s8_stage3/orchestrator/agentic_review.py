"""Optional v2 agentic review layer over the (frozen) Stage 3 claim ladder.

This does **NOT** modify the frozen linear orchestrator (``orchestrator/pipeline.py``).
It is a separate, opt-in post-hoc layer that finally wires the standalone agentic
modules (`critic` + episodic `memory` + `heartbeat`) into a real
produce -> critique -> revise loop over the claims that S14 already produced:

  * critic   : an *independent* re-check of every allowed claim for over-claiming,
               reusing the existing claim / EIS guardrails (so it is not a rubber stamp);
  * memory   : an append-only, monotonic-seq record of the review trace
               (deterministic; no fabricated timestamps);
  * heartbeat: liveness/progress telemetry with an injectable clock.

A bounded produce -> critique -> revise demo on an injected over-claim probe shows
the loop converges by *softening wording only* (absolute verbs -> "is consistent
with"), which is exactly the guardrail intent and fabricates no scientific content.

Run it after S14; it reads a ClaimAuditReport and writes agentic_review_report.json.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Callable, Optional

from s8_stage3.agentic import EpisodicMemory, Heartbeat
from s8_stage3.agentic.critic import Critique, default_claim_critic
from s8_stage3.contracts.claim_audit import ClaimAuditReport

# Deterministic wording softeners: downgrade absolute verbs to hedged phrasing.
# This is the guardrail's intent (no new science is invented).
_SOFTEN = [
    (r"\bproves?\b", "is consistent with"),
    (r"\bconfirms?\b", "is consistent with"),
    (r"\bshows?\b", "is consistent with"),
    (r"\bestablishes?\b", "is consistent with"),
    (r"\bconclusively\b", ""),
    (r"\bdefinitively\b", ""),
    (r"\bunambiguously\b", ""),
    (r"证明", "与之一致"),
    (r"唯一说明", "提示"),
]


def soften_wording(text: str) -> str:
    out = text
    for pat, rep in _SOFTEN:
        out = re.sub(pat, rep, out, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", out).strip()


def run_agentic_review(
    report: ClaimAuditReport,
    *,
    out_dir: Optional[Path] = None,
    clock: Optional[Callable[[], float]] = None,
) -> dict:
    """Run the agentic review over an S14 ClaimAuditReport. Pure + side-effect-free
    unless ``out_dir`` is given (then writes report + memory json)."""
    critic = default_claim_critic()
    memory = EpisodicMemory()
    heartbeat = Heartbeat(clock=clock) if clock is not None else Heartbeat()

    heartbeat.beat("agentic_review", "running", "start")

    # 1) Independent critique of every claim S14 produced (cross-check it is clean).
    claim_reviews = []
    for item in report.claim_ladder:
        text = item.allowed_claim or ""
        crit = critic.review(text, round=0)
        memory.record(
            "critique",
            item.claim_level,
            {"ok": crit.ok, "issues": crit.issues},
            tags=["claim_review"],
            note=str(item.claim_level_c or ""),
        )
        claim_reviews.append({
            "claim_level": item.claim_level,
            "claim_level_c": item.claim_level_c,
            "status": item.status,
            "critic_ok": crit.ok,
            "issues": crit.issues,
        })
        heartbeat.beat("agentic_review", "running", f"reviewed {item.claim_level}")

    # 2) Bounded produce -> critique -> revise demo on an injected over-claim probe.
    probe = "EIS proves the grain boundary and confirms the mechanism conclusively."
    state = {"text": probe}

    def produce(prev: Optional[Critique]) -> str:
        if prev is not None and not prev.ok:
            state["text"] = soften_wording(state["text"])
        return state["text"]

    revised, history = critic.refine(produce, max_rounds=4)
    for h in history:
        memory.record(
            "refine",
            "probe",
            {"round": h.round, "ok": h.ok, "issues": h.issues},
            tags=["refine_demo"],
        )
    heartbeat.beat("agentic_review", "done", "complete")

    result = {
        "policy": "advisory; frozen pipeline.py NOT modified; no scientific content fabricated",
        "n_claims_reviewed": len(claim_reviews),
        "all_claims_clean": all(c["critic_ok"] for c in claim_reviews),
        "claim_reviews": claim_reviews,
        "refine_demo": {
            "probe_text": probe,
            "revised_text": revised,
            "converged_clean": bool(history[-1].ok) if history else False,
            "rounds": [{"round": h.round, "ok": h.ok, "issues": h.issues} for h in history],
        },
        "memory_summary": memory.summary(),
        "heartbeat_report": heartbeat.report(),
    }

    if out_dir is not None:
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "agentic_review_report.json").write_text(
            json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        memory.persist(out_dir / "agentic_memory.json")
    return result
