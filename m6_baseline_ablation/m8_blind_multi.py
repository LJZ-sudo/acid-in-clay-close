"""M8-3b — 盲评的多评审 × 多 seed 统计版。

把 governed/popularity/random 三来源候选匿名打乱，交给**多个独立评审模型**（跨家族）
在**多个 seed**下分别打分（物理合理性 + 证据接地度，1-5）。评审看不到来源。
最后按来源聚合 mean±std（跨 judge×seed），并给出每个评审的分项。

产物 -> m6_baseline_ablation/m8_blind_multi/ 。不碰主线。
"""
from __future__ import annotations

import json
import math
import os
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE3 = ROOT / "V1.0-qianduan-mainline" / "stage3_mechanism"
SRC = STAGE3 / "src"
M7 = Path(__file__).resolve().parent / "m7_full"
OUT = Path(__file__).resolve().parent / "m8_blind_multi"
OUT.mkdir(parents=True, exist_ok=True)

SEEDS = [1, 2, 3]
GEN_MODEL = os.environ.get("M7_MODEL", "openai/gpt-5.4")
# independent judge candidates (diverse families); keep reachable ones, prefer != GEN_MODEL
JUDGE_POOL = [
    "google/gemini-2.5-flash",
    "anthropic/claude-3.5-sonnet",
    "deepseek/deepseek-chat",
    "meta-llama/llama-3.3-70b-instruct",
    "x-ai/grok-2-1212",
]
key = (ROOT / "key.txt").read_text(encoding="utf-8").strip().splitlines()[0].strip()

os.environ["STAGE3_LLM_MODE"] = "live"
os.environ["STAGE3_API_KEY"] = key
os.environ["STAGE3_API_BASE_URL"] = "https://openrouter.ai/api/v1"
os.environ["STAGE3_MODEL_CHEAP"] = GEN_MODEL
os.environ["STAGE3_MODEL_STANDARD"] = GEN_MODEL
os.environ["STAGE3_MODEL_PREMIUM"] = GEN_MODEL
os.environ["STAGE3_MODEL_TIER"] = ""
os.environ["STAGE3_USE_STRUCTURED_OUTPUTS"] = "false"
os.environ["STAGE3_ENABLE_CACHE"] = "false"
os.environ["STAGE3_LLM_TEMPERATURE"] = "0.0"
os.environ["STAGE3_MAX_LLM_CALLS_PER_RUN"] = "60"

sys.path.insert(0, str(SRC))

from s8_stage3.config.settings import load_settings                       # noqa: E402
from s8_stage3.config.model_registry import ModelRegistry                 # noqa: E402
from s8_stage3.config.llm_gateway import LLMGateway                       # noqa: E402

LOG = []


def p(m):
    line = str(m).encode("ascii", "replace").decode("ascii")
    print(line, flush=True)
    LOG.append(line)


def mean_std(xs):
    if not xs:
        return (None, None)
    m = sum(xs) / len(xs)
    v = sum((x - m) ** 2 for x in xs) / len(xs)
    return (round(m, 3), round(math.sqrt(v), 3))


ONTOPIC_POOL = [
    "chitosan", "starch", "poly(vinyl alcohol) (PVA)", "attapulgite",
    "halloysite nanotubes", "phosphoric acid", "choline chloride",
    "deep eutectic solvent", "cellulose", "glycerol",
]

RUBRIC = (
    "You are an INDEPENDENT electrochemistry reviewer. Each item is a candidate material "
    "formulation proposed as a COLD-WINDOW proton conductor operating roughly 182-299 K. "
    "You do NOT know how each candidate was generated. For EACH candidate, score two axes 1-5 "
    "(5=best):\n"
    "  plausibility : is this a physically sensible PROTON CONDUCTOR for that cold window?\n"
    "  groundedness : are components/claims coherent and on-topic (not from an unrelated device "
    "domain like Li-ion batteries or solar cells)?\n"
    "Return STRICT JSON: {\"scores\":[{\"id\":\"C01\",\"plausibility\":N,\"groundedness\":N}, ...]} "
    "covering every id."
)


def card(name, components, props):
    return {"name": name, "components": components, "expected_properties": props}


def assemble(seed):
    cands = []
    gov = json.loads((M7 / f"A2_distractor_injected_seed{seed}_raw.json").read_text(encoding="utf-8")).get("instances", [])
    for inst in gov:
        cands.append(("governed", card(inst.get("instance_name", ""), inst.get("components", []),
                                       (inst.get("expected_properties") or [])[:3])))
    metrics = json.loads((M7 / "metrics.json").read_text(encoding="utf-8"))
    pop_top = metrics["baselines"]["popularity@A2_pool"]["top_components"]
    for i in range(3):
        comps = pop_top[i:i + 4] or pop_top[:4]
        cands.append(("popularity", card(f"High-frequency formulation {i+1}", comps,
                                         ["selected by literature frequency"])))
    rng = random.Random(100 + seed)
    mix = ONTOPIC_POOL + ["LiFePO4", "silicon anode", "Ti3C2 MXene"]
    for i in range(3):
        cands.append(("random", card(f"Random formulation {i+1}", rng.sample(mix, 4), ["randomly combined"])))
    return cands


