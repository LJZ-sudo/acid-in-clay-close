"""Sample Closure Agent — main entry.

Pipeline:
    1. Build deterministic features from a Stage0ResultBundle dict.
    2. Build a trimmed prompt context (small JSON).
    3. Call an OpenAI-compatible LLM (PoloAPI / OpenAI / OpenRouter).
    4. Validate the LLM JSON against `ClosureLLMNarrative`.
    5. Apply hard guards (segment IDs exist, transitions match).
    6. Merge deterministic facts + LLM narrative into `SampleClosureReport`.
    7. On any failure, fall back to a deterministic-only report.

The function is intentionally synchronous, side-effect free, and easy to call
from both `run_closure_offline.py` and the future online finalize hook.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Load project-wide LLM settings via dotenv, matching the convention used by
# stage1_optimization/agents/llm_client.py.  Search order (override=False so
# we never clobber an explicit env var the operator already set):
#     stage0_measurement/.env  (preferred, closure-specific overrides)
#     stage1_optimization/.env (project default, contains LLM_API_KEY)
try:
    from dotenv import load_dotenv  # type: ignore

    _PROJECT_ROOT = Path(__file__).resolve().parents[3]
    for _candidate in (
        _PROJECT_ROOT / "stage0_measurement" / ".env",
        _PROJECT_ROOT / "stage1_optimization" / ".env",
    ):
        if _candidate.exists():
            load_dotenv(dotenv_path=_candidate, override=False)
except ImportError:
    pass

from .closure_features import build_deterministic_features, build_prompt_context
from .closure_schema import (
    CampaignContextLite,
    ClosureAgentInput,
    ClosureLLMNarrative,
    MechanismNote,
    PerformanceCard,
    PhaseTransitionInterp,
    ReportMeta,
    RiskFlag,
    SampleClosureReport,
    UserPrepForm,
)


logger = logging.getLogger(__name__)

_PROMPT_DIR = Path(__file__).parent / "prompts"


# ---------------------------------------------------------------------------
# Prompt utilities
# ---------------------------------------------------------------------------


def _read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def load_prompt() -> Dict[str, Any]:
    """Load the system prompt + meta + user template from disk."""
    meta_path = _PROMPT_DIR / "prompt_meta.json"
    sys_path = _PROMPT_DIR / "closure_system.md"
    user_path = _PROMPT_DIR / "closure_user_template.md"
    meta = json.loads(_read_text(meta_path))
    system = _read_text(sys_path)
    user_tpl = _read_text(user_path)
    return {
        "meta": meta,
        "system": system,
        "user_template": user_tpl,
        "prompt_sha256": _sha256_text(system + "\n---\n" + user_tpl),
    }


# ---------------------------------------------------------------------------
# Default model selection
# ---------------------------------------------------------------------------


def _default_model_settings() -> Dict[str, Any]:
    """Return the default LLM settings for the closure agent.

    Aligned with the project-wide convention from
    `stage1_optimization/agents/llm_client.py`:
        LLM_API_KEY     — shared PoloAPI key (loaded from any stage .env)
        LLM_BASE_URL    — shared base URL
    Closure-specific overrides (rarely needed):
        CLOSURE_LLM_API_KEY, CLOSURE_LLM_BASE_URL, CLOSURE_LLM_MODEL,
        CLOSURE_LLM_TEMPERATURE, CLOSURE_LLM_MAX_TOKENS

    Default *model* is `deepseek-v4-pro` (PoloAPI).  Rationale (see
    paper/closed_loop1_optimization_plan_zh.md §4.4):
        * v4-pro returns clean JSON in `content` and the chain-of-thought in a
          separate `reasoning_content` channel — perfect for guarded summaries.
        * The closure card now includes a `comprehensive_analysis_zh` field
          (≤ 600 chars cross-card synthesis), which benefits from a stronger
          reasoner than v3.x.
        * Hidden reasoning consumes tokens — `max_tokens` defaults to 3500
          to ensure the visible JSON content is not truncated.
    """
    api_key = (
        os.environ.get("CLOSURE_LLM_API_KEY")
        or os.environ.get("LLM_API_KEY")
        or os.environ.get("POLOAPI_KEY")
    )
    base_url = (
        os.environ.get("CLOSURE_LLM_BASE_URL")
        or os.environ.get("LLM_BASE_URL")
        or "https://poloai.top/v1"
    )
    return {
        "api_key": api_key,
        "base_url": base_url,
        "model": os.environ.get("CLOSURE_LLM_MODEL", "deepseek-v4-pro"),
        "temperature": float(os.environ.get("CLOSURE_LLM_TEMPERATURE", "0.2")),
        # v4-pro hidden reasoning routinely uses 3000-7000 tokens before
        # emitting any visible content.  We give it a generous budget so the
        # JSON object always renders.  Empirically: 8000 fails on ~3% of the
        # 40-sample S8 batch (one case used 3793 reasoning tok then truncated);
        # 12000 leaves a comfortable margin for the worst observed run while
        # still costing only ~¥0.03 / call upper bound.
        "max_tokens": int(os.environ.get("CLOSURE_LLM_MAX_TOKENS", "12000")),
        "timeout": float(os.environ.get("CLOSURE_LLM_TIMEOUT", "300")),
    }


# ---------------------------------------------------------------------------
# LLM call (OpenAI-compatible)
# ---------------------------------------------------------------------------


_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)
# Strip JS-style line comments and block comments outside of strings.
_LINE_COMMENT_RE = re.compile(r"^\s*//[^\n]*$", re.MULTILINE)
_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
# Trailing commas before } or ] (common LLM mistake).
_TRAILING_COMMA_RE = re.compile(r",(\s*[\}\]])")


def _strip_to_json(raw: str) -> str:
    """Extract a JSON object from a possibly-wrapped LLM response.

    Handles:
        - <think>...</think> reasoning blocks (R1-style)
        - ```json ... ``` markdown fences
        - Surrounding prose (find first '{' to last '}')
        - JS-style // line comments and /* block comments */ (v4-pro
          occasionally adds inline annotations)
        - Trailing commas before closing brace/bracket
    """
    if not raw:
        return ""
    cleaned = _THINK_RE.sub("", raw).strip()
    m = _JSON_BLOCK_RE.search(cleaned)
    if m:
        candidate = m.group(1).strip()
    elif cleaned.startswith("{") and cleaned.endswith("}"):
        candidate = cleaned
    else:
        lo = cleaned.find("{")
        hi = cleaned.rfind("}")
        candidate = cleaned[lo : hi + 1] if 0 <= lo < hi else cleaned

    # Defensive cleanup for v4-pro quirks observed on real data.
    candidate = _LINE_COMMENT_RE.sub("", candidate)
    candidate = _BLOCK_COMMENT_RE.sub("", candidate)
    candidate = _TRAILING_COMMA_RE.sub(r"\1", candidate)
    return candidate.strip()


def _call_llm(
    *,
    system_prompt: str,
    user_message: str,
    model_settings: Dict[str, Any],
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Returns (parsed_json, error). On any failure parsed_json is None."""
    api_key = model_settings.get("api_key")
    if not api_key:
        return None, "no_api_key"
    try:
        from openai import OpenAI
    except ImportError:
        return None, "openai_sdk_missing"

    try:
        client = OpenAI(
            api_key=api_key,
            base_url=model_settings["base_url"],
            timeout=model_settings.get("timeout", 240),
        )
        resp = client.chat.completions.create(
            model=model_settings["model"],
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=model_settings["temperature"],
            max_tokens=model_settings["max_tokens"],
        )
        raw = resp.choices[0].message.content or ""
        # v4-pro / R1 may return CoT separately; we don't need it but warn if
        # `content` is empty while reasoning was produced — that signals the
        # operator forgot to bump max_tokens.
        if not raw:
            try:
                cot_len = len(getattr(resp.choices[0].message, "reasoning_content", "") or "")
            except Exception:  # noqa: BLE001
                cot_len = 0
            return None, (
                f"empty_content_with_reasoning_len={cot_len}; "
                f"likely max_tokens too low for {model_settings['model']}"
            )
    except Exception as e:  # noqa: BLE001
        return None, f"llm_call_error: {e!s}"

    json_str = _strip_to_json(raw)
    try:
        parsed = json.loads(json_str)
    except json.JSONDecodeError as e:
        return None, f"json_decode_error: {e!s}"
    return parsed, None


