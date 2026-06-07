"""S02 seed-builder helper for explicit legacy/source-audit runs.

The current executable Stage3 chain builds its seed directly in
``Pipeline.run_real`` from ``stage2_seed_adapter``. This helper remains as a
small wrapper for manual S01/S02-style audits and writes the same seed bundle
artifacts as the main pipeline.
"""
from __future__ import annotations

from pathlib import Path

from s8_stage3.adapters.stage2_seed_adapter import build_seed_bundle_from_stage2
from s8_stage3.io.writers import write_json


def run_s02(
    csv_path: Path,
    data_profile_path: Path,
    execution_plan_path: Path,
    atlas_path: Path,
    visualization_manifest_path: Path,
    output_dir: Path,
    max_samples: int | None = None,
    sample_ids: list[str] | None = None,
    stage1_campaign_path: Path | None = None,
    stage2_seed_v2_path: Path | None = None,
    strict_real_input: bool = True,
    allow_legacy_atlas: bool = False,
):
    """Build and persist a Stage3 seed bundle from Stage2 artifacts."""
    output_dir = Path(output_dir)
    bundle, diagnostics = build_seed_bundle_from_stage2(
        csv_path=csv_path,
        data_profile_path=data_profile_path,
        execution_plan_path=execution_plan_path,
        atlas_path=atlas_path,
        visualization_manifest_path=visualization_manifest_path,
        max_samples=max_samples,
        sample_ids=sample_ids,
        stage1_campaign_path=stage1_campaign_path,
        stage2_seed_v2_path=stage2_seed_v2_path,
        strict_real_input=strict_real_input,
        allow_legacy_atlas=allow_legacy_atlas,
    )

    seed_dir = output_dir / "00_seed_real"
    write_json(seed_dir / "seed_bundle_real.json", bundle)
    write_json(seed_dir / "real_seed_diagnostics.json", diagnostics)
    write_json(seed_dir / "adapter_warnings.json", {"warnings": bundle.adapter_warnings})
    return bundle
