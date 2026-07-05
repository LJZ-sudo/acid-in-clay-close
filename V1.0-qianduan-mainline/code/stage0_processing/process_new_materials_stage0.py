#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Process new-material EIS txt data with existing Stage0 pipeline (rename-only strategy).

Design goals:
1) Do NOT modify code under stage0_measurement.
2) Normalize filename temperature pattern by copying source txt files to a temp folder
   with Stage0-compatible names: *_T{temp}C_seq{N}.txt
3) Reuse run_stage0_wrapper.py to run offline EIS + Arrhenius fitting.
4) Compare code-fitted Rb(T) with manually fitted Excel workbooks in data/新材料.
"""

from __future__ import annotations

import argparse
import io
import json
import math
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


# Ensure UTF-8 output on Windows terminals without breaking pytest capture.
if sys.platform == "win32" and "pytest" not in sys.modules:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_NEW_MATERIALS = PROJECT_ROOT.parent / "experiments" / "raw" / "新材料"
OUTPUT_ROOT = PROJECT_ROOT.parent / "experiments" / "output" / "new_materials_stage0_results"
NORMALIZED_INPUT_ROOT = PROJECT_ROOT.parent / "experiments" / "output" / "new_materials_stage0_input"
WRAPPER_SCRIPT = Path(__file__).resolve().parent / "run_stage0_wrapper.py"

# Per-folder excluded temperature points (low-T outliers etc.)
EXCLUDED_TEMPS_BY_FOLDER: Dict[str, List[float]] = {
    "2026.4.29CS": [-80.0, -77.0],
}

# Stage0 analyzer override for averaged-T pipeline.
ARRHENIUS_MIN_SEGMENT_POINTS = 3


@dataclass
class Geometry:
    thickness_cm: float = 0.10
    area_cm2: float = 1.96


def _safe_float(x) -> Optional[float]:
    try:
        f = float(x)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except Exception:
        return None


def _extract_temp_from_filename(name: str) -> Optional[float]:
    """
    Parse temperature from source filename.
    Supports patterns such as:
      3-ke--30℃-1.txt -> -30
      3-ke-30℃-1.txt  -> +30
      18℃-4.txt       -> +18
      ... --5.5℃ ...  -> -5.5

    Dataset naming rule:
      "--<num>℃" means negative;
      "-<num>℃" means positive (single '-' is separator).
    """
    # Rule 1: explicit negative marker with double hyphen.
    m_neg = re.search(r"--\s*(\d+(?:\.\d+)?)\s*℃", name)
    if m_neg:
        t = _safe_float(m_neg.group(1))
        if t is not None:
            return -abs(t)

    # Rule 2: single hyphen before temperature means positive in this dataset.
    m_pos_sep = re.search(r"(?<!-)-\s*(\d+(?:\.\d+)?)\s*℃", name)
    if m_pos_sep:
        t = _safe_float(m_pos_sep.group(1))
        if t is not None:
            return abs(t)

    # Rule 3: plain token without explicit sign.
    m_plain = re.search(r"(\d+(?:\.\d+)?)\s*℃", name)
    if m_plain:
        t = _safe_float(m_plain.group(1))
        if t is not None:
            return t

    # Fallback: only accept canonical "_TxxC" style tokens.
    # Avoid parsing arbitrary trailing numbers like "...-1.txt" as temperature.
    m_t = re.search(r"_T\s*([-+]?\d+(?:\.\d+)?)\s*C", name, re.IGNORECASE)
    if m_t:
        t = _safe_float(m_t.group(1))
        if t is not None:
            return t
    m_t_plain = re.search(r"_T\s*([-+]?\d+(?:\.\d+)?)(?=_|\.|$)", name, re.IGNORECASE)
    if m_t_plain:
        t = _safe_float(m_t_plain.group(1))
        if t is not None:
            return t
    return None


def _is_measurement_txt(path: Path) -> bool:
    """
    Distinguish EIS measurement txt from notes txt.
    Rule: first line contains Freq/Frequency and Z' style columns.
    """
    if path.suffix.lower() != ".txt":
        return False
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()[:30]
        if not lines:
            return False
        for line in lines:
            head = line.lower()
            if ("freq" in head or "frequency" in head) and ("z'" in head or "z(" in head or "z" in head):
                return True
        return False
    except Exception:
        return False


def _parse_geometry_from_recipe_txt(folder: Path) -> Geometry:
    """
    Read recipe note file (材料制备过程*.txt) and parse thickness/area.
    Defaults kept if parsing fails.
    """
    g = Geometry()
    recipe_files = sorted([p for p in folder.glob("*.txt") if "制备" in p.name])
    if not recipe_files:
        return g
    txt = recipe_files[0].read_text(encoding="utf-8", errors="ignore")

    # 兼容 '厚度=0.088cm'、'厚度：0.088cm'、'厚度=0.088 cm'、'厚度 0.088cm' 等多种写法。
    # 旧正则只接受中/英文冒号和空格，导致材料制备文本用 '=' 时 silently 落入默认值，
    # 再被下游 fallback 改成 0.022 cm，使得 σ_RT 被虚低 ~4 倍（trial 2–8 全部中招）。
    m_thk = re.search(r"厚度\s*[=＝：:]?\s*([0-9]+(?:\.[0-9]+)?)", txt)
    if m_thk:
        t = _safe_float(m_thk.group(1))
        if t:
            g.thickness_cm = t

    m_area = re.search(r"面积\s*[=＝：:]?\s*([0-9]+(?:\.[0-9]+)?)", txt)
    if m_area:
        a = _safe_float(m_area.group(1))
        if a:
            g.area_cm2 = a
    return g


def _normalize_folder_inputs(src_folder: Path, norm_folder: Path) -> Tuple[List[dict], List[str]]:
    """
    Copy+rename measurement txt files to Stage0-compatible filenames.
    Returns mapping records and warning list.
    """
    norm_folder.mkdir(parents=True, exist_ok=True)
    mapping: List[dict] = []
    warns: List[str] = []
    idx = 1

    txt_files = sorted([p for p in src_folder.glob("*.txt") if p.is_file()])
    for p in txt_files:
        if not _is_measurement_txt(p):
            continue
        temp_c = _extract_temp_from_filename(p.name)
        if temp_c is None:
            warns.append(f"{p.name}: cannot parse temperature")
            continue

        new_name = f"{src_folder.name}_T{temp_c:.1f}C_seq{idx:03d}.txt"
        dst = norm_folder / new_name
        shutil.copy2(p, dst)
        mapping.append(
            {
                "source_file": str(p),
                "normalized_file": str(dst),
                "temperature_C": temp_c,
                "seq": idx,
            }
        )
        idx += 1

    # Save mapping
    (norm_folder / "rename_mapping.json").write_text(
        json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return mapping, warns


def _run_stage0_offline(norm_folder: Path, out_folder: Path, geometry: Geometry, material_name: str) -> Tuple[bool, str]:
    out_folder.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        str(WRAPPER_SCRIPT),
        "--data_dir",
        str(norm_folder),
        "--output_dir",
        str(out_folder),
        "--material",
        material_name,
        "--chi_pattern",
        "*.txt",
        "--thickness",
        str(geometry.thickness_cm),
        "--area",
        str(geometry.area_cm2),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    log = (proc.stdout or "") + "\n" + (proc.stderr or "")
    (out_folder / "stage0_run.log").write_text(log, encoding="utf-8")
    return proc.returncode == 0, log


def _load_code_rb_by_temp_avg(aggregated_json: Path) -> Optional[pd.DataFrame]:
    if not aggregated_json.exists():
        return None
    data = json.loads(aggregated_json.read_text(encoding="utf-8"))
    rows = []
    for m in data.get("measurements", []):
        t = _safe_float(m.get("temperature_C"))
        rb = _safe_float(m.get("rb_ohm"))
        if t is None or rb is None:
            continue
        rows.append({"temperature_C": round(t, 3), "rb_code_ohm": rb})
    if not rows:
        return None
    df = pd.DataFrame(rows)
    return df.groupby("temperature_C", as_index=False)["rb_code_ohm"].mean()


def _summarize_code_temp_replicates(aggregated_json: Path) -> Dict[str, object]:
    """
    Summarize duplicate measurements per temperature in aggregated_results.json.
    """
    if not aggregated_json.exists():
        return {"n_total_points": 0, "n_unique_temps": 0, "n_duplicate_temps": 0, "duplicate_temps": []}

    data = json.loads(aggregated_json.read_text(encoding="utf-8"))
    rows = []
    for m in data.get("measurements", []):
        t = _safe_float(m.get("temperature_C"))
        rb = _safe_float(m.get("rb_ohm"))
        if t is None or rb is None:
            continue
        rows.append({"temperature_C": round(t, 3), "rb_code_ohm": rb})
    if not rows:
        return {"n_total_points": 0, "n_unique_temps": 0, "n_duplicate_temps": 0, "duplicate_temps": []}

    df = pd.DataFrame(rows)
    counts = df.groupby("temperature_C", as_index=False).size().rename(columns={"size": "n_repeats"})
    dup = counts[counts["n_repeats"] > 1].copy()
    dup_list = [
        {"temperature_C": float(r.temperature_C), "n_repeats": int(r.n_repeats)}
        for r in dup.itertuples(index=False)
    ]
    return {
        "n_total_points": int(len(df)),
        "n_unique_temps": int(counts.shape[0]),
        "n_duplicate_temps": int(dup.shape[0]),
        "duplicate_temps": dup_list,
    }


def _load_code_rb_by_temp_best(aggregated_json: Path) -> Optional[pd.DataFrame]:
    """
    Pick the 'best' record per temperature:
      1) prefer status == OK
      2) max fit_quality
      3) otherwise fallback to first valid row
    """
    if not aggregated_json.exists():
        return None
    data = json.loads(aggregated_json.read_text(encoding="utf-8"))
    rows = []
    for m in data.get("measurements", []):
        t = _safe_float(m.get("temperature_C"))
        rb = _safe_float(m.get("rb_ohm"))
        if t is None or rb is None:
            continue
        rows.append(
            {
                "temperature_C": round(t, 3),
                "rb_code_ohm": rb,
                "fit_quality": _safe_float(m.get("fit_quality")) or -1.0,
                "status_ok": 1 if str(m.get("status", "")).upper() == "OK" else 0,
            }
        )
    if not rows:
        return None
    df = pd.DataFrame(rows)
    df = df.sort_values(["temperature_C", "status_ok", "fit_quality"], ascending=[True, False, False])
    best = df.groupby("temperature_C", as_index=False).first()[["temperature_C", "rb_code_ohm"]]
    return best


def _find_manual_excel_for_folder(folder_name: str) -> Optional[Path]:
    # folder_name: 2026.4.25CS -> key "4.25"
    m = re.search(r"^\d{4}\.(\d+\.\d+)", folder_name)
    key = m.group(1) if m else None
    excels = sorted(DATA_NEW_MATERIALS.glob("*.xlsx"))
    if not excels:
        return None
    if key is None:
        return excels[0]
    for p in excels:
        if key in p.name:
            return p
    return None


def _extract_manual_rb_table(excel_path: Path) -> Optional[pd.DataFrame]:
    """
    Try robust extraction from manually fitted workbook.
    Heuristics:
      - rb column: header contains 'Rb' (case-insensitive)
      - temp column: numeric column mostly in [-150,120] with enough unique values
    """
    try:
        xls = pd.ExcelFile(excel_path)
    except Exception:
        return None

    all_rows = []
    for sh in xls.sheet_names:
        try:
            df = pd.read_excel(excel_path, sheet_name=sh)
        except Exception:
            continue
        if df.empty:
            continue

        rb_col = None
        for c in df.columns:
            if "rb" in str(c).lower():
                rb_col = c
                break
        if rb_col is None:
            continue

        # Find plausible temperature column.
        temp_col = None
        for c in df.columns:
            s = pd.to_numeric(df[c], errors="coerce")
            valid = s.dropna()
            if len(valid) < 5:
                continue
            if valid.between(-150, 120).mean() < 0.8:
                continue
            if valid.nunique() < 5:
                continue
            temp_col = c
            break
        if temp_col is None:
            continue

        rb = pd.to_numeric(df[rb_col], errors="coerce")
        temp = pd.to_numeric(df[temp_col], errors="coerce")
        sub = pd.DataFrame({"temperature_C": temp, "rb_manual_ohm": rb}).dropna()
        if sub.empty:
            continue
        all_rows.append(sub)

    if not all_rows:
        return None
    out = pd.concat(all_rows, ignore_index=True)
    out["temperature_C"] = out["temperature_C"].round(3)
    return out.groupby("temperature_C", as_index=False)["rb_manual_ohm"].mean()


def _compute_compare_metrics(df: pd.DataFrame) -> Dict[str, float]:
    err = (df["rb_code_ohm"] - df["rb_manual_ohm"]).astype(float)
    mae = float(err.abs().mean())
    rmse = float((err.pow(2).mean()) ** 0.5)
    mape = float((err.abs() / df["rb_manual_ohm"].replace(0, pd.NA)).dropna().mean() * 100.0)
    return {"mae_ohm": mae, "rmse_ohm": rmse, "mape_pct": mape, "n_overlap_temps": int(len(df))}


def _rebuild_stage0_reports_with_avg_temperature_points(
    out_dir: Path, material_name: str, excluded_temps: Optional[List[float]] = None
) -> bool:
    """
    Keep Stage0 native plotting/segmentation, but feed temperature-averaged points.
    """
    aggregated_json = out_dir / "aggregated_results.json"
    if not aggregated_json.exists():
        return False

    data = json.loads(aggregated_json.read_text(encoding="utf-8"))
    rows = []
    for m in data.get("measurements", []):
        t_c = _safe_float(m.get("temperature_C"))
        sigma = _safe_float(m.get("conductivity_S_per_cm"))
        rb = _safe_float(m.get("rb_ohm"))
        if t_c is None or sigma is None or rb is None:
            continue
        if sigma <= 0:
            continue
        if str(m.get("status", "")).upper() != "OK":
            continue
        if m.get("success") is not True:
            continue
        if excluded_temps and any(abs(round(t_c, 3) - float(x)) < 1e-6 for x in excluded_temps):
            continue
        rows.append({"temperature_C": round(t_c, 3), "conductivity_S_per_cm": sigma, "rb_ohm": rb})
    if len(rows) < 3:
        return False

    avg = (
        pd.DataFrame(rows)
        .groupby("temperature_C", as_index=False)[["conductivity_S_per_cm", "rb_ohm"]]
        .mean()
        .sort_values("temperature_C", ascending=False)
        .reset_index(drop=True)
    )
    if len(avg) < 3:
        return False

    temps_k = (avg["temperature_C"] + 273.15).astype(float).to_numpy()
    conds = avg["conductivity_S_per_cm"].astype(float).to_numpy()
    rb_values = avg["rb_ohm"].astype(float).to_numpy()

    # Rebuild Stage0 arrays in aggregated_results.json to match averaged-temp logic.
    data["temperatures_K"] = temps_k.tolist()
    data["conductivities"] = conds.tolist()
    data["rb_values"] = rb_values.tolist()
    if excluded_temps:
        kept_meas = []
        excluded_set = {round(float(x), 3) for x in excluded_temps}
        for m in data.get("measurements", []):
            t_c_m = _safe_float(m.get("temperature_C"))
            if t_c_m is not None and round(t_c_m, 3) in excluded_set:
                continue
            kept_meas.append(m)
        data["measurements"] = kept_meas
        data["excluded_temps_C"] = sorted(excluded_set)
    data["temperature_aggregation"] = {
        "method": "mean_rb_per_temperature",
        "n_points_before": int(len(rows)),
        "n_points_after": int(len(avg)),
    }
    aggregated_json.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    # Use Stage0 native arrhenius + plotter modules.
    stage0_dir = PROJECT_ROOT / "stage0_measurement"
    if str(stage0_dir) not in sys.path:
        sys.path.insert(0, str(stage0_dir))
    from modules.analysis.algorithms.arrhenius import analyze_arrhenius_series
    from modules.reporting import plotter

    measurement_records = [
        {
            "success": True,
            "temperature_K": float(tk),
            "conductivity_s_per_cm": float(sg),
        }
        for tk, sg in zip(temps_k, conds)
    ]
    arrhenius = analyze_arrhenius_series(
        measurement_records,
        min_points=5,
        min_segment_points=ARRHENIUS_MIN_SEGMENT_POINTS,
        aic_improvement_threshold=5.0,
    )
    (out_dir / "arrhenius_analysis.json").write_text(
        json.dumps(arrhenius, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    plotter.plot_conductivity_arrhenius(
        temperatures_K=np.array(temps_k),
        conductivities_S_cm=np.array(conds),
        output_path=str(out_dir / "arrhenius_plot.png"),
        segments=arrhenius.get("segments") if arrhenius else None,
        material_name=material_name,
    )
    # Keep trend plot consistent with averaged points too.
    plotter.plot_conductivity_trend(
        temperatures_C=np.array(avg["temperature_C"].astype(float).to_numpy()),
        conductivities_S_cm=np.array(conds),
        output_path=str(out_dir / "conductivity_trend.png"),
    )
    return True


def process_one_folder(folder: Path, normalized_root: Path, output_root: Path) -> Dict[str, object]:
    norm_dir = normalized_root / folder.name
    out_dir = output_root / folder.name
    geometry = _parse_geometry_from_recipe_txt(folder)
    mapping, warns = _normalize_folder_inputs(folder, norm_dir)

    if not mapping:
        return {
            "folder": folder.name,
            "status": "failed_no_valid_measurements",
            "warnings": warns,
            "thickness_cm": geometry.thickness_cm,
            "area_cm2": geometry.area_cm2,
        }

    ok, _ = _run_stage0_offline(norm_dir, out_dir, geometry, material_name=folder.name)
    result: Dict[str, object] = {
        "folder": folder.name,
        "status": "success" if ok else "failed_stage0_run",
        "warnings": warns,
        "thickness_cm": geometry.thickness_cm,
        "area_cm2": geometry.area_cm2,
        "n_normalized_files": len(mapping),
    }

    # Rebuild Stage0 reports with averaged single-point-per-temperature data.
    excluded = EXCLUDED_TEMPS_BY_FOLDER.get(folder.name, [])
    _rebuild_stage0_reports_with_avg_temperature_points(out_dir, folder.name, excluded_temps=excluded)
    if excluded:
        result["excluded_temps_C"] = list(excluded)
    result["arrhenius_min_segment_points"] = ARRHENIUS_MIN_SEGMENT_POINTS

    code_df_avg = _load_code_rb_by_temp_avg(out_dir / "aggregated_results.json")
    code_df_best = _load_code_rb_by_temp_best(out_dir / "aggregated_results.json")
    excel = _find_manual_excel_for_folder(folder.name)
    if excel is not None:
        result["manual_excel"] = str(excel)
    if code_df_avg is not None:
        (out_dir / "rb_code_by_temp_avg.csv").write_text(code_df_avg.to_csv(index=False), encoding="utf-8")
    if code_df_best is not None:
        (out_dir / "rb_code_by_temp_best.csv").write_text(code_df_best.to_csv(index=False), encoding="utf-8")
    if excel is not None:
        manual_df = _extract_manual_rb_table(excel)
    else:
        manual_df = None

    # For repeated tests at same temperature, use average Rb as default strategy.
    code_df_display = code_df_avg if code_df_avg is not None else code_df_best
    result["rb_display_strategy"] = "avg_per_temp"
    result["code_temp_replicate_summary"] = _summarize_code_temp_replicates(out_dir / "aggregated_results.json")

    if code_df_display is not None and manual_df is not None:
        cmp_df = code_df_display.merge(manual_df, on="temperature_C", how="inner")
        if not cmp_df.empty:
            cmp_df["delta_rb_ohm"] = cmp_df["rb_code_ohm"] - cmp_df["rb_manual_ohm"]
            cmp_df.to_csv(out_dir / "rb_compare_code_vs_manual.csv", index=False, encoding="utf-8-sig")
            result["rb_compare_metrics"] = _compute_compare_metrics(cmp_df)
        else:
            result["rb_compare_metrics"] = {"n_overlap_temps": 0}
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Process data/新材料 via Stage0 offline pipeline")
    parser.add_argument("--input_dir", default=str(DATA_NEW_MATERIALS))
    parser.add_argument("--output_dir", default=str(OUTPUT_ROOT))
    parser.add_argument("--normalized_dir", default=str(NORMALIZED_INPUT_ROOT))
    parser.add_argument("--folders", default="", help="Comma-separated folder names to process")
    args = parser.parse_args()

    output_root = Path(args.output_dir)
    normalized_root = Path(args.normalized_dir)
    input_dir = Path(args.input_dir)

    output_root.mkdir(parents=True, exist_ok=True)
    normalized_root.mkdir(parents=True, exist_ok=True)

    folders = [d for d in input_dir.iterdir() if d.is_dir()]
    if args.folders.strip():
        allow = {x.strip() for x in args.folders.split(",") if x.strip()}
        folders = [d for d in folders if d.name in allow]
    folders = sorted(folders, key=lambda p: p.name)

    summary = {
        "input_dir": str(input_dir),
        "output_dir": str(output_root),
        "normalized_dir": str(normalized_root),
        "n_folders": len(folders),
        "folders": [],
    }

    for folder in folders:
        print(f"\n=== Processing {folder.name} ===")
        res = process_one_folder(folder, normalized_root=normalized_root, output_root=output_root)
        print(json.dumps(res, ensure_ascii=False, indent=2))
        summary["folders"].append(res)

    (output_root / "new_materials_stage0_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n[OK] summary written: {output_root / 'new_materials_stage0_summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
