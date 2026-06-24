"""M6 ablation — READ-ONLY exploration of the frozen 20260607 registry data.
Does not modify any mainline code/data. Only reads stage3 output JSON.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUN = ROOT / "V1.0-qianduan-mainline/stage3_mechanism/outputs/verification/20260607_openrouter_publication_v2"

inst = json.load(open(RUN / "08_material_instances/material_instances.json", encoding="utf-8"))
cards = json.load(open(RUN / "06_literature_materials/literature_cards_materials.json", encoding="utf-8"))
fam = json.load(open(RUN / "07_material_families/material_families.json", encoding="utf-8"))

instances = inst.get("instances", [])
print(f"# instances (S09 candidate pool): {len(instances)}")
for it in instances:
    print(f"   {it['instance_id']} <- family {it.get('family_id')}: {it['instance_name']}")

fams = fam.get("families", fam.get("material_families", []))
print(f"\n# families (S09): {len(fams)}")
for f in fams:
    fid = f.get('family_id') or f.get('id')
    nm = f.get('family_name') or f.get('name') or f.get('family')
    print(f"   {fid}: {nm}")

cardlist = cards.get("cards", [])
print(f"\n# literature material cards (S08 pool): {len(cardlist)}")
n_year = sum(1 for c in cardlist if c.get("year"))
n_doi = sum(1 for c in cardlist if c.get("doi"))
n_cite = sum(1 for c in cardlist if c.get("citations") or c.get("citation_count") or c.get("n_citations"))
print(f"   cards with year>0: {n_year}")
print(f"   cards with doi: {n_doi}")
print(f"   cards with citation count: {n_cite}")
print(f"   card field keys (sample): {sorted(cardlist[0].keys()) if cardlist else 'none'}")

# components mentioned across cards (the 'universe' of selectable materials)
comps = {}
for c in cardlist:
    for cl in c.get("component_descriptor_claims", []):
        comp = cl.get("component")
        if comp:
            comps[comp] = comps.get(comp, 0) + 1
print(f"\n# distinct components across S08 cards: {len(comps)}")
for k, v in sorted(comps.items(), key=lambda x: -x[1]):
    print(f"   {v:3d}x  {k}")
