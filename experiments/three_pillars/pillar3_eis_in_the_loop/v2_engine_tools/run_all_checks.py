"""One-click runner for all v2 safety / QC checks (Phase B dry-run pre-gate).

Aggregates every hardened check into a single HOLD-biased verdict. It answers ONE
question: *is it safe to proceed to a Phase B intelligence dry-run?* — which
requires every executed safety/QC check to be green. It does NOT and cannot
unlock any scientific claim: v2 claims remain HOLD regardless of this gate, and
the claim-unlock check is reported separately (evidence mode, default HOLD).

All inputs are optional; a check with no input is SKIPPED. A failing or erroring
check forces the overall gate to HOLD.

Checks (when inputs are supplied):
- round hash manifest complete            (--round-dir)
- approval binding MATCH                   (--round-dir)
- manual Rb QC schema valid                (--round-dir/manual_rb_qc.csv)
- score-layer separation valid             (--round-dir/score.json)
- append-only chain OK + payload dual-verify (--intake-dir)
- KK residual summary (informational)      (--kk-bundle)
- text-claim traceability valid            (--text + --claim-map)
- memory safety SAFE                        (--memory)
- CHI preconditions (never enabling)        (--chi-evidence-dir)
- claim-unlock (evidence mode, default HOLD)(--evidence-map)

Usage:
    python run_all_checks.py --round-dir DIR [--intake-dir DIR] [--kk-bundle F]
        [--text F --claim-map F] [--memory F] [--chi-evidence-dir DIR]
        [--evidence-map F] [--write NAME]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import build_round_hash_manifest as brh
import verify_approval_binding as vab
import verify_append_only_chain as vac
import validate_manual_rb_qc as vrb
import validate_score_layers as vsl
import summarize_kk_residuals as skk
import v2_claim_unlock_check as vcu
import check_chi_automation_preconditions as cchi
import verify_text_claims as vtc
import verify_memory_safe as vms
from v2tools_common import TOOLS_DIR, emit, load_json


def _check(name, ran, passed, detail):
    return {"check": name, "ran": ran, "passed": passed, "detail": detail}


def run_all(args) -> dict:
    checks: list[dict] = []

    # --- round-dir derived checks ---
    if args.round_dir:
        rd = Path(args.round_dir)
        manifest = brh.build_manifest(rd)
        checks.append(_check("round_hash_manifest", True, bool(manifest["complete"]),
                             {"complete": manifest["complete"], "missing": manifest["missing_files"]}))

        binding = vab.verify_binding(rd)
        checks.append(_check("approval_binding", True, binding["verdict"] == "MATCH",
                             {"verdict": binding["verdict"]}))

        rb_csv = rd / "manual_rb_qc.csv"
        if rb_csv.is_file():
            schema = load_json(TOOLS_DIR / "manual_rb_qc_schema.json")
            rbres = vrb.validate_csv(rb_csv, schema)
            checks.append(_check("manual_rb_qc", True, bool(rbres["valid"]),
                                 {"valid": rbres["valid"], "row_errors": rbres["row_errors"],
                                  "missing_columns": rbres["missing_columns"]}))
        else:
            checks.append(_check("manual_rb_qc", False, None, "no manual_rb_qc.csv in round dir"))

        score_json = rd / "score.json"
        if score_json.is_file():
            sres = vsl.validate_score(load_json(score_json))
            checks.append(_check("score_layers", True, bool(sres["valid"]),
                                 {"valid": sres["valid"], "errors": sres["errors"]}))
        else:
            checks.append(_check("score_layers", False, None, "no score.json in round dir"))
    else:
        for n in ("round_hash_manifest", "approval_binding", "manual_rb_qc", "score_layers"):
            checks.append(_check(n, False, None, "no --round-dir"))

    # --- append-only chain ---
    if args.intake_dir:
        chain = vac.verify_chain(Path(args.intake_dir))
        checks.append(_check("append_only_chain", True, chain["verdict"] == "OK",
                             {"verdict": chain["verdict"]}))
    else:
        checks.append(_check("append_only_chain", False, None, "no --intake-dir"))

    # --- KK summary (informational; bounded-caveat is reported, not a hard fail) ---
    if args.kk_bundle:
        kk = skk.summarize(load_json(Path(args.kk_bundle)))
        checks.append(_check("kk_residual_summary", True, True,
                             {"any_bounded_caveat_required": kk["any_bounded_caveat_required"],
                              "kk_failed_points": kk["kk_failed_points"],
                              "informational": True}))
    else:
        checks.append(_check("kk_residual_summary", False, None, "no --kk-bundle"))

    # --- text-claim traceability ---
    if args.text and args.claim_map:
        text = Path(args.text).read_text(encoding="utf-8")
        tres = vtc.verify_text(text, load_json(Path(args.claim_map)))
        checks.append(_check("text_claims", True, bool(tres["valid"]),
                             {"valid": tres["valid"],
                              "untraceable": tres["untraceable_numbers"],
                              "forbidden": tres["forbidden_wording_hits"]}))
    else:
        checks.append(_check("text_claims", False, None, "no --text/--claim-map"))

    # --- memory safety ---
    if args.memory:
        mres = vms.verify_memory(load_json(Path(args.memory)))
        checks.append(_check("memory_safe", True, mres["verdict"] == "SAFE",
                             {"verdict": mres["verdict"], "violations": mres["violations"]}))
    else:
        checks.append(_check("memory_safe", False, None, "no --memory"))

    # --- CHI preconditions (never enabling; informational for the dry-run gate) ---
    if args.chi_evidence_dir:
        chi = cchi.check(Path(args.chi_evidence_dir))
        checks.append(_check("chi_preconditions", True, chi["enables_chi_automation"] is False,
                             {"verdict": chi["verdict"], "enables_chi_automation": chi["enables_chi_automation"]}))
    else:
        checks.append(_check("chi_preconditions", False, None, "no --chi-evidence-dir"))

    # --- claim unlock (evidence mode, authoritative, default HOLD) ---
    evidence_map = None
    if args.evidence_map:
        p = Path(args.evidence_map)
        if p.is_file():
            evidence_map = load_json(p)
    unlock = vcu.evaluate_evidence(evidence_map)

    # Gate: HOLD unless every check that RAN passed.
    ran = [c for c in checks if c["ran"]]
    failed = [c for c in ran if c["passed"] is False]
    gate = "DRYRUN_ALLOWED" if (ran and not failed) else "HOLD"

    return {
        "artifact_type": "v2_all_checks_summary",
        "tool": "run_all_checks.py",
        "gate": gate,
        "checks_run": len(ran),
        "checks_failed": len(failed),
        "failed_checks": [c["check"] for c in failed],
        "checks": checks,
        "claim_unlock": {"mode": unlock["mode"], "verdict": unlock["verdict"],
                         "authoritative": unlock["authoritative"]},
        "v2_claims_status": "HOLD",
        "enables_chi_automation": False,
        "result_like_artifact": False,
        "note": ("DRYRUN_ALLOWED means safety/QC checks are green enough to attempt a "
                 "Phase B intelligence dry-run. It does NOT unlock any scientific claim; "
                 "v2 claims remain HOLD."),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--round-dir", default=None)
    parser.add_argument("--intake-dir", default=None)
    parser.add_argument("--kk-bundle", default=None)
    parser.add_argument("--text", default=None)
    parser.add_argument("--claim-map", default=None)
    parser.add_argument("--memory", default=None)
    parser.add_argument("--chi-evidence-dir", default=None)
    parser.add_argument("--evidence-map", default=None)
    parser.add_argument("--write", metavar="NAME", default=None)
    args = parser.parse_args(argv)

    result = run_all(args)
    emit(result, args.write)
    return 0 if result["gate"] == "DRYRUN_ALLOWED" else 2


if __name__ == "__main__":
    sys.exit(main())
