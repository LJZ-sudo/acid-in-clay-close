# BO v2 R4 LLM Guardrail Request

Status: request only, not a decision and not an experimental result.

Use the frozen T2-T8 primary history and the R3 raw BO candidate set to choose one R4 recipe. The guardrail should either accept the raw BO suggestion or adjust it to a nearby physically safer candidate.

## Raw BO Suggestion

- R: `0.64`
- N: `1.04`
- predicted score_v3 mean: `-1.42256821`
- predicted score_v3 std: `0.15851333`
- expected improvement scaled: `0.5771460308`

## Guardrail Rules

- Keep within locked bounds: R in [0, 1.04], N in [0.5, 1.3].
- Prefer candidates that do not simply duplicate T5 (`R=0.50,N=1.20`) or T7 (`R=0.20,N=1.10`), because those are already locked repeats.
- Watch high-N risk: N approaching 1.3 can indicate bulk acid or channel overflow risk.
- Watch high-R risk: R approaching 1.04 can indicate low-water pyrophosphate/dehydration/crystallization risk.
- Preserve the paper boundary: this is a recipe decision only, not evidence of performance.

## Required Response JSON

Fill `llm_guardrail_response_template.json` and save the completed decision as `llm_guardrail.json`.
