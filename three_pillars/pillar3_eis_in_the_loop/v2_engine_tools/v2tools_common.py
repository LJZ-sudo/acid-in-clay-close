"""Shared helpers for the v2 engine tools (relocated to three_pillars/ on 2026-06-05).

Hard boundaries (enforced by design, not just convention):
- These tools never write into ``three_pillars/`` (round templates, evidence)
  or ``V1.0-qianduan-mainline/``.
- The only writable output location is
  ``three_pillars/pillar3_eis_in_the_loop/v2_engine_tools/out/``.
- No tool emits a scientific result or claim. Free-text scanning rejects
  forbidden overclaim wording.

All tools are read-only unless an explicit ``--write`` flag is passed, and even
then writes are confined to ``out/`` via :func:`safe_out_path`.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Iterable

TOOLS_DIR = Path(__file__).resolve().parent
OUT_DIR = TOOLS_DIR / "out"

# Every synthetic fixture must carry this marker in name and/or content.
SYNTHETIC_MARKER = "synthetic_not_real_evidence"

# The 9 per-round artifacts required by the locked execution contract
# (originally defined in paper/current/scripts/build_bo_v2_execution_engine.py:
#  REQUIRED_ROUND_RESULT_FILES; that script has been retired with paper/, the
#  contract definition is preserved here).
REQUIRED_ROUND_RESULT_FILES = (
    "history_before.json",
    "raw_bo_suggestion.json",
    "llm_guardrail.json",
    "human_approval.md",
    "recipe.json",
    "stage0_result.json",
    "manual_rb_qc.csv",
    "score.json",
    "history_after.json",
)

# Inputs whose content a human approval signature must be bound to.
APPROVAL_BOUND_INPUTS = (
    "history_before.json",
    "recipe.json",
    "raw_bo_suggestion.json",
    "llm_guardrail.json",
)

# Forbidden overclaim wording. Any hit in a free-text field is a hard reject.
FORBIDDEN_WORDING = (
    "global optimum",
    "world record",
    "lowest ever",
    "global best",
    "v2 pareto achieved",
    "pareto front achieved",
    "bo+llm discovered lrs",
    "bo discovered lrs",
    "llm discovered",
    "eis proves mechanism",
    "eis proves the mechanism",
    "equivalent circuit established",
    "equivalent circuit is determined",
    "optimization completed",
    "optimization complete",
    "converged to the global",
    "mobo completed",
    "openalex validated",
    "automated chi closed-loop completed",
)

# Protected trees these tools must never write into.
PROTECTED_PREFIXES = ("three_pillars", "V1.0-qianduan-mainline")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def rollup_hash(name_to_hash: dict[str, str]) -> str:
    """Order-independent roll-up hash over ``name:hash`` pairs."""
    lines = [f"{name}:{name_to_hash[name]}" for name in sorted(name_to_hash)]
    return sha256_text("\n".join(lines))


def scan_forbidden(text: str) -> list[str]:
    """Return the list of forbidden wording hits (case-insensitive)."""
    low = text.lower()
    return [phrase for phrase in FORBIDDEN_WORDING if phrase in low]


def is_iso8601(value: str) -> bool:
    """True iff ``value`` is a parseable ISO-8601 datetime (with date+time)."""
    if not isinstance(value, str) or not value.strip():
        return False
    text = value.strip()
    # Accept a trailing 'Z' (UTC) which datetime.fromisoformat rejects pre-3.11.
    candidate = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        datetime.fromisoformat(candidate)
    except ValueError:
        return False
    # Require a time component (not a bare date) so reviewed_at is a timestamp.
    return ("T" in text) or (" " in text)


# Numeric token matcher for performance-figure extraction. Captures plain and
# scientific notation, with optional surrounding context handled by the caller.
NUMBER_RE = re.compile(
    r"(?<![\w.])"
    r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?"
    r"(?![\w])"
)

# Performance-units that mark a number as a *performance figure* requiring a
# claim-map trace. Plain integers like figure numbers or counts are ignored
# unless adjacent to one of these unit cues.
PERFORMANCE_UNIT_CUES = (
    "s cm-1", "s cm^-1", "s/cm", "s cm",
    "ev", "ohm", "Ω", "cm2", "cm^2",
    "k ", " k,", " k.", " k)", "kelvin",
    "sigma", "conductivity", "ea_high", "ea_low", "activation energy",
    "mu_median", "rb", "score_v3",
)


def load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def is_protected(path: Path) -> bool:
    norm = path.resolve().as_posix()
    return any(("/" + p + "/") in (norm + "/") or norm.endswith("/" + p) or f"/{p}/" in norm
               for p in PROTECTED_PREFIXES)


def safe_out_path(name: str) -> Path:
    """Resolve a writable path under ``out/`` only. Refuses protected trees."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    target = (OUT_DIR / name).resolve()
    if OUT_DIR.resolve() not in target.parents and target != OUT_DIR.resolve():
        raise ValueError(f"refusing to write outside out/: {target}")
    if is_protected(target):
        raise ValueError(f"refusing to write into a protected tree: {target}")
    return target


def write_out_json(name: str, payload: dict) -> Path:
    target = safe_out_path(name)
    with open(target, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
    return target


def emit(payload: dict, write_name: str | None) -> dict:
    """Print JSON to stdout; optionally also persist under out/."""
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    if write_name:
        write_out_json(write_name, payload)
    return payload
