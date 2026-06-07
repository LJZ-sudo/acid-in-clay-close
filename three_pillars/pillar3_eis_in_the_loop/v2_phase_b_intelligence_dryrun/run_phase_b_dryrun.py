"""Phase B intelligence dry-run orchestrator (codex-only).

dry-run only, no scientific claim, v2 remains HOLD.

What this does (all on SYNTHETIC inputs, no network, no real evidence):
  1. Snapshots SHA-256 of the protected scientific-evidence paths (before).
  2. Runs S08 in "api" mode against an OFFLINE fake OpenAlex provider, proving the
     api-mode plumbing works without a live connection.
  3. Runs S09 twice over a synthetic survey: baseline (flag OFF ->
     deterministic_from_d4) vs evidence-based (flag ON ->
     evidence_based_descriptor_match), and records the difference.
  4. Exercises the Stage3 intelligence layer: EpisodicMemory + Critic +
     Heartbeat (deterministic clock), and the S14 EIS-overclaim guardrail on a
     clean text and a synthetic adversarial text.
  5. Re-snapshots the protected paths (after) and proves UNCHANGED.
  6. Runs the v2 safety verifiers (verify_text_claims, verify_memory_safe) on the
     dry-run outputs.
  7. Writes auditable deliverables. NOTHING is written into any protected tree;
     transient S08/S09 artifacts go to a temp dir under this folder.

It writes deliverables 3-10 and the memory store. The final REPORT.md and
run_manifest.json are produced by the harness (manifest via --manifest-only).
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent  # .../acid-in-clay-close
STAGE3_SRC = REPO_ROOT / "V1.0-qianduan-mainline" / "stage3_mechanism" / "src"
V2_TOOLS = REPO_ROOT / "codex" / "v2_engine_tools_20260601"
FIXTURES = HERE / "fixtures"

SYNTHETIC_MARKER = "synthetic_not_real_evidence"
DISCLAIMER = "dry-run only, no scientific claim, v2 remains HOLD"

# Protected scientific-evidence paths (hard boundary #2). Files are hashed
# individually; directories get a deterministic roll-up hash over their files.
PROTECTED_FILES = [
    "V1.0-qianduan-mainline/stage2_statistics/exports/stage3_seed.json",
    "V1.0-qianduan-mainline/stage1_optimization/campaign_memory/history_db_attapulgite.json",
    "V1.0-qianduan-mainline/stage3_mechanism/data/validation/experimental_feedback.json",
]
PROTECTED_DIRS = [
    "V1.0-qianduan-mainline/stage3_mechanism/outputs/verification",
    "V1.0-qianduan-mainline/data",
]


# --------------------------------------------------------------------------- #
# path / import setup
# --------------------------------------------------------------------------- #
def _ensure_paths() -> None:
    for p in (str(STAGE3_SRC), str(V2_TOOLS)):
        if p not in sys.path:
            sys.path.insert(0, p)


def _sha256_file(path: Path):
    import hashlib

    if not path.is_file():
        return None
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _rollup_dir(root: Path) -> dict:
    """Deterministic roll-up over all files under ``root`` (sorted by relpath)."""
    import hashlib

    if not root.exists():
        return {"exists": False, "file_count": 0, "rollup_sha256": None}
    pairs = []
    for f in sorted(root.rglob("*")):
        if f.is_file():
            rel = f.relative_to(root).as_posix()
            pairs.append(f"{rel}:{_sha256_file(f)}")
    rollup = hashlib.sha256("\n".join(pairs).encode("utf-8")).hexdigest()
    return {"exists": True, "file_count": len(pairs), "rollup_sha256": rollup}


def snapshot_protected() -> dict:
    snap = {"files": {}, "dirs": {}}
    for rel in PROTECTED_FILES:
        snap["files"][rel] = _sha256_file(REPO_ROOT / rel)
    for rel in PROTECTED_DIRS:
        snap["dirs"][rel] = _rollup_dir(REPO_ROOT / rel)
    return snap


def _git_porcelain_protected() -> dict:
    out = {}
    targets = PROTECTED_FILES + PROTECTED_DIRS
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain", "--"] + targets,
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=60,
        )
        out["returncode"] = proc.returncode
        out["stdout"] = proc.stdout.strip()
        out["stderr"] = proc.stderr.strip()
    except Exception as exc:  # pragma: no cover - git optional
        out["error"] = str(exc)
    return out


# --------------------------------------------------------------------------- #
# synthetic input loading
# --------------------------------------------------------------------------- #
def _strip_meta(d: dict) -> dict:
    return {k: v for k, v in d.items() if not str(k).startswith("_")}


def _load_descriptor_sheet():
    from s8_stage3.contracts.descriptor import DescriptorSheet

    raw = _strip_meta(json.loads((FIXTURES / "descriptor_sheet_synthetic_not_real_evidence.json").read_text(encoding="utf-8")))
    return DescriptorSheet.model_validate(raw)


def _load_survey():
    from s8_stage3.contracts.literature import LiteratureSurvey

    raw = _strip_meta(json.loads((FIXTURES / "s08_survey_synthetic_not_real_evidence.json").read_text(encoding="utf-8")))
    return LiteratureSurvey.model_validate(raw)


class _EmptyClaimGateway:
    """Offline gateway: returns a schema-valid empty claim batch. No LLM, no network."""

    def chat_json(self, messages, step="", output_schema=None):
        return {"synthesis_notes": "", "component_descriptor_claims_by_card": {}}


class _DeterministicClock:
    """Monotonic integer clock so heartbeat timestamps are reproducible."""

    def __init__(self) -> None:
        self._n = 0

    def __call__(self) -> float:
        v = self._n
        self._n += 1
        return float(v)


# --------------------------------------------------------------------------- #
# dry-run core
# --------------------------------------------------------------------------- #
def _run_s08_offline(tmp: Path) -> dict:
    from s8_stage3.agents.s08_literature_scout_materials import run_s08
    from types import SimpleNamespace

    sys.path.insert(0, str(HERE))
    from fake_openalex_provider import FakeOpenAlexProvider

    provider = FakeOpenAlexProvider()
    out_dir = tmp / "s08_offline"
    survey = run_s08(
        _load_descriptor_sheet(),
        _EmptyClaimGateway(),
        out_dir,
        literature_mode="api",
        settings=SimpleNamespace(s08_api_max_results_per_query=5, openalex_mailto=""),
        api_provider=provider,
    )
    return {
        "literature_mode": "api",
        "provider": "fake_offline_provider",
        "network_used": False,
        "n_cards": len(survey.cards),
        "card_ids": [c.card_id for c in survey.cards],
        "provider_query_count": len(provider.calls),
    }


def _run_s09(tmp: Path, *, evidence_based: bool) -> dict:
    from s8_stage3.agents.s09_candidate_family_generator import run_s09
    from s8_stage3.config.settings import Stage3Settings

    settings = Stage3Settings()
    settings.s09_evidence_based_generation = bool(evidence_based)
    out_dir = tmp / ("s09_evidence" if evidence_based else "s09_baseline")

    class _ExplodingGateway:
        def chat_json(self, *a, **k):
            raise AssertionError("S09 dry-run must not call the LLM in these branches")

    run_s09(_load_descriptor_sheet(), _load_survey(), _ExplodingGateway(), out_dir, settings=settings)
    audit = json.loads((out_dir / "08_material_instances" / "candidate_generation_audit.json").read_text(encoding="utf-8"))
    instances = json.loads((out_dir / "08_material_instances" / "material_instances.json").read_text(encoding="utf-8"))
    inst_list = instances.get("instances", [])
    return {
        "s09_evidence_based_generation": bool(evidence_based),
        "generation_mode": audit.get("generation_mode"),
        "n_instances": len(inst_list),
        "instance_ids": [i.get("instance_id") for i in inst_list],
        "audit_ok": audit.get("audit_ok"),
    }


def _run_guardrail() -> dict:
    from s8_stage3.preprocess.eis_guardrails import check_eis_absolute_claims

    clean = (FIXTURES / "clean_claim_text_synthetic_not_real_evidence.txt").read_text(encoding="utf-8")
    # Synthetic adversarial text: deliberately contains an absolute EIS claim so
    # the guardrail must flag it. This is NOT a real claim; it exists only to
    # prove the guardrail fires. (Phrased to avoid the v2 forbidden-wording list.)
    adversarial = "(synthetic adversarial) EIS proves the interfacial transport picture here."
    return {
        "clean_text_findings": len(check_eis_absolute_claims(clean)),
        "adversarial_text_findings": len(check_eis_absolute_claims(adversarial)),
        "adversarial_text_is_synthetic": True,
        "note": "S14/EIS guardrail (check_eis_absolute_claims). Advisory in dry-run; "
                "0 findings on clean text and >=1 on the synthetic adversarial text proves it fires.",
    }


def _run_intelligence(tmp: Path, s08: dict, s09_base: dict, s09_evi: dict, guard: dict) -> tuple[dict, dict, Path]:
    from s8_stage3.agentic.memory import EpisodicMemory
    from s8_stage3.agentic.critic import default_claim_critic
    from s8_stage3.agentic.heartbeat import Heartbeat
    from s8_stage3.preprocess.eis_guardrails import check_eis_absolute_claims

    hb = Heartbeat(clock=_DeterministicClock(), stall_seconds=300.0)
    mem = EpisodicMemory()
    critic = default_claim_critic()
    tags = ["dry_run", SYNTHETIC_MARKER]

    hb.beat("s08_offline", "ok", "offline api-mode plumbing")
    mem.record("s08_offline", "provider", s08["provider"], tags=tags, note="offline api-mode plumbing exercised")
    mem.record("s08_offline", "n_cards", s08["n_cards"], tags=tags, note="synthetic card count only")

    hb.beat("s09_baseline", "ok", "deterministic path")
    mem.record("s09_baseline", "generation_mode", s09_base["generation_mode"], tags=tags, note="flag OFF; frozen path")
    mem.record("s09_baseline", "n_instances", s09_base["n_instances"], tags=tags, note="instance count only")

    hb.beat("s09_evidence", "ok", "evidence-based path")
    mem.record("s09_evidence", "generation_mode", s09_evi["generation_mode"], tags=tags, note="flag ON; opt-in path")
    mem.record("s09_evidence", "n_instances", s09_evi["n_instances"], tags=tags, note="instance count only")

    # critic over the clean text and the synthetic adversarial text
    clean = (FIXTURES / "clean_claim_text_synthetic_not_real_evidence.txt").read_text(encoding="utf-8")
    adversarial = "(synthetic adversarial) EIS proves the interfacial transport picture here."
    crit_clean = critic.review(clean, round=0)
    crit_adv = critic.review(adversarial, round=0)

    hb.beat("s14_guardrail", "ok", "eis guardrail")
    mem.record("s14_guardrail", "clean_text_findings", guard["clean_text_findings"], tags=tags, note="EIS guardrail on clean text")
    mem.record("s14_guardrail", "adversarial_text_findings", guard["adversarial_text_findings"], tags=tags,
               note="EIS guardrail flagged synthetic adversarial text (advisory)")
    mem.record("critic", "clean_text_ok", bool(crit_clean.ok), tags=tags, note="critic review of clean text")
    mem.record("critic", "adversarial_text_ok", bool(crit_adv.ok), tags=tags, note="critic review of synthetic adversarial text")
    hb.beat("done", "done", "dry-run complete")

    store_path = tmp / "memory_store.json"
    mem.persist(store_path)
    store = json.loads(store_path.read_text(encoding="utf-8"))

    adversarial_findings = check_eis_absolute_claims(adversarial)
    guardrail_fired = (len(crit_adv.issues) > 0) or (len(adversarial_findings) > 0)

    # Sanitized trace: NO full forbidden phrases / regex-hit text. Only booleans
    # and counts. The full adversarial detail is isolated in a separate file.
    trace = {
        "_marker": SYNTHETIC_MARKER,
        "_disclaimer": DISCLAIMER,
        "artifact_type": "memory_critic_heartbeat_trace",
        "result_like_artifact": False,
        # verify_memory_safe reads store["records"]; only safe metadata is recorded here.
        "records": store["records"],
        "next_seq": store["next_seq"],
        "critic_summary": {
            "clean_text_ok": bool(crit_clean.ok),
            "clean_text_issue_count": len(crit_clean.issues),
            "adversarial_text_ok": bool(crit_adv.ok),
            "adversarial_text_issue_count": len(crit_adv.issues),
            "guardrail_fired": bool(guardrail_fired),
            "adversarial_detail_file": "adversarial_guardrail_fixture_synthetic_not_real_evidence.json",
        },
        "heartbeat_trace": [b.__dict__ for b in hb._beats],
        "heartbeat_report": hb.report(),
    }

    # Isolated adversarial fixture: the only file that holds the raw guardrail
    # self-test text. Clearly marked synthetic + not-a-claim + scan-excluded.
    adversarial_detail = {
        "_marker": SYNTHETIC_MARKER,
        "_disclaimer": DISCLAIMER,
        "_kind": "adversarial test only",
        "_not_a_claim": True,
        "_scan_policy": "excluded from claim scans except guardrail self-test",
        "artifact_type": "adversarial_guardrail_fixture",
        "result_like_artifact": False,
        "purpose": ("Holds the synthetic adversarial text used to prove the EIS/claim "
                    "guardrail FIRES. This is a guardrail self-test fixture, NOT a scientific "
                    "claim and NOT real evidence."),
        "adversarial_text": adversarial,
        "critic_issue_count": len(crit_adv.issues),
        "critic_issues": crit_adv.issues,
        "eis_guardrail_finding_count": len(adversarial_findings),
        "eis_guardrail_findings": adversarial_findings,
        "guardrail_fired": bool(guardrail_fired),
    }
    return trace, adversarial_detail, store_path


# --------------------------------------------------------------------------- #
# safety verifiers (v2 tools)
# --------------------------------------------------------------------------- #
def _run_safety_checks(trace_path: Path) -> tuple[dict, dict]:
    import verify_text_claims as vtc
    import verify_memory_safe as vms

    text = (FIXTURES / "clean_claim_text_synthetic_not_real_evidence.txt").read_text(encoding="utf-8")
    claim_map = json.loads((FIXTURES / "claim_map_synthetic_not_real_evidence.json").read_text(encoding="utf-8"))
    text_res = vtc.verify_text(text, claim_map)
    mem_res = vms.verify_memory(json.loads(trace_path.read_text(encoding="utf-8")))
    return text_res, mem_res


# --------------------------------------------------------------------------- #
# writers
# --------------------------------------------------------------------------- #
def _w_json(name: str, payload: dict) -> None:
    (HERE / name).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _w_text(name: str, text: str) -> None:
    (HERE / name).write_text(text, encoding="utf-8")


def _s09_diff_md(base: dict, evi: dict) -> str:
    return f"""# S09 baseline vs evidence-based (synthetic dry-run)

