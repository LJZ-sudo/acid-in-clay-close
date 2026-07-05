"""M8-2b — S10 排序抗干扰的多 seed 统计版。

对 M7 的 5 个 A2 治理候选集（seed1..5），各自 + 同样 3 个 off-topic 干扰候选，
逐 seed 打乱顺序，用真 LLM S10 排序器排序，记录每 seed 指标，最后聚合 mean±std
与 "全部干扰项被压到治理之下" 的命中比例。

产物 -> V1.0-qianduan-mainline/analysis/ablation/m8_s10_multi/ 。不碰主线。
"""
from __future__ import annotations

import json
import math
import os
import random
import sys
from pathlib import Path

ROOT = next(_p for _p in Path(__file__).resolve().parents if _p.name == "V1.0-qianduan-mainline").parent
STAGE3 = ROOT / "V1.0-qianduan-mainline" / "stage3_mechanism"
SRC = STAGE3 / "src"
FROZEN = STAGE3 / "outputs" / "verification" / "20260607_openrouter_publication_v2"
M7 = Path(__file__).resolve().parent / "m7_full"
OUT = Path(__file__).resolve().parent / "m8_s10_multi"
OUT.mkdir(parents=True, exist_ok=True)

SEEDS = [1, 2, 3, 4, 5]
MODEL = os.environ.get("M7_MODEL", "openai/gpt-5.4")
key = (ROOT / "key.txt").read_text(encoding="utf-8").strip().splitlines()[0].strip()

os.environ["STAGE3_LLM_MODE"] = "live"
os.environ["STAGE3_API_KEY"] = key
os.environ["STAGE3_API_BASE_URL"] = "https://openrouter.ai/api/v1"
os.environ["STAGE3_MODEL_CHEAP"] = MODEL
os.environ["STAGE3_MODEL_STANDARD"] = MODEL
os.environ["STAGE3_MODEL_PREMIUM"] = MODEL
os.environ["STAGE3_MODEL_TIER"] = ""
os.environ["STAGE3_S10_DETERMINISTIC_FROM_AUDIT"] = "false"
os.environ["STAGE3_USE_STRUCTURED_OUTPUTS"] = "false"
os.environ["STAGE3_ENABLE_CACHE"] = "false"
os.environ["STAGE3_LLM_TEMPERATURE"] = "0.3"
os.environ["STAGE3_MAX_LLM_CALLS_PER_RUN"] = "40"

sys.path.insert(0, str(SRC))

from s8_stage3.config.settings import load_settings                       # noqa: E402
from s8_stage3.config.model_registry import ModelRegistry                 # noqa: E402
from s8_stage3.config.llm_gateway import LLMGateway                       # noqa: E402
from s8_stage3.config.prompt_registry import load_prompt                  # noqa: E402
from s8_stage3.contracts.literature import LiteratureSurvey               # noqa: E402
from s8_stage3.contracts.ranking import RankingResult                     # noqa: E402
from s8_stage3.llm.prompt_packing import pack_for_s10                     # noqa: E402

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


def distractor_instances():
    def mk(iid, name, comps, props, pid):
        return {
            "instance_id": iid, "family_id": "FX", "instance_name": name,
            "composition_description": name, "components": comps,
            "expected_properties": props, "risk_flags": [],
            "combination_novelty": "exact_match",
            "element_evidence": [{
                "component": comps[0],
                "role_in_formulation": "primary active material (off-topic device)",
                "descriptor_satisfied": ["D5", "D6"], "analog_paper_ids": [pid],
                "analog_reason": "highly cited high-performance material"}],
            "literature_support_card_ids": [pid],
            "novelty_rationale": "Famous, highly cited material from a different application domain.",
            "origin": "llm_selected_from_broad_pool",
            "source_mode": "broad_literature_pool_selection",
        }
    return [
        mk("X1", "LiFePO4 lithium-ion battery cathode", ["LiFePO4", "carbon coating", "lithium"],
           ["capacity: 170 mAh/g", "cycling: >2000 cycles", "voltage: 3.4 V"], "distractor_lifepo4"),
        mk("X2", "Silicon nanostructured Li-ion anode", ["silicon anode", "carbon"],
           ["capacity: 3579 mAh/g", "high energy density"], "distractor_silicon"),
        mk("X3", "CsPbI3 perovskite solar absorber", ["CsPbI3 perovskite solar", "FTO glass"],
           ["PCE: 21%", "bandgap: 1.7 eV"], "distractor_cspbi3"),
    ]


