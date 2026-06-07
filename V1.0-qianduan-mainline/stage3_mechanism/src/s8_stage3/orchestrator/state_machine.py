"""Stage3 step order and dependency helpers.

The current executable mainline starts from the canonical Stage2 seed and runs
S03 onward. S01/S02 source-audit helpers remain in the codebase, but they are
not part of the default executable chain.
"""
from __future__ import annotations


EXECUTABLE_STEPS: list[str] = [
    "s03_evidence_builder",
    "s04_hypothesis_generator",
    "s05_literature_scout_mechanism",
    "s06_mechanism_arbiter",
    "s06b_design_principle_extractor",
    "s07_descriptor_extractor",
    "s08_literature_scout_materials",
    "s09_candidate_family_generator",
    "s10_instance_ranker",
    "s12_prospective_registry",
    "s13_validation_binder",
    "s14_claim_auditor",
    "s11_report_compiler",
]

# Backward-compatible name for existing imports. It intentionally mirrors the
# executable S03+ chain so there is one current source of truth.
ALL_STEPS: list[str] = EXECUTABLE_STEPS.copy()


STEP_DEPENDENCIES: dict[str, list[str]] = {
    "s03_evidence_builder": [],
    "s04_hypothesis_generator": ["s03_evidence_builder"],
    "s05_literature_scout_mechanism": ["s04_hypothesis_generator"],
    "s06_mechanism_arbiter": ["s03_evidence_builder", "s05_literature_scout_mechanism"],
    "s06b_design_principle_extractor": ["s06_mechanism_arbiter"],
    "s07_descriptor_extractor": ["s06b_design_principle_extractor"],
    "s08_literature_scout_materials": ["s07_descriptor_extractor"],
    "s09_candidate_family_generator": [
        "s06b_design_principle_extractor",
        "s07_descriptor_extractor",
        "s08_literature_scout_materials",
    ],
    "s10_instance_ranker": ["s09_candidate_family_generator", "s06_mechanism_arbiter"],
    "s12_prospective_registry": ["s10_instance_ranker"],
    "s13_validation_binder": ["s12_prospective_registry"],
    "s14_claim_auditor": ["s12_prospective_registry", "s13_validation_binder", "s10_instance_ranker"],
    "s11_report_compiler": ["s10_instance_ranker", "s14_claim_auditor"],
}


def steps_until(until_step: str) -> list[str]:
    """Return executable Stage3 steps through ``until_step`` (inclusive)."""
    if not until_step:
        return EXECUTABLE_STEPS.copy()
    for i, step in enumerate(EXECUTABLE_STEPS):
        if until_step in step or step == until_step:
            return EXECUTABLE_STEPS[: i + 1]
    return EXECUTABLE_STEPS.copy()


def validate_step_order(steps: list[str]) -> list[str]:
    """Return dependency-order violations for a candidate step list."""
    seen: set[str] = set()
    violations: list[str] = []
    for step in steps:
        for dep in STEP_DEPENDENCIES.get(step, []):
            if dep not in seen:
                violations.append(
                    f"Step '{step}' requires '{dep}' but it has not been scheduled before."
                )
        seen.add(step)
    return violations
