# -*- coding: utf-8 -*-
"""Line B — Round 2 prospective MOBO+LLM recipe + Round-1 Pareto/score_v3 status.

Read-only (does NOT mutate the history DB). Mirrors line_b_guardrail_run.py but:

  * uses a NEW documented seed (``FROZEN_SEED_R2 = 20260610``) for round 2,
  * computes the just-measured trial-9 (R=0.28/N=0.96) ``score_v3`` + Pareto
    status against the protocol-consistent primary set (T2..T9), filling the
    multi-objective artifact that the single-objective morning loop did not emit,
  * writes a SEPARATE sidecar ``official_recipe_round2.json`` so the immutable
    round-1 record (``official_recipe.json``, frozen 2026-06-08) is never touched.

The recipe is frozen ONLY after this file is committed + pushed (server
timestamp); ``frozen_at`` / ``freeze_commit`` are intentionally left blank here
and back-filled into the preregistration after push. No synthesis before push.

Run from stage1_optimization/:
    python line_b_round2_run.py
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
from run_optimization_loop import build_stage1_optimizer, MOBO_HISTORY_OBJECTIVE_KEYS
from optimizers.mobo_optimizer import (
    Objective,
    annotate_pareto,
    pareto_front_indices,
    score_v3,
)

ROOT = Path(__file__).parent
CAMPAIGN = ROOT / "campaigns" / "attapulgite_aice_campaign.json"
FROZEN_SEED_R2 = 20260610
PRIMARY_EXCLUDE_TRIAL_IDS = {1}  # T1 excluded from protocol-consistent primary set


def _objectives():
    return [
        Objective(MOBO_HISTORY_OBJECTIVE_KEYS["sigma_key"], "max"),
        Objective(MOBO_HISTORY_OBJECTIVE_KEYS["ea_high_key"], "min"),
        Objective(MOBO_HISTORY_OBJECTIVE_KEYS["ea_low_excess_key"], "min"),
    ]


def main() -> None:
    cfg = CampaignConfig(str(CAMPAIGN))
    mem = MemoryManager(
        db_path=str(ROOT / "campaign_memory" / "history_db_attapulgite.json"),
        campaign_name=cfg.campaign_name,
    )
    pspace = ParameterSpace(cfg)
    objs = _objectives()
    sk = MOBO_HISTORY_OBJECTIVE_KEYS["sigma_key"]
    ek = MOBO_HISTORY_OBJECTIVE_KEYS["ea_high_key"]
    lk = MOBO_HISTORY_OBJECTIVE_KEYS["ea_low_excess_key"]

    hist = mem.get_history()

    # -- Part 1: trial-9 score_v3 + Pareto status vs primary set (T2..T9) ----- #
    primary = [t for t in hist if t.get("trial_id") not in PRIMARY_EXCLUDE_TRIAL_IDS]
    pts = []
    for t in primary:
        o = t.get("objectives") or {}
        if all(k in o for k in (sk, ek, lk)):
            pts.append({sk: float(o[sk]), ek: float(o[ek]), lk: float(o[lk])})
    front_idx = set(pareto_front_indices(pts, objs))
    annotated = annotate_pareto(pts, objs)

    print("=" * 78)
    print("[Part1] Pareto / score_v3 over protocol-consistent primary set (T2..T9):")
    for t, row in zip(primary, annotated):
        tid = t.get("trial_id")
        p = t.get("parameters") or {}
        sv3 = score_v3({"sigma_RT": row[sk], "Ea_high": row[ek], "ea_low_excess": row[lk]})
        print(f"   T{tid}: R={p.get('R')} N={p.get('N')}  "
              f"sigma={row[sk]:.4e} Ea_high={row[ek]:.4f} ea_low_excess={row[lk]:.4f}  "
              f"score_v3={sv3:.4f}  -> {row['pareto_status']}")
    last = primary[-1]
    last_obj = last.get("objectives") or {}
    last_sv3 = score_v3({"sigma_RT": float(last_obj[sk]),
                         "Ea_high": float(last_obj[ek]),
                         "ea_low_excess": float(last_obj[lk])})
    last_status = annotated[-1]["pareto_status"]
    print(f"   => latest trial T{last.get('trial_id')} (R={last.get('parameters',{}).get('R')}, "
          f"N={last.get('parameters',{}).get('N')}): score_v3={last_sv3:.4f}, "
          f"pareto_status={last_status}, pareto_front_size={len(front_idx)}")

    # -- Part 2: round-2 MOBO suggestion + real LLM guardrail + safety -------- #
    opt = build_stage1_optimizer("mobo", pspace, mem, cold_start_threshold=5,
                                 optimizer_seed=FROZEN_SEED_R2)
    raw = opt.suggest_next()
    prov = opt.get_provenance()
    print("=" * 78)
    print(f"[Step4] MOBO raw suggestion (seed={FROZEN_SEED_R2}): "
          f"R={raw['R']:.4f} N={raw['N']:.4f}")
    print(f"        mode={prov.get('mode')} weights={[round(w,3) for w in prov.get('weights',[])]} "
          f"pareto_front_size={prov.get('pareto_front_size')}")

    current_metrics = dict(last_obj)
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
    safety = SafetyValidator(cfg).validate(recipe.recommended_parameters, physical_features={})

    print("=" * 78)
    print("OFFICIAL LINE-B ROUND-2 NEXT RECIPE (MOBO + LLM guardrail):")
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
    llm_prov = {}
    try:
        llm_prov = llm.get_provenance()
        print("-" * 78)
        print("llm_provenance:", json.dumps(llm_prov, ensure_ascii=False))
    except Exception:
        pass
    print("=" * 78)

    # -- write round-2 sidecar (separate file; round-1 record untouched) ------ #
    sidecar = (ROOT.parent.parent / "research" / "prospective"
               / "line_B_mobo_closed_loop" / "official_recipe_round2.json")
    payload = {
        "line": "B",
        "title": "Prospective MOBO + LLM closed loop (Attapulgite) — Round 2",
        "campaign": cfg.campaign_name,
        "round": 2,
        "frozen_at": "",          # back-filled after git push (server timestamp)
        "freeze_commit": "",      # back-filled after git push
        "seed": FROZEN_SEED_R2,
        "reproducer": "stage1_optimization/line_b_round2_run.py",
        "round1_outcome": {
            "sample_id": last.get("metadata", {}).get("sample_id"),
            "R": last.get("parameters", {}).get("R"),
            "N": last.get("parameters", {}).get("N"),
            "sigma_RT_S_cm": float(last_obj[sk]),
            "Ea_high_eV": float(last_obj[ek]),
            "ea_low_excess_eV": float(last_obj[lk]),
            "score_v3": round(last_sv3, 4),
            "pareto_status": last_status,
            "pareto_front_size_primary_set": len(front_idx),
            "note": "Single-objective morning loop ingested T9; this is the "
                    "multi-objective (score_v3/Pareto) reading over T2..T9.",
        },
        "raw_mobo": {"R": round(raw["R"], 4), "N": round(raw["N"], 4),
                     "mode": prov.get("mode"), "weights": prov.get("weights"),
                     "pareto_front_size": prov.get("pareto_front_size")},
        "llm_final": recipe.recommended_parameters,
        "llm_used": not llm_failed,
        "confidence": getattr(recipe, "confidence_score", None),
        "safety_passed": bool(safety.to_dict().get("passed")),
        "llm_provenance": {"provider": "openrouter", **llm_prov},
        "reasoning_zh": getattr(recipe, "reasoning", ""),
        "allowed_claim": "Round 2 前瞻性地检验执行层能否在多目标(MOBO/ParEGO)下扩展 "
                         "电导/Ea Pareto 前沿；raw=MOBO、final=LLM 物理修正、safety 通过。",
        "forbidden_claim": "BO+LLM 发现了 LRS；BO+LLM 证明了普适最优；"
                           "事后改分把历史 campaign 变成成功的闭环发现。",
    }
    sidecar.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[sidecar] wrote {sidecar}")


if __name__ == "__main__":
    main()
