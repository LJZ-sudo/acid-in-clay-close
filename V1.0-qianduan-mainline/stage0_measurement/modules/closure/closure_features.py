"""Deterministic feature extraction for the Sample Closure Card.

All numeric fields and code-driven flags of a SampleClosureReport are filled
here.  The LLM never sees the raw bundle directly; it only sees the trimmed
prompt context produced by `build_prompt_context`.
"""

from __future__ import annotations

import math
import statistics
from typing import Any, Dict, List, Optional, Tuple

from .closure_schema import (
    ArrheniusSegmentRow,
    CampaignComparisonLite,
    CampaignContextLite,
    DRTPeak,
    PerformanceCard,
    PhaseTransitionInterp,
    PhaseTransitionType,
    QualityCard,
    RiskCode,
    RiskFlag,
    SampleIdentity,
    UserPrepForm,
)


_KB_J = 1.380649e-23
_EV_J = 1.602176634e-19
_NA = 6.02214076e23


def _ev_to_kj_per_mol(ev: Optional[float]) -> Optional[float]:
    if ev is None:
        return None
    return ev * _NA * _EV_J / 1000.0


def _safe_quantile(values: List[float], q: float) -> Optional[float]:
    """Return q-quantile (0..1) using linear interpolation.  None if empty."""
    cleaned = [v for v in values if v is not None and not math.isnan(v)]
    if not cleaned:
        return None
    cleaned.sort()
    n = len(cleaned)
    if n == 1:
        return cleaned[0]
    pos = q * (n - 1)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return cleaned[lo]
    frac = pos - lo
    return cleaned[lo] * (1 - frac) + cleaned[hi] * frac


# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------


def _build_user_prep_summary(form: UserPrepForm) -> Optional[str]:
    bits: List[str] = []
    if form.material_system:
        bits.append(form.material_system)
    if form.R is not None:
        bits.append(f"R={form.R:.3g}")
    if form.N is not None:
        bits.append(f"N={form.N:.3g}")
    if form.solvent:
        bits.append(f"溶剂={form.solvent}")
    if form.acid_or_base:
        bits.append(f"酸/碱={form.acid_or_base}")
    if form.drying_temp_C is not None and form.drying_time_h is not None:
        bits.append(f"干燥 {form.drying_temp_C:g}°C/{form.drying_time_h:g}h")
    if not bits and not form.free_text_notes:
        return None
    summary = "；".join(bits)
    if form.free_text_notes:
        note = form.free_text_notes.strip()
        summary = f"{summary}；备注：{note}" if summary else f"备注：{note}"
    return summary[:200]


def build_identity(bundle: dict, user_prep: UserPrepForm, prep_text_sha256: Optional[str]) -> SampleIdentity:
    recipe = bundle.get("recipe") or {}
    geometry = bundle.get("geometry") or {}
    return SampleIdentity(
        sample_id=str(bundle.get("sample_id") or "UNKNOWN"),
        material_system=user_prep.material_system or bundle.get("material_system"),
        R=user_prep.R if user_prep.R is not None else recipe.get("R"),
        N=user_prep.N if user_prep.N is not None else recipe.get("N"),
        acid_type=user_prep.acid_or_base or recipe.get("acid_type"),
        clay_type=recipe.get("clay_type"),
        thickness_cm=user_prep.sample_thickness_cm or geometry.get("thickness_cm"),
        area_cm2=user_prep.sample_area_cm2 or geometry.get("area_cm2"),
        user_prep_text_sha256=prep_text_sha256,
        user_prep_summary=_build_user_prep_summary(user_prep),
    )


# ---------------------------------------------------------------------------
# Performance card
# ---------------------------------------------------------------------------


