"""Build a per-round hash manifest over the 9 required round artifacts.

Read-only over the input round directory. Writes a manifest JSON only into
``out/`` and only when ``--write`` is passed. Does not validate the scientific
content of any artifact; it only records presence + SHA-256 + a roll-up hash and
a completeness verdict.

Usage:
    python build_round_hash_manifest.py <round_dir> [--write <name.json>]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from v2tools_common import (
    REQUIRED_ROUND_RESULT_FILES,
    emit,
    rollup_hash,
    sha256_file,
)


def build_manifest(round_dir: Path) -> dict:
    round_dir = Path(round_dir)
    files: dict[str, dict] = {}
    present_hashes: dict[str, str] = {}
    missing: list[str] = []
    for name in REQUIRED_ROUND_RESULT_FILES:
        path = round_dir / name
        if path.is_file():
            digest = sha256_file(path)
            files[name] = {
                "present": True,
                "sha256": digest,
                "size_bytes": path.stat().st_size,
            }
            present_hashes[name] = digest
        else:
            files[name] = {"present": False, "sha256": None, "size_bytes": None}
            missing.append(name)

    complete = len(missing) == 0
    return {
        "artifact_type": "v2_round_hash_manifest",
        "tool": "build_round_hash_manifest.py",
        "round_dir": round_dir.as_posix(),
        "required_files": list(REQUIRED_ROUND_RESULT_FILES),
        "files": files,
        "missing_files": missing,
        "complete": complete,
        "rollup_sha256": rollup_hash(present_hashes) if present_hashes else None,
        "result_like_artifact": False,
        "note": "Hash manifest only; no scientific result is asserted.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("round_dir", help="path to a round_XX folder")
    parser.add_argument("--write", metavar="NAME", default=None,
                        help="also write the manifest into out/NAME")
    args = parser.parse_args(argv)

    manifest = build_manifest(Path(args.round_dir))
    emit(manifest, args.write)
    return 0 if manifest["complete"] else 2


if __name__ == "__main__":
    sys.exit(main())
