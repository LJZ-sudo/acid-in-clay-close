# Stage3 Claim Audit Report

- **run_id**: `stage3-b9dd31a5a1`
- **discovery_mode**: `broad_literature_pool_selection`
- **final_audit**: `False`

## Claim Ladder

### [PASS] `closed_loop_source_system`

**Allowed claim**: Acid-in-clay is the closed-loop mother system and underwent prospective BO-driven optimisation over multiple real rounds.

- current status: closed_loop_validity=prospective_real, n_rounds=6, metrics=C:\Users\JZ\Desktop\paper\acid-in-clay-close\V1.0-qianduan-mainline\stage1_optimization\output\attapulgite_aice\closed_loop_metrics.json -> supported.
- required evidence:
  - stage1_optimization/output/attapulgite_aice/closed_loop_metrics.json with closed_loop_validity=prospective_real and n_closed_loop_rounds>=3
- forbidden overclaim: Do not call retrospective_replay or virtual_oracle runs a 'closed-loop optimisation'.

### [PASS] `mechanism_discovery`

**Allowed claim**: LLM-generated mechanism hypotheses, constrained by Stage2 evidence (V2 seed), yielded a winning mechanism describing confined vs bulk proton populations and an overfilling crossover.

- current status: mechanism_card=present, v2_evidence_cards=13.
- required evidence:
  - 04_mechanism/mechanism_card.json
  - 01_evidence/evidence_cards.json containing EvidenceUnitV2-derived cards
- forbidden overclaim: Do not say 'LLM proved the mechanism'. LLMs generate and arbitrate hypotheses; proof requires experiment + statistics.
- caveats:
  - Mechanism claim must always be hedged as 'hypothesised/supported'.

### [PASS] `llm_transfer_candidate`

**Allowed claim**: LLM selected and recombined lotus-root-starch evidence from a broad biomass / polymer / clay literature pool.

- current status: discovery_mode=broad_literature_pool_selection, claim_strength=moderate, n_candidates=5, source_term_audit_ok=True (source=09_ranking/candidate_audit.json), candidate_audit_quality_ok=True, ranking_stability_class=stable, top1_stability=0.995, top3_jaccard=0.81, bad_citation_candidates=[], low_coverage_candidates=[].
- required evidence:
  - 11_candidate_registry/prospective_candidates.json
  - 09_ranking/candidate_audit.json and source_term_audit.json with discovery-mode consistent source-term status
  - 09_ranking/ranking_robustness_v2.json with stable or moderately_stable ranking robustness
- forbidden overclaim: Do not escalate beyond the discovery_mode allowance. broad_literature_pool_selection → 'selected / recombined', NOT 'independently discovered'.
- caveats:
  - final_audit=False — cached LLM responses may have been reused; do not make final publication claims from this run.

### [TODO] `prospective_validation`

**Allowed claim**: LLM-ranked candidates were frozen before experiment and subsequently validated by wide-temperature EIS measurements.

- current status: n_prospective_links=0, n_mixed_links=0, n_retrospective_links=0.
- required evidence:
  - validation_binding_report.json with >=1 link classified as prospective_validation
  - validation_timing=prospective and validation date > registry.preregistered_at
- forbidden overclaim: If experiments preceded registry.preregistered_at, call it 'retrospective validation' only.
- caveats:
  - No prospective validation yet; only retrospective/no bindings.

### [TODO] `retrospective_validation`

**Allowed claim**: The biopolymer / PVA / 1D-clay / H3PO4 motif predicted by the evidence-constrained LLM pipeline is consistent with prior experimental measurements on the three biopolymer systems (lotus / corn starch / chitosan).

- current status: n_retrospective_links=0, n_mixed_links=0.
- required evidence:
  - validation_binding_report.json with >=1 link classified as retrospective_validation or mixed_validation
- forbidden overclaim: Do not present retrospective_validation as 'prospective discovery'.
- caveats:
  - If any experiment time > registry.preregistered_at, prefer prospective_validation for that specific candidate.

## Recommended Wording

- Core claim wording tied to discovery_mode=broad_literature_pool_selection: "LLM selected and recombined lotus-root-starch evidence from a broad biomass / polymer / clay literature pool."
- Ranking robustness wording gate: Single-winner wording is allowed with audit caveats.

## Inputs Digest

- `eis_overclaim_findings_count`: 0
- `eis_overclaim_strict`: 0
- `source_term_audit.json`: 81bd7a2c8f213a33...
- `candidate_audit.json`: 41122a254b463d6f...
- `ranking_robustness_v2.json`: 56c148bdaa041797...
- `evidence_cards.json`: 35c9fa83ec8cd284...
- `prospective_candidates.json`: 1e4fcc76392eb292...
- `validation_binding_report.json`: 54b6e33ad7af1b4b...
- `closed_loop_metrics.json`: 7be24c4f3cfd2c7c...
- `closed_loop_metrics_path`: C:\Users\JZ\Desk...
- `audit_built_at`: 2026-06-07T09:48:21Z
