# BO v2 Approval Signing Checklist

Status: `PASS_READY_FOR_HUMAN_SIGNING`
Ready to sign: `4`
Signed and ready for start gate: `0`

| round | signing status | form | signed output | blocking item |
| --- | --- | --- | --- | --- |
| `v2-R1` | `READY_FOR_HUMAN_SIGNING` | `three_pillars/pillar3_eis_in_the_loop/bo_v2_locked/round_01_v2-R1_locked_repeat/approval_form_to_sign.md` | `three_pillars/pillar3_eis_in_the_loop/bo_v2_locked/round_01_v2-R1_locked_repeat/human_approval.md` | human_approval.md missing |
| `v2-R2` | `READY_FOR_HUMAN_SIGNING` | `three_pillars/pillar3_eis_in_the_loop/bo_v2_locked/round_02_v2-R2_locked_repeat/approval_form_to_sign.md` | `three_pillars/pillar3_eis_in_the_loop/bo_v2_locked/round_02_v2-R2_locked_repeat/human_approval.md` | human_approval.md missing |
| `v2-R3` | `READY_FOR_HUMAN_SIGNING` | `three_pillars/pillar3_eis_in_the_loop/bo_v2_locked/round_03_v2-R3_raw_bo_suggestion/approval_form_to_sign.md` | `three_pillars/pillar3_eis_in_the_loop/bo_v2_locked/round_03_v2-R3_raw_bo_suggestion/human_approval.md` | human_approval.md missing |
| `v2-R4` | `READY_FOR_HUMAN_SIGNING` | `three_pillars/pillar3_eis_in_the_loop/bo_v2_locked/round_04_v2-R4_llm_guardrail_adjusted/approval_form_to_sign.md` | `three_pillars/pillar3_eis_in_the_loop/bo_v2_locked/round_04_v2-R4_llm_guardrail_adjusted/human_approval.md` | human_approval.md missing |

## Required Operator Actions

1. Open each `approval_form_to_sign.md`; do not edit locked recipe or preflight files after reviewing hashes.
2. Check all required boxes only after human review.
3. Fill `Approved by:` and `Date:` using `YYYY-MM-DD`.
4. Save the completed copy as `human_approval.md` in the same round directory.
5. Re-run approval/start gates before EIS. Manual EIS is allowed; automated CHI remains blocked without macrotest/dummy-cell evidence.

This checklist prepares human signing only. It does not sign approval files, create raw EIS data, start CHI automation, run Stage0, score results, import history, or upgrade manuscript claims.
