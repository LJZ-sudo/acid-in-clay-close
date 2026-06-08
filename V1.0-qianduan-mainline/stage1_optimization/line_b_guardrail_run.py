# -*- coding: utf-8 -*-
"""Line B — real BO+LLM guardrail recommendation (Steps 4-6, read-only).

Mirrors run_optimization_loop.py Steps 4-6 WITHOUT ingesting a fresh Stage0
measurement and WITHOUT mutating the history DB:

  Step 4  left brain  : MOBOOptimizer(ParEGO).suggest_next()  (seed=20260608)
  Step 5  right brain : StrategyPlanner.decide_with_fallback() -> real gpt-5.4
  Step 6  safety      : SafetyValidator.validate()

"current_metrics" is taken from the most-recent trial in the locked history
(the agent's last-observed state). This produces the official guardrailed next
R/N for the prospective freeze. Live OpenRouter call required.

Run from stage1_optimization/:
    python line_b_guardrail_run.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from canonical_input.campaign_parser import CampaignConfig
from canonical_input.design_space import ParameterSpace
from campaign_memory.memory_manager import MemoryManager
from agents.llm_client import LLMClient
from agents.strategy_planner import StrategyPlanner
from safety.safety_validator import SafetyValidator
from run_optimization_loop import build_stage1_optimizer

ROOT = Path(__file__).parent
CAMPAIGN = ROOT / "campaigns" / "attapulgite_aice_campaign.json"
FROZEN_SEED = 20260608


def main() -> None:
    cfg = CampaignConfig(str(CAMPAIGN))
    mem = MemoryManager(
        db_path=str(ROOT / "campaign_memory" / "history_db_attapulgite.json"),
        campaign_name=cfg.campaign_name,
    )
    pspace = ParameterSpace(cfg)

    # Step 4 — left brain (frozen-seed MOBO)
    opt = build_stage1_optimizer("mobo", pspace, mem, cold_start_threshold=5,
                                 optimizer_seed=FROZEN_SEED)
    raw = opt.suggest_next()
    prov = opt.get_provenance()
    print("=" * 78)
    print(f"[Step4] MOBO raw suggestion (seed={FROZEN_SEED}): "
          f"R={raw['R']:.4f} N={raw['N']:.4f}")
    print(f"        mode={prov.get('mode')} weights={[round(w,3) for w in prov.get('weights',[])]}")

    # current context = latest trial in locked history (agent's last-observed state)
    hist = mem.get_history()
    last = hist[-1]
    current_metrics = dict(last.get("objectives") or {})
    print(f"[ctx ] latest trial params={last.get('parameters')} objectives keys={list(current_metrics)}")

    # Step 5 — right brain (real LLM guardrail)
    llm = LLMClient(temperature=0.0, max_tokens=8000)
    ok = llm.test_connection()
    print(f"[Step5] LLM connection ok={ok}  model={llm.model}  base={llm.base_url}")
    planner = StrategyPlanner(campaign_config=cfg, memory_manager=mem, llm_client=llm)
    recipe = planner.decide_with_fallback(
        current_metrics=current_metrics,
        optimizer_suggestion=raw,
        fallback_to_optimizer=True,
        physical_features=None,
    )
    llm_failed = any("LLM" in str(w) and ("失败" in str(w) or "fail" in str(w).lower())
                     for w in (recipe.warnings or []))

    # Step 6 — safety
    safety = SafetyValidator(cfg).validate(recipe.recommended_parameters, physical_features={})

    print("=" * 78)
    print("OFFICIAL LINE-B NEXT RECIPE (BO + LLM guardrail):")
    print(f"   raw MOBO     : R={raw['R']:.4f} N={raw['N']:.4f}")
    print(f"   LLM final    : {recipe.recommended_parameters}")
    print(f"   llm_used     : {not llm_failed}  confidence={getattr(recipe,'confidence_score',None)}")
    print(f"   safety_box   : {json.dumps(safety.to_dict(), ensure_ascii=False)}")
    print("-" * 78)
    print("LLM reasoning:")
    print(getattr(recipe, "reasoning", "") or "(none)")
    if recipe.warnings:
        print("-" * 78)
        print("warnings:", recipe.warnings)
    if getattr(recipe, "llm_provenance", None) or getattr(llm, "get_provenance", None):
        try:
            print("-" * 78)
            print("llm_provenance:", json.dumps(llm.get_provenance(), ensure_ascii=False))
        except Exception:
            pass
    print("=" * 78)


if __name__ == "__main__":
    main()
