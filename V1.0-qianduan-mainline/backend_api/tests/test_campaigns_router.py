# -*- coding: utf-8 -*-
"""Smoke tests for routers/campaigns.py.

Runs against the real on-disk Stage1 data — no mocking. As of 2026-06-07 the
S8 sepiolite mother-system campaign has been archived to
experiments/three_pillars/pillar1_transfer_agent/s8_acid_in_clay_mother_system/, so the
only campaign shipped under stage1_optimization/campaigns/ is
`attapulgite_aice_campaign`.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend_api.main import fastapi_app  # noqa: E402

CAMPAIGN_SLUG = "attapulgite_aice_campaign"


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(fastapi_app)


def test_list_campaigns(client: TestClient) -> None:
    resp = client.get("/api/campaigns")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    slugs = {row["slug"] for row in body["campaigns"]}
    assert CAMPAIGN_SLUG in slugs


def test_get_campaign_meta(client: TestClient) -> None:
    resp = client.get(f"/api/campaigns/{CAMPAIGN_SLUG}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["objective"]["target"] == "combined_score"
    assert body["objective"]["goal"] == "maximize"
    assert "R" in body["bounds"] and "N" in body["bounds"]


def test_get_trials(client: TestClient) -> None:
    resp = client.get(f"/api/campaigns/{CAMPAIGN_SLUG}/trials")
    assert resp.status_code == 200
    body = resp.json()
    assert body["n_trials"] >= 1
    first = body["trials"][0]
    assert "parameters" in first and "objectives" in first
    assert isinstance(body["pareto_trial_ids"], list)


def test_get_next_recipe(client: TestClient) -> None:
    resp = client.get(f"/api/campaigns/{CAMPAIGN_SLUG}/next-recipe")
    # On-disk file may be absent in some clones; allow either 200 or 404 but
    # ensure the wrapper shape if present.
    assert resp.status_code in (200, 404)
    if resp.status_code == 200:
        body = resp.json()
        assert body["requested_campaign"] == CAMPAIGN_SLUG
        assert "recipe" in body
        # 公共包装字段（两种来源都应有）
        assert "history_db" in body
        assert "output_dir" in body
        assert "next_recipe_path" in body
        assert "recipe_source" in body
        # schema 诊断仅出现在 ondisk 单目标 recipe 分支；
        # 当冻结的线 B 官方 MOBO+LLM recipe 权威时，走 official 形状（无 schema 诊断）。
        if body["recipe_source"] == "ondisk_next_experiment_recipe":
            assert "schema_valid" in body
            assert isinstance(body["schema_warnings"], list)
        else:
            assert body["recipe_source"] == "line_b_official_mobo_llm"
            assert "optimizer_vs_llm_delta" in body["recipe"]
        rec = body["recipe"]["recipe"]
        assert "recommended_parameters" in rec


def test_get_health(client: TestClient) -> None:
    resp = client.get(f"/api/campaigns/{CAMPAIGN_SLUG}/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["n_history_trials"] >= 1
    assert "limitations" in body


def test_unknown_campaign_404(client: TestClient) -> None:
    resp = client.get("/api/campaigns/this-does-not-exist")
    assert resp.status_code == 404


def test_invalid_name_400(client: TestClient) -> None:
    # The router rejects names with characters outside [A-Za-z0-9._-].
    # FastAPI will URL-decode the slash; instead use a name that contains a banned char directly.
    resp = client.get("/api/campaigns/bad name with space")
    assert resp.status_code in (400, 404)  # 404 if FastAPI rejects the path before our handler
    resp2 = client.get("/api/campaigns/has*star")
    assert resp2.status_code in (400, 404)
