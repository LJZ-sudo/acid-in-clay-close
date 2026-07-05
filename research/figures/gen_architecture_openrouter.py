# -*- coding: utf-8 -*-
"""Typeset the code-grounded ASCII architecture into a clean diagram via OpenRouter.

The raw ASCII (SYSTEM_ARCHITECTURE_CODE_GROUNDED_20260622.md) is too dense for an image model,
so we feed a STRUCTURED, diagram-appropriate spec (6 stages + flow + decision nodes + badges)
and ask for a professional software-architecture flowchart. DRAFT only; final = draw.io/PPT.
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
    "Create a clean, professional SYSTEM-ARCHITECTURE / data-flow diagram (engineering flowchart "
    "style, white background, restrained palette: deep blue, teal, grey, one orange accent; thin "
    "clean strokes; large legible sans-serif labels; clear arrows). Title at top: "
    "'Acid-in-Clay closed-loop self-driving lab — code-grounded pipeline'. Landscape 16:9.\n\n"
    "SIX numbered stage boxes, connected TOP-TO-BOTTOM by labelled arrows. Put a small rounded "
    "badge on each box: green 'DETERMINISTIC' or blue 'LLM' as noted.\n\n"
    "1) STAGE 0 - Measurement to Evidence  [badge DETERMINISTIC]\n"
    "   variable-temperature impedance (+25 to -90 C); per-point chain: data QA -> Kramers-Kronig "
    "validation -> bulk-resistance fitting (4 strategies) -> DRT -> segmented Arrhenius (AICc model "
    "competition). Outputs: sigma(T), Ea, transition temperature, quality flags.\n"
    "   arrow down labelled 'sigma(T) | Ea | T_break'\n"
    "2) STAGE 1 - Closed-loop optimisation  [badge: LLM only at planner step]\n"
    "   six steps; multi-objective Bayesian optimisation (ParEGO + Gaussian process Matern-2.5 + "
    "Expected Improvement) -> LLM strategy planner (safety screening + fallback) -> safety "
    "validator -> termination A/B/C/D. small decision diamond: 'cold-start < 5 -> random sampling'.\n"
    "   arrow down labelled 'history_db  (R,N -> combined_score)'\n"
    "3) STAGE 2 - Statistics to evidence atlas  [badge DETERMINISTIC]\n"
    "   eight evidence units -> hash-anchored seed.\n"
    "   arrow down labelled 'seed (sha256-anchored)'\n"
    "4) STAGE 3 - Mechanism reasoning + candidate generation + claim governance\n"
    "   sub-flow left-to-right: S04-S08 reasoning/literature [LLM] -> S09 candidate generation "
    "[badge DETERMINISTIC by default] -> S10 ranking (8-weight score) -> S14 claim ladder C0-C5 "
    "(EIS capped at C4) + advisory critic/memory. To the right, two boundary badges stacked: "
    "orange 'identifiability ceiling (mechanism not claimable)' on top, blue 'reproducibility floor' "
    "at bottom, framing the governed outputs (design rules, prospective candidates).\n"
    "5) BACKEND API + read-only cockpit\n"
    "   FastAPI + Socket.IO (port 8000); provenance & campaigns read-only; pipeline router DISABLED.\n"
    "6) v2 guardrail engine  [badge: claims HOLD, CHI automation OFF]\n"
    "   SHA-256 append-only chain + hash-bound human approval.\n\n"
    "BOTTOM ribbon spanning the full width: 'Guardrails: replay != real | separate history per "
    "system | claim audit | prospective freeze (git timestamp)'.\n\n"
    "Keep it minimal and readable, like a Nature/IEEE system-architecture figure. No clutter, no "
    "code snippets, large labels only."
)


def main():
    body = json.dumps({"model": MODEL, "messages": [{"role": "user", "content": PROMPT}],
                       "modalities": ["image", "text"]}).encode()
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions", data=body,
        headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json",
                 "HTTP-Referer": "https://local", "X-Title": "acid-in-clay architecture diagram"})
    resp = json.loads(urllib.request.urlopen(req, timeout=240).read())
    msg = resp["choices"][0]["message"]
    imgs = msg.get("images") or []
    if not imgs:
        print("No image. text:", (msg.get("content") or "")[:400], "usage:", resp.get("usage"))
        return
    for i, im in enumerate(imgs):
        url = im.get("image_url", {}).get("url", "") if isinstance(im, dict) else ""
        if url.startswith("data:"):
            (OUT / f"architecture_diagram_draft_{i}.png").write_bytes(
                base64.b64decode(url.split(",", 1)[1]))
            print(f"Saved -> {OUT / f'architecture_diagram_draft_{i}.png'}  cost={resp.get('usage',{}).get('cost')}")


if __name__ == "__main__":
    main()
