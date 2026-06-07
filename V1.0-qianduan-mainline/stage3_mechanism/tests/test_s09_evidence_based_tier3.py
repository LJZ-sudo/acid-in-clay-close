"""Tier3 (issue 4): S09 opt-in evidence-based candidate generation.

The frozen default keeps the fixed deterministic I1..I5 set. This adds an
opt-in generator that builds candidates by greedy descriptor coverage over the
S08 component-claim pool, with every component grounded in real claim paper_ids.

Pins:
  1. the flag defaults OFF (frozen behaviour unchanged);
  2. the generator clusters real components, cites their real paper_ids, covers
     descriptors, and never invents component names;
  3. family names carry no substance names (S09 generation contract).
"""
from __future__ import annotations

import json

from s8_stage3.agents.s09_candidate_family_generator import (
    _build_evidence_based_output,
    run_s09,
)
from s8_stage3.config.settings import Stage3Settings
from s8_stage3.contracts.descriptor import DescriptorSheet, MechanismDescriptor
from s8_stage3.contracts.literature import ComponentDescriptorClaim, LiteratureCard, LiteratureSurvey
from s8_stage3.contracts.material import MaterialInstanceSet


class _ExplodingGateway:
    """A gateway that fails loudly if the LLM path is taken. Both the
    deterministic and evidence-based branches must avoid calling it."""

    def chat_json(self, *args, **kwargs):  # pragma: no cover - must not run
        raise AssertionError("run_s09 should not call the LLM in this branch")


def _descriptor_sheet():
    return DescriptorSheet(
        descriptors=[
            MechanismDescriptor(descriptor_id="D1", descriptor_text="OH-rich host", mechanism_role="donor"),
            MechanismDescriptor(descriptor_id="D2", descriptor_text="1-D confinement", mechanism_role="confine"),
            MechanismDescriptor(descriptor_id="D3", descriptor_text="mobile proton carrier", mechanism_role="carry"),
        ]
    )


def _survey():
    return LiteratureSurvey(
        step_id="s08",
        survey_scope="material_search",
        cards=[
            LiteratureCard(
                card_id="P1",
                title="starch host",
                component_descriptor_claims=[
                    ComponentDescriptorClaim(component="starch", descriptor_ids=["D1"], claim_text="OH-rich host")
                ],
            ),
            LiteratureCard(
                card_id="P2",
                title="clay confinement",
                component_descriptor_claims=[
                    ComponentDescriptorClaim(
                        component="attapulgite", descriptor_ids=["D2", "D3"], claim_text="1-D confinement"
                    )
                ],
            ),
            LiteratureCard(
                card_id="P3",
                title="acid carrier",
                component_descriptor_claims=[
                    ComponentDescriptorClaim(
                        component="phosphoric acid", descriptor_ids=["D1", "D3"], claim_text="proton donor"
                    )
                ],
            ),
        ],
    )


def test_flag_defaults_off():
    assert getattr(Stage3Settings(), "s09_evidence_based_generation", False) is False


def test_evidence_based_output_is_grounded_and_covers_descriptors():
    out = _build_evidence_based_output(_survey(), _descriptor_sheet())
    assert out is not None
    assert len(out.instances) == 3  # one per distinct component seed

    allowed_components = {"starch", "attapulgite", "phosphoric acid"}
    allowed_papers = {"P1", "P2", "P3"}
    for inst in out.instances:
        # no fabricated components
        assert set(inst.components).issubset(allowed_components)
        # every element evidence cites only real paper ids
        for ev in inst.element_evidence:
            assert set(ev.analog_paper_ids).issubset(allowed_papers)
            assert ev.descriptor_satisfied  # descriptors actually attributed
        # derived support ids are the union of element evidence papers
        assert set(inst.literature_support_card_ids).issubset(allowed_papers)
        assert inst.combination_novelty == "novel_combination"
        assert inst.novelty_rationale

    # the widest-coverage seed should reach full 3/3 descriptor coverage
    i1 = out.instances[0]
    assert i1.expected_properties == ["descriptor_coverage: 3/3"]
    assert set(i1.components) == {"attapulgite", "phosphoric acid"}


