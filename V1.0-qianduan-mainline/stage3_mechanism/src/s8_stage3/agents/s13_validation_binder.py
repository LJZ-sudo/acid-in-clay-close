"""S13 Validation Binder — 把藕粉/玉米淀粉/壳聚糖实验数据绑定到
S12 已冻结的候选 (P-Stage3-I)。

纯确定性代码。从
    stage3_mechanism/data/validation/biopolymer_validation_results.csv
读取实验记录，自动：
    1. 计算派生配方变量（pure_h3po4_g / dry_matrix_g / 比值等）；
    2. 根据 sample_id / material_system / components 匹配候选；
    3. 根据 preregistered_at vs validation_timing 判定 claim_eligibility。

单向：只能追加到注册表的 validation_record_ids，绝不修改 S09/S10/S12。
"""

from __future__ import annotations

import csv
import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from s8_stage3.contracts.experimental_feedback import ExperimentalFeedback
from s8_stage3.contracts.prospective import ProspectiveCandidateRegistry
from s8_stage3.contracts.validation import (
    CandidateValidationLink,
    DerivedFormulation,
    ValidationBindingReport,
    ValidationRecord,
)
from s8_stage3.io.writers import write_json

logger = logging.getLogger(__name__)


_SIGMA_COLS = [
    "sigma_299k_s_cm",
    "sigma_273k_s_cm",
    "sigma_253k_s_cm",
    "sigma_233k_s_cm",
    "sigma_213k_s_cm",
    "sigma_193k_s_cm",
]


def _to_float_or_none(v) -> Optional[float]:
    if v is None:
        return None
    s = str(v).strip()
    if not s or s.lower() in ("nan", "na", "n/a", "null", "none"):
        return None
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def _to_float_or_zero(v) -> float:
    f = _to_float_or_none(v)
    return f if f is not None else 0.0


def _compute_derived(r: ValidationRecord) -> DerivedFormulation:
    pure_h3po4 = r.h3po4_85wt_g * 0.85 if r.h3po4_85wt_g else 0.0
    water_from_acid = r.h3po4_85wt_g * 0.15 if r.h3po4_85wt_g else 0.0
    dry_matrix = (
        r.lotus_starch_g + r.starch_g + r.chitosan_g + r.pva_g + r.attapulgite_g
    )
    h3po4_to_dry = pure_h3po4 / dry_matrix if dry_matrix > 1e-9 else None
    atta_frac = r.attapulgite_g / dry_matrix if dry_matrix > 1e-9 else None
    biopolymer_mass = r.lotus_starch_g + r.starch_g + r.chitosan_g
    pva_to_bio = r.pva_g / biopolymer_mass if biopolymer_mass > 1e-9 else None
    return DerivedFormulation(
        pure_h3po4_g=round(pure_h3po4, 6) if pure_h3po4 else None,
        water_from_acid_g=round(water_from_acid, 6) if water_from_acid else None,
        dry_matrix_g=round(dry_matrix, 6) if dry_matrix else None,
        h3po4_to_dry_matrix=round(h3po4_to_dry, 6) if h3po4_to_dry is not None else None,
        attapulgite_wt_fraction_dry_matrix=(
            round(atta_frac, 6) if atta_frac is not None else None
        ),
        pva_to_biopolymer=round(pva_to_bio, 6) if pva_to_bio is not None else None,
    )


def _sha256_or_missing(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else "missing"
    except Exception:  # noqa: BLE001
        return "error"


def _parse_iso_datetime(value: str):
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _candidate_by_id(registry: ProspectiveCandidateRegistry, candidate_id: Optional[str]):
    if not candidate_id:
        return None
    return next((c for c in registry.candidates if c.candidate_id == candidate_id), None)


def _candidate_by_instance_id(registry: ProspectiveCandidateRegistry, instance_id: Optional[str]):
    if not instance_id:
        return None
    return next((c for c in registry.candidates if c.instance_id == instance_id), None)


def _load_reference_registry_from_feedback(
    feedback: ExperimentalFeedback,
    feedback_path: Path,
) -> tuple[Optional[ProspectiveCandidateRegistry], Optional[Path], list[str]]:
    warnings: list[str] = []
    raw_path = str((feedback.provenance or {}).get("agent_registry_path") or "").strip()
    if not raw_path:
        return None, None, warnings

    ref_path = Path(raw_path)
    if not ref_path.is_absolute():
        ref_path = feedback_path.parent / ref_path
    if not ref_path.exists():
        warnings.append(f"provenance_registry_missing:{ref_path}")
        return None, ref_path, warnings
    try:
        registry = ProspectiveCandidateRegistry.model_validate(
            json.loads(ref_path.read_text(encoding="utf-8"))
        )
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"provenance_registry_invalid:{ref_path}:{exc}")
        return None, ref_path, warnings
    warnings.append(f"timing_reference_registry:{ref_path}")
    return registry, ref_path, warnings


