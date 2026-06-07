# Phase B Cleanup Acceptance Note

- **Date:** 2026-06-02
- **Scope:** small post-run cleanup of the Phase B intelligence dry-run products + a tiny settings test. No scope expansion.
- **Banner:** dry-run only, no scientific claim, **v2 remains HOLD**, Phase C **not unlocked**.

## Cleanup verdict: PASS

All five requested fixes were applied and re-verified; both test suites and all
verifiers are green; protected evidence is byte-for-byte unchanged.

## What changed

1. **`run_phase_b_dryrun.py` manifest** — `run_manifest.json` now includes explicit
   guarantees `no_live_llm=true`, `no_network=true`, `synthetic_only=true`,
   `phase_b_applicable_safety_checks_only=true`, plus `manifest_excludes`. Manifest
   hashing now skips `__pycache__/**`, `*.pyc`, `.pytest_cache/**`. Existing
   `v2_claims_status=HOLD`, `result_like_artifact=false`,
   `enables_chi_automation=false` are retained.
2. **Adversarial wording isolated** — `memory_critic_heartbeat_trace.json` no longer
   contains any forbidden phrase or regex-hit text. It keeps only `critic_summary`
   (`clean_text_ok`, `adversarial_text_ok`, issue counts, `guardrail_fired=true`).
   The raw guardrail self-test text moved to
   `adversarial_guardrail_fixture_synthetic_not_real_evidence.json`, marked
   `synthetic_not_real_evidence` / adversarial-test-only / not-a-claim /
   excluded-from-claim-scans-except-guardrail-self-test. (Verified: a grep for
   `EIS proves` / `eis_overclaim` in the trace returns no matches.)
3. **Report updated** — `PHASE_B_INTELLIGENCE_DRYRUN_REPORT.md` now states that
   `run_all_checks.py` represents **Phase B applicable safety checks PASS only**, not
   a full v2 QC gate PASS, and that round/intake/KK/CHI remain unrun (needed before
   Phase C / a real closed loop). A cleanup subsection documents these changes.
4. **Settings test added** — in
   `V1.0-qianduan-mainline/stage3_mechanism/tests/test_s09_evidence_based_tier3.py`:
   `test_settings_flag_defaults_false` (env unset -> `False`) and
   `test_settings_flag_reads_env_true` (`STAGE3_S09_EVIDENCE_BASED_GENERATION=true`
   -> `True`), both via `monkeypatch` (no CLI, no side effects).

## Tests summary

| suite | command | result |
|---|---|---|
| v2 engine tools | `codex/v2_engine_tools_20260601 > python -m pytest tests -q` | **34 passed** |
| stage3 mechanism | `V1.0-qianduan-mainline/stage3_mechanism > python -m pytest tests -q` | **161 passed** (159 + 2 new settings tests; 3 pre-existing `datetime.utcnow` deprecation warnings, unrelated) |

Verifiers (re-run after cleanup):
- `verify_memory_safe.py` on the trace -> `SAFE` (10 records, 0 violations).
- `verify_text_claims.py` on the clean text + claim map -> `valid=true` (2/2 anchored, 0 forbidden).
- `run_phase_b_dryrun.py` -> exit 0; `run_phase_b_dryrun.py --manifest-only` -> manifest rebuilt.

## Protected evidence unchanged

`protected_evidence_check.json` verdict **UNCHANGED**. SHA-256 before==after on all
targets: `stage3_seed.json`, `history_db_attapulgite.json`,
`experimental_feedback.json`, `stage3_mechanism/outputs/verification/**` (459 files),
`data/**` (3921 files). No live OpenAlex, no live LLM, no CHI automation. The cleanup
modified only files under `codex/v2_phase_b_intelligence_dryrun_20260602/` and the two
allowed source/test files; `paper/current/**` was not touched.

## Status (fixed)

- **v2 remains HOLD** — authoritative `claim_unlock` (evidence mode) = HOLD;
  `v2_claims_status=HOLD`, `enables_chi_automation=false`.
- **Phase C still NOT unlocked** — requires a real closed loop + the currently-unrun
  checks + explicit human confirmation.

## Remaining limitations

- `run_all_checks.py` covers only the two Phase-B-applicable checks (`text_claims`,
  `memory_safe`). Round-artifact, append-only intake, KK-residual, and CHI-precondition
  checks have no Stage3 counterpart yet and were not run.
- The intelligence layer (memory/critic/heartbeat) is exercised by the wrapper but is
  still **not wired into** the live `orchestrator/pipeline.py`.
- No Stage3 -> round-artifact adapter exists yet (would be the minimal bridge to run
  the remaining checks against a real campaign).
- S08 has a single provider (OpenAlex), exercised only via an offline fake here; a real
  run still needs a live mailto + manual curation. No multi-source is implied.
