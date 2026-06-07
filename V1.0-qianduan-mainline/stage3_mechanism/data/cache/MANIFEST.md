# Stage3 Cache Manifest

Current status date: 2026-06-07

Cache directory policy:

- `current/`: active cache root used by Stage3 by default. `Stage3Settings.cache_dir` resolves here unless `STAGE3_CACHE_DIR` is explicitly set.
- `current/llm_cache/`: active LLM response cache for live LLM runs (keyed by prompt/model SHA). Contains raw snapshot mirrors under `_raw_snapshots/` for debugging.
- `current/literature_cache/`: active literature query cache for API/hybrid literature runs.

The pre-convergence archive cache was cleared in the [2026-06-07] cleanup; the recommended pattern for reproducible audit runs remains:

```powershell
$env:STAGE3_ENABLE_CACHE='false'
```

or point `STAGE3_CACHE_DIR` to a deliberate, run-specific cache root rather than this shared `current/` cache.
