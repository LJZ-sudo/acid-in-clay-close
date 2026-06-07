from __future__ import annotations

import json
import logging
from pathlib import Path

from pydantic import BaseModel, Field

from s8_stage3.config.prompt_registry import load_prompt
from s8_stage3.contracts.descriptor import DescriptorSheet
from s8_stage3.contracts.literature import (
    ComponentDescriptorClaim,
    LiteratureCard,
    LiteratureSurvey,
)
from s8_stage3.io.writers import write_json

logger = logging.getLogger(__name__)


class _S08BatchClaimOutput(BaseModel):
    synthesis_notes: str = ""
    component_descriptor_claims_by_card: dict[str, list[ComponentDescriptorClaim]] = Field(default_factory=dict)


def _paper_card_material_summary(pc) -> str:
    """Build a materials summary from the current PaperCard schema.

    Older S08 code expected a ``material_relevant_findings`` field, but the
    current PaperCard contract stores all extracted findings under mechanism,
    numerical, EIS, and Arrhenius/VTF fields regardless of stage target.
    """
    findings: list[str] = []
    for attr in (
        "material_relevant_findings",
        "mechanism_relevant_findings",
        "arrhenius_vtf_findings",
        "eis_shape_findings",
        "limitations",
    ):
        values = getattr(pc, attr, []) or []
        if isinstance(values, list):
            findings.extend(str(item) for item in values if str(item).strip())
    numerical = getattr(pc, "numerical_findings", []) or []
    if isinstance(numerical, list):
        for item in numerical[:3]:
            if isinstance(item, dict):
                metric = item.get("metric", "")
                value = item.get("value", "")
                unit = item.get("unit", "")
                conditions = item.get("conditions", "")
                text = " ".join(str(x) for x in [metric, value, unit, conditions] if str(x).strip())
                if text:
                    findings.append(text)
            elif str(item).strip():
                findings.append(str(item))
    return " ".join(findings[:3])


def _paper_card_relevance_score(pc) -> float:
    judgement = getattr(pc, "relevance_judgement", {}) or {}
    try:
        score = float(judgement.get("score", 0.0))
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, score))


def _select_material_paper_cards(
    paper_cards: list,
    *,
    min_relevance: float = 0.3,
) -> list:
    selected: list = []
    dropped_low_relevance = 0
    dropped_empty_summary = 0
    for pc in paper_cards:
        score = _paper_card_relevance_score(pc)
        if score < min_relevance:
            dropped_low_relevance += 1
            continue
        if not _paper_card_material_summary(pc).strip():
            dropped_empty_summary += 1
            continue
        selected.append(pc)
    logger.info(
        "[S08] Selected %d/%d material paper cards for D4 extraction "
        "(min_relevance=%.2f, dropped_low_relevance=%d, dropped_empty_summary=%d)",
        len(selected),
        len(paper_cards),
        min_relevance,
        dropped_low_relevance,
        dropped_empty_summary,
    )
    return selected


def _extra_mock_material_cards(existing_ids: set[str]) -> list[LiteratureCard]:
    extras = [
        LiteratureCard(
            card_id="MAT-pva",
            title="PVA matrix continuity and hydrogen-bond compatibilisation",
            authors="Mock P",
            year=2022,
            summary="PVA improves film continuity and hydrogen-bond coupling in acid polymer membranes.",
            relevance_to_descriptors="D2, D4",
            component_descriptor_claims=[
                ComponentDescriptorClaim(
                    component="PVA",
                    descriptor_ids=["D2", "D4"],
                    quantitative_anchor="film-forming compatibiliser",
                    claim_text="PVA supports acid retention and cold-window matrix continuity.",
                )
            ],
        ),
        LiteratureCard(
            card_id="MAT-sep",
            title="Sepiolite as one-dimensional hydrated clay scaffold",
            authors="Mock S",
            year=2021,
            summary="Sepiolite offers 1-D fibrous confinement and acid retention analogs.",
            relevance_to_descriptors="D3, D5",
            component_descriptor_claims=[
                ComponentDescriptorClaim(
                    component="sepiolite",
                    descriptor_ids=["D3", "D5"],
                    quantitative_anchor="1-D fibrous clay",
                    claim_text="Sepiolite-like clay supports confinement and leakage-control descriptors.",
                )
            ],
        ),
        LiteratureCard(
            card_id="MAT-biomass-A",
            title="Biomass starch placeholder as OH-rich host",
            authors="Mock B",
            year=2024,
            summary="Biomass starch provides dense OH sites and retained bound water.",
            relevance_to_descriptors="D1, D4",
            component_descriptor_claims=[
                ComponentDescriptorClaim(
                    component="biomass-starch-A",
                    descriptor_ids=["D1", "D4"],
                    quantitative_anchor="OH-rich biopolymer host",
                    claim_text="Biomass starch analog supports OH-rich and cold-window host descriptors.",
                )
            ],
        ),
    ]
    return [card for card in extras if card.card_id not in existing_ids]


