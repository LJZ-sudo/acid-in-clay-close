#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Process attapulgite (AO) EIS folders into Stage0 + Stage1-ready outputs."""
from __future__ import annotations

import argparse
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from process_new_materials_stage0 import (
    PROJECT_ROOT,
    Geometry,
    _normalize_folder_inputs,
    _parse_geometry_from_recipe_txt,
    _rebuild_stage0_reports_with_avg_temperature_points,
    _run_stage0_offline,
    _safe_float,
)


AO_INPUT_ROOT = PROJECT_ROOT / "data" / "ao"
AO_OUTPUT_ROOT = PROJECT_ROOT / "output" / "ao_stage0_results"
AO_NORMALIZED_ROOT = PROJECT_ROOT / "output" / "ao_stage0_input"
SAMPLE_BUS_ROOT = PROJECT_ROOT / "output" / "stage0_results"


def _read_recipe_text(folder: Path) -> str:
    recipe_files = sorted([p for p in folder.glob("*.txt") if "制备" in p.name])
    if not recipe_files:
        return ""
    return recipe_files[0].read_text(encoding="utf-8", errors="ignore")


def _parse_rn(folder: Path) -> Tuple[Optional[float], Optional[float]]:
    text = _read_recipe_text(folder)
    r_val = n_val = None
    m_r = re.search(r"\bR\s*=\s*([0-9]+(?:\.[0-9]+)?)", text, re.IGNORECASE)
    m_n = re.search(r"\bN\s*=\s*([0-9]+(?:\.[0-9]+)?)", text, re.IGNORECASE)
    if m_r:
        r_val = _safe_float(m_r.group(1))
    if m_n:
        n_val = _safe_float(m_n.group(1))

    if r_val is not None and n_val is not None:
        return r_val, n_val

    for p in folder.glob("*.txt"):
        m = re.search(
            r"R\s*([0-9]+(?:\.[0-9]+)?)\s*-\s*N\s*([0-9]+(?:\.[0-9]+)?)",
            p.name,
            re.IGNORECASE,
        )
        if m:
            return _safe_float(m.group(1)), _safe_float(m.group(2))
    return r_val, n_val


def _parse_geometry(folder: Path) -> Geometry:
    """Use recipe geometry strictly from 材料制备.txt; refuse to fabricate defaults.

    历史 bug：原版当解析失败时把厚度静默替换为 0.022 cm（220 μm），
    实际样品厚度~830–1030 μm，导致 σ_RT 被虚低 ~4×。
    新行为：如果 recipe text 解析不到 thickness/area，直接抛错让用户补全
    材料制备.txt，绝不静默兜底。
    """
    if not _read_recipe_text(folder).strip():
        raise ValueError(
            f"{folder}/材料制备.txt 缺失或为空 —— Stage0 必须有真实厚度/面积才能算 σ_RT。"
        )
    geometry = _parse_geometry_from_recipe_txt(folder)
    if geometry.thickness_cm == Geometry().thickness_cm:
        raise ValueError(
            f"{folder}/材料制备.txt 未解析到 '厚度=... cm'。"
            "请在文件中显式写明 '厚度=0.0XX cm' 后重跑 Stage0。"
        )
    if geometry.area_cm2 == Geometry().area_cm2:
        # 默认 1.96 cm² 是当前所有 AO coin cell 的固定值，与"未解析"无法区分；
        # 这里允许保留默认，但记入 metadata 以便审计。
        pass
    return geometry


def _geometry_source(geometry: Geometry) -> Dict[str, str]:
    """Record where the geometry values came from for downstream audit gates."""
    defaults = Geometry()
    return {
        "thickness_cm_source": "recipe_text",
        "area_cm2_source": "default_coin_cell"
        if geometry.area_cm2 == defaults.area_cm2
        else "recipe_text",
    }


