import json
from pathlib import Path

import pytest


def _write_json(path: Path, data: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _v2_seed() -> dict:
    return {
        "schema_version": "0.2.0",
        "seed_id": "seed-helper-test",
        "source_system": "s8_reference",
        "source_mode": "retrospective",
        "stage3_ready": True,
        "stage3_blocking_reasons": [],
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
        "evidence_units": [
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
    }


def test_s01_audits_legacy_csv_rows(tmp_path):
    from s8_stage3.agents.s01_data_auditor import run_s01

    rows = [
        {"sample_id": "S1", "T_K": "250.0"},
        {"sample_id": "S1", "T_K": "260.0"},
        {"sample_id": "", "T_K": "270.0"},
        {"sample_id": "S2", "T_K": "not-a-number"},
    ]

    audit = run_s01(rows, {"min_points_per_sample": 2}, tmp_path)

    assert audit["status"] == "warn"
    assert audit["input_row_count"] == 4
    assert audit["clean_row_count"] == 2
    assert audit["skipped_row_count"] == 2
    assert (tmp_path / "00_preprocess" / "data_audit.json").exists()
    clean_rows = json.loads((tmp_path / "00_preprocess" / "clean_rows.json").read_text(encoding="utf-8"))
    assert len(clean_rows["rows"]) == 2


def test_s01_fails_when_no_clean_rows_remain(tmp_path):
    from s8_stage3.agents.s01_data_auditor import run_s01

    with pytest.raises(RuntimeError, match="Data audit failed"):
        run_s01([{"sample_id": "", "T_K": ""}], {}, tmp_path)

    audit = json.loads((tmp_path / "00_preprocess" / "data_audit.json").read_text(encoding="utf-8"))
    assert audit["status"] == "fail"


def test_s02_wraps_stage2_seed_adapter_and_writes_artifacts(tmp_path):
    from s8_stage3.agents.s02_segment_builder import run_s02

    seed_path = _write_json(tmp_path / "stage2" / "stage3_seed.json", _v2_seed())

    bundle = run_s02(
        csv_path=None,
        data_profile_path=None,
        execution_plan_path=None,
        atlas_path=None,
        visualization_manifest_path=None,
        output_dir=tmp_path / "stage3",
        stage2_seed_v2_path=seed_path,
        strict_real_input=True,
    )

    assert bundle.stage2_seed_v2_path == str(seed_path)
    assert bundle.seed_sample_summaries[0].composition_r == pytest.approx(1.25)
    assert (tmp_path / "stage3" / "00_seed_real" / "seed_bundle_real.json").exists()
    assert (tmp_path / "stage3" / "00_seed_real" / "real_seed_diagnostics.json").exists()
