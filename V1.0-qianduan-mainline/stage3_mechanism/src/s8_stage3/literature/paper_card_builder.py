"""Paper Card Builder — 从解析后的论文全文构建结构化 PaperCard。

使用 LLM 做定向信息提取，只提取对 Stage3 有价值的字段。
不是全文摘要器。
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from s8_stage3.contracts.paper_card import PaperCard, TraceSpan
from s8_stage3.literature.paper_reader import ParsedPaper, read_paper
from s8_stage3.config.prompt_registry import load_prompt

logger = logging.getLogger(__name__)

_CARD_SYSTEM_PROMPT = """You are a scientific paper information extractor for a proton conduction research project.
Extract ONLY structured information relevant to proton transport mechanisms, EIS analysis, Arrhenius/VTF behavior, and material properties.

Output a JSON object with these exact keys:
- system_identity: {base_material, dopant, form_factor, other}
- measurement_scope: {temp_range, freq_range, humidity, other_conditions}
- mechanism_relevant_findings: [list of single-sentence findings about proton transport mechanism]
- numerical_findings: [{metric, value, unit, conditions}]
- eis_shape_findings: [findings about Nyquist/Bode/impedance shape]
- arrhenius_vtf_findings: [findings about activation energy, Arrhenius, VTF fits]
- limitations: [study limitations or caveats]
- relevance_judgement: {score: 0.0-1.0, reason: "one sentence"}
- supports_axes: dict mapping a mechanism axis key to the axis value this paper's conclusions SUPPORT.
- conflicts_axes: dict mapping a mechanism axis key to the axis value this paper's conclusions REFUTE.

Both use the SAME axis key+value vocabulary as the S04 hypothesis generator. You MUST pick values from
the canonical sets below (do NOT invent new axis values; if none fit, omit that axis instead of guessing):

  transport (how protons move):
    - Grotthuss_hopping
    - vehicular_diffusion
    - hybrid_grotthuss_vehicular
    - ionic_liquid_like

  phase_structure (connectivity of the conductive phase):
    - single_continuous_phase
    - single_percolation_threshold
    - multi_threshold_confined_domains
    - core_shell_interfacial

  temperature_dependence (functional form of sigma(T)):
    - pure_Arrhenius
    - VTF
    - piecewise_Arrhenius
    - Arrhenius_with_MeyerNeldel_coupling

  transition_topology (how many structural/dynamical transitions):
    - no_transition
    - single_transition
    - multi_transition

Examples (values are strictly from the above vocabulary):
  supports_axes: {"transport": "Grotthuss_hopping", "temperature_dependence": "piecewise_Arrhenius"}
  conflicts_axes: {"transport": "vehicular_diffusion"}

