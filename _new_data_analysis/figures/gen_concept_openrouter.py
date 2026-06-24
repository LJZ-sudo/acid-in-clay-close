# -*- coding: utf-8 -*-
"""Generate a DRAFT graphical-abstract (concept figure) via OpenRouter image model.

IMPORTANT honesty rule: this is used ONLY for the conceptual/graphical-abstract figure.
ALL quantitative/data figures (regularity, reproducibility floor, calibration,
identifiability) are produced by matplotlib from REAL data — never by an image model.
This draft will be redrawn in PPT/vector later (per user). Minimal text in the prompt
because raster image models garble small scientific labels.
"""
import base64
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KEY = (ROOT / "key.txt").read_text(encoding="utf-8").strip()
OUT = Path(__file__).resolve().parent
MODEL = "google/gemini-3-pro-image"

PROMPT = (
    "Create a clean, modern SCIENTIFIC JOURNAL GRAPHICAL ABSTRACT (flat vector style, "
    "white background, restrained 4-color palette: deep blue, teal, warm orange, grey). "
    "Landscape 16:9. Minimal, large, legible labels only.\n\n"
    "Concept: 'Characterization-frugal CREDIBLE autonomous discovery of a sub-zero proton "
    "transport transition in biopolymer-clay-phosphoric-acid composites.'\n\n"
    "Layout three connected panels left-to-right with arrows:\n"
    "LEFT panel titled 'EIS-only evidence': a pressed grey clay/biopolymer pellet between two "
    "electrodes inside a cold chamber with a thermometer reading negative degrees; next to it a "
    "small line plot of log-conductivity versus 1/Temperature showing TWO straight segments "
    "meeting at a kink labelled 'sub-zero transition (~ -30 C)'.\n"
    "CENTER panel titled 'Two modes, one governed core': a robot/AI agent head icon; two looping "
    "arrows labelled 'transfer reasoning' and 'closed-loop optimization'; below it a vertical "
    "GATE/LADDER icon labelled 'claim ladder C0-C5' and a CALIBRATION gauge dial.\n"
    "RIGHT panel titled 'Limits made explicit': several overlapping faint repeated curves with a "
    "shaded horizontal band labelled 'reproducibility floor'; above it a dashed ceiling line "
    "labelled 'identifiability ceiling: mechanism not claimable'.\n\n"
    "Style like a Nature/Cell graphical abstract: crisp, lots of whitespace, thin clean strokes, "
    "no photorealism, no clutter, no paragraphs of text."
)


def main():
    body = json.dumps({
        "model": MODEL,
        "messages": [{"role": "user", "content": PROMPT}],
        "modalities": ["image", "text"],
    }).encode()
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions", data=body,
        headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json",
                 "HTTP-Referer": "https://local", "X-Title": "acid-in-clay graphical abstract"})
    resp = json.loads(urllib.request.urlopen(req, timeout=180).read())
    msg = resp["choices"][0]["message"]
    imgs = msg.get("images") or []
    if not imgs:
        print("No image returned. Raw text:", (msg.get("content") or "")[:500])
        print("usage:", resp.get("usage"))
        return
    n = 0
    for i, im in enumerate(imgs):
        url = im.get("image_url", {}).get("url", "") if isinstance(im, dict) else ""
        if url.startswith("data:"):
            b64 = url.split(",", 1)[1]
            (OUT / f"concept_abstract_draft_{i}.png").write_bytes(base64.b64decode(b64))
            n += 1
            print(f"Saved -> {OUT / f'concept_abstract_draft_{i}.png'}")
    print(f"done, {n} image(s); model={MODEL}; usage={resp.get('usage')}")


if __name__ == "__main__":
    main()
