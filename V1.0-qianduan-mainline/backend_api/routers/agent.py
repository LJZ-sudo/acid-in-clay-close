# -*- coding: utf-8 -*-
"""Agent decision routes — real rule-based decision engine with LLM fallback.

Implements a Planner → Critic → Orchestrator decision loop that:
- Planner proposes next action based on current measurement state
- Critic evaluates QC quality and risk
- Orchestrator arbitrates and emits the final action

The SSE stream pushes PLAN_PROPOSED, CRITIC_REVIEWED, ACTION_EXECUTED events.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend_api.services.hardware_adapter import get_hardware_adapter

router = APIRouter()


def _build_action_gate(hw):
    """WP4 Cutover:自主硬件命令的唯一受控入口(ActionGate)。

    把 stage1_optimization 加入 path 后按 scientific_harness.* 顶层导入(绕开包 __init__ 的重依赖)。
    默认 shadow(行为与 legacy 一致);SCITX_HARNESS_MODE=enforce 时按策略拦截 allowlist 外命令。
    导入失败时返回 None,调用方回退 legacy 直连(fail-safe,不阻断 backend)。
    """
    import sys as _sys
    from pathlib import Path as _Path
    stage1_dir = _Path(__file__).resolve().parents[2] / "stage1_optimization"
    if str(stage1_dir) not in _sys.path:
        _sys.path.insert(0, str(stage1_dir))
    try:
        from scientific_harness.action_gate import ActionGate
        return ActionGate(enqueue_fn=hw.enqueue_command)
    except Exception:
        return None

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_AGENT_STATE_DIR = _PROJECT_ROOT / "runs" / "_agent_state"
_DECISIONS_FILE = _AGENT_STATE_DIR / "decisions.jsonl"
_CONFIG_FILE = _AGENT_STATE_DIR / "config.json"


class DecideRequest(BaseModel):
    run_id: Optional[str] = None
    context: Optional[dict] = None
    force_rule_based: bool = False


class StartRunRequest(BaseModel):
    profile: Optional[str] = None
    mode: str = "autonomous"


class ThinkingRequest(BaseModel):
    run_id: Optional[str] = None
    context: Optional[dict] = None


def _default_config() -> Dict[str, Any]:
    return {
        "model": "gpt-5.4",
        "fallback": "rule_based",
        "api_provider": "openrouter",
        "phase_threshold": 0.2,
        "qc_retest_grades": ["C", "D", "UNKNOWN"],
        "max_retest_count": 2,
    }


def _load_persisted_state() -> Dict[str, Any]:
    """Load agent state from disk on startup."""
    state = {
        "current_run_id": None,
        "status": "idle",
        "decisions": [],
        "sessions": {},
        "config": _default_config(),
    }
    try:
        if _CONFIG_FILE.exists():
            saved = json.loads(_CONFIG_FILE.read_text(encoding="utf-8"))
            state["config"].update(saved)
    except Exception:
        pass
    try:
        if _DECISIONS_FILE.exists():
            lines = _DECISIONS_FILE.read_text(encoding="utf-8").strip().split("\n")
            for line in lines[-200:]:
                if line.strip():
                    state["decisions"].append(json.loads(line))
            if state["decisions"]:
                last = state["decisions"][-1]
                state["current_run_id"] = last.get("run_id")
    except Exception:
        pass
    return state


def _persist_decision(record: Dict[str, Any]) -> None:
    """Append a decision record to disk."""
    try:
        _AGENT_STATE_DIR.mkdir(parents=True, exist_ok=True)
        with open(_DECISIONS_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    except Exception:
        pass


def _persist_config(config: Dict[str, Any]) -> None:
    """Save agent config to disk."""
    try:
        _AGENT_STATE_DIR.mkdir(parents=True, exist_ok=True)
        _CONFIG_FILE.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


_agent_state = _load_persisted_state()


def _get_latest_measurement_context() -> Dict[str, Any]:
    """Pull the latest measurement state from HardwareAdapter."""
    hw = get_hardware_adapter()
    measurements = hw.get_measurements()
    events = hw.get_events()

    ctx = {
        "measurement_count": len(measurements),
        "temperature_C": hw._current_temperature,
        "target_temperature_C": hw._target_temperature,
        "running": hw._running,
        "mode": hw._measurement_mode,
        "step_size": hw._step_size,
        "latest_measurement": measurements[-1] if measurements else None,
        "latest_qc_grade": None,
        "latest_r2": None,
        "latest_rb_ohm": None,
        "latest_phase_score": None,
        "retest_count": 0,
    }

    for evt in reversed(events):
        et = evt.get("type", "")
        p = evt.get("payload", {})
        if et == "QC_GRADE" and ctx["latest_qc_grade"] is None:
            ctx["latest_qc_grade"] = p.get("qc_grade")
            ctx["latest_r2"] = p.get("r_squared")
        if et == "Rb_FIT" and ctx["latest_rb_ohm"] is None:
            ctx["latest_rb_ohm"] = p.get("rb_ohm")
        if et == "PHASE_SCORE" and ctx["latest_phase_score"] is None:
            ctx["latest_phase_score"] = p.get("phase_jump_score")
        if all([ctx["latest_qc_grade"], ctx["latest_rb_ohm"], ctx["latest_phase_score"]]):
            break

    retest_count = sum(1 for e in events[-10:] if e.get("type") in ("AGENT_RE_MEASURE", "RE_MEASURE"))
    ctx["retest_count"] = retest_count

    return ctx


def _planner_propose(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Planner: risk-seeking proposal generator.

    Looks at phase_jump_score and proposes fine scan / backtrack when
    score exceeds threshold.  Otherwise proposes continue with current step.
    """
    phase_score = ctx.get("latest_phase_score") or 0.0
    threshold = _agent_state["config"]["phase_threshold"]
    mode = ctx.get("mode", "COARSE")
    temp = ctx.get("temperature_C")

    if phase_score > threshold * 1.5 and temp is not None:
        return {
            "role": "planner",
            "action": "BACKTRACK",
            "reason": f"phase_jump_score={phase_score:.4f} >> threshold; backtrack to confirm onset",
            "confidence": 0.88,
        }

    if phase_score > threshold and mode != "FINE":
        return {
            "role": "planner",
            "action": "TRIGGER_FINE_SCAN",
            "reason": f"phase_jump_score={phase_score:.4f} > threshold={threshold}; switching to fine scan",
            "proposed_step": _agent_state["config"].get("fine_step", 1.0),
            "confidence": 0.92,
        }

    return {
        "role": "planner",
        "action": "CONTINUE_MEASUREMENT",
        "reason": f"Normal measurement; phase_score={phase_score:.4f} < threshold",
        "confidence": 0.95,
    }


