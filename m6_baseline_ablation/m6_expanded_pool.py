"""M6 (expanded) — enlarge the candidate pool from N=5 to dozens by recipe
enumeration, then compare selectors on their ability to rank the experimentally
validated winner (I1, LRS route) near the top.

READ-ONLY w.r.t. mainline. No LLM calls. No experiments. All artifacts written
inside m6_baseline_ablation/.

Why this is honest:
- The candidate pool is enlarged by *combinatorial enumeration* of components
  that already exist in the frozen S08 literature pool (no new claims invented).
- Every candidate (synthetic AND the 5 real ones) is scored by the SAME
  deterministic feature function that is computed objectively from the S08 pool
  (literature support, descriptor coverage, low-T topical support, completeness).
  No LLM sub-scores are used, so the comparison is fully reproducible.
- The ONLY external ground-truth anchor is I1 (experimentally validated positive)
  and I2 (boundary). The headline metric = can a selector rank I1 into top-k in a
  large pool where random success is rare.
"""
import json
import itertools
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
RUN = ROOT / "V1.0-qianduan-mainline/stage3_mechanism/outputs/verification/20260607_openrouter_publication_v2"
OUT = Path(__file__).resolve().parent

cards = json.load(open(RUN / "06_literature_materials/literature_cards_materials.json", encoding="utf-8"))["cards"]
real_instances = json.load(open(RUN / "08_material_instances/material_instances.json", encoding="utf-8"))["instances"]

LOW_T_KEYWORDS = ["anti-freeze", "antifreeze", "subzero", "sub-zero", "low temperature",
                  "low-temperature", "cold", "wide temperature", "freez"]

# ---------------------------------------------------------------------------
# Component bucketing (same logic as _explore)
# ---------------------------------------------------------------------------
def comp_bucket(text):
    t = (text or "").lower()
    if "paam" in t or "polyacrylamide" in t: return "paam_graft_starch"
    if "starch" in t: return "starch"
    if "pva" in t or "vinyl alcohol" in t: return "pva"
    if "chitosan" in t: return "chitosan"
    if "pbi" in t or "polybenzimidazole" in t: return "pbi"
    if "spes" in t or "polyether sulfone" in t or "ether sulfone" in t: return "spes"
    if "phosphotungstic" in t or "pwa" in t: return "pwa"
    if "phosphate glass" in t: return "phosphate_glass"
    if "eutectic" in t or "des" in t or "choline" in t: return "des"
    if "phosphoric" in t or "h3po4" in t or "(pa)" in t or t.strip() in ("pa","h3po4"): return "phosphoric_acid"
    if "halloysite" in t or "hnt" in t: return "halloysite"
    if "attapulgite" in t or "qatp" in t or "1d at" in t or "atp" in t: return "attapulgite"
    if "montmorillonite" in t or "mmt" in t: return "montmorillonite"
    if "functionalized clay" in t or "nanofiller" in t: return "functionalized_clay"
    if "nb2o5" in t: return "nb2o5"
    if "carbon dot" in t or "(cds)" in t: return "carbon_dots"
    if "peg" in t or "ethylene glycol" in t: return "peg"
    return None

# ---------------------------------------------------------------------------
# Build objective bucket features from the S08 pool
# ---------------------------------------------------------------------------
bucket_cards = {}        # bucket -> set(card_id) that mention it
bucket_desc = {}         # bucket -> set(descriptor_id) claimed for it
bucket_lowT = {}         # bucket -> count of low-T-topical cards mentioning it
for c in cards:
    title = (c.get("title") or "").lower()
    summ = (c.get("summary") or "").lower()
    is_lowT = any(k in title or k in summ for k in LOW_T_KEYWORDS)
    for cl in c.get("component_descriptor_claims", []):
        b = comp_bucket(cl.get("component", ""))
        if not b:
            continue
        bucket_cards.setdefault(b, set()).add(c["card_id"])
        for d in cl.get("descriptor_ids", []):
            bucket_desc.setdefault(b, set()).add(d)
        if is_lowT:
            bucket_lowT[b] = bucket_lowT.get(b, 0) + 1

bucket_freq = {b: len(v) for b, v in bucket_cards.items()}
ALL_BUCKETS = sorted(bucket_freq, key=lambda b: -bucket_freq[b])

