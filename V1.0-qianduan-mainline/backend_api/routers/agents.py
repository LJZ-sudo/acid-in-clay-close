# -*- coding: utf-8 -*-
"""Multi-agent status endpoints — /api/agents/*

Exposes the Planner/Critic/Orchestrator triad as a multi-agent view.
Delegates to the single-agent state in agent.py.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter

router = APIRouter()

AGENT_DEFINITIONS = [
    {
        "id": "planner",
        "name": "Planner",
        "role": "Proposes measurement actions based on current experiment context",
        "capabilities": ["phase_detection", "temperature_policy", "backtrack_decision"],
    },
    {
        "id": "critic",
        "name": "Critic",
        "role": "Reviews proposals using QC grades and retest logic",
        "capabilities": ["qc_validation", "retest_recommendation"],
    },
    {
        "id": "orchestrator",
        "name": "Orchestrator",
        "role": "Arbitrates between Planner and Critic, applies final policy",
        "capabilities": ["policy_application", "conflict_resolution"],
    },
]

_messages: list[dict] = []


@router.get("/status")
def get_agents_status():
    from backend_api.routers.agent import _agent_state
    latest = _agent_state.get("decisions", [])[-1] if _agent_state.get("decisions") else None
    agents = []
    for defn in AGENT_DEFINITIONS:
        agent = {**defn, "status": "idle"}
        if latest:
            role_data = latest.get(defn["id"])
            if role_data:
                agent["status"] = "active"
                agent["last_action"] = role_data
        agents.append(agent)
    return {"agents": agents, "total_decisions": len(_agent_state.get("decisions", []))}


@router.get("/capabilities")
def get_capabilities():
    return {"agents": AGENT_DEFINITIONS}


@router.get("/health")
def health_check():
    from backend_api.routers.agent import _agent_state
    return {
        "healthy": True,
        "decisions_count": len(_agent_state.get("decisions", [])),
        "current_run_id": _agent_state.get("current_run_id"),
    }


@router.get("/messages")
def get_messages(limit: int = 50, type: str = "", sender: str = "", receiver: str = ""):
    from backend_api.routers.agent import _agent_state
    msgs = []
    for d in _agent_state.get("decisions", [])[-limit:]:
        ts = d.get("timestamp", datetime.now().isoformat())
        msgs.append({"id": d["id"], "timestamp": ts, "sender": "planner", "receiver": "critic", "type": "proposal", "data": d.get("planner", {})})
        msgs.append({"id": d["id"] + "_c", "timestamp": ts, "sender": "critic", "receiver": "orchestrator", "type": "review", "data": d.get("critic", {})})
        msgs.append({"id": d["id"] + "_o", "timestamp": ts, "sender": "orchestrator", "receiver": "system", "type": "decision", "data": d.get("orchestrator", {})})
    if sender:
        msgs = [m for m in msgs if m["sender"] == sender]
    if receiver:
        msgs = [m for m in msgs if m["receiver"] == receiver]
    if type:
        msgs = [m for m in msgs if m["type"] == type]
    return {"messages": msgs[-limit:], "total": len(msgs)}


@router.post("/evaluate")
def evaluate(params: dict = None):
    """Invoke critic evaluation on arbitrary data."""
    if params is None:
        params = {}
    from backend_api.routers.agent import _critic_review
    ctx = params.get("data", {})
    proposal = {"action": "EVALUATE", "reason": params.get("type", "manual"), "phase_score": ctx.get("phase_score", 0)}
    result = _critic_review(proposal, ctx)
    record = {
        "id": uuid.uuid4().hex[:8],
        "timestamp": datetime.now().isoformat(),
        "type": params.get("type", "manual"),
        "input": params,
        "critic_result": result,
    }
    _messages.append(record)
    return {"ok": True, "evaluation": result, "record_id": record["id"]}


@router.get("/stats")
def get_stats():
    from backend_api.routers.agent import _agent_state
    decisions = _agent_state.get("decisions", [])
    action_counts: dict[str, int] = {}
    for d in decisions:
        a = d.get("action", "unknown")
        action_counts[a] = action_counts.get(a, 0) + 1
    return {
        "total_decisions": len(decisions),
        "total_messages": len(decisions) * 3,
        "action_distribution": action_counts,
        "sessions": len(_agent_state.get("sessions", {})),
    }
