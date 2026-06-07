"""Batch CLI: generate Sample Closure Cards for existing Stage0 bundles.

Examples
--------

Dry run (no LLM, deterministic-only) for one sample::

    python -m stage0_measurement.run_closure_offline \\
        --bundles V1.0-qianduan-mainline/output/stage0_results/S8-2-1-1 \\
        --no-llm

Full run for all S8 bundles, writing closure_report.json next to each bundle::

    python -m stage0_measurement.run_closure_offline \\
        --bundles "V1.0-qianduan-mainline/output/stage0_results/S8-*" \\
        --campaign S8-acid-in-clay
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from glob import glob
from pathlib import Path
from typing import List, Optional

from modules.closure.closure_agent import run_closure_for_bundle_path
from modules.closure.closure_schema import CampaignContextLite


logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("closure_offline")


def _resolve_bundle_paths(patterns: List[str]) -> List[Path]:
    bundle_paths: List[Path] = []
    for pat in patterns:
        # Accept either a sample directory or a glob expansion.
        for raw in glob(pat):
            p = Path(raw)
            if p.is_dir():
                candidate = p / "stage0_result_bundle.json"
                if candidate.exists():
                    bundle_paths.append(candidate)
            elif p.name == "stage0_result_bundle.json" and p.exists():
                bundle_paths.append(p)
    bundle_paths = sorted(set(bundle_paths))
    return bundle_paths


def _scan_campaign_best_sigma(bundle_paths: List[Path]) -> Optional[float]:
    """Pre-pass: compute current best σ_RT across the input set, for context."""
    best: Optional[float] = None
    for bp in bundle_paths:
        try:
            data = json.loads(bp.read_text(encoding="utf-8"))
        except Exception:
            continue
        ok = [p for p in data.get("eis_points") or [] if p.get("status") == "OK"]
        if not ok:
            continue
        rt = min(ok, key=lambda p: abs((p.get("T_C") or 1e9) - 25.0))
        sigma_rt = rt.get("sigma_S_cm")
        if sigma_rt is None:
            continue
        if best is None or sigma_rt > best:
            best = sigma_rt
    return best


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Batch generate Sample Closure Cards.")
    parser.add_argument(
        "--bundles",
        nargs="+",
        required=True,
        help="One or more sample directories or glob patterns containing stage0_result_bundle.json.",
    )
    parser.add_argument(
        "--campaign",
        default=None,
        help="Optional campaign name for the closure card's tiny comparison line.",
    )
    parser.add_argument(
        "--user-prep",
        default=None,
        help="Optional path to a single user_prep.json applied to ALL bundles (rare; usually per-sample sidecar).",
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Skip LLM call; produce deterministic-only reports.",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Override CLOSURE_LLM_MODEL (e.g. deepseek-v3.1, DeepSeek-R1).",
    )
    parser.add_argument(
        "--output-suffix",
        default="closure_report.json",
        help="Filename written next to each bundle (default: closure_report.json).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit to first N bundles for smoke tests.",
    )
    args = parser.parse_args(argv)

    bundles = _resolve_bundle_paths(args.bundles)
    if args.limit:
        bundles = bundles[: args.limit]
    if not bundles:
        logger.error("No bundles matched %s", args.bundles)
        return 1

    logger.info("Processing %d bundle(s)", len(bundles))
    best_sigma = _scan_campaign_best_sigma(bundles)
    if best_sigma is not None:
        logger.info("Pre-scan best σ_RT = %.3e S/cm", best_sigma)

    campaign_ctx = CampaignContextLite(
        campaign_name=args.campaign,
        n_samples_so_far=len(bundles),
        current_best_sigma_RT_S_per_cm=best_sigma,
    )

    user_prep_path = Path(args.user_prep) if args.user_prep else None
    model_settings = None
    if args.model:
        from modules.closure.closure_agent import _default_model_settings  # noqa: WPS437

        model_settings = _default_model_settings()
        model_settings["model"] = args.model

    ok_count = 0
    fallback_count = 0
    fail_count = 0
    summary_rows = []

    for bp in bundles:
        try:
            sample_user_prep = bp.parent / "user_prep.json"
            chosen_prep = sample_user_prep if sample_user_prep.exists() else user_prep_path
            report, out = run_closure_for_bundle_path(
                bp,
                output_path=bp.parent / args.output_suffix,
                user_prep_path=chosen_prep,
                campaign_context=campaign_ctx,
                use_llm=not args.no_llm,
                model_settings=model_settings,
            )
            ok_count += 1
            if not report.meta.llm_used:
                fallback_count += 1
            summary_rows.append(
                {
                    "sample_id": report.meta.sample_id,
                    "llm_used": report.meta.llm_used,
                    "fallback_reason": report.meta.fallback_reason,
                    "sigma_RT_S_per_cm": report.performance_card.sigma_RT_S_per_cm,
                    "n_segments": report.performance_card.n_segments,
                    "n_phase_transitions": len(report.phase_transitions),
                    "n_risks": len(report.risks_warnings),
                    "output": str(out),
                }
            )
            logger.info(
                "[OK] %s  llm_used=%s  σ_RT=%s",
                report.meta.sample_id,
                report.meta.llm_used,
                f"{report.performance_card.sigma_RT_S_per_cm:.3e}"
                if report.performance_card.sigma_RT_S_per_cm
                else "n/a",
            )
        except Exception as e:  # noqa: BLE001
            fail_count += 1
            logger.exception("[FAIL] %s: %s", bp, e)

    logger.info("Done. ok=%d fallback=%d fail=%d", ok_count, fallback_count, fail_count)
    return 0 if fail_count == 0 else 2


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    sys.exit(main())