def _segments_from_bundle(bundle: dict) -> List[ArrheniusSegmentRow]:
    arr = bundle.get("arrhenius") or {}
    eis_points = bundle.get("eis_points") or []
    ok_T_C = sorted(
        [float(p["T_C"]) for p in eis_points if p.get("status") == "OK" and p.get("T_C") is not None]
    )

    transitions_K = arr.get("transition_temps_K") or []
    transitions_C = sorted([T - 273.15 for T in transitions_K])

    eas_eV = arr.get("ea_segments_eV") or []
    n_seg = arr.get("n_segments") or len(eas_eV)
    if n_seg <= 0:
        return []

    # Build segment T-bounds in ascending temperature order.  The bundle
    # writes Ea high → low going from segment 0 → last (high-T first).
    if not ok_T_C:
        bounds_C: List[Tuple[Optional[float], Optional[float]]] = [(None, None)] * n_seg
    else:
        T_min_all = ok_T_C[0]
        T_max_all = ok_T_C[-1]
        cuts = [T_min_all] + transitions_C + [T_max_all]
        # cuts is len = n_seg + 1 if transitions_C has n_seg-1 entries.
        if len(cuts) - 1 != n_seg:
            # Mismatch: fall back to even-split bounds with whatever we know.
            cuts = [T_min_all] + transitions_C + [T_max_all]
            cuts = cuts[: n_seg + 1] if len(cuts) > n_seg + 1 else cuts + [T_max_all] * (n_seg + 1 - len(cuts))
        bounds_C = list(zip(cuts[:-1], cuts[1:]))

    rows: List[ArrheniusSegmentRow] = []
    # `ea_segments_eV` ordering: bundle convention high-T first → low-T last.
    # We map ea_segments[0] to the highest-T segment.
    for i in range(n_seg):
        # bundle order high-T first
        bundle_idx = i  # 0 = high-T
        # corresponding T-range (highest T-range first)
        rev_idx = n_seg - 1 - i  # in ascending bounds list
        t_low, t_high = bounds_C[rev_idx] if 0 <= rev_idx < len(bounds_C) else (None, None)
        ea_eV = eas_eV[bundle_idx] if bundle_idx < len(eas_eV) else None
        n_pts: Optional[int] = None
        if t_low is not None and t_high is not None:
            n_pts = sum(1 for T in ok_T_C if t_low - 1e-6 <= T <= t_high + 1e-6)
        rows.append(
            ArrheniusSegmentRow(
                idx=bundle_idx,
                T_low_C=t_low,
                T_high_C=t_high,
                Ea_eV=ea_eV,
                Ea_kJ_per_mol=_ev_to_kj_per_mol(ea_eV),
                R2=None,
                n_points=n_pts,
            )
        )
    return rows


def build_performance_card(bundle: dict) -> PerformanceCard:
    arr = bundle.get("arrhenius") or {}
    eis_points = bundle.get("eis_points") or []
    ok = [p for p in eis_points if p.get("status") == "OK" and p.get("sigma_S_cm") is not None]

    sigma_RT = None
    sigma_max = None
    T_at_max = None
    T_min = None
    sigma_at_T_min = None
    if ok:
        # σ at room temperature ≈ point with T_C closest to 25°C
        rt_pt = min(ok, key=lambda p: abs((p.get("T_C") or 1e9) - 25.0))
        sigma_RT = rt_pt.get("sigma_S_cm")
        max_pt = max(ok, key=lambda p: p.get("sigma_S_cm") or -1.0)
        sigma_max = max_pt.get("sigma_S_cm")
        T_at_max = max_pt.get("T_C")
        min_pt = min(ok, key=lambda p: p.get("T_C") or 1e9)
        T_min = min_pt.get("T_C")
        sigma_at_T_min = min_pt.get("sigma_S_cm")

    transitions_C = sorted([T - 273.15 for T in (arr.get("transition_temps_K") or [])])
    return PerformanceCard(
        sigma_RT_S_per_cm=sigma_RT,
        sigma_max_S_per_cm=sigma_max,
        T_at_sigma_max_C=T_at_max,
        T_min_measured_C=T_min,
        sigma_at_T_min_S_per_cm=sigma_at_T_min,
        transport_model=arr.get("best_model_type"),
        n_segments=int(arr.get("n_segments") or 0),
        transition_temps_C=transitions_C,
        segments=_segments_from_bundle(bundle),
        arrhenius_confidence=arr.get("confidence"),
        highlight_zh="",
    )


