# BO+LLM v2 locked package

This package locks the prospective BO+LLM v2 execution protocol without changing the current Stage1 history.

- Protocol lock: `protocol_lock.json`
- Primary history: `history_primary_t2_t8.json`
- Campaign scaffold: `attapulgite_aice_v2_locked_campaign.json`
- Round templates: `prospective_round_templates.json`

Main rule: T1 is retained in full audit and excluded from the primary protocol-consistent analysis. New v2 results must be written append-only into the round directories before they are used in figures or manuscript claims.
