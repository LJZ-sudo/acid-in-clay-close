"""Quality filter for legacy CSV rows before Stage3 seed construction."""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def filter_csv_rows(
    rows: list[dict],
    min_points_per_sample: int = 3,
) -> tuple[list[dict], list[str]]:
    """Return ``(clean_rows, warning_messages)`` for legacy CSV rows."""
    warnings: list[str] = []
    clean: list[dict] = []

    sample_counts: dict[str, int] = {}
    for row in rows:
        sid = row.get("sample_id") or row.get("Sample_ID") or ""
        t_raw = row.get("T") or row.get("T_K") or row.get("temp") or ""
        if not sid:
            warnings.append(f"Row skipped: missing sample_id in {row}")
            continue
        try:
            float(t_raw)
        except (TypeError, ValueError):
            warnings.append(f"Row skipped: invalid T value '{t_raw}' for sample {sid}")
            continue
        clean.append(row)
        sample_counts[sid] = sample_counts.get(sid, 0) + 1

    for sid, cnt in sample_counts.items():
        if cnt < min_points_per_sample:
            warnings.append(
                f"Sample {sid}: only {cnt} data points (< {min_points_per_sample}), "
                "segment reconstruction may be unreliable."
            )

    if warnings:
        logger.warning("[QualityFilter] %d warnings:\n%s", len(warnings), "\n".join(warnings[:10]))

    return clean, warnings