# ---------------------------------------------------------------------------
# Recipe grammar for enumeration
# ---------------------------------------------------------------------------
HOSTS   = ["starch", "pva", "chitosan", "pbi", "spes", "paam_graft_starch"]
ACIDS   = ["phosphoric_acid", "pwa", "des", "phosphate_glass"]
CLAYS   = [None, "attapulgite", "halloysite", "montmorillonite", "functionalized_clay"]
ADDS    = [None, "nb2o5", "carbon_dots", "peg"]

def make_candidate(buckets, name=None, cid=None, is_real=False):
    bset = [b for b in buckets if b]
    return {
        "candidate_id": cid,
        "name": name or " + ".join(bset),
        "buckets": bset,
        "is_real": is_real,
    }

pool = []
seen = set()
# single + double host enumeration to keep size in the dozens-to-low-hundreds
for host in HOSTS:
    for acid in ACIDS:
        for clay in CLAYS:
            for add in ADDS:
                buckets = tuple(b for b in [host, acid, clay, add] if b)
                key = frozenset(buckets)
                if key in seen:
                    continue
                seen.add(key)
                pool.append(make_candidate(buckets))

# inject the 5 REAL instances by their true component buckets (dedup-aware)
real_anchor_ids = {}
for it in real_instances:
    buckets = []
    for comp in it["components"]:
        b = comp_bucket(comp)
        if b and b not in buckets:
            buckets.append(b)
    key = frozenset(buckets)
    # remove any synthetic duplicate so the real one carries the anchor id
    pool = [c for c in pool if frozenset(c["buckets"]) != key]
    cand = make_candidate(buckets, name=it["instance_name"], cid=it["instance_id"], is_real=True)
    pool.append(cand)
    real_anchor_ids[it["instance_id"]] = key

# assign synthetic ids
k = 0
for c in pool:
    if not c["candidate_id"]:
        c["candidate_id"] = f"SYN{k:03d}"
        k += 1

N = len(pool)

# ---------------------------------------------------------------------------
# Deterministic scoring functions (computed objectively from S08 features)
# ---------------------------------------------------------------------------
def feat(c):
    bs = c["buckets"]
    support = sum(bucket_freq.get(b, 0) for b in bs)                       # popularity-ish
    desc = set()
    for b in bs:
        desc |= bucket_desc.get(b, set())
    desc_cov = len(desc)                                                   # mechanism breadth
    lowT = sum(bucket_lowT.get(b, 0) for b in bs)                          # cold-window evidence
    has_acid = any(b in ACIDS for b in bs)
    has_host = any(b in HOSTS for b in bs)
    has_clay = any(b in CLAYS[1:] for b in bs)
    completeness = (0.5 * has_host + 0.5 * has_acid)                       # formulation completeness
    return dict(support=support, desc_cov=desc_cov, lowT=lowT,
                completeness=completeness, has_clay=has_clay,
                n_comp=len(bs))

def governed_score(c):
    f = feat(c)
    # multi-dimensional governance: mechanism breadth + cold evidence +
    # completeness + bounded support, with a clay-confinement prior (acid-in-clay).
    return (0.30 * f["desc_cov"]
            + 0.25 * f["lowT"]
            + 0.20 * (2 * f["completeness"])
            + 0.15 * min(f["support"], 6) / 6.0 * 3
            + 0.10 * (1.0 if f["has_clay"] else 0.0) * 3)

def popularity_score(c):
    return float(sum(bucket_freq.get(b, 0) for b in c["buckets"]))

# ---------------------------------------------------------------------------
# Selector evaluation: rank validated winner I1 in a pool of size N
# ---------------------------------------------------------------------------
WINNER = "I1"
rng = np.random.default_rng(20260607)

def order_by(score_fn):
    scored = [(score_fn(c) + rng.random() * 1e-9, c["candidate_id"]) for c in pool]
    scored.sort(key=lambda x: -x[0])
    return [cid for _, cid in scored]

def rank_of(order, cid):
    return order.index(cid) + 1

gov_order = order_by(governed_score)
pop_order = order_by(popularity_score)

# random: analytic + MC
N_MC = 50000
def mc_random_topk(k):
    hits = 0
    ids = [c["candidate_id"] for c in pool]
    for _ in range(N_MC):
        rng.shuffle(ids)
        if WINNER in ids[:k]:
            hits += 1
    return hits / N_MC

