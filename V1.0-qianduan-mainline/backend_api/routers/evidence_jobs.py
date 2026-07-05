# -*- coding: utf-8 -*-
"""Global evidence & jobs routes — serves /api/evidence and /api/jobs endpoints.

These are called by the frontend runsAudit.js and are separate from the
run-scoped evidence endpoints in the runs router.
"""
from __future__ import annotations

import json
from pathlib import Path

from typing import Optional

import shutil

from fastapi import APIRouter, HTTPException, Query, UploadFile, File
from fastapi.responses import StreamingResponse

router = APIRouter()

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
RUNS_DIR = PROJECT_ROOT.parent / "experiments" / "runs"


@router.get("/evidence/{evidence_id}")
def get_evidence_by_id(evidence_id: str, download: int = 0):
    """Look up an evidence package by ID across all runs."""
    if not RUNS_DIR.exists():
        raise HTTPException(404, "Evidence not found")

    for run_dir in RUNS_DIR.iterdir():
        evidence_dir = run_dir / "evidence"
        if not evidence_dir.exists():
            continue
        for f in evidence_dir.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                if data.get("evidence_id") == evidence_id or f.stem == evidence_id:
                    if download:
                        content = json.dumps(data, indent=2, ensure_ascii=False)
                        return StreamingResponse(
                            iter([content]),
                            media_type="application/json",
                            headers={"Content-Disposition": f"attachment; filename={evidence_id}.json"},
                        )
                    return data
            except Exception:
                continue

    raise HTTPException(404, f"Evidence '{evidence_id}' not found")


@router.post("/jobs/threshold_sweep")
def threshold_sweep(payload: Optional[dict] = None):
    """Threshold/method sensitivity (M1-8 / G2): 转变对 Rb 方法 / KK 阈值 / 管线假阳性的稳健性。

    只读 stage0_v2 真实产物(rb_invariance + breakpoint_uncertainty + synthetic_validation);
    产物缺失时返回 generated=False + 生成命令(不伪造)。
    """
    from backend_api.services.sensitivity_jobs import run_threshold_sweep
    return run_threshold_sweep(payload)


@router.post("/jobs/ablation")
def ablation(payload: Optional[dict] = None):
    """Ablation (M1-8): Rb 提取策略消融(4 轨迹)+ 稳健回归消融(全点/稳健/留一)。

    只读 stage0_v2 真实产物(rb_invariance + arrhenius_robust);缺失返回生成命令。
    """
    from backend_api.services.sensitivity_jobs import run_ablation
    return run_ablation(payload)


@router.post("/jobs/report_scores")
def report_scores(payload: Optional[dict] = None):
    """Report scoring job (placeholder)."""
    return {"ok": True, "message": "Report scores not yet implemented", "results": []}


@router.get("/reports/check")
def check_reports(files: str = Query("")):
    """Check existence of multiple report files. Accepts comma-separated paths."""
    if not files:
        return {"results": {}}
    results = {}
    for f in files.split(","):
        f = f.strip()
        if not f:
            continue
        fpath = PROJECT_ROOT / f
        if not fpath.exists():
            fpath = PROJECT_ROOT.parent / "experiments" / "output" / f
        exists = fpath.exists() and fpath.resolve().is_relative_to(PROJECT_ROOT.resolve())
        results[f] = {"exists": exists, "size": fpath.stat().st_size if exists else 0}
    return {"results": results}


@router.get("/reports/download")
def download_report(file: str = Query("")):
    """Download a generated report file."""
    if not file:
        raise HTTPException(400, "No file specified")

    report_path = PROJECT_ROOT / file
    if not report_path.exists():
        output_path = PROJECT_ROOT.parent / "experiments" / "output" / file
        if output_path.exists():
            report_path = output_path
        else:
            raise HTTPException(404, f"Report file not found: {file}")

    if not report_path.resolve().is_relative_to(PROJECT_ROOT.resolve()):
        raise HTTPException(403, "Access denied")

    content = report_path.read_text(encoding="utf-8")
    ext = report_path.suffix.lower()
    mime = "text/markdown" if ext == ".md" else "application/json" if ext == ".json" else "text/plain"

    return StreamingResponse(
        iter([content]),
        media_type=mime,
        headers={"Content-Disposition": f"attachment; filename={report_path.name}"},
    )


LITERATURE_DIR = PROJECT_ROOT.parent / "experiments" / "raw" / "literature"
LITERATURE_RECS_PATH = PROJECT_ROOT.parent / "experiments" / "output" / "literature_recommendations.json"


@router.get("/literature/recommendations")
def get_literature_recommendations():
    """Get recommended search terms for literature retrieval."""
    if LITERATURE_RECS_PATH.exists():
        data = json.loads(LITERATURE_RECS_PATH.read_text(encoding="utf-8"))
        return {"ok": True, "recommendations": data}

    try:
        from stage3_mechanism.literature_recommender import generate_recommendations
        result = generate_recommendations(use_llm=False)
        LITERATURE_RECS_PATH.parent.mkdir(parents=True, exist_ok=True)
        LITERATURE_RECS_PATH.write_text(
            json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return {"ok": True, "recommendations": result}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.post("/literature/recommendations/regenerate")
def regenerate_literature_recommendations(use_llm: bool = False):
    """Regenerate literature search recommendations."""
    try:
        from stage3_mechanism.literature_recommender import generate_recommendations
        result = generate_recommendations(use_llm=use_llm)
        LITERATURE_RECS_PATH.parent.mkdir(parents=True, exist_ok=True)
        LITERATURE_RECS_PATH.write_text(
            json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return {"ok": True, "recommendations": result}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.get("/literature/files")
def list_literature_files():
    """List uploaded literature files."""
    LITERATURE_DIR.mkdir(parents=True, exist_ok=True)
    files = []
    for f in sorted(LITERATURE_DIR.iterdir()):
        if f.is_file() and f.suffix.lower() in (".pdf", ".txt", ".md", ".json"):
            files.append({
                "name": f.name,
                "size": f.stat().st_size,
                "type": f.suffix.lower(),
            })
    return {"ok": True, "files": files, "directory": str(LITERATURE_DIR)}


@router.post("/literature/upload")
async def upload_literature(file: UploadFile = File(...)):
    """Upload a literature file (PDF, TXT, MD) to data/literature/."""
    LITERATURE_DIR.mkdir(parents=True, exist_ok=True)
    allowed = {".pdf", ".txt", ".md", ".json"}
    ext = Path(file.filename or "unknown").suffix.lower()
    if ext not in allowed:
        raise HTTPException(400, f"File type {ext} not allowed. Accepted: {', '.join(allowed)}")

    safe_name = "".join(c for c in (file.filename or "upload") if c.isalnum() or c in ".-_ ")
    dest = LITERATURE_DIR / safe_name
    with open(dest, "wb") as f_out:
        shutil.copyfileobj(file.file, f_out)

    return {
        "ok": True,
        "filename": safe_name,
        "size": dest.stat().st_size,
        "path": str(dest),
    }
