from __future__ import annotations

import logging
from pathlib import Path

from pydantic import BaseModel, Field

from s8_stage3.config.prompt_registry import load_prompt
from s8_stage3.contracts.hypothesis import HypothesisBoard
from s8_stage3.contracts.literature import LiteratureCard, LiteratureSurvey
from s8_stage3.contracts.paper import PaperRecord
from s8_stage3.io.writers import write_json

logger = logging.getLogger(__name__)


class _SynthesisOutput(BaseModel):
    synthesis_notes: str = Field("")


def _papers_to_literature_cards(papers: list[PaperRecord]) -> list[LiteratureCard]:
    return [
        LiteratureCard(
            card_id=p.paper_id,
            title=p.title,
            authors=p.authors,
            year=p.year,
            doi=p.doi,
            summary=(p.abstract or "")[:500],
            relevance_to_mechanism="API literature candidate",
        )
        for p in papers
    ]


def _summarize_with_llm(cards: list[LiteratureCard], board: HypothesisBoard, gateway) -> str:
    if not cards:
        return "No mechanism literature retrieved."
    card_text = "\n".join(
        f"[{card.card_id}] {card.title} ({card.year}): {card.summary[:220]}"
        for card in cards[:10]
    )
    hypothesis_text = "\n".join(
        f"{hyp.hypothesis_id}: {hyp.mechanism_label}"
        for hyp in board.hypotheses
    )
    raw = gateway.chat_json(
        [
            {"role": "system", "content": load_prompt("s05_literature_mechanism")},
            {
                "role": "user",
                "content": (
                    f"Hypotheses:\n{hypothesis_text}\n\nLiterature:\n{card_text}\n\n"
                    "Return JSON with synthesis_notes."
                ),
            },
        ],
        step="s05_literature_mechanism",
        output_schema=_SynthesisOutput,
    )
    return str(raw.get("synthesis_notes") or raw.get("notes") or "Synthesis unavailable.")


def _fetch_api_papers(board: HypothesisBoard, settings, lit_cache) -> list[PaperRecord]:
    from s8_stage3.literature.providers.openalex_provider import OpenAlexProvider
    from s8_stage3.literature.query_builder import build_mechanism_queries

    queries = build_mechanism_queries(board.model_dump(mode="json"))
    provider = OpenAlexProvider(mailto=getattr(settings, "openalex_mailto", ""))
    max_per = int(getattr(settings, "max_papers_per_query", 10) or 10)
    papers: list[PaperRecord] = []
    for query in queries[:5]:
        cached = lit_cache.get("openalex", query) if lit_cache else None
        if cached:
            papers.extend([PaperRecord(**row) for row in cached])
            continue
        results = provider.search(query, max_results=max_per)
        papers.extend(results)
        if lit_cache:
            lit_cache.put("openalex", query, 0, [row.model_dump() for row in results])
    return papers


def _fetch_manual_cards_and_context(
    settings,
    *,
    strict: bool = False,
) -> tuple[list[LiteratureCard], str]:
    from s8_stage3.literature.context_pack_builder import (
        format_context_for_llm,
        load_context_pack,
    )
    from s8_stage3.literature.evidence_row_builder import extract_rows_from_cards
    from s8_stage3.literature.manual_ingest import LiteratureWorkspace
    from s8_stage3.literature.paper_card_builder import load_paper_cards

    ws = LiteratureWorkspace(settings.literature_workspace_dir)
    ctx_path = ws.context_packs_dir / "ctx-s05.json"
    ctx = load_context_pack(ctx_path)
    if ctx:
        paper_cards = load_paper_cards(ws.paper_cards_dir / "mechanism")
        if strict and not paper_cards:
            raise RuntimeError("[S05][strict] context pack exists but paper_cards/mechanism is empty")
        rows = extract_rows_from_cards(paper_cards)
        if strict and not rows:
            raise RuntimeError("[S05][strict] paper cards exist but evidence rows are empty")
        cards = [
            LiteratureCard(
                card_id=pc.paper_id,
                title=str(pc.bibliography.get("title", "")),
                authors=str(pc.bibliography.get("authors", "")),
                year=int(pc.bibliography.get("year", 0) or 0),
                summary=" ".join(pc.mechanism_relevant_findings[:3]),
                relevance_to_mechanism=str(pc.relevance_judgement.get("reason", "")),
            )
            for pc in paper_cards
        ]
        return cards, format_context_for_llm(ctx, rows)

    if strict:
        raise RuntimeError(
            f"[S05][strict] manual mode requires context pack at {ctx_path}. "
            "Run literature ingest/rebuild first."
        )

    registry = ws.get_registry()
    entries = registry.by_stage("s05_mechanism") or registry.all_entries()
    cards = [
        LiteratureCard(
            card_id=e.paper_id,
            title=e.title or "",
            authors=", ".join(e.authors) if isinstance(e.authors, list) else str(e.authors or ""),
            year=e.year or 0,
            summary="",
            relevance_to_mechanism="From manual registry fallback.",
        )
        for e in entries
    ]
    return cards, ""


def run_s05(
    hypothesis_board: HypothesisBoard,
    gateway,
    output_dir: Path,
    literature_mode: str = "mock",
    lit_cache=None,
    settings=None,
    manual_strict: bool = False,
) -> LiteratureSurvey:
    cards: list[LiteratureCard] = []
    context_text = ""

    if literature_mode == "mock":
        raw = gateway.chat_json([], step="s05_literature_mechanism", output_schema=LiteratureSurvey)
        survey = LiteratureSurvey.model_validate(raw)
        write_json(output_dir / "03_literature_mechanism" / "literature_cards_mechanism.json", survey)
        return survey

    if literature_mode == "api":
        from s8_stage3.literature.deduper import deduplicate

        papers = _fetch_api_papers(hypothesis_board, settings, lit_cache)
        deduped = deduplicate(papers)
        max_total = int(getattr(settings, "max_total_papers_per_step", 50) or 50)
        cards = _papers_to_literature_cards(deduped.records[:max_total])
    elif literature_mode == "manual":
        cards, context_text = _fetch_manual_cards_and_context(settings, strict=manual_strict)
    elif literature_mode == "hybrid":
        cards, context_text = _fetch_manual_cards_and_context(settings, strict=False)
        try:
            api_cards = _papers_to_literature_cards(_fetch_api_papers(hypothesis_board, settings, lit_cache))
            seen = {card.card_id for card in cards}
            cards.extend([card for card in api_cards if card.card_id not in seen])
        except Exception as exc:  # noqa: BLE001
            logger.warning("[S05] Hybrid API retrieval failed: %s", exc)
    else:
        raise ValueError(f"Unknown literature_mode for S05: {literature_mode}")

    synthesis = _summarize_with_llm(cards, hypothesis_board, gateway)
    if context_text:
        synthesis = f"{context_text}\n\n{synthesis}"
    survey = LiteratureSurvey(
        step_id="s05",
        survey_scope="mechanism_constraint",
        cards=cards,
        synthesis_notes=synthesis,
    )
    write_json(output_dir / "03_literature_mechanism" / "literature_cards_mechanism.json", survey)
    return survey
