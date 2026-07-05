# -*- coding: utf-8 -*-
"""Data query routes — serves measurement data from both static files and live HardwareAdapter.

All endpoints that display scientific data call real analysis code from
stage0_measurement modules when available.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Optional, List

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel

from backend_api.services.hardware_adapter import get_hardware_adapter

router = APIRouter()

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

_SAFE_ID_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.")


def _read_chi_txt(file_path: str):
    """Parse a CHI EIS .txt file → (frequencies, z_real, z_imag) lists.

    Tolerant of header lines + extra whitespace.  Returns empty lists on
    any error rather than raising.
    """
    p = Path(file_path)
    if not p.exists():
        return [], [], []
    freqs, zr, zi = [], [], []
    try:
        lines = p.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:  # noqa: BLE001
        return [], [], []
    # CHI exports use either tab or comma separators with a header block
    # ending at the first numeric line.  Walk the file and pick out rows
    # whose first 3 columns parse as floats.
    for raw in lines:
        line = raw.strip()
        if not line or line[0].isalpha():
            continue
        parts = [t for t in line.replace(",", " ").split() if t]
        if len(parts) < 3:
            continue
        try:
            f, r, i = float(parts[0]), float(parts[1]), float(parts[2])
        except ValueError:
            continue
        freqs.append(f)
        zr.append(r)
        zi.append(i)
    return freqs, zr, zi


def _validate_id(value: str, name: str = "id") -> str:
    """Reject path-traversal characters in user-supplied IDs."""
    if not value or not all(c in _SAFE_ID_CHARS for c in value):
        raise HTTPException(400, f"Invalid {name}")
    return value


class ArrheniusCalcRequest(BaseModel):
    conductivity_data: List[dict]
    segmentation: Optional[dict] = None
    source_run_id: Optional[str] = None


class NextPlanDecision(BaseModel):
    decision: str = "approved"
    notes: Optional[str] = None


@router.get("/measurements")
def get_measurements(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
):
    """Paginated measurement history — merges static results with live data."""
    hw = get_hardware_adapter()
    live = hw.get_measurements()

    results_dir = PROJECT_ROOT.parent / "experiments" / "output" / "phase1_results"
    static_measurements = []
    if results_dir.exists():
        files = sorted(results_dir.glob("*_analysis_result.json"))
        for f in files:
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                static_measurements.append({
                    "sample_id": data.get("sample_id", f.stem.replace("_analysis_result", "")),
                    "file": f.name,
                    "source": "static",
                })
            except Exception:
                continue

    all_measurements = static_measurements + [
        {**m, "source": "live"} for m in live
    ]
    total = len(all_measurements)
    page = all_measurements[offset: offset + limit]
    return {"measurements": page, "total": total, "offset": offset, "limit": limit}


@router.get("/current_eis")
def get_current_eis():
    hw = get_hardware_adapter()
    measurements = hw.get_measurements()
    if measurements:
        latest = measurements[-1]
        return {"data": latest, "source": "live"}
    return {"data": None, "message": "No active measurement"}


@router.get("/measurements/{index}/eis")
def get_eis_by_index(index: int):
    """Return the raw EIS spectrum for measurement ``index``.

    Response shape (mirrors what Analysis.jsx expects):

    ``{ data: <measurement_dict>, eis: { points: [{z_real, z_imag, frequency}, ...],
                                          frequencies, z_real, z_imag } }``
    """
    hw = get_hardware_adapter()
    measurements = hw.get_measurements()
    if not (0 <= index < len(measurements)):
        raise HTTPException(404, f"Measurement index {index} not found")
    m = measurements[index]
    freqs = m.get("frequencies") or []
    zr = m.get("z_real") or []
    zi = m.get("z_imag") or []
    # Fallback: re-read the CHI .txt file if the arrays weren't kept in memory
    # (this can happen for measurements imported from disk after a restart).
    if (not freqs) and m.get("raw_eis_file"):
        try:
            freqs2, zr2, zi2 = _read_chi_txt(m["raw_eis_file"])
            freqs, zr, zi = freqs2, zr2, zi2
        except Exception:  # noqa: BLE001
            pass
    points = []
    n = min(len(freqs), len(zr), len(zi))
    for i in range(n):
        points.append({
            "frequency": freqs[i],
            "z_real": zr[i],
            "z_imag": zi[i],
        })
    r2 = m.get("r_squared") if m.get("r_squared") is not None else m.get("fit_quality")
    sig = m.get("conductivity_S_cm")
    qc = m.get("qc_grade") or m.get("critic_grade")
    return {
        "data": m,
        "eis": {
            "points": points,
            "frequencies": freqs,
            "z_real": zr,
            "z_imag": zi,
            "n_points": n,
            "temperature_C": m.get("temperature_C"),
            "rb_ohm": m.get("rb_ohm"),
            "conductivity_S_cm": sig,
            "sigma_S_cm": sig,
            "r_squared": r2,
            "qc_grade": qc,
            "qc": qc,
            "raw_eis_file": m.get("raw_eis_file"),
        },
    }


@router.get("/phase_transitions")
def get_phase_transitions():
    hw = get_hardware_adapter()
    transitions = [
        e for e in hw.get_events()
        if e.get("type") == "PHASE_TRANSITION_DETECTED"
    ]
    return {"phase_transitions": transitions}


@router.get("/arrhenius")
def get_arrhenius(sample_id: Optional[str] = None):
    if not sample_id:
        return {"error": "sample_id required"}
    _validate_id(sample_id, "sample_id")
    result_file = PROJECT_ROOT.parent / "experiments" / "output" / "phase1_results" / f"{sample_id}_analysis_result.json"
    if not result_file.exists():
        raise HTTPException(404, f"Result not found for {sample_id}")
    data = json.loads(result_file.read_text(encoding="utf-8"))
    return {
        "sample_id": sample_id,
        "arrhenius": data.get("arrhenius_analysis", {}),
    }


@router.get("/arrhenius/realtime")
def get_arrhenius_realtime():
    """Scatter points from current measurements plus optional segmented Arrhenius fit.

    ``arrhenius_fit`` is the live snapshot written only after a **successful** global
    ``_run_global_arrhenius`` finalize (not updated from incremental per-point fits).
    Axes match ``analyze_arrhenius``: x = 1000/T (1/K), y = ln(σ) (S/cm natural log).
    """
    hw = get_hardware_adapter()
    measurements = hw.get_measurements()
    sample_id = getattr(hw, "_sample_id", None)
    points = []
    for m in measurements:
        t_k = m.get("temperature_K")
        cond = m.get("conductivity_S_cm")
        t_c = m.get("temperature_C")
        if t_k and cond and t_k > 0 and cond > 0:
            inv_t = 1000.0 / float(t_k)
            ln_s = math.log(float(cond))
            points.append({
                "1000_T": round(inv_t, 6),
                "ln_sigma": round(ln_s, 6),
                "log_sigma": round(math.log10(float(cond)), 6),
                "temperature_K": t_k,
                "temperature_C": t_c,
                "T_C": t_c,
                "sigma_S_cm": cond,
                "conductivity_S_cm": cond,
                "rb_ohm": m.get("rb_ohm"),
                "step_idx": m.get("step_idx"),
            })
    snap = None
    try:
        snap = hw.get_live_arrhenius_snapshot()
    except Exception:
        snap = None
    gbl = None
    try:
        gbl = hw.get_global_arrhenius()
    except Exception:
        gbl = None
    return {
        "sample_id": sample_id,
        "points": points,
        "count": len(points),
        "arrhenius_fit": snap,
        "global_arrhenius": gbl,
    }


@router.post("/calculate_arrhenius")
def calculate_arrhenius(req: ArrheniusCalcRequest):
    """Run Arrhenius segmented analysis on provided conductivity data.

    When stage0 is importable, uses ``extract_arrhenius_series_from_records`` (same screening as
    mainline: T, σ, Rb ranges and Rb monotonicity along cooling). Rows must include ``rb_ohm``.

    Falls back to a basic linear fit when stage0 is not importable or the scientific step fails.
    """
    rows = req.conductivity_data
    if len(rows) < 5:
        return {"success": False, "error": "Need at least 5 data points"}

    records = []
    for row in rows:
        t = row.get("temperature_K")
        s = row.get("sigma_S_per_cm") or row.get("conductivity_S_per_cm") or row.get("conductivity_S_cm")
        rb = row.get("rb_ohm") or row.get("rb")
        if t is None or s is None or rb is None:
            continue
        try:
            records.append(
                {
                    "temperature_K": float(t),
                    "conductivity_S_cm": float(s),
                    "rb_ohm": float(rb),
                }
            )
        except (TypeError, ValueError):
            continue

    try:
        from stage0_measurement.modules.analysis.eis_pipeline import (
            extract_valid_arrhenius_series,
            analyze_arrhenius_series,
        )
    except ImportError:
        extract_valid_arrhenius_series = None
        analyze_arrhenius_series = None

    temps_K: list = []
    conds: list = []

    if extract_valid_arrhenius_series is not None:
        temps_K, conds = extract_valid_arrhenius_series(
            records,
            temperature_key="temperature_K",
            conductivity_key="conductivity_S_cm",
            rb_key="rb_ohm",
        )
        if len(temps_K) < 5:
            return {
                "success": False,
                "error": "Insufficient points after unified filter (need ≥5 rows each with "
                "temperature_K, sigma, and rb_ohm).",
            }
    else:
        for row in rows:
            t = row.get("temperature_K")
            s = row.get("sigma_S_per_cm") or row.get("conductivity_S_per_cm") or row.get("conductivity_S_cm")
            if t and s and float(t) > 0 and float(s) > 0:
                temps_K.append(float(t))
                conds.append(float(s))
        if len(temps_K) < 5:
            return {"success": False, "error": "Insufficient valid data points after filtering"}

    if analyze_arrhenius_series is not None:
        try:
            seg_params = req.segmentation or {}
            # Canonical scientific Arrhenius analyzer (AICc-based segment selection,
            # capped at 3 segments). Note: legacy `max_segments` and `alpha`
            # parameters from the deprecated arrhenius_scientific module are no
            # longer honored; the new analyzer auto-selects segments via AICc.
            result = analyze_arrhenius_series(
                records,
                min_points=seg_params.get("min_points", 5),
                temperature_key="temperature_K",
                conductivity_key="conductivity_S_cm",
                rb_key="rb_ohm",
            )
            if result.get("success"):
                segments_out = []
                for seg in result.get("segments", []):
                    segments_out.append({
                        "segment": seg.get("segment_id", seg.get("label", "")),
                        "Ea_kJ_mol": seg.get("Ea_kJ_mol", seg.get("activation_energy_kJ_mol")),
                        "sigma0_S_per_cm": seg.get("sigma0", seg.get("pre_exponential")),
                        "T_range_K": seg.get("T_range_K", seg.get("temperature_range_K", [])),
                        "points": seg.get("n_points", seg.get("data_points")),
                        "r_squared": seg.get("r_squared", seg.get("R2")),
                    })

                phase_transitions = []
                for t_k in result.get("transition_temps_K", []):
                    if isinstance(t_k, (int, float)) and t_k > 0:
                        phase_transitions.append({
                            "Tc_K": t_k,
                            "temperature_C": t_k - 273.15,
                        })

                return {
                    "success": True,
                    "source": "stage0_scientific",
                    "advanced_arrhenius_results": segments_out,
                    "phase_transitions": phase_transitions,
                    "n_segments": result.get("n_segments", len(segments_out)),
                    "AIC": result.get("AIC"),
                    "BIC": result.get("BIC"),
                    "r_squared_overall": result.get("r_squared_overall"),
                    "segmentation_meta": result.get("segmentation_meta", {}),
                    "conductivity_data": [{"temperature_K": t, "sigma_S_per_cm": s} for t, s in zip(temps_K, conds)],
                }
        except Exception as e:
            return {"success": False, "error": f"Arrhenius analysis failed: {str(e)}"}

    inv_t = [1000.0 / t for t in temps_K]
    ln_s = [math.log(s) for s in conds]
    n = len(inv_t)
    sum_x = sum(inv_t)
    sum_y = sum(ln_s)
    sum_xy = sum(x * y for x, y in zip(inv_t, ln_s))
    sum_x2 = sum(x * x for x in inv_t)
    denom = n * sum_x2 - sum_x * sum_x
    if abs(denom) < 1e-30:
        return {"success": False, "error": "Degenerate data"}

    slope = (n * sum_xy - sum_x * sum_y) / denom
    intercept = (sum_y - slope * sum_x) / n
    R = 8.314e-3
    Ea_kJ = -slope * R

    ss_res = sum((y - (slope * x + intercept)) ** 2 for x, y in zip(inv_t, ln_s))
    ss_tot = sum((y - sum_y / n) ** 2 for y in ln_s)
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0

    return {
        "success": True,
        "source": "fallback_linear",
        "advanced_arrhenius_results": [{
            "segment": "single",
            "Ea_kJ_mol": round(Ea_kJ, 3),
            "sigma0_S_per_cm": math.exp(intercept),
            "T_range_K": [min(temps_K), max(temps_K)],
            "points": n,
            "r_squared": round(r2, 6),
        }],
        "phase_transitions": [],
        "n_segments": 1,
        "r_squared_overall": round(r2, 6),
        "conductivity_data": [{"temperature_K": t, "sigma_S_per_cm": s} for t, s in zip(temps_K, conds)],
    }


@router.get("/report")
@router.get("/report/{exp_id}")
def get_report(exp_id: Optional[str] = None, language: str = "en-US"):
    if not exp_id:
        return {"error": "sample_id required"}
    _validate_id(exp_id, "exp_id")
    report_dir = PROJECT_ROOT.parent / "experiments" / "output" / "stage1_reports"
    report_file = report_dir / f"{exp_id}_scientific_state_report.md"
    if not report_file.exists():
        raise HTTPException(404, f"Report not found for {exp_id}")
    return {"sample_id": exp_id, "content": report_file.read_text(encoding="utf-8")}


@router.get("/experiments")
def list_experiments():
    results_dir = PROJECT_ROOT.parent / "experiments" / "output" / "phase1_results"
    if not results_dir.exists():
        return {"experiments": []}
    files = sorted(results_dir.glob("*_analysis_result.json"))
    return {"experiments": [
        {"sample_id": f.stem.replace("_analysis_result", ""), "file": f.name}
        for f in files
    ]}


@router.get("/history")
def get_history():
    return list_experiments()


@router.get("/experiment/{exp_id}")
def get_experiment(exp_id: str):
    _validate_id(exp_id, "exp_id")
    result_file = PROJECT_ROOT.parent / "experiments" / "output" / "phase1_results" / f"{exp_id}_analysis_result.json"
    if not result_file.exists():
        raise HTTPException(404, f"Experiment not found: {exp_id}")
    return json.loads(result_file.read_text(encoding="utf-8"))


@router.get("/next-plan")
@router.get("/next-plan/{exp_id}")
def get_next_plan(exp_id: Optional[str] = None):
    """Get the next experiment plan — calls stage1_optimization if available."""
    hw = get_hardware_adapter()
    measurements = hw.get_measurements()

    if len(measurements) < 3:
        return {
            "exp_id": exp_id,
            "plan": None,
            "status": "insufficient_data",
            "message": f"Need more measurements ({len(measurements)}/3 minimum) before generating a plan",
        }

    try:
        from stage1_optimization.canonical_input.phase1_canonical_input import extract_canonical_phase1_input

        analysis_data = {
            "sample_id": hw._sample_id or exp_id or "unknown",
            "measurements": measurements,
            "arrhenius_analysis": {},
        }
        canonical = extract_canonical_phase1_input(analysis_data)

        return {
            "exp_id": exp_id,
            "plan": {
                "type": "next_experiment",
                "sample_id": hw._sample_id,
                "measurements_so_far": len(measurements),
                "canonical_input_ready": True,
                "suggested_action": "Generate mechanism report and plan next temperature range",
            },
            "status": "plan_available",
            "message": "Stage 1 analysis available; review and approve to generate report",
        }
    except ImportError:
        return {
            "exp_id": exp_id,
            "plan": {
                "type": "basic_plan",
                "sample_id": hw._sample_id,
                "measurements_so_far": len(measurements),
                "suggested_action": "Continue measurement or review existing data",
            },
            "status": "basic_plan",
            "message": "Stage 1 optimization module not available; basic plan generated",
        }


@router.post("/next-plan/decision")
@router.post("/next-plan/{exp_id}/decision")
def decide_next_plan(exp_id: Optional[str] = None, payload: Optional[dict] = None):
    if payload is None:
        payload = {}
    decision = payload.get("decision", "approved")
    return {
        "ok": True,
        "exp_id": exp_id,
        "decision": decision,
        "message": f"Plan {decision}",
    }


@router.post("/next-plan/apply")
@router.post("/next-plan/{exp_id}/apply")
def apply_approved_next_plan(exp_id: Optional[str] = None):
    """Apply the approved plan — triggers Stage 1 report generation."""
    hw = get_hardware_adapter()
    measurements = hw.get_measurements()

    if len(measurements) < 3:
        return {"ok": False, "message": "Insufficient measurements for report generation"}

    try:
        from stage1_optimization.report_service import generate_mechanism_report_from_canonical
        from stage1_optimization.canonical_input.phase1_canonical_input import extract_canonical_phase1_input

        sample_id = hw._sample_id or exp_id or "unknown"

        temperature_results = []
        temps, rbs, conds = [], [], []
        for m in measurements:
            t_k = m.get("temperature_K", m.get("temperature_C", 0) + 273.15)
            rb = m.get("rb_ohm", 0)
            sigma = m.get("conductivity_S_cm", 0)
            temps.append(t_k)
            rbs.append(rb)
            conds.append(sigma)
            temperature_results.append({
                "temperature_K": t_k,
                "rb_ohm": rb,
                "conductivity_S_cm": sigma,
                "rb_method": m.get("fit_method", "unknown"),
                "r_squared": m.get("r_squared", None),
                "n_points": m.get("n_points"),
            })

        analysis_data = {
            "sample_id": sample_id,
            "material_type": getattr(hw, "_material_type", None),
            "R": getattr(hw, "_R", None),
            "N": getattr(hw, "_N", None),
            "L_cm": getattr(hw, "_L_cm", None),
            "S_cm2": getattr(hw, "_S_cm2", None),
            "temperatures": temps,
            "rb_values": rbs,
            "conductivity_values": conds,
            "temperature_results": temperature_results,
            "arrhenius": {},
        }
        canonical = extract_canonical_phase1_input(analysis_data)

        output_dir = Path(__file__).resolve().parent.parent.parent.parent / "experiments" / "output" / "stage1_reports"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"report_{sample_id}_{len(measurements)}pts.md"

        result = generate_mechanism_report_from_canonical(
            canonical_input=canonical,
            output_md_path=output_path,
        )

        report_ok = result.get("ok", False)
        resp = {
            "ok": report_ok,
            "exp_id": exp_id,
            "message": "Report generation completed" if report_ok else "Report generation failed",
            "measurements_used": len(measurements),
            "report_path": str(output_path) if report_ok else None,
        }
        if result.get("next_plan"):
            resp["next_plan"] = result["next_plan"]
            resp["next_plan_path"] = result.get("next_plan_path")
        return resp
    except ImportError:
        return {
            "ok": False,
            "message": "Stage 1 optimization module not available",
        }
    except Exception as e:
        return {
            "ok": False,
            "message": f"Report generation error: {str(e)}",
        }


@router.get("/next-plan/saved/{sample_id}")
def get_saved_next_plan(sample_id: str):
    """Retrieve a previously generated next_experiment_plan.json for a sample."""
    sample_id = _validate_id(sample_id, "sample_id")
    reports_dir = Path(__file__).resolve().parent.parent.parent.parent / "experiments" / "output" / "stage1_reports"
    plan_files = sorted(reports_dir.glob(f"{sample_id}_next_experiment_plan.json"), reverse=True)
    if not plan_files:
        return {"ok": False, "message": f"No saved plan for {sample_id}"}
    plan = json.loads(plan_files[0].read_text(encoding="utf-8"))
    return {"ok": True, "sample_id": sample_id, "next_plan": plan, "path": str(plan_files[0])}


@router.post("/archive")
def archive_experiment():
    """Archive the current experiment data."""
    hw = get_hardware_adapter()
    if hw._run_id:
        hw._finalize_run("archived")
        return {"ok": True, "run_id": hw._run_id, "message": "Experiment archived"}
    return {"ok": True, "message": "No active run to archive"}


@router.post("/run_arrhenius_from_eis")
def run_arrhenius_from_eis(payload: dict = None):
    """Arrhenius from stored measurements or explicit file rows (unified pipeline screening)."""
    if payload is None:
        payload = {}
    eis_files = payload.get("eis_files", [])
    if not eis_files:
        hw = get_hardware_adapter()
        measurements = hw.get_measurements()
        if not measurements:
            return {"success": False, "error": "No EIS data available"}
        records = measurements
    else:
        records = []
        for f in eis_files:
            records.append(
                {
                    "temperature_K": f.get("temperature_K"),
                    "conductivity_S_cm": f.get("conductivity_S_cm") or f.get("conductivity_S_per_cm"),
                    "rb_ohm": f.get("rb_ohm"),
                }
            )

    try:
        from stage0_measurement.modules.analysis.eis_pipeline import (
            analyze_arrhenius_series,
        )
    except ImportError:
        return {"success": False, "error": "Arrhenius analysis module not available"}

    result = analyze_arrhenius_series(
        records,
        min_points=5,
        temperature_key="temperature_K",
        conductivity_key="conductivity_S_cm",
        rb_key="rb_ohm",
    )
    if not result or not result.get("success", False):
        return {
            "success": False,
            "error": result.get("error")
            if result
            else "Insufficient points after unified Arrhenius filter (need T_K, sigma, rb_ohm per row).",
        }
    return {"success": True, **result}


@router.post("/run_arrhenius_advanced")
def run_arrhenius_advanced(payload: dict = None):
    """Advanced Arrhenius — delegates to calculate_arrhenius with extended params."""
    if payload is None:
        payload = {}
    req = ArrheniusCalcRequest(
        conductivity_data=payload.get("conductivity_data", []),
        segmentation=payload.get("segmentation"),
    )
    return calculate_arrhenius(req)
