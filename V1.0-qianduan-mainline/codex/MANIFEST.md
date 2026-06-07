# Project-Local Codex Manifest

Current status date: 2026-06-07

This project-local `codex/` folder stores read-only audit snapshots produced by
`V1.0-qianduan-mainline/scripts/audit_mainline.py`. It is NOT part of the active
Stage0 / Stage1 / Stage2 / Stage3 runtime path; nothing in the pipeline reads
from here.

## Retention policy

Only the latest `<YYYYMMDD_HHMMSS>_mainline_audit.{json,md}` pair is retained.
Older snapshots and the historical `archive/20260518_deep_audit_runs/` deep-audit
exports have been pruned during the 2026-06 cleanup, since their results have
been superseded by the live `stage3_mechanism/outputs/verification/` audit runs.

To regenerate a fresh snapshot, run from the project root:

```
python V1.0-qianduan-mainline/scripts/audit_mainline.py
```
