# -*- coding: utf-8 -*-
"""Unified FastAPI backend for the EIS Agent system.

Consolidates the former Flask (port 5000) + FastAPI (port 8000) dual-server
architecture into a single FastAPI application with SocketIO support.

Run:
    uvicorn backend_api.main:app --host 0.0.0.0 --port 8000 --reload
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from contextlib import asynccontextmanager

from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend_api.routers import control, data, agent, agents, runs, pipeline, evidence_jobs, samples, campaigns, provenance

# SocketIO server (compatible with frontend socket.io-client)
try:
    import socketio as _sio_module
    sio = _sio_module.AsyncServer(async_mode="asgi", cors_allowed_origins="*")
    _sio_available = True
except ImportError:
    sio = None
    _sio_available = False
    print("[backend_api] python-socketio not installed — WebSocket disabled (REST/SSE still work)")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown hooks."""
    print("[backend_api] Starting up...")
    if _sio_available and sio is not None:
        print("[backend_api] SocketIO enabled")
        from backend_api.services.hardware_adapter import get_hardware_adapter
        hw = get_hardware_adapter()
        hw.set_sio_emit(sio.emit)
    yield
    print("[backend_api] Shutting down...")


fastapi_app = FastAPI(
    title="EIS Agent Orchestrator",
    version="2.0.0",
    description="Unified backend for the autonomous EIS measurement & analysis system",
    lifespan=lifespan,
)

fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@fastapi_app.get("/health")
def health():
    return {"status": "ok", "version": "2.0.0", "socketio": _sio_available}


fastapi_app.include_router(control.router, prefix="/api/control", tags=["Control"])
fastapi_app.include_router(data.router, prefix="/api/data", tags=["Data"])
fastapi_app.include_router(agent.router, prefix="/api/agent", tags=["Agent"])
fastapi_app.include_router(agents.router, prefix="/api/agents", tags=["Multi-Agent"])
fastapi_app.include_router(runs.router, prefix="/api/runs", tags=["Runs"])
# Legacy diagnostic only: mutating /api/pipeline triggers are disabled because
# the current mainline uses /api/control plus direct Stage2/Stage3 CLIs.
fastapi_app.include_router(pipeline.router, prefix="/api/pipeline", tags=["Pipeline"])
fastapi_app.include_router(evidence_jobs.router, prefix="/api", tags=["Evidence & Jobs"])
fastapi_app.include_router(samples.router, prefix="/api/samples", tags=["Samples & Closure Reports"])
fastapi_app.include_router(campaigns.router, prefix="/api/campaigns", tags=["Campaigns"])
fastapi_app.include_router(provenance.router, prefix="/api/provenance", tags=["Provenance"])

# Compatibility aliases: some frontend clients call /api/<endpoint> directly
@fastapi_app.post("/api/calculate_arrhenius", tags=["Data (compat)"])
def _compat_calculate_arrhenius(req: data.ArrheniusCalcRequest):
    return data.calculate_arrhenius(req)

@fastapi_app.post("/api/run_arrhenius_from_eis", tags=["Data (compat)"])
def _compat_arrhenius_from_eis(payload: Optional[dict] = None):
    return data.run_arrhenius_from_eis(payload)

@fastapi_app.post("/api/run_arrhenius_advanced", tags=["Data (compat)"])
def _compat_arrhenius_advanced(payload: Optional[dict] = None):
    return data.run_arrhenius_advanced(payload)

# SocketIO event handlers
if _sio_available and sio is not None:
    @sio.event
    async def connect(sid, environ):
        print(f"[sio] Client connected: {sid}")

    @sio.event
    async def disconnect(sid):
        print(f"[sio] Client disconnected: {sid}")

    @sio.event
    async def ping(sid, data=None):
        """Respond to client ping with pong (heartbeat)."""
        await sio.emit("pong", {"ts": data.get("ts") if data else None}, to=sid)

    @sio.event
    async def subscribe(sid, data=None):
        """Client subscribes to data channels."""
        channels = (data or {}).get("channels", [])
        for ch in channels:
            await sio.enter_room(sid, ch)
        await sio.emit("subscribed", {
            "channels": channels,
            "last_seq": (data or {}).get("last_seq", 0),
        }, to=sid)

    # Wrap FastAPI inside SocketIO ASGI app
    app = _sio_module.ASGIApp(sio, other_asgi_app=fastapi_app, socketio_path="/socket.io")
else:
    app = fastapi_app


def get_sio():
    """Get the SocketIO server instance for emitting events from other modules."""
    return sio