def _parse_row(row: dict) -> ValidationRecord:
    rec = ValidationRecord(
        validation_id=str(row.get("validation_id", "")).strip() or "VAL-unknown",
        candidate_id=(row.get("candidate_id") or None) or None,
        instance_id=(row.get("instance_id") or None) or None,
        sample_id=str(row.get("sample_id", "")).strip(),
        material_system=str(row.get("material_system", "biopolymer_clay_h3po4")).strip()
        or "biopolymer_clay_h3po4",
        validation_timing=str(row.get("validation_timing", "unknown")).strip() or "unknown",
        measured_at=str(row.get("measured_at", "") or ""),
        lotus_starch_g=_to_float_or_zero(row.get("lotus_starch_g")),
        starch_g=_to_float_or_zero(row.get("starch_g")),
        chitosan_g=_to_float_or_zero(row.get("chitosan_g")),
        pva_g=_to_float_or_zero(row.get("pva_g")),
        attapulgite_g=_to_float_or_zero(row.get("attapulgite_g")),
        h3po4_85wt_g=_to_float_or_zero(row.get("h3po4_85wt_g")),
        water_g=_to_float_or_zero(row.get("water_g")),
        acetic_acid_1wt_g=_to_float_or_zero(row.get("acetic_acid_1wt_g")),
        pva_dissolution_temp_C=_to_float_or_none(row.get("pva_dissolution_temp_C")),
        gelatinization_schedule_C=str(row.get("gelatinization_schedule_C", "") or ""),
        drying_temp_C=_to_float_or_none(row.get("drying_temp_C")),
        seal_pressure_MPa=_to_float_or_none(row.get("seal_pressure_MPa")),
        final_mass_g=_to_float_or_none(row.get("final_mass_g")),
        thickness_cm=_to_float_or_none(row.get("thickness_cm")),
        electrode_area_cm2=_to_float_or_none(row.get("electrode_area_cm2")),
        sigma_299k_s_cm=_to_float_or_none(row.get("sigma_299k_s_cm")),
        sigma_273k_s_cm=_to_float_or_none(row.get("sigma_273k_s_cm")),
        sigma_253k_s_cm=_to_float_or_none(row.get("sigma_253k_s_cm")),
        sigma_233k_s_cm=_to_float_or_none(row.get("sigma_233k_s_cm")),
        sigma_213k_s_cm=_to_float_or_none(row.get("sigma_213k_s_cm")),
        sigma_193k_s_cm=_to_float_or_none(row.get("sigma_193k_s_cm")),
        ea_high_eV=_to_float_or_none(row.get("ea_high_eV")),
        ea_low_eV=_to_float_or_none(row.get("ea_low_eV")),
        t_break_K=_to_float_or_none(row.get("t_break_K")),
        t_arc_K=_to_float_or_none(row.get("t_arc_K")),
        leakage_score=_to_float_or_none(row.get("leakage_score")),
        mass_loss_pct=_to_float_or_none(row.get("mass_loss_pct")),
        notes=str(row.get("notes", "") or ""),
    )
    rec.derived = _compute_derived(rec)
    return rec


