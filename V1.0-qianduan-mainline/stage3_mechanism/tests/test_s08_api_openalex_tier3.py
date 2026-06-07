"""Tier3 (issue 2): S08 materials literature 'api' mode (OpenAlex-backed).

Before Tier3 the 'api' branch just logged a warning and wrote an empty survey.
Now it fetches real materials literature via an injectable OpenAlex provider and
runs the existing D4 component-claim extraction. These tests use an injected
fake provider (no network) and pin:
  1. api mode turns PaperRecords into LiteratureCards and writes support files.
  2. api mode is offline-safe: an empty provider result -> empty survey, no crash.
"""
from __future__ import annotations

from types import SimpleNamespace

from s8_stage3.agents.s08_literature_scout_materials import run_s08
from s8_stage3.contracts.descriptor import DescriptorSheet, MechanismDescriptor


class _FakeRecord(SimpleNamespace):
    pass


class _FakeProvider:
    def __init__(self, records):
        self._records = records
        self.calls = []

    def search(self, query, max_results=10, from_year=None):
        self.calls.append((query, max_results, from_year))
        # return the canned records only for the first query to exercise de-dupe
        return self._records if len(self.calls) == 1 else []


class _FakeGateway:
    """Returns a schema-valid empty claim batch (no LLM)."""

    def chat_json(self, messages, step="", output_schema=None):
        return {"synthesis_notes": "", "component_descriptor_claims_by_card": {}}


def _descriptor_sheet():
    return DescriptorSheet(
        descriptors=[
            MechanismDescriptor(
                descriptor_id="D1",
                descriptor_text="host with dense hydrogen-bond donor sites",
                mechanism_role="proton donor network",
                priority="critical",
            ),
            MechanismDescriptor(
                descriptor_id="D2",
                descriptor_text="one-dimensional confinement channel",
                mechanism_role="acid confinement",
                priority="important",
            ),
        ]
    )


def test_s08_api_mode_builds_cards_from_provider(tmp_path):
    records = [
        _FakeRecord(
            paper_id="W123",
            title="Acid-in-clay proton conductor",
            authors="A B, C D",
            year=2023,
            doi="10.1/abc",
            abstract="Phosphoric acid confined in attapulgite shows proton conduction.",
        ),
        _FakeRecord(
            paper_id="W123",  # duplicate id -> must be de-duped
            title="dup",
            authors="",
            year=2023,
            doi="",
            abstract="",
        ),
        _FakeRecord(
            paper_id="W456",
            title="Halloysite nanotube electrolyte",
            authors="E F",
            year=2022,
            doi="10.2/xyz",
            abstract="Halloysite confines acid for conduction.",
        ),
    ]
    provider = _FakeProvider(records)

    survey = run_s08(
        _descriptor_sheet(),
        _FakeGateway(),
        tmp_path,
        literature_mode="api",
        settings=SimpleNamespace(s08_api_max_results_per_query=5),
        api_provider=provider,
    )

    card_ids = {c.card_id for c in survey.cards}
    assert card_ids == {"W123", "W456"}  # de-duped
    assert provider.calls  # provider was actually queried
    # support files written
    assert (tmp_path / "06_literature_materials" / "literature_cards_materials.json").exists()
    assert (tmp_path / "06_literature_materials" / "s08_claim_extraction_diagnostics.json").exists()


def test_s08_api_mode_is_offline_safe(tmp_path):
    provider = _FakeProvider([])  # network returns nothing

    survey = run_s08(
        _descriptor_sheet(),
        _FakeGateway(),
        tmp_path,
        literature_mode="api",
        settings=SimpleNamespace(),
        api_provider=provider,
    )

    assert survey.cards == []
    assert survey.step_id == "s08"
    # empty result still writes a well-formed (empty) survey, no exception
    assert (tmp_path / "06_literature_materials" / "literature_cards_materials.json").exists()