def _write_material_support_files(output_dir: Path, survey: LiteratureSurvey) -> None:
    claims: list[dict] = []
    for card in survey.cards:
        for claim in card.component_descriptor_claims:
            claims.append(
                {
                    "card_id": card.card_id,
                    "paper_id": card.card_id,
                    "paper_title": card.title,
                    "component": claim.component,
                    "descriptor_ids": claim.descriptor_ids,
                    "quantitative_anchor": claim.quantitative_anchor,
                    "claim_text": claim.claim_text,
                    "confidence": claim.confidence,
                    "human_review_status": claim.human_review_status,
                    "reviewer": claim.reviewer,
                    "review_notes": claim.review_notes,
                }
            )
    out_dir = output_dir / "06_literature_materials"
    write_json(out_dir / "literature_cards_materials.json", survey)
    write_json(out_dir / "descriptor_claim_pool.json", {"claims": claims, "n_claims": len(claims)})
    descriptor_counts: dict[str, int] = {}
    for claim in claims:
        for did in claim["descriptor_ids"]:
            descriptor_counts[did] = descriptor_counts.get(did, 0) + 1
    write_json(
        out_dir / "claim_coverage_summary.json",
        {"descriptor_claim_counts": descriptor_counts, "n_cards": len(survey.cards)},
    )
    write_json(
        out_dir / "material_pool_balance.json",
        {
            "n_cards": len(survey.cards),
            "n_component_descriptor_claims": len(claims),
            "card_ids": [card.card_id for card in survey.cards],
        },
    )


def _descriptor_input(descriptor_sheet: DescriptorSheet) -> list[dict]:
    descriptors: list[dict] = []
    for descriptor in descriptor_sheet.descriptors:
        dumped = descriptor.model_dump(mode="json")
        descriptors.append(
            {
                "id": dumped.get("descriptor_id"),
                "text": dumped.get("descriptor_text"),
                "priority": dumped.get("priority"),
            }
        )
    return descriptors


def _card_input(card: LiteratureCard) -> dict:
    return {
        "card_id": card.card_id,
        "title": card.title,
        "summary": card.summary,
        "relevance_to_descriptors": card.relevance_to_descriptors,
    }


def _batched(items: list[LiteratureCard], size: int) -> list[list[LiteratureCard]]:
    size = max(1, int(size or 1))
    return [items[i : i + size] for i in range(0, len(items), size)]


def _valid_claims_for_card(
    claims: list[ComponentDescriptorClaim],
    *,
    valid_descriptor_ids: set[str],
) -> list[ComponentDescriptorClaim]:
    valid: list[ComponentDescriptorClaim] = []
    for claim in claims:
        descriptor_ids = [did for did in claim.descriptor_ids if did in valid_descriptor_ids]
        if not claim.component.strip() or not descriptor_ids:
            continue
        valid.append(claim.model_copy(update={"descriptor_ids": descriptor_ids}))
    return valid