def _critic_review(proposal: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Critic: risk-averse verifier & QC gate.

    Checks QC grade and may override planner's proposal if quality is too low.
    """
    qc_grade = ctx.get("latest_qc_grade", "UNKNOWN")
    r2 = ctx.get("latest_r2")
    retest_count = ctx.get("retest_count", 0)
    retest_grades = _agent_state["config"]["qc_retest_grades"]
    max_retests = _agent_state["config"]["max_retest_count"]

    approved = True
    override_action = None
    reason = f"QC={qc_grade}, R²={r2}"

    if qc_grade in retest_grades:
        if retest_count < max_retests:
            approved = False
            override_action = "RE_MEASURE"
            reason = f"QC={qc_grade} is below threshold; retest recommended (attempt {retest_count + 1}/{max_retests})"
        else:
            reason = f"QC={qc_grade} low but max retests ({max_retests}) reached; proceeding with caution"

    return {
        "role": "critic",
        "approved": approved,
        "override_action": override_action,
        "qc_grade": qc_grade,
        "r2": r2,
        "reason": reason,
        "confidence": 0.90 if approved else 0.75,
    }


def _orchestrator_decide(proposal: Dict[str, Any], critic: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Orchestrator: decision arbitration + state machine.

    Arbitrates between planner and critic to produce final executable action.
    """
    if not critic["approved"] and critic.get("override_action"):
        final_action = critic["override_action"]
        source_agent = "critic"
        reason = critic["reason"]
    else:
        final_action = proposal["action"]
        source_agent = "planner"
        reason = proposal["reason"]

    hw = get_hardware_adapter()

    # WP4 Cutover:自主硬件命令统一经 ActionGate 受控入口(不再直连 enqueue_command)。
    # 默认 shadow → 行为与 legacy 完全一致;enforce 模式下 allowlist 外命令会被阻断。
    _params = {"TRIGGER_FINE_SCAN": None, "BACKTRACK": {"backtrack_delta": 10.0},
               "RE_MEASURE": None}
    gate_decision = None
    if final_action in _params:
        gate = _build_action_gate(hw)
        if gate is not None:
            from scientific_harness.action_gate import ActionProposal
            dec = gate.submit(ActionProposal(command=final_action, params=_params[final_action],
                                             source="autonomous", rationale=reason))
            gate_decision = dec.to_dict()
        else:
            # fail-closed:gate 不可用时**不**直连硬件(自主路径绝不绕过 SciTX)。
            # action_gate 为纯 stdlib、导入可靠,此分支实际不触发;留作权威性硬约束。
            gate_decision = {"command": final_action, "decision": "BLOCKED",
                             "dispatched": False, "reasons": ["action_gate_unavailable_fail_closed"]}

    return {
        "role": "orchestrator",
        "action": final_action,
        "source_agent": source_agent,
        "reason": reason,
        "proposal_action": proposal["action"],
        "critic_approved": critic["approved"],
        "confidence": (proposal["confidence"] + critic["confidence"]) / 2,
        "gate_decision": gate_decision,
    }


def _run_decision_cycle(ctx: Dict[str, Any] = None) -> Dict[str, Any]:
    """Execute one full Planner → Critic → Orchestrator cycle."""
    if ctx is None:
        ctx = _get_latest_measurement_context()

    proposal = _planner_propose(ctx)
    critic = _critic_review(proposal, ctx)
    decision = _orchestrator_decide(proposal, critic, ctx)

    decision_record = {
        "id": uuid.uuid4().hex[:8],
        "timestamp": datetime.now().isoformat(),
        "run_id": ctx.get("run_id") or _agent_state.get("current_run_id"),
        "planner": proposal,
        "critic": critic,
        "orchestrator": decision,
        "action": decision["action"],
        "reasoning": decision["reason"],
        "confidence": decision["confidence"],
        "source": "rule_based",
    }
    _agent_state["decisions"].append(decision_record)
    _persist_decision(decision_record)
    return decision_record


@router.post("/start-run")
def start_run(req: StartRunRequest):
    run_id = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    _agent_state["current_run_id"] = run_id
    _agent_state["status"] = "running"
    _agent_state["decisions"] = []
    return {"ok": True, "run_id": run_id, "mode": req.mode}


@router.post("/decide")
def decide(req: DecideRequest):
    """Synchronous agent decision — runs full Planner→Critic→Orchestrator cycle."""
    ctx = _get_latest_measurement_context()
    if req.context:
        ctx.update(req.context)
    if req.run_id:
        ctx["run_id"] = req.run_id
    return _run_decision_cycle(ctx)


@router.get("/stream")
async def stream_decisions(request: Request):
    """SSE stream that replays recent decisions and then pushes new ones."""
    hw = get_hardware_adapter()

    async def event_generator():
        yield f"data: {json.dumps({'type': 'CONNECTED', 'timestamp': datetime.now().isoformat()})}\n\n"

        for d in _agent_state["decisions"][-50:]:
            yield f"data: {json.dumps({'type': 'PLAN_PROPOSED', 'payload': d.get('planner', {}), 'timestamp': d['timestamp']})}\n\n"
            yield f"data: {json.dumps({'type': 'CRITIC_REVIEWED', 'payload': d.get('critic', {}), 'timestamp': d['timestamp']})}\n\n"
            yield f"data: {json.dumps({'type': 'ACTION_EXECUTED', 'payload': d.get('orchestrator', {}), 'timestamp': d['timestamp']})}\n\n"

        last_count = len(_agent_state["decisions"])
        import asyncio
        for _ in range(300):
            if await request.is_disconnected():
                break
            current_count = len(_agent_state["decisions"])
            if current_count > last_count:
                for d in _agent_state["decisions"][last_count:]:
                    yield f"data: {json.dumps({'type': 'PLAN_PROPOSED', 'payload': d.get('planner', {}), 'timestamp': d['timestamp']})}\n\n"
                    yield f"data: {json.dumps({'type': 'CRITIC_REVIEWED', 'payload': d.get('critic', {}), 'timestamp': d['timestamp']})}\n\n"
                    yield f"data: {json.dumps({'type': 'ACTION_EXECUTED', 'payload': d.get('orchestrator', {}), 'timestamp': d['timestamp']})}\n\n"
                last_count = current_count
            await asyncio.sleep(1.0)

        yield f"data: {json.dumps({'type': 'STREAM_END'})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/status")
