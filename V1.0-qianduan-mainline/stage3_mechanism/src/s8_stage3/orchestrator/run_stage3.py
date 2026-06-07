from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("run_stage3")


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage3 Mechanism & Materials Pipeline")
    parser.add_argument("--mode", choices=["mock", "real"], default="mock")
    parser.add_argument("--llm-mode", choices=["mock", "live"], default=None)
    parser.add_argument("--literature-mode", choices=["mock", "api", "manual", "hybrid"], default=None)
    parser.add_argument("--model-tier", choices=["cheap", "standard", "premium"], default=None)
    parser.add_argument("--until", default="")
    parser.add_argument("--max-samples", type=int, default=0)
    parser.add_argument("--sample-ids", default="")
    parser.add_argument("--stage2-output-dir", default="")
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--allow-legacy-atlas", action="store_true")
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument(
        "--s09-evidence-based-generation",
        action="store_true",
        help="Opt-in: enable S09 evidence-based candidate generation (default OFF keeps the frozen deterministic_from_d4 path).",
    )
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--build-query-packets-only", action="store_true")
    parser.add_argument("--ingest-manual-papers", action="store_true")
    parser.add_argument("--rebuild-paper-cards", action="store_true")
    parser.add_argument("--rebuild-evidence-tables", action="store_true")
    parser.add_argument("--stage-target", choices=["s05_mechanism", "s08_materials"], default=None)
    parser.add_argument("--manual-strict", action="store_true")
    parser.add_argument("--fetch-oa-papers", action="store_true")
    parser.add_argument("--oa-max-per-query", type=int, default=5)
    parser.add_argument("--oa-max-total", type=int, default=10)
    parser.add_argument("--oa-min-year", type=int, default=2010)
    args = parser.parse_args()

    if args.llm_mode:
        os.environ["STAGE3_LLM_MODE"] = args.llm_mode
    if args.model_tier:
        os.environ["STAGE3_MODEL_TIER"] = args.model_tier
    if args.no_cache:
        os.environ["STAGE3_ENABLE_CACHE"] = "false"
    if args.s09_evidence_based_generation:
        os.environ["STAGE3_S09_EVIDENCE_BASED_GENERATION"] = "true"

    from s8_stage3.config.llm_gateway import LLMGateway
    from s8_stage3.config.model_registry import ModelRegistry
    from s8_stage3.config.settings import load_settings

    settings = load_settings()
    registry = ModelRegistry(
        cheap=settings.model_cheap,
        standard=settings.model_standard,
        premium=settings.model_premium,
    )
    gateway = LLMGateway(settings, registry)
    literature_mode = args.literature_mode or settings.literature_mode

    if args.smoke:
        ok = gateway.smoke_chat()
        sys.exit(0 if ok else 1)
    if args.build_query_packets_only:
        _run_query_packets(args, settings)
        return
    if args.ingest_manual_papers:
        _run_ingest(args, settings)
        return
    if args.fetch_oa_papers:
        _run_fetch_oa_papers(args, settings)
        return
    if args.rebuild_paper_cards or args.rebuild_evidence_tables:
        _run_rebuild_literature(args, settings)
        return

    from s8_stage3.orchestrator.pipeline import Pipeline

    sample_ids = [s.strip() for s in args.sample_ids.split(",") if s.strip()] or None
    output_dir = Path(args.output_dir).resolve() if args.output_dir else settings.outputs_dir
    pipeline = Pipeline(
        settings=settings,
        gateway=gateway,
        output_dir=output_dir,
        run_mode=args.mode,
        literature_mode=literature_mode,
        until_step=args.until,
        max_samples=args.max_samples or None,
        sample_ids=sample_ids,
        manual_strict=args.manual_strict,
        stage2_output_dir=Path(args.stage2_output_dir) if args.stage2_output_dir else None,
        allow_legacy_atlas=bool(args.allow_legacy_atlas),
    )
    results = pipeline.run_mock() if args.mode == "mock" else pipeline.run_real()
    logger.info("Pipeline completed successfully; outputs written to %s", output_dir)
    logger.info("Result keys: %s", ", ".join(sorted(results.keys())))


