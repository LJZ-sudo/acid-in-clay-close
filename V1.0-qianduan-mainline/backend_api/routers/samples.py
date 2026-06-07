# -*- coding: utf-8 -*-
"""Sample-centric routes — list / detail / closure report.

These endpoints expose Stage0 result bundles and the new SampleClosureReport
to the frontend SampleClosureCard page (paper §6.2).

Read-only by design: the Closure Report is a researcher-facing summary and
does NOT feed Stage1 / Stage2 / Stage3 (paper §4.1).
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

router = APIRouter()
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Stage0 bundle locations: support both legacy (output/stage0_results) and
# the per-stage local layout (stage0_measurement/output/stage0_results).
_STAGE0_RESULT_DIRS = [
    PROJECT_ROOT / "output" / "stage0_results",
    PROJECT_ROOT / "stage0_measurement" / "output" / "stage0_results",
]
# process_ao_stage0.py 默认把 bundle 写到按日期命名的子目录下，sample_id 在 JSON 里
# （例如文件夹 2026.5.12 / bundle.sample_id = ATA-2026-5-12-R0.35-N0.95）
_AO_STAGE0_RESULTS_ROOT = PROJECT_ROOT / "output" / "ao_stage0_results"


_SAFE_ID_CHARS = set(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_."
)


def _safe_sample_id(sample_id: str) -> str:
    if not sample_id or not all(c in _SAFE_ID_CHARS for c in sample_id):
        raise HTTPException(400, "Invalid sample_id")
    return sample_id


def _parse_r_n_from_chi_style_id(sample_id: str) -> Optional[Tuple[float, float]]:
    """从 CHI 材料名如 R0.35-N0.95-1 中解析 (R, N)，失败则 None。"""
    if not sample_id:
        return None
    m = re.search(r"R\s*([0-9.]+)\s*[-_]\s*N\s*([0-9.]+)", sample_id, re.I)
    if not m:
        return None
    try:
        return float(m.group(1)), float(m.group(2))
    except ValueError:
        return None


def _bundle_recipe_match(bundle: Dict[str, Any], r: float, n: float, tol: float = 0.03) -> bool:
    rec = bundle.get("recipe") or {}
    try:
        br = float(rec.get("R"))
        bn = float(rec.get("N"))
    except (TypeError, ValueError):
        return False
    return abs(br - r) <= tol and abs(bn - n) <= tol


def _iter_bundle_parent_dirs() -> List[Path]:
    """所有可能含有 stage0_result_bundle.json 的父目录。"""
    roots: List[Path] = list(_STAGE0_RESULT_DIRS)
    if _AO_STAGE0_RESULTS_ROOT.exists():
        roots.append(_AO_STAGE0_RESULTS_ROOT)
    out: List[Path] = []
    for root in roots:
        if not root.exists():
            continue
        try:
            for p in root.iterdir():
                if p.is_dir() and (p / "stage0_result_bundle.json").exists():
                    out.append(p)
        except OSError:
            continue
    return out


def _scan_bundle_dir_for_sample_id(sample_id: str) -> Optional[Path]:
    """按 bundle['sample_id'] 精确匹配，或按 R/N 与 CHI 短名宽松匹配（取最新 mtime）。"""
    sid = _safe_sample_id(sample_id)
    candidates: List[Tuple[float, Path]] = []
    rn = _parse_r_n_from_chi_style_id(sid)

    for parent in _iter_bundle_parent_dirs():
        bundle_path = parent / "stage0_result_bundle.json"
        bundle = _load_json(bundle_path)
        if not bundle:
            continue
        bid = str(bundle.get("sample_id") or "").strip()
        if bid == sid:
            return parent
        if rn and _bundle_recipe_match(bundle, rn[0], rn[1]):
            try:
                mt = bundle_path.stat().st_mtime
            except OSError:
                mt = 0.0
            candidates.append((mt, parent))

    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


def _resolve_sample_dir(sample_id: str) -> Path:
    sid = _safe_sample_id(sample_id)
    for root in _STAGE0_RESULT_DIRS:
        candidate = (root / sid).resolve()
        try:
            if not candidate.is_relative_to(root.resolve()):
                continue
        except ValueError:
            continue
        if candidate.exists() and candidate.is_dir():
            return candidate
    # ao_stage0_results/<date>/ 目录名通常不是 sample_id
    if _AO_STAGE0_RESULTS_ROOT.exists():
        ao_cand = (_AO_STAGE0_RESULTS_ROOT / sid).resolve()
        try:
            if ao_cand.is_relative_to(_AO_STAGE0_RESULTS_ROOT.resolve()) and ao_cand.is_dir():
                if (ao_cand / "stage0_result_bundle.json").exists():
                    return ao_cand
        except ValueError:
            pass

    scanned = _scan_bundle_dir_for_sample_id(sid)
    if scanned is not None:
        return scanned
    raise HTTPException(404, f"Sample {sample_id} not found")


def _load_json(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        logger.warning("Failed to load %s: %s", path, e)
        return None


def _list_all_sample_dirs() -> List[Path]:
    """列出所有含 bundle 的目录（含 ao_stage0_results 下的日期子目录）。"""
    out = _iter_bundle_parent_dirs()
    out.sort(key=lambda p: p.name)
    return out


def _bundle_summary_row(bundle: Dict[str, Any], closure: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    arr = bundle.get("arrhenius") or {}
    eis_pts = bundle.get("eis_points") or []
    ok_pts = [p for p in eis_pts if p.get("status") == "OK"]

    sigma_RT = None
    if ok_pts:
        rt = min(ok_pts, key=lambda p: abs((p.get("T_C") or 1e9) - 25.0))
        sigma_RT = rt.get("sigma_S_cm")

    row: Dict[str, Any] = {
        "sample_id": bundle.get("sample_id"),
        "material_system": bundle.get("material_system"),
        "R": (bundle.get("recipe") or {}).get("R"),
        "N": (bundle.get("recipe") or {}).get("N"),
        "n_eis_points": len(eis_pts),
        "n_eis_ok": len(ok_pts),
        "sigma_RT_S_per_cm": sigma_RT,
        "n_segments": arr.get("n_segments"),
        "transition_temps_K": arr.get("transition_temps_K") or [],
        "best_model_type": arr.get("best_model_type"),
        "arrhenius_confidence": arr.get("confidence"),
        "has_closure_report": closure is not None,
        "closure_llm_used": (closure or {}).get("meta", {}).get("llm_used"),
    }
    return row


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


class SampleListResponse(BaseModel):
    samples: List[Dict[str, Any]]
    total: int


@router.get("", response_model=SampleListResponse)
def list_samples(
    limit: int = Query(200, ge=1, le=1000),
    has_closure: Optional[bool] = None,
):
    """List all known samples with a thin summary row each."""
    # 同一 bundle.sample_id 可能同时出现在 stage0_results 与 ao_stage0_results，
    # 只保留 bundle 文件较新的一份，避免下拉框重复。
    best: Dict[str, tuple[float, Dict[str, Any]]] = {}
    for sd in _list_all_sample_dirs():
        bundle = _load_json(sd / "stage0_result_bundle.json")
        if bundle is None:
            continue
        closure = _load_json(sd / "closure_report.json")
        if has_closure is True and closure is None:
            continue
        if has_closure is False and closure is not None:
            continue
        row = _bundle_summary_row(bundle, closure)
        bid = str(row.get("sample_id") or sd.name).strip()
        bundle_path = sd / "stage0_result_bundle.json"
        try:
            mt = bundle_path.stat().st_mtime
        except OSError:
            mt = 0.0
        prev = best.get(bid)
        if prev is None or mt >= prev[0]:
            best[bid] = (mt, row)
    rows = [pair[1] for pair in sorted(best.values(), key=lambda x: x[0], reverse=True)]
    return SampleListResponse(samples=rows[:limit], total=len(rows))


@router.get("/resolve/{sample_id}")
def resolve_sample_alias(sample_id: str):
    """把 CHI 短名（如 R0.35-N0.95-1）解析到磁盘上的 Stage0 bundle 目录与 canonical id。"""
    sd = _resolve_sample_dir(sample_id)
    bundle = _load_json(sd / "stage0_result_bundle.json") or {}
    return {
        "input": sample_id,
        "canonical_sample_id": bundle.get("sample_id"),
        "bundle_dir": str(sd),
    }


@router.get("/{sample_id}")
def get_sample(sample_id: str):
    """Aggregated sample view: bundle + closure report (if any)."""
    sd = _resolve_sample_dir(sample_id)
    bundle = _load_json(sd / "stage0_result_bundle.json")
    if bundle is None:
        raise HTTPException(404, f"Bundle missing for {sample_id}")
    closure = _load_json(sd / "closure_report.json")
    canon = bundle.get("sample_id") or sample_id
    return {
        "sample_id": canon,
        "bundle": bundle,
        "closure_report": closure,
        "summary": _bundle_summary_row(bundle, closure),
    }


@router.get("/{sample_id}/bundle")
def get_bundle(sample_id: str):
    sd = _resolve_sample_dir(sample_id)
    bundle = _load_json(sd / "stage0_result_bundle.json")
    if bundle is None:
        raise HTTPException(404, f"Bundle missing for {sample_id}")
    return bundle


_CHI_FNAME_T = re.compile(r"_T(-?\d+(?:\.\d+)?)_", re.I)


def _resolve_source_folder(sd: Path) -> Optional[Path]:
    """Find the on-disk folder that holds raw CHI .txt files for this sample.

    experiment_metadata.json was originally written with absolute Windows paths
    that may point to a different machine; we re-anchor under PROJECT_ROOT/data
    if needed, then try a few sensible siblings (output/.../<date> -> data/ao/<date>).
    """
    meta = _load_json(sd / "experiment_metadata.json") or {}
    candidates: List[Path] = []
    raw = meta.get("source_folder")
    if raw:
        p = Path(raw)
        if p.exists():
            candidates.append(p)
        # Reanchor: take trailing "data/ao/<...>" or just last segment under data/ao
        parts = p.parts
        if "data" in parts:
            i = parts.index("data")
            candidates.append(PROJECT_ROOT.joinpath(*parts[i:]))
        candidates.append(PROJECT_ROOT / "data" / "ao" / p.name)
    # sd 自身的目录名常常就是日期或 <date>__<tag>
    name = sd.name
    base = name.split("__", 1)[0]
    candidates.append(PROJECT_ROOT / "data" / "ao" / base)
    candidates.append(PROJECT_ROOT / "data" / "ao" / name)
    for c in candidates:
        try:
            if c.exists() and c.is_dir():
                return c
        except OSError:
            continue
    return None


def _parse_chi_spectrum(path: Path) -> Optional[Dict[str, Any]]:
    """Parse a CHI EIS .txt file → {points: [{freq, zReal, zImag, zMag, phase}], T_C}."""
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
    points: List[Dict[str, float]] = []
    in_table = False
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        if not in_table:
            if s.lower().startswith("freq/hz"):
                in_table = True
            continue
        parts = [p.strip() for p in s.split(",")]
        if len(parts) < 3:
            continue
        try:
            f = float(parts[0]); zr = float(parts[1]); zi = float(parts[2])
        except ValueError:
            continue
        zm = float(parts[3]) if len(parts) >= 4 and parts[3] else (zr * zr + zi * zi) ** 0.5
        ph = float(parts[4]) if len(parts) >= 5 and parts[4] else None
        points.append({"freq": f, "zReal": zr, "zImag": zi, "zMag": zm, "phase": ph})
    if not points:
        return None
    t_c: Optional[float] = None
    m = _CHI_FNAME_T.search(path.name)
    if m:
        try:
            t_c = float(m.group(1))
        except ValueError:
            t_c = None
    return {"T_C": t_c, "file": path.name, "n_points": len(points), "points": points}


@router.get("/{sample_id}/eis-spectra")
def get_eis_spectra(sample_id: str, t_c: Optional[float] = Query(None, description="若指定，只返回最接近该温度(°C)的一个频谱")):
    """Return raw EIS Nyquist spectra parsed from the CHI .txt files used to
    build this sample's bundle. One entry per temperature point.

    Designed for the Analysis page's "已落盘样品" view: lets the frontend draw
    the real Nyquist curve (not just the aggregated rb/sigma scalars).
    """
    sd = _resolve_sample_dir(sample_id)
    bundle = _load_json(sd / "stage0_result_bundle.json") or {}
    geometry = bundle.get("geometry") or {}
    eis_meta_by_t = {}
    for pt in (bundle.get("eis_points") or []):
        if pt.get("T_C") is not None:
            eis_meta_by_t[round(float(pt["T_C"]), 2)] = pt

    src = _resolve_source_folder(sd)
    if src is None:
        raise HTTPException(404, "原始 CHI 频谱目录不可访问（experiment_metadata.source_folder 未指向本机存在的路径）。")

    spectra: List[Dict[str, Any]] = []
    for txt in sorted(src.glob("*.txt")):
        if "制备" in txt.name:
            continue
        spec = _parse_chi_spectrum(txt)
        if spec is None:
            continue
        meta = eis_meta_by_t.get(round(spec["T_C"], 2)) if spec.get("T_C") is not None else None
        if meta:
            spec["rb_ohm"] = meta.get("rb_ohm")
            spec["sigma_S_cm"] = meta.get("sigma_S_cm")
            spec["status"] = meta.get("status")
            spec["rb_confidence"] = meta.get("rb_confidence")
        spectra.append(spec)

    spectra = [s for s in spectra if s.get("T_C") is not None]
    spectra.sort(key=lambda s: s["T_C"])
    if not spectra:
        raise HTTPException(404, f"在 {src} 下未找到可解析的 EIS .txt 频谱。")

    if t_c is not None:
        nearest = min(spectra, key=lambda s: abs(s["T_C"] - float(t_c)))
        spectra = [nearest]

    return {
        "sample_id": (bundle.get("sample_id") or sample_id),
        "source_folder": str(src),
        "geometry": geometry,
        "n_spectra": len(spectra),
        "spectra": spectra,
    }


@router.get("/{sample_id}/closure-report")
def get_closure_report(sample_id: str):
    sd = _resolve_sample_dir(sample_id)
    closure = _load_json(sd / "closure_report.json")
    if closure is None:
        raise HTTPException(404, "Closure report not generated yet")
    return closure


class GenerateClosureRequest(BaseModel):
    use_llm: bool = True
    model: Optional[str] = None
    user_prep_form: Optional[Dict[str, Any]] = None


@router.post("/{sample_id}/closure-report")
def generate_closure_report(sample_id: str, req: Optional[GenerateClosureRequest] = None):
    """Generate (or regenerate) a closure report for the given sample.

    The endpoint is intentionally synchronous and lightweight; for batch jobs
    use `stage0_measurement/run_closure_offline.py` from the CLI.
    """
    if req is None:
        req = GenerateClosureRequest()
    sd = _resolve_sample_dir(sample_id)
    bundle_path = sd / "stage0_result_bundle.json"
    if not bundle_path.exists():
        raise HTTPException(404, f"Bundle missing for {sample_id}")

    # Lazy import to keep router import-time light.
    import sys

    stage0_root = PROJECT_ROOT / "stage0_measurement"
    if str(stage0_root) not in sys.path:
        sys.path.insert(0, str(stage0_root))
    from modules.closure.closure_agent import (  # type: ignore
        _default_model_settings,
        generate_sample_closure_report,
        write_report,
    )
    from modules.closure.closure_schema import UserPrepForm  # type: ignore

    user_prep_form: Optional[UserPrepForm] = None
    user_prep_text: Optional[str] = None
    if req.user_prep_form:
        try:
            user_prep_form = UserPrepForm.model_validate(req.user_prep_form)
            user_prep_text = json.dumps(req.user_prep_form, sort_keys=True, ensure_ascii=False)
        except Exception as e:  # noqa: BLE001
            raise HTTPException(400, f"Invalid user_prep_form: {e}") from e
    else:
        sidecar = sd / "user_prep.json"
        if sidecar.exists():
            try:
                payload = json.loads(sidecar.read_text(encoding="utf-8"))
                user_prep_form = UserPrepForm.model_validate(payload)
                user_prep_text = json.dumps(payload, sort_keys=True, ensure_ascii=False)
            except Exception:
                pass

    settings = None
    if req.model:
        settings = _default_model_settings()
        settings["model"] = req.model

    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    report = generate_sample_closure_report(
        bundle=bundle,
        user_prep_form=user_prep_form,
        use_llm=req.use_llm,
        model_settings=settings,
        user_prep_text=user_prep_text,
    )
    out = sd / "closure_report.json"
    write_report(report, out)
    return {
        "ok": True,
        "sample_id": sample_id,
        "llm_used": report.meta.llm_used,
        "fallback_reason": report.meta.fallback_reason,
        "path": str(out.relative_to(PROJECT_ROOT)),
    }
