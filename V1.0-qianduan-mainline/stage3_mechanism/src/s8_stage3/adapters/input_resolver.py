"""Resolve Stage2 inputs for Stage3 real-mode runs.

The resolver deliberately chooses one complete input directory.  It does not
mix a legacy CSV/atlas directory with a newer ``stage3_seed.json`` from another
location, because that can silently bind unrelated evidence layers together.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

_BASE = Path(__file__).parent.parent.parent.parent  # stage3_mechanism/
_MAINLINE = _BASE.parent

LEGACY_REQUIRED_FILES = [
    "s8_input.csv",
    "data_profile.json",
    "execution_plan.json",
    "s8_evidence_atlas.json",
    "visualization_manifest.json",
]


@dataclass
class ResolvedInputs:
    input_dir: Path
    csv_path: Path | None = None
    data_profile_path: Path | None = None
    execution_plan_path: Path | None = None
    atlas_path: Path | None = None
    visualization_manifest_path: Path | None = None
    stage1_campaign_path: Path | None = None
    stage2_seed_v2_path: Path | None = None
    strict_real_input: bool = True
    allow_legacy_atlas: bool = False
    input_source: str = ""

    def is_complete(self) -> bool:
        if self.stage2_seed_v2_path and self.stage2_seed_v2_path.exists():
            return True
        return all(
            p is not None and p.exists()
            for p in [
                self.csv_path,
                self.data_profile_path,
                self.execution_plan_path,
                self.atlas_path,
                self.visualization_manifest_path,
            ]
        )


def _candidate_dirs(stage2_output_dir: str | Path | None) -> list[tuple[str, Path]]:
    candidates: list[tuple[str, Path]] = []
    if stage2_output_dir:
        candidates.append(("cli_stage2_output_dir", Path(stage2_output_dir)))
    env_dir = os.getenv("STAGE3_STAGE2_OUTPUT_DIR", "").strip()
    if env_dir:
        candidates.append(("env_STAGE3_STAGE2_OUTPUT_DIR", Path(env_dir)))
    candidates.extend(
        [
            ("stage2_statistics_exports", _MAINLINE / "stage2_statistics" / "exports"),
            ("stage3_input", _BASE / "input"),
        ]
    )
    return candidates


def _legacy_paths(input_dir: Path) -> dict[str, Path | None]:
    return {
        "csv_path": input_dir / "s8_input.csv",
        "data_profile_path": input_dir / "data_profile.json",
        "execution_plan_path": input_dir / "execution_plan.json",
        "atlas_path": input_dir / "s8_evidence_atlas.json",
        "visualization_manifest_path": input_dir / "visualization_manifest.json",
    }


def _has_legacy_bundle(input_dir: Path) -> bool:
    return all((input_dir / name).exists() for name in LEGACY_REQUIRED_FILES)


def find_stage1_campaign(input_dir: Path | None = None) -> Path | None:
    """Locate an optional Stage1 campaign file for SystemContext metadata."""
    candidates_explicit: list[Path] = []
    if input_dir is not None:
        candidates_explicit.append(input_dir / "stage1_campaign.json")
    candidates_explicit.extend(
        [
            _BASE / "input" / "stage1_campaign.json",
            _BASE / "data" / "input" / "stage1_campaign.json",
        ]
    )
    for c in candidates_explicit:
        if c.exists():
            return c

    campaigns_dir = _MAINLINE / "stage1_optimization" / "campaigns"
    if campaigns_dir.exists():
        files = sorted(
            campaigns_dir.glob("*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if files:
            return files[0]
    return None


def find_stage3_seed_v2(stage2_output_dir: str | Path | None = None) -> Path | None:
    """Compatibility helper: return the first same-directory V2 seed candidate."""
    for _, input_dir in _candidate_dirs(stage2_output_dir):
        seed = input_dir / "stage3_seed.json"
        if seed.exists():
            return seed
    return None


def resolve_inputs(
    stage2_output_dir: str | Path | None = None,
    allow_legacy_atlas: bool = False,
) -> ResolvedInputs:
    """Resolve Stage3 real inputs from one complete source directory.

    Default real mode is strict: a same-directory ``stage3_seed.json`` is
    required.  Legacy CSV/atlas fallback is only enabled by explicit request.
    """
    searched: list[str] = []
    legacy_candidate: tuple[str, Path] | None = None

    for source, input_dir in _candidate_dirs(stage2_output_dir):
        input_dir = input_dir.resolve()
        searched.append(f"{source}:{input_dir}")
        if not input_dir.exists():
            continue

        seed_path = input_dir / "stage3_seed.json"
        if seed_path.exists():
            paths = _legacy_paths(input_dir)
            return ResolvedInputs(
                input_dir=input_dir,
                **paths,
                stage1_campaign_path=find_stage1_campaign(input_dir),
                stage2_seed_v2_path=seed_path,
                strict_real_input=True,
                allow_legacy_atlas=allow_legacy_atlas,
                input_source=source,
            )

        if _has_legacy_bundle(input_dir) and legacy_candidate is None:
            legacy_candidate = (source, input_dir)

    if allow_legacy_atlas and legacy_candidate is not None:
        source, input_dir = legacy_candidate
        paths = _legacy_paths(input_dir)
        return ResolvedInputs(
            input_dir=input_dir,
            **paths,
            stage1_campaign_path=find_stage1_campaign(input_dir),
            stage2_seed_v2_path=None,
            strict_real_input=False,
            allow_legacy_atlas=True,
            input_source=source,
        )

    hint = (
        "No canonical stage3_seed.json found. Re-run Stage2 so the same output "
        "directory contains stage3_seed.json, or pass --allow-legacy-atlas for "
        "explicit legacy CSV/atlas fallback."
    )
    raise FileNotFoundError(hint + "\nSearched:\n" + "\n".join(searched))
