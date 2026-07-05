"""M8 task3 — 盲评（去掉"自评"嫌疑）。

把三类来源的候选混在一起、匿名、打乱顺序，交给一个**独立评审模型**按统一 rubric
对"作为冷窗(~182-299K)质子导体的物理合理性 + 证据接地度"打 1-5 分。评审看不到来源标签。

三类来源：
  governed   : M7 治理 agent 在污染池(A2)生成的候选
  popularity : 污染池里频次最高的组分堆出来的候选（= 干扰项主导）
  random     : 池内组分随机组配

评审模型优先用跨模型（与生成模型不同），不可达则回退生成模型并如实标注。
产物 -> V1.0-qianduan-mainline/analysis/ablation/m8_blind/ ，不碰主线。
"""
from __future__ import annotations

import json
import os
import random
import sys
from pathlib import Path

ROOT = next(_p for _p in Path(__file__).resolve().parents if _p.name == "V1.0-qianduan-mainline").parent
STAGE3 = ROOT / "V1.0-qianduan-mainline" / "stage3_mechanism"
SRC = STAGE3 / "src"
M7 = Path(__file__).resolve().parent / "m7_full"
OUT = Path(__file__).resolve().parent / "m8_blind"
OUT.mkdir(parents=True, exist_ok=True)

