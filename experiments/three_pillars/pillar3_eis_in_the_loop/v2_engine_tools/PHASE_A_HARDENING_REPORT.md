# v2 Phase A Hardening Report

- **Date:** 2026-06-02
- **Scope:** harden the v2 execution/QC tools from the first batch into a
  **Phase B intelligence dry-run pre-gate**. Only `codex/v2_engine_tools_20260601/`
  was modified.
- **Verdict context (unchanged):** current small paper **GO**; v2 **HOLD**; EIS =
  bounded QC / supporting evidence only; no v2 claim is emitted.

All tools remain **default read-only / default-safe** and emit **no scientific
result or claim**. The hardening makes the safety gates strictly harder to pass by
accident and adds two new pre-Phase-B safety verifiers plus a one-click aggregator.

---

## 1. Required items — status

| # | Required item | Status | Where |
|---|---|---|---|
| 1 | `v2_claim_unlock_check.py` evidence-bound; hand-written booleans cannot ALLOW; missing report/manifest -> HOLD | **Done** | `v2_claim_unlock_check.py` |
| 2 | `verify_append_only_chain.py` payload_path / payload_sha256 dual-verify (missing / replaced) | **Done** | `verify_append_only_chain.py` |
| 3 | `manual_rb_qc_schema.json` adds `round_id`, `acceptance_decision`, `caveat`, ISO `reviewed_at` | **Done** | `manual_rb_qc_schema.json` + `validate_manual_rb_qc.py` |
| 4 | `summarize_kk_residuals.py`: `kk_passed=false` always forces bounded caveat | **Done** | `summarize_kk_residuals.py` |
| 5 | `check_chi_automation_preconditions.py`: real evidence -> `HUMAN_DEVICE_REVIEW_REQUIRED`, never enables CHI | **Done** | `check_chi_automation_preconditions.py` |
| 6 | `verify_text_claims.py`: performance numbers must trace to claim map/sample/path | **Done (new)** | `verify_text_claims.py` |
| 7 | `verify_memory_safe.py`: reject forbidden wording / unsourced numbers / fabricated results | **Done (new)** | `verify_memory_safe.py` |
| 8 | `run_all_checks.py`: one-click runner for all v2 safety/QC checks | **Done (new)** | `run_all_checks.py` |
| 9 | Expanded `tests/fixtures/`, all marked `synthetic_not_real_evidence` | **Done** | `tests/fixtures/` |
| 10 | Every tool tested; `PHASE_A_HARDENING_REPORT.md` produced | **Done** | `tests/`, this file |

---

## 2. What each hardening changes (behavioral deltas)

### 1. `v2_claim_unlock_check.py` — evidence-bound, two modes
- **`--mode evidence` (default, authoritative):** ALLOW requires (a) a complete
  round **hash manifest** (`artifact_type=v2_round_hash_manifest`, `complete=true`)
  AND (b) every one of the 8 unlock conditions bound to a **real report file on
  disk**, optionally checked against an expected verdict. Any missing map, missing
  report, unreadable/incomplete manifest, or verdict mismatch -> **HOLD**.
- **`--mode declared` (dry-run only, non-authoritative):** accepts a booleans JSON
  but can **never** return ALLOW — its best verdict is
  `DECLARED_ONLY_NOT_AUTHORITATIVE`. This closes the "hand-written `true` unlocks a
  claim" hole.

### 2. `verify_append_only_chain.py` — payload dual verification
- New verdicts `PAYLOAD_MISSING` and `PAYLOAD_REPLACED`. When an entry declares a
  `payload_path`, the tool resolves it under the intake dir, confirms the file
  exists, and re-hashes it against `payload_sha256`. Catches a deleted or swapped
  raw payload even when the manifest chain is internally consistent. Legacy
  (payload-less) chains still verify as before.

### 3. `manual_rb_qc_schema.json` (v2) — stricter intake
- New required columns: `round_id`, `acceptance_decision` (`accepted`/`rejected`/
  `needs_review`), `caveat`.
- `reviewed_at` is now validated as **ISO-8601** (`type: iso8601`); `06/01/2026`
  and bare dates fail.
- New conditional rules: main-text tier additionally requires `round_id` +
  `acceptance_decision`; an `accepted` row may not be `screening/exploratory`
  (`forbid_value`); a `rejected` row must record a `caveat`.

### 4. `summarize_kk_residuals.py` — KK failure is decisive
- An explicit `kk_passed=false` now **always** sets `bounded_caveat_required=true`
  and verdict `KK_FAILED_BOUNDED_CAVEAT`, overriding any "within threshold"
  numeric verdict. New `kk_failed_points` counter.

### 5. `check_chi_automation_preconditions.py` — synthetic vs real
- Distinguishes a **synthetic** fixture (marker in dir path or scanned file
  contents) from a **real** evidence set. Real, fully-provisioned evidence can only
  reach `HUMAN_DEVICE_REVIEW_REQUIRED`; synthetic reaches the dry-run
  `PRECONDITIONS_MET_SYNTHETIC`. In **every** branch `enables_chi_automation=false`
  and manual EIS remains the only allowed route.

