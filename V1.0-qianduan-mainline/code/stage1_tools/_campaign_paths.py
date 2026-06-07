# -*- coding: utf-8 -*-
"""Campaign storage helpers for legacy Stage1 utility scripts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
STAGE1_DIR = PROJECT_ROOT / "stage1_optimization"
DEFAULT_REPLAY_CAMPAIGN = (
    PROJECT_ROOT.parent
    / "three_pillars"
    / "pillar1_transfer_agent"
    / "s8_acid_in_clay_mother_system"
    / "s8_sepiolite_campaign_config.json"
)
DEFAULT_REAL_CAMPAIGN = STAGE1_DIR / "campaigns" / "attapulgite_aice_campaign.json"


@dataclass(frozen=True)
class CampaignStorage:
    campaign_config: Path
    campaign_name: str
    source_tag: str
    history_db: Path
    output_dir: Path
    next_recipe: Path
    closed_loop_metrics: Path

    @property
    def is_attapulgite_real(self) -> bool:
        return (
            self.source_tag == "attapulgite_aice"
            or self.history_db.name == "history_db_attapulgite.json"
        )


def _resolve_config(path: Optional[str | Path], default: Path) -> Path:
    raw = Path(path) if path else default
    if raw.is_absolute():
        return raw.resolve()
    if raw.parts and raw.parts[0] == "stage1_optimization":
        return (PROJECT_ROOT / raw).resolve()
    return (STAGE1_DIR / raw).resolve()


def _resolve_stage1_path(raw: Optional[str], default: Path, *, base_dir: Path | None = None) -> Path:
    if not raw:
        return default.resolve()
    path = Path(raw)
    if path.is_absolute():
        return path.resolve()
    anchor = base_dir if base_dir is not None else STAGE1_DIR
    return (anchor / path).resolve()


def load_campaign_storage(
    campaign_config: Optional[str | Path] = None,
    *,
    default_campaign: Path = DEFAULT_REPLAY_CAMPAIGN,
) -> CampaignStorage:
    cfg_path = _resolve_config(campaign_config, default_campaign)
    data = json.loads(cfg_path.read_text(encoding="utf-8"))
    storage = data.get("storage") or {}
    cfg_dir = cfg_path.parent
    output_dir = _resolve_stage1_path(
        storage.get("output_dir"), STAGE1_DIR / "output", base_dir=cfg_dir
    )
    history_db = _resolve_stage1_path(
        storage.get("history_db"),
        STAGE1_DIR / "campaign_memory" / "history_db_attapulgite.json",
        base_dir=cfg_dir,
    )
    return CampaignStorage(
        campaign_config=cfg_path,
        campaign_name=str(data.get("campaign_name") or cfg_path.stem),
        source_tag=str(data.get("source_tag") or cfg_path.stem),
        history_db=history_db,
        output_dir=output_dir,
        next_recipe=output_dir / "next_experiment_recipe.json",
        closed_loop_metrics=output_dir / "closed_loop_metrics.json",
    )


def require_not_real_history_reset(storage: CampaignStorage, *, allowed: bool) -> None:
    if storage.is_attapulgite_real and not allowed:
        raise RuntimeError(
            "Refusing to reset attapulgite real history. "
            "Pass the explicit allow flag only when this is intentional."
        )
