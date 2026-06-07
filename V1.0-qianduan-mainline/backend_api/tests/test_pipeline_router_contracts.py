# -*- coding: utf-8 -*-
from __future__ import annotations

from fastapi.testclient import TestClient

from backend_api.main import fastapi_app


def test_pipeline_status_is_explicitly_legacy_disabled() -> None:
    client = TestClient(fastapi_app)

    resp = client.get("/api/pipeline/status")

    assert resp.status_code == 200
    body = resp.json()
    assert body["stage2"]["status"] == "disabled"
    assert "run_pipeline.py" in body["stage2"]["message"]


def test_pipeline_trigger_does_not_call_missing_run_pipeline() -> None:
    client = TestClient(fastapi_app)

    resp = client.post("/api/pipeline/stage2")

    assert resp.status_code == 410
    detail = resp.json()["detail"]
    assert detail["status"] == "disabled"
    assert detail["run_pipeline_exists"] is False
    assert "stage2_statistics/main_agent.py" in detail["current_entrypoints"]["stage2"]
