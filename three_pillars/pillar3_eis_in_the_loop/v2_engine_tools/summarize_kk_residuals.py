"""Summarize numeric Kramers-Kronig residuals (mu_median) for an EIS bundle.

Read-only reporting helper. Reads a Stage0-style bundle JSON, walks its EIS
points, and reports per-point KK residual vs threshold. Flags any point that
requires a bounded caveat (residual above threshold, or no numeric KK on a
legacy record).

This tool emits QC bookkeeping only. It never emits a mechanism or performance
claim, and it never decides that EIS proves a mechanism.

Bundle shape (tolerant):
    {"eis_points": [ {"temperature_K":.., "kk_residual":.., "kk_residual_metric":..,
                      "kk_threshold":.., "kk_passed":..}, ... ]}
Also accepts points under "points" or top-level list.

Usage:
    python summarize_kk_residuals.py <bundle.json> [--threshold 0.05] [--write NAME]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from v2tools_common import emit, load_json

DEFAULT_THRESHOLD = 0.05


def _points(bundle) -> list:
    if isinstance(bundle, list):
        return bundle
    if isinstance(bundle, dict):
        for key in ("eis_points", "points", "EISPoints"):
            if isinstance(bundle.get(key), list):
                return bundle[key]
    return []


def summarize(bundle, default_threshold: float = DEFAULT_THRESHOLD) -> dict:
    rows = []
    numeric = 0
    legacy = 0
    above = 0
    kk_failed = 0
    for i, pt in enumerate(_points(bundle)):
        if not isinstance(pt, dict):
            continue
        residual = pt.get("kk_residual", pt.get("kk_mu_median"))
        threshold = pt.get("kk_threshold", default_threshold)
        metric = pt.get("kk_residual_metric")
        # Honor an explicit kk_passed flag if present (could be bool or "false").
        kk_passed_raw = pt.get("kk_passed", None)
        kk_passed = None
        if isinstance(kk_passed_raw, bool):
            kk_passed = kk_passed_raw
        elif isinstance(kk_passed_raw, str) and kk_passed_raw.strip().lower() in ("true", "false"):
            kk_passed = kk_passed_raw.strip().lower() == "true"

        is_numeric = isinstance(residual, (int, float))
        bounded_caveat = True
        verdict = "BOUNDED_CAVEAT_REQUIRED"
        if is_numeric:
            numeric += 1
            if residual <= threshold:
                bounded_caveat = False
                verdict = "WITHIN_THRESHOLD"
            else:
                above += 1
                verdict = "ABOVE_THRESHOLD_BOUNDED_CAVEAT"
        else:
            legacy += 1
            verdict = "NO_NUMERIC_KK_LEGACY_BOUNDED_CAVEAT"

        # HARDENING: an explicit kk_passed=false ALWAYS forces a bounded caveat,
        # overriding any "within threshold" verdict. KK failure is decisive.
        if kk_passed is False:
            kk_failed += 1
            bounded_caveat = True
            verdict = "KK_FAILED_BOUNDED_CAVEAT"

        rows.append({
            "index": i,
            "temperature_K": pt.get("temperature_K"),
            "kk_residual": residual if is_numeric else None,
            "kk_residual_metric": metric,
            "kk_passed": kk_passed,
            "threshold": threshold,
            "is_numeric": is_numeric,
            "bounded_caveat_required": bounded_caveat,
            "verdict": verdict,
        })

    return {
        "artifact_type": "kk_residual_summary",
        "tool": "summarize_kk_residuals.py",
        "default_threshold": default_threshold,
        "point_count": len(rows),
        "numeric_kk_points": numeric,
        "legacy_no_kk_points": legacy,
        "above_threshold_points": above,
        "kk_failed_points": kk_failed,
        "any_bounded_caveat_required": any(r["bounded_caveat_required"] for r in rows),
        "points": rows,
        "eis_is_mechanism_proof": False,
        "result_like_artifact": False,
        "note": "EIS is bounded QC / supporting evidence only; never mechanism proof. "
                "An explicit kk_passed=false always forces a bounded caveat.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle")
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    parser.add_argument("--write", metavar="NAME", default=None)
    args = parser.parse_args(argv)

    bundle = load_json(Path(args.bundle))
    result = summarize(bundle, args.threshold)
    emit(result, args.write)
    return 0


if __name__ == "__main__":
    sys.exit(main())