def _match_candidate(
    rec: ValidationRecord,
    registry: ProspectiveCandidateRegistry,
    *,
    reference_registry: Optional[ProspectiveCandidateRegistry] = None,
) -> Optional[str]:
    """基于 candidate_id 显式字段 / instance_name 语义匹配。"""
    if rec.candidate_id:
        current = _candidate_by_id(registry, rec.candidate_id)
        if current is not None:
            return current.candidate_id

    # If the record points to an earlier frozen registry, its instance_id is
    # from that registry too. Do semantic remapping into the current rerun
    # instead of treating stale instance ids as direct pointers.
    stale_reference_id = bool(
        rec.candidate_id
        and _candidate_by_id(registry, rec.candidate_id) is None
        and reference_registry is not None
        and _candidate_by_id(reference_registry, rec.candidate_id) is not None
    )
    if rec.instance_id and not stale_reference_id:
        current = _candidate_by_instance_id(registry, rec.instance_id)
        if current is not None:
            return current.candidate_id

    # 语义匹配：判断体系关键词
    rec_text = " ".join([rec.material_system, rec.sample_id, rec.notes]).lower()
    biopolymer_tag = ""
    if rec.lotus_starch_g > 0 or "lotus" in rec_text or "lrs" in rec_text:
        biopolymer_tag = "lotus"
    elif rec.starch_g > 0 or "starch" in rec_text:
        biopolymer_tag = "starch"
    elif rec.chitosan_g > 0 or "chitosan" in rec_text or "chito" in rec_text:
        biopolymer_tag = "chitosan"

    has_h3po4 = rec.h3po4_85wt_g > 0 or "h3po4" in rec_text or "phosphoric" in rec_text
    has_attapulgite = (
        rec.attapulgite_g > 0
        or "attapulgite" in rec_text
        or "1d-clay" in rec_text
        or "1d clay" in rec_text
    )
    has_pva = rec.pva_g > 0 or "pva" in rec_text

    def _score(name: str, components: list[str]) -> float:
        name_bag = name.lower()
        comp_bag = " ".join(components).lower()
        bag = f"{name_bag} {comp_bag}"
        s = 0.0
        if biopolymer_tag == "lotus":
            if "lotus" in name_bag:
                s += 2.8
            elif "starch" in name_bag:
                s += 2.4
            elif "lotus" in comp_bag or "starch" in comp_bag:
                s += 2.0
        if biopolymer_tag == "starch":
            if "starch" in name_bag:
                s += 2.4
            elif "starch" in comp_bag:
                s += 2.0
        if biopolymer_tag == "chitosan":
            if "chitosan" in name_bag:
                s += 3.2
            elif "chitosan" in comp_bag:
                s += 2.2
        if has_pva:
            if "pva" in name_bag:
                s += 0.6
            elif "pva" in comp_bag:
                s += 0.4
        if has_attapulgite and (
            "attapulgite" in name_bag
            or "sepiolite" in name_bag
            or "halloysite" in name_bag
            or "1-d" in name_bag
            or "fibrous clay" in name_bag
            or "nanotube" in name_bag
        ):
            s += 1.2
        elif has_attapulgite and (
            "attapulgite" in comp_bag
            or "sepiolite" in comp_bag
            or "halloysite" in comp_bag
            or "1-d" in comp_bag
            or "fibrous clay" in comp_bag
            or "nanotube" in comp_bag
        ):
            s += 0.8
        if has_h3po4:
            if "h3po4" in name_bag or "phosphoric" in name_bag:
                s += 1.0
            elif "h3po4" in comp_bag or "phosphoric" in comp_bag:
                s += 0.8
        return s

    best_id: Optional[str] = None
    best_score = 0.0
    for c in registry.candidates:
        s = _score(c.instance_name, c.components)
        if s > best_score:
            best_score = s
            best_id = c.candidate_id
    if best_score >= 2.0:
        return best_id
    return None


def _classify_timing(
    rec: ValidationRecord,
    registry: ProspectiveCandidateRegistry,
    candidate_id: Optional[str] = None,
    *,
    reference_registry: Optional[ProspectiveCandidateRegistry] = None,
) -> str:
    preregistered_at = registry.preregistered_at
    if reference_registry is not None:
        ref_cand = _candidate_by_id(reference_registry, rec.candidate_id)
        if ref_cand is None:
            ref_cand = _candidate_by_instance_id(reference_registry, rec.instance_id)
        if ref_cand and ref_cand.preregistered_at:
            preregistered_at = ref_cand.preregistered_at
        elif reference_registry.preregistered_at:
            preregistered_at = reference_registry.preregistered_at

    if candidate_id:
        cand = next((c for c in registry.candidates if c.candidate_id == candidate_id), None)
        if cand and cand.preregistered_at and reference_registry is None:
            preregistered_at = cand.preregistered_at

    measured = _parse_iso_datetime(rec.measured_at)
    frozen = _parse_iso_datetime(preregistered_at)

    if rec.validation_timing == "retrospective":
        return "retrospective"
    if rec.validation_timing == "prospective":
        if measured is not None and frozen is not None and measured > frozen:
            return "prospective"
        return "unknown"
    if measured is not None and frozen is not None:
        return "prospective" if measured > frozen else "retrospective"
    return "retrospective"


