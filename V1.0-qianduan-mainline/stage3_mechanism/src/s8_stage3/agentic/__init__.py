"""Tier 3 / v2 agentic capability layer for Stage 3 (research-claw).

These modules give the Stage 3 pipeline the agent-systems building blocks it
currently lacks: episodic **memory**, a liveness/progress **heartbeat**, and a
self-**critic** loop. They are intentionally standalone and are NOT wired into
the frozen linear orchestrator (`orchestrator/pipeline.py`); enabling them is a
deliberate v2 step. Nothing here fabricates timestamps or scientific evidence:
memory orders events by a monotonic sequence counter, the heartbeat uses an
injectable clock, and the critic only flags text.
"""

from .critic import Critic, Critique, eis_overclaim_rule, nonempty_rule, overclaim_rule
from .heartbeat import Beat, Heartbeat
from .memory import EpisodicMemory, MemoryRecord

__all__ = [
    "EpisodicMemory",
    "MemoryRecord",
    "Heartbeat",
    "Beat",
    "Critic",
    "Critique",
    "overclaim_rule",
    "eis_overclaim_rule",
    "nonempty_rule",
]
