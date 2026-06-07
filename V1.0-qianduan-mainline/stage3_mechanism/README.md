# Stage3 Mechanism: Evidence-Constrained Material Reasoning

Current status date: 2026-05-19

Stage3 consumes the canonical Stage2 V2 seed and turns S8 retrospective
evidence into mechanism hypotheses, design principles, candidate material
families, ranked instances, validation binding, and claim audit artifacts.

Stage3 is separate from the attapulgite AiCE Stage0/Stage1 BO history. It can
produce transfer-validation ideas and campaign seeds, but it must not write S8
retrospective data into the attapulgite real history database.

## Current Input Contract

Real mode should consume:

```text
stage2_statistics/exports/stage3_seed.json
```

The resolver selects inputs in this order:

1. CLI `--stage2-output-dir`
2. `STAGE3_STAGE2_OUTPUT_DIR`
3. `stage2_statistics/exports`
4. `stage3_mechanism/input`
5. legacy `stage3_mechanism/data/input`

Strict real mode requires a same-directory `stage3_seed.json`. Legacy atlas
fallback is disabled unless `--allow-legacy-atlas` is passed explicitly.

## Main Entrypoint

```powershell
cd D:\acid-in-clay-close\V1.0-qianduan-mainline
$env:PYTHONPATH='stage3_mechanism/src'
python -m s8_stage3.orchestrator.run_stage3 `
  --mode real `
  --stage2-output-dir stage2_statistics/exports `
  --output-dir stage3_mechanism/outputs/verification/current_stage3_run
```

Always use an explicit `--output-dir` for verification or production runs.
`outputs/stage3/` is now only an example or archived run location, not an
implicit global truth.

## Executable Step Chain

The current default chain starts at S03:

```text
Stage3SeedBundle
-> seed_sanitizer
-> S03 evidence_builder
-> S04 hypothesis_generator
-> S05 literature_scout_mechanism
-> S06 mechanism_arbiter
-> S06b design_principle_extractor
-> S07 descriptor_extractor
-> S08 literature_scout_materials
-> S09 candidate_family_generator
-> S10 instance_ranker
-> S12 prospective_registry
-> S13 validation_binder
-> S14 claim_auditor
-> S11 report_compiler
```

The step order is defined in `src/s8_stage3/orchestrator/state_machine.py`.
`S01 Data Auditor` and `S02 Segment Builder` remain available as explicit
legacy/source-audit helpers, but the default real pipeline does not call them.

## Current Outputs

Outputs are written relative to the selected `--output-dir`:

- `00_sanitizer_digest.json`
- `00_seed_real/seed_bundle_real.json`
- `00_seed_real/real_seed_diagnostics.json`
- `01_evidence/evidence_cards.json`
- `02_hypotheses/hypothesis_board.json`
- `03_literature_mechanism/literature_cards_mechanism.json`
- `04_mechanism/mechanism_card.json`
- `04b_design_principles/design_principles.json`
- `05_descriptors/descriptor_sheet.json`
- `06_literature_materials/literature_cards_materials.json`
- `07_material_families/material_families.json`
- `08_material_instances/material_instances.json`
- `09_ranking/ranked_top_list.json`
- `09_ranking/ranking_robustness_v2.json`
- `10_reports/stage3_report.json`
- `10_reports/stage3_report.md`
- `11_candidate_registry/prospective_candidates.json`
- `12_validation_binding/validation_binding_report.json`
- `13_claim_audit/claim_audit_report.json`
- `run_manifest.json`
- `run_cost_summary.json`

`run_manifest.json` records the Stage2 input directory, seed path, seed hash,
selected steps, output directory, strict/legacy input mode, robustness summary,
and adapter warning count.

## Validation Feedback

Optional Stage3 transfer-validation feedback should use:

```text
stage3_mechanism/data/validation/experimental_feedback.json
```

S13 reads explicit JSON feedback first and keeps CSV fallback for older
validation data. S13/S14 may use validation evidence to bind or gate claims, but
they do not modify S09/S10/S12 candidate artifacts and do not write Stage1
attapulgite history.

## Claim and Robustness Rules

- S03 uses Stage2 V2 `evidence_units` as the authoritative evidence source.
- S10 writes ranking robustness as an audit artifact; it does not rewrite the
  ranked top list.
- S14 gates claim strength using validation timing and robustness. No feedback
  means hypothesis/candidate wording only. Retrospective feedback cannot become
  prospective-validation wording.

## Tests

```powershell
cd D:\acid-in-clay-close\V1.0-qianduan-mainline
$env:PYTHONPATH='stage3_mechanism/src'
python -m pytest -q stage3_mechanism\tests
```

## Maintenance Notes

- Do not place material answers such as lotus starch, PVA, or attapulgite into
  upstream prompts before the allowed candidate-generation stage.
- Do not mix legacy atlas files with a different V2 seed directory.
- Do not treat historical `outputs/stage3/` reports as current unless the run
  manifest proves they consumed the current Stage2 seed.
- Update this README when the executable step list, input contract, or claim
  gate changes.