def agent_status():
    decisions = _agent_state["decisions"]
    return {
        "status": _agent_state["status"],
        "run_id": _agent_state["current_run_id"],
        "current_run_id": _agent_state["current_run_id"],
        "total_decisions": len(decisions),
        "config": _agent_state["config"],
        "latest_decision": decisions[-1] if decisions else None,
        "latest_decisions": decisions[-50:],
        "decisions": decisions[-50:],
    }


@router.get("/heartbeat")
def heartbeat():
    return {"alive": True, "timestamp": datetime.now().isoformat()}


@router.post("/config")
def update_config(config: dict):
    _agent_state["config"].update(config)
    _persist_config(_agent_state["config"])
    return {"ok": True, "config": _agent_state["config"]}


@router.post("/autonomous/start-thinking")
def start_thinking(req: ThinkingRequest):
    session_id = uuid.uuid4().hex[:12]
    ctx = _get_latest_measurement_context()
    if req.context:
        ctx.update(req.context)
    decision = _run_decision_cycle(ctx)

    _agent_state["sessions"][session_id] = {
        "status": "completed",
        "decision": decision,
        "events": [
            {"type": "PLAN_PROPOSED", "payload": decision["planner"], "timestamp": decision["timestamp"]},
            {"type": "CRITIC_REVIEWED", "payload": decision["critic"], "timestamp": decision["timestamp"]},
            {"type": "ACTION_EXECUTED", "payload": decision["orchestrator"], "timestamp": decision["timestamp"]},
        ],
    }
    return {"ok": True, "session_id": session_id, "status": "completed", "decision": decision}


