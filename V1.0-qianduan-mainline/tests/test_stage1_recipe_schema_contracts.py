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
    assert recipe["source_mode"] == "history_only"
    assert recipe["source_tag"] == campaign["source_tag"]
    assert Path(recipe["history_db"]).resolve() == history_db
    assert "input_bundle_hash" in recipe
    assert recipe["created_at"]
    assert recipe["recipe"]["recommended_parameters"]["R"] is not None
    assert recipe["recipe"]["recommended_parameters"]["N"] is not None
    assert isinstance(recipe["optimizer_suggestion"], dict)
    assert isinstance(recipe["optimizer_vs_llm_delta"], dict)
    assert isinstance(recipe["safety_box"], dict)