### 6. `verify_text_claims.py` (new) — number traceability
- Extracts performance numbers (number adjacent to `S cm-1`/`eV`/`ohm`/`Ω`/`cm2`/`K`,
  or preceded by `sigma`/`Ea_high`/`conductivity`/`score_v3`/`Rb`/`mu_median`) and
  requires each to match a claim-map anchor that carries **both** a `sample_id` and
  a data `path`. Untraceable numbers or forbidden wording -> FAIL.

### 7. `verify_memory_safe.py` (new) — memory pre-gate
- Rejects a memory store containing (a) forbidden claim wording, (b) unsourced
  performance numbers, or (c) fabricated experiment results (measurement-like keys
  without a `sample_id`+path provenance). Verdict `SAFE` only with zero violations.

### 8. `run_all_checks.py` (new) — one-click pre-gate
- Runs every check and returns a HOLD-biased `gate`: `DRYRUN_ALLOWED` only if every
  executed safety/QC check passed; otherwise `HOLD`. It always reports
  `v2_claims_status = "HOLD"`, `enables_chi_automation = false`, and the separate
  (default-HOLD) evidence-mode claim-unlock verdict. The gate authorizes a Phase B
  **dry-run only** — never a claim upgrade.

---

## 3. Test results

Command (from `codex/v2_engine_tools_20260601/`):

```
python -m pytest tests/ -v
```

**Result: 34 passed** (Python 3.12.7, pytest 8.4.1). Linter: **no errors**.

Coverage by hardened behavior:
- Unlock: declared-never-ALLOW; evidence none/full/missing-report/wrong-verdict/no-manifest.
- Chain: payload clean / missing / replaced; legacy clean/broken/overwrite still correct.
- Rb QC v2: ISO helper; valid v2 CSV; invalid CSV (empty round_id, non-ISO `reviewed_at`, accepted+screening forbidden).
- KK: `kk_passed=false` forces caveat even within threshold; above-threshold still caveats.
- CHI: no-dir DISABLED; synthetic PRECONDITIONS_MET_SYNTHETIC; **real -> HUMAN_DEVICE_REVIEW_REQUIRED**; needs-macro DISABLED; never enables.
- Text: clean traces; untraceable fails; forbidden wording fails; anchor-without-provenance ignored.
- Memory: safe SAFE; unsafe surfaces all three violation types.
- Aggregator: DRYRUN_ALLOWED when green (claim-unlock still HOLD); HOLD on failed chain; HOLD on unsafe memory.
- Boundary: protected prefixes declared.

---

## 4. Acceptance checklist

| Criterion | Result |
|---|---|
| pytest all pass | **Yes — 34 passed** |
| `paper/current/` modifications | **0** (git: only `??` untracked, no edits) |
| `V1.0-qianduan-mainline/` modifications | **0** (git: only `??` untracked, no edits) |
| Real experimental results generated | **No** — all fixtures `synthetic_not_real_evidence`; every output `result_like_artifact=false` |
| v2 claim generated | **No** — forbidden-wording scans built into score/text/memory checks |
| v2 still HOLD | **Yes** — unlock default HOLD; aggregator reports `v2_claims_status=HOLD`; CHI never enabled |
| Writes confined to `out/` | **Yes** — verified via CLI smoke (then cleaned) |

---

## 5. Files

**Modified:** `v2tools_common.py` (ISO-8601 + number helpers + synthetic marker),
`v2_claim_unlock_check.py`, `verify_append_only_chain.py`, `manual_rb_qc_schema.json`,
`validate_manual_rb_qc.py`, `summarize_kk_residuals.py`,
`check_chi_automation_preconditions.py`, `tests/fixtures/make_hashed_fixtures.py`,
`tests/test_v2_engine_tools.py`, the two standalone Rb QC CSV fixtures.

**Added (tools):** `verify_text_claims.py`, `verify_memory_safe.py`, `run_all_checks.py`.

**Added (fixtures, all `synthetic_not_real_evidence`):** payload chains
(`append_only_payload_{clean,missing,replaced}_*`), `kk_bundle_passed_flag_*`,
`memory_{safe,unsafe}_*`, `claim_map_*`, `text_{clean,untraceable}_*`,
`unlock_evidence_*` (manifest + 8 reports), `chi_realish_evidence_*`.

---

## 6. Boundaries reaffirmed

These tools do **not** unlock v2 claims, do **not** enable CHI automation, and emit
**no** scientific result. v2 remains **HOLD** until real signed/hash-bound approvals,
real append-only raw EIS, Stage0 gate pass, accepted manual Rb QC, score gate,
reviewed history import, Stage3 rerun claim gate, and a new frozen manifest +
presubmission pass are all satisfied on **real** data. The aggregator's
`DRYRUN_ALLOWED` authorizes only a Phase B intelligence **dry-run**, never a claim.
