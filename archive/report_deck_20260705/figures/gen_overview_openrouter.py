# -*- coding: utf-8 -*-
"""Image-to-image: redraw the internal architecture diagram into a clean JOURNAL schematic.

Uses the user's existing architecture image as a reference and asks an OpenRouter image model
to produce a publication-grade system-overview schematic that (a) keeps the real scientific
structure but (b) removes ALL code/file names and internal pipeline jargon, (c) is English-only,
(d) follows nature-figure schematic principles (narrative not dashboard, restrained palette,
label-light). This is a DRAFT concept figure; data panels remain matplotlib (no image model).
"""
import base64
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
KEY = (ROOT / "key.txt").read_text(encoding="utf-8").strip()
OUT = Path(__file__).resolve().parent
MODEL = "google/gemini-3-pro-image"

# reference architecture image (open in the user's IDE / saved in workspace root)
REF = ROOT / "ChatGPT Image May 11, 2026, 12_53_44 PM.png"

PROMPT = (
    "Redraw the attached scientific system-overview diagram as a CLEAN, JOURNAL-QUALITY "
    "schematic for a research-paper figure. Keep the real scientific structure but REMOVE every "
    "file name, code identifier and software/pipeline term: no '.json', no 'history_db', no "
    "'Stage 0/1/2/3', no 'CHI', no database-cylinder icons labelled with filenames, no "
    "'bundle'/'seed' tokens. Use ENGLISH ONLY, flat vector style, white background, generous "
    "whitespace, thin clean strokes, restrained palette (deep blue, teal, warm orange, grey) with "
    "a single accent. Make it a NARRATIVE left-to-right schematic, NOT a dashboard.\n\n"
    "Content to preserve, relabelled in plain scientific English:\n"
    "LEFT — three material roles: (1) a 'mother system' (sepiolite + phosphoric acid) used as "
    "PRIOR EVIDENCE ONLY, never mixed into optimisation; (2) a 'source system' (attapulgite + "
    "phosphoric acid) that runs a REAL closed loop; (3) a 'transfer family' (lotus-root starch, "
    "starch, chitosan) used for VALIDATION.\n"
    "CENTRE-TOP — measurement to evidence: variable-temperature impedance spectroscopy from "
    "+25 to -90 degrees C, yielding conductivity, activation energy and a sub-zero transition "
    "temperature.\n"
    "CENTRE — two coupled modes around ONE governed core: 'transfer reasoning' and 'closed-loop "
    "Bayesian optimisation with a language-model screening step', gated by a 'calibrated claim "
    "ladder'.\n"
    "RIGHT — governed outputs (design rules, prospective candidates) plus the two explicit limits: "
    "a 'reproducibility floor' (from below) and an 'identifiability ceiling' (mechanism not "
    "claimable, from above).\n"
    "BOTTOM — a thin guardrail strip: 'replay is not real measurement', 'separate optimisation "
    "history per system', 'claim audit'.\n\n"
    "Only large, legible labels. Landscape 16:9. Style: Nature/Cell narrative overview schematic."
)


def main():
    if not REF.exists():
        print(f"reference image not found: {REF}")
        return
    b64 = base64.b64encode(REF.read_bytes()).decode()
    content = [
        {"type": "text", "text": PROMPT},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
    ]
    body = json.dumps({
        "model": MODEL,
        "messages": [{"role": "user", "content": content}],
        "modalities": ["image", "text"],
    }).encode()
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions", data=body,
        headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json",
                 "HTTP-Referer": "https://local", "X-Title": "acid-in-clay overview schematic"})
    resp = json.loads(urllib.request.urlopen(req, timeout=240).read())
    msg = resp["choices"][0]["message"]
    imgs = msg.get("images") or []
    if not imgs:
        print("No image returned. text:", (msg.get("content") or "")[:400])
        print("usage:", resp.get("usage"))
        return
    for i, im in enumerate(imgs):
        url = im.get("image_url", {}).get("url", "") if isinstance(im, dict) else ""
        if url.startswith("data:"):
            (OUT / f"overview_schematic_draft_{i}.png").write_bytes(
                base64.b64decode(url.split(",", 1)[1]))
            print(f"Saved -> {OUT / f'overview_schematic_draft_{i}.png'}")
    print(f"usage={resp.get('usage')}")


if __name__ == "__main__":
    main()
