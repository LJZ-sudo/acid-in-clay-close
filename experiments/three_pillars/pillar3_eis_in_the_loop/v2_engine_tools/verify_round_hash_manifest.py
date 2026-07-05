"""Verify a round directory against a previously built hash manifest.

Read-only. Recomputes SHA-256 of each required artifact and compares against the
manifest. Detects TAMPERED files, MISSING files, and incompleteness.

Verdicts:
    OK                 - all present, all hashes match, complete
    TAMPERED           - a present file's hash differs from the manifest
    MISSING            - a manifest-listed file is now absent (or vice versa)
    INCOMPLETE         - manifest itself was not complete

Usage:
    python verify_round_hash_manifest.py <round_dir> <manifest.json> [--write NAME]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from v2tools_common import (
    REQUIRED_ROUND_RESULT_FILES,
    emit,
    load_json,
    rollup_hash,
    sha256_file,
)


def verify_manifest(round_dir: Path, manifest: dict) -> dict:
    round_dir = Path(round_dir)
    recorded = manifest.get("files", {})
    tampered: list[str] = []
    missing: list[str] = []
    extra_present: list[str] = []
    present_hashes: dict[str, str] = {}

    for name in REQUIRED_ROUND_RESULT_FILES:
        rec = recorded.get(name, {})
        path = round_dir / name
        now_present = path.is_file()
        rec_present = bool(rec.get("present"))

        if now_present:
            digest = sha256_file(path)
            present_hashes[name] = digest
            if rec_present and rec.get("sha256") and digest != rec["sha256"]:
                tampered.append(name)
            if not rec_present:
                extra_present.append(name)
        else:
            if rec_present:
                missing.append(name)

    incomplete = not bool(manifest.get("complete"))
    rollup_now = rollup_hash(present_hashes) if present_hashes else None
    rollup_match = rollup_now == manifest.get("rollup_sha256")

    if tampered:
        verdict = "TAMPERED"
    elif missing or extra_present:
        verdict = "MISSING"
    elif incomplete:
        verdict = "INCOMPLETE"
    else:
        verdict = "OK"

    return {
        "artifact_type": "v2_round_hash_manifest_verification",
        "tool": "verify_round_hash_manifest.py",
        "round_dir": round_dir.as_posix(),
        "verdict": verdict,
        "tampered_files": tampered,
        "missing_files": missing,
        "unexpected_present_files": extra_present,
        "manifest_complete": not incomplete,
        "rollup_match": rollup_match,
        "result_like_artifact": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("round_dir")
    parser.add_argument("manifest")
    parser.add_argument("--write", metavar="NAME", default=None)
    args = parser.parse_args(argv)

    manifest = load_json(Path(args.manifest))
    result = verify_manifest(Path(args.round_dir), manifest)
    emit(result, args.write)
    return 0 if result["verdict"] == "OK" else 2


if __name__ == "__main__":
    sys.exit(main())
