# -*- coding: utf-8 -*-
from __future__ import annotations

import pytest

from backend_api.services.hardware_adapter import (
    PROJECT_ROOT,
    HardwareAdapter,
    _load_stage1_campaign_runtime,
)


def test_start_invalid_campaign_does_not_leave_adapter_running():
    adapter = HardwareAdapter()
    adapter._connected = True

    with pytest.raises(FileNotFoundError):
        adapter.start(sample_id="ATA-contract", campaign="missing_campaign_slug")

    assert adapter._running is False


def test_start_rejects_unsafe_sample_id_without_running():
    adapter = HardwareAdapter()
    adapter._connected = True

    with pytest.raises(ValueError):
        adapter.start(sample_id="ATA*contract")

    assert adapter._running is False


def test_start_rejects_unsafe_ao_folder_without_running():
    adapter = HardwareAdapter()
    adapter._connected = True

    with pytest.raises(ValueError):
        adapter.start(sample_id="ATA-contract", ao_folder="..\\bad")

    assert adapter._running is False


def test_start_rejects_state_path_outside_runs_without_running():
    adapter = HardwareAdapter()
    adapter._connected = True

    with pytest.raises(ValueError):
        adapter.start(
            sample_id="ATA-contract",
            state_path=str(PROJECT_ROOT / "online_experiment_state.json"),
        )

    assert adapter._running is False


def test_campaign_runtime_rejects_path_outside_project():
    with pytest.raises(ValueError):
        _load_stage1_campaign_runtime(
            campaign_config=str(PROJECT_ROOT.parent / "outside_campaign.json"),
        )