# ---------------------------------------------------------------------------
# Quality card
# ---------------------------------------------------------------------------


def _classify_nyquist_morphology(eis_points: List[dict]) -> Optional[str]:
    ok = [p for p in eis_points if p.get("status") == "OK"]
    if not ok:
        return None
    arc_visible_count = sum(1 for p in ok if p.get("arc_visible"))
    semicircle_count = sum(1 for p in ok if p.get("semicircle_visible"))
    n = len(ok)
    if semicircle_count >= 0.6 * n:
        return "single_semicircle"
    if arc_visible_count >= 0.6 * n:
        return "compressed_arc"
    if arc_visible_count == 0 and semicircle_count == 0:
        return "tail_dominant"
    return "mixed"


def _extract_drt_peaks(bundle: dict) -> List[DRTPeak]:
    """Expose DRT peaks ONLY if the bundle carries a *reliable* DRT result.

    Reliability gate (R^2 > 0.8) is intentional: on the current LRS spectra the
    canonical Tikhonov DRT is unreliable (reconstruction R^2 < 0 — blocking-electrode
    low-frequency capacitive tail is beyond a pure relaxation kernel; see
    ``V1.0-qianduan-mainline/analysis/drt/relaxation_evolution.json``). So we surface no relaxation
    peaks rather than untrustworthy ones. When the bundle later carries a DRT result
    that passes the gate, peaks flow through automatically. Accepts both the compact
    (``bundle['drt']``) and full (``bundle['drt_result']``) shapes.
    """
    drt = bundle.get("drt") or bundle.get("drt_result")
    if not isinstance(drt, dict) or not drt.get("success"):
        return []
    fit_quality = drt.get("fit_quality") or {}
    r2 = fit_quality.get("r_squared")
    if r2 is None or float(r2) < 0.8:  # reliability gate
        return []
    peaks: List[DRTPeak] = []
    for p in (drt.get("peaks") or [])[:5]:
        tau = p.get("tau", p.get("tau_s"))
        inten = p.get("relative_intensity")
        if inten is None:
            inten = p.get("intensity")
        if tau is None or inten is None:
            continue
        peaks.append(DRTPeak(tau_s=float(tau), intensity=float(inten)))
    return peaks


def build_quality_card(bundle: dict) -> QualityCard:
    eis_points = bundle.get("eis_points") or []
    n_total = len(eis_points)
    ok_pts = [p for p in eis_points if p.get("status") == "OK"]
    n_ok = len(ok_pts)
    n_rej = sum(1 for p in eis_points if p.get("status") and p.get("status") != "OK")

    kk_warns = [bool(p.get("kk_warning")) for p in ok_pts if p.get("kk_warning") is not None]
    kk_pass_rate = (1.0 - sum(kk_warns) / len(kk_warns)) if kk_warns else None

    confs = [float(p["rb_confidence"]) for p in ok_pts if p.get("rb_confidence") is not None]
    p25 = _safe_quantile(confs, 0.25)
    p50 = _safe_quantile(confs, 0.50)
    p75 = _safe_quantile(confs, 0.75)

    # QC distribution from rb_confidence buckets (no native QC grade in bundle)
    qc_dist: Dict[str, int] = {"A": 0, "B": 0, "C": 0, "D": 0}
    for c in confs:
        if c >= 0.9:
            qc_dist["A"] += 1
        elif c >= 0.75:
            qc_dist["B"] += 1
        elif c >= 0.5:
            qc_dist["C"] += 1
        else:
            qc_dist["D"] += 1

    return QualityCard(
        n_eis_points=n_total,
        n_eis_ok=n_ok,
        n_eis_rejected=n_rej,
        KK_pass_rate=kk_pass_rate,
        rb_confidence_p25=p25,
        rb_confidence_p50=p50,
        rb_confidence_p75=p75,
        qc_distribution=qc_dist,
        nyquist_morphology_auto=_classify_nyquist_morphology(eis_points),
        drt_peaks=_extract_drt_peaks(bundle),  # gated: empty unless a reliable DRT (R^2>0.8) is present
        verdict_zh="",
    )