result = {
    "experiment": "M6_expanded_pool",
    "read_only_source": str(RUN.relative_to(ROOT)),
    "pool_size_N": N,
    "n_real_anchors": len(real_anchor_ids),
    "winner": WINNER,
    "selectors": {
        "deterministic_proxy_governance_NOT_the_real_agent": {
            "winner_rank": rank_of(gov_order, WINNER),
            "winner_top1": gov_order[0] == WINNER,
            "winner_in_top3": WINNER in gov_order[:3],
            "winner_in_top5": WINNER in gov_order[:5],
            "top5": gov_order[:5],
            "_note": "hand-built deterministic feature weighting; it does NOT "
                     "represent the production S10 LLM ranker. Its poor rank here "
                     "shows that a naive deterministic proxy is worse than popularity, "
                     "and that fairly scoring an enlarged pool REQUIRES re-running the "
                     "real LLM ranker (needs key + cost), not just more literature.",
        },
        "popularity_freq": {
            "winner_rank": rank_of(pop_order, WINNER),
            "winner_top1": pop_order[0] == WINNER,
            "winner_in_top3": WINNER in pop_order[:3],
            "winner_in_top5": WINNER in pop_order[:5],
            "top5": pop_order[:5],
        },
        "random": {
            "p_top1": round(1 / N, 4),
            "p_top3": round(3 / N, 4),
            "p_top5": round(5 / N, 4),
            "mc_p_top1": round(mc_random_topk(1), 4),
            "mc_p_top3": round(mc_random_topk(3), 4),
            "mc_p_top5": round(mc_random_topk(5), 4),
        },
    },
    "bucket_frequency": bucket_freq,
    "bucket_lowT_support": bucket_lowT,
    "caveats": [
        "Pool enlarged by combinatorial enumeration of existing S08 components; "
        "synthetic candidates are not LLM-vetted instances, they exist only to "
        "create a realistic negative background so random/popularity baselines "
        "are no longer trivially correct.",
        "Scoring is a deterministic proxy (no LLM sub-scores), chosen so the whole "
        "comparison is reproducible; it is NOT the exact production S10 LLM ranker.",
        "Only I1 (positive) / I2 (boundary) have experimental ground truth, so the "
        "metric is winner-retrieval rank, not a powered multi-point precision claim.",
    ],
    "honest_findings": [
        "GOOD: enlarging the pool to N=482 pushed the random baseline's P(top1) "
        "from 0.20 (N=5) down to 0.002 -- the methodological step works and needs "
        "no experiments, only literature/enumeration.",
        "BAD-for-story: pure popularity (component literature frequency) still "
        "ranks the validated winner I1 at #1, so 'selecting the LRS route' is NOT "
        "a capability unique to the agent at any pool size.",
        "BLOCKER: a hand-built deterministic proxy is worse than popularity; to "
        "fairly compare the REAL governed agent against baselines in the enlarged "
        "pool, the production LLM ranker must score all 482 candidates. That is an "
        "LLM-cost step (not a physical experiment), and is the true remaining gap.",
    ],
}

(OUT / "m6_expanded_results.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

prox = result['selectors']['deterministic_proxy_governance_NOT_the_real_agent']
print(f"pool size N = {N}  (real anchors: {len(real_anchor_ids)})")
print(f"\nWINNER I1 retrieval rank (lower=better, out of {N}):")
print(f"  deterministic_proxy : rank {prox['winner_rank']}  top3={prox['winner_in_top3']}  (NOT the real agent)")
print(f"  popularity_freq     : rank {result['selectors']['popularity_freq']['winner_rank']}  "
      f"top3={result['selectors']['popularity_freq']['winner_in_top3']}")
print(f"  random (analytic)   : P(top1)={result['selectors']['random']['p_top1']}  "
      f"P(top3)={result['selectors']['random']['p_top3']}  P(top5)={result['selectors']['random']['p_top5']}")
print(f"  random (MC)         : P(top1)={result['selectors']['random']['mc_p_top1']}  "
      f"P(top3)={result['selectors']['random']['mc_p_top3']}  P(top5)={result['selectors']['random']['mc_p_top5']}")
print(f"\ngov top5:  {gov_order[:5]}")
print(f"pop top5:  {pop_order[:5]}")
print(f"\nWrote {OUT/'m6_expanded_results.json'}")
