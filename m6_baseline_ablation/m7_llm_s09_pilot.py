"""M7 pilot: 让真 LLM 第一次跑 S09 候选生成(关掉冻结的 deterministic_from_d4)。

目的：把"创新点1"的消融从"确定性管线 vs 基线"升级为"真 LLM agent vs 基线"。
本脚本只读冻结输入(descriptor_sheet + S08 文献证据池)，把 S09 切到 LLM 分支，
看真 LLM 能否仅凭文献证据池**独立**重组出质子导体候选家族/实例。

不碰主线：输出全部落在 m6_baseline_ablation/m7_llm_pilot/ 下。
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]          # acid-in-clay-close
STAGE3 = ROOT / "V1.0-qianduan-mainline" / "stage3_mechanism"
SRC = STAGE3 / "src"
FROZEN = STAGE3 / "outputs" / "verification" / "20260607_openrouter_publication_v2"
OUT = Path(__file__).resolve().parent / "m7_llm_pilot"
OUT.mkdir(parents=True, exist_ok=True)

MODEL = os.environ.get("M7_MODEL", "openai/gpt-5.4")

# ---- key ----
key = (ROOT / "key.txt").read_text(encoding="utf-8").strip().splitlines()[0].strip()

# ---- env MUST be set before importing settings (settings reads env at import) ----
os.environ["STAGE3_LLM_MODE"] = "live"
os.environ["STAGE3_API_KEY"] = key
os.environ["STAGE3_API_BASE_URL"] = "https://openrouter.ai/api/v1"
os.environ["STAGE3_MODEL_CHEAP"] = MODEL
os.environ["STAGE3_MODEL_STANDARD"] = MODEL
os.environ["STAGE3_MODEL_PREMIUM"] = MODEL
os.environ["STAGE3_MODEL_TIER"] = ""                       # empty -> s09 routes to PREMIUM via STEP_TIER_MAP
os.environ["STAGE3_S09_DETERMINISTIC_FROM_D4"] = "false"   # <-- turn OFF frozen hardcode
os.environ["STAGE3_S09_EVIDENCE_BASED_GENERATION"] = "false"  # <-- also OFF (that branch is deterministic too)
os.environ["STAGE3_USE_STRUCTURED_OUTPUTS"] = "false"      # OpenRouter proxy: use json_object, not strict json_schema
os.environ["STAGE3_ENABLE_CACHE"] = "false"                # genuine call, no stale reuse
os.environ["STAGE3_CACHE_DIR"] = str(OUT / "cache")
os.environ["STAGE3_LLM_TEMPERATURE"] = "0.2"               # small temp so it can actually generate
os.environ["STAGE3_MAX_LLM_CALLS_PER_RUN"] = "20"

sys.path.insert(0, str(SRC))

from s8_stage3.config.settings import load_settings          # noqa: E402
from s8_stage3.config.model_registry import ModelRegistry     # noqa: E402
from s8_stage3.config.llm_gateway import LLMGateway            # noqa: E402
from s8_stage3.contracts.literature import LiteratureSurvey    # noqa: E402
from s8_stage3.contracts.descriptor import DescriptorSheet     # noqa: E402
from s8_stage3.agents.s09_candidate_family_generator import (  # noqa: E402
    _S09Output,
    _compact_s09_payload,
)
from s8_stage3.llm.prompt_packing import pack_for_s09  # noqa: E402
from s8_stage3.config.prompt_registry import load_prompt  # noqa: E402
from s8_stage3.contracts.material import (  # noqa: E402
    MaterialFamilySet,
    MaterialInstanceSet,
)


def asciisafe(s: object) -> str:
    return str(s).encode("ascii", "replace").decode("ascii")


LOG = []


def log(msg: str) -> None:
    line = asciisafe(msg)
    print(line, flush=True)
    LOG.append(line)


def main() -> int:
    settings = load_settings()
    log(f"[cfg] llm_mode={settings.llm_mode} base={settings.api_base_url} model={MODEL}")
    log(f"[cfg] s09_deterministic_from_d4={settings.s09_deterministic_from_d4} "
        f"s09_evidence_based={settings.s09_evidence_based_generation} "
        f"structured={settings.use_structured_outputs} cache={settings.enable_cache}")
    log(f"[cfg] key={key[:10]}... (len={len(key)})")

    registry = ModelRegistry(settings.model_cheap, settings.model_standard, settings.model_premium)
    gateway = LLMGateway(settings, registry)

    # --- step name route check (must be PREMIUM, i.e. the configured model) ---
    routed = gateway.resolve_model_for_step("s09_candidate_family_generator")
    log(f"[route] s09 -> {routed}")

    # --- smoke first (cheap, 1 call) ---
    log("[smoke] pinging endpoint ...")
    ok = gateway.smoke_chat()
    log(f"[smoke] reachable={ok}")
    if not ok:
        log("[abort] endpoint not reachable / model invalid; not spending on s09.")
        (OUT / "pilot_console.txt").write_text("\n".join(LOG), encoding="utf-8")
        return 2

    # --- load frozen inputs ---
    ds = DescriptorSheet.model_validate(
        json.loads((FROZEN / "05_descriptors" / "descriptor_sheet.json").read_text(encoding="utf-8"))
    )
    ls = LiteratureSurvey.model_validate(
        json.loads((FROZEN / "06_literature_materials" / "literature_cards_materials.json").read_text(encoding="utf-8"))
    )
    n_claims = sum(len(c.component_descriptor_claims) for c in ls.cards)
    log(f"[input] descriptors={len(ds.descriptors)} cards={len(ls.cards)} d4_claims={n_claims}")

    # --- reproduce run_s09's genuine LLM branch (both deterministic flags are OFF) ---
    log("[s09] packing frozen evidence + calling real LLM ...")
    packed = pack_for_s09(ds.model_dump(mode="json"), ls.model_dump(mode="json"), None)
    prompt_name = "s09_family_generator"
    try:
        if json.loads(packed).get("descriptor_claim_pool"):
            packed = _compact_s09_payload(packed)
            prompt_name = "s09_family_generator_compact"
    except Exception:
        prompt_name = "s09_family_generator"
    log(f"[s09] prompt={prompt_name} payload_chars={len(packed)}")

    raw = gateway.chat_json(
        [
            {"role": "system", "content": load_prompt(prompt_name)},
            {"role": "user", "content": packed},
        ],
        step="s09_candidate_family_generator",
        output_schema=_S09Output,
    )
    # Keep the UNMODIFIED LLM output for the record (proves the LLM really generated these).
    (OUT / "llm_s09_raw.json").write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")

    # Minimal schema repair: the only required key the model omitted is
    # element_evidence[*].role_in_formulation (we did NOT force strict json_schema,
    # OpenRouter proxy support varies). Backfill from analog_reason; raw kept above.
    n_fixed = 0
    for inst in raw.get("instances", []) or []:
        for ev in inst.get("element_evidence", []) or []:
            if not ev.get("role_in_formulation"):
                ev["role_in_formulation"] = ev.get("analog_reason") or "(role not explicitly labeled by LLM)"
                n_fixed += 1
    log(f"[s09] backfilled role_in_formulation on {n_fixed} element_evidence entries")

    parsed = _S09Output.model_validate(raw)
    families = MaterialFamilySet(families=parsed.families)
    instances = MaterialInstanceSet(instances=parsed.instances)
    log(f"[s09] families={len(families.families)} instances={len(instances.instances)}")

    # dump full results to disk (utf-8) and print ascii summary
    (OUT / "llm_families.json").write_text(families.model_dump_json(indent=2), encoding="utf-8")
    (OUT / "llm_instances.json").write_text(instances.model_dump_json(indent=2), encoding="utf-8")

    for fam in families.families:
        d = fam.model_dump()
        log(f"  FAMILY {asciisafe(d.get('family_id'))}: {asciisafe(d.get('name') or d.get('label') or '')}")
    for inst in instances.instances:
        d = inst.model_dump()
        comps = d.get("components") or d.get("composition") or d.get("formula") or ""
        log(f"  INST {asciisafe(d.get('instance_id') or d.get('id'))}: "
            f"{asciisafe(d.get('name') or d.get('label') or '')} | comps={asciisafe(comps)[:160]}")

    cost = gateway.get_cost_summary()
    log(f"[cost] calls={cost['total_calls']} ok={cost['successes']} fail={cost['failures']} "
        f"tokens={cost['total_tokens']}")
    (OUT / "cost_summary.json").write_text(json.dumps(cost, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "pilot_console.txt").write_text("\n".join(LOG), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