def run_once(gateway, governed, distractors, mech_card, lit, shuffle_seed):
    distractor_ids = {d["instance_id"] for d in distractors}
    rng = random.Random(shuffle_seed)
    cands = governed + distractors
    rng.shuffle(cands)
    packed = pack_for_s10(cands, mech_card, lit, None)
    raw = gateway.chat_json(
        [{"role": "system", "content": load_prompt("s10_instance_ranker")},
         {"role": "user", "content": packed}],
        step="s10_instance_ranker", output_schema=RankingResult)
    if "ranked_candidates" not in raw:
        for a in ("rankings", "candidates", "top_candidates"):
            if a in raw:
                raw["ranked_candidates"] = raw.pop(a)
                break
    result = RankingResult.model_validate(raw)
    result.ranked_candidates.sort(key=lambda c: c.rank)
    gov_ranks, dis_ranks, gov_sc, dis_sc = [], [], [], []
    for c in result.ranked_candidates:
        if c.instance_id in distractor_ids:
            dis_ranks.append(c.rank); dis_sc.append(c.total_score)
        else:
            gov_ranks.append(c.rank); gov_sc.append(c.total_score)
    return {
        "all_distractors_below_all_governed": bool(
            dis_ranks and gov_ranks and min(dis_ranks) > max(gov_ranks)),
        "worst_governed_rank": max(gov_ranks) if gov_ranks else None,
        "best_distractor_rank": min(dis_ranks) if dis_ranks else None,
        "avg_governed_score": round(sum(gov_sc) / len(gov_sc), 3) if gov_sc else None,
        "avg_distractor_score": round(sum(dis_sc) / len(dis_sc), 3) if dis_sc else None,
        "n_governed": len(gov_ranks), "n_distractors": len(dis_ranks),
    }


def main():
    settings = load_settings()
    registry = ModelRegistry(settings.model_cheap, settings.model_standard, settings.model_premium)
    gateway = LLMGateway(settings, registry)
    p(f"[cfg] model={MODEL} seeds={SEEDS} s10_det={settings.s10_deterministic_from_audit}")

    mech = json.loads((FROZEN / "04_mechanism" / "mechanism_card.json").read_text(encoding="utf-8"))
    mech_card = mech.get("mechanism_card", mech)
    lit = LiteratureSurvey.model_validate(json.loads(
        (FROZEN / "06_literature_materials" / "literature_cards_materials.json").read_text(encoding="utf-8")
    )).model_dump(mode="json")
    dis = distractor_instances()

    per_seed = []
    for s in SEEDS:
        gov_raw = json.loads((M7 / f"A2_distractor_injected_seed{s}_raw.json").read_text(encoding="utf-8"))
        gov = gov_raw.get("instances", [])
        for inst in gov:
            for ev in inst.get("element_evidence", []) or []:
                ev.setdefault("role_in_formulation", ev.get("analog_reason") or "(unlabeled)")
        r = run_once(gateway, list(gov), [dict(d) for d in dis], mech_card, lit, shuffle_seed=1000 + s)
        r["seed"] = s
        per_seed.append(r)
        p(f"  seed{s}: all_below={r['all_distractors_below_all_governed']} "
          f"gov_avg={r['avg_governed_score']} dis_avg={r['avg_distractor_score']} "
          f"worst_gov_rank={r['worst_governed_rank']} best_dis_rank={r['best_distractor_rank']}")

    n = len(per_seed)
    hits = sum(1 for r in per_seed if r["all_distractors_below_all_governed"])
    gov_m, gov_s = mean_std([r["avg_governed_score"] for r in per_seed if r["avg_governed_score"] is not None])
    dis_m, dis_s = mean_std([r["avg_distractor_score"] for r in per_seed if r["avg_distractor_score"] is not None])
    agg = {
        "n_seeds": n,
        "suppression_hit_rate": f"{hits}/{n}",
        "avg_governed_score_mean_std": [gov_m, gov_s],
        "avg_distractor_score_mean_std": [dis_m, dis_s],
        "score_gap_mean": round((gov_m - dis_m), 3) if (gov_m is not None and dis_m is not None) else None,
        "per_seed": per_seed,
    }
    (OUT / "s10_multiseed_summary.json").write_text(json.dumps(agg, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "console.txt").write_text("\n".join(LOG), encoding="utf-8")
    p(f"[agg] suppression {hits}/{n} | gov={gov_m}+/-{gov_s} dis={dis_m}+/-{dis_s} gap={agg['score_gap_mean']}")
    p("[done] -> m8_s10_multi/s10_multiseed_summary.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
