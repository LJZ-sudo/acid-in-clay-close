"""把 sample_aggregator / segment_fitter / sample_trend / meyer_neldel_segment / morphology
的所有结果汇总成 Stage3Seed (P-Stage2-G/H)。

EvidenceUnitV2 强度分级 + supporting_sample_ids 强制由本模块统一打包，
不允许下游再生成"无 sample 追溯"的 evidence。
"""

from __future__ import annotations

import hashlib
import math
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd

from .schema_v2 import (
    EvidenceUnitV2,
    ModelComparisonSummary,
    MorphologySummary,
    SampleSummary,
    Stage3Seed,
    TemperatureSegment,
    TrendResult,
)
from .strength_rules import assign_strength, confidence_from_strength


def _ev_id(prefix: str, *parts: str) -> str:
    h = hashlib.sha1("::".join(parts).encode("utf-8")).hexdigest()[:8]
    return f"{prefix}-{h}"


def _trend_to_evidence(t: TrendResult) -> EvidenceUnitV2:
    direction = (
        "no clear monotonic relation"
        if t.effect_size is None or abs(t.effect_size) < 0.1
        else ("positive" if t.effect_size > 0 else "negative")
    )
    statement = (
        f"Sample-level Spearman analysis of {t.target_metric} vs {t.predictor} "
        f"on {t.n_samples} samples: rho={t.effect_size:.3f}, "
        f"p={t.p_value:.3g}, direction={direction}."
        if t.effect_size is not None and t.p_value is not None
        else f"Sample-level analysis of {t.target_metric} vs {t.predictor} could not be computed (n={t.n_samples})."
    )
    metrics: Dict[str, Any] = {
        "target_metric": t.target_metric,
        "predictor": t.predictor,
        "spearman_rho": t.effect_size,
        "p_value": t.p_value,
        "ci_low_rho": t.ci_low,
        "ci_high_rho": t.ci_high,
        "n_samples": t.n_samples,
    }
    if t.candidate_transition_points:
        metrics["candidate_transition_points"] = t.candidate_transition_points

    return EvidenceUnitV2(
        evidence_id=_ev_id("E-COMP", t.target_metric, t.predictor),
        layer="composition_trend",
        title=f"{t.target_metric} ~ {t.predictor} (sample-level)",
        statement=statement,
        strength=t.strength,
        confidence=confidence_from_strength(t.strength),
        supporting_sample_ids=[],  # filled by builder
        supporting_metrics=metrics,
        statistical_method="spearman + segmented_regression on sample-level summary; bootstrap by sample",
        limitations=t.limitations,
        required_followup=[
            "Independent replication for candidates near segmented breakpoints.",
            "Decouple initial water content from final composition before promoting causal claim.",
        ],
        safe_for_stage3=True,
    )


def _model_comparison_to_evidence(summary: ModelComparisonSummary) -> EvidenceUnitV2:
    counts = summary.best_model_counts or {}
    n_fit = summary.n_samples_with_fit
    statement = (
        f"Per-sample model competition on {n_fit}/{summary.n_samples_total} samples (ln(sigma) residual space, AICc): "
        f"Arrhenius={counts.get('Arrhenius', 0)}, "
        f"Piecewise={counts.get('Piecewise', 0)}, "
        f"VTF={counts.get('VTF', 0)}."
    )
    method_quality = "high" if n_fit >= 20 else "medium" if n_fit >= 10 else "low"
    strength = assign_strength(n_samples=n_fit, method_quality=method_quality)

    return EvidenceUnitV2(
        evidence_id=_ev_id("E-MODEL", "per_sample_competition"),
        layer="model_competition",
        title="Per-sample Arrhenius vs Piecewise vs VTF preference distribution",
        statement=statement,
        strength=strength,
        confidence=confidence_from_strength(strength),
        supporting_sample_ids=[],  # caller fills with all samples that produced fits
        supporting_metrics={
            "n_samples_total": summary.n_samples_total,
            "n_samples_with_fit": n_fit,
            "best_model_counts": counts,
            "mean_delta_aicc_arrhenius_vs_piecewise": summary.mean_delta_aic_arrhenius_vs_piecewise,
            "mean_delta_aicc_arrhenius_vs_vtf": summary.mean_delta_aic_arrhenius_vs_vtf,
        },
        statistical_method="per-sample non-linear least squares + AICc (ln-sigma residual space)",
        limitations=[
            "Model preference is per-sample; do not aggregate as a single global Arrhenius/VTF claim.",
            "Piecewise breakpoint selected by brute-force RSS minimization; report breakpoint CI in followup work.",
        ],
        required_followup=[
            "Bootstrap T_break_K per sample to assess breakpoint stability.",
            "Compare AICc vs BIC sensitivity for Arrhenius/VTF preference.",
        ],
        safe_for_stage3=True,
    )


