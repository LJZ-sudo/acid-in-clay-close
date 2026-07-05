"""Validate a v2 score.json keeps the four evidence layers strictly separate.

Required structure:
- ``raw_result_ref``     : reference to the raw/Stage0 result (string)
- ``manual_rb_qc_ref``   : reference to the QC-passed Rb entry (string)
- ``score_v3``           : number (the locked scalar score)
- ``pareto_status``      : string tag (e.g. "on_front" / "dominated")

Hard rejects:
- Any ``claim``/``publication``/``conclusion`` field (publication wording must
  not live in a score record).
- Any free-text field containing forbidden overclaim wording
  (global optimum, world record, v2 Pareto achieved, BO+LLM discovered LRS,
  EIS proves mechanism, ...).

Read-only. Asserts no scientific result.

Usage:
    python validate_score_layers.py <score.json> [--write NAME]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from v2tools_common import emit, load_json, scan_forbidden

REQUIRED_FIELDS = ("raw_result_ref", "manual_rb_qc_ref", "score_v3", "pareto_status")
FORBIDDEN_FIELDS = ("claim", "publication", "conclusion", "headline", "claims")


def _iter_strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _iter_strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _iter_strings(v)


def validate_score(score: dict) -> dict:
    errors: list[str] = []

    for field in REQUIRED_FIELDS:
        if field not in score:
            errors.append(f"missing required field: {field}")
    if "score_v3" in score and not isinstance(score["score_v3"], (int, float)):
        errors.append("score_v3 must be a number")
    if "raw_result_ref" in score and not str(score.get("raw_result_ref") or "").strip():
        errors.append("raw_result_ref must be non-empty")
    if "manual_rb_qc_ref" in score and not str(score.get("manual_rb_qc_ref") or "").strip():
        errors.append("manual_rb_qc_ref must be non-empty")

    present_forbidden_fields = [f for f in FORBIDDEN_FIELDS if f in score]
    for f in present_forbidden_fields:
        errors.append(f"forbidden field present (publication wording must not live in score): {f}")

    forbidden_hits: list[str] = []
    for text in _iter_strings(score):
        forbidden_hits.extend(scan_forbidden(text))
    forbidden_hits = sorted(set(forbidden_hits))
    if forbidden_hits:
        errors.append(f"forbidden wording hits: {forbidden_hits}")

    return {
        "artifact_type": "score_layer_validation",
        "tool": "validate_score_layers.py",
        "valid": not errors,
        "errors": errors,
        "forbidden_field_hits": present_forbidden_fields,
        "forbidden_wording_hits": forbidden_hits,
        "result_like_artifact": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("score")
    parser.add_argument("--write", metavar="NAME", default=None)
    args = parser.parse_args(argv)

    score = load_json(Path(args.score))
    result = validate_score(score)
    emit(result, args.write)
    return 0 if result["valid"] else 2


if __name__ == "__main__":
    sys.exit(main())
