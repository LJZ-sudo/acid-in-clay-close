# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STAGE0_DIR = PROJECT_ROOT / "code" / "stage0_processing"
STAGE1_DIR = PROJECT_ROOT / "stage1_optimization"
for path in (STAGE0_DIR, STAGE1_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import process_ao_stage0 as ao  # noqa: E402
from campaign_memory.memory_manager import MemoryManager  # noqa: E402
from canonical_input.campaign_parser import CampaignConfig  # noqa: E402
from canonical_input.state0_parser import State0Parser, _safe_eval_formula  # noqa: E402
from closed_loop.metrics_aggregator import build_closed_loop_metrics  # noqa: E402


CAMPAIGN = STAGE1_DIR / "campaigns" / "attapulgite_aice_campaign.json"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _campaign_config() -> CampaignConfig:
    return CampaignConfig(str(CAMPAIGN))


def test_stage0_offline_failure_does_not_write_contract_outputs(tmp_path, monkeypatch):
    folder = tmp_path / "ao_in"
    folder.mkdir()
    calls = []

    monkeypatch.setattr(ao, "AO_NORMALIZED_ROOT", tmp_path / "normalized")
    monkeypatch.setattr(ao, "AO_OUTPUT_ROOT", tmp_path / "stage0_out")
    monkeypatch.setattr(ao, "SAMPLE_BUS_ROOT", tmp_path / "sample_bus")
    monkeypatch.setattr(ao, "_parse_rn", lambda _folder: (0.1, 0.7))
    monkeypatch.setattr(ao, "_parse_geometry", lambda _folder: ao.Geometry(thickness_cm=0.083, area_cm2=1.96))
    monkeypatch.setattr(ao, "_normalize_folder_inputs", lambda *_args, **_kw: (["point1.txt"], []))
    monkeypatch.setattr(ao, "_run_stage0_offline", lambda *_args, **_kw: (False, tmp_path / "stage0_run.log"))
    monkeypatch.setattr(ao, "_write_experiment_metadata", lambda *_args, **_kw: calls.append("metadata"))
    monkeypatch.setattr(ao, "_write_stage0_result_bundle", lambda *_args, **_kw: calls.append("bundle"))
    monkeypatch.setattr(ao, "_sync_to_sample_bus", lambda *_args, **_kw: calls.append("sample_bus"))

    result = ao.process_ao_folder(folder, sample_id="ATA-test")

    assert result["status"] == "failed_stage0_run"
    assert calls == []


def test_stage0_bundle_marks_missing_recipe_not_objective_ready(tmp_path):
    out_dir = tmp_path / "stage0"
    _write_json(out_dir / "aggregated_results.json", {
        "success": True,
        "measurements": [{
            "temperature_K": 298.15,
            "temperature_C": 25.0,
            "success": True,
            "rb_ohm": 10.0,
            "conductivity_S_per_cm": 1e-3,
        }],
    })
    _write_json(out_dir / "arrhenius_analysis.json", {
        "success": True,
        "n_segments": 1,
        "segments": [{"Ea_eV": 0.12, "n_points": 5, "temp_range_K": [273.15, 323.15]}],
    })
    metadata = {
        "material_system": "Attapulgite AiCE",
        "source_mode": "real",
        "source_system": "attapulgite_aice",
        "parameters": {"R": None, "N": None},
        "sample_meta": {"acid_type": "H3PO4", "clay_type": "attapulgite", "thickness_cm": 0.083, "area_cm2": 1.96},
        "geometry_source": {"thickness_cm_source": "recipe_text", "area_cm2_source": "default_coin_cell"},
    }

    bundle_path = ao._write_stage0_result_bundle(out_dir, "ATA-missing-rn", metadata, rebuild_ok=True)
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))

    assert bundle["bundle_meta"]["stage0_bundle_schema_version"] == "0.2.0"
    assert bundle["data_validity"]["recipe_ok"] is False
    assert bundle["data_validity"]["objective_ready"] is False
    assert "recipe_R_or_N_missing" in bundle["data_validity"]["invalid_reasons"]


def test_stage1_parameters_fall_back_to_bundle_recipe(tmp_path):
    _write_json(tmp_path / "stage0_result_bundle.json", {
        "recipe": {"R": 0.35, "N": 0.95, "acid_type": "H3PO4", "clay_type": "attapulgite"},
    })

    params = State0Parser(str(tmp_path), campaign_config=_campaign_config()).extract_experiment_parameters()

    assert params == {"R": 0.35, "N": 0.95}