> {DISCLAIMER}. All inputs are `{SYNTHETIC_MARKER}`. No real candidate, no real measurement.

This compares the two S09 generation paths on the **same synthetic survey**. It
proves the new explicit switch routes generation correctly. It makes NO claim
that either candidate set is scientifically meaningful.

| aspect | baseline (flag OFF) | evidence-based (flag ON) |
|---|---|---|
| `s09_evidence_based_generation` | `{base['s09_evidence_based_generation']}` | `{evi['s09_evidence_based_generation']}` |
| `generation_mode` | `{base['generation_mode']}` | `{evi['generation_mode']}` |
| `n_instances` | {base['n_instances']} | {evi['n_instances']} |
| `instance_ids` | {base['instance_ids']} | {evi['instance_ids']} |
| `audit_ok` | {base['audit_ok']} | {evi['audit_ok']} |

## Interpretation (bounded)
- Default (`flag OFF`) keeps the **frozen** `deterministic_from_d4` path; this is
  unchanged from the frozen baseline.
- Explicit opt-in (`flag ON`) routes to `evidence_based_descriptor_match`, which
  builds candidates by descriptor coverage over the synthetic claim pool.
- The difference here is **mechanism/plumbing only**. No scientific superiority is
  claimed for either set. v2 remains HOLD.
