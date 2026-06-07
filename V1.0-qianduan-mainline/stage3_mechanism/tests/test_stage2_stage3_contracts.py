import json
import sys
from pathlib import Path

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _write_json(path: Path, data: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _v2_seed(*, stage3_ready: bool = True, evidence_units: list[dict] | None = None) -> dict:
    return {
        "schema_version": "0.2.0",
        "seed_id": "seed-test",
        "source_system": "s8_reference",
        "source_mode": "retrospective",
        "stage3_ready": stage3_ready,
        "stage3_blocking_reasons": [] if stage3_ready else ["test_blocker"],
        "input_files": {"input_csv": "s8_input.csv"},
        "input_hashes": {"input_csv": "abc123"},
        "sample_summary": [
            {
                "sample_id": "S1",
                "R": 1.25,
                "N": 2.5,
                "n_temperature_points": 6,
                "quality_flags": [],
            }
        ],
        "segment_fits": [
            {
                "segment_id": "S1_seg0",
                "sample_id": "S1",
                "T_min_K": 240.0,
                "T_max_K": 320.0,
                "n_points": 6,
                "segment_label": "single",
                "arrhenius_ea_eV": 0.21,
                "arrhenius_ln_sigma0": -3.0,
            }
        ],
        "evidence_units": evidence_units
        if evidence_units is not None
        else [
            {
                "evidence_id": "EV1",
                "layer": "composition_trend",
                "title": "V2 evidence",
                "statement": "Stage2 V2 evidence is the authoritative Stage3 input.",
                "strength": "moderate",
                "confidence": 0.72,
                "supporting_sample_ids": ["S1"],
                "supporting_segment_ids": ["S1_seg0"],
                "supporting_metrics": {"n_samples": 1},
                "safe_for_stage3": True,
            }
        ],
        "stage3_guardrails": {
            "do_not_overclaim": ["Do not overclaim mechanism certainty."],
            "allowed_inference": ["Use evidence for hypothesis generation."],
        },
    }


def test_stage2_sample_summary_marks_missing_rn():
    from stage2_statistics.core.sample_aggregator import build_sample_summaries

    df = pd.DataFrame(
        {
            "sample_id": ["S1", "S1"],
            "T_K": [250.0, 260.0],
            "sigma": [1e-4, 2e-4],
        }
    )

    [summary] = build_sample_summaries(df)

    assert summary.R is None
    assert summary.N is None
    assert "missing_R" in summary.quality_flags
    assert "missing_N" in summary.quality_flags


def test_stage2_seed_blocks_stage3_when_rn_missing():
    from stage2_statistics.core.schema_v2 import (
        ModelComparisonSummary,
        MorphologySummary,
        SampleSummary,
        TemperatureSegment,
    )
    from stage2_statistics.core.stage3_seed_builder import build_stage3_seed

    seed = build_stage3_seed(
        run_id="test-run",
        summaries=[
            SampleSummary(
                sample_id="S1",
                R=None,
                N=2.5,
                n_temperature_points=6,
                quality_flags=["missing_R"],
            )
        ],
        segments=[
            TemperatureSegment(
                segment_id="S1_seg0",
                sample_id="S1",
                T_min_K=240.0,
                T_max_K=320.0,
                n_points=6,
                segment_label="single",
                arrhenius_ea_eV=0.21,
            )
        ],
        trends=[],
        model_summary=ModelComparisonSummary(
            n_samples_total=1,
            n_samples_with_fit=1,
            best_model_counts={"Arrhenius": 1},
        ),
        mn_result={"strength": "tentative"},
        morphology_summary=MorphologySummary(n_samples_total=1),
        input_files={"input_csv": "s8_input.csv"},
        input_hashes={"input_csv": "abc123"},
    )

    assert seed.schema_version == "0.2.0"
    assert seed.source_system == "s8_reference"
    assert seed.source_mode == "retrospective"
    assert seed.input_hashes["input_csv"] == "abc123"
    assert seed.stage3_ready is False
    assert any(reason.startswith("missing_R_or_N:S1") for reason in seed.stage3_blocking_reasons)


def test_stage3_resolver_uses_one_canonical_directory(monkeypatch, tmp_path):
    from s8_stage3.adapters import input_resolver

    canonical = tmp_path / "canonical"
    legacy = tmp_path / "legacy"
    _write_json(canonical / "stage3_seed.json", _v2_seed())
    legacy.mkdir()
    for name in [
        "s8_input.csv",
        "data_profile.json",
        "execution_plan.json",
        "s8_evidence_atlas.json",
        "visualization_manifest.json",
    ]:
        (legacy / name).write_text("{}" if name.endswith(".json") else "sample_id,T_K\n", encoding="utf-8")

    monkeypatch.setattr(
        input_resolver,
        "_candidate_dirs",
        lambda stage2_output_dir=None: [("cli", canonical), ("legacy", legacy)],
    )

    resolved = input_resolver.resolve_inputs()

    assert resolved.input_dir == canonical
    assert resolved.stage2_seed_v2_path == canonical / "stage3_seed.json"
    assert resolved.csv_path == canonical / "s8_input.csv"
    assert resolved.strict_real_input is True


def test_stage3_resolver_requires_explicit_legacy_fallback(monkeypatch, tmp_path):
    from s8_stage3.adapters import input_resolver

    legacy = tmp_path / "legacy"
    legacy.mkdir()
    for name in [
        "s8_input.csv",
        "data_profile.json",
        "execution_plan.json",
        "s8_evidence_atlas.json",
        "visualization_manifest.json",
    ]:
        (legacy / name).write_text("{}" if name.endswith(".json") else "sample_id,T_K\n", encoding="utf-8")

    monkeypatch.setattr(
        input_resolver,
        "_candidate_dirs",
        lambda stage2_output_dir=None: [("legacy", legacy)],
    )

    with pytest.raises(FileNotFoundError, match="No canonical stage3_seed.json"):
        input_resolver.resolve_inputs()

    resolved = input_resolver.resolve_inputs(allow_legacy_atlas=True)
    assert resolved.input_dir == legacy
    assert resolved.strict_real_input is False
    assert resolved.allow_legacy_atlas is True
    assert resolved.atlas_path == legacy / "s8_evidence_atlas.json"


def test_v2_adapter_is_authoritative_and_ignores_conflicting_csv(tmp_path):
    from s8_stage3.adapters.stage2_seed_adapter import build_seed_bundle_from_stage2

    seed_path = _write_json(tmp_path / "stage3_seed.json", _v2_seed())
    csv_path = tmp_path / "s8_input.csv"
    csv_path.write_text("sample_id,R,N,T_K,sigma\nS1,9,9,300,0.001\n", encoding="utf-8")

    bundle, diagnostics = build_seed_bundle_from_stage2(
        csv_path=csv_path,
        data_profile_path=None,
        execution_plan_path=None,
        atlas_path=None,
        stage2_seed_v2_path=seed_path,
        strict_real_input=True,
    )

    assert diagnostics["input_mode"] == "stage2_seed_v2"
    assert bundle.seed_sample_summaries[0].composition_r == pytest.approx(1.25)
    assert bundle.seed_sample_summaries[0].composition_n == pytest.approx(2.5)
    assert bundle.seed_composition_nodes[0].r == pytest.approx(1.25)
    assert bundle.stage2_seed_v2_path == str(seed_path)


def test_v2_adapter_rejects_not_ready_or_missing_rn_in_strict_mode(tmp_path):
    from s8_stage3.adapters.stage2_seed_adapter import build_seed_bundle_from_stage2

    not_ready_path = _write_json(tmp_path / "not_ready" / "stage3_seed.json", _v2_seed(stage3_ready=False))
    with pytest.raises(RuntimeError, match="not Stage3-ready"):
        build_seed_bundle_from_stage2(None, None, None, None, stage2_seed_v2_path=not_ready_path)

    missing_rn = _v2_seed()
    missing_rn["sample_summary"][0]["R"] = None
    missing_rn_path = _write_json(tmp_path / "missing_rn" / "stage3_seed.json", missing_rn)
    with pytest.raises(RuntimeError, match="missing R/N"):
        build_seed_bundle_from_stage2(None, None, None, None, stage2_seed_v2_path=missing_rn_path)


def test_s03_strict_real_rejects_empty_v2_evidence(tmp_path):
    from s8_stage3.agents.s03_evidence_builder import run_s03
    from s8_stage3.contracts.seed import Stage3SeedBundle

    seed = Stage3SeedBundle(
        bundle_id="real-test",
        source_mode="real",
        stage2_seed_v2=_v2_seed(evidence_units=[]),
    )

    with pytest.raises(RuntimeError, match="zero usable Stage2 V2 evidence"):
        run_s03(seed, tmp_path, strict_real_input=True)


def test_s03_preserves_v2_supporting_metrics(tmp_path):
    from s8_stage3.agents.s03_evidence_builder import run_s03
    from s8_stage3.contracts.seed import Stage3SeedBundle

    seed = Stage3SeedBundle(
        bundle_id="real-test",
        source_mode="real",
        stage2_seed_v2=_v2_seed(),
    )

    bundle = run_s03(seed, tmp_path, strict_real_input=True)

    card = next(c for c in bundle.evidence_cards if c.card_id == "V2-E1")
    assert card.support_metrics["n_samples"] == "1"
    assert card.support_metrics["v2_evidence_id"] == "EV1"


def test_sanitizer_does_not_warn_missing_ea_for_vtf_segments():
    from s8_stage3.contracts.seed import SeedSegment, Stage3SeedBundle
    from s8_stage3.pre_llm.seed_sanitizer import sanitize_seed

    seed = Stage3SeedBundle(
        bundle_id="real-test",
        source_mode="real",
        seed_segments=[
            SeedSegment(
                segment_id="S1_vtf",
                sample_id="S1",
                t_min=240.0,
                t_max=320.0,
                n_points=6,
                fit_type="vtf",
                representative_ea=None,
            )
        ],
    )

    digest = sanitize_seed(seed)
    flag_types = [flag["flag_type"] for flag in digest["sanitization_flags"]]
    assert "missing_ea" not in flag_types


def test_pipeline_step_list_uses_state_machine_source():
    from s8_stage3.orchestrator.pipeline import Pipeline
    from s8_stage3.orchestrator.state_machine import EXECUTABLE_STEPS

    pipeline = Pipeline(settings=object(), gateway=object(), output_dir=Path.cwd())

    assert pipeline._resolve_steps() == EXECUTABLE_STEPS
    assert pipeline._resolve_steps() is not EXECUTABLE_STEPS
    assert pipeline._resolve_steps()[-1] == "s11_report_compiler"
    assert pipeline._resolve_steps()[:2] == [
        "s03_evidence_builder",
        "s04_hypothesis_generator",
    ]


def test_pipeline_manifest_records_output_dir(tmp_path):
    from s8_stage3.orchestrator.pipeline import Pipeline, StepResult, StepStatus

    class Gateway:
        def get_cost_summary(self):
            return {}

    pipeline = Pipeline(settings=object(), gateway=Gateway(), output_dir=tmp_path)
    pipeline.step_results = [StepResult("s03_evidence_builder", StepStatus.COMPLETED)]
    pipeline._write_run_manifest()

    manifest = json.loads((tmp_path / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["output_dir"] == str(tmp_path)
    assert manifest["selected_steps"] == ["s03_evidence_builder"]
