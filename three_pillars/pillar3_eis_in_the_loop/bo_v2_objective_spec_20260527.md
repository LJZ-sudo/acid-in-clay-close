# Locked objective specification for `attapulgite_aice_v2_locked`

Date locked: 2026-05-27

## Analysis sets

`full_as_run_audit`: T1-T8, preserving all historical trials and original execution chronology.

`primary_protocol_consistent_set`: T2-T8, excluding T1 because the clay content was not fixed to the later `1 g attapulgite` protocol.

No new v2 result may change this definition.

## Variables

| symbol | meaning | direction |
| --- | --- | --- |
| `R` | acid/water molar ratio | design variable |
| `N` | liquid/clay mass ratio | design variable |
| `sigma_RT` | near-room-temperature proton conductivity in S cm^-1 | maximize |
| `Ea_high` | apparent activation energy in the high-temperature segment, eV | minimize |
| `ea_low_excess` | low-temperature degradation penalty, eV | minimize |

## Pareto rule

A new point is a Pareto improvement if no prior point in the primary protocol-consistent set has:

- `sigma_RT` greater than or equal to the new point,
- `Ea_high` less than or equal to the new point,
- `ea_low_excess` less than or equal to the new point,

with at least one strict improvement.

## Secondary scalar score

```text
score_v3 = log10(sigma_RT) - 1.0 * Ea_high - 0.2 * ea_low_excess
```

Use `score_v3` only as a secondary scalar summary. The paper should prioritize the Pareto interpretation because the trade-off between conductivity, high-segment barrier and low-temperature degradation is physically meaningful.

## Locked statements

Allowed:

- The v2 campaign prospectively tests whether the execution layer can reproduce or expand the conductivity/Ea Pareto front.
- T1 is retained in the full audit but excluded from the primary protocol-consistent analysis.
- The old combined score did not establish a completed optimization claim.

Not allowed:

- BO+LLM discovered LRS.
- BO+LLM proved a universal optimum.
- A post hoc score change turns the historical campaign into a successful closed-loop discovery.

## Data products to generate after each v2 round

| artifact | required fields |
| --- | --- |
| `history_before` | trial IDs, R, N, raw metric values, excluded flags |
| `raw_bo_suggestion` | optimizer state, acquisition function, proposed R/N |
| `llm_guardrail` | accepted/adjusted R/N, reason, physical risks |
| `human_approval` | approval time, approver, final recipe |
| `stage0_result` | raw EIS path, processing code version, conductivity table, segmented Arrhenius metrics |
| `manual_rb_qc` | manual Rb, auto Rb, selected Rb, difference, QC tier |
| `score` | `sigma_RT`, `Ea_high`, `ea_low_excess`, `score_v3`, Pareto status |
| `history_after` | append-only campaign state |
