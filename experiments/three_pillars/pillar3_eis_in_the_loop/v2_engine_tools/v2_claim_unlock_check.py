"""Default-HOLD, evidence-bound pre-claim verifier for v2 claim upgrades.

HARDENED (Phase A). There are two modes:

* ``--mode evidence`` (DEFAULT, the only mode valid for a real unlock):
  each of the 8 unlock conditions must be backed by a **real report file on
  disk** (an evidence binding), AND a round **hash manifest** must be supplied
  and be complete. A hand-written boolean JSON can never produce ALLOW in this
  mode. Missing the evidence map, any report file, or the hash manifest -> HOLD.

* ``--mode declared`` (TESTING / DRY-RUN ONLY): accepts a plain conditions JSON
  of booleans. This mode is explicitly labelled non-authoritative and can NEVER
  emit ``ALLOW``; the strongest verdict it returns is ``DECLARED_ONLY_NOT_AUTHORITATIVE``.
  It exists only so a dry-run can show the shape of a fully-true input.

In both modes the tool never upgrades a claim. It is biased to HOLD.

Unlock conditions (from v2_claims_still_blocked.md):
    1. signed_hash_bound_approval
    2. real_append_only_raw_eis
    3. stage0_result_gate_pass
    4. manual_rb_qc_acceptable
    5. score_gate_pass
    6. history_import_reviewed
    7. stage3_rerun_claim_gate_passed
    8. new_frozen_manifest_and_presubmission_pass

Evidence map JSON shape (--evidence-map):
    {
      "round_hash_manifest": "<path to a build_round_hash_manifest.py output>",
      "conditions": {
        "signed_hash_bound_approval": {
          "report": "<path to a real report file>",
          "verdict_field": "verdict",          # optional
          "expected_verdict": "MATCH"           # optional; if set, must equal
        },
        ...
      }
    }

Usage:
    python v2_claim_unlock_check.py --evidence-map MAP.json [--write NAME]
    python v2_claim_unlock_check.py --mode declared --conditions C.json   # dry-run only
    (no input, or any gap => HOLD)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from v2tools_common import emit, load_json

UNLOCK_CONDITIONS = (
    "signed_hash_bound_approval",
    "real_append_only_raw_eis",
    "stage0_result_gate_pass",
    "manual_rb_qc_acceptable",
    "score_gate_pass",
    "history_import_reviewed",
    "stage3_rerun_claim_gate_passed",
    "new_frozen_manifest_and_presubmission_pass",
)


def _load_optional_json(path: Path):
    if not path.is_file():
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None


def evaluate_declared(conditions: dict | None) -> dict:
    """DRY-RUN ONLY. Never authoritative; can never ALLOW."""
    per_condition: dict[str, dict] = {}
    missing: list[str] = []
    not_true: list[str] = []

    src = conditions if isinstance(conditions, dict) else {}
    for cond in UNLOCK_CONDITIONS:
        if cond not in src:
            per_condition[cond] = {"present": False, "value": None, "satisfied": False}
            missing.append(cond)
            continue
        val = src[cond]
        satisfied = val is True
        per_condition[cond] = {"present": True, "value": val, "satisfied": satisfied}
        if not satisfied:
            not_true.append(cond)

    all_true = not missing and not not_true
    # Critically: declared mode NEVER returns ALLOW.
    verdict = "DECLARED_ONLY_NOT_AUTHORITATIVE" if all_true else "HOLD"

    return {
        "artifact_type": "v2_claim_unlock_check",
        "tool": "v2_claim_unlock_check.py",
        "mode": "declared",
        "verdict": verdict,
        "authoritative": False,
        "default_is_hold": True,
        "conditions": per_condition,
        "missing_conditions": missing,
        "unsatisfied_conditions": not_true,
        "note": ("DECLARED mode is a dry-run shape check ONLY. It cannot unlock a "
                 "claim and never returns ALLOW. Use --mode evidence for a real check."),
        "result_like_artifact": False,
    }


def evaluate_evidence(evidence_map: dict | None) -> dict:
    """Authoritative, evidence-bound. ALLOW only if every condition is backed by
    a real report file (and optional verdict matches) AND a complete hash manifest
    is supplied. Any gap -> HOLD."""
    per_condition: dict[str, dict] = {}
    problems: list[str] = []

    if not isinstance(evidence_map, dict):
        return _evidence_result("HOLD", {}, ["no evidence map provided or unreadable"],
                                manifest_ok=False, manifest_path=None)

    # 1. Round hash manifest must be present and complete.
    manifest_path = evidence_map.get("round_hash_manifest")
    manifest_ok = False
    if not manifest_path:
        problems.append("missing round_hash_manifest reference")
    else:
        manifest = _load_optional_json(Path(manifest_path))
        if manifest is None:
            problems.append(f"round_hash_manifest unreadable: {manifest_path}")
        elif manifest.get("artifact_type") != "v2_round_hash_manifest":
            problems.append("round_hash_manifest is not a v2_round_hash_manifest artifact")
        elif not manifest.get("complete"):
            problems.append("round_hash_manifest.complete is not true")
        else:
            manifest_ok = True

    # 2. Each condition must bind to a real report file on disk.
    cond_map = evidence_map.get("conditions", {})
    if not isinstance(cond_map, dict):
        cond_map = {}

    for cond in UNLOCK_CONDITIONS:
        entry = cond_map.get(cond)
        rec = {"present": False, "report": None, "report_exists": False,
               "verdict_ok": None, "satisfied": False}
        if not isinstance(entry, dict):
            per_condition[cond] = rec
            problems.append(f"{cond}: no evidence binding")
            continue
        rec["present"] = True
        report = entry.get("report")
        rec["report"] = report
        if not report:
            per_condition[cond] = rec
            problems.append(f"{cond}: evidence binding has no report path")
            continue
        report_path = Path(report)
        if not report_path.is_file():
            per_condition[cond] = rec
            problems.append(f"{cond}: report file missing on disk: {report}")
            continue
        rec["report_exists"] = True

        # Optional verdict check against the report's content.
        expected = entry.get("expected_verdict")
        if expected is not None:
            report_data = _load_optional_json(report_path)
            field = entry.get("verdict_field", "verdict")
            actual = report_data.get(field) if isinstance(report_data, dict) else None
            rec["verdict_ok"] = (actual == expected)
            if actual != expected:
                per_condition[cond] = rec
                problems.append(f"{cond}: report {field}={actual!r} != expected {expected!r}")
                continue
        rec["satisfied"] = True
        per_condition[cond] = rec

    all_satisfied = all(per_condition[c]["satisfied"] for c in UNLOCK_CONDITIONS)
    verdict = "ALLOW" if (all_satisfied and manifest_ok and not problems) else "HOLD"
    return _evidence_result(verdict, per_condition, problems, manifest_ok, manifest_path)


def _evidence_result(verdict, per_condition, problems, manifest_ok, manifest_path):
    return {
        "artifact_type": "v2_claim_unlock_check",
        "tool": "v2_claim_unlock_check.py",
        "mode": "evidence",
        "verdict": verdict,
        "authoritative": True,
        "default_is_hold": True,
        "round_hash_manifest": manifest_path,
        "round_hash_manifest_ok": manifest_ok,
        "conditions": per_condition,
        "problems": problems,
        "note": ("ALLOW requires every unlock condition bound to a real report file "
                 "(optionally verdict-checked) AND a complete round hash manifest. "
                 "Hand-written booleans cannot unlock a claim. This tool upgrades nothing."),
        "result_like_artifact": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("evidence", "declared"), default="evidence",
                        help="evidence (default, authoritative) or declared (dry-run only)")
    parser.add_argument("--evidence-map", default=None,
                        help="path to an evidence map JSON (evidence mode)")
    parser.add_argument("--conditions", default=None,
                        help="path to a booleans JSON (declared/dry-run mode only)")
    parser.add_argument("--write", metavar="NAME", default=None)
    args = parser.parse_args(argv)

    if args.mode == "declared":
        conditions = _load_optional_json(Path(args.conditions)) if args.conditions else None
        result = evaluate_declared(conditions)
    else:
        evidence_map = _load_optional_json(Path(args.evidence_map)) if args.evidence_map else None
        result = evaluate_evidence(evidence_map)

    emit(result, args.write)
    return 0 if result["verdict"] == "ALLOW" else 2


if __name__ == "__main__":
    sys.exit(main())
