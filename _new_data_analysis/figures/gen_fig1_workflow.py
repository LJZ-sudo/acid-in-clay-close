# -*- coding: utf-8 -*-
"""Generate the journal Figure 1 (overall workflow) via OpenRouter.

Main thread = "Evidence-limited autonomous science" (per independent review): four horizontal
stages, deterministic core + LLM only at proposal/explanation, outputs bounded by measurement
reproducibility and model identifiability. ENGLISH, journal-grade, minimal accurate labels.
Avoid the 'floor/ceiling' metaphor -> use precise terms 'measurement reproducibility' /
'model identifiability'. DRAFT (final = vector redraw), but labels must be accurate.
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
    "Create a clean, professional JOURNAL FIGURE 1 (scientific workflow schematic, 16:9 landscape, "
    "white background, flat vector, generous whitespace, thin clean strokes, restrained palette: "
    "deep blue + teal + grey with ONE orange accent, large legible sans-serif labels, ENGLISH ONLY, "
    "no clutter, no code/file names). Nature/IEEE methods-figure aesthetic. Title at top: "
    "'Evidence-limited autonomous discovery of proton-conducting biopolymer-clay membranes'.\n\n"
    "FOUR numbered stage panels left-to-right, connected by labelled horizontal arrows:\n\n"
    "PANEL 1 - 'Materials & measurement'. Icons/labels: biopolymer-clay membranes (lotus-root "
    "starch, starch, chitosan; attapulgite source system); arrow to 'variable-temperature impedance "
    "spectroscopy (+25 to -90 C)'; arrow to transport descriptors 'conductivity sigma, activation "
    "energy Ea, low-temperature transport-regime transition'.\n"
    "  arrow labelled 'transport descriptors'\n\n"
    "PANEL 2 - 'Evidence calibration'. Two stacked sub-boxes: (a) 'independent repeats -> measurement "
    "reproducibility'; (b) 'competing transport models -> model identifiability limit'. \n"
    "  arrow labelled 'calibrated evidence'\n\n"
    "PANEL 3 - 'Governed reasoning & closed loop'. A small circular loop labelled "
    "'propose -> make -> measure -> update'; inside: 'multi-objective Bayesian optimisation' + "
    "'language-model safety screen'; a small note 'deterministic core; language model proposes & "
    "explains only'.\n"
    "  arrow labelled 'governed decision'\n\n"
    "PANEL 4 - 'Credibility-bounded outputs'. Labels: 'calibrated confidence', 'graded claims "
    "(C0-C4)', 'design rules & prospective candidates'.\n\n"
    "BOTTOM ribbon spanning full width (grey): 'Provenance & governance: separate optimisation "
    "history per system | prospective freeze | claim audit'.\n\n"
    "Minimal and readable. Large labels only, no paragraphs. Make the four panels visually distinct "
    "and the left-to-right flow obvious."
)


def main():
    body = json.dumps({"model": MODEL, "messages": [{"role": "user", "content": PROMPT}],
                       "modalities": ["image", "text"]}).encode()
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions", data=body,
        headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json",
                 "HTTP-Referer": "https://local", "X-Title": "fig1 workflow"})
    resp = json.loads(urllib.request.urlopen(req, timeout=240).read())
    msg = resp["choices"][0]["message"]
    imgs = msg.get("images") or []
    if not imgs:
        print("NO image. text:", (msg.get("content") or "")[:400], "usage:", resp.get("usage"))
        return
    for i, im in enumerate(imgs):
        url = im.get("image_url", {}).get("url", "") if isinstance(im, dict) else ""
        if url.startswith("data:"):
            (OUT / f"fig1_workflow_draft_{i}.png").write_bytes(base64.b64decode(url.split(",", 1)[1]))
            print(f"Saved -> {OUT / f'fig1_workflow_draft_{i}.png'}  cost={resp.get('usage',{}).get('cost')}")


if __name__ == "__main__":
    main()
