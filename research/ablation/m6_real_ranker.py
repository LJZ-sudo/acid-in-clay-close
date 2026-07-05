"""M6 (faithful) — score the enlarged candidate pool with the REAL production
ranking function, not a hand-rolled proxy.

Key finding: the frozen 20260607 publication run used
``generation_mode = deterministic_from_candidate_audit`` (see
09_ranking/ranking_generation_audit.json). So the function that actually ranked
the published top-5 is the deterministic ``audit_candidates()`` in
``s8_stage3/scoring/candidate_audit.py`` — the LLM is used upstream at S09 to
*generate* candidate instances + element_evidence, NOT to rank. This means the
faithful comparison needs NO API key and NO cost: we import and call the real
scoring function.

This script (READ-ONLY on mainline):
  1. imports the real ``audit_candidates`` from the mainline package;
  2. builds 482 candidates (5 real anchors + combinatorial synthetics);
  3. gives each candidate element_evidence derived from the REAL S08
     descriptor_claim_pool.json (the same pool the scorer reads);
  4. real I1-I5 keep their authentic element_evidence from material_instances.json;
  5. calls the real ``audit_candidates`` to score all 482 (reads frozen pool
     files only; writes nothing into mainline);
  6. reports where the experimentally validated winner I1 lands vs popularity /
     random baselines.

Honesty notes are emitted in the JSON output.
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = next(_p for _p in Path(__file__).resolve().parents if _p.name == "research").parent
RUN = ROOT / "V1.0-qianduan-mainline/stage3_mechanism/outputs/verification/20260607_openrouter_publication_v2"
SRC = ROOT / "V1.0-qianduan-mainline/stage3_mechanism/src"
OUT = Path(__file__).resolve().parent

# import the REAL production scorer (module deps are stdlib-only)
sys.path.insert(0, str(SRC))
from s8_stage3.scoring.candidate_audit import audit_candidates  # noqa: E402

POOL = json.load(open(RUN / "06_literature_materials/descriptor_claim_pool.json", encoding="utf-8"))["claims"]
real_instances = json.load(open(RUN / "08_material_instances/material_instances.json", encoding="utf-8"))["instances"]

# ---------------------------------------------------------------------------
# component bucketing + per-bucket evidence drawn from the REAL claim pool
# ---------------------------------------------------------------------------
def comp_bucket(text):
    t = (text or "").lower()
    if "paam" in t or "polyacrylamide" in t: return "paam_graft_starch"
    if "starch" in t: return "starch"
    if "pva" in t or "vinyl alcohol" in t: return "pva"
    if "chitosan" in t: return "chitosan"
    if "pbi" in t or "polybenzimidazole" in t: return "pbi"
    if "spes" in t or "ether sulfone" in t: return "spes"
    if "phosphotungstic" in t or "pwa" in t: return "pwa"
    if "phosphate glass" in t: return "phosphate_glass"
    if "eutectic" in t or "des" in t or "choline" in t: return "des"
    if "phosphoric" in t or "h3po4" in t or "(pa)" in t or t.strip() in ("pa", "h3po4"): return "phosphoric_acid"
    if "halloysite" in t or "hnt" in t: return "halloysite"
    if "attapulgite" in t or "qatp" in t or "1d at" in t: return "attapulgite"
    if "montmorillonite" in t or "mmt" in t: return "montmorillonite"
    if "functionalized clay" in t or "nanofiller" in t: return "functionalized_clay"
    if "nb2o5" in t: return "nb2o5"
    if "carbon dot" in t or "(cds)" in t: return "carbon_dots"
    if "peg" in t or "ethylene glycol" in t: return "peg"
    return None

# representative component string + (descriptor_ids, card_ids) per bucket
bucket_repr = {}
bucket_desc = {}
bucket_cards = {}
bucket_freq = {}
for cl in POOL:
    b = comp_bucket(cl.get("component", ""))
    if not b:
        continue
    bucket_repr.setdefault(b, cl["component"])
    for d in cl.get("descriptor_ids", []):
        bucket_desc.setdefault(b, set()).add(d)
    cid = cl.get("card_id")
    if cid:
        bucket_cards.setdefault(b, set()).add(cid)
for b, cards in bucket_cards.items():
    bucket_freq[b] = len(cards)

def synth_element_evidence(buckets):
    ev = []
    for b in buckets:
        ev.append({
            "component": bucket_repr.get(b, b),
            "role_in_formulation": f"{bucket_repr.get(b, b)} contributes its literature-claimed roles.",
            "descriptor_satisfied": sorted(bucket_desc.get(b, set())),
            "analog_paper_ids": sorted(bucket_cards.get(b, set())),
            "analog_reason": "Deterministically mapped from the S08 descriptor_claim_pool.",
        })
    return ev

# ---------------------------------------------------------------------------
# recipe grammar -> 482-candidate pool (same as m6_expanded_pool)
# ---------------------------------------------------------------------------
HOSTS = ["starch", "pva", "chitosan", "pbi", "spes", "paam_graft_starch"]
ACIDS = ["phosphoric_acid", "pwa", "des", "phosphate_glass"]
CLAYS = [None, "attapulgite", "halloysite", "montmorillonite", "functionalized_clay"]
ADDS = [None, "nb2o5", "carbon_dots", "peg"]

pool = []
seen = set()
for host in HOSTS:
    for acid in ACIDS:
        for clay in CLAYS:
            for add in ADDS:
                buckets = tuple(b for b in [host, acid, clay, add] if b)
                key = frozenset(buckets)
                if key in seen:
                    continue
                seen.add(key)
                pool.append({"buckets": list(buckets), "is_real": False})

# inject real I1-I5 (carry their authentic element_evidence)
real_keys = {}
real_by_key = {}
for it in real_instances:
    buckets = []
    for comp in it["components"]:
        b = comp_bucket(comp)
        if b and b not in buckets:
            buckets.append(b)
    key = frozenset(buckets)
    real_keys[it["instance_id"]] = key
    real_by_key[key] = it
    pool = [c for c in pool if frozenset(c["buckets"]) != key]
    pool.append({"buckets": buckets, "is_real": True, "real": it})

# ---------------------------------------------------------------------------
# build instance_dumps + ranking_dump for the REAL audit_candidates()
# ---------------------------------------------------------------------------
instance_dumps = []
ranking_candidates = []
synth_n = 0
for c in pool:
    if c.get("is_real"):
        it = c["real"]
        iid = it["instance_id"]
        inst = {
            "instance_id": iid,
            "instance_name": it["instance_name"],
            "composition_description": it.get("composition_description", ""),
            "components": it["components"],
            "expected_properties": it.get("expected_properties", []),
            "risk_flags": it.get("risk_flags", []),
            "combination_novelty": it.get("combination_novelty", "novel_combination"),
            "element_evidence": it.get("element_evidence", []),
            "literature_support_card_ids": it.get("literature_card_ids", []),
            "novelty_rationale": it.get("novelty_rationale", ""),
        }
    else:
        iid = f"SYN{synth_n:03d}"
        synth_n += 1
        buckets = c["buckets"]
        names = [bucket_repr.get(b, b) for b in buckets]
        inst = {
            "instance_id": iid,
            "instance_name": " + ".join(names),
            "composition_description": " + ".join(names),
            "components": names,
            "expected_properties": [],
            "risk_flags": [],
            "combination_novelty": "novel_combination",
            "element_evidence": synth_element_evidence(buckets),
            "literature_support_card_ids": sorted({cid for b in buckets for cid in bucket_cards.get(b, set())}),
            "novelty_rationale": "",
        }
    c["instance_id"] = iid
    instance_dumps.append(inst)
    ranking_candidates.append({
        "instance_id": iid,
        "instance_name": inst["instance_name"],
        "total_score": 0.0,
        "combination_novelty": inst["combination_novelty"],
    })

ranking_dump = {"ranked_candidates": ranking_candidates}

# call the REAL production scorer (reads frozen pool files; writes nothing)
audit_rows, reranked = audit_candidates(
    instance_dumps, ranking_dump, RUN, source_term_ok=True,
)

N = len(reranked)
rank_of = {row["instance_id"]: i + 1 for i, row in enumerate(reranked)}
score_of = {row["instance_id"]: row["deterministic_total_score"] for row in audit_rows}

WINNER = "I1"
BOUNDARY = "I2"

# popularity baseline on the same pool
def popularity_score(c):
    return float(sum(bucket_freq.get(b, 0) for b in c["buckets"]))

rng = np.random.default_rng(20260607)
pop_scored = sorted(pool, key=lambda c: -(popularity_score(c) + rng.random() * 1e-9))
pop_rank = {c["instance_id"]: i + 1 for i, c in enumerate(pop_scored)}

top10 = [(row["instance_id"], row["instance_name"][:48], row["deterministic_total_score"])
         for row in reranked[:10]]

result = {
    "experiment": "M6_real_ranker_on_enlarged_pool",
    "scorer": "REAL production audit_candidates() from s8_stage3.scoring.candidate_audit",
    "published_ranking_mode": "deterministic_from_candidate_audit (NOT an LLM ranker)",
    "read_only_source": str(RUN.relative_to(ROOT)),
    "pool_size_N": N,
    "winner": WINNER,
    "winner_frozen_score": score_of.get(WINNER),
    "boundary": BOUNDARY,
    "results": {
        "real_deterministic_ranker": {
            "winner_rank": rank_of.get(WINNER),
            "winner_in_top1": rank_of.get(WINNER) == 1,
            "winner_in_top3": rank_of.get(WINNER, 999) <= 3,
            "winner_in_top5": rank_of.get(WINNER, 999) <= 5,
            "boundary_rank": rank_of.get(BOUNDARY),
            "winner_score": score_of.get(WINNER),
            "top10": top10,
        },
        "popularity_freq": {
            "winner_rank": pop_rank.get(WINNER),
            "winner_in_top3": pop_rank.get(WINNER, 999) <= 3,
        },
        "random": {
            "p_top1": round(1 / N, 4),
            "p_top3": round(3 / N, 4),
            "p_top5": round(5 / N, 4),
        },
    },
    "honest_findings": [
        "The published ranker is DETERMINISTIC code, not an LLM, so this faithful "
        "comparison needs no API key and is fully reproducible.",
        "Synthetic candidates get element_evidence deterministically mapped from the "
        "real S08 claim pool, so they are scored by the exact same production function "
        "as the real I1-I5; this is a fair, leakage-controlled enlarged-pool test.",
        "LLM 'intelligence' in the real pipeline lives at S09 (which components to "
        "combine + how to justify them). This test holds that fixed and asks: does the "
        "real deterministic scorer still surface the validated winner I1 in a large pool?",
    ],
}

(OUT / "m6_real_ranker_results.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

print(f"REAL scorer = audit_candidates (deterministic_from_candidate_audit)")
print(f"pool size N = {N}")
print(f"\nWINNER I1: frozen score={score_of.get(WINNER)}  rank={rank_of.get(WINNER)}/{N}  "
      f"top3={rank_of.get(WINNER,999)<=3}  top5={rank_of.get(WINNER,999)<=5}")
print(f"BOUNDARY I2: rank={rank_of.get(BOUNDARY)}/{N}")
print(f"popularity baseline: I1 rank={pop_rank.get(WINNER)}/{N}")
print(f"random: P(top1)={1/N:.4f}  P(top3)={3/N:.4f}  P(top5)={5/N:.4f}")
print("\nReal-ranker top10:")
for iid, nm, sc in top10:
    star = " <-- I1 WINNER" if iid == WINNER else (" <-- I2 boundary" if iid == BOUNDARY else "")
    print(f"  {rank_of[iid]:3d}. {iid:7s} {sc:.4f}  {nm}{star}")
print(f"\nWrote {OUT/'m6_real_ranker_results.json'}")
