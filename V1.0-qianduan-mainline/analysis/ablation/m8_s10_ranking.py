"""M8 task2 — 把抗干扰对照延伸到 S10 排序阶段。

构造一个被污染的候选集 = M7 治理 agent 生成的 5 个质子导体候选 + 3 个高显著 off-topic
干扰候选（LiFePO4 电池正极 / 硅负极 / CsPbI3 钙钛矿太阳能）。让**真 LLM S10**（关掉
s10_deterministic_from_audit）排序，看治理是否在排序阶段也把干扰项压到底部 / 给低分。

产物 -> V1.0-qianduan-mainline/analysis/ablation/m8_s10/ ，不碰主线。
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = next(_p for _p in Path(__file__).resolve().parents if _p.name == "V1.0-qianduan-mainline").parent
STAGE3 = ROOT / "V1.0-qianduan-mainline" / "stage3_mechanism"
SRC = STAGE3 / "src"
FROZEN = STAGE3 / "outputs" / "verification" / "20260607_openrouter_publication_v2"
M7 = Path(__file__).resolve().parent / "m7_full"
OUT = Path(__file__).resolve().parent / "m8_s10"
OUT.mkdir(parents=True, exist_ok=True)

MODEL = os.environ.get("M7_MODEL", "openai/gpt-5.4")
key = (ROOT / "key.txt").read_text(encoding="utf-8").strip().splitlines()[0].strip()

os.environ["STAGE3_LLM_MODE"] = "live"
os.environ["STAGE3_API_KEY"] = key
os.environ["STAGE3_API_BASE_URL"] = "https://openrouter.ai/api/v1"
os.environ["STAGE3_MODEL_CHEAP"] = MODEL
os.environ["STAGE3_MODEL_STANDARD"] = MODEL
os.environ["STAGE3_MODEL_PREMIUM"] = MODEL
os.environ["STAGE3_MODEL_TIER"] = ""
os.environ["STAGE3_S10_DETERMINISTIC_FROM_AUDIT"] = "false"   # <-- real LLM ranker
os.environ["STAGE3_USE_STRUCTURED_OUTPUTS"] = "false"
os.environ["STAGE3_ENABLE_CACHE"] = "false"
os.environ["STAGE3_LLM_TEMPERATURE"] = "0.2"
os.environ["STAGE3_MAX_LLM_CALLS_PER_RUN"] = "20"

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


def distractor_instances():
    def mk(iid, name, comps, props, pid):
        return {
            "instance_id": iid,
            "family_id": "FX",
            "instance_name": name,
            "composition_description": name,
            "components": comps,
            "expected_properties": props,
            "risk_flags": [],
            "combination_novelty": "exact_match",
            "element_evidence": [{
                "component": comps[0],
                "role_in_formulation": "primary active material (off-topic device)",
                "descriptor_satisfied": ["D5", "D6"],
                "analog_paper_ids": [pid],
                "analog_reason": "highly cited high-performance material",
            }],
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


def main():
    settings = load_settings()
    registry = ModelRegistry(settings.model_cheap, settings.model_standard, settings.model_premium)
    gateway = LLMGateway(settings, registry)
    p(f"[cfg] model={MODEL} s10_det={settings.s10_deterministic_from_audit} (real LLM ranker)")
    if not gateway.smoke_chat():
        p("[abort] endpoint unreachable")
        (OUT / "console.txt").write_text("\n".join(LOG), encoding="utf-8")
        return 2

    # governed candidates from M7 A2 (distractor-pool) seed1
    gov_raw = json.loads((M7 / "A2_distractor_injected_seed1_raw.json").read_text(encoding="utf-8"))
    gov = gov_raw.get("instances", [])
    for inst in gov:  # ensure required key present
        for ev in inst.get("element_evidence", []) or []:
            ev.setdefault("role_in_formulation", ev.get("analog_reason") or "(unlabeled)")
    dis = distractor_instances()
    distractor_ids = {d["instance_id"] for d in dis}

    # interleave so position can't bias the ranker
    candidates = []
    for i in range(max(len(gov), len(dis))):
        if i < len(gov):
            candidates.append(gov[i])
        if i < len(dis):
            candidates.append(dis[i])
    p(f"[input] governed={len(gov)} distractors={len(dis)} total={len(candidates)}")

    mech = json.loads((FROZEN / "04_mechanism" / "mechanism_card.json").read_text(encoding="utf-8"))
    mech_card = mech.get("mechanism_card", mech)
    lit = LiteratureSurvey.model_validate(
        json.loads((FROZEN / "06_literature_materials" / "literature_cards_materials.json").read_text(encoding="utf-8"))
    ).model_dump(mode="json")

    packed = pack_for_s10(candidates, mech_card, lit, None)
    p("[s10] calling real LLM ranker ...")
    raw = gateway.chat_json(
        [{"role": "system", "content": load_prompt("s10_instance_ranker")},
         {"role": "user", "content": packed}],
        step="s10_instance_ranker",
        output_schema=RankingResult,
    )
    (OUT / "s10_raw.json").write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")

    # normalize
    if "ranked_candidates" not in raw:
        for a in ("rankings", "candidates", "top_candidates"):
            if a in raw:
                raw["ranked_candidates"] = raw.pop(a)
                break
    result = RankingResult.model_validate(raw)
    result.ranked_candidates.sort(key=lambda c: c.rank)

    n = len(result.ranked_candidates)
    rows = []
    distractor_ranks = []
    gov_ranks = []
    for c in result.ranked_candidates:
        is_d = c.instance_id in distractor_ids
        (distractor_ranks if is_d else gov_ranks).append(c.rank)
        rows.append((c.rank, c.instance_id, "DISTRACTOR" if is_d else "governed",
                     round(c.total_score, 3), c.instance_name[:48]))
        p(f"  #{c.rank} [{'DISTRACTOR' if is_d else 'governed  '}] score={round(c.total_score,3)} "
          f"{c.instance_id} {c.instance_name[:48]}")

    summary = {
        "n_candidates": n,
        "n_governed": len(gov_ranks),
        "n_distractors": len(distractor_ranks),
        "distractor_ranks": sorted(distractor_ranks),
        "governed_ranks": sorted(gov_ranks),
        "worst_governed_rank": max(gov_ranks) if gov_ranks else None,
        "best_distractor_rank": min(distractor_ranks) if distractor_ranks else None,
        "all_distractors_below_all_governed": (
            bool(distractor_ranks and gov_ranks and min(distractor_ranks) > max(gov_ranks))
        ),
        "avg_distractor_score": round(
            sum(c.total_score for c in result.ranked_candidates if c.instance_id in distractor_ids)
            / (len(distractor_ranks) or 1), 3),
        "avg_governed_score": round(
            sum(c.total_score for c in result.ranked_candidates if c.instance_id not in distractor_ids)
            / (len(gov_ranks) or 1), 3),
    }
    (OUT / "ranking_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "console.txt").write_text("\n".join(LOG), encoding="utf-8")
    p(f"[verdict] all_distractors_below_all_governed={summary['all_distractors_below_all_governed']} "
      f"avg_score governed={summary['avg_governed_score']} vs distractor={summary['avg_distractor_score']}")
    p("[done] -> m8_s10/ranking_summary.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
