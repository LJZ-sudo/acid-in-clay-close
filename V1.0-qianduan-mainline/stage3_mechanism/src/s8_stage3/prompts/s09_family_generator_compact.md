# S09 Compact Candidate Family Generator

You convert mechanism descriptors and S08 component-level claims into audit-ready material candidates.

Return JSON only. Match this top-level shape:

```json
{"families": [], "instances": []}
```

Use the input fields:
- `descriptors`: mechanism descriptor ids and short text.
- `descriptor_claim_pool`: atomic evidence items with `component`, `descriptor_id`, `paper_id`, `anchor`, and `claim`.
- `generation_contract`: hard output limits.
- `system_context`, if present, especially the low-temperature window.

Rules:
- Generate exactly 3 families and exactly 5 instances.
- Family names must be abstract archetypes, not concrete substance names.
- Each family needs `family_id`, `family_name`, `family_description`, `descriptor_match`, and `literature_support_card_ids`.
- Each instance needs `instance_id`, `family_id`, `instance_name`, `composition_description`, `components`, `expected_properties`, `risk_flags`, `combination_novelty`, `element_evidence`, and `novelty_rationale`.
- At least 3 instances must be `novel_combination`; at most 1 may be `exact_match`.
- Cite only `paper_id` values present in `descriptor_claim_pool`.
- For each meaningful component, add one `element_evidence` entry. Put descriptor ids only when supported by a matching or clearly analogous claim.
- Prefer cold-side-operable routes for roughly 182-299 K operation: bound-water hosts, OH-rich polymers/biopolymers, clays, retained phosphoric acid, plasticised or anti-freeze motifs.
- Include one quaternary synergy instance if support exists: biopolymer or chitosan/starch host + PVA/PVP/PAA-like film former + 1-D fibrous/tubular clay + phosphoric acid.
- Keep prose concise: one sentence for family descriptions, one sentence for analog reasons, and no more than 3 expected properties per instance.

JSON field details:
- `descriptor_match`: array of strings like `"D1: reason"`.
- `expected_properties`: array of strings like `"cold_window: plausible bound-water continuity"`.
- `components`: array of concrete substance names.
- `element_evidence[].descriptor_satisfied`: array of descriptor ids.
- `element_evidence[].analog_paper_ids`: array of cited S08 paper ids.
- `novelty_rationale`: 1-3 concise sentences explaining why the combination is novel or why an exact match is retained as a control.
