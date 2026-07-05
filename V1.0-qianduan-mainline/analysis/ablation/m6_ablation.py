"""M6 baseline ablation for the evidence-constrained transfer/ranking agent.

READ-ONLY w.r.t. mainline: this script only *reads* the frozen 20260607 stage3
outputs and writes its own artifacts inside V1.0-qianduan-mainline/analysis/ablation/. It does not
call any LLM and does not modify any stage1/stage3 code, data, or registry.

Three sub-experiments:
  M6-A  Selector comparison  : can each selector rank the experimentally
                               validated winner (I1, the lotus/starch route)
                               into top-1? Baselines = random / popularity
                               (component literature-frequency proxy) / shallow
                               naive-LLM proxy (novelty + citation only) vs the
                               full governed weighted score.
  M6-B  Leave-one-weight-out : remove each governance dimension, recompute the
                               ranking, and measure whether I1 stays top-1 and
                               how much the order changes (rank correlation).
  M6-C  Robustness reference : reuse the existing 200-seed weight-jitter result.

Ground truth: experiment validated I1 (lotus-root-starch / LRS family route) as
the positive winner; I2 (chitosan) is the boundary control. No experimental
ground truth exists for I3/I4/I5, so the primary metric is "rank the validated
winner I1 at top-1". Statistical caveats are reported in the output.
"""
import json
import itertools
from pathlib import Path

import numpy as np

ROOT = next(_p for _p in Path(__file__).resolve().parents if _p.name == "V1.0-qianduan-mainline").parent
RUN = ROOT / "V1.0-qianduan-mainline/stage3_mechanism/outputs/verification/20260607_openrouter_publication_v2"
OUT = Path(__file__).resolve().parent

# ----------------------------------------------------------------------------
# Load frozen sub-scores (deterministic == llm here; delta logged as ~0)
# ----------------------------------------------------------------------------
rer = json.load(open(RUN / "09_ranking/deterministic_reranked_top_list.json", encoding="utf-8"))
cands = rer["ranked_candidates"]

robust = json.load(open(RUN / "09_ranking/ranking_robustness_v2.json", encoding="utf-8"))
WEIGHTS = robust["default_weights"]  # canonical governance weights

cards = json.load(open(RUN / "06_literature_materials/literature_cards_materials.json", encoding="utf-8"))["cards"]
instances = json.load(open(RUN / "08_material_instances/material_instances.json", encoding="utf-8"))["instances"]

WINNER = "I1"          # experimentally validated positive (LRS route)
BOUNDARY = "I2"        # boundary control (chitosan)

# Map sub-score json keys -> weight keys
SUBSCORE_OF = {
    "mechanism_fit":               lambda c: c["mechanism_fit_score"],
    "evidence_quality":            lambda c: c["evidence_quality_score"],
    "formulation_completeness":    lambda c: c["formulation_completeness_score"],
    "low_temperature_plausibility":lambda c: c["low_temperature_plausibility_score"],
    "processability":              lambda c: c["processability_score"],
    "novelty":                     lambda c: c["novelty_score"],
    "citation":                    lambda c: c["citation_validity"],
    "one_minus_risk":              lambda c: 1.0 - c["risk_score"],
}


def governed_score(c, weights):
    return sum(weights[k] * SUBSCORE_OF[k](c) for k in weights)


def rank_by(score_fn, rng=None, jitter=0.0):
    """Return list of instance_ids ordered best->worst. Ties broken randomly
    (with optional rng) so degenerate selectors don't get a free deterministic win."""
    scored = []
    for c in cands:
        s = score_fn(c)
        if rng is not None:
            s = s + rng.normal(0, jitter) if jitter else s + rng.random() * 1e-9
        scored.append((s, c["instance_id"]))
    # stable-ish: sort by score desc, random tiny tiebreak already applied
    scored.sort(key=lambda x: -x[0])
    return [iid for _, iid in scored]


# ----------------------------------------------------------------------------
# Verify reproduction of frozen total scores
# ----------------------------------------------------------------------------
repro = {}
for c in cands:
    g = governed_score(c, WEIGHTS)
    repro[c["instance_id"]] = {
        "recomputed": round(g, 4),
        "frozen": round(c["deterministic_total_score"], 4),
        "match": abs(g - c["deterministic_total_score"]) < 1e-6,
    }

