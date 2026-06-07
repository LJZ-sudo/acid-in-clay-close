"""Stage2 -> Stage3SeedBundle adapter.

The canonical Stage2 -> Stage3 contract is `stage3_seed.json` (schema 0.2.0).
When that V2 seed is available, it is authoritative: CSV/atlas files are only
diagnostic or legacy fallback inputs and must not override sample, segment, or
evidence data carried by the seed.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from s8_stage3.contracts.seed import (
    SeedAtlasHint,
    SeedCompositionNode,
    SeedSampleSummary,
    SeedSegment,
    Stage3SeedBundle,
    SystemContext,
)


@dataclass
class AdapterWarnings:
    missing_fields: list[str] = field(default_factory=list)
    invalid_values: list[str] = field(default_factory=list)
    atlas_csv_inconsistencies: list[str] = field(default_factory=list)
    unreliable_segments: list[str] = field(default_factory=list)
    t_issues: list[str] = field(default_factory=list)

    def all_warnings(self) -> list[str]:
        return (
            self.missing_fields
            + self.invalid_values
            + self.atlas_csv_inconsistencies
            + self.unreliable_segments
            + self.t_issues
        )

    def to_dict(self) -> dict[str, list[str]]:
        return {
            "missing_fields": self.missing_fields,
            "invalid_values": self.invalid_values,
            "atlas_csv_inconsistencies": self.atlas_csv_inconsistencies,
            "unreliable_segments": self.unreliable_segments,
            "t_arc_t_break_issues": self.t_issues,
        }


def _safe_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return default
    return f if math.isfinite(f) else default


def _safe_int(value: Any, default: int = 0) -> int:
    f = _safe_float(value)
    return int(f) if f is not None else default


def _sha256_file(path: Optional[Path]) -> Optional[str]:
    if path is None or not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json_dict(path: Optional[Path]) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _load_csv_rows(path: Optional[Path]) -> list[dict[str, str]]:
    if path is None or not path.exists():
        return []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _normalize_scan_dir(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in {"heating", "heat", "warming", "up"}:
        return "heating"
    if text in {"cooling", "cool", "down"}:
        return "cooling"
    return "unknown"


def _sigma0_from_ln(value: Any) -> Optional[float]:
    f = _safe_float(value)
    if f is None:
        return None
    try:
        return math.exp(f)
    except OverflowError:
        return None


def _select_items(items: list[dict[str, Any]], sample_ids: Optional[list[str]], max_samples: Optional[int]) -> list[dict[str, Any]]:
    selected = items
    if sample_ids:
        allowed = set(sample_ids)
        selected = [item for item in selected if str(item.get("sample_id") or "") in allowed]
    if max_samples:
        selected = selected[: max(0, int(max_samples))]
    return selected


def _validate_v2_seed(v2: dict[str, Any], strict: bool, warnings: AdapterWarnings) -> None:
    if v2.get("stage3_ready") is not True:
        reason = "; ".join(str(x) for x in (v2.get("stage3_blocking_reasons") or []))
        msg = f"Stage2 V2 seed is not Stage3-ready: {reason or 'stage3_ready is false'}"
        if strict:
            raise RuntimeError(msg)
        warnings.invalid_values.append(msg)

    evidence_units = v2.get("evidence_units") or []
    usable_evidence = [
        ev for ev in evidence_units
        if isinstance(ev, dict) and ev.get("safe_for_stage3") is not False
    ]
    if not usable_evidence:
        msg = "Stage2 V2 seed contains no usable evidence units"
        if strict:
            raise RuntimeError(msg)
        warnings.missing_fields.append(msg)

    missing_rn = [
        str(row.get("sample_id") or f"sample_{idx}")
        for idx, row in enumerate(v2.get("sample_summary") or [])
        if row.get("R") is None or row.get("N") is None
    ]
    if missing_rn:
        msg = "Stage2 V2 seed has samples with missing R/N: " + ",".join(missing_rn)
        if strict:
            raise RuntimeError(msg)
        warnings.missing_fields.append(msg)


def _build_system_context(stage1_campaign_path: Optional[Path]) -> SystemContext:
    campaign = _load_json_dict(stage1_campaign_path)
    if campaign:
        description = (
            campaign.get("description")
            or campaign.get("campaign_name")
            or campaign.get("name")
            or "attapulgite AiCE campaign"
        )
        parameters = campaign.get("parameters") or campaign.get("design_space") or {}
        return SystemContext(
            chemistry_summary=str(description),
            key_variables={
                "R": "campaign composition parameter R",
                "N": "campaign composition parameter N",
                **{str(k): str(v)[:120] for k, v in parameters.items() if isinstance(k, str)},
            },
            provenance=str(stage1_campaign_path),
        )
    return SystemContext(
        chemistry_summary="S8 retrospective acid-in-clay reference evidence",
        key_variables={"R": "composition ratio R", "N": "composition ratio N"},
        provenance="stage2_seed_adapter_default",
    )


def _build_segments_from_v2(v2: dict[str, Any], sample_ids: Optional[list[str]], max_samples: Optional[int]) -> list[SeedSegment]:
    raw_segments = _select_items(v2.get("segment_fits") or [], sample_ids, None)
    if max_samples and sample_ids is None:
        kept_samples = {
            str(row.get("sample_id"))
            for row in (v2.get("sample_summary") or [])[: max(0, int(max_samples))]
        }
        raw_segments = [row for row in raw_segments if str(row.get("sample_id")) in kept_samples]

    segments: list[SeedSegment] = []
    for idx, row in enumerate(raw_segments):
        fit_type = str(row.get("fit_type") or row.get("model") or "arrhenius").lower()
        ln_sigma0 = row.get("arrhenius_ln_sigma0")
        segments.append(
            SeedSegment(
                segment_id=str(row.get("segment_id") or f"{row.get('sample_id', 'sample')}_seg{idx}"),
                sample_id=str(row.get("sample_id") or ""),
                scan_dir=_normalize_scan_dir(row.get("scan_dir")),
                t_min=_safe_float(row.get("T_min_K") or row.get("t_min") or row.get("T_min"), 0.0) or 0.0,
                t_max=_safe_float(row.get("T_max_K") or row.get("t_max") or row.get("T_max"), 0.0) or 0.0,
                n_points=_safe_int(row.get("n_points")),
                representative_ea=_safe_float(
                    row.get("arrhenius_ea_eV")
                    if row.get("arrhenius_ea_eV") is not None
                    else row.get("representative_ea")
                ),
                representative_sigma0=(
                    _safe_float(row.get("arrhenius_sigma0"))
                    if row.get("arrhenius_sigma0") is not None
                    else _sigma0_from_ln(ln_sigma0)
                ),
                segment_order=_safe_int(row.get("segment_order"), idx),
                fit_type=fit_type,
                is_wide_range=bool(row.get("is_wide_range") or (_safe_int(row.get("n_points")) >= 6)),
            )
        )
    return segments


def _build_sample_summaries_from_v2(
    v2: dict[str, Any],
    segments: list[SeedSegment],
    sample_ids: Optional[list[str]],
    max_samples: Optional[int],
) -> list[SeedSampleSummary]:
    raw_samples = _select_items(v2.get("sample_summary") or [], sample_ids, max_samples)
    segment_ids_by_sample: dict[str, list[str]] = {}
    scan_dirs_by_sample: dict[str, set[str]] = {}
    for seg in segments:
        segment_ids_by_sample.setdefault(seg.sample_id, []).append(seg.segment_id)
        scan_dirs_by_sample.setdefault(seg.sample_id, set()).add(seg.scan_dir)

    summaries: list[SeedSampleSummary] = []
    for row in raw_samples:
        sample_id = str(row.get("sample_id") or "")
        r = _safe_float(row.get("R"))
        n = _safe_float(row.get("N"))
        if r is None or n is None:
            continue
        summaries.append(
            SeedSampleSummary(
                sample_id=sample_id,
                composition_r=r,
                composition_n=n,
                scan_dirs=sorted(scan_dirs_by_sample.get(sample_id, set())),
                t_break_k=_safe_float(row.get("T_break") or row.get("t_break_k") or row.get("T_break_K")),
                t_arc_k=_safe_float(row.get("T_arc") or row.get("t_arc_k") or row.get("T_arc_K")),
                has_eis_feature=bool(row.get("has_eis_feature") or segment_ids_by_sample.get(sample_id)),
                conductivity_trend=str(row.get("conductivity_trend") or row.get("composition_trend") or ""),
                segment_ids=segment_ids_by_sample.get(sample_id, []),
            )
        )
    return summaries


def _build_composition_nodes(summaries: list[SeedSampleSummary]) -> list[SeedCompositionNode]:
    buckets: dict[tuple[float, float], list[SeedSampleSummary]] = {}
    for summary in summaries:
        buckets.setdefault(
            (round(summary.composition_r, 8), round(summary.composition_n, 8)),
            [],
        ).append(summary)

    nodes: list[SeedCompositionNode] = []
    for idx, ((r, n), rows) in enumerate(sorted(buckets.items()), start=1):
        scan_dirs = sorted({d for row in rows for d in row.scan_dirs if d})
        nodes.append(
            SeedCompositionNode(
                node_id=f"CN-{idx:03d}",
                r=r,
                n=n,
                sample_ids=[row.sample_id for row in rows],
                sample_count=len(rows),
                available_scan_dirs=scan_dirs,
            )
        )
    return nodes


def _build_atlas_hints(atlas: dict[str, Any]) -> list[SeedAtlasHint]:
    raw_items: list[dict[str, Any]] = []
    for key in ("evidence_cards", "cards", "atlas_hints", "items"):
        value = atlas.get(key)
        if isinstance(value, list):
            raw_items = [x for x in value if isinstance(x, dict)]
            break
    hints: list[SeedAtlasHint] = []
    for idx, item in enumerate(raw_items[:50], start=1):
        statement = (
            item.get("statement")
            or item.get("claim")
            or item.get("text")
            or item.get("title")
            or ""
        )
        if not statement:
            continue
        claim_level = str(item.get("claim_level") or item.get("type") or "observation")
        if claim_level not in {"observation", "interpretation", "question"}:
            claim_level = "observation"
        hints.append(
            SeedAtlasHint(
                hint_id=str(item.get("hint_id") or item.get("card_id") or f"AH-{idx:03d}"),
                claim_level=claim_level,
                theme=str(item.get("theme") or item.get("title") or ""),
                statement=str(statement),
                confidence=_safe_float(item.get("confidence"), 0.5) or 0.5,
                tags=[str(t) for t in (item.get("tags") or [])],
                support_metrics=item.get("support_metrics") or {},
                usage_policy="allowed_as_context_only",
            )
        )
    return hints


def _build_seed_bundle_from_v2(
    *,
    stage2_seed_v2: dict[str, Any],
    stage2_seed_v2_path: Optional[Path],
    csv_path: Optional[Path],
    data_profile_path: Optional[Path],
    execution_plan_path: Optional[Path],
    atlas_path: Optional[Path],
    visualization_manifest_path: Optional[Path],
    max_samples: Optional[int],
    sample_ids: Optional[list[str]],
    stage1_campaign_path: Optional[Path],
    warnings: AdapterWarnings,
) -> tuple[Stage3SeedBundle, dict[str, Any]]:
    segments = _build_segments_from_v2(stage2_seed_v2, sample_ids, max_samples)
    summaries = _build_sample_summaries_from_v2(stage2_seed_v2, segments, sample_ids, max_samples)
    nodes = _build_composition_nodes(summaries)
    atlas = _load_json_dict(atlas_path)

    diagnostics = {
        "input_mode": "stage2_seed_v2",
        "stage2_seed_v2_path": str(stage2_seed_v2_path) if stage2_seed_v2_path else None,
        "stage2_seed_v2_sha256": _sha256_file(stage2_seed_v2_path),
        "stage2_seed_v2_id": stage2_seed_v2.get("seed_id"),
        "stage2_seed_v2_stage3_ready": stage2_seed_v2.get("stage3_ready"),
        "stage2_seed_v2_blocking_reasons": stage2_seed_v2.get("stage3_blocking_reasons") or [],
        "sample_count": len(summaries),
        "segment_count": len(segments),
        "composition_node_count": len(nodes),
        "evidence_unit_count": len(stage2_seed_v2.get("evidence_units") or []),
        "input_hashes": {
            "stage2_seed_v2": _sha256_file(stage2_seed_v2_path),
            "csv": _sha256_file(csv_path),
            "data_profile": _sha256_file(data_profile_path),
            "execution_plan": _sha256_file(execution_plan_path),
            "atlas": _sha256_file(atlas_path),
            "visualization_manifest": _sha256_file(visualization_manifest_path),
        },
        "warnings": warnings.to_dict(),
    }
    bundle = Stage3SeedBundle(
        bundle_id=str(stage2_seed_v2.get("seed_id") or f"stage2-v2-{uuid.uuid4().hex[:8]}"),
        source_mode="real",
        seed_segments=segments,
        seed_sample_summaries=summaries,
        seed_composition_nodes=nodes,
        seed_atlas_hints=_build_atlas_hints(atlas),
        upstream_facts={
            "input_mode": "stage2_seed_v2",
            "stage3_ready": stage2_seed_v2.get("stage3_ready"),
            "stage3_blocking_reasons": stage2_seed_v2.get("stage3_blocking_reasons") or [],
            "input_hashes": stage2_seed_v2.get("input_hashes") or {},
        },
        system_context=_build_system_context(stage1_campaign_path),
        adapter_warnings=warnings.all_warnings(),
        stage2_seed_v2=stage2_seed_v2,
        stage2_seed_v2_path=str(stage2_seed_v2_path) if stage2_seed_v2_path else None,
    )
    return bundle, diagnostics


def _build_seed_bundle_from_legacy(
    *,
    csv_path: Optional[Path],
    atlas_path: Optional[Path],
    stage1_campaign_path: Optional[Path],
    warnings: AdapterWarnings,
) -> tuple[Stage3SeedBundle, dict[str, Any]]:
    rows = _load_csv_rows(csv_path)
    by_sample: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        sample_id = str(row.get("sample_id") or row.get("Sample") or "").strip()
        if not sample_id:
            continue
        by_sample.setdefault(sample_id, []).append(row)

    segments: list[SeedSegment] = []
    summaries: list[SeedSampleSummary] = []
    for idx, (sample_id, sample_rows) in enumerate(by_sample.items(), start=1):
        first = sample_rows[0]
        r = _safe_float(first.get("R"))
        n = _safe_float(first.get("N"))
        if r is None or n is None:
            warnings.missing_fields.append(f"legacy sample missing R/N: {sample_id}")
            continue
        temps = [
            _safe_float(row.get("T_K") or row.get("T") or row.get("temperature_K"))
            for row in sample_rows
        ]
        temps = [t for t in temps if t is not None]
        seg_id = f"{sample_id}_legacy_seg0"
        segments.append(
            SeedSegment(
                segment_id=seg_id,
                sample_id=sample_id,
                scan_dir=_normalize_scan_dir(first.get("scan_dir")),
                t_min=min(temps) if temps else 0.0,
                t_max=max(temps) if temps else 0.0,
                n_points=len(temps),
                representative_ea=_safe_float(first.get("Ea") or first.get("ea_eV")),
                fit_type="legacy",
                is_wide_range=len(temps) >= 6,
            )
        )
        summaries.append(
            SeedSampleSummary(
                sample_id=sample_id,
                composition_r=r,
                composition_n=n,
                scan_dirs=[segments[-1].scan_dir],
                has_eis_feature=True,
                segment_ids=[seg_id],
            )
        )

    atlas = _load_json_dict(atlas_path)
    nodes = _build_composition_nodes(summaries)
    diagnostics = {
        "input_mode": "legacy_csv_atlas",
        "sample_count": len(summaries),
        "segment_count": len(segments),
        "composition_node_count": len(nodes),
        "input_hashes": {
            "csv": _sha256_file(csv_path),
            "atlas": _sha256_file(atlas_path),
        },
        "warnings": warnings.to_dict(),
    }
    bundle = Stage3SeedBundle(
        bundle_id=f"legacy-{uuid.uuid4().hex[:8]}",
        source_mode="real",
        seed_segments=segments,
        seed_sample_summaries=summaries,
        seed_composition_nodes=nodes,
        seed_atlas_hints=_build_atlas_hints(atlas),
        upstream_facts={"input_mode": "legacy_csv_atlas"},
        system_context=_build_system_context(stage1_campaign_path),
        adapter_warnings=warnings.all_warnings(),
    )
    return bundle, diagnostics


def build_seed_bundle_from_stage2(
    csv_path: Optional[Path],
    data_profile_path: Optional[Path],
    execution_plan_path: Optional[Path],
    atlas_path: Optional[Path],
    visualization_manifest_path: Optional[Path] = None,
    *,
    max_samples: Optional[int] = None,
    sample_ids: Optional[list[str]] = None,
    stage1_campaign_path: Optional[Path] = None,
    stage2_seed_v2_path: Optional[Path] = None,
    strict_real_input: bool = True,
    allow_legacy_atlas: bool = False,
) -> tuple[Stage3SeedBundle, dict[str, Any]]:
    warnings = AdapterWarnings()
    csv_path = Path(csv_path) if csv_path else None
    data_profile_path = Path(data_profile_path) if data_profile_path else None
    execution_plan_path = Path(execution_plan_path) if execution_plan_path else None
    atlas_path = Path(atlas_path) if atlas_path else None
    visualization_manifest_path = (
        Path(visualization_manifest_path) if visualization_manifest_path else None
    )
    stage1_campaign_path = Path(stage1_campaign_path) if stage1_campaign_path else None
    stage2_seed_v2_path = Path(stage2_seed_v2_path) if stage2_seed_v2_path else None

    stage2_seed_v2 = _load_json_dict(stage2_seed_v2_path)
    if stage2_seed_v2:
        _validate_v2_seed(stage2_seed_v2, strict_real_input, warnings)
        return _build_seed_bundle_from_v2(
            stage2_seed_v2=stage2_seed_v2,
            stage2_seed_v2_path=stage2_seed_v2_path,
            csv_path=csv_path,
            data_profile_path=data_profile_path,
            execution_plan_path=execution_plan_path,
            atlas_path=atlas_path,
            visualization_manifest_path=visualization_manifest_path,
            max_samples=max_samples,
            sample_ids=sample_ids,
            stage1_campaign_path=stage1_campaign_path,
            warnings=warnings,
        )

    if strict_real_input and not allow_legacy_atlas:
        raise RuntimeError(
            "No canonical stage3_seed.json was provided. Re-run Stage2 or pass "
            "--allow-legacy-atlas for explicit legacy fallback."
        )
    return _build_seed_bundle_from_legacy(
        csv_path=csv_path,
        atlas_path=atlas_path,
        stage1_campaign_path=stage1_campaign_path,
        warnings=warnings,
    )
