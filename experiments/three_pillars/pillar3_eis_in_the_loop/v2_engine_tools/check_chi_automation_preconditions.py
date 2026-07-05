"""Check CHI automation preconditions. Default verdict: DISABLED. Never enables CHI.

HARDENED (Phase A): the tool now distinguishes a *synthetic fixture* evidence set
from a *real* evidence set, and treats real evidence more conservatively:

- No evidence / missing preconditions / preflight NEEDS_REFERENCE_MACRO -> DISABLED.
- All preconditions present in a clearly SYNTHETIC set -> PRECONDITIONS_MET_SYNTHETIC
  (a dry-run shape check; still does NOT enable CHI).
- All preconditions present in a set that looks REAL (no synthetic_not_real_evidence
  marker) -> HUMAN_DEVICE_REVIEW_REQUIRED. The tool refuses to self-certify real
  hardware readiness; a human device review is mandatory. CHI is still NOT enabled.

In every branch ``enables_chi_automation`` is False and manual EIS remains the only
allowed route. The tool reports readiness; it never flips an automation switch.

CHI execution must stay disabled until all of the following exist and pass:
  - policy/registry docs: CHI_AUTOMATION_POLICY, CHI_MACRO_VALIDATION,
    CHI_MACRO_COMMAND_REGISTRY (+ a macro_command_registry config),
  - macrotest evidence,
  - dummy-cell evidence,
  - a per-round CHI preflight whose status is NOT "NEEDS_REFERENCE_MACRO".

Usage:
    python check_chi_automation_preconditions.py --evidence-dir DIR [--write NAME]
    (no dir, or missing files => DISABLED)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from v2tools_common import SYNTHETIC_MARKER, emit

REQUIRED_DOCS = (
    "CHI_AUTOMATION_POLICY.md",
    "CHI_MACRO_VALIDATION.md",
    "CHI_MACRO_COMMAND_REGISTRY.md",
    "macro_command_registry.yaml",
)
REQUIRED_EVIDENCE = (
    "macrotest_evidence.json",
    "dummy_cell_evidence.json",
    "chi_eis_preflight_gate.json",
)


def _looks_synthetic(evidence_dir: Path) -> bool:
    """True iff the dir path OR any evidence file content carries the synthetic
    marker. A real evidence set is one that does NOT advertise itself synthetic."""
    if SYNTHETIC_MARKER in evidence_dir.as_posix():
        return True
    for name in REQUIRED_DOCS + REQUIRED_EVIDENCE:
        p = evidence_dir / name
        if p.is_file():
            try:
                if SYNTHETIC_MARKER in p.read_text(encoding="utf-8", errors="ignore"):
                    return True
            except OSError:
                continue
    return False


def check(evidence_dir: Path | None) -> dict:
    present_docs: dict[str, bool] = {}
    present_evidence: dict[str, bool] = {}
    preflight_status = None
    reasons: list[str] = []

    if evidence_dir is None or not Path(evidence_dir).is_dir():
        reasons.append("no evidence dir provided or dir missing")
        return _result(evidence_dir, "DISABLED", present_docs, present_evidence,
                       preflight_status, reasons, is_synthetic=None)

    evidence_dir = Path(evidence_dir)
    for d in REQUIRED_DOCS:
        present_docs[d] = (evidence_dir / d).is_file()
        if not present_docs[d]:
            reasons.append(f"missing doc: {d}")
    for e in REQUIRED_EVIDENCE:
        present_evidence[e] = (evidence_dir / e).is_file()
        if not present_evidence[e]:
            reasons.append(f"missing evidence: {e}")

    preflight_path = evidence_dir / "chi_eis_preflight_gate.json"
    if preflight_path.is_file():
        try:
            with open(preflight_path, "r", encoding="utf-8") as fh:
                preflight_status = json.load(fh).get("status")
        except (OSError, json.JSONDecodeError):
            preflight_status = None
            reasons.append("chi_eis_preflight_gate.json unreadable")
        if preflight_status == "NEEDS_REFERENCE_MACRO":
            reasons.append("preflight status NEEDS_REFERENCE_MACRO")

    all_docs = all(present_docs.values()) and len(present_docs) == len(REQUIRED_DOCS)
    all_evidence = all(present_evidence.values()) and len(present_evidence) == len(REQUIRED_EVIDENCE)
    preflight_ok = preflight_status not in (None, "NEEDS_REFERENCE_MACRO")

    is_synthetic = _looks_synthetic(evidence_dir)

    if not (all_docs and all_evidence and preflight_ok):
        verdict = "DISABLED"
    elif is_synthetic:
        verdict = "PRECONDITIONS_MET_SYNTHETIC"
    else:
        # Real-looking evidence: never self-certify. Escalate to a human.
        verdict = "HUMAN_DEVICE_REVIEW_REQUIRED"
        reasons.append("real evidence set: mandatory human device review before any CHI use")

    return _result(evidence_dir, verdict, present_docs, present_evidence,
                   preflight_status, reasons, is_synthetic=is_synthetic)


def _result(evidence_dir, verdict, docs, evidence, preflight_status, reasons, is_synthetic):
    return {
        "artifact_type": "chi_automation_precondition_check",
        "tool": "check_chi_automation_preconditions.py",
        "verdict": verdict,
        "default_is_disabled": True,
        "evidence_dir": (Path(evidence_dir).as_posix() if evidence_dir else None),
        "evidence_looks_synthetic": is_synthetic,
        "required_docs_present": docs,
        "required_evidence_present": evidence,
        "preflight_status": preflight_status,
        "reasons": reasons,
        "manual_eis_remains_only_allowed_route": True,
        "enables_chi_automation": False,
        "result_like_artifact": False,
        "note": ("DISABLED by default. PRECONDITIONS_MET_SYNTHETIC is a dry-run shape "
                 "check on synthetic fixtures. Real evidence can only reach "
                 "HUMAN_DEVICE_REVIEW_REQUIRED. No branch enables CHI automation."),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-dir", default=None)
    parser.add_argument("--write", metavar="NAME", default=None)
    args = parser.parse_args(argv)

    result = check(Path(args.evidence_dir) if args.evidence_dir else None)
    emit(result, args.write)
    # Non-zero unless an explicit synthetic preconditions-met dry-run. Real
    # evidence (HUMAN_DEVICE_REVIEW_REQUIRED) and DISABLED both return non-zero
    # so automation can never be gated "green" by this tool.
    return 0 if result["verdict"] == "PRECONDITIONS_MET_SYNTHETIC" else 3


if __name__ == "__main__":
    sys.exit(main())
