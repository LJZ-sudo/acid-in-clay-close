# S09 baseline vs evidence-based (synthetic dry-run)

> dry-run only, no scientific claim, v2 remains HOLD. All inputs are `synthetic_not_real_evidence`. No real candidate, no real measurement.

This compares the two S09 generation paths on the **same synthetic survey**. It
proves the new explicit switch routes generation correctly. It makes NO claim
that either candidate set is scientifically meaningful.

| aspect | baseline (flag OFF) | evidence-based (flag ON) |
|---|---|---|
| `s09_evidence_based_generation` | `False` | `True` |
| `generation_mode` | `deterministic_from_d4` | `evidence_based_descriptor_match` |
| `n_instances` | 5 | 3 |
| `instance_ids` | ['I1', 'I2', 'I3', 'I4', 'I5'] | ['I1', 'I2', 'I3'] |
| `audit_ok` | True | True |

## Interpretation (bounded)
- Default (`flag OFF`) keeps the **frozen** `deterministic_from_d4` path; this is
  unchanged from the frozen baseline.
- Explicit opt-in (`flag ON`) routes to `evidence_based_descriptor_match`, which
  builds candidates by descriptor coverage over the synthetic claim pool.
- The difference here is **mechanism/plumbing only**. No scientific superiority is
  claimed for either set. v2 remains HOLD.
