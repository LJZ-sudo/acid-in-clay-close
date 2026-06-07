"""Rebuild campaign-aware Stage1 closed-loop metrics.

This is intentionally deterministic and does not call Stage0 hardware or LLMs.
It reads the campaign config, its configured history DB, and closed_loop_rounds
under the configured output directory, then writes closed_loop_metrics.json.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional

from closed_loop.metrics_aggregator import build_closed_loop_metrics


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_stage1_path(root: Path, value: Optional[str], fallback: str) -> Path:
    raw = Path(value or fallback)
    return raw if raw.is_absolute() else root / raw


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Rebuild Stage1 closed_loop_metrics.json for one campaign."
    )
    parser.add_argument(
        "--campaign-config",
        default="campaigns/attapulgite_aice_campaign.json",
        help="Campaign config JSON path, relative to stage1_optimization by default.",
    )
    parser.add_argument(
        "--n-initial-points",
        type=int,
        default=3,
        help="Number of initial trials used for best_initial_* metrics.",
    )
    args = parser.parse_args()

    stage1_root = Path(__file__).resolve().parent
    campaign_path = _resolve_stage1_path(stage1_root, args.campaign_config, "")
    campaign = _load_json(campaign_path)
    storage = campaign.get("storage") or {}
    objective = campaign.get("objective") or {}

    history_db_path = _resolve_stage1_path(
        stage1_root,
        storage.get("history_db"),
        "campaign_memory/history_db_attapulgite.json",
    )
    output_dir = _resolve_stage1_path(stage1_root, storage.get("output_dir"), "output")

    metrics = build_closed_loop_metrics(
        output_dir=output_dir,
        history_db_path=history_db_path,
        n_initial_points=args.n_initial_points,
        objective_target=objective.get("target", "combined_score"),
        objective_goal=objective.get("goal", "maximize"),
        campaign_name=campaign.get("campaign_name"),
        campaign_config=campaign,
    )
    out_path = output_dir / "closed_loop_metrics.json"
    print(
        json.dumps(
            {
                "wrote": str(out_path),
                "campaign_name": metrics.get("campaign_name"),
                "closed_loop_validity": metrics.get("closed_loop_validity"),
                "n_closed_loop_rounds": metrics.get("n_closed_loop_rounds"),
                "n_history_trials": metrics.get("n_history_trials"),
                "n_bo_suggestions": metrics.get("n_bo_suggestions"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
