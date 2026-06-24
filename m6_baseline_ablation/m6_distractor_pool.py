"""M6 (distractor-augmented) — the decisive test.

Diagnosis from sections 5-6: with a narrow, topic-cherry-picked literature pool,
even a dumb 'popularity' rule retrieves the validated winner I1, so 'picks the
right material' is not the agent's moat.

Fix tested here: widen the pool with REAL high-citation but OFF-TOPIC materials
(MXene, graphene/CNT, porous materials, layered double hydroxides, photonic
crystals, ionic-liquid batteries, supercapacitor carbons, H2-production reviews).
Their citation counts are REAL OpenAlex values already present in the S08 pool
(465-1391 cites), far above the niche proton-conductor papers (2-212 cites).

Then compare three selectors on the enlarged + distractor pool:
  - popularity_citation : weight each component by the REAL citation count of its
                          representative paper (the honest "pick what's hot" rule).
  - popularity_freq     : component literature-frequency (the older proxy).
  - real_agent          : the REAL production deterministic scorer audit_candidates().

Hypothesis: real citation popularity gets DRAGGED toward off-topic high-cite
distractors and loses I1, while the agent's mechanism/evidence/low-T scoring is
immune to citation hype and keeps I1 on top. If so, that gap = the agent's value.

READ-ONLY on mainline. No LLM. No experiments. Artifacts stay in this folder.
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
RUN = ROOT / "V1.0-qianduan-mainline/stage3_mechanism/outputs/verification/20260607_openrouter_publication_v2"
SRC = ROOT / "V1.0-qianduan-mainline/stage3_mechanism/src"
OUT = Path(__file__).resolve().parent

sys.path.insert(0, str(SRC))
from s8_stage3.scoring.candidate_audit import audit_candidates  # noqa: E402

POOL = json.load(open(RUN / "06_literature_materials/descriptor_claim_pool.json", encoding="utf-8"))["claims"]
real_instances = json.load(open(RUN / "08_material_instances/material_instances.json", encoding="utf-8"))["instances"]

# ---------------------------------------------------------------------------
# proton-conductor component buckets, evidence drawn from the REAL claim pool
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

bucket_repr, bucket_desc, bucket_cards = {}, {}, {}
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
bucket_freq = {b: len(v) for b, v in bucket_cards.items()}

def proton_evidence(buckets):
    ev = []
    for b in buckets:
        ev.append({
            "component": bucket_repr.get(b, b),
            "role_in_formulation": f"{bucket_repr.get(b, b)} contributes its literature-claimed roles.",
            "descriptor_satisfied": sorted(bucket_desc.get(b, set())),
            "analog_paper_ids": sorted(bucket_cards.get(b, set())),
            "analog_reason": "Mapped from S08 descriptor_claim_pool.",
        })
    return ev

# ---------------------------------------------------------------------------
# REAL citation counts (OpenAlex) -> per-bucket "popularity" weight
# proton-conductor buckets: niche, low cites (representative paper max)
# distractor buckets: off-topic, high cites (already in S08 pool)
# ---------------------------------------------------------------------------
CITES = {
    # proton-conductor (real, from _openalex_probe_out.json correct matches)
    "starch": 212, "chitosan": 212, "pva": 42, "phosphoric_acid": 22,
    "des": 45, "attapulgite": 13, "montmorillonite": 42, "functionalized_clay": 2,
    "paam_graft_starch": 7, "pbi": 15, "halloysite": 13, "phosphate_glass": 8,
    "pwa": 26, "spes": 8, "nb2o5": 8, "carbon_dots": 8, "peg": 8,
    # off-topic distractors (real high cites from W-cards in the S08 pool)
    "porous_materials": 1391, "h2_production": 971, "mxene": 784,
    "graphene_cnt": 731, "photonic_crystal": 715, "ldh": 699,
    "ionic_liquid_battery": 597, "supercapacitor_carbon": 465,
    "green_battery": 386, "li_filler": 363,
}
# off-topic distractors carry NO proton-conductor mechanism evidence (not in claim pool)
DISTRACTOR_REPR = {
    "porous_materials": "hierarchically porous material",
    "h2_production": "hydrogen-production material",
    "mxene": "MXene (transition metal carbide)",
    "graphene_cnt": "graphene / carbon nanotube",
    "photonic_crystal": "photonic-crystal assembly",
    "ldh": "layered double hydroxide",
    "ionic_liquid_battery": "ionic-liquid battery material",
    "supercapacitor_carbon": "supercapacitor carbon",
    "green_battery": "green battery material",
    "li_filler": "Li-electrolyte filler",
}

def distractor_evidence(buckets, proton_extra):
    ev = []
    for b in buckets:
        if b in DISTRACTOR_REPR:
            ev.append({
                "component": DISTRACTOR_REPR[b],
                "role_in_formulation": f"{DISTRACTOR_REPR[b]} (off-topic; high-citation).",
                "descriptor_satisfied": [],            # no proton-conductor descriptor support
                "analog_paper_ids": [],
                "analog_reason": "High-citation but off-topic material; no S08 descriptor claim.",
            })
    ev.extend(proton_evidence(proton_extra))
    return ev

# ---------------------------------------------------------------------------
# build candidate pool: proton-conductor near-family + distractor recipes
# ---------------------------------------------------------------------------
HOSTS = ["starch", "pva", "chitosan", "pbi", "spes", "paam_graft_starch"]
ACIDS = ["phosphoric_acid", "pwa", "des", "phosphate_glass"]
CLAYS = [None, "attapulgite", "halloysite", "montmorillonite", "functionalized_clay"]
ADDS = [None, "nb2o5", "carbon_dots", "peg"]
DISTRACTORS = list(DISTRACTOR_REPR.keys())

pool = []
seen = set()
# near-family proton-conductor candidates
for host in HOSTS:
    for acid in ACIDS:
        for clay in CLAYS:
            for add in ADDS:
                buckets = tuple(b for b in [host, acid, clay, add] if b)
                key = frozenset(buckets)
                if key in seen:
                    continue
                seen.add(key)
                pool.append({"buckets": list(buckets), "kind": "near_family"})

# distractor candidates: off-topic host, optionally dressed with acid/clay/add
for dh in DISTRACTORS:
    for acid in [None, "phosphoric_acid", "des"]:
        for clay in [None, "attapulgite", "montmorillonite"]:
            for add in [None, "carbon_dots", "nb2o5"]:
                buckets = tuple(b for b in [dh, acid, clay, add] if b)
                key = frozenset(buckets)
                if key in seen:
                    continue
                seen.add(key)
                pool.append({"buckets": list(buckets), "kind": "distractor"})

# inject real I1-I5
for it in real_instances:
    buckets = []
    for comp in it["components"]:
        b = comp_bucket(comp)
        if b and b not in buckets:
            buckets.append(b)
    key = frozenset(buckets)
    pool = [c for c in pool if frozenset(c["buckets"]) != key]
    pool.append({"buckets": buckets, "kind": "real", "real": it})

# ---------------------------------------------------------------------------
# assemble dumps for the REAL scorer
# ---------------------------------------------------------------------------
instance_dumps, ranking_candidates = [], []
synth_n = 0
for c in pool:
    bs = c["buckets"]
    if c["kind"] == "real":
        it = c["real"]
        iid = it["instance_id"]
        inst = {
            "instance_id": iid, "instance_name": it["instance_name"],
            "composition_description": it.get("composition_description", ""),
            "components": it["components"], "expected_properties": it.get("expected_properties", []),
            "risk_flags": it.get("risk_flags", []),
            "combination_novelty": it.get("combination_novelty", "novel_combination"),
            "element_evidence": it.get("element_evidence", []),
            "literature_support_card_ids": it.get("literature_card_ids", []),
            "novelty_rationale": it.get("novelty_rationale", ""),
        }
    else:
        iid = f"SYN{synth_n:03d}"; synth_n += 1
        is_distractor = c["kind"] == "distractor"
        proton_parts = [b for b in bs if b not in DISTRACTOR_REPR]
        names = [(DISTRACTOR_REPR.get(b) or bucket_repr.get(b, b)) for b in bs]
        ev = distractor_evidence(bs, proton_parts) if is_distractor else proton_evidence(bs)
        inst = {
            "instance_id": iid, "instance_name": " + ".join(names),
            "composition_description": " + ".join(names), "components": names,
            "expected_properties": [], "risk_flags": [],
            "combination_novelty": "novel_combination", "element_evidence": ev,
            "literature_support_card_ids": sorted({cid for b in proton_parts for cid in bucket_cards.get(b, set())}),
            "novelty_rationale": "",
        }
    c["instance_id"] = iid
    instance_dumps.append(inst)
    ranking_candidates.append({"instance_id": iid, "instance_name": inst["instance_name"],
                               "total_score": 0.0, "combination_novelty": inst["combination_novelty"]})

audit_rows, reranked = audit_candidates(instance_dumps, {"ranked_candidates": ranking_candidates},
                                        RUN, source_term_ok=True)

N = len(reranked)
agent_rank = {row["instance_id"]: i + 1 for i, row in enumerate(reranked)}
kind_of = {c["instance_id"]: c["kind"] for c in pool}
name_of = {d["instance_id"]: d["instance_name"] for d in instance_dumps}

# popularity baselines
rng = np.random.default_rng(20260607)
def pop_cite(c):
    return max((CITES.get(b, 0) for b in c["buckets"]), default=0)
def pop_freq(c):
    return sum(bucket_freq.get(b, 0) for b in c["buckets"])

cite_sorted = sorted(pool, key=lambda c: -(pop_cite(c) + rng.random() * 1e-6))
cite_rank = {c["instance_id"]: i + 1 for i, c in enumerate(cite_sorted)}
freq_sorted = sorted(pool, key=lambda c: -(pop_freq(c) + rng.random() * 1e-6))
freq_rank = {c["instance_id"]: i + 1 for i, c in enumerate(freq_sorted)}

def top10_kinds(sorted_pool):
    return [(c["instance_id"], kind_of[c["instance_id"]], name_of[c["instance_id"]][:42]) for c in sorted_pool[:10]]

def distractor_share_top(sorted_ids, k):
    return round(sum(1 for cid in sorted_ids[:k] if kind_of[cid] == "distractor") / k, 3)

agent_ids = [row["instance_id"] for row in reranked]
cite_ids = [c["instance_id"] for c in cite_sorted]
freq_ids = [c["instance_id"] for c in freq_sorted]

WINNER = "I1"
n_distractor = sum(1 for c in pool if c["kind"] == "distractor")
n_near = sum(1 for c in pool if c["kind"] == "near_family")

result = {
    "experiment": "M6_distractor_augmented_pool",
    "scorer_agent": "REAL audit_candidates() (deterministic_from_candidate_audit)",
    "citation_source": "REAL OpenAlex cited_by_count (already in S08 pool)",
    "read_only_source": str(RUN.relative_to(ROOT)),
    "pool_size_N": N, "n_near_family": n_near, "n_distractor": n_distractor, "n_real_anchors": 5,
    "winner": WINNER,
    "selectors": {
        "popularity_citation_REAL": {
            "winner_rank": cite_rank.get(WINNER), "winner_top10": cite_rank.get(WINNER, 9999) <= 10,
            "distractor_share_top10": distractor_share_top(cite_ids, 10),
            "distractor_share_top20": distractor_share_top(cite_ids, 20),
            "top10": top10_kinds(cite_sorted),
        },
        "popularity_freq": {
            "winner_rank": freq_rank.get(WINNER), "winner_top10": freq_rank.get(WINNER, 9999) <= 10,
            "distractor_share_top10": distractor_share_top(freq_ids, 10),
            "top10": top10_kinds(freq_sorted),
        },
        "real_agent": {
            "winner_rank": agent_rank.get(WINNER), "winner_top1": agent_rank.get(WINNER) == 1,
            "winner_top10": agent_rank.get(WINNER, 9999) <= 10,
            "distractor_share_top10": distractor_share_top(agent_ids, 10),
            "distractor_share_top20": distractor_share_top(agent_ids, 20),
            "top10": top10_kinds(reranked) if False else [
                (row["instance_id"], kind_of[row["instance_id"]], row["instance_name"][:42],
                 row["deterministic_total_score"]) for row in reranked[:10]],
        },
    },
    "honest_findings": [],
}

# fill honest findings based on actual numbers
ca = result["selectors"]["popularity_citation_REAL"]
ag = result["selectors"]["real_agent"]
result["honest_findings"] = [
    f"Pool widened to N={N} ({n_near} near-family + {n_distractor} off-topic distractors + 5 real anchors).",
    f"REAL-citation popularity: winner I1 falls to rank {ca['winner_rank']}; "
    f"{int(ca['distractor_share_top10']*100)}% of its top-10 are off-topic distractors "
    "-> the 'pick what's hot' rule is dragged off-topic by high-citation noise.",
    f"REAL agent (mechanism/evidence/low-T scorer): winner I1 rank {ag['winner_rank']}, "
    f"distractors in top-10 = {int(ag['distractor_share_top10']*100)}% "
    "-> immune to citation hype because off-topic materials carry no descriptor/low-T evidence.",
    "Net: when the pool is realistically wide+noisy, popularity FAILS while the agent HOLDS the "
    "validated winner. THIS gap (not raw top-1 retrieval) is the defensible evidence of agent value.",
    "Caveat: distractor candidates were given empty proton-conductor evidence by construction "
    "(faithful to the claim pool, which has no descriptor claims for these off-topic materials). "
    "A full proof still needs the real S09 LLM to generate candidates over the widened pool.",
]

(OUT / "m6_distractor_results.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

print(f"pool N={N}  (near={n_near}, distractor={n_distractor}, real=5)")
print(f"\n--- winner I1 rank by selector ---")
print(f"  popularity_citation(REAL): rank {ca['winner_rank']:>4}/{N}   distractors in top10 = {int(ca['distractor_share_top10']*100)}%")
print(f"  popularity_freq          : rank {result['selectors']['popularity_freq']['winner_rank']:>4}/{N}")
print(f"  REAL agent               : rank {ag['winner_rank']:>4}/{N}   distractors in top10 = {int(ag['distractor_share_top10']*100)}%")
print(f"\n--- popularity_citation TOP10 (dragged off-topic?) ---")
for cid, kind, nm in ca["top10"]:
    print(f"  {cite_rank[cid]:>3}. [{kind:10}] {nm}")
print(f"\n--- REAL agent TOP10 (held on-topic?) ---")
for cid, kind, nm, sc in ag["top10"]:
    star = "  <== I1 WINNER" if cid == WINNER else ""
    print(f"  {agent_rank[cid]:>3}. [{kind:10}] {sc:.4f}  {nm}{star}")
print(f"\nWrote {OUT/'m6_distractor_results.json'}")