def _build_candidate_link(
    candidate_id: str,
    registry: ProspectiveCandidateRegistry,
    bound_records: list[ValidationRecord],
) -> CandidateValidationLink:
    cand = next((c for c in registry.candidates if c.candidate_id == candidate_id), None)
    instance_name = cand.instance_name if cand else ""
    sigmas_299 = [r.sigma_299k_s_cm for r in bound_records if r.sigma_299k_s_cm]
    sigmas_193 = [r.sigma_193k_s_cm for r in bound_records if r.sigma_193k_s_cm]
    any_pros = any(r.validation_timing == "prospective" for r in bound_records)
    any_retro = any(r.validation_timing == "retrospective" for r in bound_records)
    any_unknown = any(r.validation_timing == "unknown" for r in bound_records)

    if any_pros and not any_retro:
        eligibility = "prospective_validation"
    elif any_retro and not any_pros:
        eligibility = "retrospective_validation"
    elif any_pros and any_retro:
        eligibility = "mixed_validation"
    else:
        eligibility = "unvalidated_candidate"
    notes = ""
    if any_unknown:
        notes = (
            "One or more bound records have unknown timing; they do not support "
            "prospective validation claims."
        )

    return CandidateValidationLink(
        candidate_id=candidate_id,
        instance_name=instance_name,
        n_experiments_bound=len(bound_records),
        experiment_ids=[r.validation_id for r in bound_records],
        best_sigma_299k_s_cm=max(sigmas_299) if sigmas_299 else None,
        best_sigma_193k_s_cm=max(sigmas_193) if sigmas_193 else None,
        any_prospective=any_pros,
        any_retrospective=any_retro,
        claim_eligibility=eligibility,
        binding_notes=notes,
    )


def _load_records_from_feedback(feedback_path: Path) -> tuple[list[ValidationRecord], ExperimentalFeedback]:
    raw = json.loads(feedback_path.read_text(encoding="utf-8"))
    feedback = ExperimentalFeedback.model_validate(raw)
    records: list[ValidationRecord] = []
    for rec in feedback.validation_records:
        rec.derived = _compute_derived(rec)
        records.append(rec)
    return records, feedback


def _load_records_from_csv(csv_path: Path) -> list[ValidationRecord]:
    records: list[ValidationRecord] = []
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for raw in reader:
            if not any((v or "").strip() for v in raw.values()):
                continue
            records.append(_parse_row(raw))
    return records


