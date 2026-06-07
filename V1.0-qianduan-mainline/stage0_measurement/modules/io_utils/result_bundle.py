"""Stage0 每样品 result bundle 聚合层 (P-Stage0-A)。

不替换底层 EIS / Arrhenius 算法，而是把每个样品下所有 scan 的：
    aggregated_results.json
    arrhenius_analysis.json
    eis_features.json
统一聚合为单个 Pydantic 模型 ``Stage0ResultBundle``，并写出
``output/stage0_results/<sample_id>/stage0_result_bundle.json``。

设计要点：
    - 每个 EIS 测量点输出 (T_K, rb_ohm, rb_method, rb_confidence, sigma_S_cm,
      kk_residual, kk_warning, arc_visible, semicircle_visible,
      characteristic_frequency, peak_neg_zimag_ohm, quality_flags[]).
    - 温度程序由 scan 名解析 (`300-120K 3K-min`) 并叠加每个 EIS 点的实际 T_K
      统计 mean/std。
    - 文件级 sha256 写入 file_hashes，方便后续做 closed_loop_metrics 复现。
    - 当源 JSON 字段缺失时不引发异常，而是用 None / quality_flags 标注。
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Pydantic schema
# ---------------------------------------------------------------------------

class TempProgram(BaseModel):
    scan_dir: str
    T_start_K: Optional[float] = None
    T_end_K: Optional[float] = None
    rate_K_per_min: Optional[float] = None
    is_heating: Optional[bool] = None
    T_actual_mean_K: List[float] = Field(default_factory=list)
    T_actual_std_K: List[float] = Field(default_factory=list)
    T_actual_K: List[float] = Field(default_factory=list)


class EISPoint(BaseModel):
    scan_dir: str
    T_K: float
    T_C: Optional[float] = None
    status: str = "OK"
    rb_ohm: Optional[float] = None
    rb_method: Optional[str] = None
    # rb_confidence: legacy numeric goodness value. Tier2 keeps it for
    # backward-compat but ALWAYS pairs it with rb_confidence_basis so a reader
    # knows what it actually means (e.g. "arc_fit_r2") instead of mistaking it
    # for a calibrated probability.
    rb_confidence: Optional[float] = None
    rb_confidence_basis: Optional[str] = None
    sigma_S_cm: Optional[float] = None
    kk_warning: Optional[bool] = None
    # kk_residual: numeric Kramers-Kronig residual (median |residual|, the same
    # mu_median that validate_kk_consistency uses for its pass/fail decision).
    # None means the source measurement predates Tier2 residual propagation
    # (legacy bundles only carried the kk_warning bool).
    kk_residual: Optional[float] = None
    kk_residual_metric: Optional[str] = None
    kk_mu_rmse: Optional[float] = None
    kk_mu_max: Optional[float] = None
    kk_score: Optional[float] = None
    kk_passed: Optional[bool] = None
    kk_threshold: Optional[float] = None
    arc_visible: Optional[bool] = None
    semicircle_visible: Optional[bool] = None
    characteristic_frequency_Hz: Optional[float] = None
    peak_neg_zimag_ohm: Optional[float] = None
    nyquist_peak_ratio: Optional[float] = None
    R_high_freq_ohm: Optional[float] = None
    R_low_freq_ohm: Optional[float] = None
    quality_flags: List[str] = Field(default_factory=list)


class ArrheniusSummary(BaseModel):
    success: bool = False
    best_model_type: Optional[str] = None
    n_segments: int = 0
    transition_temps_K: List[float] = Field(default_factory=list)
    ea_segments_eV: List[float] = Field(default_factory=list)
    ea_single_eV: Optional[float] = None
    ea_high_eV: Optional[float] = None
    ea_low_eV: Optional[float] = None
    t_break_K: Optional[float] = None
    confidence: Optional[float] = None
    fit_quality_flags: List[str] = Field(default_factory=list)


class Recipe(BaseModel):
    R: Optional[float] = None
    N: Optional[float] = None
    acid_type: str = "H3PO4"
    clay_type: str = "sepiolite"
    excel_id: Optional[str] = None


class Geometry(BaseModel):
    area_cm2: Optional[float] = None
    thickness_cm: Optional[float] = None


class BundleMeta(BaseModel):
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    source_scan_dirs: List[str] = Field(default_factory=list)
    legacy_pipeline_version: str = "stage0_offline_v2.0_eis_v4.0"
    stage0_bundle_schema_version: str = "0.1.0"


class Stage0ResultBundle(BaseModel):
    sample_id: str
    material_system: str = "acid_in_clay"
    recipe: Recipe = Field(default_factory=Recipe)
    geometry: Geometry = Field(default_factory=Geometry)
    temperature_program: List[TempProgram] = Field(default_factory=list)
    eis_points: List[EISPoint] = Field(default_factory=list)
    arrhenius: ArrheniusSummary = Field(default_factory=ArrheniusSummary)
    file_hashes: Dict[str, str] = Field(default_factory=dict)
    bundle_meta: BundleMeta = Field(default_factory=BundleMeta)
    limitations: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SCAN_PATTERN = re.compile(
    r"(?P<start>\d+)\s*-\s*(?P<end>\d+)\s*K\s*(?P<rate>\d+(?:\.\d+)?)\s*K[-\s]*min",
    re.IGNORECASE,
)


def _safe_float(v) -> Optional[float]:
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return f


def _parse_scan_dir(name: str) -> Dict[str, Optional[float]]:
    m = _SCAN_PATTERN.search(name)
    if not m:
        return {"T_start_K": None, "T_end_K": None, "rate_K_per_min": None, "is_heating": None}
    start = float(m.group("start"))
    end = float(m.group("end"))
    rate = float(m.group("rate"))
    return {
        "T_start_K": start,
        "T_end_K": end,
        "rate_K_per_min": rate,
        "is_heating": start < end,
    }


def _sha256(p: Path) -> Optional[str]:
    if not p.exists() or not p.is_file():
        return None
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_json(p: Path) -> Optional[dict]:
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


class _KKResidual(BaseModel):
    """已抽取的数值 KK 残差视图（None 值表示该来源记录未携带数值残差）。"""

    residual: Optional[float] = None
    metric: Optional[str] = None
    mu_rmse: Optional[float] = None
    mu_max: Optional[float] = None
    score: Optional[float] = None
    passed: Optional[bool] = None
    threshold: Optional[float] = None
    is_numeric: bool = False


def _extract_kk_residual(meas: dict) -> Tuple[_KKResidual, List[str]]:
    """从 measurement 记录抽取数值 KK 残差。

    Tier2 (2026-06-01): 优先读取由升级后 offline pipeline 落盘的数值字段
    (``kk_mu_median`` 等，或嵌套的 ``kk_result`` dict)。若都不存在，则说明该
    记录由旧 pipeline 产出（仅有 ``kk_warning`` bool），返回 is_numeric=False 并
    打 legacy flag —— 绝不伪造数值，保持 ``kk_residual=None`` 的诚实状态。
    """
    flags: List[str] = []

    # 兼容两种来源：扁平字段 或 嵌套 kk_result。
    nested = meas.get("kk_result") if isinstance(meas.get("kk_result"), dict) else {}

    def _pick(key: str):
        if meas.get(key) is not None:
            return meas.get(key)
        return nested.get(key.replace("kk_", "")) if nested else None

    mu_median = _safe_float(_pick("kk_mu_median"))
    if mu_median is None and nested:
        mu_median = _safe_float(nested.get("mu_median"))

    if mu_median is None:
        # 旧 pipeline：无数值残差。
        if meas.get("kk_warning"):
            flags.append("kk_warning_set_by_legacy_pipeline")
        flags.append("kk_residual_unavailable_legacy_record")
        return _KKResidual(is_numeric=False), flags

    res = _KKResidual(
        residual=mu_median,
        metric="mu_median_linKK",
        mu_rmse=_safe_float(_pick("kk_mu_rmse")) if _pick("kk_mu_rmse") is not None else _safe_float(nested.get("mu_rmse")),
        mu_max=_safe_float(_pick("kk_mu_max")) if _pick("kk_mu_max") is not None else _safe_float(nested.get("mu_max")),
        score=_safe_float(_pick("kk_score")) if _pick("kk_score") is not None else _safe_float(nested.get("score")),
        passed=(bool(_pick("kk_passed")) if _pick("kk_passed") is not None else (bool(nested.get("passed")) if nested.get("passed") is not None else None)),
        threshold=_safe_float(_pick("kk_threshold")) if _pick("kk_threshold") is not None else _safe_float((nested.get("details") or {}).get("threshold")),
        is_numeric=True,
    )
    if meas.get("kk_warning"):
        flags.append("kk_warning_set")
    return res, flags


def _resolve_rb_confidence(meas: dict) -> Tuple[Optional[float], Optional[str], List[str]]:
    """解析 rb_confidence 并标注其口径（可解释性，issue 10）。

    返回 (value, basis, flags)。当前 offline pipeline 把 ``fit_quality``（弧拟合
    R²）作为 rb 置信度，这本身没问题，但若不标注口径，读者会误以为它是经过校准的
    概率。这里始终附带 basis 标签，并在沿用 R² 代理时打一个显式 flag。
    """
    flags: List[str] = []
    basis = meas.get("rb_confidence_basis")
    val = _safe_float(meas.get("rb_confidence"))
    if val is None:
        val = _safe_float(meas.get("fit_quality"))
        if val is not None:
            basis = basis or "arc_fit_r2"
    if basis == "arc_fit_r2":
        flags.append("rb_confidence_is_arc_fit_r2_proxy")
    return val, basis, flags


def _eis_feature_index(eis_data: Optional[dict]) -> Dict[float, dict]:
    if not eis_data:
        return {}
    out: Dict[float, dict] = {}
    for f in eis_data.get("features_by_temperature", []) or []:
        T = _safe_float(f.get("temperature_K"))
        if T is not None:
            out[round(T, 3)] = f
    return out


# ---------------------------------------------------------------------------
# Per-scan extraction
# ---------------------------------------------------------------------------

def _build_eis_points_for_scan(
    scan_dir_name: str,
    aggregated: dict,
    eis_features: Optional[dict],
) -> Tuple[List[EISPoint], List[float], List[str]]:
    """从 aggregated_results.json + eis_features.json 拼出该 scan 的所有 EISPoint。"""
    points: List[EISPoint] = []
    actual_T_K: List[float] = []
    flags: List[str] = []

    feature_index = _eis_feature_index(eis_features)
    for meas in aggregated.get("measurements", []) or []:
        T_K = _safe_float(meas.get("temperature_K"))
        if T_K is None:
            continue
        actual_T_K.append(T_K)

        kk, kk_flags = _extract_kk_residual(meas)
        rb_conf, rb_basis, rb_flags = _resolve_rb_confidence(meas)
        feat = feature_index.get(round(T_K, 3))
        point_flags: List[str] = list(kk_flags) + list(rb_flags)
        if meas.get("status") and meas["status"] != "OK":
            point_flags.append(f"status:{meas['status']}")
        if not meas.get("success", True):
            point_flags.append("legacy_failure")
        if feat is not None and not feat.get("data_valid", True):
            point_flags.append("data_invalid")

        rb = _safe_float(meas.get("rb_ohm"))
        sigma = _safe_float(meas.get("conductivity_S_per_cm"))

        points.append(
            EISPoint(
                scan_dir=scan_dir_name,
                T_K=T_K,
                T_C=_safe_float(meas.get("temperature_C")),
                status=str(meas.get("status") or "OK"),
                rb_ohm=rb,
                rb_method=(meas.get("rb_method") or None),
                rb_confidence=rb_conf,
                rb_confidence_basis=rb_basis,
                sigma_S_cm=sigma,
                kk_warning=bool(meas.get("kk_warning")) if meas.get("kk_warning") is not None else None,
                kk_residual=kk.residual,
                kk_residual_metric=kk.metric,
                kk_mu_rmse=kk.mu_rmse,
                kk_mu_max=kk.mu_max,
                kk_score=kk.score,
                kk_passed=kk.passed,
                kk_threshold=kk.threshold,
                arc_visible=(bool(feat["arc_visible"]) if feat and feat.get("arc_visible") is not None else None),
                semicircle_visible=(
                    bool(feat["semicircle_visible"]) if feat and feat.get("semicircle_visible") is not None else None
                ),
                characteristic_frequency_Hz=_safe_float(feat.get("characteristic_frequency")) if feat else None,
                peak_neg_zimag_ohm=_safe_float(feat.get("peak_neg_zimag_ohm")) if feat else None,
                nyquist_peak_ratio=_safe_float(feat.get("nyquist_peak_ratio")) if feat else None,
                R_high_freq_ohm=_safe_float(feat.get("R_high_freq_ohm")) if feat else None,
                R_low_freq_ohm=_safe_float(feat.get("R_low_freq_ohm")) if feat else None,
                quality_flags=point_flags,
            )
        )

    return points, actual_T_K, flags


def _build_arrhenius_summary(arr_data: Optional[dict]) -> ArrheniusSummary:
    if not arr_data:
        return ArrheniusSummary(success=False)
    success = bool(arr_data.get("success"))
    if not success:
        return ArrheniusSummary(success=False)

    segments = arr_data.get("segments") or []
    eas: List[float] = []
    for seg in segments:
        ea = _safe_float(seg.get("Ea_eV"))
        if ea is not None:
            eas.append(ea)

    transitions = [
        _safe_float(t) for t in (arr_data.get("transition_temps_K") or []) if _safe_float(t) is not None
    ]
    transitions = [t for t in transitions if t is not None]  # type: ignore[list-item]

    flags: List[str] = []
    if not eas:
        flags.append("no_segment_ea_extracted")

    summary = ArrheniusSummary(
        success=True,
        best_model_type=arr_data.get("best_model_type"),
        n_segments=int(arr_data.get("n_segments", len(segments))),
        transition_temps_K=transitions,  # type: ignore[arg-type]
        ea_segments_eV=eas,
        ea_single_eV=eas[0] if len(eas) == 1 else None,
        ea_high_eV=eas[0] if len(eas) >= 2 else None,
        ea_low_eV=eas[-1] if len(eas) >= 2 else None,
        t_break_K=transitions[0] if transitions else None,  # type: ignore[index]
        confidence=_safe_float(arr_data.get("confidence")),
        fit_quality_flags=flags,
    )
    return summary


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_bundle_for_sample(
    sample_dir: Path,
    sample_id: str,
    rn_info: Optional[dict] = None,
) -> Stage0ResultBundle:
    """聚合一个样品下所有 scan 的输出为 Stage0ResultBundle。"""
    rn_info = rn_info or {}
    bundle = Stage0ResultBundle(
        sample_id=sample_id,
        recipe=Recipe(
            R=_safe_float(rn_info.get("R")),
            N=_safe_float(rn_info.get("N")),
            excel_id=rn_info.get("excel_sample_id") or rn_info.get("excel_id"),
        ),
        geometry=Geometry(
            area_cm2=_safe_float(rn_info.get("S_cm2")),
            thickness_cm=_safe_float(rn_info.get("L_cm")),
        ),
    )

    file_hashes: Dict[str, str] = {}
    source_scans: List[str] = []
    arrhenius_collected: Optional[ArrheniusSummary] = None
    sample_limitations: List[str] = []

    for scan_dir in sorted([d for d in sample_dir.iterdir() if d.is_dir()]):
        agg_p = scan_dir / "aggregated_results.json"
        arr_p = scan_dir / "arrhenius_analysis.json"
        eis_p = scan_dir / "eis_features.json"

        agg = _read_json(agg_p)
        if agg is None:
            sample_limitations.append(f"scan {scan_dir.name}: aggregated_results.json missing or invalid")
            continue

        arr = _read_json(arr_p)
        eis = _read_json(eis_p)

        scan_meta = _parse_scan_dir(scan_dir.name)
        points, actual_T, _ = _build_eis_points_for_scan(scan_dir.name, agg, eis)

        if actual_T:
            mean_T = sum(actual_T) / len(actual_T)
            std_T = (sum((t - mean_T) ** 2 for t in actual_T) / len(actual_T)) ** 0.5
        else:
            mean_T, std_T = None, None

        bundle.temperature_program.append(
            TempProgram(
                scan_dir=scan_dir.name,
                T_start_K=scan_meta["T_start_K"],
                T_end_K=scan_meta["T_end_K"],
                rate_K_per_min=scan_meta["rate_K_per_min"],
                is_heating=scan_meta["is_heating"],
                T_actual_mean_K=[mean_T] if mean_T is not None else [],
                T_actual_std_K=[std_T] if std_T is not None else [],
                T_actual_K=actual_T,
            )
        )
        bundle.eis_points.extend(points)
        source_scans.append(scan_dir.name)

        h_agg = _sha256(agg_p)
        h_arr = _sha256(arr_p)
        h_eis = _sha256(eis_p)
        if h_agg:
            file_hashes[f"{scan_dir.name}/aggregated_results.json"] = h_agg
        if h_arr:
            file_hashes[f"{scan_dir.name}/arrhenius_analysis.json"] = h_arr
        if h_eis:
            file_hashes[f"{scan_dir.name}/eis_features.json"] = h_eis

        if arr is not None and arrhenius_collected is None:
            arrhenius_collected = _build_arrhenius_summary(arr)

    if arrhenius_collected is not None:
        bundle.arrhenius = arrhenius_collected

    bundle.file_hashes = file_hashes
    bundle.bundle_meta.source_scan_dirs = source_scans

    # Tier2 (2026-06-01): limitations 改为「按实际数据动态生成」，不再写死。
    n_points = len(bundle.eis_points)
    n_numeric_kk = sum(1 for p in bundle.eis_points if p.kk_residual is not None)
    n_rb_proxy = sum(1 for p in bundle.eis_points if p.rb_confidence_basis == "arc_fit_r2")

    dynamic_limitations: List[str] = []
    if n_points == 0:
        pass
    elif n_numeric_kk == 0:
        dynamic_limitations.append(
            "kk_residual is None for all points: source measurements predate Tier2 numerical "
            "KK residual propagation (legacy pipeline only emitted a kk_warning bool). "
            "Re-process the raw EIS through the upgraded offline pipeline to populate mu_median."
        )
    elif n_numeric_kk < n_points:
        dynamic_limitations.append(
            f"kk_residual present for {n_numeric_kk}/{n_points} points; the remainder are legacy "
            "records without a numerical residual."
        )
    if n_rb_proxy > 0:
        dynamic_limitations.append(
            f"rb_confidence for {n_rb_proxy}/{n_points} points is an arc-fit R^2 proxy "
            "(rb_confidence_basis='arc_fit_r2'), NOT a calibrated probability; read it as fit goodness only."
        )
    bundle.limitations = sample_limitations + dynamic_limitations
    return bundle


def write_bundle(bundle: Stage0ResultBundle, sample_dir: Path) -> Path:
    out_path = sample_dir / "stage0_result_bundle.json"
    out_path.write_text(bundle.model_dump_json(indent=2), encoding="utf-8")
    return out_path


def build_all_bundles(
    stage0_results_dir: Path,
    rn_mapping_path: Optional[Path] = None,
) -> List[Tuple[str, Path, Stage0ResultBundle]]:
    """批量遍历 stage0_results_dir 下的所有样品文件夹生成 bundle。"""
    rn_index: Dict[str, dict] = {}
    if rn_mapping_path is not None and rn_mapping_path.exists():
        try:
            data = json.loads(rn_mapping_path.read_text(encoding="utf-8"))
            for s in data.get("samples", []) or []:
                folder = s.get("result_folder")
                if folder:
                    rn_index[folder] = s
        except Exception:
            pass

    out: List[Tuple[str, Path, Stage0ResultBundle]] = []
    for sample_dir in sorted([d for d in stage0_results_dir.iterdir() if d.is_dir() and d.name.startswith("S8-")]):
        sample_id = sample_dir.name
        bundle = build_bundle_for_sample(sample_dir, sample_id, rn_index.get(sample_id))
        out_path = write_bundle(bundle, sample_dir)
        out.append((sample_id, out_path, bundle))
    return out