def _attach_component_descriptor_claims(
    *,
    descriptor_sheet: DescriptorSheet,
    cards: list[LiteratureCard],
    gateway,
    settings,
    strict: bool,
) -> tuple[str, dict]:
    if not cards:
        return "", {"n_batches": 0, "n_claims": 0, "n_cards": 0}
    if all(card.component_descriptor_claims for card in cards):
        n_claims = sum(len(card.component_descriptor_claims) for card in cards)
        return "", {"n_batches": 0, "n_claims": n_claims, "n_cards": len(cards), "source": "preexisting"}

    valid_descriptor_ids = {
        str(row["id"]) for row in _descriptor_input(descriptor_sheet) if row.get("id")
    }
    batch_size = int(getattr(settings, "s08_claim_batch_size", 4) or 4)
    synthesis_notes: list[str] = []
    n_claims = 0
    n_batches = 0
    cards_by_id = {card.card_id: card for card in cards}

    for batch in _batched(cards, batch_size):
        batch_ids = {card.card_id for card in batch}
        payload = {
            "descriptors": _descriptor_input(descriptor_sheet),
            "cards": [_card_input(card) for card in batch],
        }
        try:
            raw = gateway.chat_json(
                [
                    {"role": "system", "content": load_prompt("s08_literature_materials")},
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
                ],
                step="s08_summarize_batch",
                output_schema=_S08BatchClaimOutput,
            )
        except Exception as exc:
            msg = f"[S08] component claim extraction failed for batch {sorted(batch_ids)}: {exc}"
            if strict:
                raise RuntimeError(msg) from exc
            logger.warning(msg)
            continue

        parsed = _S08BatchClaimOutput.model_validate(raw)
        if parsed.synthesis_notes:
            synthesis_notes.append(parsed.synthesis_notes.strip())
        for card_id, claims in parsed.component_descriptor_claims_by_card.items():
            if card_id not in batch_ids:
                logger.warning("[S08] Dropping claims for card outside current batch: %s", card_id)
                continue
            valid_claims = _valid_claims_for_card(
                claims,
                valid_descriptor_ids=valid_descriptor_ids,
            )
            cards_by_id[card_id].component_descriptor_claims = valid_claims
            n_claims += len(valid_claims)
        n_batches += 1

    diagnostics = {
        "n_batches": n_batches,
        "n_claims": n_claims,
        "n_cards": len(cards),
        "n_cards_with_claims": sum(1 for card in cards if card.component_descriptor_claims),
    }
    if strict and cards and n_claims == 0:
        raise RuntimeError("[S08][strict] component claim extraction produced zero D4 claims")
    return " ".join(note for note in synthesis_notes if note), diagnostics


def _build_api_queries(descriptor_sheet: DescriptorSheet, *, max_queries: int = 5) -> list[str]:
    """Compose OpenAlex search queries from the descriptor sheet.

    A stable base query anchors the materials domain; high-priority descriptor
    texts are appended as focused sub-queries. Bounded to ``max_queries`` to
    keep API usage polite and reproducible.
    """
    base = "proton conducting clay-confined acid composite solid electrolyte"
    queries: list[str] = [base]
    rows = sorted(
        _descriptor_input(descriptor_sheet),
        key=lambda r: (r.get("priority") is None, r.get("priority")),
    )
    for row in rows:
        text = str(row.get("text") or "").strip()
        if text:
            queries.append(f"{text} proton conductor material")
        if len(queries) >= max_queries:
            break
    # de-dupe while preserving order
    seen: set[str] = set()
    out: list[str] = []
    for q in queries:
        if q not in seen:
            seen.add(q)
            out.append(q)
    return out


def _fetch_api_cards(
    descriptor_sheet: DescriptorSheet,
    settings,
    *,
    provider=None,
    strict: bool = False,
) -> list[LiteratureCard]:
    """Fetch real materials literature via OpenAlex and build LiteratureCards.

    Offline-safe: the provider already swallows network errors and returns an
    empty list, so a failed/absent network yields an empty survey rather than a
    crash. ``provider`` is injectable for tests; in production it defaults to a
    real :class:`OpenAlexProvider`.
    """
    if provider is None:
        from s8_stage3.literature.providers.openalex_provider import OpenAlexProvider

        provider = OpenAlexProvider(mailto=str(getattr(settings, "openalex_mailto", "") or ""))

    max_results = int(getattr(settings, "s08_api_max_results_per_query", 8) or 8)
    from_year = getattr(settings, "s08_api_from_year", None)

    cards: list[LiteratureCard] = []
    seen_ids: set[str] = set()
    for query in _build_api_queries(descriptor_sheet):
        records = provider.search(query, max_results=max_results, from_year=from_year)
        for rec in records:
            paper_id = str(getattr(rec, "paper_id", "") or "").strip()
            if not paper_id or paper_id in seen_ids:
                continue
            seen_ids.add(paper_id)
            cards.append(
                LiteratureCard(
                    card_id=paper_id,
                    title=str(getattr(rec, "title", "") or ""),
                    authors=str(getattr(rec, "authors", "") or ""),
                    year=int(getattr(rec, "year", 0) or 0),
                    doi=str(getattr(rec, "doi", "") or ""),
                    summary=str(getattr(rec, "abstract", "") or "")[:2000],
                    relevance_to_descriptors=f"OpenAlex match for: {query}",
                )
            )
    logger.info("[S08] API mode (OpenAlex) fetched %d unique material cards", len(cards))
    if strict and not cards:
        raise RuntimeError("[S08][strict] API mode fetched zero material cards")
    return cards


