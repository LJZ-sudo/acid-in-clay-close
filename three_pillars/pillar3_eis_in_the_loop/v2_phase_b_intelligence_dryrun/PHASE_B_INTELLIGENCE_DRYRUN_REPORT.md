# Phase B Intelligence Dry-Run Report

- **Date:** 2026-06-02
- **Scope:** prepare + run an auditable, synthetic Phase B intelligence dry-run for the `acid-in-clay-close` project.
- **Boundary banner:** **dry-run only, no scientific claim, v2 remains HOLD.** All inputs are `synthetic_not_real_evidence`.

---

## Verdicts (required answers)

| Question | Answer |
|---|---|
| **Phase B pass?** | **PASS** (synthetic dry-run; capability + wiring only) |
| **v2 claim still HOLD?** | **YES — HOLD.** The authoritative `v2_claim_unlock_check` (evidence mode) returns `HOLD`. |
| **Enter Phase C experiments?** | **NOT YET.** Only on dry-run PASS **AND** explicit human confirmation. This report does not authorise Phase C. |
| **Protected evidence touched?** | **NO.** Before==after SHA-256 on all 5 protected targets (see proof below). |
| **CHI automation enabled?** | **NO.** `enables_chi_automation = false` everywhere. |

PASS here means: the intelligence-layer pieces (S09 switch, memory/critic/heartbeat, S08 offline, EIS guardrail) run end-to-end on synthetic inputs, produce a claim-safe auditable trace, and pass every applicable safety gate. It is **not** a scientific result and unlocks **no** claim.

---

## What was built / changed

### Source changes (minimal, additive, default-OFF) — justified
Allowed under the brief ("可小范围修改 stage3_mechanism 源码/测试，用于暴露开关"). None touch frozen `outputs/`, `data/`, or evidence.

1. `V1.0-qianduan-mainline/stage3_mechanism/src/s8_stage3/config/settings.py` — added field
   `s09_evidence_based_generation: bool = _env_bool("STAGE3_S09_EVIDENCE_BASED_GENERATION", False)`.
   **Why:** the S09 evidence-based branch already read this attribute via `getattr(..., False)`, but it was
   unreachable (no settings field / no env / no CLI). This makes it an explicit, auditable switch. **Default
   False preserves the frozen `deterministic_from_d4` path.**
2. `.../orchestrator/run_stage3.py` — added `--s09-evidence-based-generation` flag that sets
   `STAGE3_S09_EVIDENCE_BASED_GENERATION=true` before `load_settings()` (mirrors the existing `--no-cache` pattern). Default OFF.
3. `.../tests/test_s09_evidence_based_tier3.py` — added two `run_s09`-level tests proving default settings ->
   `deterministic_from_d4` and explicit flag -> `evidence_based_descriptor_match` (and that neither calls the LLM).

### New codex-only deliverables (this directory)
`fake_openalex_provider.py`, `fixtures/*` (all `synthetic_not_real_evidence`), `run_phase_b_dryrun.py`, and the
10 deliverables listed below.

---

## Dry-run results (synthetic)

### S08 — offline api mode
- `literature_mode=api`, provider = `fake_offline_provider`, **`network_used=false`**.
- Produced 3 synthetic cards (`SYN-W001/2/3`), de-duped over 4 queries. Proves api-mode plumbing runs offline.

### S09 — baseline vs evidence-based (same synthetic survey)
| | baseline (flag OFF) | evidence-based (flag ON) |
|---|---|---|
| `generation_mode` | `deterministic_from_d4` | `evidence_based_descriptor_match` |
| `n_instances` | 5 (`I1..I5`) | 3 (`I1..I3`) |
| `audit_ok` | true | true |

The default is unchanged from the frozen path; the difference is mechanism/plumbing only. See `s09_baseline_vs_evidence_based_diff.md`.

### Intelligence layer — memory / critic / heartbeat
- `EpisodicMemory` recorded **only** safe metadata (provider name, mode strings, instance counts, critic verdicts). No performance numbers, no measurement keys, no claim wording.
- `Critic` (default rules): clean text -> ok; synthetic adversarial text -> flagged.
- `Heartbeat` ran on a deterministic integer clock (reproducible; no wall-clock fabricated into artifacts).

### S14 / EIS guardrail
- `check_eis_absolute_claims`: **0** findings on clean text, **1** on the synthetic adversarial text -> guardrail fires.

---

## Safety gates

### Individual verifiers (in deliverables)
- `text_claim_safety_check.json`: `valid = true` (every performance number traces to a synthetic claim-map anchor with sample_id+path; no forbidden wording).
- `memory_safety_check.json`: `verdict = SAFE` (0 violations).