# ---------------------------------------------------------------------------
# Phase transitions (deterministic skeleton)
# ---------------------------------------------------------------------------


def build_phase_transitions_skeleton(bundle: dict) -> List[PhaseTransitionInterp]:
    arr = bundle.get("arrhenius") or {}
    transitions_K = arr.get("transition_temps_K") or []
    eas_eV = arr.get("ea_segments_eV") or []
    out: List[PhaseTransitionInterp] = []
    for i, T_K in enumerate(transitions_K):
        T_C = float(T_K) - 273.15
        confidence = "medium"
        if i + 1 < len(eas_eV) and i < len(eas_eV):
            delta = abs(eas_eV[i + 1] - eas_eV[i])
            if delta >= 0.2:
                confidence = "high"
            elif delta < 0.05:
                confidence = "low"
        out.append(
            PhaseTransitionInterp(
                T_C=round(T_C, 2),
                type_zh="不确定",
                type_code="uncertain",
                confidence=confidence,  # type: ignore[arg-type]
                note_zh="",
            )
        )
    return out


# ---------------------------------------------------------------------------
# Risks / warnings (rule-based)
# ---------------------------------------------------------------------------


_RISK_DEFAULT_TEXT: Dict[str, str] = {
    "RB_BELOW_1OHM": "存在 Rb<1Ω 的点，低温段拟合误差可能放大",
    "KK_WARN_HIGH": "KK 警告比例偏高，建议复核高频部分",
    "FEW_POINTS_PER_SEGMENT": "某段点数偏少，分段 Ea 仅供参考",
    "QC_DEGRADED": "拟合置信度中位数偏低",
    "ARRHENIUS_LOW_CONFIDENCE": "整体 Arrhenius 拟合置信度偏低",
    "USER_PREP_MISSING": "未提供制备表单，仅基于配方推断身份",
    "TRANSITION_AMBIGUOUS": "相变 T 接近段间 ΔEa 阈值",
}


def build_risks(
    bundle: dict,
    performance: PerformanceCard,
    quality: QualityCard,
    user_prep: UserPrepForm,
) -> List[RiskFlag]:
    flags: List[RiskFlag] = []
    eis_points = bundle.get("eis_points") or []

    if any((p.get("rb_ohm") or 1e9) < 1.0 for p in eis_points if p.get("status") == "OK"):
        flags.append(RiskFlag(code="RB_BELOW_1OHM", severity="warn", human_zh=_RISK_DEFAULT_TEXT["RB_BELOW_1OHM"]))

    if quality.KK_pass_rate is not None and quality.KK_pass_rate < 0.6:
        flags.append(RiskFlag(code="KK_WARN_HIGH", severity="warn", human_zh=_RISK_DEFAULT_TEXT["KK_WARN_HIGH"]))

    if any((s.n_points or 0) <= 2 for s in performance.segments):
        flags.append(
            RiskFlag(
                code="FEW_POINTS_PER_SEGMENT",
                severity="warn",
                human_zh=_RISK_DEFAULT_TEXT["FEW_POINTS_PER_SEGMENT"],
            )
        )

    if quality.rb_confidence_p50 is not None and quality.rb_confidence_p50 < 0.6:
        flags.append(RiskFlag(code="QC_DEGRADED", severity="warn", human_zh=_RISK_DEFAULT_TEXT["QC_DEGRADED"]))

    if performance.arrhenius_confidence is not None and performance.arrhenius_confidence < 0.7:
        flags.append(
            RiskFlag(
                code="ARRHENIUS_LOW_CONFIDENCE",
                severity="warn",
                human_zh=_RISK_DEFAULT_TEXT["ARRHENIUS_LOW_CONFIDENCE"],
            )
        )

    if user_prep.material_system is None and not user_prep.formula:
        flags.append(
            RiskFlag(code="USER_PREP_MISSING", severity="info", human_zh=_RISK_DEFAULT_TEXT["USER_PREP_MISSING"])
        )

    return flags


