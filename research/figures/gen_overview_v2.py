# -*- coding: utf-8 -*-
"""Iterate the system-overview schematic (2 variants) via OpenRouter image-to-image.

Variant V2 = vertical/portrait layout + materials-page palette (aqua/teal/violet/lilac, one warm
accent). Variant V3 = horizontal but with EXPLICIT flow arrows: a dashed 'prior-evidence' arrow
from the mother system into the reasoning core (never into optimisation), and a solid
'transfer-validation' arrow from the core to the biopolymer family. Reference = the user's
architecture image. DRAFT concept figures only (data panels stay matplotlib).
"""
import base64
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KEY = (ROOT / "key.txt").read_text(encoding="utf-8").strip()
OUT = Path(__file__).resolve().parent
MODEL = "google/gemini-3-pro-image"
REF = ROOT / "ChatGPT Image May 11, 2026, 12_53_44 PM.png"

BASE = (
    "Redraw the attached diagram as a CLEAN JOURNAL system-overview schematic. ENGLISH ONLY. "
    "Remove ALL file names, code identifiers and pipeline jargon (no '.json', 'history_db', "
    "'Stage 0/1/2/3', 'CHI', 'bundle', 'seed', no database-cylinder-with-filename icons). Flat "
    "vector, generous whitespace, thin clean strokes, large legible labels only, narrative not "
    "dashboard.\nScientific content to keep (plain English): three material roles — a MOTHER "
    "SYSTEM (sepiolite + phosphoric acid) used as PRIOR EVIDENCE ONLY (never mixed into "
    "optimisation), a SOURCE SYSTEM (attapulgite + phosphoric acid) running a REAL closed loop, "
    "and a TRANSFER FAMILY (lotus-root starch, starch, chitosan) for VALIDATION; measurement to "
    "evidence by variable-temperature impedance (+25 to -90 C) giving conductivity, activation "
    "energy and a sub-zero transition temperature; one governed core with two modes (transfer "
    "reasoning; closed-loop Bayesian optimisation with a language-model screening step) gated by a "
    "CALIBRATED CLAIM LADDER; governed outputs (design rules, prospective candidates) bounded by a "
    "REPRODUCIBILITY FLOOR (from below) and an IDENTIFIABILITY CEILING (mechanism not claimable, "
    "from above); a thin guardrail strip (replay is not real measurement; separate optimisation "
    "history per system; claim audit)."
)

VARIANTS = {
    "overview_v2_vertical": BASE + (
        "\nLAYOUT: VERTICAL / PORTRAIT, top-to-bottom flow (material roles at top -> measurement "
        "-> governed core -> outputs/limits at bottom). PALETTE: materials-page scheme — aqua, "
        "teal, soft violet and lilac, with a SINGLE warm-red accent reserved only for the "
        "identifiability ceiling. Calm, low-saturation."
    ),
    "overview_v3_arrows": BASE + (
        "\nLAYOUT: horizontal, but make the FLOW ARROWS explicit and primary: (1) a DASHED arrow "
        "labelled 'prior evidence' from the mother system into the reasoning core, with a small "
        "crossed-out branch showing it does NOT enter the optimisation history; (2) a SOLID arrow "
        "labelled 'transfer validation' from the core to the biopolymer family; (3) a closed "
        "circular arrow on the source system labelled 'propose -> make -> measure -> update'. "
        "PALETTE: deep blue + teal + grey with one orange accent."
    ),
}


def gen(tag, prompt, ref_b64):
    content = [{"type": "text", "text": prompt},
               {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{ref_b64}"}}]
    body = json.dumps({"model": MODEL, "messages": [{"role": "user", "content": content}],
                       "modalities": ["image", "text"]}).encode()
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions", data=body,
        headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json",
                 "HTTP-Referer": "https://local", "X-Title": f"overview {tag}"})
    resp = json.loads(urllib.request.urlopen(req, timeout=240).read())
    msg = resp["choices"][0]["message"]
    for i, im in enumerate(msg.get("images") or []):
        url = im.get("image_url", {}).get("url", "") if isinstance(im, dict) else ""
        if url.startswith("data:"):
            (OUT / f"{tag}.png").write_bytes(base64.b64decode(url.split(",", 1)[1]))
            print(f"Saved -> {OUT / f'{tag}.png'}  (cost {resp.get('usage',{}).get('cost')})")
            return
    print(f"{tag}: no image; text={(msg.get('content') or '')[:200]}")


def main():
    ref_b64 = base64.b64encode(REF.read_bytes()).decode()
    for tag, prompt in VARIANTS.items():
        gen(tag, prompt, ref_b64)


if __name__ == "__main__":
    main()
