# Stage2 Statistics: S8 Evidence Atlas

Current status date: 2026-05-19

Stage2 converts the S8 retrospective acid-in-clay dataset into the canonical
evidence contract consumed by Stage3. It is not part of the attapulgite AiCE
Stage0/Stage1 BO training loop.

## Current Role

- Source system: S8 sepiolite retrospective evidence.
- Source mode: retrospective.
- Primary input: `data/s8_input.csv`.
- Canonical Stage2 -> Stage3 contract: `exports/stage3_seed.json`.
- Backward-compatible export: `exports/s8_evidence_atlas.json`.

`stage3_seed.json` is the authoritative handoff artifact. The legacy atlas and
CSV files are retained for diagnostics and historical compatibility, but Stage3
strict real mode should consume the V2 seed.

## Main Entrypoint

```powershell
cd D:\acid-in-clay-close\V1.0-qianduan-mainline
python stage2_statistics\main_agent.py stage2_statistics\data\s8_input.csv
```

By default the pipeline writes to:

```text
stage2_statistics/exports/
```

Use `--output-dir` only when deliberately writing an isolated verification run.

## Current Outputs

The current default export set is:

- `stage3_seed.json`: canonical V2 seed for Stage3.
- `evidence_units.json`: V2 evidence units.
- `s8_evidence_atlas.json`: legacy-compatible evidence atlas.
- `data_profile.json`: input profile and data coverage.
- `execution_plan.json`: enabled analysis modules.
- `visualization_manifest.json`: figure manifest; written as `{}` when no plots are emitted.
- `run_summary.json` / `run_summary.md`: run-level audit summary.
- `excluded_samples.csv` / `excluded_samples.json`: rows excluded during quality filtering.

The current canonical seed is expected to include:

- `schema_version`
- `source_system="s8_reference"`
- `source_mode="retrospective"`
- `input_files`
- `input_hashes`
- `stage3_ready`
- `stage3_blocking_reasons`
- `sample_summary`
- `segment_fits`
- `evidence_units`

## Contract Rules

- Missing `R` or `N` must be reflected in `quality_flags` and block Stage3 readiness.
- Stage2 may still write audit artifacts when `stage3_ready=false`.
- Stage3 strict real mode must reject a non-ready seed.
- S8 evidence is a mother-system reference, not attapulgite BO training data.

## Tests

```powershell
cd D:\acid-in-clay-close\V1.0-qianduan-mainline
python -m pytest -q tests\test_stage2_current_seed_contract.py stage3_mechanism\tests\test_stage2_stage3_contracts.py
```

## Maintenance Notes

- Treat `exports/stage3_seed.json` as the current truth for Stage3 input.
- Do not delete raw `data/s8_input.csv` or historical exports; archive old
  generated outputs into dated folders when they are no longer current.
- Update this README when the Stage2 -> Stage3 schema changes.
