"""S01 data-audit helper for legacy Stage2 CSV inputs.

The current Stage3 executable chain starts from the canonical Stage2 V2 seed
and normally begins at S03. This helper is kept for explicit legacy/source
audits so old CSV-style inputs fail clearly instead of silently producing a bad
seed.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from s8_stage3.io.writers import write_json
from s8_stage3.preprocess.quality_filter import filter_csv_rows


def run_s01(
    csv_rows: list[dict],
    data_profile: dict,
    output_dir: Path,
) -> dict:
    """Audit raw CSV rows and write a deterministic preprocess report."""
    output_dir = Path(output_dir)
    min_points = int((data_profile or {}).get("min_points_per_sample", 3) or 3)
    clean_rows, warnings = filter_csv_rows(csv_rows, min_points_per_sample=min_points)

    input_count = len(csv_rows or [])
    clean_count = len(clean_rows)
    skipped_count = input_count - clean_count
    status = "pass"
    if warnings:
        status = "warn"
    if input_count == 0 or clean_count == 0:
        status = "fail"

    audit: dict[str, Any] = {
        "step_id": "s01_data_auditor",
        "status": status,
        "input_row_count": input_count,
        "clean_row_count": clean_count,
        "skipped_row_count": skipped_count,
        "min_points_per_sample": min_points,
        "warning_count": len(warnings),
        "warnings": warnings,
        "data_profile": data_profile or {},
    }

    preprocess_dir = output_dir / "00_preprocess"
    write_json(preprocess_dir / "data_audit.json", audit)
    write_json(preprocess_dir / "clean_rows.json", {"rows": clean_rows})

    if status == "fail":
        raise RuntimeError("[S01] Data audit failed: no clean CSV rows remain.")
    return audit
