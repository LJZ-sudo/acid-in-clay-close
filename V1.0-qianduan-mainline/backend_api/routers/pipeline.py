# -*- coding: utf-8 -*-
"""Legacy pipeline trigger routes.

The current mainline no longer has a repo-root ``run_pipeline.py`` entrypoint.
Keeping these routes as queued subprocess triggers would silently point users at
a broken path, so mutating trigger endpoints are disabled with an explicit
diagnostic. Status endpoints remain available for legacy UI probes.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
RUN_PIPELINE = PROJECT_ROOT / "run_pipeline.py"
LEGACY_MESSAGE = (
    "The legacy /api/pipeline trigger is disabled because run_pipeline.py is "
    "not part of the current mainline. Use /api/control for Stage0/Stage1 real "
    "runs, stage2_statistics/main_agent.py for Stage2, and "
    "stage3_mechanism/src/s8_stage3/orchestrator/run_stage3.py for Stage3."
)


class Stage0BatchRequest(BaseModel):
    sample_id: Optional[str] = None


class Stage1Request(BaseModel):
    sample_id: Optional[str] = None


class PipelineStatus(BaseModel):
    stage: str
    status: str
    message: str = ""


_pipeline_status: dict[str, PipelineStatus] = {}


def _disabled_detail(stage: str, requested: Optional[dict] = None) -> dict:
    return {
        "ok": False,
        "stage": stage,
        "status": "disabled",
        "mode": "legacy_disabled",
        "message": LEGACY_MESSAGE,
        "run_pipeline_path": str(RUN_PIPELINE),
        "run_pipeline_exists": RUN_PIPELINE.exists(),
        "requested": requested or {},
        "current_entrypoints": {
            "stage0_stage1_real": "/api/control/start",
            "stage2": "python stage2_statistics/main_agent.py stage2_statistics/data/s8_input.csv",
            "stage3": (
                "python -m s8_stage3.orchestrator.run_stage3 --mode real "
                "--stage2-output-dir stage2_statistics/exports"
            ),
        },
    }


def _raise_disabled(stage: str, requested: Optional[dict] = None) -> None:
    _pipeline_status[stage] = PipelineStatus(
        stage=stage,
        status="disabled",
        message=LEGACY_MESSAGE,
    )
    raise HTTPException(status_code=410, detail=_disabled_detail(stage, requested))


@router.post("/stage0/batch")
def trigger_stage0_batch(req: Stage0BatchRequest):
    """Legacy Stage0 batch trigger, disabled for the current mainline."""
    _raise_disabled("stage0", {"sample_id": req.sample_id})


@router.post("/stage1")
def trigger_stage1(req: Stage1Request):
    """Legacy Stage1 trigger, disabled for the current mainline."""
    _raise_disabled("stage1", {"sample_id": req.sample_id})


@router.post("/stage2")
def trigger_stage2(adaptive: bool = True):
    """Legacy Stage2 trigger, disabled for the current mainline."""
    _raise_disabled("stage2", {"adaptive": adaptive})


@router.post("/stage3")
def trigger_stage3():
    """Legacy Stage3 trigger, disabled for the current mainline."""
    _raise_disabled("stage3")


@router.get("/status/{stage}")
def get_pipeline_status(stage: str):
    """Return diagnostic status for a legacy pipeline stage."""
    if stage in _pipeline_status:
        return _pipeline_status[stage].model_dump()
    return {
        "stage": stage,
        "status": "disabled",
        "mode": "legacy_disabled",
        "message": LEGACY_MESSAGE,
        "run_pipeline_exists": RUN_PIPELINE.exists(),
    }


@router.get("/status")
def get_all_pipeline_status():
    """Return legacy-disabled status for all historical stages."""
    stages = ["stage0", "stage1", "stage2", "stage3"]
    return {
        stage: _pipeline_status.get(
            stage,
            PipelineStatus(stage=stage, status="disabled", message=LEGACY_MESSAGE),
        ).model_dump()
        for stage in stages
    }
