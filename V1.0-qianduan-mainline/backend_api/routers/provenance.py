# -*- coding: utf-8 -*-
"""Read-only provenance endpoint.

Surfaces the tamper-evidence anchors behind the prospective-validation story:
  - the current git commit / branch (the freeze timestamp that orders
    "preregister -> push -> then measure"),
  - the configured LLM (provider + model),
  - the prospective preregistration registry (LLM-selected candidates plus
    their allowed / forbidden claims) read straight off disk.

This router performs read-only IO only (git metadata + JSON files). It does
NOT run any optimisation / analysis logic and never mutates state.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter

router = APIRouter()

# backend_api/routers/provenance.py -> parents[2] == V1.0-qianduan-mainline
MAINLINE_ROOT = Path(__file__).resolve().parents[2]
# repo root is one level above the mainline folder
_REPO_ROOT = MAINLINE_ROOT.parent
_TIMING_REGISTRY = (
    MAINLINE_ROOT
    / "stage3_mechanism" / "data" / "validation" / "timing_reference_registry.json"
)
_LINE_B_RECIPE = (
    _REPO_ROOT
    / "experiments" / "prospective" / "line_B_mobo_closed_loop" / "official_recipe.json"
)


def _git(*args: str) -> Optional[str]:
    """Run a read-only git command from the repo; return stripped stdout or None."""
    try:
        out = subprocess.run(
            ["git", *args],
            cwd=str(MAINLINE_ROOT),
            capture_output=True,
            text=True,
            timeout=5,
        )
        if out.returncode == 0:
            return out.stdout.strip()
    except Exception:
        return None
    return None


def _git_info() -> Dict[str, Any]:
    return {
        "commit": _git("rev-parse", "HEAD"),
        "commit_short": _git("rev-parse", "--short", "HEAD"),
        "committed_at": _git("log", "-1", "--format=%cI"),
        "subject": _git("log", "-1", "--format=%s"),
        "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
        "remote": _git("remote", "get-url", "origin"),
    }


def _llm_info() -> Dict[str, Any]:
    """Read the live agent LLM config (provider + model). Display only."""
    cfg: Dict[str, Any] = {}
    try:
        from backend_api.routers.agent import _agent_state

        cfg = dict(_agent_state.get("config") or {})
    except Exception:
        cfg = {}
    return {
        "provider": cfg.get("api_provider"),
        "model": cfg.get("model"),
    }


def _prereg_info() -> Dict[str, Any]:
    if not _TIMING_REGISTRY.exists():
        return {"available": False}
    try:
        data = json.loads(_TIMING_REGISTRY.read_text(encoding="utf-8"))
    except Exception:
        return {"available": False}

    notes = data.get("notes", "") or ""
    candidates: List[Dict[str, Any]] = []
    for c in data.get("candidates", []):
        candidates.append(
            {
                "candidate_id": c.get("candidate_id"),
                "instance_name": c.get("instance_name"),
                "rank_before_experiment": c.get("rank_before_experiment"),
                "discovery_mode": c.get("discovery_mode"),
                "validation_status": c.get("validation_status"),
                "allowed_claim": c.get("allowed_claim"),
                "forbidden_claim": c.get("forbidden_claim"),
            }
        )
    return {
        "available": True,
        "source_file": str(_TIMING_REGISTRY.relative_to(MAINLINE_ROOT)).replace("\\", "/"),
        "preregistered_at": data.get("preregistered_at"),
        "run_id": data.get("run_id"),
        "discovery_mode": data.get("discovery_mode"),
        # The on-disk anchor is an honestly-labelled reconstruction; surface that
        # so the UI never overstates the provenance.
        "reconstructed": "RECONSTRUCTED" in notes,
        "notes": notes,
        "candidates": candidates,
    }


def _line_b_info() -> Dict[str, Any]:
    """Surface the frozen Line-B official recipe (raw MOBO -> LLM guardrail).

    This is the on-disk single-source-of-truth produced by
    ``stage1_optimization/line_b_guardrail_run.py``; display only.
    """
    if not _LINE_B_RECIPE.exists():
        return {"available": False}
    try:
        data = json.loads(_LINE_B_RECIPE.read_text(encoding="utf-8"))
    except Exception:
        return {"available": False}
    data["available"] = True
    data["source_file"] = (
        str(_LINE_B_RECIPE.relative_to(_REPO_ROOT)).replace("\\", "/")
    )
    return data


@router.get("")
def get_provenance() -> Dict[str, Any]:
    """Aggregate read-only provenance: git anchor + LLM config + preregistration."""
    return {
        "git": _git_info(),
        "llm": _llm_info(),
        "preregistration": _prereg_info(),
        "line_b": _line_b_info(),
    }
