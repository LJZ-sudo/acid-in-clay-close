"""Verify the integrity of an append-only raw-EIS intake hash chain.

HARDENED (Phase A): dual payload verification. In addition to the chain-link
checks, when an entry declares a ``payload_path`` the tool now resolves that path
(relative to the intake dir) and confirms:
- the payload file actually exists  -> else PAYLOAD_MISSING
- its on-disk SHA-256 equals the entry's ``payload_sha256`` -> else PAYLOAD_REPLACED

This catches the case where the manifest chain is internally consistent but the
raw payload it points at was deleted or swapped after the fact.

The intake directory contains a series of manifest JSON files (any names), each:

    {
      "seq": <int, 0-based, contiguous>,
      "payload_sha256": "<hex of the raw payload it admits>",
      "payload_path": "<optional path, relative to intake dir, to the raw payload>",
      "parent_hash": "<entry_hash of seq-1, or null for seq 0>",
      "entry_hash": "<sha256(parent_hash_str + payload_sha256)>"
    }

The chain is append-only iff:
- seq values are 0..N-1 with no gaps and no duplicates,
- each entry_hash recomputes correctly from (parent_hash, payload_sha256),
- each parent_hash equals the previous entry's entry_hash (seq 0 -> null),
- every declared payload exists and its hash matches payload_sha256.

Verdicts (worst wins, in this order):
    OVERWRITE_DETECTED | PAYLOAD_REPLACED | PAYLOAD_MISSING |
    MISSING_PARENT | BROKEN_CHAIN | OK | EMPTY

This tool never writes raw EIS and never fabricates data; it only inspects
manifests and hashes payloads on disk.

Usage:
    python verify_append_only_chain.py <intake_dir> [--write NAME]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from v2tools_common import emit, sha256_file, sha256_text


def _entry_hash(parent_hash, payload_sha256: str) -> str:
    parent_str = "null" if parent_hash in (None, "", "null") else str(parent_hash)
    return sha256_text(parent_str + payload_sha256)


def verify_chain(intake_dir: Path) -> dict:
    intake_dir = Path(intake_dir)
    entries = []
    for p in sorted(intake_dir.glob("*.json")):
        try:
            with open(p, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError):
            continue
        if "seq" in data and "payload_sha256" in data and "entry_hash" in data:
            data["_file"] = p.name
            entries.append(data)

    if not entries:
        return _result(intake_dir, "EMPTY", 0, [], [], [], [], [], [])

    seqs = [e["seq"] for e in entries]
    duplicates = sorted({s for s in seqs if seqs.count(s) > 1})
    entries_by_seq = {e["seq"]: e for e in entries}
    unique_seqs = sorted(set(seqs))
    gaps = [i for i in range(max(unique_seqs) + 1) if i not in entries_by_seq]

    tampered: list[int] = []
    broken_links: list[int] = []
    payload_missing: list[int] = []
    payload_replaced: list[int] = []
    payload_checked: list[int] = []

    prev_hash = None
    for i in unique_seqs:
        e = entries_by_seq[i]
        recomputed = _entry_hash(e.get("parent_hash"), e["payload_sha256"])
        if recomputed != str(e.get("entry_hash", "")).lower():
            tampered.append(i)
        # link check
        if i == 0:
            if e.get("parent_hash") not in (None, "", "null"):
                broken_links.append(i)
        else:
            if str(e.get("parent_hash")) != str(prev_hash):
                broken_links.append(i)
        prev_hash = e.get("entry_hash")

        # dual payload verification (only when a payload_path is declared)
        payload_rel = e.get("payload_path")
        if payload_rel:
            payload_checked.append(i)
            payload_abs = (intake_dir / payload_rel)
            if not payload_abs.is_file():
                payload_missing.append(i)
            else:
                actual = sha256_file(payload_abs)
                if actual != str(e.get("payload_sha256", "")).lower():
                    payload_replaced.append(i)

    if duplicates or tampered:
        verdict = "OVERWRITE_DETECTED"
    elif payload_replaced:
        verdict = "PAYLOAD_REPLACED"
    elif payload_missing:
        verdict = "PAYLOAD_MISSING"
    elif gaps:
        verdict = "MISSING_PARENT"
    elif broken_links:
        verdict = "BROKEN_CHAIN"
    else:
        verdict = "OK"

    return _result(intake_dir, verdict, len(entries), tampered, broken_links,
                   duplicates, gaps, payload_missing, payload_replaced, payload_checked)


def _result(intake_dir, verdict, n, tampered, broken_links, duplicates, gaps,
            payload_missing, payload_replaced, payload_checked=None):
    return {
        "artifact_type": "v2_append_only_chain_verification",
        "tool": "verify_append_only_chain.py",
        "intake_dir": Path(intake_dir).as_posix(),
        "verdict": verdict,
        "entry_count": n,
        "tampered_seqs": tampered,
        "broken_link_seqs": broken_links,
        "duplicate_seqs": duplicates,
        "missing_seqs": gaps or [],
        "payload_missing_seqs": payload_missing,
        "payload_replaced_seqs": payload_replaced,
        "payload_checked_seqs": payload_checked or [],
        "writes_raw_eis": False,
        "result_like_artifact": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("intake_dir")
    parser.add_argument("--write", metavar="NAME", default=None)
    args = parser.parse_args(argv)

    result = verify_chain(Path(args.intake_dir))
    emit(result, args.write)
    return 0 if result["verdict"] == "OK" else 2


if __name__ == "__main__":
    sys.exit(main())