# ---------------------------------------------------------------------------
# Hard guard rails on the LLM narrative
# ---------------------------------------------------------------------------


def _validate_narrative(
    narrative: ClosureLLMNarrative,
    *,
    performance_card: PerformanceCard,
    phase_transitions: List[PhaseTransitionInterp],
    risks_warnings: List[RiskFlag],
) -> Optional[str]:
    """Return None if narrative is consistent with deterministic facts, else a reason."""
    seg_ids = {s.idx for s in performance_card.segments}
    bad_ids = [i for i in narrative.mechanism_supporting_segment_ids if i not in seg_ids]
    if bad_ids:
        return f"mechanism_supporting_segment_ids contains unknown idx: {bad_ids}"

    if len(narrative.phase_transition_notes) != len(phase_transitions):
        return (
            f"phase_transition_notes length mismatch: "
            f"narrative={len(narrative.phase_transition_notes)} vs facts={len(phase_transitions)}"
        )
    for i, (n_pt, det_pt) in enumerate(zip(narrative.phase_transition_notes, phase_transitions)):
        try:
            t_n = float(n_pt.get("T_C"))
        except (TypeError, ValueError):
            return f"phase_transition_notes[{i}].T_C not parseable"
        if abs(t_n - det_pt.T_C) > 0.1:
            return f"phase_transition_notes[{i}].T_C drifted: {t_n} vs {det_pt.T_C}"

    risk_codes = {r.code for r in risks_warnings}
    bad_risks = [c for c in narrative.risk_human_messages if c not in risk_codes]
    if bad_risks:
        return f"risk_human_messages references unknown codes: {bad_risks}"

    return None


