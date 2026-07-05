# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CAMPAIGN = PROJECT_ROOT / "stage1_optimization" / "campaigns" / "attapulgite_aice_campaign.json"
RECIPE = PROJECT_ROOT / "stage1_optimization" / "output" / "attapulgite_aice" / "next_experiment_recipe.json"


def test_current_attapulgite_next_recipe_uses_v020_schema():
    campaign = json.loads(CAMPAIGN.read_text(encoding="utf-8"))
    recipe = json.loads(RECIPE.read_text(encoding="utf-8"))
    history_db = (PROJECT_ROOT / "stage1_optimization" / campaign["storage"]["history_db"]).resolve()

    assert recipe["schema_version"] == "0.2.0"
    assert recipe["artifact_type"] == "stage1_next_experiment_recipe"
    assert Path(recipe["campaign_config"]).resolve() == CAMPAIGN.resolve()
    # 生产者无关契约:该文件可由 suggest_next.py(source_mode="history_only")或
    # run_optimization_loop.py(真机/回放 loop,source_mode ∈ {real,replay,virtual_oracle})生成。
    # 断言合法枚举 + 与 metadata 自洽,而非写死单一生产者的 mode(避免真机产物被误判为回归)。
    valid_modes = {"history_only", "real", "replay", "virtual_oracle"}
    assert recipe["source_mode"] in valid_modes
    meta_mode = (recipe.get("metadata") or {}).get("source_mode")
    if meta_mode is not None:
        assert meta_mode == recipe["source_mode"]  # 顶层与 metadata 自洽
    # source_mode=="real" 是真机产物 → 必须带真实 input_bundle_hash(可溯源、非占位)。
    if recipe["source_mode"] == "real":
        assert recipe["input_bundle_hash"]
    assert recipe["source_tag"] == campaign["source_tag"]
    assert Path(recipe["history_db"]).resolve() == history_db
    assert "input_bundle_hash" in recipe
    assert recipe["created_at"]
    assert recipe["recipe"]["recommended_parameters"]["R"] is not None
    assert recipe["recipe"]["recommended_parameters"]["N"] is not None
    assert isinstance(recipe["optimizer_suggestion"], dict)
    assert isinstance(recipe["optimizer_vs_llm_delta"], dict)
    assert isinstance(recipe["safety_box"], dict)
