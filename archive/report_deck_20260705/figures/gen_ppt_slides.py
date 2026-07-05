# -*- coding: utf-8 -*-
"""Generate two PPT layout images via OpenRouter:

  slide1_three_innovations  - three plain-language innovation cards (WHAT / HOW SURE / HOW MADE)
  slide2_idea_flow          - one horizontal 5-step arrow telling the storyline

Plain language on purpose (the earlier wording was too abstract). ENGLISH short labels only
(image models render English reliably); the text is meant to be re-typed in PowerPoint. DRAFT.
"""
import base64
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
KEY = (ROOT / "key.txt").read_text(encoding="utf-8").strip()
OUT = Path(__file__).resolve().parent
MODEL = "google/gemini-3-pro-image"

SLIDE1 = (
    "Create a clean, professional PRESENTATION SLIDE layout (16:9, white background, flat vector, "
    "generous whitespace, restrained palette: deep blue + teal + grey with ONE orange accent, large "
    "legible sans-serif text, NO clutter, no icons-with-filenames). This is the opening slide of a "
    "research talk.\n\n"
    "TITLE at top (bold): 'Three things this paper contributes'.\n"
    "Subtitle line under it (smaller, grey): 'Setting: only impedance data, few samples, no extra "
    "structural characterisation'.\n\n"
    "THREE equal CARDS side by side, each with a big number badge (1,2,3), a short bold heading, one "
    "plain sentence, and a tiny evidence line at the bottom:\n\n"
    "CARD 1 - teal accent - heading 'WHAT WE FOUND'. Sentence: 'Protons still conduct below 0 C, and "
    "the turning-point temperature can be tuned by the recipe.' Evidence line: '13 repeats, 4 material "
    "families, turn at -22 to -39 C'.\n\n"
    "CARD 2 - blue accent - heading 'HOW SURE WE CAN BE'. Sentence: 'Two rulers from the same data: a "
    "FLOOR for how well we can measure, and a CEILING for what we are allowed to claim.' Evidence line: "
    "'measurement floor ~0.25 dex; rival mechanisms indistinguishable'.\n\n"
    "CARD 3 - orange accent - heading 'HOW IT WAS MADE'. Sentence: 'A real propose-make-measure loop "
    "that never over-claims.' Evidence line: 'Bayesian search beats random; language-model keeps it "
    "safe; honest result reported'.\n\n"
    "Keep it minimal and elegant, like a top-conference title slide. Large text only, no paragraphs."
)

SLIDE2 = (
    "Create a clean, professional PRESENTATION SLIDE layout (16:9, white background, flat vector, "
    "generous whitespace, restrained palette: deep blue + teal + grey with one orange accent, large "
    "legible sans-serif text). This slide shows the STORYLINE as ONE horizontal left-to-right arrow "
    "passing through FIVE numbered chevron/arrow steps.\n\n"
    "TITLE at top (bold): 'The storyline in one line'.\n\n"
    "FIVE chevron steps connected by a single big arrow:\n"
    "STEP 1 (grey): 'Hard setting' - 'impedance data only, few samples'.\n"
    "STEP 2 (teal): 'We found something' - 'a sub-zero conductivity turn that the recipe can tune'.\n"
    "STEP 3 (blue): 'Can we trust it?' - 'measure a reproducibility FLOOR + recalibrate confidence'.\n"
    "STEP 4 (orange): 'How far can we claim?' - 'an identifiability CEILING: mechanism not claimable'.\n"
    "STEP 5 (blue): 'Did the loop help?' - 'search faster, stays safe, honest null result'.\n\n"
    "BELOW the arrow leave clear whitespace, then ONE single centered bold summary line (write it "
    "EXACTLY once, do not repeat it): A floor and a ceiling frame what an honest self-driving lab can "
    "discover.\n\n"
    "Minimal, elegant, conference-grade. Large text only, no paragraphs, no extra icons."
)

VARIANTS = {"slide1_three_innovations": SLIDE1, "slide2_idea_flow": SLIDE2}


def gen(tag, prompt):
    body = json.dumps({"model": MODEL, "messages": [{"role": "user", "content": prompt}],
                       "modalities": ["image", "text"]}).encode()
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions", data=body,
        headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json",
                 "HTTP-Referer": "https://local", "X-Title": f"ppt {tag}"})
    resp = json.loads(urllib.request.urlopen(req, timeout=240).read())
    msg = resp["choices"][0]["message"]
    imgs = msg.get("images") or []
    if not imgs:
        print(f"{tag}: NO image. text={(msg.get('content') or '')[:300]} usage={resp.get('usage')}")
        return
    for i, im in enumerate(imgs):
        url = im.get("image_url", {}).get("url", "") if isinstance(im, dict) else ""
        if url.startswith("data:"):
            (OUT / f"{tag}.png").write_bytes(base64.b64decode(url.split(",", 1)[1]))
            print(f"Saved -> {OUT / f'{tag}.png'}  cost={resp.get('usage',{}).get('cost')}")
            return


def main():
    for tag, prompt in VARIANTS.items():
        try:
            gen(tag, prompt)
        except Exception as e:
            print(f"{tag}: ERROR {e}")


if __name__ == "__main__":
    main()