# ---------------------------------------------------------------------------
# Merge narrative + facts
# ---------------------------------------------------------------------------


_PT_TYPE_CODE_VALID = {
    "eutectic",
    "glass_transition",
    "ice_nucleation",
    "transport_mechanism_switch",
    "uncertain",
}
_PT_TYPE_ZH_VALID = {"共晶", "玻璃化", "冰核化", "输运机制切换", "不确定"}


def _merge_into_report(
    *,
    meta: ReportMeta,
    deterministic: Dict[str, Any],
    narrative: Optional[ClosureLLMNarrative],
    do_not_overclaim: List[str],
) -> SampleClosureReport:
    perf: PerformanceCard = deterministic["performance_card"]
    qual = deterministic["quality_card"]
    transitions: List[PhaseTransitionInterp] = list(deterministic["phase_transitions"])
    risks: List[RiskFlag] = list(deterministic["risks_warnings"])
    comparison = deterministic["campaign_comparison"]

    comprehensive_analysis = ""

    if narrative is not None:
        # Apply LLM short text into deterministic structures.
        perf = perf.model_copy(update={"highlight_zh": narrative.performance_highlight_zh[:80]})
        qual = qual.model_copy(update={"verdict_zh": narrative.quality_verdict_zh[:120]})
        for i, pt in enumerate(transitions):
            note = narrative.phase_transition_notes[i] if i < len(narrative.phase_transition_notes) else {}
            type_code = note.get("type_code") or "uncertain"
            if type_code not in _PT_TYPE_CODE_VALID:
                type_code = "uncertain"
            type_zh = note.get("type_zh") or "不确定"
            if type_zh not in _PT_TYPE_ZH_VALID:
                type_zh = "不确定"
            transitions[i] = pt.model_copy(
                update={
                    "type_zh": type_zh,
                    "type_code": type_code,  # type: ignore[arg-type]
                    "note_zh": (note.get("note_zh") or "")[:60],
                }
            )
        for r in risks:
            msg = narrative.risk_human_messages.get(r.code)
            if msg:
                r.human_zh = msg[:60]
        comparison = comparison.model_copy(
            update={"one_liner_zh": (narrative.campaign_one_liner_zh or comparison.one_liner_zh)[:200]}
        )
        mechanism = MechanismNote(
            primary_zh=narrative.mechanism_primary_zh,
            supporting_segment_ids=narrative.mechanism_supporting_segment_ids,
            caveat_zh=narrative.mechanism_caveat_zh,
        )
        comprehensive_analysis = (narrative.comprehensive_analysis_zh or "")[:600]
    else:
        mechanism = MechanismNote(
            primary_zh="（未启用 LLM 或 LLM 不可用，按确定性事实呈现）",
            supporting_segment_ids=[],
            caveat_zh="此报告未经 LLM 复述，机理段留空",
        )

    return SampleClosureReport(
        meta=meta,
        identity=deterministic["identity"],
        performance_card=perf,
        quality_card=qual,
        phase_transitions=transitions,
        mechanism_note=mechanism,
        risks_warnings=risks,
        campaign_comparison=comparison,
        comprehensive_analysis_zh=comprehensive_analysis,
        do_not_overclaim=do_not_overclaim,
    )


# ---------------------------------------------------------------------------
# Public entry
# ---------------------------------------------------------------------------


