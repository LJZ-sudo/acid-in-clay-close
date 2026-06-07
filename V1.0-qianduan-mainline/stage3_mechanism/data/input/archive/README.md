# Archived Stage3 Input Snapshots

Historical input snapshots retained for reproducibility audit only. These are
NOT consumed by the current pipeline.

- `s8_evidence_atlas_20260413_48units.json`: V1 atlas snapshot from 2026-04-13
  (48 evidence units, sha256 `6f4da680...`). The current V1 atlas in
  `stage2_statistics/exports/s8_evidence_atlas.json` has evolved to 56 units.
  Retained as the point-in-time atlas used by the early D2 / pre-L+D4 runs
  referenced in `CHANGELOG.md`.

The current canonical Stage3 input is `stage2_statistics/exports/stage3_seed.json`
(V2 contract). Atlas files are only consumed by the legacy `--allow-legacy-atlas`
diagnostic mode and resolve via `adapters/input_resolver.py` priority chain;
this archive entry is at priority 5 and is never reached when priority 3
(`stage2_statistics/exports/`) is populated.
