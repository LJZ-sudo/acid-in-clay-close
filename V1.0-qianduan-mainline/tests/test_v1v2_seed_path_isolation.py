# -*- coding: utf-8 -*-
"""Tier2 (issue 14): V1/V2 reconciliation = keep V1 OFF the canonical seed path.

Decision (documented in stage2_statistics/main_agent.py and
codex/remediation_tier2/04_stage1_term_and_plots_summary.md):
  * V2 (`core/stage3_seed_builder.py`) is the CANONICAL Stage2->Stage3 interface
    that produces `exports/stage3_seed.json`.
  * V1 specialists (`specialists/model_competitor.py`,
    `specialists/morphology_expert.py`, ...) are DIAGNOSTIC-ONLY. Their evidence
    is never consumed by the seed builder.

This guard prevents a future edit from silently re-coupling the V1 specialist
track into the frozen canonical seed (which would make the frozen
stage3_seed.json non-reproducible from V2 alone).
"""
from __future__ import annotations

import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SEED_BUILDER = PROJECT_ROOT / "stage2_statistics" / "core" / "stage3_seed_builder.py"


def _imported_module_roots(py_file: Path):
    tree = ast.parse(py_file.read_text(encoding="utf-8"))
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            mod = (node.module or "")
            # record both the dotted module and any "specialists" segment
            roots.add(mod)
            for part in mod.split("."):
                roots.add(part)
    return roots


def test_seed_builder_does_not_import_v1_specialists():
    assert SEED_BUILDER.exists()
    roots = _imported_module_roots(SEED_BUILDER)
    assert "specialists" not in roots, (
        "stage3_seed_builder must not import the V1 specialists track; "
        "V2 seed is canonical and V1 is diagnostic-only."
    )


def test_seed_builder_imports_only_v2_core_modules():
    # Sanity: the seed builder pulls from schema_v2 / strength_rules (V2 core),
    # not from any *_expert / *_competitor V1 module name.
    src = SEED_BUILDER.read_text(encoding="utf-8")
    for forbidden in ("model_competitor", "morphology_expert", "thermo_specialist"):
        assert f"import {forbidden}" not in src
        assert f"from .{forbidden}" not in src