def _write_experiment_metadata(
    out_dir: Path,
    sample_id: str,
    folder: Path,
    r_val: Optional[float],
    n_val: Optional[float],
    geometry: Geometry,
    geometry_source: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    geometry_source = geometry_source or _geometry_source(geometry)
    metadata = {
        "sample_id": sample_id,
        "material_system": "Attapulgite AiCE",
        "source_folder": str(folder),
        "source_mode": "real",
        "source_system": "attapulgite_aice",
        "campaign_slug": "attapulgite_aice_campaign",
        "geometry_source": geometry_source,
        "parameters": {
            "R": r_val,
            "N": n_val,
        },
        "sample_meta": {
            "clay_type": "attapulgite",
            "acid_type": "H3PO4",
            "thickness_cm": geometry.thickness_cm,
            "area_cm2": geometry.area_cm2,
            "recipe_note": _read_recipe_text(folder),
        },
    }
    (out_dir / "experiment_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return metadata


def _ao_bundle_limitations(n_points: int, n_numeric_kk: int) -> List[str]:
    """Build the AO bundle limitations honestly from what the data actually has.

    Tier2 (2026-06-01): the KK limitation is no longer written unconditionally;
    it is emitted only when numerical residuals are genuinely absent (legacy
    aggregated_results.json) or partial.
    """
    lims = [
        "AO input is a flat temperature series, not the legacy per-scan S8 folder layout.",
        "EIS morphology features are not available in this AO wrapper bundle yet.",
        "rb_confidence is the arc-fit R^2 (rb_confidence_basis='arc_fit_r2'), not a calibrated probability.",
    ]
    if n_points == 0:
        return lims
    if n_numeric_kk == 0:
        lims.insert(1,
            "kk_residual is None for all points: source aggregated_results.json predates Tier2 "
            "numerical KK residual propagation. Re-run the offline pipeline to populate mu_median.")
    elif n_numeric_kk < n_points:
        lims.insert(1,
            f"kk_residual present for {n_numeric_kk}/{n_points} points; the remainder are legacy "
            "records without a numerical residual.")
    return lims


def _write_stage0_result_bundle(
    out_dir: Path,
    sample_id: str,
    metadata: Dict[str, Any],
    rebuild_ok: bool = True,
) -> Path:
    """Create the standard Stage0 bundle consumed by ClosureAgent."""
    aggregated_path = out_dir / "aggregated_results.json"
    arrhenius_path = out_dir / "arrhenius_analysis.json"
    aggregated = json.loads(aggregated_path.read_text(encoding="utf-8"))
    arrhenius = json.loads(arrhenius_path.read_text(encoding="utf-8"))

    eis_points: List[Dict[str, Any]] = []
    n_numeric_kk = 0
    for meas in aggregated.get("measurements") or []:
        if meas.get("temperature_K") is None:
            continue
        status = str(meas.get("status") or ("OK" if meas.get("success", True) else "FAIL"))

        # Tier2 (2026-06-01, issue 10): propagate the numerical KK residual that
        # the upgraded offline pipeline now writes into each measurement
        # (kk_mu_median + aux stats). Fall back to None (honest) for legacy
        # aggregated_results.json that only carry the kk_warning bool.
        kk_mu_median = meas.get("kk_mu_median")
        kk_residual = _safe_float(kk_mu_median) if kk_mu_median is not None else None
        if kk_residual is not None:
            n_numeric_kk += 1

        flags: List[str] = [] if status == "OK" else [f"status:{status}"]
        if kk_residual is None and meas.get("kk_warning"):
            flags.append("kk_warning_set_by_legacy_pipeline")
        if kk_residual is None:
            flags.append("kk_residual_unavailable_legacy_record")
        # rb_confidence is the arc-fit R^2 (fit_quality); always label its basis.
        rb_conf = meas.get("fit_quality")
        rb_basis = "arc_fit_r2" if rb_conf is not None else None
        if rb_basis == "arc_fit_r2":
            flags.append("rb_confidence_is_arc_fit_r2_proxy")

        eis_points.append({
            "scan_dir": "ao_flat_temperature_series",
            "T_K": meas.get("temperature_K"),
            "T_C": meas.get("temperature_C"),
            "status": status,
            "rb_ohm": meas.get("rb_ohm"),
            "rb_method": meas.get("rb_method"),
            "rb_confidence": rb_conf,
            "rb_confidence_basis": rb_basis,
            "sigma_S_cm": meas.get("conductivity_S_per_cm"),
            "kk_warning": meas.get("kk_warning"),
            "kk_residual": kk_residual,
            "kk_residual_metric": "mu_median_linKK" if kk_residual is not None else None,
            "kk_mu_rmse": _safe_float(meas.get("kk_mu_rmse")) if meas.get("kk_mu_rmse") is not None else None,
            "kk_mu_max": _safe_float(meas.get("kk_mu_max")) if meas.get("kk_mu_max") is not None else None,
            "kk_score": _safe_float(meas.get("kk_score")) if meas.get("kk_score") is not None else None,
            "kk_passed": (bool(meas.get("kk_passed")) if meas.get("kk_passed") is not None else None),
            "kk_threshold": _safe_float(meas.get("kk_threshold")) if meas.get("kk_threshold") is not None else None,
            "arc_visible": None,
            "semicircle_visible": None,
            "characteristic_frequency_Hz": None,
            "peak_neg_zimag_ohm": None,
            "quality_flags": flags,
        })

    ea_segments = [
        seg.get("Ea_eV")
        for seg in (arrhenius.get("segments") or [])
        if seg.get("Ea_eV") is not None
    ]
    geometry = metadata.get("sample_meta") or {}
    params = metadata.get("parameters") or {}
    valid_eis_points = [
        p for p in eis_points
        if str(p.get("status") or "").upper() == "OK"
        and (p.get("sigma_S_cm") is not None)
        and p.get("sigma_S_cm") > 0
    ]
    stage0_ok = bool(aggregated.get("success", True)) and bool(valid_eis_points)
    arrhenius_ok = bool(rebuild_ok) and bool(arrhenius.get("success"))
    recipe_ok = params.get("R") is not None and params.get("N") is not None
    area_cm2 = _safe_float(geometry.get("area_cm2"))
    thickness_cm = _safe_float(geometry.get("thickness_cm"))
    geometry_ok = (
        area_cm2 is not None and area_cm2 > 0
        and thickness_cm is not None and thickness_cm > 0
    )
    invalid_reasons: List[str] = []
    if not stage0_ok:
        invalid_reasons.append("stage0_measurements_invalid_or_empty")
    if not arrhenius_ok:
        invalid_reasons.append("arrhenius_invalid_or_rebuild_failed")
    if not recipe_ok:
        invalid_reasons.append("recipe_R_or_N_missing")
    if not geometry_ok:
        invalid_reasons.append("geometry_missing")
    objective_ready = stage0_ok and arrhenius_ok and recipe_ok and geometry_ok
    bundle = {
        "sample_id": sample_id,
        "material_system": metadata.get("material_system") or "Attapulgite AiCE",
        "source_system": metadata.get("source_system") or "attapulgite_aice",
        "source_mode": metadata.get("source_mode") or "real",
        "recipe": {
            "R": params.get("R"),
            "N": params.get("N"),
            "acid_type": geometry.get("acid_type") or "H3PO4",
            "clay_type": geometry.get("clay_type") or "attapulgite",
            "excel_id": None,
        },
        "geometry": {
            "area_cm2": geometry.get("area_cm2"),
            "thickness_cm": geometry.get("thickness_cm"),
        },
        "geometry_source": metadata.get("geometry_source") or {},
        "data_validity": {
            "stage0_ok": stage0_ok,
            "arrhenius_ok": arrhenius_ok,
            "recipe_ok": recipe_ok,
            "geometry_ok": geometry_ok,
            "objective_ready": objective_ready,
            "invalid_reasons": invalid_reasons,
        },
        "temperature_program": [{
            "scan_dir": "ao_flat_temperature_series",
            "T_start_K": None,
            "T_end_K": None,
            "rate_K_per_min": None,
            "is_heating": None,
            "T_actual_mean_K": [],
            "T_actual_std_K": [],
            "T_actual_K": [p["T_K"] for p in eis_points if p.get("T_K") is not None],
        }],
        "eis_points": eis_points,
        "arrhenius": {
            "success": bool(arrhenius.get("success")),
            "best_model_type": arrhenius.get("best_model_type"),
            "n_segments": int(arrhenius.get("n_segments") or len(ea_segments)),
            "transition_temps_K": arrhenius.get("transition_temps_K") or [],
            "ea_segments_eV": ea_segments,
            "ea_single_eV": ea_segments[0] if len(ea_segments) == 1 else None,
            "ea_high_eV": ea_segments[0] if len(ea_segments) >= 2 else None,
            "ea_low_eV": ea_segments[-1] if len(ea_segments) >= 2 else None,
            "t_break_K": (arrhenius.get("transition_temps_K") or [None])[0],
            "confidence": arrhenius.get("confidence"),
            "fit_quality_flags": [],
            "segments": arrhenius.get("segments") or [],
        },
        "file_hashes": {},
        "bundle_meta": {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source_scan_dirs": ["ao_flat_temperature_series"],
            "legacy_pipeline_version": "ao_stage0_processing",
            "stage0_bundle_schema_version": "0.2.0",
        },
        "limitations": _ao_bundle_limitations(len(eis_points), n_numeric_kk),
    }
    out_path = out_dir / "stage0_result_bundle.json"
    out_path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path


def _sync_to_sample_bus(out_dir: Path, sample_id: str) -> Path:
    sample_dir = SAMPLE_BUS_ROOT / sample_id
    sample_dir.mkdir(parents=True, exist_ok=True)
    for name in [
        "aggregated_results.json",
        "arrhenius_analysis.json",
        "arrhenius_plot.png",
        "conductivity_trend.png",
        "experiment_metadata.json",
        "stage0_result_bundle.json",
        "closure_report.json",
        "stage0_run.log",
    ]:
        src = out_dir / name
        if src.exists():
            shutil.copy2(src, sample_dir / name)
    return sample_dir


def process_ao_folder(folder: Path, sample_id: Optional[str] = None) -> Dict[str, Any]:
    r_val, n_val = _parse_rn(folder)
    if sample_id is None:
        r_token = "NA" if r_val is None else f"{r_val:.2f}"
        n_token = "NA" if n_val is None else f"{n_val:.2f}"
        sample_id = f"ATA-{folder.name.replace('.', '-')}-R{r_token}-N{n_token}"

    norm_dir = AO_NORMALIZED_ROOT / folder.name
    out_dir = AO_OUTPUT_ROOT / folder.name
    geometry = _parse_geometry(folder)
    geometry_source = _geometry_source(geometry)
    mapping, warnings = _normalize_folder_inputs(folder, norm_dir)
    if not mapping:
        return {
            "folder": folder.name,
            "sample_id": sample_id,
            "status": "failed_no_valid_measurements",
            "warnings": warnings,
        }

    ok, stage0_log = _run_stage0_offline(norm_dir, out_dir, geometry, material_name=sample_id)
    if not ok:
        return {
            "folder": folder.name,
            "sample_id": sample_id,
            "status": "failed_stage0_run",
            "warnings": warnings,
            "n_normalized_files": len(mapping),
            "R": r_val,
            "N": n_val,
            "thickness_cm": geometry.thickness_cm,
            "area_cm2": geometry.area_cm2,
            "output_dir": str(out_dir),
            "stage0_log": str(stage0_log) if stage0_log else None,
        }

    required_outputs = [out_dir / "aggregated_results.json", out_dir / "arrhenius_analysis.json"]
    missing_outputs = [p.name for p in required_outputs if not p.exists()]
    if missing_outputs:
        return {
            "folder": folder.name,
            "sample_id": sample_id,
            "status": "failed_missing_stage0_outputs",
            "warnings": warnings,
            "missing_outputs": missing_outputs,
            "n_normalized_files": len(mapping),
            "R": r_val,
            "N": n_val,
            "thickness_cm": geometry.thickness_cm,
            "area_cm2": geometry.area_cm2,
            "output_dir": str(out_dir),
        }

    rebuild_ok = _rebuild_stage0_reports_with_avg_temperature_points(
        out_dir, sample_id, excluded_temps=[]
    )
    if not rebuild_ok:
        warnings = list(warnings) + ["arrhenius_report_rebuild_failed"]
    metadata = _write_experiment_metadata(
        out_dir, sample_id, folder, r_val, n_val, geometry, geometry_source
    )
    bundle_path = _write_stage0_result_bundle(out_dir, sample_id, metadata, rebuild_ok=rebuild_ok)
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    sample_bus_dir = _sync_to_sample_bus(out_dir, sample_id)

    return {
        "folder": folder.name,
        "sample_id": sample_id,
        "status": "success" if ok else "failed_stage0_run",
        "warnings": warnings,
        "n_normalized_files": len(mapping),
        "R": r_val,
        "N": n_val,
        "thickness_cm": geometry.thickness_cm,
        "area_cm2": geometry.area_cm2,
        "arrhenius_rebuild_ok": bool(rebuild_ok),
        "data_validity": bundle.get("data_validity"),
        "output_dir": str(out_dir),
        "sample_bus_dir": str(sample_bus_dir),
        "metadata": metadata,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Process data/ao folders into Stage0 outputs")
    parser.add_argument("--folder", default="2026.5.11", help="Folder name under data/ao")
    parser.add_argument("--sample_id", default="", help="Optional explicit sample id")
    args = parser.parse_args()

    folder = AO_INPUT_ROOT / args.folder
    if not folder.exists():
        raise SystemExit(f"AO folder not found: {folder}")

    AO_OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    AO_NORMALIZED_ROOT.mkdir(parents=True, exist_ok=True)
    SAMPLE_BUS_ROOT.mkdir(parents=True, exist_ok=True)

    result = process_ao_folder(folder, sample_id=args.sample_id.strip() or None)
    (AO_OUTPUT_ROOT / "ao_stage0_summary.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
