"""Probe: can OpenAlex (free, no key) recover citation counts for the S08 cards?
Tests title-based lookup on cards that have a real paper title.
READ-ONLY; external GET only."""
import json
import re
import time
from pathlib import Path
from urllib.parse import quote

import requests

ROOT = Path(__file__).resolve().parent.parent
RUN = ROOT / "V1.0-qianduan-mainline/stage3_mechanism/outputs/verification/20260607_openrouter_publication_v2"
cards = json.load(open(RUN / "06_literature_materials/literature_cards_materials.json", encoding="utf-8"))["cards"]

JOURNAL_NAMES = {
    "international journal of biological macromolecules",
    "journal of materials chemistry a", "chemical science", "journal of power sources",
}

def looks_like_title(t):
    t = (t or "").strip()
    if not t or t.lower() in JOURNAL_NAMES:
        return False
    if len(t.split()) < 5:
        return False
    # reject OCR garbage (lots of single chars / symbols)
    alpha = sum(c.isalpha() for c in t)
    return alpha / max(len(t), 1) > 0.6

candidates = [c for c in cards if looks_like_title(c.get("title"))]
print(f"cards with usable title: {len(candidates)}/{len(cards)}\n")

results = []
for c in candidates:
    title = re.sub(r"\s+", " ", c["title"]).strip()
    try:
        time.sleep(0.15)
        r = requests.get(
            "https://api.openalex.org/works",
            params={"search": title[:200], "per_page": 1,
                    "select": "title,doi,publication_year,cited_by_count"},
            timeout=20,
        )
        r.raise_for_status()
        hits = r.json().get("results", [])
    except Exception as e:
        print(f"  [{c['card_id']}] ERROR {e}")
        continue
    if hits:
        h = hits[0]
        results.append({
            "card_id": c["card_id"],
            "query_title": title[:70],
            "matched_title": (h.get("title") or "")[:70],
            "doi": (h.get("doi") or "").replace("https://doi.org/", ""),
            "year": h.get("publication_year"),
            "cited_by_count": h.get("cited_by_count"),
        })
        print(f"  [{c['card_id']}] cites={h.get('cited_by_count')}  y={h.get('publication_year')}")
        print(f"      q: {title[:70]}")
        print(f"      m: {(h.get('title') or '')[:70]}")
    else:
        print(f"  [{c['card_id']}] no match for: {title[:60]}")

Path(Path(__file__).resolve().parent / "_openalex_probe_out.json").write_text(
    json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"\nrecovered citations for {len(results)}/{len(candidates)} well-titled cards")