### Aggregate gate — `run_all_checks.py` (independent re-run)
Saved to `run_all_checks_output.json`:
- `gate = DRYRUN_ALLOWED`, `checks_run = 2`, `checks_failed = 0`.
- `text_claims = PASS`, `memory_safe = SAFE`.
- `claim_unlock`: mode `evidence`, verdict **`HOLD`**, authoritative `true`.
- `v2_claims_status = HOLD`, `enables_chi_automation = false`.

> **Scope of this gate (important):** `DRYRUN_ALLOWED` here means **Phase B applicable
> safety checks PASS only** — i.e. the two checks that have a Stage3-intelligence
> counterpart (`text_claims`, `memory_safe`). It is **NOT** a full v2 QC gate PASS.
> The round-artifact, append-only intake, KK-residual, and CHI-precondition checks
> were **not run** (no Stage3 counterpart yet) and must be satisfied against a real
> closed loop before Phase C / any v2 claim. `claim_unlock` remains authoritative
> **HOLD** regardless of this gate.

**Intentionally SKIPPED** (no Stage3 counterpart; passing empties would falsely HOLD the gate):
`--round-dir` (round_hash_manifest / approval_binding / manual_rb_qc / score_layers), `--intake-dir`
(append_only_chain), `--kk-bundle` (kk_residual_summary), `--chi-evidence-dir` (chi_preconditions).

**Minimal future adaptation (not built now):** a Stage3 -> round-artifact adapter that emits the 9 required
round files + an append-only intake chain would let those checks run against a real v2 campaign. For a pure
intelligence dry-run they are correctly out of scope.

---

## Protected-evidence proof (no frozen data touched)

`protected_evidence_check.json` verdict: **UNCHANGED**. SHA-256 before==after on all targets:

| target | type | result |
|---|---|---|
| `stage2_statistics/exports/stage3_seed.json` | file | identical hash |
| `stage1_optimization/campaign_memory/history_db_attapulgite.json` | file | identical hash |
| `stage3_mechanism/data/validation/experimental_feedback.json` | file | identical hash |
| `stage3_mechanism/outputs/verification/**` | dir (459 files) | identical roll-up |
| `data/**` | dir (3921 files) | identical roll-up |

The dry-run writes transient S08/S09 artifacts to a temp dir that is deleted; deliverables are written only
under this codex directory. `paper/current/` was not read or written.

---

## Tests

- `codex/v2_engine_tools_20260601`: `python -m pytest tests -q` -> **34 passed**.
- `V1.0-qianduan-mainline/stage3_mechanism`: `python -m pytest tests -q` -> **162 passed, 3 warnings** (157 prior + S09-switch, settings-env, and evidence-based truthful-metadata tests; 3 pre-existing `datetime.utcnow` deprecation warnings, unrelated to this work).

---

## Keep vs. fix

**Keep:**
- The S09 switch (settings field + CLI flag + tests). Safe, default-OFF, frozen path preserved.
- The dry-run wrapper, offline provider, synthetic fixtures, and the 10 deliverables.

**Still to fix / future (codex-only, not blocking):**
- The intelligence layer is exercised by the wrapper but is still **not wired into** the live
  `orchestrator/pipeline.py` (memory/critic/heartbeat remain standalone). Wiring them into a real run is a
  later, opt-in step.
- No Stage3 -> round-artifact adapter yet (see SKIP note), so `run_all_checks` round/intake/kk checks can't
  run against Stage3 output.
- S08 has a single provider (OpenAlex). Do not imply multi-source; a real OpenAlex run still needs a live
  mailto + manual curation (see `openalex_snapshot_or_plan.md`).

---

## Cleanup (2026-06-02)

A small post-run cleanup was applied (see `PHASE_B_CLEANUP_ACCEPTANCE_NOTE.md`):

1. **`run_manifest.json`** now carries explicit dry-run guarantees:
   `no_live_llm`, `no_network`, `synthetic_only`, `phase_b_applicable_safety_checks_only`
   (all `true`), and excludes `__pycache__/**`, `*.pyc`, `.pytest_cache/**` from hashing.
   The existing `v2_claims_status=HOLD`, `result_like_artifact=false`,
   `enables_chi_automation=false` fields are retained.
2. **Adversarial wording isolated.** The synthetic adversarial "EIS proves…" guardrail
   self-test text is no longer embedded in `memory_critic_heartbeat_trace.json`. The
   trace now keeps only `critic_summary` (`clean_text_ok`, `adversarial_text_ok`,
   issue counts, `guardrail_fired=true`). The full self-test text lives in
   `adversarial_guardrail_fixture_synthetic_not_real_evidence.json`, marked
   synthetic / adversarial-test-only / not-a-claim / scan-excluded.
3. **Settings env test** added (`Stage3Settings()` default False; env `=true` -> True).

## Boundary restatement (fixed)
Current small paper **GO** (unchanged). v2 **HOLD**. EIS = bounded QC / supporting evidence, never mechanism
proof. CHI automation never enabled. The decisive factor for any v2 claim remains **real Phase C lab
evidence**, not code. This dry-run unlocks nothing.