def _meyer_neldel_to_evidence(mn: Dict[str, Any]) -> EvidenceUnitV2:
    n_seg = mn.get("n_independent_segments", 0)
    n_uniq = mn.get("n_unique_samples", 0)
    r2 = mn.get("r2")
    statement = (
        f"Segment-level Meyer-Neldel regression: n_segments={n_seg}, n_unique_samples={n_uniq}, "
        f"R^2={r2:.3f}." if r2 is not None
        else "Segment-level Meyer-Neldel regression could not be performed (no usable segments)."
    )
    return EvidenceUnitV2(
        evidence_id=_ev_id("E-MN", "segment_level"),
        layer="model_competition",
        title="Meyer-Neldel compensation (segment-level)",
        statement=statement,
        strength=mn.get("strength", "tentative"),
        confidence=confidence_from_strength(mn.get("strength", "tentative")),
        supporting_sample_ids=[],
        supporting_metrics=mn,
        statistical_method="ln(sigma0) ~ Ea on independent Arrhenius segments; bootstrap by sample_id",
        limitations=mn.get("limitations", []),
        required_followup=[
            "Independent replication on n>=3 samples per R/N region before promoting Meyer-Neldel claim.",
        ],
        safe_for_stage3=True,
    )


def _morphology_to_evidence(m: MorphologySummary) -> EvidenceUnitV2:
    statement = (
        f"EIS morphology coverage: {m.n_samples_with_arc_evidence}/{m.n_samples_total} samples "
        f"show any arc_visible evidence; {m.n_samples_with_semicircle_evidence}/{m.n_samples_total} "
        f"show semicircle_visible. Row-level rates: arc={m.arc_visible_rate:.2%}, "
        f"semicircle={m.semicircle_visible_rate:.2%}."
    )
    if m.sparsity_warning:
        strength = "tentative"
        limitations = [
            "EIS morphology evidence is based on sparse binary features rather than full Nyquist/DRT re-analysis.",
            "Cold-window arc/semicircle counts are too low (<5 samples) to support phase-transition claims.",
        ]
    else:
        strength = "weak"
        limitations = [
            "EIS morphology evidence is based on binary CSV flags; quantitative DRT/CNLS re-analysis is required for stronger claims.",
        ]
    return EvidenceUnitV2(
        evidence_id=_ev_id("E-MORPH", "coverage"),
        layer="eis_morphology",
        title="EIS morphology coverage and sparsity",
        statement=statement,
        strength=strength,
        confidence=confidence_from_strength(strength),
        supporting_sample_ids=[],
        supporting_metrics=m.model_dump(),
        statistical_method="binary feature counting from row-level CSV",
        limitations=limitations,
        required_followup=[
            "Run quantitative DRT / Bode-Nyquist analysis on at least 5 samples spanning low-T window.",
        ],
        safe_for_stage3=True,
    )


# ---------------------------------------------------------------------------
# C1: Additional evidence generators (push V2 evidence count from 9 to ≥12)
# Each generator is pure / numeric and sample-traceable.
# ---------------------------------------------------------------------------

