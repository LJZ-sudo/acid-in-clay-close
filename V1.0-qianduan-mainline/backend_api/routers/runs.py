# -*- coding: utf-8 -*-
"""Run audit & management routes — migrated from Flask runs_audit.py + FastAPI routes_runs.py.

Provides run lifecycle, event streaming (SSE + WebSocket), evidence, export.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

router = APIRouter()

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
RUNS_DIR = PROJECT_ROOT.parent / "experiments" / "runs"

_SAFE_ID_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.")


def _safe_run_dir(run_id: str) -> Path:
    """Resolve run directory with path-traversal protection."""
    if not run_id or not all(c in _SAFE_ID_CHARS for c in run_id):
        raise HTTPException(400, "Invalid run_id")
    run_dir = (RUNS_DIR / run_id).resolve()
    if not run_dir.is_relative_to(RUNS_DIR.resolve()):
        raise HTTPException(403, "Access denied")
    return run_dir


def _read_run_events(events_file: Path):
    events = []
    if not events_file.exists():
        return events
    for idx, line in enumerate(events_file.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            evt = json.loads(line)
            evt.setdefault("_line_idx", idx)
            events.append(evt)
        except Exception:
            continue
    return events


def _event_seq(evt: dict) -> int:
    for key in ("seq", "last_seq", "step_idx", "_line_idx"):
        value = evt.get(key)
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return 0


def _filter_events(events, since: Optional[int], last_seq: Optional[int], limit: int):
    cursor = last_seq if last_seq is not None else since
    rows = [evt for evt in events if cursor is None or _event_seq(evt) > cursor]
    return rows[-limit:]


class CreateRunRequest(BaseModel):
    profile: Optional[str] = None
    mode: str = "autonomous"
    auto_start: bool = False


class ControlRunRequest(BaseModel):
    action: str  # pause, resume, stop, manual_override


@router.get("")
def list_runs(
    status: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100),
):
    """List all runs."""
    if not RUNS_DIR.exists():
        return {"runs": [], "total": 0}
    runs = []
    for d in sorted(RUNS_DIR.iterdir(), reverse=True):
        manifest_file = d / "manifest.json"
        if manifest_file.exists():
            try:
                manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
                if status and manifest.get("status") != status:
                    continue
                runs.append({
                    "run_id": d.name,
                    "status": manifest.get("status", "unknown"),
                    "created_at": manifest.get("created_at"),
                    "profile": manifest.get("profile"),
                })
            except Exception:
                continue
    return {"runs": runs[:limit], "total": len(runs)}


@router.post("")
def create_run(req: CreateRunRequest):
    run_id = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "run_id": run_id,
        "status": "created",
        "created_at": datetime.now().isoformat(),
        "profile": req.profile,
        "mode": req.mode,
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (run_dir / "events.jsonl").write_text("", encoding="utf-8")
    (run_dir / "evidence").mkdir(exist_ok=True)
    return {"ok": True, "run_id": run_id, "manifest": manifest}


@router.get("/{run_id}")
def get_run(run_id: str):
    run_dir = _safe_run_dir(run_id)
    manifest_file = run_dir / "manifest.json"
    if not manifest_file.exists():
        raise HTTPException(status_code=404, detail="Run not found")
    return json.loads(manifest_file.read_text(encoding="utf-8"))


@router.get("/{run_id}/events")
def get_events(
    run_id: str,
    since: Optional[int] = Query(None),
    last_seq: Optional[int] = Query(None),
    limit: int = Query(500, ge=1, le=5000),
):
    events_file = _safe_run_dir(run_id) / "events.jsonl"
    events = _read_run_events(events_file)
    rows = _filter_events(events, since, last_seq, limit)
    return {"events": rows, "total": len(events), "returned": len(rows)}


@router.get("/{run_id}/events/stream")
async def stream_events(
    run_id: str,
    request: Request,
    since: Optional[int] = Query(None),
    last_seq: Optional[int] = Query(None),
):
    """SSE event stream for a run - polls for new events in real time."""
    import asyncio

    async def event_generator():
        events_file = _safe_run_dir(run_id) / "events.jsonl"
        sent_count = 0
        cursor = last_seq if last_seq is not None else since
        idle_ticks = 0
        max_idle = 300  # ~5 minutes without new events

        while idle_ticks < max_idle:
            if await request.is_disconnected():
                break

            if events_file.exists():
                lines = events_file.read_text(encoding="utf-8").strip().split("\n")
                lines = [l for l in lines if l.strip()]
                new_lines = lines[sent_count:]
                for line in new_lines:
                    try:
                        evt = json.loads(line)
                    except Exception:
                        sent_count += 1
                        continue
                    evt.setdefault("_line_idx", sent_count + 1)
                    if cursor is None or _event_seq(evt) > cursor:
                        yield f"data: {line}\n\n"
                        cursor = max(cursor or 0, _event_seq(evt))
                    sent_count += 1
                    idle_ticks = 0

            manifest_file = _safe_run_dir(run_id) / "manifest.json"
            if manifest_file.exists():
                try:
                    m = json.loads(manifest_file.read_text(encoding="utf-8"))
                    if m.get("status") in ("completed", "cancelled", "archived"):
                        remaining = events_file.read_text(encoding="utf-8").strip().split("\n") if events_file.exists() else []
                        remaining = [l for l in remaining if l.strip()]
                        for line in remaining[sent_count:]:
                            yield f"data: {line}\n\n"
                        yield f"data: {json.dumps({'type': 'STREAM_END'})}\n\n"
                        return
                except Exception:
                    pass

            idle_ticks += 1
            await asyncio.sleep(1.0)

        yield f"data: {json.dumps({'type': 'STREAM_END'})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.websocket("/ws/{run_id}")
async def websocket_events(websocket: WebSocket, run_id: str):
    """WebSocket event stream for a run."""
    await websocket.accept()
    try:
        events_file = _safe_run_dir(run_id) / "events.jsonl"
        if events_file.exists():
            for line in events_file.read_text(encoding="utf-8").strip().split("\n"):
                if line.strip():
                    await websocket.send_text(line)
        await websocket.send_text(json.dumps({"type": "STREAM_END"}))
    except WebSocketDisconnect:
        pass


@router.get("/{run_id}/manifest")
def get_manifest(run_id: str):
    manifest_file = _safe_run_dir(run_id) / "manifest.json"
    if not manifest_file.exists():
        raise HTTPException(status_code=404, detail="Manifest not found")
    return json.loads(manifest_file.read_text(encoding="utf-8"))


@router.get("/{run_id}/evidence")
def list_evidence(run_id: str):
    evidence_dir = _safe_run_dir(run_id) / "evidence"
    if not evidence_dir.exists():
        return {"evidence": []}
    items = []
    for f in sorted(evidence_dir.iterdir()):
        items.append({"id": f.stem, "filename": f.name, "size": f.stat().st_size})
    return {"evidence": items}


@router.post("/{run_id}/cancel")
def cancel_run(run_id: str):
    manifest_file = _safe_run_dir(run_id) / "manifest.json"
    if manifest_file.exists():
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        manifest["status"] = "cancelled"
        manifest_file.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return {"ok": True, "run_id": run_id, "status": "cancelled"}


@router.post("/{run_id}/control")
def control_run(run_id: str, req: ControlRunRequest):
    return {"ok": True, "run_id": run_id, "action": req.action}


@router.post("/{run_id}/replay")
def replay_run(run_id: str):
    return {"ok": True, "run_id": run_id, "message": "Replay initiated"}


@router.get("/{run_id}/baseline-equivalence")
def get_baseline_equivalence(run_id: str, format: str = "json"):
    """Baseline equivalence comparison (placeholder)."""
    data = {
        "run_id": run_id,
        "metrics": [],
        "message": "Baseline equivalence not yet computed for this run",
    }
    if format == "csv":
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse("metric,agent,baseline\n", media_type="text/csv")
    return data


@router.get("/{run_id}/export")
def export_run(run_id: str):
    return {"ok": True, "run_id": run_id, "message": "Export not yet implemented"}
