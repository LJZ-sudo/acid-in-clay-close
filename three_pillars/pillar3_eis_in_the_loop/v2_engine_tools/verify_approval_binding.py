"""Verify that a human_approval.md is hash-bound to its exact round inputs.

A valid approval embeds a line of the form::

    bound_input_sha256: <hex>

where ``<hex>`` is the roll-up SHA-256 over the bound inputs
(``history_before.json``, ``recipe.json``, ``raw_bo_suggestion.json``,
``llm_guardrail.json``). This tool recomputes that roll-up from the files on disk
and compares. If any bound input changed after signing, the verdict is MISMATCH,
so a signature cannot be silently reused against altered inputs.

This tool does NOT sign anything. Signing remains a human action.

Verdicts: MATCH | MISMATCH | MISSING_APPROVAL | MISSING_INPUTS | NO_BINDING_LINE

Usage:
    python verify_approval_binding.py <round_dir> [--write NAME]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from v2tools_common import (
    APPROVAL_BOUND_INPUTS,
    emit,
    rollup_hash,
    sha256_file,
)

BINDING_RE = re.compile(r"bound_input_sha256:\s*([0-9a-fA-F]{64})")


def extract_binding(approval_path: Path) -> str | None:
    text = approval_path.read_text(encoding="utf-8")
    m = BINDING_RE.search(text)
    return m.group(1).lower() if m else None


def verify_binding(round_dir: Path) -> dict:
    round_dir = Path(round_dir)
    approval = round_dir / "human_approval.md"

    if not approval.is_file():
        return _result(round_dir, "MISSING_APPROVAL", None, None, [], list(APPROVAL_BOUND_INPUTS))

    missing_inputs = [n for n in APPROVAL_BOUND_INPUTS if not (round_dir / n).is_file()]
    if missing_inputs:
        return _result(round_dir, "MISSING_INPUTS", None, None, [], missing_inputs)

    declared = extract_binding(approval)
    if declared is None:
        return _result(round_dir, "NO_BINDING_LINE", None, None, [], [])

    present_hashes = {n: sha256_file(round_dir / n) for n in APPROVAL_BOUND_INPUTS}
    recomputed = rollup_hash(present_hashes)
    verdict = "MATCH" if recomputed == declared else "MISMATCH"
    return _result(round_dir, verdict, declared, recomputed, list(APPROVAL_BOUND_INPUTS), [])


def _result(round_dir, verdict, declared, recomputed, bound, missing):
    return {
        "artifact_type": "v2_approval_binding_verification",
        "tool": "verify_approval_binding.py",
        "round_dir": Path(round_dir).as_posix(),
        "verdict": verdict,
        "declared_bound_input_sha256": declared,
        "recomputed_bound_input_sha256": recomputed,
        "bound_inputs": bound,
        "missing": missing,
        "signing_is_human_action": True,
        "result_like_artifact": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("round_dir")
    parser.add_argument("--write", metavar="NAME", default=None)
    args = parser.parse_args(argv)

    result = verify_binding(Path(args.round_dir))
    emit(result, args.write)
    return 0 if result["verdict"] == "MATCH" else 2


if __name__ == "__main__":
    sys.exit(main())