def _model_dominance_to_evidence(summary: ModelComparisonSummary) -> Optional[EvidenceUnitV2]:
    """Highlight the most-preferred transport model (e.g. VTF dominance).
    A separate, headline-style evidence unit so Stage3 sees the asymmetry
    explicitly instead of having to read sub-counts."""
    counts = summary.best_model_counts or {}
    n_fit = summary.n_samples_with_fit
    if n_fit < 5 or not counts:
        return None
    best_model, best_count = max(counts.items(), key=lambda kv: kv[1])
    frac = best_count / max(1, n_fit)
    if frac < 0.5:
        return None  # No clear dominance — skip to avoid noise.
    method_quality = "high" if n_fit >= 20 else "medium" if n_fit >= 10 else "low"
    strength = assign_strength(n_samples=n_fit, method_quality=method_quality)
    if frac < 0.7:
        # Weaker dominance shouldn't be reported above moderate.
        if strength == "strong":
            strength = "moderate"
    statement = (
        f"On {n_fit} samples, {best_model} is the AICc-preferred per-sample transport model "
        f"in {best_count}/{n_fit} cases ({frac:.0%}); "
        f"this asymmetry is the dominant signal in the model-competition layer."
    )
    return EvidenceUnitV2(
        evidence_id=_ev_id("E-MODEL-DOM", best_model),
        layer="model_competition",
        title=f"Per-sample model dominance: {best_model}",
        statement=statement,
        strength=strength,
        confidence=confidence_from_strength(strength),
        supporting_sample_ids=[],
        supporting_metrics={
            "dominant_model": best_model,
            "dominant_count": best_count,
            "n_samples_with_fit": n_fit,
            "dominant_fraction": round(frac, 4),
            "best_model_counts": counts,
        },
        statistical_method="per-sample AICc model selection (Arrhenius vs Piecewise vs VTF)",
        limitations=[
            "Model preference is per-sample; the dominance fraction does not imply "
            "a single global model holds for every (R, N) region.",
            "AICc dominance does not by itself imply VTF > Arrhenius mechanism truth — "
            "could reflect curvature in cold-window σ(T) due to sparse sampling.",
        ],
        required_followup=[
            "Bootstrap AICc per sample to assess whether dominance is stable under resampling.",
            "Stratify dominance by (R, N) to detect region-specific model regimes.",
        ],
        safe_for_stage3=True,
    )


