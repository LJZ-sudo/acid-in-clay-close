"""Verify that Stage3 episodic-memory records are claim-safe before memory is used.

HARDENED Phase A precondition for ever enabling the intelligence-layer memory
(EpisodicMemory). It rejects a memory store that contains any of:

1. **Forbidden claim wording** in any string field ("BO+LLM discovered LRS",
   "EIS proves mechanism", "v2 Pareto achieved", "global optimum", ...).
2. **Unsourced performance numbers** — a performance figure (sigma/Ea/Rb/KK/score
   with a unit or cue) recorded without provenance (a sample_id + data path).
3. **Fabricated experiment results** — a record whose value carries measurement-like
   keys (sigma, conductivity, Ea, rb_ohm, kk_residual, score_v3, ...) without
   provenance binding it to a real source.

Memory store shape (tolerant): EpisodicMemory.persist() output, i.e.
    {"records": [ {"seq":..,"step":..,"key":..,"value":..,"tags":[..],"note":".."}, ... ]}
or a bare list of such records.

A record is considered *sourced* iff it (or its value dict) contains a non-empty
``sample_id`` AND one of ``path`` / ``data_path`` / ``source_path``.

Read-only. Emits no claim. Verdict SAFE only if zero violations.

Usage:
    python verify_memory_safe.py <memory.json> [--write NAME]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from v2tools_common import emit, load_json, scan_forbidden
from verify_text_claims import extract_performance_numbers

MEASUREMENT_LIKE_KEYS = (
    "sigma", "sigma_rt", "sigma_s_cm", "conductivity",
    "ea_high", "ea_low", "ea_low_excess", "rb_ohm",
    "kk_residual", "kk_mu_median", "score_v3",
)
PATH_KEYS = ("path", "data_path", "source_path")


def _records(store) -> list:
    if isinstance(store, list):
        return store
    if isinstance(store, dict) and isinstance(store.get("records"), list):
        return store["records"]
    return []


def _collect_strings(obj) -> list[str]:
    out: list[str] = []
    if isinstance(obj, str):
        out.append(obj)
    elif isinstance(obj, dict):
        for k, v in obj.items():
            out.append(str(k))
            out.extend(_collect_strings(v))
    elif isinstance(obj, list):
        for v in obj:
            out.extend(_collect_strings(v))
    elif obj is not None:
        out.append(str(obj))
    return out


def _has_provenance(record: dict) -> bool:
    candidates = [record]
    val = record.get("value")
    if isinstance(val, dict):
        candidates.append(val)
    src = record.get("source")
    if isinstance(src, dict):
        candidates.append(src)
    for c in candidates:
        if str(c.get("sample_id") or "").strip() and any(
            str(c.get(pk) or "").strip() for pk in PATH_KEYS
        ):
            return True
    return False


def _has_measurement_keys(record: dict) -> list[str]:
    hits: list[str] = []
    val = record.get("value")
    scope = val if isinstance(val, dict) else {}
    for k in scope:
        if str(k).lower() in MEASUREMENT_LIKE_KEYS:
            hits.append(str(k))
    return hits


def verify_memory(store) -> dict:
    records = _records(store)
    violations: list[dict] = []

    for idx, rec in enumerate(records):
        if not isinstance(rec, dict):
            violations.append({"record": idx, "type": "malformed_record",
                               "detail": "record is not an object"})
            continue
        seq = rec.get("seq", idx)
        text_blob = "\n".join(_collect_strings(rec))
        sourced = _has_provenance(rec)

        # 1. forbidden wording
        fb = sorted(set(scan_forbidden(text_blob)))
        if fb:
            violations.append({"record": idx, "seq": seq,
                               "type": "forbidden_wording", "detail": fb})

        # 2. unsourced performance numbers
        perf = extract_performance_numbers(text_blob)
        if perf and not sourced:
            violations.append({"record": idx, "seq": seq,
                               "type": "unsourced_performance_number",
                               "detail": [p["raw"] for p in perf]})

        # 3. fabricated experiment results (measurement-like keys w/o provenance)
        mk = _has_measurement_keys(rec)
        if mk and not sourced:
            violations.append({"record": idx, "seq": seq,
                               "type": "fabricated_experiment_result",
                               "detail": mk})

    verdict = "SAFE" if not violations else "UNSAFE"
    return {
        "artifact_type": "memory_safety_verification",
        "tool": "verify_memory_safe.py",
        "verdict": verdict,
        "record_count": len(records),
        "violation_count": len(violations),
        "violations": violations,
        "result_like_artifact": False,
        "note": ("Memory may record provenance/flags/critic-verdicts/candidate-ids, "
                 "never fabricated results, unsourced performance numbers, or claim wording."),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("memory")
    parser.add_argument("--write", metavar="NAME", default=None)
    args = parser.parse_args(argv)

    store = load_json(Path(args.memory))
    result = verify_memory(store)
    emit(result, args.write)
    return 0 if result["verdict"] == "SAFE" else 2


if __name__ == "__main__":
    sys.exit(main())