@router.get("/autonomous/session/{session_id}/status")
def get_session_status(session_id: str):
    session = _agent_state["sessions"].get(session_id)
    if not session:
        return {"session_id": session_id, "status": "not_found", "decision": None}
    return {"session_id": session_id, "status": session["status"], "decision": session.get("decision")}


@router.get("/autonomous/session/{session_id}/events")
def get_session_events(session_id: str):
    session = _agent_state["sessions"].get(session_id)
    return {"session_id": session_id, "events": session["events"] if session else []}


@router.post("/autonomous/session/{session_id}/stop")
def stop_session(session_id: str):
    if session_id in _agent_state["sessions"]:
        _agent_state["sessions"][session_id]["status"] = "stopped"
    return {"ok": True, "session_id": session_id, "status": "stopped"}


@router.get("/autonomous/stream")
async def stream_autonomous(request: Request):
    """SSE stream for autonomous decisions — pushes real decisions as they occur."""
    async def event_generator():
        yield f"data: {json.dumps({'type': 'CONNECTED', 'timestamp': datetime.now().isoformat()})}\n\n"

        last_count = len(_agent_state["decisions"])
        import asyncio
        for _ in range(600):
            if await request.is_disconnected():
                break

            hw = get_hardware_adapter()
            if hw._running and hw._autonomous:
                ctx = _get_latest_measurement_context()
                decision = _run_decision_cycle(ctx)
                yield f"data: {json.dumps({'type': 'PLAN_PROPOSED', 'payload': decision.get('planner', {}), 'timestamp': decision['timestamp']})}\n\n"
                yield f"data: {json.dumps({'type': 'CRITIC_REVIEWED', 'payload': decision.get('critic', {}), 'timestamp': decision['timestamp']})}\n\n"
                yield f"data: {json.dumps({'type': 'ACTION_EXECUTED', 'payload': decision.get('orchestrator', {}), 'timestamp': decision['timestamp']})}\n\n"
                await asyncio.sleep(2.0)
            else:
                await asyncio.sleep(1.0)

        yield f"data: {json.dumps({'type': 'STREAM_END'})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/autonomous/auto-decision")
def auto_decision(req: DecideRequest):
    """Closed-loop fast decision after measurement — runs full cycle."""
    return decide(req)