def _fetch_manual_cards_and_context(settings, *, strict: bool = False) -> tuple[list[LiteratureCard], str]:
    from s8_stage3.literature.context_pack_builder import (
        format_context_for_llm,
        load_context_pack,
    )
    from s8_stage3.literature.evidence_row_builder import extract_rows_from_cards
    from s8_stage3.literature.manual_ingest import LiteratureWorkspace
    from s8_stage3.literature.paper_card_builder import load_paper_cards

    ws = LiteratureWorkspace(settings.literature_workspace_dir)
    ctx_path = ws.context_packs_dir / "ctx-s08.json"
    ctx = load_context_pack(ctx_path)
    if ctx:
        paper_cards = load_paper_cards(ws.paper_cards_dir / "materials")
        if strict and not paper_cards:
            raise RuntimeError("[S08][strict] context pack exists but paper_cards/materials is empty")
        selected_cards = _select_material_paper_cards(
            paper_cards,
            min_relevance=float(getattr(settings, "s08_min_claim_relevance", 0.3) or 0.0),
        )
        if strict and not selected_cards:
            raise RuntimeError("[S08][strict] no material paper cards passed relevance/summary filters")
        rows = extract_rows_from_cards(selected_cards)
        if strict and not rows:
            raise RuntimeError("[S08][strict] paper cards exist but evidence rows are empty")
        cards = [
            LiteratureCard(
                card_id=pc.paper_id,
                title=str(pc.bibliography.get("title", "")),
                authors=str(pc.bibliography.get("authors", "")),
                year=int(pc.bibliography.get("year", 0) or 0),
                summary=_paper_card_material_summary(pc),
                relevance_to_descriptors=str(pc.relevance_judgement.get("reason", "")),
            )
            for pc in selected_cards
        ]
        return cards, format_context_for_llm(ctx, rows)
    if strict:
        raise RuntimeError(f"[S08][strict] manual mode requires context pack at {ctx_path}.")
    registry = ws.get_registry()
    entries = registry.by_stage("s08_materials") or registry.all_entries()
    cards = [
        LiteratureCard(
            card_id=e.paper_id,
            title=e.title or "",
            authors=", ".join(e.authors) if isinstance(e.authors, list) else str(e.authors or ""),
            year=e.year or 0,
            summary="",
            relevance_to_descriptors="From manual registry fallback.",
        )
        for e in entries
    ]
    return cards, ""


def run_s08(
    descriptor_sheet: DescriptorSheet,
    gateway,
    output_dir: Path,
    literature_mode: str = "mock",
    lit_cache=None,
    settings=None,
    manual_strict: bool = False,
    api_provider=None,
) -> LiteratureSurvey:
    if literature_mode == "mock":
        raw = gateway.chat_json(
            [
                {"role": "system", "content": load_prompt("s08_literature_materials")},
                {"role": "user", "content": descriptor_sheet.model_dump_json()},
            ],
            step="s08_literature_scout_materials",
            output_schema=LiteratureSurvey,
        )
        survey = LiteratureSurvey.model_validate(raw)
        existing = {card.card_id for card in survey.cards}
        survey.cards.extend(_extra_mock_material_cards(existing))
        _write_material_support_files(output_dir, survey)
        return survey

    context_text = ""
    cards: list[LiteratureCard] = []
    if literature_mode == "manual":
        cards, context_text = _fetch_manual_cards_and_context(settings, strict=manual_strict)
    elif literature_mode == "api":
        # Tier3 (issue 2): real OpenAlex-backed materials literature. Offline-safe
        # (empty result -> empty survey, no crash). Provider injectable for tests.
        cards = _fetch_api_cards(
            descriptor_sheet, settings, provider=api_provider, strict=manual_strict
        )
    elif literature_mode == "hybrid":
        cards, context_text = _fetch_manual_cards_and_context(settings, strict=False)
        api_cards = _fetch_api_cards(descriptor_sheet, settings, provider=api_provider, strict=False)
        existing_ids = {c.card_id for c in cards}
        cards.extend(c for c in api_cards if c.card_id not in existing_ids)
    else:
        raise ValueError(f"Unknown literature_mode for S08: {literature_mode}")

    claim_notes = ""
    claim_diagnostics = {"n_batches": 0, "n_claims": 0, "n_cards": len(cards)}
    if literature_mode in {"manual", "hybrid", "api"} and cards:
        claim_notes, claim_diagnostics = _attach_component_descriptor_claims(
            descriptor_sheet=descriptor_sheet,
            cards=cards,
            gateway=gateway,
            settings=settings,
            strict=manual_strict,
        )

    survey = LiteratureSurvey(
        step_id="s08",
        survey_scope="material_search",
        cards=cards,
        synthesis_notes=claim_notes or context_text or "Material literature survey completed.",
    )
    _write_material_support_files(output_dir, survey)
    write_json(output_dir / "06_literature_materials" / "s08_claim_extraction_diagnostics.json", claim_diagnostics)
    return survey
