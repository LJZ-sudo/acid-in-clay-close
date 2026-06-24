# -*- coding: utf-8 -*-
"""M1-8 契约测试:/api/jobs/threshold_sweep 与 /api/jobs/ablation 已接真实 v2 产物。

锁定:不再返回 placeholder "not yet implemented";结构正确;读真实 stage0_v2 产物。
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from backend_api.main import fastapi_app


def test_threshold_sweep_not_placeholder() -> None:
    client = TestClient(fastapi_app)
    resp = client.post("/api/jobs/threshold_sweep")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["job"] == "threshold_sweep"
    # 旧 placeholder 文案必须消失
    assert "not yet implemented" not in body.get("message", "")
    assert "generated" in body
    # 产物存在时应有结果 + 风险计数;缺失时应给生成命令(诚实)
    if body["generated"]:
        assert isinstance(body["results"], list)
        assert "rb_routing_risk_counts" in body["summary"]
    else:
        assert body["generate_commands"]


def test_ablation_not_placeholder_and_has_rb_strategies() -> None:
    client = TestClient(fastapi_app)
    resp = client.post("/api/jobs/ablation")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["job"] == "ablation"
    assert "not yet implemented" not in body.get("message", "")
    if body["generated"]:
        assert body["results"]
        row = body["results"][0]
        # Rb 策略消融必须含 4 条轨迹
        assert set(row["rb_strategy_ablation"].keys()) == {
            "legacy_routed", "fixed_plateau", "fixed_zero_crossing", "method_ensemble"}
        assert "robust_regression_ablation" in row
    else:
        assert body["generate_commands"]
