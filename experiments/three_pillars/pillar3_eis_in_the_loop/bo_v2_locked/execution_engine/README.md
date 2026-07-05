# BO v2 Prospective Execution Engine

This directory turns the BO+LLM v2 lock into an append-only execution engine. It defines the state machine, queue, result intake schema, and per-round templates. No prospective result is considered valid until the required non-template files are filled and QC passes.
