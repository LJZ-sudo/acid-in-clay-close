# BO+LLM v2 locked campaign plan

Date: 2026-05-27

Campaign name: `attapulgite_aice_v2_locked`

## Position in the paper

BO+LLM v2 是执行能力证明，不是 LRS 发现证据。主文写法应固定为：

> A locked BO+LLM extension from protocol-consistent attapulgite history prospectively tested whether the execution layer could reproduce or expand the conductivity/Ea Pareto front.

禁止写法：

- BO+LLM discovered LRS.
- The BO campaign found the universal best condition.
- The original campaign optimized the transfer material.

## T1 handling

T1 保留在 full as-run audit 中，但从 primary protocol-consistent optimization analysis 中排除。

理由：T1 的制备记录使用 `1.65 g attapulgite`，而 T2-T8 使用 `1 g attapulgite`。这说明 T1 是 clay-content constraint 固定前的 pilot/out-of-protocol 点。该排除规则必须在 v2 新实验开始前锁定，不能在看见新结果后改变。

## Locked primary history

Primary history: T2-T8 only.

Design variables:

- `R`: acid/water molar ratio.
- `N`: liquid/clay mass ratio.

Primary endpoint:

- Pareto improvement over `sigma_RT`, `Ea_high`, and `ea_low_excess`.

Secondary scalar score:

```text
score_v3 = log10(sigma_RT) - 1.0 * Ea_high - 0.2 * ea_low_excess
```

The old conservative score remains only for audit continuity.

## Minimum prospective rounds

| round | target | purpose | status before experiment |
| --- | --- | --- | --- |
| v2-R1 | `R=0.50, N=1.20` repeat | reproduce T5 highest conductivity endpoint | locked repeat |
| v2-R2 | `R=0.20, N=1.10` repeat | reproduce T7 lowest `Ea_high` endpoint | locked repeat |
| v2-R3 | one raw BO suggestion from frozen T2-T8 history | test optimizer-only recommendation | freeze before synthesis |
| v2-R4 | one LLM-adjusted recommendation after physics guardrail | test BO+LLM execution path | freeze before synthesis |

## Required round record

Every prospective round must save:

1. history before round;
2. raw BO suggestion;
3. LLM adjustment and reason;
4. human approval;
5. recipe and sample ID;
6. raw EIS path;
7. Stage0 output path;
8. manual/auto Rb QC;
9. `sigma_RT`, `Ea_high`, `ea_low_excess`, `score_v3`, Pareto status;
10. history after round.

Suggested folder:

```text
three_pillars/pillar3_eis_in_the_loop/bo_v2_locked/
```

Suggested per-round file names:

```text
round_01_history_before.json
round_01_raw_bo_suggestion.json
round_01_llm_guardrail.json
round_01_human_approval.md
round_01_recipe.md
round_01_stage0_result.json
round_01_manual_rb_qc.csv
round_01_score.json
round_01_history_after.json
```

## Success interpretation

Strongest case: a new point extends the Pareto front or reproducibly confirms the T5/T7 endpoints while following the locked protocol.

Acceptable case: no new Pareto point, but the campaign produces complete prospective execution records and a defensible trade-off map.

Weak case: incomplete traceability or failed repeats. Then BO+LLM remains supplementary execution proof only.
