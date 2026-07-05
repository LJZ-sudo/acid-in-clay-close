"""Generate hash-dependent synthetic fixtures (synthetic_not_real_evidence).

Creates:
- round_valid_synthetic_not_real_evidence/  (9 required files; human_approval.md
  carries a correct bound_input_sha256 over the 4 bound inputs)
- append_only_clean_synthetic_not_real_evidence/   (valid 3-link chain)
- append_only_broken_synthetic_not_real_evidence/  (wrong parent link)
- append_only_overwrite_synthetic_not_real_evidence/ (tampered entry_hash)

Run:  python tests/fixtures/make_hashed_fixtures.py
Idempotent. Writes only under tests/fixtures/. Nothing here is real evidence.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

FX = Path(__file__).resolve().parent
TOOLS_DIR = FX.parent.parent
sys.path.insert(0, str(TOOLS_DIR))

from v2tools_common import APPROVAL_BOUND_INPUTS, rollup_hash, sha256_file, sha256_text  # noqa: E402

MARK = "synthetic_not_real_evidence"


def _wj(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def build_round() -> Path:
    rd = FX / "round_valid_synthetic_not_real_evidence"
    rd.mkdir(parents=True, exist_ok=True)
    _wj(rd / "history_before.json", {"_marker": MARK, "rows": [{"R": 0.5, "N": 1.2}]})
    _wj(rd / "recipe.json", {"_marker": MARK, "R": 0.5, "N": 1.2, "attapulgite_g": 1.0})
    _wj(rd / "raw_bo_suggestion.json", {"_marker": MARK, "R": 0.51, "N": 1.18})
    _wj(rd / "llm_guardrail.json", {"_marker": MARK, "decision": "accept", "reason": "synthetic"})
    _wj(rd / "stage0_result.json", {"_marker": MARK, "sigma_RT": 0.01})
    _wj(rd / "score.json", {
        "_marker": MARK,
        "raw_result_ref": "stage0_result.json",
        "manual_rb_qc_ref": "manual_rb_qc.csv",
        "score_v3": -1.0,
        "pareto_status": "dominated",
    })
    _wj(rd / "history_after.json", {"_marker": MARK, "rows": [{"R": 0.5, "N": 1.2}, {"R": 0.51, "N": 1.18}]})
    (rd / "manual_rb_qc.csv").write_text(
        "round_id,sample_id,temperature_K,Rb_ohm,thickness_cm,area_cm2,sigma_S_cm-1,rb_source,"
        "kk_mu_median,temp_sequence,reviewer,reviewed_at,qc_tier,acceptance_decision,caveat\n"
        f"v2r00,{MARK},273,120.5,0.022,1.96,0.0085,manual,0.041,cooling,synthetic_reviewer,"
        "2026-06-01T00:00:00Z,main-text candidate,accepted,\n",
        encoding="utf-8",
    )
    # Bind approval to the 4 bound inputs.
    present = {n: sha256_file(rd / n) for n in APPROVAL_BOUND_INPUTS}
    bound = rollup_hash(present)
    (rd / "human_approval.md").write_text(
        f"# Human Approval ({MARK})\n\n"
        "This is a synthetic approval for tool testing only; it authorizes nothing real.\n\n"
        f"bound_input_sha256: {bound}\n\n"
        "signed_by: synthetic_reviewer\n",
        encoding="utf-8",
    )
    return rd


def _entry_hash(parent, payload_sha: str) -> str:
    parent_str = "null" if parent in (None, "", "null") else str(parent)
    return sha256_text(parent_str + payload_sha)


def build_chain_clean() -> Path:
    d = FX / "append_only_clean_synthetic_not_real_evidence"
    d.mkdir(parents=True, exist_ok=True)
    prev = None
    for seq in range(3):
        payload = sha256_text(f"{MARK}-payload-{seq}")
        eh = _entry_hash(prev, payload)
        _wj(d / f"intake_{seq:02d}.json", {
            "_marker": MARK, "seq": seq, "payload_sha256": payload,
            "parent_hash": prev, "entry_hash": eh,
        })
        prev = eh
    return d


def build_chain_broken() -> Path:
    d = FX / "append_only_broken_synthetic_not_real_evidence"
    d.mkdir(parents=True, exist_ok=True)
    prev = None
    for seq in range(3):
        payload = sha256_text(f"{MARK}-payload-{seq}")
        # seq 2 points to a wrong parent, but entry_hash is computed consistently
        # with that wrong parent so only the LINK is broken, not the hash.
        parent = prev
        if seq == 2:
            parent = "deadbeef" * 8
        eh = _entry_hash(parent, payload)
        _wj(d / f"intake_{seq:02d}.json", {
            "_marker": MARK, "seq": seq, "payload_sha256": payload,
            "parent_hash": parent, "entry_hash": eh,
        })
        prev = _entry_hash(prev, payload)  # the true chain head continues correctly
    return d


def build_chain_overwrite() -> Path:
    d = FX / "append_only_overwrite_synthetic_not_real_evidence"
    d.mkdir(parents=True, exist_ok=True)
    prev = None
    for seq in range(3):
        payload = sha256_text(f"{MARK}-payload-{seq}")
        eh = _entry_hash(prev, payload)
        if seq == 1:
            # Tamper: payload changed after the fact but entry_hash left stale.
            payload = sha256_text(f"{MARK}-payload-{seq}-OVERWRITTEN")
        _wj(d / f"intake_{seq:02d}.json", {
            "_marker": MARK, "seq": seq, "payload_sha256": payload,
            "parent_hash": prev, "entry_hash": eh,
        })
        prev = eh
    return d


def build_chain_with_payloads() -> tuple[Path, Path, Path]:
    """Three payload-bearing chains: clean / payload-missing / payload-replaced.

    Each entry declares payload_path pointing at a sibling .bin file whose hash
    must equal payload_sha256 (dual verification)."""
    def _build(dirname: str, mode: str) -> Path:
        d = FX / dirname
        d.mkdir(parents=True, exist_ok=True)
        prev = None
        for seq in range(3):
            content = f"{MARK}-raw-eis-payload-{seq}".encode("utf-8")
            payload_name = f"payload_{seq:02d}.bin"
            payload_file = d / payload_name
            payload_file.write_bytes(content)
            payload_sha = hashlib.sha256(content).hexdigest()
            eh = _entry_hash(prev, payload_sha)
            _wj(d / f"intake_{seq:02d}.json", {
                "_marker": MARK, "seq": seq, "payload_sha256": payload_sha,
                "payload_path": payload_name, "parent_hash": prev, "entry_hash": eh,
            })
            prev = eh
            if mode == "missing" and seq == 1:
                payload_file.unlink()  # delete the raw payload after the fact
            if mode == "replaced" and seq == 1:
                payload_file.write_bytes(content + b"-TAMPERED")  # swap raw content
        return d

    clean = _build("append_only_payload_clean_synthetic_not_real_evidence", "clean")
    missing = _build("append_only_payload_missing_synthetic_not_real_evidence", "missing")
    replaced = _build("append_only_payload_replaced_synthetic_not_real_evidence", "replaced")
    return clean, missing, replaced


def main() -> int:
    build_round()
    build_chain_clean()
    build_chain_broken()
    build_chain_overwrite()
    build_chain_with_payloads()
    print("synthetic_not_real_evidence fixtures generated.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
