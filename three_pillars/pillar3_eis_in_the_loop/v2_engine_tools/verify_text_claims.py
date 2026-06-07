"""Verify that every performance NUMBER in a text traces to a claim map.

HARDENED Phase A safety gate for manuscript-bound text. It extracts numbers that
are *performance figures* (a number immediately adjacent to a performance unit
such as ``S cm-1``, ``eV``, ``ohm``/``Ω``, ``cm2``, ``K``, or preceded by a cue
like ``sigma`` / ``Ea_high`` / ``conductivity`` / ``score_v3``) and requires each
one to match an allowed numeric anchor declared in a claim map (with a sample ID
and a data path). Any performance number with no claim-map trace -> FAIL.

It also runs the forbidden-wording scan, so overclaim phrases fail the text too.

This tool reads text and a claim map; it never writes a manuscript, never invents
a number, and emits no claim of its own.

Claim map JSON shape (--claim-map):
    {
      "allowed_numbers": [
        {"value": "0.0366", "unit": "eV", "sample_id": "...", "path": "...", "claim_id": "..."},
        {"value": "1.5e-2", "unit": "S cm-1", "sample_id": "...", "path": "...", "claim_id": "..."},
        {"value": "273", "unit": "K", "sample_id": "...", "path": "...", "claim_id": "..."}
      ]
    }
Every allowed_number must carry a non-empty sample_id AND path, else it is
ignored (an anchor with no provenance is not a valid trace).

Usage:
    python verify_text_claims.py <text_file> --claim-map MAP.json [--tolerance 1e-6] [--write NAME]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from v2tools_common import emit, load_json, scan_forbidden

# A performance number is a numeric token adjacent to a unit, or preceded by a cue.
_NUM = r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?"
_UNIT = r"(?:S\s*cm\^?-?1|S\s*/\s*cm|eV|ohm|Ω|cm\^?2|K)\b"
_CUE = r"(?:sigma|σ|Ea_high|Ea_low|ea_low_excess|conductivity|activation\s+energy|score_v3|mu_median|Rb)"

_PAT_NUM_UNIT = re.compile(rf"({_NUM})\s*{_UNIT}", re.IGNORECASE)
_PAT_CUE_NUM = re.compile(rf"{_CUE}[^\d\n]{{0,16}}?({_NUM})", re.IGNORECASE)


def extract_performance_numbers(text: str) -> list[dict]:
    found: list[dict] = []
    seen_spans: set[tuple[int, int]] = set()
    for pat in (_PAT_NUM_UNIT, _PAT_CUE_NUM):
        for m in pat.finditer(text):
            span = m.span(1)
            if span in seen_spans:
                continue
            seen_spans.add(span)
            raw = m.group(1)
            try:
                val = float(raw)
            except ValueError:
                continue
            start = max(0, m.start() - 30)
            end = min(len(text), m.end() + 10)
            found.append({"raw": raw, "value": val, "context": text[start:end].strip()})
    return found


def _allowed_floats(claim_map: dict) -> list[float]:
    out: list[float] = []
    for entry in (claim_map.get("allowed_numbers") or []):
        if not isinstance(entry, dict):
            continue
        # an anchor needs provenance: sample_id AND path
        if not (str(entry.get("sample_id") or "").strip() and str(entry.get("path") or "").strip()):
            continue
        try:
            out.append(float(entry.get("value")))
        except (TypeError, ValueError):
            continue
    return out


def _matches(value: float, allowed: list[float], tol: float) -> bool:
    for a in allowed:
        denom = max(abs(a), abs(value), 1e-12)
        if abs(a - value) <= tol * denom or abs(a - value) <= tol:
            return True
    return False


def verify_text(text: str, claim_map: dict, tolerance: float = 1e-6) -> dict:
    allowed = _allowed_floats(claim_map)
    numbers = extract_performance_numbers(text)
    untraceable = [n for n in numbers if not _matches(n["value"], allowed, tolerance)]
    forbidden_hits = sorted(set(scan_forbidden(text)))

    valid = (not untraceable) and (not forbidden_hits)
    return {
        "artifact_type": "text_claim_verification",
        "tool": "verify_text_claims.py",
        "valid": valid,
        "performance_numbers_found": len(numbers),
        "allowed_anchor_count": len(allowed),
        "untraceable_numbers": untraceable,
        "forbidden_wording_hits": forbidden_hits,
        "result_like_artifact": False,
        "note": ("Every performance number must trace to a claim-map anchor that has "
                 "a sample_id and a data path. Untraceable numbers or forbidden wording fail."),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("text_file")
    parser.add_argument("--claim-map", required=True)
    parser.add_argument("--tolerance", type=float, default=1e-6)
    parser.add_argument("--write", metavar="NAME", default=None)
    args = parser.parse_args(argv)

    text = Path(args.text_file).read_text(encoding="utf-8")
    claim_map = load_json(Path(args.claim_map))
    result = verify_text(text, claim_map, args.tolerance)
    emit(result, args.write)
    return 0 if result["valid"] else 2


if __name__ == "__main__":
    sys.exit(main())