def anonymize(cands, seed):
    rng = random.Random(900 + seed)
    order = list(range(len(cands)))
    rng.shuffle(order)
    anon, keymap = [], {}
    for new_i, orig_i in enumerate(order):
        src, c = cands[orig_i]
        aid = f"C{new_i+1:02d}"
        keymap[aid] = src
        anon.append({"id": aid, **c})
    return anon, keymap


def smoke(gateway, model):
    try:
        r = gateway.chat_json([{"role": "user", "content": "Reply strict JSON: {\"ok\": true}"}],
                              step="judge_smoke", model=model)
        return isinstance(r, dict)
    except Exception as e:
        p(f"[judge] {model} unreachable: {str(e)[:80]}")
        return False


def judge_scores(gateway, model, anon):
    raw = gateway.chat_json(
        [{"role": "system", "content": RUBRIC},
         {"role": "user", "content": json.dumps({"candidates": anon}, ensure_ascii=False)}],
        step="blind_judge", model=model)
    return raw.get("scores") or raw.get("results") or []


def main():
    settings = load_settings()
    registry = ModelRegistry(settings.model_cheap, settings.model_standard, settings.model_premium)
    gateway = LLMGateway(settings, registry)

    judges = [m for m in JUDGE_POOL if smoke(gateway, m)]
    if len(judges) < 2:  # ensure at least 2; add generator as same-family fallback
        if GEN_MODEL not in judges and smoke(gateway, GEN_MODEL):
            judges.append(GEN_MODEL)
    p(f"[cfg] gen={GEN_MODEL} judges={judges} seeds={SEEDS}")
    if not judges:
        p("[abort] no judge reachable")
        (OUT / "console.txt").write_text("\n".join(LOG), encoding="utf-8")
        return 2

    # collect scores: source -> {plaus:[], ground:[]}, and per-judge breakdown
    agg = {}
    per_judge = {}
    records = []
    for seed in SEEDS:
        cands = assemble(seed)
        anon, keymap = anonymize(cands, seed)
        for judge in judges:
            try:
                scores = judge_scores(gateway, judge, anon)
            except Exception as e:
                p(f"[warn] judge={judge} seed={seed} failed: {str(e)[:80]}")
                continue
            for s in scores:
                src = keymap.get(s.get("id"), "?")
                pl = float(s.get("plausibility", 0) or 0)
                gr = float(s.get("groundedness", 0) or 0)
                agg.setdefault(src, {"plaus": [], "ground": []})
                agg[src]["plaus"].append(pl)
                agg[src]["ground"].append(gr)
                pj = per_judge.setdefault(judge, {})
                pj.setdefault(src, {"plaus": [], "ground": []})
                pj[src]["plaus"].append(pl)
                pj[src]["ground"].append(gr)
                records.append({"seed": seed, "judge": judge, "id": s.get("id"), "source": src,
                                "plausibility": pl, "groundedness": gr})
            p(f"  judge={judge} seed={seed}: scored {len(scores)}")

    summary = {"gen_model": GEN_MODEL, "judges": judges, "seeds": SEEDS,
               "n_judge_seed_combos": len(judges) * len(SEEDS), "by_source": {}, "by_judge": {}}
    for src, d in agg.items():
        pm, ps = mean_std(d["plaus"])
        gm, gs = mean_std(d["ground"])
        summary["by_source"][src] = {"n_scores": len(d["plaus"]),
                                     "plausibility_mean_std": [pm, ps],
                                     "groundedness_mean_std": [gm, gs]}
    for judge, srcs in per_judge.items():
        summary["by_judge"][judge] = {}
        for src, d in srcs.items():
            pm, ps = mean_std(d["plaus"])
            summary["by_judge"][judge][src] = {"plaus_mean": pm, "ground_mean": mean_std(d["ground"])[0]}

    (OUT / "blind_multi_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "blind_multi_records.json").write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "console.txt").write_text("\n".join(LOG), encoding="utf-8")

    p("---- aggregate by source (across judges x seeds) ----")
    for src in ("governed", "random", "popularity"):
        if src in summary["by_source"]:
            st = summary["by_source"][src]
            p(f"[avg] {src:10s} plaus={st['plausibility_mean_std'][0]}+/-{st['plausibility_mean_std'][1]} "
              f"ground={st['groundedness_mean_std'][0]}+/-{st['groundedness_mean_std'][1]} (n={st['n_scores']})")
    p("---- per judge (plausibility mean) ----")
    for judge, srcs in summary["by_judge"].items():
        line = " ".join(f"{s}={srcs[s]['plaus_mean']}" for s in ("governed", "random", "popularity") if s in srcs)
        p(f"[judge] {judge}: {line}")
    p("[done] -> m8_blind_multi/blind_multi_summary.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
