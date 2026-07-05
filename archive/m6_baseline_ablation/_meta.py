"""Extract literature-card metadata to judge whether real citation counts are
fetchable. READ-ONLY on mainline."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUN = ROOT / "V1.0-qianduan-mainline/stage3_mechanism/outputs/verification/20260607_openrouter_publication_v2"
cards = json.load(open(RUN / "06_literature_materials/literature_cards_materials.json", encoding="utf-8"))["cards"]

def asciisafe(s):
    return s.encode("ascii", "replace").decode("ascii")

KNOWN_JOURNALS = {
    "international journal of biological macromolecules",
    "journal of materials chemistry a",
    "chemical science",
    "journal of power sources",
    "electrochimica acta",
    "acs applied materials & interfaces",
    "rsc advances",
}

usable_doi = 0
usable_title = 0
lines = [f"total cards: {len(cards)}", ""]
for c in cards:
    doi = (c.get("doi") or "").strip()
    title = (c.get("title") or "").strip()
    year = c.get("year") or 0
    looks_journal = title.lower() in KNOWN_JOURNALS or len(title.split()) <= 4
    if doi:
        usable_doi += 1
    if title and not looks_journal:
        usable_title += 1
    flag = []
    if doi: flag.append("DOI")
    if title and not looks_journal: flag.append("TITLE")
    lines.append(f"  {c['card_id']}  y={year:<5} [{','.join(flag) or 'NONE'}]")
    lines.append(f"      title: {asciisafe(title[:100])}")
    if doi:
        lines.append(f"      doi  : {asciisafe(doi)}")

lines.append("")
lines.append(f"fetchable by DOI   : {usable_doi}/{len(cards)}")
lines.append(f"fetchable by title : {usable_title}/{len(cards)}")
out = "\n".join(lines)
print(out)
Path(Path(__file__).resolve().parent / "_meta_out.txt").write_text(out, encoding="utf-8")
