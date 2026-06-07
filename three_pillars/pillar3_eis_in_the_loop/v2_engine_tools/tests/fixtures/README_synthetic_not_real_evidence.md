# Synthetic fixtures — synthetic_not_real_evidence

Every file in this directory is **synthetic_not_real_evidence**. None of it is a
real measurement, real approval, real raw EIS, or real QC record. These fixtures
exist solely to exercise the v2 codex-only validation/integrity tools.

- Do not cite anything here as scientific evidence.
- Do not copy these into `three_pillars/` (round templates / evidence) or `V1.0-qianduan-mainline/`.
- Hash-dependent fixtures (append-only chains, round approval binding) are produced
  by `make_hashed_fixtures.py` so the embedded SHA-256 values are internally correct.