GEN_MODEL = os.environ.get("M7_MODEL", "openai/gpt-5.4")
# independent judge candidates (first reachable & different from GEN_MODEL preferred)
JUDGE_CANDIDATES = [
    os.environ.get("M8_JUDGE_MODEL", "").strip(),
    "google/gemini-2.5-flash",
    "anthropic/claude-3.5-sonnet",
    "openai/gpt-5.4",
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
os.environ["STAGE3_MAX_LLM_CALLS_PER_RUN"] = "20"

sys.path.insert(0, str(SRC))

from s8_stage3.config.settings import load_settings                       # noqa: E402
from s8_stage3.config.model_registry import ModelRegistry                 # noqa: E402
from s8_stage3.config.llm_gateway import LLMGateway                       # noqa: E402

LOG = []


def p(m):
    line = str(m).encode("ascii", "replace").decode("ascii")
    print(line, flush=True)
    LOG.append(line)


ONTOPIC_POOL = [
    "chitosan", "starch", "poly(vinyl alcohol) (PVA)", "attapulgite",
    "halloysite nanotubes", "phosphoric acid", "choline chloride",
    "deep eutectic solvent", "cellulose", "glycerol",
]


def candidate_card(name, components, props):
    return {"name": name, "components": components, "expected_properties": props}


def assemble():
    cands = []  # (source, card)
    # governed: from M7 A2 seed1
    gov = json.loads((M7 / "A2_distractor_injected_seed1_raw.json").read_text(encoding="utf-8")).get("instances", [])
    for inst in gov:
        cands.append(("governed", candidate_card(
            inst.get("instance_name", ""),
            inst.get("components", []),
            (inst.get("expected_properties") or [])[:3],
        )))
    # popularity: top components on the polluted pool (distractor-dominated)
    metrics = json.loads((M7 / "metrics.json").read_text(encoding="utf-8"))
    pop_top = metrics["baselines"]["popularity@A2_pool"]["top_components"]
    for i in range(3):
        comps = pop_top[i:i + 4] or pop_top[:4]
        cands.append(("popularity", candidate_card(
            f"High-frequency formulation {i+1}", comps,
            ["selected by literature frequency"])))
    # random: random combos from on-topic + distractor mix
    rng = random.Random(7)
    mix = ONTOPIC_POOL + ["LiFePO4", "silicon anode", "Ti3C2 MXene"]
    for i in range(3):
        comps = rng.sample(mix, 4)
        cands.append(("random", candidate_card(
            f"Random formulation {i+1}", comps, ["randomly combined"])))
    return cands


def pick_judge(gateway):
    for m in JUDGE_CANDIDATES:
        if not m:
            continue
        try:
            r = gateway.chat_json(
                [{"role": "user", "content": "Reply with strict JSON: {\"ok\": true}"}],
                step="judge_smoke", model=m)
            if isinstance(r, dict):
                p(f"[judge] {m} reachable")
                return m
        except Exception as e:
            p(f"[judge] {m} unreachable: {str(e)[:90]}")
    return GEN_MODEL


def main():
    settings = load_settings()
    registry = ModelRegistry(settings.model_cheap, settings.model_standard, settings.model_premium)
    gateway = LLMGateway(settings, registry)

    judge = pick_judge(gateway)
    cross = judge != GEN_MODEL
    p(f"[cfg] gen_model={GEN_MODEL} judge_model={judge} cross_model={cross}")

    cands = assemble()
    rng = random.Random(123)
    order = list(range(len(cands)))
    rng.shuffle(order)
    anon = []          # what the judge sees (no source)
    keymap = {}        # anon_id -> source
    for new_i, orig_i in enumerate(order):
        src, card = cands[orig_i]
        aid = f"C{new_i+1:02d}"
        keymap[aid] = src
        anon.append({"id": aid, **card})
    (OUT / "anonymized_candidates.json").write_text(
        json.dumps(anon, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "keymap.json").write_text(json.dumps(keymap, ensure_ascii=False, indent=2), encoding="utf-8")

    rubric = (
        "You are an INDEPENDENT electrochemistry reviewer. Each item is a candidate material "
        "formulation proposed as a COLD-WINDOW proton conductor operating roughly 182-299 K "
        "(sub-zero to room temperature). You do NOT know how each candidate was generated. "
        "For EACH candidate, score two axes 1-5 (5=best):\n"
        "  plausibility   : is this a physically sensible PROTON CONDUCTOR for that cold window?\n"
        "  groundedness   : are the components/claims coherent and on-topic (not from an unrelated "
        "device domain like Li-ion batteries or solar cells)?\n"
        "Return STRICT JSON: {\"scores\":[{\"id\":\"C01\",\"plausibility\":N,\"groundedness\":N,"
        "\"reason\":\"...\"}, ...]} covering every id."
    )
    user = json.dumps({"candidates": anon}, ensure_ascii=False)
    p(f"[blind] judging {len(anon)} anonymized candidates with {judge} ...")
    raw = gateway.chat_json(
        [{"role": "system", "content": rubric}, {"role": "user", "content": user}],
        step="blind_judge",
        model=judge,
    )
    (OUT / "judge_raw.json").write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")

    scores = raw.get("scores") or raw.get("results") or []
    by_src = {}
    rows = []
    for s in scores:
        aid = s.get("id")
        src = keymap.get(aid, "?")
        pl = float(s.get("plausibility", 0) or 0)
        gr = float(s.get("groundedness", 0) or 0)
        by_src.setdefault(src, []).append((pl, gr))
        rows.append((aid, src, pl, gr, str(s.get("reason", ""))[:60]))

    summary = {"judge_model": judge, "cross_model": cross, "by_source": {}}
    for src, vals in by_src.items():
        n = len(vals)
        summary["by_source"][src] = {
            "n": n,
            "avg_plausibility": round(sum(v[0] for v in vals) / n, 2),
            "avg_groundedness": round(sum(v[1] for v in vals) / n, 2),
        }
    (OUT / "blind_eval_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    for aid, src, pl, gr, reason in sorted(rows, key=lambda r: r[1]):
        p(f"  {aid} [{src:10s}] plaus={pl} ground={gr} {reason}")
    for src, st in summary["by_source"].items():
        p(f"[avg] {src:10s} plausibility={st['avg_plausibility']} groundedness={st['avg_groundedness']} (n={st['n']})")
    (OUT / "console.txt").write_text("\n".join(LOG), encoding="utf-8")
    p("[done] -> m8_blind/blind_eval_summary.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
