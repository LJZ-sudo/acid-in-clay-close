"""M7 full ablation — 量化 governed LLM agent (S09) 相对基线的增量。

实验矩阵（每个 LLM arm 跑 N seeds）：
  A0  governed_full       : 完整冻结证据池（pilot 配置）
  A1  ablate_evidence     : 抽空所有文献证据（只剩 D1-D7 描述符）-> 测"证据约束"的价值
  A2  distractor_injected : 在证据池里注入高显著 off-topic 干扰卡 -> 测抗干扰

非 LLM 基线（同池，确定性，可复现）：
  B_random      : 从池内组分随机组配
  B_popularity  : 按 claim 频次堆叠最热组分（会被 A2 干扰项带偏）

指标：
  distractor_inclusion_rate : 候选组分里命中 off-topic 词表的比例（越低越好）
  evidence_audit_rate       : 候选组分里有真实(池内)paper_id 支撑的比例（越高越好）
  ontopic_rate              : 候选组分命中质子导体相关词表的比例
  seed_stability_jaccard    : 同 arm 跨 seed 的组分集合平均 Jaccard

全部产物 -> V1.0-qianduan-mainline/analysis/ablation/m7_full/ ，不碰主线。
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter
from itertools import combinations
from pathlib import Path

ROOT = next(_p for _p in Path(__file__).resolve().parents if _p.name == "V1.0-qianduan-mainline").parent
STAGE3 = ROOT / "V1.0-qianduan-mainline" / "stage3_mechanism"
SRC = STAGE3 / "src"
FROZEN = STAGE3 / "outputs" / "verification" / "20260607_openrouter_publication_v2"
OUT = Path(__file__).resolve().parent / "m7_full"
OUT.mkdir(parents=True, exist_ok=True)

MODEL = os.environ.get("M7_MODEL", "openai/gpt-5.4")
N_SEEDS = int(os.environ.get("M7_N_SEEDS", "5"))

key = (ROOT / "key.txt").read_text(encoding="utf-8").strip().splitlines()[0].strip()

os.environ["STAGE3_LLM_MODE"] = "live"
os.environ["STAGE3_API_KEY"] = key
os.environ["STAGE3_API_BASE_URL"] = "https://openrouter.ai/api/v1"
os.environ["STAGE3_MODEL_CHEAP"] = MODEL
os.environ["STAGE3_MODEL_STANDARD"] = MODEL
os.environ["STAGE3_MODEL_PREMIUM"] = MODEL
os.environ["STAGE3_MODEL_TIER"] = ""
os.environ["STAGE3_S09_DETERMINISTIC_FROM_D4"] = "false"
os.environ["STAGE3_S09_EVIDENCE_BASED_GENERATION"] = "false"
os.environ["STAGE3_USE_STRUCTURED_OUTPUTS"] = "false"
os.environ["STAGE3_ENABLE_CACHE"] = "false"
os.environ["STAGE3_MAX_LLM_CALLS_PER_RUN"] = "60"

sys.path.insert(0, str(SRC))

from s8_stage3.config.settings import load_settings                       # noqa: E402
from s8_stage3.config.model_registry import ModelRegistry                 # noqa: E402
from s8_stage3.config.llm_gateway import LLMGateway                       # noqa: E402
from s8_stage3.config.prompt_registry import load_prompt                  # noqa: E402
from s8_stage3.contracts.literature import LiteratureSurvey               # noqa: E402
from s8_stage3.contracts.descriptor import DescriptorSheet                # noqa: E402
from s8_stage3.contracts.material import MaterialInstanceSet              # noqa: E402
from s8_stage3.llm.prompt_packing import pack_for_s09                     # noqa: E402
from s8_stage3.agents.s09_candidate_family_generator import (             # noqa: E402
    _S09Output,
    _compact_s09_payload,
)

# ---------------------------------------------------------------------------
# component classification word-lists
# ---------------------------------------------------------------------------
ONTOPIC = [
    "chitosan", "starch", "lotus", "amylose", "amylopectin", "cellulose",
    "poly(vinyl alcohol)", "pva", "attapulgite", "palygorskite", "halloysite",
    "hnt", "sepiolite", "montmorillonite", "clay", "kaolin",
    "phosphoric", "phosphate", "h3po4", "phosphonic",
    "deep eutectic", "des", "choline", "imidazole", "imidazolium",
    "hydrogel", "polyacrylamide", "paam", "sulfonated", "pbi", "nafion",
    "benzimidazole", "glycerol", "nb2o5", "graphene oxide", "go",
]
DISTRACTORS = [
    "lifepo4", "lithium iron phosphate", "silicon anode", "cspbi3", "cspbbr3",
    "perovskite solar", "halide perovskite", "mos2", "molybdenum disulfide",
    "tio2 photocatal", "platinum catalyst", "pt/c", "zno nanorod",
    "mxene", "ti3c2", "sodium-ion cathode", "supercapacitor electrode",
]


def classify(component: str) -> str:
    s = (component or "").lower()
    for d in DISTRACTORS:
        if d in s:
            return "distractor"
    for o in ONTOPIC:
        if o in s:
            return "ontopic"
    return "other"


# ---------------------------------------------------------------------------
# survey variants
# ---------------------------------------------------------------------------
def load_base():
    ds = DescriptorSheet.model_validate(
        json.loads((FROZEN / "05_descriptors" / "descriptor_sheet.json").read_text(encoding="utf-8"))
    )
    ls = LiteratureSurvey.model_validate(
        json.loads((FROZEN / "06_literature_materials" / "literature_cards_materials.json").read_text(encoding="utf-8"))
    )
    return ds, ls


def survey_ablate_evidence(ls: LiteratureSurvey) -> LiteratureSurvey:
    """A1: keep card count but redact ALL evidence content (title/summary/claims)."""
    d = ls.model_dump(mode="json")
    for i, c in enumerate(d["cards"]):
        c["title"] = f"redacted_card_{i}"
        c["summary"] = ""
        c["relevance_to_descriptors"] = ""
        c["relevance_to_mechanism"] = ""
        c["component_descriptor_claims"] = []
    return LiteratureSurvey.model_validate(d)


def _distractor_cards() -> list[dict]:
    """High-salience off-topic cards, each claiming to satisfy descriptors,
    with MANY claims so a popularity baseline gets dragged toward them."""
    specs = [
        ("LiFePO4", "LiFePO4 olivine cathode delivers 170 mAh/g with excellent cycling", ["D5", "D6", "D7"]),
        ("silicon anode", "Silicon anode reaches 3579 mAh/g via nanostructuring", ["D5", "D6", "D7"]),
        ("CsPbI3 perovskite solar", "CsPbI3 perovskite solar cell exceeds 21% PCE", ["D5", "D6"]),
        ("MoS2", "MoS2 basal-plane HER catalyst, 10 mA/cm2 at low overpotential", ["D5", "D7"]),
        ("Pt/C catalyst", "Pt/C ORR catalyst, mass activity 0.6 A/mg at 0.9 V", ["D6", "D7"]),
        ("Ti3C2 MXene", "Ti3C2 MXene supercapacitor electrode, 1500 F/cm3", ["D5", "D6", "D7"]),
    ]
    cards = []
    for name, finding, dids in specs:
        claims = []
        # repeat each (component, descriptor) several times -> inflate frequency
        for did in dids:
            for rep in range(3):
                claims.append({
                    "component": name,
                    "descriptor_ids": [did],
                    "quantitative_anchor": "highly cited, >1000 citations",
                    "claim_text": f"{finding} ({did}); widely cited high-performance material.",
                    "confidence": "supported",
                })
        cards.append({
            "card_id": f"distractor_{name.split()[0].lower()}",
            "title": f"Highly cited {name} (off-topic)",
            "authors": "",
            "year": 2024,
            "doi": "",
            "summary": f"Substance: {name}. Findings: {finding}.",
            "relevance_to_mechanism": "",
            "relevance_to_descriptors": f"{name} is a famous high-performance material.",
            "component_descriptor_claims": claims,
            "supports_hypothesis_ids": [],
            "weakens_hypothesis_ids": [],
        })
    return cards


def survey_distractor(ls: LiteratureSurvey) -> LiteratureSurvey:
    """A2: original pool + injected high-salience off-topic cards."""
    d = ls.model_dump(mode="json")
    d["cards"] = d["cards"] + _distractor_cards()
    return LiteratureSurvey.model_validate(d)


# ---------------------------------------------------------------------------
# LLM S09 (reproduces run_s09's genuine LLM branch + minimal repair)
# ---------------------------------------------------------------------------
def call_llm_s09(ds, ls_variant, gateway):
    packed = pack_for_s09(ds.model_dump(mode="json"), ls_variant.model_dump(mode="json"), None)
    prompt_name = "s09_family_generator"
    try:
        if json.loads(packed).get("descriptor_claim_pool"):
            packed = _compact_s09_payload(packed)
            prompt_name = "s09_family_generator_compact"
    except Exception:
        prompt_name = "s09_family_generator"
    raw = gateway.chat_json(
        [
            {"role": "system", "content": load_prompt(prompt_name)},
            {"role": "user", "content": packed},
        ],
        step="s09_candidate_family_generator",
        output_schema=_S09Output,
    )
    repaired = json.loads(json.dumps(raw))  # deep copy for validation
    for inst in repaired.get("instances", []) or []:
        for ev in inst.get("element_evidence", []) or []:
            if not ev.get("role_in_formulation"):
                ev["role_in_formulation"] = ev.get("analog_reason") or "(unlabeled)"
    parsed = _S09Output.model_validate(repaired)
    return raw, MaterialInstanceSet(instances=parsed.instances)


# ---------------------------------------------------------------------------
# deterministic baselines (no LLM)
# ---------------------------------------------------------------------------
def pool_components(ds, ls_variant):
    packed = json.loads(pack_for_s09(ds.model_dump(mode="json"), ls_variant.model_dump(mode="json"), None))
    freq = Counter()
    for cl in packed.get("descriptor_claim_pool", []):
        comp = cl.get("component")
        if comp:
            freq[comp] += 1
    for cp in packed.get("component_evidence_pool", []):
        comp = cp.get("component")
        if comp:
            freq[comp] += 1
    return freq


def baseline_random(freq, n_inst=5, size=4, seed=0):
    import random
    rng = random.Random(seed)
    comps = list(freq.keys())
    insts = []
    for _ in range(n_inst):
        k = min(size, len(comps))
        insts.append(rng.sample(comps, k) if comps else [])
    return insts


def baseline_popularity(freq, n_inst=5, size=4):
    top = [c for c, _ in freq.most_common(size)]
    return [list(top) for _ in range(n_inst)]


# ---------------------------------------------------------------------------
# metrics
# ---------------------------------------------------------------------------
def valid_paper_ids(ls_variant) -> set:
    return {c.card_id for c in ls_variant.cards}


def instance_components(instset) -> list[list[str]]:
    return [list(i.components) for i in instset.instances]


def metrics_for_components(list_of_comp_lists, valid_ids=None, instset=None):
    all_comps = [c for lst in list_of_comp_lists for c in lst]
    n = len(all_comps) or 1
    n_distract = sum(1 for c in all_comps if classify(c) == "distractor")
    n_ontopic = sum(1 for c in all_comps if classify(c) == "ontopic")
    out = {
        "n_instances": len(list_of_comp_lists),
        "n_components_total": len(all_comps),
        "distractor_inclusion_rate": round(n_distract / n, 3),
        "ontopic_rate": round(n_ontopic / n, 3),
    }
    # evidence audit only meaningful for LLM instances
    if instset is not None and valid_ids is not None:
        ev_total = 0
        ev_backed = 0
        for inst in instset.instances:
            for ev in inst.element_evidence:
                ev_total += 1
                pids = [p for p in ev.analog_paper_ids if p in valid_ids]
                if pids:
                    ev_backed += 1
        out["evidence_audit_rate"] = round(ev_backed / (ev_total or 1), 3)
        out["n_evidence_entries"] = ev_total
    return out


def jaccard(a, b):
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 1.0
    return len(sa & sb) / len(sa | sb or {1})


def seed_stability(per_seed_comp_lists):
    """avg pairwise Jaccard of the *set* of components used across seeds."""
    sets = [set(c for lst in seed for c in lst) for seed in per_seed_comp_lists]
    if len(sets) < 2:
        return 1.0
    vals = [jaccard(a, b) for a, b in combinations(sets, 2)]
    return round(sum(vals) / len(vals), 3)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main():
    log = []

    def p(m):
        line = str(m).encode("ascii", "replace").decode("ascii")
        print(line, flush=True)
        log.append(line)

    settings = load_settings()
    registry = ModelRegistry(settings.model_cheap, settings.model_standard, settings.model_premium)
    gateway = LLMGateway(settings, registry)
    p(f"[cfg] model={MODEL} n_seeds={N_SEEDS} s09_det={settings.s09_deterministic_from_d4}")

    if not gateway.smoke_chat():
        p("[abort] endpoint unreachable")
        (OUT / "console.txt").write_text("\n".join(log), encoding="utf-8")
        return 2

    ds, ls = load_base()
    arms = {
        "A0_governed_full": ls,
        "A1_ablate_evidence": survey_ablate_evidence(ls),
        "A2_distractor_injected": survey_distractor(ls),
    }

    results = {"arms": {}, "baselines": {}}

    for arm_name, ls_variant in arms.items():
        vids = valid_paper_ids(ls_variant)
        per_seed_comps = []
        per_seed_metrics = []
        for seed in range(1, N_SEEDS + 1):
            settings.llm_seed = seed
            settings.llm_temperature = 0.6
            try:
                raw, instset = call_llm_s09(ds, ls_variant, gateway)
            except Exception as e:
                p(f"[{arm_name} seed{seed}] FAILED: {str(e)[:200]}")
                continue
            comps = instance_components(instset)
            per_seed_comps.append(comps)
            m = metrics_for_components(comps, valid_ids=vids, instset=instset)
            per_seed_metrics.append(m)
            (OUT / f"{arm_name}_seed{seed}_raw.json").write_text(
                json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            p(f"[{arm_name} seed{seed}] inst={m['n_instances']} "
              f"distract={m['distractor_inclusion_rate']} ontopic={m['ontopic_rate']} "
              f"evidence={m.get('evidence_audit_rate')}")

        # aggregate across seeds
        def avg(key):
            vals = [mm[key] for mm in per_seed_metrics if key in mm and mm[key] is not None]
            return round(sum(vals) / len(vals), 3) if vals else None

        results["arms"][arm_name] = {
            "n_runs": len(per_seed_metrics),
            "avg_distractor_inclusion_rate": avg("distractor_inclusion_rate"),
            "avg_ontopic_rate": avg("ontopic_rate"),
            "avg_evidence_audit_rate": avg("evidence_audit_rate"),
            "seed_stability_jaccard": seed_stability(per_seed_comps),
            "per_seed": per_seed_metrics,
        }

    # baselines on A0 pool and A2 pool
    for pool_name, ls_variant in (("A0_pool", ls), ("A2_pool", arms["A2_distractor_injected"])):
        freq = pool_components(ds, ls_variant)
        rnd = baseline_random(freq, seed=42)
        pop = baseline_popularity(freq)
        results["baselines"][f"random@{pool_name}"] = metrics_for_components(rnd)
        results["baselines"][f"popularity@{pool_name}"] = metrics_for_components(pop)
        results["baselines"][f"popularity@{pool_name}"]["top_components"] = [
            c for c, _ in freq.most_common(6)
        ]
        p(f"[baseline {pool_name}] popularity_top={[c for c,_ in freq.most_common(6)]}")

    (OUT / "metrics.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "console.txt").write_text("\n".join(log), encoding="utf-8")
    p("[done] metrics -> m7_full/metrics.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