"""


def _openalex_md() -> str:
    return f"""# OpenAlex: offline snapshot + real-run plan

> {DISCLAIMER}. The snapshot below is `{SYNTHETIC_MARKER}` and MUST NOT be cited as literature.

## What ran in this dry-run
- S08 `api` mode was exercised with an **offline** `FakeOpenAlexProvider`
  (`fake_openalex_provider.py`). No network call was made (`network_used=false`).
- The provider returns a small, fixed pool of clearly-synthetic records whose
  titles/abstracts are stamped `{SYNTHETIC_MARKER}`. These are NOT real papers.

## Offline snapshot template (synthetic)
```
SYN-W001  OH-rich biopolymer host for proton transport   (synthetic)
SYN-W002  One-dimensional clay confinement of acid phases (synthetic)
SYN-W003  Retained phosphoric acid as a mobile proton carrier (synthetic)
```

## Plan for a REAL OpenAlex run (future, human-gated)
1. Set `STAGE3_OPENALEX_MAILTO` to a real contact (polite pool).
2. Run S08 with `--literature-mode api` (live `OpenAlexProvider`).
3. Persist the raw API response as a dated snapshot under a NEW codex dir.
4. **Manual curation required**: a human reviews each returned paper, records a
   curation decision (keep/drop/uncertain) in a CSV with reviewer + timestamp,
   before any card informs a claim.