def test_family_names_carry_no_substance_names():
    out = _build_evidence_based_output(_survey(), _descriptor_sheet())
    for fam in out.families:
        for substance in ("starch", "attapulgite", "phosphoric"):
            assert substance not in fam.family_name.lower()


def test_empty_survey_returns_none():
    empty = LiteratureSurvey(step_id="s08", survey_scope="material_search", cards=[])
    assert _build_evidence_based_output(empty, _descriptor_sheet()) is None


def _generation_mode(output_dir) -> str:
    audit = json.loads(
        (output_dir / "08_material_instances" / "candidate_generation_audit.json").read_text(
            encoding="utf-8"
        )
    )
    return audit["generation_mode"]


def _instances(output_dir) -> list:
    data = json.loads(
        (output_dir / "08_material_instances" / "material_instances.json").read_text(
            encoding="utf-8"
        )
    )
    return data["instances"]


def _load_instance_set(output_dir) -> MaterialInstanceSet:
    """Round-trip the written JSON through pydantic to prove schema validity."""
    data = json.loads(
        (output_dir / "08_material_instances" / "material_instances.json").read_text(
            encoding="utf-8"
        )
    )
    return MaterialInstanceSet.model_validate(data)


def test_run_s09_default_settings_takes_deterministic_path(tmp_path):
    """Default Stage3Settings (flag OFF) must keep the frozen deterministic_from_d4
    path and never reach the evidence-based branch or the LLM."""
    settings = Stage3Settings()
    assert getattr(settings, "s09_evidence_based_generation", False) is False

    run_s09(
        _descriptor_sheet(),
        _survey(),
        _ExplodingGateway(),
        tmp_path,
        settings=settings,
    )
    assert _generation_mode(tmp_path) == "deterministic_from_d4"


def test_run_s09_explicit_flag_takes_evidence_based_path(tmp_path):
    """Explicitly enabling the flag must route S09 through the evidence-based
    descriptor-match branch."""
    settings = Stage3Settings()
    settings.s09_evidence_based_generation = True

    run_s09(
        _descriptor_sheet(),
        _survey(),
        _ExplodingGateway(),
        tmp_path,
        settings=settings,
    )
    assert _generation_mode(tmp_path) == "evidence_based_descriptor_match"


def test_run_s09_evidence_based_metadata_is_truthful_not_llm(tmp_path):
    """The deterministic evidence-based branch must NOT label its instances as
    LLM-selected from a broad pool; metadata must reflect the real mechanism;
    and the written JSON must round-trip through MaterialInstanceSet.model_validate."""
    settings = Stage3Settings()
    settings.s09_evidence_based_generation = True

    run_s09(
        _descriptor_sheet(),
        _survey(),
        _ExplodingGateway(),
        tmp_path,
        settings=settings,
    )
    assert _generation_mode(tmp_path) == "evidence_based_descriptor_match"

    instances = _instances(tmp_path)
    assert instances  # non-empty
    for inst in instances:
        # not misleadingly attributed to an LLM broad-pool selection
        assert inst["origin"] != "llm_selected_from_broad_pool"
        assert inst["source_mode"] != "broad_literature_pool_selection"
        # truthful, non-LLM deterministic labels
        assert inst["source_mode"] == "evidence_based_descriptor_match"
        assert inst["origin"] == "deterministic_evidence_based_descriptor_match"

    # schema round-trip: this is the regression that the contract fix repairs.
    instance_set = _load_instance_set(tmp_path)
    assert instance_set.instances  # validated, non-empty
    origin_values = sorted({i.origin for i in instance_set.instances})
    source_mode_values = sorted({i.source_mode for i in instance_set.instances})
    assert origin_values == ["deterministic_evidence_based_descriptor_match"]
    assert source_mode_values == ["evidence_based_descriptor_match"]


def test_settings_flag_defaults_false(monkeypatch):
    """With the env var unset, the settings field defaults to False."""
    monkeypatch.delenv("STAGE3_S09_EVIDENCE_BASED_GENERATION", raising=False)
    assert Stage3Settings().s09_evidence_based_generation is False


def test_settings_flag_reads_env_true(monkeypatch):
    """Setting the env var to 'true' flips the settings field to True (no CLI)."""
    monkeypatch.setenv("STAGE3_S09_EVIDENCE_BASED_GENERATION", "true")
    assert Stage3Settings().s09_evidence_based_generation is True
