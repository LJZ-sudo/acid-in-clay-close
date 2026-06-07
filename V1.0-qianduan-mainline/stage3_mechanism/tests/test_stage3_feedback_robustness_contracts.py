import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "stage3_mechanism" / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def _write_json(path: Path, data: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _registry():
    from s8_stage3.contracts.prospective import (
        ProspectiveCandidate,
        ProspectiveCandidateRegistry,
    )

    return ProspectiveCandidateRegistry(
        run_id="run-test",
        preregistered_at="2026-05-18T00:00:00Z",
        n_candidates=1,
        candidates=[
            ProspectiveCandidate(
                candidate_id="PC-test-1",
                instance_id="I1",
                instance_name="lotus starch / PVA / H3PO4 / attapulgite",
                preregistered_at="2026-05-18T00:00:00Z",
                components=["lotus starch", "PVA", "H3PO4", "attapulgite"],
            )
        ],
    )


def _feedback_record(**overrides):
    data = {
        "validation_id": "VAL-1",
        "candidate_id": "PC-test-1",
        "instance_id": None,
        "sample_id": "BIO-1",
        "validation_timing": "prospective",
        "measured_at": "2026-05-19T00:00:00Z",
        "lotus_starch_g": 1.0,
        "pva_g": 0.2,
        "attapulgite_g": 0.1,
        "h3po4_85wt_g": 0.3,
        "sigma_299k_s_cm": 0.01,
        "ea_high_eV": 0.22,
        "leakage_score": 0.0,
        "notes": "contract test",
    }
    data.update(overrides)
    return data


def _feedback(records):
    return {
        "schema_version": "0.1.0",
        "artifact_type": "stage3_experimental_feedback",
        "created_at": "2026-05-19T00:00:00Z",
        "source_system": "transfer_validation",
        "source_mode": "real",
        "validation_records": records,
        "input_hashes": {"fixture": "abc123"},
        "provenance": {"test": True},
    }


def test_s13_prefers_json_feedback_over_csv_and_does_not_mutate_registry(tmp_path):
    from s8_stage3.agents.s13_validation_binder import run_s13

    registry = _registry()
    before = registry.model_dump(mode="json")
    feedback_path = _write_json(tmp_path / "experimental_feedback.json", _feedback([_feedback_record()]))
    csv_path = tmp_path / "legacy.csv"
    csv_path.write_text(
        "validation_id,candidate_id,sample_id,validation_timing,sigma_299k_s_cm\n"
        "CSV-1,PC-test-1,CSV-S,retrospective,0.001\n",
        encoding="utf-8",
    )

    report = run_s13(
        registry,
        tmp_path / "out",
        SimpleNamespace(),
        feedback_path=feedback_path,
        csv_path=csv_path,
    )

    assert report.feedback_schema_valid is True
    assert report.source_feedback_path == str(feedback_path)
    assert report.source_csv_path == ""
    assert report.n_records == 1
    assert report.candidate_links[0].claim_eligibility == "prospective_validation"
    assert registry.model_dump(mode="json") == before


def test_experimental_feedback_rejects_missing_candidate_and_instance():
    from s8_stage3.contracts.experimental_feedback import ExperimentalFeedback

    bad = _feedback([_feedback_record(candidate_id=None, instance_id=None)])

    with pytest.raises(ValueError, match="candidate_id or instance_id"):
        ExperimentalFeedback.model_validate(bad)


def test_s13_prospective_requires_legal_timestamp(tmp_path):
    from s8_stage3.agents.s13_validation_binder import run_s13

    feedback_path = _write_json(
        tmp_path / "experimental_feedback.json",
        _feedback([_feedback_record(measured_at="", validation_timing="prospective")]),
    )

    report = run_s13(_registry(), tmp_path / "out", SimpleNamespace(), feedback_path=feedback_path)

    assert report.records[0].validation_timing == "unknown"
    assert report.candidate_links[0].claim_eligibility == "unvalidated_candidate"


def test_s13_uses_feedback_provenance_registry_for_timing(tmp_path):
    from s8_stage3.agents.s13_validation_binder import run_s13
    from s8_stage3.contracts.prospective import (
        ProspectiveCandidate,
        ProspectiveCandidateRegistry,
    )

    reference_registry = ProspectiveCandidateRegistry(
        run_id="old-run",
        preregistered_at="2026-05-02T00:00:00Z",
        candidates=[
            ProspectiveCandidate(
                candidate_id="PC-old-1",
                instance_id="I-old",
                instance_name="old lotus starch / PVA / attapulgite / H3PO4",
                preregistered_at="2026-05-02T00:00:00Z",
                components=["lotus starch", "PVA", "attapulgite", "H3PO4"],
            )
        ],
    )
    reference_path = _write_json(
        tmp_path / "old_registry.json",
        reference_registry.model_dump(mode="json"),
    )

    feedback = _feedback(
        [
            _feedback_record(
                candidate_id="PC-old-1",
                instance_id="I-old",
                measured_at="2026-05-09T00:00:00Z",
                validation_timing="prospective",
            )
        ]
    )
    feedback["provenance"] = {"agent_registry_path": str(reference_path)}
    feedback_path = _write_json(tmp_path / "experimental_feedback.json", feedback)

    report = run_s13(_registry(), tmp_path / "out", SimpleNamespace(), feedback_path=feedback_path)

    assert report.records[0].candidate_id == "PC-test-1"
    assert report.records[0].validation_timing == "prospective"
    assert report.candidate_links[0].claim_eligibility == "prospective_validation"
    assert any("timing_reference_registry" in w for w in report.feedback_warnings)


def test_s13_stale_instance_id_is_semantically_remapped(tmp_path):
    from s8_stage3.agents.s13_validation_binder import run_s13
    from s8_stage3.contracts.prospective import (
        ProspectiveCandidate,
        ProspectiveCandidateRegistry,
    )

    current_registry = ProspectiveCandidateRegistry(
        run_id="current-run",
        preregistered_at="2026-05-18T00:00:00Z",
        candidates=[
            ProspectiveCandidate(
                candidate_id="PC-current-wrong",
                instance_id="I-old",
                instance_name="starch / PVA / attapulgite / H3PO4",
                preregistered_at="2026-05-18T00:00:00Z",
                components=["starch", "PVA", "attapulgite", "H3PO4"],
            ),
            ProspectiveCandidate(
                candidate_id="PC-current-chito",
                instance_id="I-current",
                instance_name="Chitosan/organic-modified attapulgite/phosphoric acid composite",
                preregistered_at="2026-05-18T00:00:00Z",
                components=["chitosan", "phosphoric acid"],
            ),
        ],
    )
    reference_registry = ProspectiveCandidateRegistry(
        run_id="old-run",
        preregistered_at="2026-05-02T00:00:00Z",
        candidates=[
            ProspectiveCandidate(
                candidate_id="PC-old-1",
                instance_id="I-old",
                instance_name="old chitosan / clay / H3PO4",
                preregistered_at="2026-05-02T00:00:00Z",
                components=["chitosan", "attapulgite", "H3PO4"],
            )
        ],
    )
    reference_path = _write_json(
        tmp_path / "old_registry.json",
        reference_registry.model_dump(mode="json"),
    )
    feedback = _feedback(
        [
            _feedback_record(
                candidate_id="PC-old-1",
                instance_id="I-old",
                material_system="chitosan/PVA/attapulgite/H3PO4",
                chitosan_g=0.2,
                lotus_starch_g=0.0,
                measured_at="2026-05-09T00:00:00Z",
                validation_timing="prospective",
            )
        ]
    )
    feedback["provenance"] = {"agent_registry_path": str(reference_path)}
    feedback_path = _write_json(tmp_path / "experimental_feedback.json", feedback)

    report = run_s13(current_registry, tmp_path / "out", SimpleNamespace(), feedback_path=feedback_path)

    assert report.records[0].candidate_id == "PC-current-chito"
    assert report.records[0].validation_timing == "prospective"


def _write_s14_base(output_dir: Path, binding_links: list[dict]):
    _write_json(
        output_dir / "01_evidence" / "evidence_cards.json",
        {"evidence_cards": [{"card_id": "V2-E1", "support_metrics": {"v2_evidence_id": "EV1"}}]},
    )
    _write_json(
        output_dir / "04_mechanism" / "mechanism_card.json",
        {"mechanism_card": {"selected_hypothesis_id": "H1"}},
    )
    _write_json(
        output_dir / "11_candidate_registry" / "prospective_candidates.json",
        {"run_id": "run-test", "n_candidates": 1, "preregistered_at": "2026-05-18T00:00:00Z"},
    )
    _write_json(
        output_dir / "09_ranking" / "candidate_audit.json",
        {
            "n_candidates": 1,
            "source_term_audit_ok": True,
            "rows": [
                {
                    "instance_id": "I1",
                    "descriptor_claim_coverage": 0.9,
                    "n_element_descriptor_pairs": 2,
                    "bad_cited_paper_ids": [],
                }
            ],
        },
    )
    _write_json(
        output_dir / "09_ranking" / "ranking_robustness_v2.json",
        {
            "status": "ok",
            "stability_class": "stable",
            "top1_stability_rate": 0.9,
            "top3_jaccard_mean": 0.95,
            "recommended_wording_hint": "Single-winner wording is allowed with audit caveats.",
        },
    )
    _write_json(
        output_dir / "12_validation_binding" / "validation_binding_report.json",
        {"candidate_links": binding_links},
    )


def test_s14_validation_claim_gate_distinguishes_none_retro_prospective(tmp_path):
    from s8_stage3.agents.s14_claim_auditor import run_s14

    settings = SimpleNamespace(
        discovery_mode="broad_literature_pool_selection",
        final_audit=True,
    )

    none_dir = tmp_path / "none"
    _write_s14_base(none_dir, [])
    none_report = run_s14(none_dir, settings)
    assert next(i for i in none_report.claim_ladder if i.claim_level == "prospective_validation").is_supported is False
    assert next(i for i in none_report.claim_ladder if i.claim_level == "retrospective_validation").is_supported is False

    retro_dir = tmp_path / "retro"
    _write_s14_base(retro_dir, [{"candidate_id": "PC-test-1", "claim_eligibility": "retrospective_validation"}])
    retro_report = run_s14(retro_dir, settings)
    assert next(i for i in retro_report.claim_ladder if i.claim_level == "prospective_validation").is_supported is False
    assert next(i for i in retro_report.claim_ladder if i.claim_level == "retrospective_validation").is_supported is True

    pros_dir = tmp_path / "pros"
    _write_s14_base(pros_dir, [{"candidate_id": "PC-test-1", "claim_eligibility": "prospective_validation"}])
    pros_report = run_s14(pros_dir, settings)
    assert next(i for i in pros_report.claim_ladder if i.claim_level == "prospective_validation").is_supported is True


def test_s14_downgrades_transfer_claim_when_ranking_robustness_unstable(tmp_path):
    from s8_stage3.agents.s14_claim_auditor import run_s14

    _write_s14_base(tmp_path, [])
    _write_json(
        tmp_path / "09_ranking" / "ranking_robustness_v2.json",
        {
            "status": "ok",
            "stability_class": "unstable",
            "top1_stability_rate": 0.2,
            "top3_jaccard_mean": 0.3,
            "recommended_wording_hint": "Ranking is unstable; report candidates as hypotheses.",
        },
    )

    report = run_s14(
        tmp_path,
        SimpleNamespace(discovery_mode="broad_literature_pool_selection", final_audit=True),
    )
    transfer = next(i for i in report.claim_ladder if i.claim_level == "llm_transfer_candidate")

    assert transfer.is_supported is False
    assert any("ranking_robustness_v2" in b for b in report.publication_blockers)


def test_ranking_robustness_v2_writes_stability_fields_and_preserves_ranked_list(tmp_path):
    from s8_stage3.scoring.ranking_robustness_v2 import run_ranking_robustness_v2

    ranked_path = _write_json(
        tmp_path / "09_ranking" / "ranked_top_list.json",
        {"ranked_candidates": [{"instance_id": "I1"}]},
    )
    before = ranked_path.read_text(encoding="utf-8")
    _write_json(
        tmp_path / "09_ranking" / "candidate_audit.json",
        {
            "rows": [
                {
                    "instance_id": "I1",
                    "instance_name": "one",
                    "descriptor_claim_coverage": 0.9,
                    "citation_validity": 0.9,
                    "novelty_score": 0.8,
                    "risk_score": 0.1,
                    "term_leakage_penalty": 0.0,
                    "prospective_status_score": 0.0,
                },
                {
                    "instance_id": "I2",
                    "instance_name": "two",
                    "descriptor_claim_coverage": 0.5,
                    "citation_validity": 0.7,
                    "novelty_score": 0.6,
                    "risk_score": 0.2,
                    "term_leakage_penalty": 0.0,
                    "prospective_status_score": 0.0,
                },
            ]
        },
    )

    summary = run_ranking_robustness_v2(output_dir=tmp_path, n_seeds=20, plot=False)

    assert (tmp_path / "09_ranking" / "ranking_robustness_v2.json").exists()
    assert summary["status"] == "ok"
    assert summary["stability_class"] in {"stable", "moderately_stable", "unstable"}
    assert "unstable_candidates" in summary
    assert "recommended_wording_hint" in summary
    assert ranked_path.read_text(encoding="utf-8") == before


def test_pipeline_manifest_records_ranking_robustness_summary(tmp_path):
    from s8_stage3.orchestrator.pipeline import Pipeline, StepResult, StepStatus

    _write_json(
        tmp_path / "09_ranking" / "ranking_robustness_v2.json",
        {
            "status": "ok",
            "stability_class": "stable",
            "top1_stability_rate": 0.8,
            "top3_jaccard_mean": 0.9,
            "recommended_wording_hint": "ok",
        },
    )

    class Gateway:
        def get_cost_summary(self):
            return {}

    pipeline = Pipeline(settings=object(), gateway=Gateway(), output_dir=tmp_path)
    pipeline.step_results = [StepResult("s10_instance_ranker", StepStatus.COMPLETED)]
    pipeline._write_run_manifest()
    manifest = json.loads((tmp_path / "run_manifest.json").read_text(encoding="utf-8"))

    assert manifest["ranking_robustness"]["stability_class"] == "stable"
    assert manifest["ranking_robustness"]["top1_stability_rate"] == 0.8
