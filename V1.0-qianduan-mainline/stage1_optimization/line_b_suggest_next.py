# -*- coding: utf-8 -*-
"""Line B — prospective MOBO next-R/N suggester (read-only, reproducible).

Builds the SAME objects as run_optimization_loop.py (CampaignConfig ->
MemoryManager -> ParameterSpace -> build_stage1_optimizer('mobo')) and calls
the ParEGO suggester with a FIXED seed so the recommendation is reproducible
and can be frozen into the preregistration before any measurement.

This does NOT run hardware, does NOT call the LLM, and does NOT mutate the
history DB. It only reads the locked history and asks the optimizer.

Run from stage1_optimization/:
    python line_b_suggest_next.py
"""
from __future__ import annotations

import math
from pathlib import Path

from canonical_input.campaign_parser import CampaignConfig
from canonical_input.design_space import ParameterSpace
from campaign_memory.memory_manager import MemoryManager
from run_optimization_loop import build_stage1_optimizer, MOBO_HISTORY_OBJECTIVE_KEYS
from optimizers.mobo_optimizer import locked_v2_objectives, pareto_front_indices

ROOT = Path(__file__).parent
CAMPAIGN = ROOT / "campaigns" / "attapulgite_aice_campaign.json"
FROZEN_SEED = 20260608  # the seed that defines THE prospective recommendation

K_SIGMA = MOBO_HISTORY_OBJECTIVE_KEYS["sigma_key"]
K_EAH = MOBO_HISTORY_OBJECTIVE_KEYS["ea_high_key"]
K_EAL = MOBO_HISTORY_OBJECTIVE_KEYS["ea_low_excess_key"]


def combined_score(o: dict) -> float:
    return math.log10(o[K_SIGMA]) - 3.0 * o[K_EAH] - 0.5 * o[K_EAL]


def main() -> None:
    cfg = CampaignConfig(str(CAMPAIGN))
    mem = MemoryManager(
        db_path=str(ROOT / "campaign_memory" / "history_db_attapulgite.json"),
        campaign_name=cfg.campaign_name,
    )
    pspace = ParameterSpace(cfg)
    objectives = locked_v2_objectives(**MOBO_HISTORY_OBJECTIVE_KEYS)

    hist = mem.get_history()
    print("=" * 78)
    print(f"Campaign      : {cfg.campaign_name}")
    print(f"Search domain : R in [0, 1.04], N in [0.5, 1.3]")
    print(f"History trials: {len(hist)}")
    print("-" * 78)
    print(f"{'#':>2}  {'R':>6} {'N':>6}  {'sigma_RT':>10} {'Ea_high':>8} {'ea_lo_exc':>9} {'score':>8}")

    P, valid = [], []
    for i, t in enumerate(hist, 1):
        p = t.get("parameters") or {}
        o = t.get("objectives") or {}
        if not all(k in o for k in (K_SIGMA, K_EAH, K_EAL)):
            print(f"{i:>2}  {p.get('R'):>6} {p.get('N'):>6}  (missing objective keys -> skipped)")
            continue
        sc = combined_score(o)
        print(f"{i:>2}  {p['R']:>6.3f} {p['N']:>6.3f}  {o[K_SIGMA]:>10.3e} {o[K_EAH]:>8.3f} {o[K_EAL]:>9.3f} {sc:>8.3f}")
        P.append({obj.key: float(o[obj.key]) for obj in objectives})
        valid.append((i, p, o, sc))

    # Current Pareto front (from measured history)
    pf = pareto_front_indices(P, objectives)
    print("-" * 78)
    print(f"Pareto front (measured): {len(pf)} member(s)")
    for idx in pf:
        i, p, o, sc = valid[idx]
        print(f"   #{i}  R={p['R']:.3f} N={p['N']:.3f}  sigma_RT={o[K_SIGMA]:.3e} "
              f"Ea_high={o[K_EAH]:.3f} ea_lo_exc={o[K_EAL]:.3f}")

    # FROZEN recommendation (fixed seed -> reproducible)
    opt = build_stage1_optimizer("mobo", pspace, mem, cold_start_threshold=5,
                                 optimizer_seed=FROZEN_SEED)
    rec = opt.suggest_next()
    prov = opt.get_provenance()
    print("=" * 78)
    print(f"PROSPECTIVE MOBO RECOMMENDATION (seed={FROZEN_SEED}):")
    print(f"   R = {rec['R']:.4f}   N = {rec['N']:.4f}")
    print(f"   mode={prov.get('mode')}  n_train_points={prov.get('n_train_points')}  "
          f"pareto_front_size={prov.get('pareto_front_size')}")
    print(f"   ParEGO weights [sigma,Ea_high,ea_lo_exc] = "
          f"{[round(w,3) for w in prov.get('weights', [])]}")
    print("-" * 78)
    print("Suggestion spread across ParEGO weight draws (robustness, seeds 1-8):")
    for s in range(1, 9):
        o2 = build_stage1_optimizer("mobo", pspace, mem, cold_start_threshold=5, optimizer_seed=s)
        r2 = o2.suggest_next()
        w2 = o2.get_provenance().get("weights", [])
        print(f"   seed {s}:  R={r2['R']:.4f} N={r2['N']:.4f}   w={[round(w,2) for w in w2]}")
    print("=" * 78)


if __name__ == "__main__":
    main()