def _run_query_packets(args, settings) -> None:
    from s8_stage3.literature.query_packet_builder import (
        build_material_query_packet,
        build_mechanism_query_packet,
        save_query_packet,
    )

    import json

    out_dir = settings.literature_workspace_dir / "00_query_packets"
    targets = [args.stage_target] if args.stage_target else ["s05_mechanism", "s08_materials"]
    for target in targets:
        if target == "s05_mechanism":
            h_path = settings.outputs_dir / "02_hypotheses" / "hypothesis_board.json"
            data = json.loads(h_path.read_text(encoding="utf-8")) if h_path.exists() else {"hypotheses": []}
            packet = build_mechanism_query_packet(data)
            save_query_packet(packet, out_dir / "s05_mechanism")
        elif target == "s08_materials":
            d_path = settings.outputs_dir / "05_descriptors" / "descriptor_sheet.json"
            data = json.loads(d_path.read_text(encoding="utf-8")) if d_path.exists() else {"descriptors": []}
            packet = build_material_query_packet(data)
            save_query_packet(packet, out_dir / "s08_materials")


def _run_ingest(args, settings) -> None:
    from s8_stage3.literature.manual_ingest import LiteratureWorkspace, ingest_inbox

    ws = LiteratureWorkspace(settings.literature_workspace_dir)
    result = ingest_inbox(ws, stage=args.stage_target or "")
    logger.info("Ingest complete: %s new, %s duplicate, %s failed", result.success, result.skipped_duplicate, result.failed)


def _run_fetch_oa_papers(args, settings) -> None:
    from s8_stage3.literature.manual_ingest import LiteratureWorkspace
    from s8_stage3.literature.oa_fetcher import fetch_and_download_oa_papers
    from s8_stage3.literature.query_builder import build_material_queries, build_mechanism_queries

    import json

    ws = LiteratureWorkspace(settings.literature_workspace_dir)
    targets = [args.stage_target] if args.stage_target else ["s05_mechanism", "s08_materials"]
    for target in targets:
        if target == "s05_mechanism":
            h_path = settings.outputs_dir / "02_hypotheses" / "hypothesis_board.json"
            if not h_path.exists():
                logger.warning("Missing %s; run through S04 first", h_path)
                continue
            queries = build_mechanism_queries(json.loads(h_path.read_text(encoding="utf-8")))
        else:
            d_path = settings.outputs_dir / "05_descriptors" / "descriptor_sheet.json"
            if not d_path.exists():
                logger.warning("Missing %s; run through S07 first", d_path)
                continue
            queries = build_material_queries(json.loads(d_path.read_text(encoding="utf-8")))
        result = fetch_and_download_oa_papers(
            queries=queries,
            workspace=ws,
            stage_target=target,
            mailto=getattr(settings, "openalex_mailto", ""),
            max_per_query=args.oa_max_per_query,
            max_total=args.oa_max_total,
            min_year=args.oa_min_year,
        )
        logger.info("[OAFetch] %s: %s", target, result.summary_line())


def _run_rebuild_literature(args, settings) -> None:
    from s8_stage3.literature.context_pack_builder import build_all_context_packs, save_context_packs
    from s8_stage3.literature.evidence_row_builder import extract_rows_from_cards, reset_counter
    from s8_stage3.literature.evidence_table_builder import (
        build_material_evidence_table,
        build_mechanism_evidence_table,
        save_evidence_table,
    )
    from s8_stage3.literature.manual_ingest import LiteratureWorkspace
    from s8_stage3.literature.paper_card_builder import load_paper_cards

    ws = LiteratureWorkspace(settings.literature_workspace_dir)
    reset_counter()
    mech_cards = load_paper_cards(ws.paper_cards_dir / "mechanism")
    mat_cards = load_paper_cards(ws.paper_cards_dir / "materials")
    mech_rows = extract_rows_from_cards(mech_cards)
    mat_rows = extract_rows_from_cards(mat_cards)
    mech_table = build_mechanism_evidence_table(mech_rows) if mech_rows else None
    mat_table = build_material_evidence_table(mat_rows) if mat_rows else None
    if mech_table:
        save_evidence_table(mech_table, ws.curated_tables_dir)
    if mat_table:
        save_evidence_table(mat_table, ws.curated_tables_dir)
    packs = build_all_context_packs(mech_table, mat_table)
    if packs:
        save_context_packs(packs, ws.context_packs_dir)
    logger.info("Evidence rebuild: mechanism=%d rows, materials=%d rows, packs=%d", len(mech_rows), len(mat_rows), len(packs))


if __name__ == "__main__":
    main()
