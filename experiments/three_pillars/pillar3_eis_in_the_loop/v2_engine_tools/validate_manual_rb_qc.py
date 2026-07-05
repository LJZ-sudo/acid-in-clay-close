"""Validate a manual Rb QC CSV against manual_rb_qc_schema.json.

Read-only. Checks required columns, types, units (via column names), value
ranges, enum membership, and a conditional rule that main-text-tier rows must
carry a human reviewer, a review timestamp, and a numeric KK residual.

This validates STRUCTURE only. It never certifies a measurement as real
evidence and never writes QC data.

Usage:
    python validate_manual_rb_qc.py <rb_qc.csv> [--schema PATH] [--write NAME]
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from v2tools_common import TOOLS_DIR, emit, is_iso8601, load_json

DEFAULT_SCHEMA = TOOLS_DIR / "manual_rb_qc_schema.json"


def _is_number(value: str) -> bool:
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


def _check_cell(col: str, raw: str, spec: dict) -> list[str]:
    errs: list[str] = []
    kind = spec.get("type")
    val = (raw or "").strip()

    if kind == "string":
        if spec.get("non_empty") and not val:
            errs.append(f"{col}: empty (non-empty required)")
        return errs
    if kind == "iso8601":
        if not val:
            errs.append(f"{col}: empty (ISO-8601 timestamp required)")
        elif not is_iso8601(val):
            errs.append(f"{col}: '{val}' is not a valid ISO-8601 datetime")
        return errs
    if kind == "enum":
        if val not in spec.get("values", []):
            errs.append(f"{col}: '{val}' not in {spec.get('values')}")
        return errs
    if kind == "number_or_empty":
        if val == "":
            return errs
        kind = "number"  # fall through to numeric checks
    if kind == "number":
        if not _is_number(val):
            errs.append(f"{col}: '{val}' is not a number")
            return errs
        num = float(val)
        if "min" in spec:
            if spec.get("exclusive_min") and num <= spec["min"]:
                errs.append(f"{col}: {num} must be > {spec['min']}")
            elif not spec.get("exclusive_min") and num < spec["min"]:
                errs.append(f"{col}: {num} must be >= {spec['min']}")
        if "max" in spec and num > spec["max"]:
            errs.append(f"{col}: {num} must be <= {spec['max']}")
    return errs


def validate_csv(csv_path: Path, schema: dict) -> dict:
    csv_path = Path(csv_path)
    required = schema.get("required_columns", [])
    specs = schema.get("column_specs", {})
    rules = schema.get("conditional_rules", [])

    row_errors: list[dict] = []
    with open(csv_path, "r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        header = reader.fieldnames or []
        missing_cols = [c for c in required if c not in header]
        rows = list(reader)

    if missing_cols:
        return {
            "artifact_type": "manual_rb_qc_validation",
            "tool": "validate_manual_rb_qc.py",
            "csv": csv_path.as_posix(),
            "valid": False,
            "missing_columns": missing_cols,
            "row_count": len(rows),
            "row_errors": [],
            "result_like_artifact": False,
        }

    for idx, row in enumerate(rows, start=1):
        errs: list[str] = []
        for col, spec in specs.items():
            errs.extend(_check_cell(col, row.get(col, ""), spec))
        for rule in rules:
            if (row.get(rule["if_column"], "").strip() == rule.get("equals")):
                for col in rule.get("require_non_empty", []):
                    if not (row.get(col, "") or "").strip():
                        errs.append(f"{col}: required non-empty when "
                                    f"{rule['if_column']}={rule['equals']}")
                forbid = rule.get("forbid_value")
                if forbid:
                    fcol = forbid.get("column")
                    if (row.get(fcol, "") or "").strip() == forbid.get("equals"):
                        errs.append(f"{fcol}={forbid.get('equals')!r} forbidden when "
                                    f"{rule['if_column']}={rule['equals']}")
        if errs:
            row_errors.append({"row": idx, "errors": errs})

    return {
        "artifact_type": "manual_rb_qc_validation",
        "tool": "validate_manual_rb_qc.py",
        "csv": csv_path.as_posix(),
        "valid": not row_errors,
        "missing_columns": [],
        "row_count": len(rows),
        "row_errors": row_errors,
        "result_like_artifact": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--write", metavar="NAME", default=None)
    args = parser.parse_args(argv)

    schema = load_json(Path(args.schema))
    result = validate_csv(Path(args.csv), schema)
    emit(result, args.write)
    return 0 if result["valid"] else 2


if __name__ == "__main__":
    sys.exit(main())