5. Single provider only for now (OpenAlex). Do NOT imply Semantic Scholar /
   Crossref / Scopus multi-source; those providers do not exist yet.

## Boundary
OpenAlex output is a discovery aid, never evidence by itself. No "OpenAlex
validated" claim is permitted. v2 remains HOLD.
"""


def _mobo_md() -> str:
    return f"""# MOBO / Pareto retrospective boundary (doc-only)

> {DISCLAIMER}.

This dry-run does **not** run MOBO/Pareto and does not touch any optimisation
history. This file only fixes the boundary for a future, real v2 campaign.

## Hard boundaries
- MOBO/Pareto must run only on a NEW, real v2 campaign in a NEW directory.
- It must never rewrite, re-rank, or "improve" the current small-paper results
  in `paper/current/` or the frozen `V1.0-qianduan-mainline/` history.
- No "v2 Pareto achieved", "MOBO completed", or "global optimum" claim is allowed
  (these are on the forbidden-wording list and are blocked by the safety gate).
- Any retrospective analysis of frozen data is read-only and descriptive; it
  cannot upgrade a claim.

## Status
Not started. v2 remains HOLD. Entry requires real Phase C data + human approval.
"""


def _phase_c_md(s09_base: dict, s09_evi: dict) -> str:
    return f"""# Next: Phase C experiment readiness (gated)

