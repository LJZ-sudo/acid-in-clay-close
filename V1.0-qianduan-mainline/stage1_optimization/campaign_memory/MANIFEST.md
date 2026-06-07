# Stage1 Campaign Memory Manifest

Current status date: 2026-06-07

Campaign memory policy:

- `history_db_attapulgite.json`: the **only** active history database. The current
  backend campaign `attapulgite_aice_campaign` writes here.
- The `MemoryManager` enforces campaign-name consistency and sample/hash
  deduplication before appending trials.

History of related artifacts:

- The retired S8/sepiolite mother-system history (the previous `history_db.json` /
  20 retrospective trials) and its campaign config have been migrated out of
  `stage1_optimization/` and archived under
  `three_pillars/pillar1_transfer_agent/s8_acid_in_clay_mother_system/` on
  2026-06-07. They are now Pillar 1 transfer-agent evidence, not Stage1 BO
  training data, and must not be mixed back into the attapulgite history.
- Older `archive/20260518_legacy_backups/` and `backups/` subdirectories (which
  held S8-era manual snapshots) were deleted in the same cleanup; git history
  preserves them if recovery is ever needed.