def _segment_ea_distribution_to_evidence(
    segments: List[TemperatureSegment],
) -> Optional[EvidenceUnitV2]:
    """Pool segment-level Ea values, separate high-T vs low-T regimes,
    and report distribution + how many segments contribute to each."""
    if not segments:
        return None
    high_eas: List[float] = []
    low_eas: List[float] = []
    high_segs: List[str] = []
    low_segs: List[str] = []
    high_samples: set[str] = set()
    low_samples: set[str] = set()
    for seg in segments:
        if seg.arrhenius_ea_eV is None:
            continue
        label = (seg.segment_label or "").lower()
        if "low" in label:
            low_eas.append(seg.arrhenius_ea_eV)
            low_segs.append(seg.segment_id)
            low_samples.add(seg.sample_id)
        elif "high" in label or "single" in label or "mid" in label:
            high_eas.append(seg.arrhenius_ea_eV)
            high_segs.append(seg.segment_id)
            high_samples.add(seg.sample_id)
    if not high_eas and not low_eas:
        return None

    def _stats(xs: List[float]) -> Dict[str, Any]:
        if not xs:
            return {"n": 0}
        xs_sorted = sorted(xs)
        n = len(xs_sorted)
        mean = sum(xs_sorted) / n
        var = sum((x - mean) ** 2 for x in xs_sorted) / max(1, n - 1)
        return {
            "n": n,
            "mean_eV": round(mean, 4),
            "std_eV": round(math.sqrt(var), 4),
            "median_eV": round(xs_sorted[n // 2], 4),
            "min_eV": round(min(xs_sorted), 4),
            "max_eV": round(max(xs_sorted), 4),
        }

    stats_high = _stats(high_eas)
    stats_low = _stats(low_eas)

    n_high = stats_high.get("n", 0)
    n_low = stats_low.get("n", 0)
    n_total_segs = n_high + n_low
    method_quality = "high" if n_total_segs >= 60 else "medium" if n_total_segs >= 20 else "low"
    n_unique = len(high_samples | low_samples)
    strength = assign_strength(n_samples=n_unique, method_quality=method_quality)

    statement = (
        f"Pooled segment-level activation energies: high/mid-T n={n_high} "
        f"(mean={stats_high.get('mean_eV')} eV, median={stats_high.get('median_eV')} eV); "
        f"low-T n={n_low} (mean={stats_low.get('mean_eV')} eV, "
        f"median={stats_low.get('median_eV')} eV) across {n_unique} samples. "
        "Aggregate distribution — not a single global Ea claim."
    )
    return EvidenceUnitV2(
        evidence_id=_ev_id("E-SEG-EA", "high_low_distribution"),
        layer="model_competition",
        title="Segment-level Ea distribution (high-T vs low-T)",
        statement=statement,
        strength=strength,
        confidence=confidence_from_strength(strength),
        supporting_sample_ids=sorted(high_samples | low_samples),
        supporting_segment_ids=sorted(high_segs + low_segs),
        supporting_metrics={
            "high_or_mid_T": stats_high,
            "low_T": stats_low,
            "n_segments_total": n_total_segs,
            "n_unique_samples": n_unique,
        },
        statistical_method="pool of per-segment Arrhenius fits; descriptive distribution only",
        limitations=[
            "Segments are correlated within a single sample; bootstrap by sample_id before "
            "any inferential claim about Ea_high vs Ea_low difference.",
            "high/mid/single labels are merged into one bucket; finer label-stratified analysis is required for region-specific claims.",
        ],
        required_followup=[
            "Bootstrap Ea_high − Ea_low difference per sample; report 95% CI.",
            "Test whether the Ea_low > Ea_high contrast is driven by a small subset of (R, N) regions.",
        ],
        safe_for_stage3=True,
    )


def _phase_transition_incidence_to_evidence(
    summaries: List[SampleSummary],
    segments: List[TemperatureSegment],
    model_summary: ModelComparisonSummary,
) -> Optional[EvidenceUnitV2]:
    """Count samples that show a piecewise breakpoint and report the breakpoint distribution."""
    piecewise_breaks: List[float] = []
    samples_with_break: set[str] = set()
    for seg in segments:
        params = seg.piecewise_model_params or {}
        tb = params.get("T_break_K") or params.get("t_break_K") or params.get("T_break")
        if tb is None:
            continue
        try:
            tbf = float(tb)
        except (TypeError, ValueError):
            continue
        piecewise_breaks.append(tbf)
        samples_with_break.add(seg.sample_id)

    n_total = len(summaries)
    n_with_break = len(samples_with_break)
    counts = model_summary.best_model_counts or {}
    n_piecewise_winners = int(counts.get("Piecewise", 0))

    if n_total == 0:
        return None

    if piecewise_breaks:
        breaks_sorted = sorted(piecewise_breaks)
        mean_break = sum(breaks_sorted) / len(breaks_sorted)
        median_break = breaks_sorted[len(breaks_sorted) // 2]
        break_min, break_max = min(breaks_sorted), max(breaks_sorted)
    else:
        mean_break = median_break = break_min = break_max = None  # type: ignore

    frac_break = n_with_break / max(1, n_total)
    method_quality = "medium" if n_total >= 20 else "low"
    strength = assign_strength(n_samples=n_with_break, method_quality=method_quality)
    if n_with_break < 5:
        strength = "tentative"

    statement = (
        f"Detectable piecewise breakpoint observed on {n_with_break}/{n_total} samples "
        f"({frac_break:.0%}); "
        + (
            f"breakpoint distribution: median={median_break:.1f} K, "
            f"mean={mean_break:.1f} K, range=[{break_min:.1f}, {break_max:.1f}] K. "
            if piecewise_breaks
            else "no usable T_break_K could be extracted from segment fits. "
        )
        + f"Per-sample model competition picked Piecewise as best AICc on {n_piecewise_winners}/{n_total} samples."
    )
    return EvidenceUnitV2(
        evidence_id=_ev_id("E-PHASE", "piecewise_break_incidence"),
        layer="model_competition",
        title="Phase transition / piecewise breakpoint incidence",
        statement=statement,
        strength=strength,
        confidence=confidence_from_strength(strength),
        supporting_sample_ids=sorted(samples_with_break),
        supporting_metrics={
            "n_samples_total": n_total,
            "n_samples_with_break": n_with_break,
            "fraction_with_break": round(frac_break, 4),
            "n_piecewise_aicc_winners": n_piecewise_winners,
            "break_T_K_distribution": {
                "n": len(piecewise_breaks),
                "mean_K": round(mean_break, 2) if mean_break is not None else None,
                "median_K": round(median_break, 2) if median_break is not None else None,
                "min_K": round(break_min, 2) if break_min is not None else None,
                "max_K": round(break_max, 2) if break_max is not None else None,
            },
        },
        statistical_method="count of samples with extracted T_break_K + AICc piecewise winners",
        limitations=[
            "T_break_K is taken from each segment's piecewise_model_params and may include "
            "duplicates or low-confidence breakpoints; bootstrap CI per sample is required "
            "before any phase-transition claim.",
            "Detection of a breakpoint does NOT identify its physical mechanism (acid solidification, water freezing, hydrogen-bond reorganization).",
        ],
        required_followup=[
            "Bootstrap T_break_K per sample; report 95% CI.",
            "Cross-check breakpoint temperatures against EIS arc/semicircle visibility flags in the same sample.",
        ],
        safe_for_stage3=True,
    )


def _top_performer_region_to_evidence(
    summaries: List[SampleSummary],
) -> Optional[EvidenceUnitV2]:
    """Bound the (R, N) box that contains the top-decile of σ_299K samples.
    Acts as a Stage1 BO prior."""
    rows = [
        s for s in summaries
        if s.sigma_299K_interp_S_cm is not None
        and s.R is not None
        and s.N is not None
    ]
    if len(rows) < 8:
        return None
    rows_sorted = sorted(rows, key=lambda s: s.sigma_299K_interp_S_cm or 0.0, reverse=True)
    k = max(3, int(round(0.20 * len(rows_sorted))))
    top = rows_sorted[:k]
    Rs = [s.R for s in top if s.R is not None]
    Ns = [s.N for s in top if s.N is not None]
    if not Rs or not Ns:
        return None
    R_min, R_max = min(Rs), max(Rs)
    N_min, N_max = min(Ns), max(Ns)
    sigma_top_min = top[-1].sigma_299K_interp_S_cm
    sigma_top_max = top[0].sigma_299K_interp_S_cm

    n_total = len(rows_sorted)
    method_quality = "high" if n_total >= 30 else "medium" if n_total >= 15 else "low"
    strength = assign_strength(n_samples=k, method_quality=method_quality)
    if k < 6:
        strength = "tentative"

    statement = (
        f"The top-{k}/{n_total} samples by σ(299 K) span R∈[{R_min:.3f}, {R_max:.3f}] "
        f"and N∈[{N_min:.3f}, {N_max:.3f}]; "
        f"σ(299 K) within this top set spans [{sigma_top_min:.3e}, {sigma_top_max:.3e}] S/cm. "
        "Treat this region as a sample-distribution observation, not a guarantee of best performance."
    )
    return EvidenceUnitV2(
        evidence_id=_ev_id("E-COMP-TOP", "sigma_299K_topbox"),
        layer="composition_trend",
        title="Top-performer (R, N) bounding box for σ(299 K)",
        statement=statement,
        strength=strength,
        confidence=confidence_from_strength(strength),
        supporting_sample_ids=[s.sample_id for s in top],
        supporting_metrics={
            "top_k": k,
            "n_total_with_sigma_299K": n_total,
            "R_min": round(R_min, 4),
            "R_max": round(R_max, 4),
            "N_min": round(N_min, 4),
            "N_max": round(N_max, 4),
            "sigma_top_min_S_cm": sigma_top_min,
            "sigma_top_max_S_cm": sigma_top_max,
        },
        statistical_method="top-decile / top-quintile bounding box on (R, N) of σ(299 K) ranking",
        limitations=[
            "Bounding box is descriptive, not a fitted Pareto front; small samples can give misleading boxes.",
            "Top-decile selection is sensitive to interpolation choice for σ(299 K); rerun under jackknife to assess stability.",
        ],
        required_followup=[
            "Jackknife / bootstrap the bounding box; report fraction of resamples for which a given (R, N) lies inside.",
            "Stage1 BO can use this box as an exploration prior, not as a constraint.",
        ],
        safe_for_stage3=True,
    )


# ---------------------------------------------------------------------------
# Top candidate regions & questions
# ---------------------------------------------------------------------------

def _top_candidate_regions(summaries: List[SampleSummary], top_k: int = 3) -> List[Dict[str, Any]]:
    ranked = [
        s for s in summaries
        if s.sigma_299K_interp_S_cm is not None and s.sigma_299K_interp_S_cm > 0
    ]
    ranked.sort(key=lambda s: s.sigma_299K_interp_S_cm, reverse=True)  # type: ignore[arg-type]
    out = []
    for s in ranked[:top_k]:
        out.append(
            {
                "sample_id": s.sample_id,
                "R": s.R,
                "N": s.N,
                "sigma_299K_S_cm": s.sigma_299K_interp_S_cm,
                "sigma_233K_S_cm": s.sigma_233K_interp_S_cm,
                "best_arrhenius_ea_eV": s.best_arrhenius_ea_eV,
            }
        )
    return out


def _unresolved_questions(
    morph: MorphologySummary,
    mn: Dict[str, Any],
    model_summary: ModelComparisonSummary,
) -> List[Dict[str, Any]]:
    qs: List[Dict[str, Any]] = []
    if morph.sparsity_warning:
        qs.append(
            {
                "question_id": "Q-MORPH-1",
                "question": "Does the cold-window EIS arc actually appear in S8 acid-in-clay samples, or is the binary 'arc_visible' flag an artifact of fitting noise?",
                "needed_evidence": ["DRT analysis on >=5 samples with full Nyquist", "Bode-plot inspection in 100 K-300 K window"],
            }
        )
    if (mn.get("n_unique_samples") or 0) < 10:
        qs.append(
            {
                "question_id": "Q-MN-1",
                "question": "Is the Meyer-Neldel compensation behaviour real, or driven by <10 unique samples?",
                "needed_evidence": ["Independent replicates in 3+ R/N regions"],
            }
        )
    if model_summary.n_samples_with_fit < 20:
        qs.append(
            {
                "question_id": "Q-MODEL-1",
                "question": "Per-sample model preference is fragile; do Arrhenius/Piecewise/VTF rankings hold under bootstrap?",
                "needed_evidence": ["Bootstrap RSS / AICc per sample"],
            }
        )
    return qs


# ---------------------------------------------------------------------------
# Builder entry
# ---------------------------------------------------------------------------

def build_stage3_seed(
    *,
    run_id: str,
    summaries: List[SampleSummary],
    segments: List[TemperatureSegment],
    trends: List[TrendResult],
    model_summary: ModelComparisonSummary,
    mn_result: Dict[str, Any],
    morphology_summary: MorphologySummary,
    data_profile: Optional[Dict[str, Any]] = None,
    input_files: Optional[Dict[str, str]] = None,
    input_hashes: Optional[Dict[str, str]] = None,
) -> Stage3Seed:
    sample_ids_all = [s.sample_id for s in summaries]
    samples_with_fit = [s.sample_id for s in summaries if s.best_arrhenius_ea_eV is not None]

    # Build evidence units with proper supporting_sample_ids
    evidences: List[EvidenceUnitV2] = []
    for t in trends:
        ev = _trend_to_evidence(t)
        ev.supporting_sample_ids = list(samples_with_fit) if t.target_metric.startswith("best_") else list(sample_ids_all)
        evidences.append(ev)

    ev_model = _model_comparison_to_evidence(model_summary)
    ev_model.supporting_sample_ids = list(samples_with_fit)
    evidences.append(ev_model)

    ev_mn = _meyer_neldel_to_evidence(mn_result)
    ev_mn.supporting_sample_ids = list(samples_with_fit)
    evidences.append(ev_mn)

    ev_morph = _morphology_to_evidence(morphology_summary)
    ev_morph.supporting_sample_ids = [
        s.sample_id for s in summaries if s.has_arc_visible or s.has_semicircle_visible
    ]
    evidences.append(ev_morph)

    # C1 expansion: extra evidence units derived from the same aggregated
    # data — model dominance, segment-level Ea distribution, phase-transition
    # incidence, top-performer bounding box. Each is sample-traceable and
    # marks its own limitations / followups.
    ev_dom = _model_dominance_to_evidence(model_summary)
    if ev_dom is not None:
        ev_dom.supporting_sample_ids = list(samples_with_fit)
        evidences.append(ev_dom)

    ev_segea = _segment_ea_distribution_to_evidence(segments)
    if ev_segea is not None:
        evidences.append(ev_segea)

    ev_phase = _phase_transition_incidence_to_evidence(summaries, segments, model_summary)
    if ev_phase is not None:
        evidences.append(ev_phase)

    ev_topbox = _top_performer_region_to_evidence(summaries)
    if ev_topbox is not None:
        evidences.append(ev_topbox)

    blocking_reasons: List[str] = []
    if not summaries:
        blocking_reasons.append("no_sample_summary")
    if not segments:
        blocking_reasons.append("no_segment_fits")
    if not evidences:
        blocking_reasons.append("no_evidence_units")

    missing_rn = [
        s.sample_id for s in summaries
        if s.R is None or s.N is None or "missing_R" in s.quality_flags or "missing_N" in s.quality_flags
    ]
    if missing_rn:
        blocking_reasons.append(
            "missing_R_or_N:" + ",".join(missing_rn[:20])
        )

    inconsistent_rn = [
        s.sample_id for s in summaries
        if "RN_inconsistent_R" in s.quality_flags or "RN_inconsistent_N" in s.quality_flags
    ]
    if inconsistent_rn:
        blocking_reasons.append(
            "inconsistent_R_or_N:" + ",".join(inconsistent_rn[:20])
        )

    seed = Stage3Seed(
        seed_id=_ev_id("SEED", run_id, datetime.utcnow().isoformat()),
        source_stage2_run_id=run_id,
        input_files=input_files or {},
        input_hashes=input_hashes or {},
        stage3_ready=not blocking_reasons,
        stage3_blocking_reasons=blocking_reasons,
        data_profile=data_profile or {},
        sample_summary=summaries,
        segment_fits=segments,
        model_comparison_summary=model_summary,
        morphology_summary=morphology_summary,
        evidence_units=evidences,
        top_candidate_regions=_top_candidate_regions(summaries),
        unresolved_questions=_unresolved_questions(morphology_summary, mn_result, model_summary),
    )
    return seed


def evidence_units_to_dataframe(evidences: List[EvidenceUnitV2]) -> pd.DataFrame:
    rows = []
    for e in evidences:
        d = e.model_dump()
        rows.append(d)
    return pd.DataFrame(rows)