# ----------------------------------------------------------------------------
# Popularity proxy: component literature frequency from the S08 pool
# ----------------------------------------------------------------------------
def comp_bucket(text):
    t = text.lower()
    # order matters: PAAm-g-starch before bare 'starch'
    if "paam" in t or "polyacrylamide" in t:
        return "paam_graft"
    if "starch" in t:
        return "starch"
    if "pva" in t or "vinyl alcohol" in t:
        return "pva"
    if "chitosan" in t:
        return "chitosan"
    if "phosphoric" in t or "h3po4" in t or "(pa)" in t or t.strip() == "pa":
        return "phosphoric_acid"
    if "halloysite" in t or "hnt" in t:
        return "halloysite"
    if "attapulgite" in t or "qatp" in t or "1d at" in t:
        return "attapulgite"
    if "nb2o5" in t:
        return "nb2o5"
    if "montmorillonite" in t or "mmt" in t:
        return "mmt"
    if "phosphate glass" in t:
        return "phosphate_glass"
    if "des" in t or "eutectic" in t:
        return "des"
    return t.strip()[:24]

bucket_freq = {}
for c in cards:
    seen = set()
    for cl in c.get("component_descriptor_claims", []):
        b = comp_bucket(cl.get("component", ""))
        if b and b not in seen:      # count once per card
            seen.add(b)
            bucket_freq[b] = bucket_freq.get(b, 0) + 1

inst_components = {it["instance_id"]: it["components"] for it in instances}

def popularity_score(c):
    iid = c["instance_id"]
    comps = inst_components.get(iid, [])
    return float(sum(bucket_freq.get(comp_bucket(x), 0) for x in comps))

def naive_shallow_score(c):
    # naive LLM proxy: prefers "novel-sounding & well-cited" only, no mechanism/
    # evidence/low-T/processability governance.
    return 0.5 * c["novelty_score"] + 0.5 * c["citation_validity"]

# ----------------------------------------------------------------------------
# M6-A  Selector comparison (Monte Carlo for tie-breaking / random)
# ----------------------------------------------------------------------------
N_MC = 20000
rng = np.random.default_rng(20260607)

def mc_topk_hit(score_fn, k, target, jitter_random=False):
    hits = 0
    for _ in range(N_MC):
        if jitter_random:
            order = rank_by(lambda c: 0.0, rng=rng, jitter=0.0)  # pure random via tiny noise
            # pure random permutation:
            ids = [c["instance_id"] for c in cands]
            rng.shuffle(ids)
            order = ids
        else:
            order = rank_by(score_fn, rng=rng)
        if target in order[:k]:
            hits += 1
    return hits / N_MC

selectors = {
    "random":              {"fn": None, "random": True},
    "popularity_freq":     {"fn": popularity_score, "random": False},
    "naive_shallow_llm":   {"fn": naive_shallow_score, "random": False},
    "full_governed_agent": {"fn": lambda c: governed_score(c, WEIGHTS), "random": False},
}

m6a = {}
for name, spec in selectors.items():
    top1 = mc_topk_hit(spec["fn"], 1, WINNER, jitter_random=spec["random"])
    top2 = mc_topk_hit(spec["fn"], 2, WINNER, jitter_random=spec["random"])
    top2_both = 0
    # also track both winner+boundary in top2
    for _ in range(N_MC):
        if spec["random"]:
            ids = [c["instance_id"] for c in cands]; rng.shuffle(ids); order = ids
        else:
            order = rank_by(spec["fn"], rng=rng)
        if WINNER in order[:2] and BOUNDARY in order[:2]:
            top2_both += 1
    m6a[name] = {
        "p_winner_top1": round(top1, 4),
        "p_winner_top2": round(top2, 4),
        "p_winner_and_boundary_top2": round(top2_both / N_MC, 4),
    }

# analytic random reference for sanity
n = len(cands)
m6a_analytic_random = {
    "p_winner_top1": round(1 / n, 4),
    "p_winner_top2": round(2 / n, 4),
    "p_winner_and_boundary_top2": round((2 * 1) / (n * (n - 1)), 4),  # ordered pair / perms
}

# ----------------------------------------------------------------------------
# M6-B  Leave-one-weight-out ablation
# ----------------------------------------------------------------------------
def spearman(a, b):
    ra = {v: i for i, v in enumerate(a)}
    rb = {v: i for i, v in enumerate(b)}
    keys = list(ra.keys())
    x = np.array([ra[k] for k in keys], float)
    y = np.array([rb[k] for k in keys], float)
    x -= x.mean(); y -= y.mean()
    denom = (np.sqrt((x**2).sum()) * np.sqrt((y**2).sum()))
    return float((x * y).sum() / denom) if denom else 1.0