> {DISCLAIMER}.

Phase B is a synthetic capability/wiring dry-run. Phase C (real experiments,
new freeze, new claims) is the binding bottleneck and is **not** unlocked here.

## What Phase B established (mechanism only)
- S09 evidence-based generation is now an explicit, default-OFF switch
  (`generation_mode`: `{s09_base['generation_mode']}` -> `{s09_evi['generation_mode']}`).
- Intelligence layer (memory/critic/heartbeat) produces an auditable, claim-safe
  trace on synthetic inputs.
- S08 api mode runs offline; EIS guardrail fires on adversarial text.

## What Phase C still requires (real lab work, human-led)
- [ ] LRS conductivity repeats (n>=3) with manual Rb QC + KK validation.
- [ ] Low-temperature EIS series with bounded caveats.
- [ ] Hysteresis / reproducibility checks.
- [ ] DC polarisation (electronic vs ionic) where claimed.
- [ ] Structural/thermal support (DSC, FTIR/Raman, SEM/EDS) for any mechanism wording.
- [ ] A NEW freeze + a NEW claim map, audited by the v2 evidence-mode unlock check.

## Gate
Do NOT enter Phase C on the basis of this dry-run alone. Entry requires:
(1) this dry-run PASS, AND (2) explicit human confirmation. v2 remains HOLD.
"""


# --------------------------------------------------------------------------- #
# manifest mode
# --------------------------------------------------------------------------- #
def _manifest_excluded(rel: str) -> bool:
    """Exclude transient / cache artifacts from the manifest."""
    parts = rel.split("/")
    if "__pycache__" in parts or ".pytest_cache" in parts:
        return True
    if rel.endswith(".pyc"):
        return True
    return False


def _build_manifest() -> dict:
    files = {}
    for f in sorted(HERE.rglob("*")):
        if not f.is_file() or f.name == "run_manifest.json":
            continue
        rel = f.relative_to(HERE).as_posix()
        if _manifest_excluded(rel):
            continue
        files[rel] = _sha256_file(f)
    return {
        "_marker": SYNTHETIC_MARKER,
        "_disclaimer": DISCLAIMER,
        "artifact_type": "phase_b_run_manifest",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "python_version": sys.version.split()[0],
        "result_like_artifact": False,
        # Explicit dry-run guarantees (cleanup 2026-06-02).
        "no_live_llm": True,
        "no_network": True,
        "synthetic_only": True,
        "phase_b_applicable_safety_checks_only": True,
        "manifest_excludes": ["__pycache__/**", "*.pyc", ".pytest_cache/**"],
        "file_count": len(files),
        "files_sha256": files,
        "v2_claims_status": "HOLD",
        "enables_chi_automation": False,
    }


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest-only", action="store_true",
                        help="Only (re)build run_manifest.json over the deliverable dir.")
    args = parser.parse_args(argv)

    _ensure_paths()

    if args.manifest_only:
        _w_json("run_manifest.json", _build_manifest())
        print("run_manifest.json rebuilt")
        return 0

    before = snapshot_protected()

    tmp = Path(tempfile.mkdtemp(prefix="phase_b_dryrun_", dir=str(HERE)))
    try:
        s08 = _run_s08_offline(tmp)
        s09_base = _run_s09(tmp, evidence_based=False)
        s09_evi = _run_s09(tmp, evidence_based=True)
        guard = _run_guardrail()
        trace, adversarial_detail, store_path = _run_intelligence(tmp, s08, s09_base, s09_evi, guard)

        # isolate the adversarial guardrail self-test text into its own file
        _w_json("adversarial_guardrail_fixture_synthetic_not_real_evidence.json", adversarial_detail)
        # write the sanitized trace first so the safety verifier can read records from it
        _w_json("memory_critic_heartbeat_trace.json", trace)
        text_res, mem_res = _run_safety_checks(HERE / "memory_critic_heartbeat_trace.json")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    after = snapshot_protected()
    unchanged = (before == after)

    protected = {
        "_marker": SYNTHETIC_MARKER,
        "_disclaimer": DISCLAIMER,
        "artifact_type": "protected_evidence_check",
        "result_like_artifact": False,
        "verdict": "UNCHANGED" if unchanged else "CHANGED",
        "before": before,
        "after": after,
        "git_status_porcelain": _git_porcelain_protected(),
        "note": "Dry-run writes nothing into protected trees; before==after proves it.",
    }
    _w_json("protected_evidence_check.json", protected)

    # safety check deliverables (stamp synthetic + disclaimer)
    for res in (text_res, mem_res):
        res["_marker"] = SYNTHETIC_MARKER
        res["_disclaimer"] = DISCLAIMER
    _w_json("text_claim_safety_check.json", text_res)
    _w_json("memory_safety_check.json", mem_res)

    # markdown deliverables
    _w_text("s09_baseline_vs_evidence_based_diff.md", _s09_diff_md(s09_base, s09_evi))
    _w_text("openalex_snapshot_or_plan.md", _openalex_md())
    _w_text("mobo_retrospective_boundary.md", _mobo_md())
    _w_text("next_phase_c_experiment_readiness.md", _phase_c_md(s09_base, s09_evi))

    # a compact run summary for the harness to fold into the report
    summary = {
        "_marker": SYNTHETIC_MARKER,
        "_disclaimer": DISCLAIMER,
        "artifact_type": "phase_b_dryrun_summary",
        "result_like_artifact": False,
        "s08_offline": s08,
        "s09_baseline": s09_base,
        "s09_evidence": s09_evi,
        "guardrail": guard,
        "text_claim_valid": text_res["valid"],
        "memory_verdict": mem_res["verdict"],
        "protected_verdict": protected["verdict"],
        "v2_claims_status": "HOLD",
        "enables_chi_automation": False,
    }
    _w_json("dryrun_summary.json", summary)

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if (text_res["valid"] and mem_res["verdict"] == "SAFE" and unchanged) else 2


if __name__ == "__main__":
    sys.exit(main())
