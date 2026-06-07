import json
from pathlib import Path
from types import SimpleNamespace

import pytest


def _write_json(path: Path, data: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


class _StaticGateway:
    def __init__(self, payload: dict):
        self.payload = payload
        self.calls = 0

    def chat_json(self, *args, **kwargs):
        self.calls += 1
        return json.loads(json.dumps(self.payload))


class _RaisingGateway:
    is_mock = False

    def __init__(self):
        self.calls = 0

    def chat_json(self, *args, **kwargs):
        self.calls += 1
        raise AssertionError("live gateway should not be called")


def test_s06_rejects_mechanism_id_not_from_s04(tmp_path):
    from s8_stage3.agents.s06_mechanism_arbiter import run_s06
    from s8_stage3.contracts.evidence import EvidenceBundle, EvidenceCard
    from s8_stage3.contracts.hypothesis import Hypothesis, HypothesisBoard
    from s8_stage3.contracts.literature import LiteratureSurvey

    gateway = _StaticGateway(
        {
            "step_id": "s06_mechanism",
            "mechanism_card": {
                "selected_hypothesis_id": "H999",
                "mechanism_label": "invented id",
                "justification": "bad",
                "confidence": 0.5,
            },
        }
    )
    evidence = EvidenceBundle(evidence_cards=[EvidenceCard(card_id="E1", statement="e")])
    board = HypothesisBoard(
        hypotheses=[
            Hypothesis(hypothesis_id="H1", mechanism_label="m1", description="d"),
            Hypothesis(hypothesis_id="H2", mechanism_label="m2", description="d"),
            Hypothesis(hypothesis_id="H3", mechanism_label="m3", description="d"),
        ]
    )

    with pytest.raises(RuntimeError, match="selected_hypothesis_id"):
        run_s06(
            evidence,
            LiteratureSurvey(step_id="s05", survey_scope="mechanism_constraint"),
            gateway,
            tmp_path,
            hypothesis_board=board,
        )


def test_s04_prunes_invalid_evidence_refs_and_writes_audit(tmp_path):
    from s8_stage3.agents.s04_hypothesis_generator import run_s04
    from s8_stage3.contracts.evidence import EvidenceBundle, EvidenceCard

    gateway = _StaticGateway(
        {
            "step_id": "s04_hypotheses",
            "hypotheses": [
                {
                    "hypothesis_id": "H1",
                    "mechanism_label": "valid",
                    "description": "valid",
                    "supporting_evidence_ids": ["E1"],
                },
                {
                    "hypothesis_id": "H2",
                    "mechanism_label": "invalid",
                    "description": "invalid",
                    "supporting_evidence_ids": ["BAD"],
                },
                {
                    "hypothesis_id": "H3",
                    "mechanism_label": "mixed",
                    "description": "mixed",
                    "supporting_evidence_ids": ["E1", "MISSING"],
                },
            ],
        }
    )
    evidence = EvidenceBundle(evidence_cards=[EvidenceCard(card_id="E1", statement="e")])

    board = run_s04(evidence, gateway, tmp_path)
    audit = json.loads(
        (tmp_path / "02_hypotheses" / "hypothesis_reference_audit.json").read_text(
            encoding="utf-8"
        )
    )

    assert audit["invalid_refs"]["H2"]["invalid_supporting_evidence_ids"] == ["BAD"]
    assert board.hypotheses[1].supporting_evidence_ids == []
    assert board.hypotheses[2].supporting_evidence_ids == ["E1"]


def test_s06b_prompt_carries_real_evidence_and_mechanism():
    from s8_stage3.agents.s06b_design_principle_extractor import _pack_prompt
    from s8_stage3.contracts.evidence import EvidenceBundle, EvidenceCard
    from s8_stage3.contracts.mechanism import MechanismArbitrationResult, MechanismCard

    evidence = EvidenceBundle(
        evidence_cards=[
            EvidenceCard(
                card_id="V2-E1",
                statement="Authoritative V2 transport evidence.",
                confidence=0.72,
            )
        ]
    )
    arbitration = MechanismArbitrationResult(
        mechanism_card=MechanismCard(
            selected_hypothesis_id="H1",
            mechanism_label="Confined proton network",
            justification="Evidence aligns with confined transport.",
            evidence_alignment=["V2-E1 supports the mechanism"],
        )
    )

    packed = _pack_prompt(arbitration, evidence)

    assert "V2-E1" in packed
    assert "Confined proton network" in packed
    assert "EvidenceCards (S03)" in packed


def test_s09_writes_candidate_generation_audit(tmp_path):
    from s8_stage3.agents.s09_candidate_family_generator import run_s09
    from s8_stage3.contracts.descriptor import DescriptorSheet, MechanismDescriptor
    from s8_stage3.contracts.literature import LiteratureCard, LiteratureSurvey

    gateway = _StaticGateway(
        {
            "families": [
                {
                    "family_id": "F1",
                    "family_name": "test family",
                    "descriptor_match": ["D1: ok"],
                }
            ],
            "instances": [
                {
                    "instance_id": "I1",
                    "family_id": "F1",
                    "instance_name": "test instance",
                    "components": ["starch"],
                    "combination_novelty": "novel_combination",
                    "element_evidence": [
                        {
                            "component": "starch",
                            "role_in_formulation": "OH host",
                            "descriptor_satisfied": ["D1"],
                            "analog_paper_ids": ["MISSING"],
                            "analog_reason": "bad ref",
                        }
                    ],
                    "novelty_rationale": (
                        "This is a long enough rationale explaining that the exact combination "
                        "is not present in the source pool and is assembled from component-level "
                        "evidence for audit testing."
                    ),
                }
            ],
        }
    )
    descriptors = DescriptorSheet(
        descriptors=[
            MechanismDescriptor(
                descriptor_id="D1",
                descriptor_text="OH-rich host",
                mechanism_role="host",
            )
        ]
    )
    survey = LiteratureSurvey(
        step_id="s08",
        survey_scope="material_search",
        cards=[LiteratureCard(card_id="MAT1", title="source card")]
    )
    settings = SimpleNamespace(
        discovery_mode="broad_literature_pool_selection",
        final_audit=False,
    )

    run_s09(descriptors, survey, gateway, tmp_path, settings=settings)
    audit = json.loads(
        (tmp_path / "08_material_instances" / "candidate_generation_audit.json").read_text(
            encoding="utf-8"
        )
    )

    assert audit["audit_ok"] is False
    assert audit["instances_with_bad_paper_ids"][0]["instance_id"] == "I1"
    assert audit["instances_with_bad_paper_ids"][0]["bad_paper_ids"] == ["MISSING"]


def test_s08_manual_mode_extracts_d4_claim_pool(tmp_path, monkeypatch):
    from s8_stage3.agents import s08_literature_scout_materials as s08
    from s8_stage3.contracts.descriptor import DescriptorSheet, MechanismDescriptor
    from s8_stage3.contracts.literature import LiteratureCard

    descriptors = DescriptorSheet(
        descriptors=[
            MechanismDescriptor(
                descriptor_id="D1",
                descriptor_text="OH-rich host",
                mechanism_role="host",
            )
        ]
    )
    cards = [
        LiteratureCard(
            card_id="MAT1",
            title="PVA membrane",
            summary="PVA improves hydrogen-bonded film continuity.",
            relevance_to_descriptors="D1",
        )
    ]
    gateway = _StaticGateway(
        {
            "synthesis_notes": "polymer hosts cover D1",
            "component_descriptor_claims_by_card": {
                "MAT1": [
                    {
                        "component": "PVA",
                        "descriptor_ids": ["D1", "D999"],
                        "quantitative_anchor": "film-forming polymer",
                        "claim_text": "PVA provides D1-type matrix continuity (MAT1).",
                        "confidence": "supported",
                    }
                ],
                "OUTSIDE_BATCH": [
                    {
                        "component": "bad",
                        "descriptor_ids": ["D1"],
                        "claim_text": "bad",
                    }
                ],
            },
        }
    )
    monkeypatch.setattr(
        s08,
        "_fetch_manual_cards_and_context",
        lambda settings, strict=False: (cards, "manual context"),
    )

    survey = s08.run_s08(
        descriptors,
        gateway,
        tmp_path,
        literature_mode="manual",
        settings=SimpleNamespace(s08_claim_batch_size=4),
        manual_strict=True,
    )

    claim_pool = json.loads(
        (tmp_path / "06_literature_materials" / "descriptor_claim_pool.json").read_text(
            encoding="utf-8"
        )
    )
    diagnostics = json.loads(
        (
            tmp_path
            / "06_literature_materials"
            / "s08_claim_extraction_diagnostics.json"
        ).read_text(encoding="utf-8")
    )

    assert gateway.calls == 1
    assert survey.cards[0].component_descriptor_claims[0].component == "PVA"
    assert survey.cards[0].component_descriptor_claims[0].descriptor_ids == ["D1"]
    assert claim_pool["n_claims"] == 1
    assert claim_pool["claims"][0]["component"] == "PVA"
    assert diagnostics["n_cards_with_claims"] == 1


def test_s09_pack_caps_raw_fallback_when_d4_claims_exist():
    from s8_stage3.llm.prompt_packing import pack_for_s09

    descriptor_sheet = {
        "descriptors": [{"descriptor_id": "D1", "descriptor_text": "OH host"}]
    }
    cards = [
        {
            "card_id": "MAT-D4",
            "title": "structured",
            "summary": "structured card",
            "component_descriptor_claims": [
                {
                    "component": "PVA",
                    "descriptor_ids": ["D1"],
                    "claim_text": "PVA supports D1",
                }
            ],
        }
    ]
    cards.extend(
        {
            "card_id": f"RAW{i}",
            "title": f"raw {i}",
            "summary": f"raw fallback summary {i}",
            "relevance_to_descriptors": "fallback",
        }
        for i in range(12)
    )

    payload = json.loads(
        pack_for_s09(
            descriptor_sheet,
            {"cards": cards},
            system_context=None,
        )
    )

    assert len(payload["descriptor_claim_pool"]) == 1
    assert len(payload["raw_cards_fallback"]) == 8
    assert payload["raw_cards_fallback_omitted_count"] == 4


def test_s09_compact_payload_uses_d4_claims_and_drops_long_fallbacks():
    from s8_stage3.agents.s09_candidate_family_generator import _compact_s09_payload
    from s8_stage3.llm.prompt_packing import pack_for_s09

    descriptor_sheet = {
        "descriptors": [{"descriptor_id": "D1", "descriptor_text": "OH host" * 80}]
    }
    cards = [
        {
            "card_id": "MAT-D4",
            "title": "structured",
            "summary": "structured card",
            "component_descriptor_claims": [
                {
                    "component": "PVA",
                    "descriptor_ids": ["D1"],
                    "claim_text": "PVA supports D1 " * 80,
                }
            ],
        }
    ]
    cards.extend(
        {
            "card_id": f"RAW{i}",
            "title": f"raw {i}",
            "summary": "raw fallback summary " * 80,
            "relevance_to_descriptors": "fallback",
        }
        for i in range(12)
    )

    full = pack_for_s09(descriptor_sheet, {"cards": cards}, system_context=None)
    compact = json.loads(_compact_s09_payload(full))

    assert len(json.dumps(compact, ensure_ascii=False)) < len(full)
    assert len(compact["descriptor_claim_pool"]) == 1
    assert "raw_cards_fallback" not in compact
    assert compact["generation_contract"]["instances"].startswith("exactly 5")


def test_candidate_audit_requires_component_descriptor_pair_support(tmp_path):
    from s8_stage3.scoring.candidate_audit import audit_candidates

    out = tmp_path
    _write_json(
        out / "06_literature_materials" / "descriptor_claim_pool.json",
        {
            "claims": [
                {
                    "card_id": "MAT1",
                    "component": "starch",
                    "descriptor_ids": ["D1"],
                    "claim_text": "starch supports D1",
                }
            ]
        },
    )
    _write_json(
        out / "06_literature_materials" / "literature_cards_materials.json",
        {"cards": [{"card_id": "MAT1"}]},
    )
    inst = {
        "instance_id": "I1",
        "instance_name": "test",
        "combination_novelty": "novel_combination",
        "element_evidence": [
            {
                "component": "starch",
                "descriptor_satisfied": ["D1"],
                "analog_paper_ids": ["MAT1"],
            },
            {
                "component": "attapulgite",
                "descriptor_satisfied": ["D1"],
                "analog_paper_ids": ["MAT1"],
            },
        ],
    }
    ranking = {
        "ranked_candidates": [
            {
                "instance_id": "I1",
                "instance_name": "test",
                "total_score": 0.9,
                "combination_novelty": "novel_combination",
            }
        ]
    }

    rows, reranked = audit_candidates([inst], ranking, out)
    row = rows[0]

    assert row["descriptor_claim_coverage"] == pytest.approx(0.5)
    assert row["n_element_descriptor_pairs"] == 2
    assert row["n_supported_element_descriptor_pairs"] == 1
    assert row["unsupported_element_descriptor_pairs"][0]["component"] == "attapulgite"
    assert reranked[0]["deterministic_rank"] == 1


def test_candidate_audit_priority_separates_complete_formulation(tmp_path):
    from s8_stage3.scoring.candidate_audit import audit_candidates

    out = tmp_path
    _write_json(
        out / "06_literature_materials" / "descriptor_claim_pool.json",
        {
            "claims": [
                {
                    "card_id": "MAT-starch",
                    "component": "starch",
                    "descriptor_ids": ["D1"],
                    "claim_text": "starch host sites",
                    "confidence": "supported",
                },
                {
                    "card_id": "MAT-pva",
                    "component": "PVA",
                    "descriptor_ids": ["D3"],
                    "claim_text": "PVA film matrix",
                    "confidence": "supported",
                },
                {
                    "card_id": "MAT-clay",
                    "component": "attapulgite",
                    "descriptor_ids": ["D1"],
                    "claim_text": "attapulgite confinement",
                    "confidence": "supported",
                    "quantitative_anchor": "0.02 S/cm",
                },
                {
                    "card_id": "MAT-acid",
                    "component": "phosphoric acid",
                    "descriptor_ids": ["D4"],
                    "claim_text": "acid carrier",
                    "confidence": "supported",
                },
                {
                    "card_id": "MAT-chito",
                    "component": "chitosan",
                    "descriptor_ids": ["D1"],
                    "claim_text": "chitosan host",
                    "confidence": "hint",
                },
            ]
        },
    )
    _write_json(
        out / "06_literature_materials" / "literature_cards_materials.json",
        {"cards": [{"card_id": cid} for cid in ["MAT-starch", "MAT-pva", "MAT-clay", "MAT-acid", "MAT-chito"]]},
    )
    complete = {
        "instance_id": "I-complete",
        "instance_name": "Starch/PVA/attapulgite/H3PO4 membrane",
        "components": ["starch", "PVA", "attapulgite", "phosphoric acid"],
        "expected_properties": ["cold_window: bound-water retention", "processability: film membrane"],
        "risk_flags": ["acid leaching must be measured"],
        "combination_novelty": "novel_combination",
        "element_evidence": [
            {"component": "starch", "descriptor_satisfied": ["D1"], "analog_paper_ids": ["MAT-starch"]},
            {"component": "PVA", "descriptor_satisfied": ["D3"], "analog_paper_ids": ["MAT-pva"]},
            {"component": "attapulgite", "descriptor_satisfied": ["D1"], "analog_paper_ids": ["MAT-clay"]},
            {"component": "phosphoric acid", "descriptor_satisfied": ["D4"], "analog_paper_ids": ["MAT-acid"]},
        ],
    }
    partial = {
        "instance_id": "I-partial",
        "instance_name": "Chitosan/phosphoric acid composite",
        "components": ["chitosan", "phosphoric acid"],
        "expected_properties": ["host_sites: chitosan matrix", "carrier: phosphoric acid"],
        "risk_flags": ["acid loading needs optimisation"],
        "combination_novelty": "novel_combination",
        "element_evidence": [
            {"component": "chitosan", "descriptor_satisfied": ["D1"], "analog_paper_ids": ["MAT-chito"]},
            {"component": "phosphoric acid", "descriptor_satisfied": ["D4"], "analog_paper_ids": ["MAT-acid"]},
        ],
    }
    ranking = {
        "ranked_candidates": [
            {"instance_id": "I-partial", "instance_name": "partial", "total_score": 0.9},
            {"instance_id": "I-complete", "instance_name": "complete", "total_score": 0.9},
        ]
    }

    rows, reranked = audit_candidates([partial, complete], ranking, out)
    by_id = {row["instance_id"]: row for row in rows}

    assert by_id["I-complete"]["audit_gate_score"] > 0.8
    assert by_id["I-partial"]["audit_gate_score"] > 0.8
    assert by_id["I-complete"]["material_priority_score"] > by_id["I-partial"]["material_priority_score"]
    assert reranked[0]["instance_id"] == "I-complete"


def test_s10_deterministic_ranker_skips_live_gateway(tmp_path):
    from s8_stage3.agents.s10_instance_ranker import run_s10
    from s8_stage3.contracts.literature import LiteratureSurvey
    from s8_stage3.contracts.material import MaterialInstanceSet
    from s8_stage3.contracts.mechanism import MechanismArbitrationResult, MechanismCard

    _write_json(
        tmp_path / "06_literature_materials" / "descriptor_claim_pool.json",
        {
            "claims": [
                {"card_id": "MAT1", "component": "starch", "descriptor_ids": ["D1"], "claim_text": "starch D1"},
                {"card_id": "MAT2", "component": "PVA", "descriptor_ids": ["D2"], "claim_text": "PVA D2"},
            ]
        },
    )
    _write_json(
        tmp_path / "06_literature_materials" / "literature_cards_materials.json",
        {"cards": [{"card_id": "MAT1"}, {"card_id": "MAT2"}]},
    )
    instances = MaterialInstanceSet.model_validate(
        {
            "instances": [
                {
                    "instance_id": "I1",
                    "family_id": "F1",
                    "instance_name": "starch/PVA membrane",
                    "components": ["starch", "PVA"],
                    "combination_novelty": "novel_combination",
                    "element_evidence": [
                        {
                            "component": "starch",
                            "role_in_formulation": "hydrogen-bond host",
                            "descriptor_satisfied": ["D1"],
                            "analog_paper_ids": ["MAT1"],
                        },
                        {
                            "component": "PVA",
                            "role_in_formulation": "polymer matrix",
                            "descriptor_satisfied": ["D2"],
                            "analog_paper_ids": ["MAT2"],
                        },
                    ],
                    "novelty_rationale": "new combination",
                },
                {
                    "instance_id": "I2",
                    "family_id": "F1",
                    "instance_name": "starch control",
                    "components": ["starch"],
                    "combination_novelty": "exact_match",
                    "element_evidence": [
                        {
                            "component": "starch",
                            "role_in_formulation": "hydrogen-bond host",
                            "descriptor_satisfied": ["D1"],
                            "analog_paper_ids": ["MAT1"],
                        },
                    ],
                    "novelty_rationale": "control baseline",
                },
            ]
        }
    )
    arbitration = MechanismArbitrationResult(
        mechanism_card=MechanismCard(
            selected_hypothesis_id="H1",
            mechanism_label="test mechanism",
            justification="test",
        )
    )
    gateway = _RaisingGateway()

    ranking = run_s10(
        instances,
        arbitration,
        LiteratureSurvey(step_id="s08", survey_scope="material_search"),
        gateway,
        tmp_path,
        settings=SimpleNamespace(s10_deterministic_from_audit=True),
    )

    assert gateway.calls == 0
    assert [c.instance_id for c in ranking.ranked_candidates] == ["I1", "I2"]
    assert (tmp_path / "09_ranking" / "candidate_audit.json").exists()
    audit = json.loads((tmp_path / "09_ranking" / "ranking_generation_audit.json").read_text(encoding="utf-8"))
    assert audit["generation_mode"] == "deterministic_from_candidate_audit"


def test_s11_deterministic_report_skips_live_gateway(tmp_path):
    from s8_stage3.agents.s11_report_compiler import run_s11
    from s8_stage3.contracts.evidence import EvidenceBundle, EvidenceCard
    from s8_stage3.contracts.material import MaterialFamilySet, MaterialInstanceSet
    from s8_stage3.contracts.mechanism import MechanismArbitrationResult, MechanismCard
    from s8_stage3.contracts.ranking import RankedCandidate, RankingResult

    gateway = _RaisingGateway()
    report = run_s11(
        EvidenceBundle(evidence_cards=[EvidenceCard(card_id="E1", statement="evidence")]),
        MechanismArbitrationResult(
            mechanism_card=MechanismCard(
                selected_hypothesis_id="H1",
                mechanism_label="test mechanism",
                justification="supported by E1",
            )
        ),
        MaterialFamilySet(families=[]),
        MaterialInstanceSet(instances=[]),
        RankingResult(
            ranked_candidates=[
                RankedCandidate(rank=1, instance_id="I1", instance_name="candidate", total_score=0.8)
            ]
        ),
        gateway,
        tmp_path,
        settings=SimpleNamespace(s11_deterministic_report=True),
    )

    assert gateway.calls == 0
    assert report.sections
    audit = json.loads((tmp_path / "10_reports" / "report_generation_audit.json").read_text(encoding="utf-8"))
    assert audit["generation_mode"] == "deterministic_fallback_report"


def test_s14_final_audit_blocks_weak_candidate_audit(tmp_path):
    from s8_stage3.agents.s14_claim_auditor import run_s14

    _write_json(
        tmp_path / "01_evidence" / "evidence_cards.json",
        {"evidence_cards": [{"card_id": "V2-E1", "support_metrics": {"v2_evidence_id": "EV1"}}]},
    )
    _write_json(
        tmp_path / "04_mechanism" / "mechanism_card.json",
        {"mechanism_card": {"selected_hypothesis_id": "H1"}},
    )
    _write_json(
        tmp_path / "11_candidate_registry" / "prospective_candidates.json",
        {"run_id": "r1", "n_candidates": 1},
    )
    _write_json(
        tmp_path / "09_ranking" / "candidate_audit.json",
        {
            "n_candidates": 1,
            "source_term_audit_ok": True,
            "rows": [
                {
                    "instance_id": "I1",
                    "descriptor_claim_coverage": 0.0,
                    "n_element_descriptor_pairs": 1,
                    "bad_cited_paper_ids": [],
                }
            ],
        },
    )

    settings = SimpleNamespace(
        discovery_mode="broad_literature_pool_selection",
        final_audit=True,
    )
    report = run_s14(tmp_path, settings)

    assert any("candidate_audit" in blocker for blocker in report.publication_blockers)
    transfer = next(item for item in report.claim_ladder if item.claim_level == "llm_transfer_candidate")
    assert transfer.is_supported is False


def test_s14_required_evidence_paths_are_output_dir_relative(tmp_path):
    from s8_stage3.agents.s14_claim_auditor import run_s14

    _write_json(
        tmp_path / "01_evidence" / "evidence_cards.json",
        {"evidence_cards": [{"card_id": "V2-E1", "support_metrics": {"v2_evidence_id": "EV1"}}]},
    )
    _write_json(
        tmp_path / "04_mechanism" / "mechanism_card.json",
        {"mechanism_card": {"selected_hypothesis_id": "H1"}},
    )
    _write_json(
        tmp_path / "11_candidate_registry" / "prospective_candidates.json",
        {"run_id": "r1", "n_candidates": 1},
    )
    _write_json(
        tmp_path / "09_ranking" / "candidate_audit.json",
        {
            "n_candidates": 1,
            "source_term_audit_ok": True,
            "rows": [
                {
                    "instance_id": "I1",
                    "descriptor_claim_coverage": 0.8,
                    "n_element_descriptor_pairs": 1,
                    "bad_cited_paper_ids": [],
                }
            ],
        },
    )

    settings = SimpleNamespace(
        discovery_mode="broad_literature_pool_selection",
        final_audit=True,
    )
    report = run_s14(tmp_path, settings)
    required = [
        ref
        for item in report.claim_ladder
        for ref in item.required_evidence
    ]

    assert any(ref.startswith("04_mechanism/") for ref in required)
    assert any(ref.startswith("01_evidence/") for ref in required)
    assert any(ref.startswith("11_candidate_registry/") for ref in required)
    assert not any("outputs/stage3/" in ref for ref in required)