# ---------------------------------------------------------------------------
# Campaign comparison (lite)
# ---------------------------------------------------------------------------


def build_campaign_comparison(
    performance: PerformanceCard, ctx: CampaignContextLite
) -> CampaignComparisonLite:
    delta_pct: Optional[float] = None
    one_liner = ""
    if (
        performance.sigma_RT_S_per_cm is not None
        and ctx.current_best_sigma_RT_S_per_cm is not None
        and ctx.current_best_sigma_RT_S_per_cm > 0
    ):
        delta = (
            (performance.sigma_RT_S_per_cm - ctx.current_best_sigma_RT_S_per_cm)
            / ctx.current_best_sigma_RT_S_per_cm
            * 100.0
        )
        delta_pct = round(delta, 2)
        if delta >= 0:
            one_liner = f"室温 σ 比当前最佳高 {delta:+.1f}%"
        else:
            one_liner = f"室温 σ 比当前最佳低 {abs(delta):.1f}%"
    elif ctx.n_samples_so_far is not None:
        one_liner = f"在当前 {ctx.n_samples_so_far} 个样品中，本样品已纳入对比池"
    return CampaignComparisonLite(
        rank_by_sigma_RT=None,  # leave to caller if it has full campaign data
        delta_vs_best_pct=delta_pct,
        one_liner_zh=one_liner[:60],
    )


# ---------------------------------------------------------------------------
# Public: aggregate deterministic features
# ---------------------------------------------------------------------------


def build_deterministic_features(
    bundle: dict,
    user_prep: UserPrepForm,
    campaign_ctx: CampaignContextLite,
    *,
    prep_text_sha256: Optional[str] = None,
) -> Dict[str, Any]:
    """Return a dict carrying all code-driven sections of the closure report.

    The dict is later merged with the LLM narrative slice in `closure_agent`.
    """
    identity = build_identity(bundle, user_prep, prep_text_sha256)
    performance = build_performance_card(bundle)
    quality = build_quality_card(bundle)
    transitions = build_phase_transitions_skeleton(bundle)
    risks = build_risks(bundle, performance, quality, user_prep)
    comparison = build_campaign_comparison(performance, campaign_ctx)
    return {
        "identity": identity,
        "performance_card": performance,
        "quality_card": quality,
        "phase_transitions": transitions,
        "risks_warnings": risks,
        "campaign_comparison": comparison,
    }


# ---------------------------------------------------------------------------
# Prompt context (the slice we hand to the LLM)
# ---------------------------------------------------------------------------


def build_prompt_context(
    *,
    identity: SampleIdentity,
    performance_card: PerformanceCard,
    quality_card: QualityCard,
    phase_transitions: List[PhaseTransitionInterp],
    risks_warnings: List[RiskFlag],
    campaign_comparison: CampaignComparisonLite,
) -> Dict[str, Any]:
    """Trim the deterministic facts down to a JSON payload for the LLM prompt."""
    return {
        "identity": identity.model_dump(),
        "performance_card": {
            **performance_card.model_dump(exclude={"highlight_zh"}),
            "segments": [s.model_dump() for s in performance_card.segments],
        },
        "quality_card": quality_card.model_dump(exclude={"verdict_zh"}),
        "phase_transitions": [
            {"T_C": pt.T_C, "confidence": pt.confidence} for pt in phase_transitions
        ],
        "risks_warnings": [{"code": r.code, "severity": r.severity} for r in risks_warnings],
        "campaign_comparison": campaign_comparison.model_dump(exclude={"one_liner_zh"}),
    }