def generate_sample_closure_report(
    *,
    bundle: Dict[str, Any],
    user_prep_form: Optional[UserPrepForm] = None,
    campaign_context: Optional[CampaignContextLite] = None,
    run_id: Optional[str] = None,
    use_llm: bool = True,
    model_settings: Optional[Dict[str, Any]] = None,
    user_prep_text: Optional[str] = None,
) -> SampleClosureReport:
    """Build a SampleClosureReport for one finished sample.

    Args:
        bundle: Stage0ResultBundle dict (already loaded JSON).
        user_prep_form: Optional structured prep form supplied by the user.
        campaign_context: Optional thin campaign context (best σ_RT only).
        run_id: Optional run identifier propagated to meta.
        use_llm: When False, returns a deterministic-only report (skips LLM).
        model_settings: Optional override for the LLM call.
        user_prep_text: Free-form text to be hashed into identity (kept short).
    """
    user_prep = user_prep_form or UserPrepForm()
    ctx = campaign_context or CampaignContextLite()
    prep_sha = _sha256_text(user_prep_text)[:32] if user_prep_text else None

    # 1. Deterministic features
    deterministic = build_deterministic_features(
        bundle, user_prep, ctx, prep_text_sha256=prep_sha
    )

    sample_id = str(bundle.get("sample_id") or "UNKNOWN")
    meta_dt = datetime.now(timezone.utc).isoformat()

    # 2. Prompt context + input hash
    ctx_payload = build_prompt_context(
        identity=deterministic["identity"],
        performance_card=deterministic["performance_card"],
        quality_card=deterministic["quality_card"],
        phase_transitions=deterministic["phase_transitions"],
        risks_warnings=deterministic["risks_warnings"],
        campaign_comparison=deterministic["campaign_comparison"],
    )
    input_sha = _sha256_text(json.dumps(ctx_payload, sort_keys=True, ensure_ascii=False))[:32]

    # 3. Decide on LLM call
    fallback_reason: Optional[str] = None
    narrative: Optional[ClosureLLMNarrative] = None
    prompt_pack = load_prompt()
    settings = model_settings or _default_model_settings()

    if not use_llm:
        fallback_reason = "use_llm=False"
    elif not settings.get("api_key"):
        fallback_reason = "no_api_key"
    else:
        user_msg = prompt_pack["user_template"].format(
            prompt_context_json=json.dumps(ctx_payload, ensure_ascii=False, indent=2)
        )
        parsed, err = _call_llm(
            system_prompt=prompt_pack["system"],
            user_message=user_msg,
            model_settings=settings,
        )
        if parsed is None:
            fallback_reason = err or "unknown_llm_error"
            logger.warning("ClosureAgent LLM call failed: %s", fallback_reason)
        else:
            try:
                narrative = ClosureLLMNarrative.model_validate(parsed)
            except Exception as e:  # noqa: BLE001
                fallback_reason = f"narrative_schema_error: {e!s}"
                narrative = None
            if narrative is not None:
                guard_err = _validate_narrative(
                    narrative,
                    performance_card=deterministic["performance_card"],
                    phase_transitions=deterministic["phase_transitions"],
                    risks_warnings=deterministic["risks_warnings"],
                )
                if guard_err:
                    fallback_reason = f"guardrail_failed: {guard_err}"
                    narrative = None

    # 4. Build meta
    meta = ReportMeta(
        sample_id=sample_id,
        run_id=run_id,
        generated_at=meta_dt,
        llm_used=narrative is not None,
        llm_provider="poloai" if narrative is not None else None,
        llm_model=settings.get("model") if narrative is not None else None,
        prompt_version=prompt_pack["meta"].get("prompt_version"),
        prompt_sha256=prompt_pack["prompt_sha256"][:32],
        seed=None,
        input_summary_sha256=input_sha,
        fallback_reason=fallback_reason,
    )

    # 5. Merge
    return _merge_into_report(
        meta=meta,
        deterministic=deterministic,
        narrative=narrative,
        do_not_overclaim=prompt_pack["meta"].get("do_not_overclaim", []),
    )


def write_report(report: SampleClosureReport, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    return output_path


# Convenience: input-driven entry, used by CLI / online finalize hook
def run_closure_for_bundle_path(
    bundle_path: Path,
    *,
    output_path: Optional[Path] = None,
    user_prep_path: Optional[Path] = None,
    campaign_context: Optional[CampaignContextLite] = None,
    use_llm: bool = True,
    model_settings: Optional[Dict[str, Any]] = None,
    run_id: Optional[str] = None,
) -> Tuple[SampleClosureReport, Path]:
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    user_prep_form: Optional[UserPrepForm] = None
    user_prep_text: Optional[str] = None
    if user_prep_path and user_prep_path.exists():
        try:
            payload = json.loads(user_prep_path.read_text(encoding="utf-8"))
            user_prep_form = UserPrepForm.model_validate(payload)
            user_prep_text = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        except Exception as e:  # noqa: BLE001
            logger.warning("Failed to load user_prep_form from %s: %s", user_prep_path, e)

    report = generate_sample_closure_report(
        bundle=bundle,
        user_prep_form=user_prep_form,
        campaign_context=campaign_context,
        run_id=run_id,
        use_llm=use_llm,
        model_settings=model_settings,
        user_prep_text=user_prep_text,
    )
    out = output_path or (bundle_path.parent / "closure_report.json")
    write_report(report, out)
    return report, out