Rules:
- Each finding should be ONE sentence, not a paragraph.
- Include page/section references where possible.
- Be factual, not interpretive.
- If a field has no relevant info, use empty list/dict.
- supports_axes / conflicts_axes can be {} if the paper does not clearly take a position on any axis.
- NEVER write a free-text axis value like "Arrhenius" or "low_activation_energy". Pick from the canonical vocabulary or OMIT the axis."""


_FALLBACK_KEYWORDS = [
    r"conductivity", r"S\s*/\s*cm", r"activation\s+energy", r"eV",
    r"Nyquist", r"semicircle", r"tail", r"Arrhenius", r"VTF",
    r"Grotthuss", r"vehicular", r"proton\s+hopping", r"interfacial\s+water",
]
_FALLBACK_RE = re.compile("|".join(f"({kw})" for kw in _FALLBACK_KEYWORDS), re.IGNORECASE)

MIN_QUALITY_FINDINGS = 2

# Canonical mechanism axis vocabulary — MUST stay aligned with
# prompts/s04_hypothesis_generator.md. Any LLM-produced axis value outside these
# sets will be dropped by _sanitize_axes() with a warning (see SDL §14.3 note).
_CANONICAL_AXIS_VOCAB: dict[str, set[str]] = {
    "transport": {
        "Grotthuss_hopping",
        "vehicular_diffusion",
        "hybrid_grotthuss_vehicular",
        "ionic_liquid_like",
    },
    "phase_structure": {
        "single_continuous_phase",
        "single_percolation_threshold",
        "multi_threshold_confined_domains",
        "core_shell_interfacial",
    },
    "temperature_dependence": {
        "pure_Arrhenius",
        "VTF",
        "piecewise_Arrhenius",
        "Arrhenius_with_MeyerNeldel_coupling",
    },
    "transition_topology": {
        "no_transition",
        "single_transition",
        "multi_transition",
    },
}


def _sanitize_axes(raw: dict, paper_id: str, field_name: str) -> dict:
    """只保留 canonical vocabulary 中的 axis 值；其余丢弃并记 warning。"""
    if not isinstance(raw, dict):
        return {}
    clean: dict[str, str] = {}
    for k, v in raw.items():
        if k not in _CANONICAL_AXIS_VOCAB:
            logger.warning(
                "[CardBuilder] %s: unknown %s key %r dropped",
                paper_id, field_name, k,
            )
            continue
        if not isinstance(v, str):
            continue
        if v in _CANONICAL_AXIS_VOCAB[k]:
            clean[k] = v
        else:
            logger.warning(
                "[CardBuilder] %s: %s[%s]=%r not in canonical vocab, dropped",
                paper_id, field_name, k, v,
            )
    return clean


def _count_findings(card: PaperCard) -> int:
    return (
        len(card.mechanism_relevant_findings)
        + len(card.numerical_findings)
        + len(card.eis_shape_findings)
        + len(card.arrhenius_vtf_findings)
    )


def check_card_quality(card: PaperCard) -> str:
    """返回质量状态: 'carded' | 'low_quality'。"""
    if _count_findings(card) >= MIN_QUALITY_FINDINGS:
        return "carded"
    return "low_quality"


def fallback_keyword_extract(parsed: ParsedPaper) -> list[str]:
    """轻量规则抽取：从全文中找关键词邻域句子。"""
    text = parsed.full_text or parsed.summary_text(max_chars=20000)
    sentences = re.split(r'(?<=[.!?])\s+', text)
    findings = []
    seen = set()
    for sent in sentences:
        if _FALLBACK_RE.search(sent) and sent.strip() not in seen:
            cleaned = sent.strip()[:300]
            findings.append(cleaned)
            seen.add(cleaned)
            if len(findings) >= 10:
                break
    return findings


def build_paper_card(
    parsed: ParsedPaper,
    paper_id: str,
    stage_target: str,
    gateway,
) -> tuple[PaperCard, str]:
    """从 ParsedPaper 构建 PaperCard。

    Returns: (card, status) 其中 status 为
        'carded' | 'carded_fallback' | 'card_failed_quality_gate'
    """
    summary = parsed.summary_text(max_chars=6000)
    user_prompt = (
        f"Paper text (truncated):\n\n{summary}\n\n"
        f"Stage target: {stage_target}\n"
        "Extract structured information as specified."
    )

    result = gateway.chat_json(
        [
            {"role": "system", "content": _CARD_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        step=f"paper_card_{paper_id[:20]}",
    )

    trace_spans = []
    for sec in parsed.sections[:5]:
        trace_spans.append(TraceSpan(
            section=sec.get("heading", ""),
            text_snippet=sec.get("text", "")[:200],
        ))

    card = PaperCard(
        paper_id=paper_id,
        stage_target=stage_target,
        bibliography={
            "title": parsed.title,
            "authors": parsed.authors,
            "year": parsed.year,
        },
        system_identity=result.get("system_identity", {}),
        measurement_scope=result.get("measurement_scope", {}),
        mechanism_relevant_findings=result.get("mechanism_relevant_findings", []),
        numerical_findings=result.get("numerical_findings", []),
        eis_shape_findings=result.get("eis_shape_findings", []),
        arrhenius_vtf_findings=result.get("arrhenius_vtf_findings", []),
        limitations=result.get("limitations", []),
        relevance_judgement=result.get("relevance_judgement", {}),
        supports_axes=_sanitize_axes(result.get("supports_axes") or {}, paper_id, "supports_axes"),
        conflicts_axes=_sanitize_axes(result.get("conflicts_axes") or {}, paper_id, "conflicts_axes"),
        trace_spans=trace_spans,
    )

    quality = check_card_quality(card)
    if quality == "carded":
        return card, "carded"

    fb_findings = fallback_keyword_extract(parsed)
    if fb_findings:
        card.mechanism_relevant_findings.extend(fb_findings)
        logger.info(
            f"[CardBuilder] {paper_id}: LLM findings low ({_count_findings(card) - len(fb_findings)}), "
            f"fallback added {len(fb_findings)} keyword sentences"
        )
        return card, "carded_fallback"

    logger.warning(f"[CardBuilder] {paper_id}: failed quality gate (findings < {MIN_QUALITY_FINDINGS})")
    return card, "card_failed_quality_gate"


def build_paper_card_from_file(
    file_path: Path,
    paper_id: str,
    stage_target: str,
    gateway,
) -> tuple[PaperCard, str]:
    """从文件路径构建 PaperCard。返回 (card, status)。"""
    parsed = read_paper(file_path)
    return build_paper_card(parsed, paper_id, stage_target, gateway)


def build_cards_for_registry(
    workspace_base: Path,
    registry_entries: list,
    stage_target: str,
    gateway,
    output_dir: Path,
    registry=None,
) -> list[PaperCard]:
    """批量为 registry 中 status=parsed/new 的条目生成 PaperCard。

    写 quality log 并更新 registry 状态。
    """
    cards = []
    quality_log: list[dict] = []
    output_dir.mkdir(parents=True, exist_ok=True)

    for entry in registry_entries:
        if entry.ingest_status not in ("parsed", "new"):
            continue
        local = workspace_base / entry.local_path
        if not local.exists():
            logger.warning(f"[CardBuilder] File missing: {local}")
            continue

        try:
            card, status = build_paper_card_from_file(
                local, entry.paper_id, stage_target, gateway,
            )
            card_path = output_dir / f"{entry.paper_id}_card.json"
            card_path.write_text(card.model_dump_json(indent=2), encoding="utf-8")

            if status != "card_failed_quality_gate":
                cards.append(card)

            if registry:
                registry.update_status(entry.paper_id, status)

            quality_log.append({
                "paper_id": entry.paper_id,
                "local_path": str(entry.local_path),
                "status": status,
                "findings_count": _count_findings(card),
                "mechanism_findings": len(card.mechanism_relevant_findings),
                "numerical_findings": len(card.numerical_findings),
                "eis_findings": len(card.eis_shape_findings),
                "arrhenius_findings": len(card.arrhenius_vtf_findings),
            })

            logger.info(f"[CardBuilder] {entry.paper_id}: {status}")
        except Exception as e:
            logger.error(f"[CardBuilder] FAILED: {entry.paper_id}: {e}")
            quality_log.append({
                "paper_id": entry.paper_id,
                "local_path": str(entry.local_path),
                "status": "card_build_error",
                "error": str(e),
            })

    log_path = output_dir / "card_quality_log.json"
    log_path.write_text(
        json.dumps(quality_log, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    logger.info(f"[CardBuilder] Quality log: {log_path} ({len(quality_log)} entries)")
    return cards


def load_paper_cards(cards_dir: Path) -> list[PaperCard]:
    """从目录加载已有的 PaperCard JSON 文件。"""
    cards = []
    if not cards_dir.is_dir():
        return cards
    for f in sorted(cards_dir.glob("*_card.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            cards.append(PaperCard(**data))
        except Exception as e:
            logger.warning(f"[CardBuilder] Load error {f.name}: {e}")
    return cards
