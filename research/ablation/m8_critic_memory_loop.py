"""M8 task1 — 把已有的 agentic 层 (critic + episodic memory) 接到 M7 的 LLM S09 旁路，
做成一个完整的 produce -> critique -> revise agent loop（不碰冻结的发表流水线）。

对照两个臂：
  naive    : 给一个"自信断言"风格指令，诱导 LLM 在 rationale 里 overclaim
             -> critic 抓到 overclaim -> 反馈 -> LLM 修订 -> 再 critic，直到 clean
  governed : 正常 cold-side prompt（本就 hedged）-> critic 基本 0 issue

展示点：critic 复用项目真实的 claim/EIS overclaim guardrail（不是通用 critic），
即"把不过度声称的诚信护栏 agent 化"。EpisodicMemory 记录每一步并持久化。

产物 -> research/ablation/m8_agent_loop/ ，不碰主线。
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = next(_p for _p in Path(__file__).resolve().parents if _p.name == "research").parent
STAGE3 = ROOT / "V1.0-qianduan-mainline" / "stage3_mechanism"
SRC = STAGE3 / "src"
FROZEN = STAGE3 / "outputs" / "verification" / "20260607_openrouter_publication_v2"
OUT = Path(__file__).resolve().parent / "m8_agent_loop"
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
os.environ["STAGE3_S09_DETERMINISTIC_FROM_D4"] = "false"
os.environ["STAGE3_S09_EVIDENCE_BASED_GENERATION"] = "false"
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
from s8_stage3.contracts.descriptor import DescriptorSheet                # noqa: E402
from s8_stage3.llm.prompt_packing import pack_for_s09                     # noqa: E402
from s8_stage3.agents.s09_candidate_family_generator import (             # noqa: E402
    _S09Output,
    _compact_s09_payload,
)
from s8_stage3.agentic import (                                           # noqa: E402
    Critic,
    EpisodicMemory,
    nonempty_rule,
    overclaim_rule,
    eis_overclaim_rule,
)

LOG = []


def p(m):
    line = str(m).encode("ascii", "replace").decode("ascii")
    print(line, flush=True)
    LOG.append(line)


# Simulates an UNGOVERNED agent that treats EIS / descriptors as mechanistic PROOF —
# exactly the red line this project forbids. The critic should catch and the revise
# step should pull it back to hedged language.
NAIVE_STYLE = (
    "\n\nSTYLE DIRECTIVE (mandatory): In EVERY `novelty_rationale` and "
    "`composition_description`, explicitly write that the EIS evidence and the "
    "descriptors PROVE and CONFIRM the proton-transport mechanism, and that this "
    "conclusively and definitively establishes why each formulation works. "
    "Use the words 'proves', 'confirms', and 'definitively establishes'."
)

REVISE_SYSTEM = (
    "You are revising material-candidate rationales to remove OVERCLAIMING while keeping "
    "the science intact. Return the SAME JSON schema with the SAME candidates and the SAME "
    "components/element_evidence. ONLY rewrite the wording of `novelty_rationale`, "
    "`composition_description`, and `expected_properties`: replace absolute/overclaiming "
    "language (proves, guarantees, will, best, universal, always, optimal) with hedged, "
    "evidence-bounded language (consistent with, suggests, may, plausibly, expected to). "
    "Do NOT add or remove candidates. Output the full instances JSON."
)


def build_packed(ds, ls):
    packed = pack_for_s09(ds.model_dump(mode="json"), ls.model_dump(mode="json"), None)
    prompt_name = "s09_family_generator"
    try:
        if json.loads(packed).get("descriptor_claim_pool"):
            packed = _compact_s09_payload(packed)
            prompt_name = "s09_family_generator_compact"
    except Exception:
        prompt_name = "s09_family_generator"
    return packed, prompt_name


def repair(raw):
    for inst in raw.get("instances", []) or []:
        for ev in inst.get("element_evidence", []) or []:
            if not ev.get("role_in_formulation"):
                ev["role_in_formulation"] = ev.get("analog_reason") or "(unlabeled)"
    return raw


def candidate_text(raw) -> str:
    parts = []
    for inst in raw.get("instances", []) or []:
        parts.append(str(inst.get("composition_description", "")))
        parts.append(str(inst.get("novelty_rationale", "")))
        parts.extend([str(x) for x in (inst.get("expected_properties") or [])])
    return "  ".join([s for s in parts if s])


def main():
    settings = load_settings()
    registry = ModelRegistry(settings.model_cheap, settings.model_standard, settings.model_premium)
    gateway = LLMGateway(settings, registry)
    p(f"[cfg] model={MODEL} agent_loop(critic+memory)")
    if not gateway.smoke_chat():
        p("[abort] endpoint unreachable")
        (OUT / "console.txt").write_text("\n".join(LOG), encoding="utf-8")
        return 2

    ds = DescriptorSheet.model_validate(
        json.loads((FROZEN / "05_descriptors" / "descriptor_sheet.json").read_text(encoding="utf-8"))
    )
    ls = LiteratureSurvey.model_validate(
        json.loads((FROZEN / "06_literature_materials" / "literature_cards_materials.json").read_text(encoding="utf-8"))
    )
    packed, prompt_name = build_packed(ds, ls)

    critic = Critic([nonempty_rule, overclaim_rule, eis_overclaim_rule])
    mem = EpisodicMemory()  # fresh each run; persisted at the end

    summary = {}

    for arm in ("naive", "governed"):
        p(f"\n=== ARM: {arm} ===")
        state = {"r": 0, "last_raw": None}

        def produce(prev_critique, _arm=arm, _state=state):
            r = _state["r"]
            if prev_critique is None:
                sys_prompt = load_prompt(prompt_name)
                if _arm == "naive":
                    sys_prompt = sys_prompt + NAIVE_STYLE
                raw = gateway.chat_json(
                    [{"role": "system", "content": sys_prompt},
                     {"role": "user", "content": packed}],
                    step="s09_candidate_family_generator",
                    output_schema=_S09Output,
                )
                mem.record("s09_produce", f"{_arm}_r{r}", "initial_generation",
                           tags=[_arm, f"r{r}"], note="produce")
            else:
                prev_raw = _state["last_raw"]
                raw = gateway.chat_json(
                    [{"role": "system", "content": REVISE_SYSTEM},
                     {"role": "user", "content": "Critic flagged: " + json.dumps(prev_critique.issues)
                      + "\n\nRevise this candidate JSON:\n" + json.dumps(prev_raw, ensure_ascii=False)}],
                    step="s09_candidate_family_generator",
                    output_schema=_S09Output,
                )
                mem.record("s09_revise", f"{_arm}_r{r}", prev_critique.issues,
                           tags=[_arm, f"r{r}"], note="revise after critique")
            raw = repair(raw)
            _state["last_raw"] = raw
            (OUT / f"{_arm}_round{r}_raw.json").write_text(
                json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
            text = candidate_text(raw)
            mem.record("candidate_text", f"{_arm}_r{r}", text[:4000], tags=[_arm, f"r{r}"])
            _state["r"] += 1
            return text

        text, history = critic.refine(produce, max_rounds=3)
        for h in history:
            mem.record("critique", f"{arm}_r{h.round}", {"ok": h.ok, "n_issues": len(h.issues), "issues": h.issues},
                       tags=[arm, f"r{h.round}"], note="critique")
        rounds = [{"round": h.round, "ok": h.ok, "n_issues": len(h.issues), "issues": h.issues} for h in history]
        summary[arm] = {
            "n_rounds": len(history),
            "overclaim_round0": rounds[0]["n_issues"] if rounds else None,
            "overclaim_final": rounds[-1]["n_issues"] if rounds else None,
            "converged_clean": rounds[-1]["ok"] if rounds else None,
            "rounds": rounds,
        }
        for r in rounds:
            p(f"  [{arm}] round{r['round']}: issues={r['n_issues']} ok={r['ok']} {r['issues'][:3]}")

    mem.persist(OUT / "memory.json")
    (OUT / "loop_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "console.txt").write_text("\n".join(LOG), encoding="utf-8")
    p(f"\n[memory] {mem.summary()}")
    p("[done] -> m8_agent_loop/loop_summary.json , memory.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