def run_s13(
    registry: ProspectiveCandidateRegistry,
    output_dir: Path,
    settings,
    *,
    feedback_path: Optional[Path] = None,
    csv_path: Optional[Path] = None,
) -> ValidationBindingReport:
    """读取实验 CSV 并绑定到注册表。CSV 不存在则生成空报告。"""
    stage3_root = Path(__file__).parent.parent.parent.parent
    if feedback_path is None:
        feedback_path = stage3_root / "data" / "validation" / "experimental_feedback.json"
    if csv_path is None:
        csv_path = stage3_root / "data" / "validation" / "biopolymer_validation_results.csv"

    binding_path = output_dir / "12_validation_binding" / "validation_binding_report.json"

    source_csv = ""
    source_feedback = ""
    feedback_schema_valid = False
    feedback_warnings: list[str] = []
    input_hashes: dict[str, str] = {}
    reference_registry: Optional[ProspectiveCandidateRegistry] = None

    if feedback_path.exists():
        try:
            records, feedback = _load_records_from_feedback(feedback_path)
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"Invalid experimental feedback JSON at {feedback_path}: {exc}") from exc
        source_feedback = str(feedback_path)
        feedback_schema_valid = True
        input_hashes = dict(feedback.input_hashes)
        input_hashes.setdefault("experimental_feedback.json", _sha256_or_missing(feedback_path))
        reference_registry, reference_registry_path, reference_warnings = _load_reference_registry_from_feedback(
            feedback,
            feedback_path,
        )
        feedback_warnings.extend(reference_warnings)
        if reference_registry_path is not None:
            input_hashes.setdefault(
                "timing_reference_registry",
                _sha256_or_missing(reference_registry_path),
            )
        logger.info("[S13] Loaded %d validation records from %s", len(records), feedback_path)
    elif csv_path.exists():
        records = _load_records_from_csv(csv_path)
        source_csv = str(csv_path)
        input_hashes = {"validation_csv": _sha256_or_missing(csv_path)}
        feedback_warnings.append("experimental_feedback_json_missing_csv_fallback_used")
        logger.info("[S13] Loaded %d validation records from legacy CSV %s", len(records), csv_path)
    else:
        logger.warning(
            "[S13] No experimental feedback JSON or validation CSV found; writing "
            "empty binding report. Populate feedback and re-run S13 to bind experiments."
        )
        empty = ValidationBindingReport(
            run_id=registry.run_id,
            source_csv_path=str(csv_path),
            source_feedback_path=str(feedback_path),
            feedback_schema_valid=False,
            feedback_warnings=["feedback_json_and_csv_missing"],
            n_records=0,
            n_bound=0,
            n_unbound=0,
            records=[],
            candidate_links=[],
            input_hashes={},
            notes="Feedback JSON and CSV missing; run S13 again after populating validation results.",
        )
        write_json(binding_path, empty)
        return empty

    bucket: dict[str, list[ValidationRecord]] = {}
    for rec in records:
        matched_id = _match_candidate(rec, registry, reference_registry=reference_registry)
        if matched_id is None:
            continue
        timing = _classify_timing(
            rec,
            registry,
            matched_id,
            reference_registry=reference_registry,
        )
        rec.candidate_id = matched_id
        rec.validation_timing = timing
        bucket.setdefault(matched_id, []).append(rec)

    links: list[CandidateValidationLink] = [
        _build_candidate_link(cid, registry, recs) for cid, recs in bucket.items()
    ]

    n_bound = sum(len(recs) for recs in bucket.values())
    n_unbound = len(records) - n_bound

    report = ValidationBindingReport(
        run_id=registry.run_id,
        source_csv_path=source_csv,
        source_feedback_path=source_feedback,
        feedback_schema_valid=feedback_schema_valid,
        feedback_warnings=feedback_warnings,
        input_hashes=input_hashes,
        n_records=len(records),
        n_bound=n_bound,
        n_unbound=n_unbound,
        records=records,
        candidate_links=links,
        notes=(
            "Binding is append-only; S13 does not modify S09/S10/S12. "
            f"Registry preregistered_at={registry.preregistered_at}, "
            f"run_id={registry.run_id}."
        ),
    )
    write_json(binding_path, report)

    # 同时把 link 结果回写到 registry 的 validation_record_ids（仅追加字段）
    _append_validation_links(registry, bucket, output_dir)

    logger.info(
        "[S13] Bound %d/%d validation records to %d candidates. "
        "Unbound records: %d.",
        n_bound,
        len(records),
        len(links),
        n_unbound,
    )
    return report


def _append_validation_links(
    registry: ProspectiveCandidateRegistry,
    bucket: dict[str, list[ValidationRecord]],
    output_dir: Path,
) -> None:
    """把 validation_record_ids 追加到 registry 候选中；写入独立文件，
    不覆盖原 prospective_candidates.json（那是冻结文件）。"""
    updated: list[dict] = []
    for c in registry.candidates:
        entry = c.model_dump(mode="json")
        recs = bucket.get(c.candidate_id, [])
        entry["validation_record_ids"] = [r.validation_id for r in recs]
        if recs:
            if any(r.validation_timing == "prospective" for r in recs):
                entry["validation_status"] = "validated_consistent"
            elif any(r.validation_timing == "retrospective" for r in recs):
                entry["validation_status"] = "retrospective_linked"
        updated.append(entry)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    link_path = (
        output_dir
        / "12_validation_binding"
        / f"candidate_validation_link_{ts}.json"
    )
    write_json(
        link_path,
        {
            "registry_run_id": registry.run_id,
            "registry_preregistered_at": registry.preregistered_at,
            "candidates_with_validation": updated,
            "notes": (
                "Append-only view of registry candidates with validation_record_ids "
                "attached. The frozen registry file itself is not modified."
            ),
        },
    )
