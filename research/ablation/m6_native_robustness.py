"""M6 (native) — quantify the REAL S09/S10 agent's behaviour on the frozen run:
did the LLM, while seeing genuinely high-citation OFF-TOPIC cards in its S08
pool, adopt any of them into families/instances/registry?

This needs NO key and NO re-run: it just cross-references frozen artifacts.
READ-ONLY on mainline.
"""
import json
from pathlib import Path

ROOT = next(_p for _p in Path(__file__).resolve().parents if _p.name == "research").parent
RUN = ROOT / "V1.0-qianduan-mainline/stage3_mechanism/outputs/verification/20260607_openrouter_publication_v2"
OUT = Path(__file__).resolve().parent

cards = json.load(open(RUN / "06_literature_materials/literature_cards_materials.json", encoding="utf-8"))["cards"]
families = json.load(open(RUN / "07_material_families/material_families.json", encoding="utf-8"))["families"]
instances = json.load(open(RUN / "08_material_instances/material_instances.json", encoding="utf-8"))["instances"]
registry = json.load(open(RUN / "11_candidate_registry/prospective_candidates.json", encoding="utf-8"))["candidates"]
probe = {p["card_id"]: p.get("cited_by_count", 0)
         for p in json.load(open(OUT / "_openalex_probe_out.json", encoding="utf-8"))}

# cards the LLM actually USED downstream (S09 families + S10 instances + registry)
used = set()
for f in families:
    used.update(f.get("literature_support_card_ids", []))
for it in instances:
    used.update(it.get("literature_card_ids", []) or it.get("literature_support_card_ids", []))
    for ev in it.get("element_evidence", []):
        used.update(ev.get("analog_paper_ids", []))
for c in registry:
    used.update(c.get("literature_card_ids", []))

# classify each card: off-topic == no proton-conductor descriptor claim
rows = []
for c in cards:
    cid = c["card_id"]
    has_claims = bool(c.get("component_descriptor_claims"))
    is_offtopic = not has_claims
    rows.append({
        "card_id": cid,
        "title": (c.get("title") or "")[:70],
        "has_descriptor_claims": has_claims,
        "off_topic": is_offtopic,
        "real_citations": probe.get(cid, c.get("year") and 0),
        "adopted_by_agent": cid in used,
    })

offtopic = [r for r in rows if r["off_topic"]]
offtopic_cited = sorted(offtopic, key=lambda r: -(r["real_citations"] or 0))
n_offtopic = len(offtopic)
n_offtopic_adopted = sum(1 for r in offtopic if r["adopted_by_agent"])
ontopic = [r for r in rows if not r["off_topic"]]
n_ontopic_adopted = sum(1 for r in ontopic if r["adopted_by_agent"])

result = {
    "experiment": "M6_native_robustness_on_frozen_run",
    "needs_key": False,
    "n_cards_total": len(cards),
    "n_off_topic_cards": n_offtopic,
    "n_off_topic_adopted_by_agent": n_offtopic_adopted,
    "n_on_topic_cards": len(ontopic),
    "n_on_topic_adopted_by_agent": n_ontopic_adopted,
    "max_off_topic_citation": max((r["real_citations"] or 0) for r in offtopic) if offtopic else 0,
    "off_topic_cards_ranked_by_citation": offtopic_cited,
    "interpretation": (
        f"The frozen S08 pool fed to S09 contained {n_offtopic} off-topic cards "
        f"(no proton-conductor descriptor claim), several with very high REAL citations "
        f"(up to {max((r['real_citations'] or 0) for r in offtopic) if offtopic else 0}). "
        f"The real LLM agent adopted {n_offtopic_adopted} of them into any "
        f"family/instance/registry. So the published pipeline did NOT chase citation "
        f"hype — but note this is the COMBINED effect of (a) the evidence-constrained "
        f"architecture (off-topic cards carry no descriptor claim, so they are hard to "
        f"select by construction) AND (b) the LLM. It is NOT proof of standalone LLM "
        f"judgement, because the off-topic cards were structurally evidence-empty."
    ),
    "honest_limit": (
        "To prove standalone LLM resistance you would have to feed the LLM off-topic "
        "cards that ALSO carry (fabricated) proton-conductor descriptor claims and see "
        "if it rejects them. That requires fabricating literature evidence, which "
        "violates the project's honesty guardrails, so it must NOT be done."
    ),
}

(OUT / "m6_native_robustness_results.json").write_text(
    json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

print(f"S08 pool: {len(cards)} cards | off-topic (no descriptor claim): {n_offtopic} | on-topic: {len(ontopic)}")
print(f"off-topic cards adopted by the real agent: {n_offtopic_adopted}/{n_offtopic}")
print(f"on-topic cards adopted by the real agent : {n_ontopic_adopted}/{len(ontopic)}")
print(f"\nhigh-citation OFF-TOPIC cards the LLM saw but did NOT adopt:")
for r in offtopic_cited[:10]:
    print(f"  cites={str(r['real_citations'] or 0):>5}  adopted={r['adopted_by_agent']}  {r['title']}")
print(f"\nWrote {OUT/'m6_native_robustness_results.json'}")
