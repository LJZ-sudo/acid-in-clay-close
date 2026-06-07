# Stage2 Exports Manifest

Current status date: 2026-06-07

This directory is the current canonical Stage2 output root consumed by Stage3 strict real mode.

Latest verified run:

- Command: `python stage2_statistics\main_agent.py stage2_statistics\data\s8_input.csv`
- Run time: 2026-06-07 15:43 local
- Input: `stage2_statistics/data/s8_input.csv`
- Input SHA256: `21f3caad64ba3cf7...` (see `data/s8_input.manifest.json` for full value)
- `stage3_seed.json` schema version: `0.2.0`
- `stage3_seed.json` seed id: `SEED-1ad04c55`
- `stage3_ready`: `true`
- Stage3 seed SHA256: `4edbd1366e75b41c7432825624545024f1468cbf08eca4d554689f6cf9bcea22`
- Sample summaries: 40
- Segment fits: 158
- Evidence units: 13

Notes:

- `s8_evidence_atlas.json` remains for backward compatibility (V1 track); Stage3 strict mode does NOT consume it. The `--allow-legacy-atlas` fallback in Stage3 adapter is kept for diagnostics only.
- `stage3_seed.json` is the canonical Stage2 -> Stage3 contract (V2 track).
- `visualization_manifest.json` is expected even when only a subset of figures is generated.
- Re-running `main_agent.py` regenerates `stage3_seed.json` and `s8_evidence_atlas.json`. Update this MANIFEST in the same commit to keep SHA256 in sync.