baseline_order = rank_by(lambda c: governed_score(c, WEIGHTS), rng=np.random.default_rng(1))
m6b = {"baseline_order": baseline_order, "leave_one_out": {}}
for drop in WEIGHTS:
    w2 = {k: v for k, v in WEIGHTS.items() if k != drop}
    # renormalize remaining weights to keep scale comparable
    s = sum(w2.values())
    w2n = {k: v / s for k, v in w2.items()}
    order = rank_by(lambda c: governed_score(c, w2n), rng=np.random.default_rng(1))
    m6b["leave_one_out"][drop] = {
        "dropped_weight": WEIGHTS[drop],
        "new_top1": order[0],
        "winner_still_top1": order[0] == WINNER,
        "new_order": order,
        "spearman_vs_baseline": round(spearman(baseline_order, order), 4),
    }

# ----------------------------------------------------------------------------
# M6-C  Robustness reference (existing artifact)
# ----------------------------------------------------------------------------
m6c = {
    "source": "09_ranking/ranking_robustness_v2.json",
    "n_seeds": robust["n_seeds"],
    "weight_jitter_sigma": robust["weight_jitter_sigma"],
    "top1_stability_rate": robust["top1_stability_rate"],
    "top3_jaccard_mean": robust["top3_jaccard_mean"],
    "spearman_to_default_mean": robust["spearman_to_default"]["mean"],
    "default_top1": robust["default_top1"],
}

# ----------------------------------------------------------------------------
# Assemble + persist
# ----------------------------------------------------------------------------
result = {
    "experiment": "M6_baseline_ablation",
    "generated_for": "Nature-Communications system-innovation angle stress test",
    "read_only_source": str(RUN.relative_to(ROOT)),
    "n_candidate_instances": n,
    "n_families": 3,
    "n_literature_cards": len(cards),
    "winner_instance": WINNER,
    "boundary_instance": BOUNDARY,
    "score_reproduction_check": repro,
    "component_literature_frequency": bucket_freq,
    "M6A_selector_comparison": {
        "n_monte_carlo": N_MC,
        "selectors": m6a,
        "analytic_random_reference": m6a_analytic_random,
    },
    "M6B_leave_one_weight_out": m6b,
    "M6C_robustness_reference": m6c,
    "statistical_caveats": [
        f"Candidate pool at the scoring stage is only N={n} instances (3 families); "
        "Monte-Carlo / analytic random baselines therefore have wide intervals.",
        f"Literature pool is {len(cards)} cards with NO citation counts available, so the "
        "'popularity' baseline is a component literature-frequency proxy, not true citations.",
        "Experimental ground truth exists only for I1 (positive) and I2 (boundary); "
        "I3/I4/I5 are unvalidated, so this is a mechanistic attribution, not a powered "
        "head-to-head superiority claim.",
    ],
}

(OUT / "m6_results.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

# Console summary
print("=== score reproduction (recomputed vs frozen) ===")
for k, v in repro.items():
    print(f"  {k}: {v['recomputed']} vs {v['frozen']}  match={v['match']}")
print("\n=== M6-A selector comparison (P winner I1 ranked) ===")
print(f"  {'selector':22s} {'top1':>7s} {'top2':>7s} {'I1&I2_top2':>11s}")
for name, v in m6a.items():
    print(f"  {name:22s} {v['p_winner_top1']:>7.3f} {v['p_winner_top2']:>7.3f} {v['p_winner_and_boundary_top2']:>11.3f}")
print(f"  {'(analytic random)':22s} {m6a_analytic_random['p_winner_top1']:>7.3f} "
      f"{m6a_analytic_random['p_winner_top2']:>7.3f} {m6a_analytic_random['p_winner_and_boundary_top2']:>11.3f}")
print("\n=== M6-B leave-one-weight-out (does I1 stay top1?) ===")
for drop, v in m6b["leave_one_out"].items():
    flag = "OK" if v["winner_still_top1"] else "FLIP -> " + v["new_top1"]
    print(f"  drop {drop:30s} w={v['dropped_weight']:.2f}  top1={v['new_top1']:3s} ({flag})  rho={v['spearman_vs_baseline']}")
print("\n=== M6-C robustness (existing 200-seed) ===")
print(f"  top1_stability_rate={m6c['top1_stability_rate']}  default_top1={m6c['default_top1']}")
print(f"\nWrote {OUT / 'm6_results.json'}")
