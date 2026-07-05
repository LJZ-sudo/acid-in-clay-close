# OpenAlex: offline snapshot + real-run plan

> dry-run only, no scientific claim, v2 remains HOLD. The snapshot below is `synthetic_not_real_evidence` and MUST NOT be cited as literature.

## What ran in this dry-run
- S08 `api` mode was exercised with an **offline** `FakeOpenAlexProvider`
  (`fake_openalex_provider.py`). No network call was made (`network_used=false`).
- The provider returns a small, fixed pool of clearly-synthetic records whose
  titles/abstracts are stamped `synthetic_not_real_evidence`. These are NOT real papers.

## Offline snapshot template (synthetic)
```
SYN-W001  OH-rich biopolymer host for proton transport   (synthetic)
SYN-W002  One-dimensional clay confinement of acid phases (synthetic)
SYN-W003  Retained phosphoric acid as a mobile proton carrier (synthetic)
```

## Plan for a REAL OpenAlex run (future, human-gated)
1. Set `STAGE3_OPENALEX_MAILTO` to a real contact (polite pool).
2. Run S08 with `--literature-mode api` (live `OpenAlexProvider`).
3. Persist the raw API response as a dated snapshot under a NEW codex dir.
4. **Manual curation required**: a human reviews each returned paper, records a
   curation decision (keep/drop/uncertain) in a CSV with reviewer + timestamp,
   before any card informs a claim.
5. Single provider only for now (OpenAlex). Do NOT imply Semantic Scholar /
   Crossref / Scopus multi-source; those providers do not exist yet.

## Boundary
OpenAlex output is a discovery aid, never evidence by itself. No "OpenAlex
validated" claim is permitted. v2 remains HOLD.