def test_stage1_rejects_metadata_bundle_parameter_conflict(tmp_path):
    _write_json(tmp_path / "experiment_metadata.json", {"parameters": {"R": 0.35, "N": 0.95}})
    _write_json(tmp_path / "stage0_result_bundle.json", {"recipe": {"R": 0.5, "N": 0.95}})

    parser = State0Parser(str(tmp_path), campaign_config=_campaign_config())

    with pytest.raises(ValueError, match="parameter conflict"):
        parser.extract_experiment_parameters()


def test_stage1_missing_recipe_parameter_returns_no_real_parameters(tmp_path):
    _write_json(tmp_path / "stage0_result_bundle.json", {"recipe": {"R": 0.35, "N": None}})

    parser = State0Parser(str(tmp_path), campaign_config=_campaign_config())

    assert parser.extract_experiment_parameters() == {}
    assert "experiment_parameters_missing" in parser.get_validity_flags()


def test_stage1_missing_ea_marks_objective_invalid_without_penalty(tmp_path):
    _write_json(tmp_path / "stage0_result_bundle.json", {
        "sample_id": "ATA-invalid-ea",
        "data_validity": {
            "stage0_ok": True,
            "arrhenius_ok": False,
            "recipe_ok": True,
            "geometry_ok": True,
            "objective_ready": False,
            "invalid_reasons": ["arrhenius_invalid_or_rebuild_failed"],
        },
        "recipe": {"R": 0.35, "N": 0.95},
        "eis_points": [{
            "scan_dir": "ao_flat_temperature_series",
            "T_K": 298.15,
            "T_C": 25.0,
            "status": "OK",
            "sigma_S_cm": 1e-3,
        }],
        "arrhenius": {"success": False},
    })

    metrics = State0Parser(str(tmp_path), campaign_config=_campaign_config()).extract_objective_metrics()

    assert metrics["objective_valid"] is False
    assert "combined_score" not in metrics
    assert "arrhenius_invalid_or_rebuild_failed" in metrics["objective_invalid_reasons"]


def test_memory_manager_deduplicates_sample_id_and_bundle_hash(tmp_path):
    manager = MemoryManager(str(tmp_path / "history.json"), campaign_name="Attapulgite_AiCE_Wide_Temp_Optimization")

    first = manager.add_trial(
        parameters={"R": 0.35, "N": 0.95},
        objectives={"combined_score": -2.0},
        metadata={"sample_id": "ATA-001", "input_bundle_hash": "hash-1"},
    )
    second = manager.add_trial(
        parameters={"R": 0.35, "N": 0.95},
        objectives={"combined_score": -2.0},
        metadata={"sample_id": "ATA-001", "input_bundle_hash": "hash-1"},
    )

    assert first == second == 1
    assert len(manager.get_history()) == 1


def test_stage1_objective_formula_uses_ast_allowlist():
    value = _safe_eval_formula(
        "math.log10(conductivity_room_temp_S_cm) - 3.0 * ea_high_temp_eV",
        {"conductivity_room_temp_S_cm": 1e-3, "ea_high_temp_eV": 0.1},
    )

    assert value == pytest.approx(-3.3)
    with pytest.raises(ValueError):
        _safe_eval_formula("__import__('os').system('echo bad')", {})


def test_closed_loop_metrics_rewrites_via_temp_replace(tmp_path):
    output_dir = tmp_path / "out"
    history_db = tmp_path / "history.json"
    _write_json(history_db, {
        "campaign_name": "Attapulgite_AiCE_Wide_Temp_Optimization",
        "trials": [
            {
                "trial_id": 1,
                "parameters": {"R": 0.35, "N": 0.95},
                "objectives": {"combined_score": -2.0, "conductivity_room_temp_S_cm": 1e-3},
            }
        ],
    })
    _write_json(output_dir / "closed_loop_metrics.json", {"stale": True})

    metrics = build_closed_loop_metrics(
        output_dir=output_dir,
        history_db_path=history_db,
        campaign_name="Attapulgite_AiCE_Wide_Temp_Optimization",
        campaign_config={"source_tag": "attapulgite_aice"},
    )

    written = json.loads((output_dir / "closed_loop_metrics.json").read_text(encoding="utf-8"))
    assert written["campaign_name"] == "Attapulgite_AiCE_Wide_Temp_Optimization"
    assert written["source_system"] == "attapulgite_aice"
    assert written["n_history_trials"] == 1
    assert "stale" not in written
    assert metrics["n_history_trials"] == 1
    assert not (output_dir / "closed_loop_metrics.json.tmp").exists()


def test_chi_executor_close_is_idempotent():
    mod = pytest.importorskip("stage0_measurement.modules.automation.chi_executor")
    executor = mod.ChiExecutor(config={"wait_times": {}, "measurement_time_mapping": {}})

    assert executor.close() is None
    assert executor.close() is None
