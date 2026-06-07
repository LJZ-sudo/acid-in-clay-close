"""C2: Multi-seed + weight-perturbation ranking robustness analysis.

Reads `09_ranking/candidate_audit.json` (deterministic sub-scores per candidate)
and stress-tests the material-priority ranker by:

  (1) varying the material-priority weights over a Dirichlet-style sampling
      around the default weights;
  (2) adding small Gaussian jitter (default sigma=0.02) on every sub-score
      across many random seeds to model measurement uncertainty;
  (3) optionally overriding `source_term_ok` / `term_leakage_penalty` and
      `prospective_status_score` so the robustness reflects the *current*
      audit state (post-C3 the term_leakage_penalty drops to 0).

For each candidate we record rank distribution, top-1 / top-3 frequencies,
and Spearman correlation against the default deterministic ranking.

Outputs under the current run output_dir:
    09_ranking/ranking_robustness_v2.json
    09_ranking/ranking_robustness_v2_heatmap.png

This is a post-hoc module: it never mutates `ranked_top_list.json` or
`deterministic_reranked_top_list.json`.
"""
from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_WEIGHTS = {
    "mechanism_fit": 0.20,
    "evidence_quality": 0.18,
    "formulation_completeness": 0.18,
    "low_temperature_plausibility": 0.14,
    "processability": 0.11,
    "novelty": 0.05,
    "citation": 0.04,
    "one_minus_risk": 0.10,
}

# ---------------------------------------------------------------------------
# Pure scoring helpers — no numpy dependency in the inner loop until needed.
# ---------------------------------------------------------------------------


@dataclass
class CandidateRow:
    instance_id: str
    instance_name: str
    mechanism_fit: float
    evidence_quality: float
    formulation_completeness: float
    low_temperature_plausibility: float
    processability: float
    citation: float
    novelty: float
    risk: float
    term_leakage_penalty: float
    prospective: float

    def base_score(
        self,
        weights: dict[str, float],
        *,
        term_leakage_penalty: Optional[float] = None,
        sub_score_jitter: Optional[dict[str, float]] = None,
    ) -> float:
        j = sub_score_jitter or {}
        mechanism = max(0.0, min(1.0, self.mechanism_fit + j.get("mechanism_fit", 0.0)))
        evidence = max(0.0, min(1.0, self.evidence_quality + j.get("evidence_quality", 0.0)))
        formulation = max(0.0, min(1.0, self.formulation_completeness + j.get("formulation_completeness", 0.0)))
        low_temp = max(0.0, min(1.0, self.low_temperature_plausibility + j.get("low_temperature_plausibility", 0.0)))
        process = max(0.0, min(1.0, self.processability + j.get("processability", 0.0)))
        cit = max(0.0, min(1.0, self.citation + j.get("citation", 0.0)))
        nov = max(0.0, min(1.0, self.novelty + j.get("novelty", 0.0)))
        risk = max(0.0, min(1.0, self.risk + j.get("risk", 0.0)))
        w = weights
        raw = (
            w["mechanism_fit"] * mechanism
            + w["evidence_quality"] * evidence
            + w["formulation_completeness"] * formulation
            + w["low_temperature_plausibility"] * low_temp
            + w["processability"] * process
            + w["citation"] * cit
            + w["novelty"] * nov
            + w["one_minus_risk"] * (1.0 - risk)
        )
        penalty = self.term_leakage_penalty if term_leakage_penalty is None else term_leakage_penalty
        return max(0.0, min(1.0, raw - penalty + 0.05 * self.prospective))


def _load_candidate_rows(
    audit_path: Path,
    *,
    source_term_ok: Optional[bool],
) -> list[CandidateRow]:
    data = json.loads(audit_path.read_text(encoding="utf-8"))
    rows: list[CandidateRow] = []
    for r in data.get("rows") or []:
        penalty_raw = float(r.get("term_leakage_penalty") or 0.0)
        if source_term_ok is True:
            penalty = 0.0
        elif source_term_ok is False:
            penalty = max(penalty_raw, 0.3)
        else:  # None -> keep recorded penalty
            penalty = penalty_raw
        rows.append(
            CandidateRow(
                instance_id=str(r.get("instance_id") or ""),
                instance_name=str(r.get("instance_name") or ""),
                mechanism_fit=float(r.get("mechanism_fit_score", r.get("descriptor_claim_coverage") or 0.0) or 0.0),
                evidence_quality=float(r.get("evidence_quality_score", r.get("descriptor_claim_coverage") or 0.0) or 0.0),
                formulation_completeness=float(
                    r.get("formulation_completeness_score", r.get("descriptor_claim_coverage") or 0.0) or 0.0
                ),
                low_temperature_plausibility=float(
                    r.get("low_temperature_plausibility_score", r.get("descriptor_claim_coverage") or 0.0) or 0.0
                ),
                processability=float(r.get("processability_score", 0.5) or 0.0),
                citation=float(r.get("citation_validity") or 0.0),
                novelty=float(r.get("novelty_score") or 0.0),
                risk=float(r.get("risk_score") or 0.0),
                term_leakage_penalty=penalty,
                prospective=float(r.get("prospective_status_score") or 0.0),
            )
        )
    return rows


def _rank(scores: list[float]) -> list[int]:
    order = sorted(range(len(scores)), key=lambda i: -scores[i])
    rk = [0] * len(scores)
    for r, idx in enumerate(order, start=1):
        rk[idx] = r
    return rk


def _spearman(a: list[int], b: list[int]) -> float:
    n = len(a)
    if n < 2:
        return 1.0
    mean_a = sum(a) / n
    mean_b = sum(b) / n
    num = sum((a[i] - mean_a) * (b[i] - mean_b) for i in range(n))
    den_a = math.sqrt(sum((a[i] - mean_a) ** 2 for i in range(n)))
    den_b = math.sqrt(sum((b[i] - mean_b) ** 2 for i in range(n)))
    if den_a == 0 or den_b == 0:
        return 1.0
    return num / (den_a * den_b)


def run_ranking_robustness_v2(
    *,
    output_dir: Path,
    n_seeds: int = 200,
    weight_jitter_sigma: float = 0.05,
    sub_score_jitter_sigma: float = 0.02,
    source_term_ok: Optional[bool] = True,
    rng_seed: int = 20260501,
    plot: bool = True,
) -> dict:
    """Run the v2 robustness analysis. Returns the summary dict (also written to JSON)."""
    audit_path = output_dir / "09_ranking" / "candidate_audit.json"
    if not audit_path.exists():
        raise FileNotFoundError(f"candidate_audit.json not found at {audit_path}")

    import random
    rows = _load_candidate_rows(audit_path, source_term_ok=source_term_ok)
    out_json = output_dir / "09_ranking" / "ranking_robustness_v2.json"
    if len(rows) < 2:
        summary = {
            "method": "ranking_robustness_v2",
            "status": "insufficient_candidates",
            "n_candidates": len(rows),
            "n_seeds": n_seeds,
            "stability_class": "insufficient",
            "top1_stability_rate": None,
            "top3_jaccard_mean": None,
            "rank_std_summary": {},
            "unstable_candidates": [r.instance_id for r in rows],
            "recommended_wording_hint": (
                "Insufficient candidates for ranking robustness; avoid single-winner claims."
            ),
            "per_candidate": [],
        }
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        return summary

    n = len(rows)
    rng = random.Random(rng_seed)

    # 1. Default ranking (no perturbation)
    default_scores = [r.base_score(DEFAULT_WEIGHTS) for r in rows]
    default_ranks = _rank(default_scores)
    default_top1 = rows[default_scores.index(max(default_scores))].instance_id
    default_top3 = {
        rows[i].instance_id
        for i in sorted(range(n), key=lambda i: -default_scores[i])[:3]
    }

    # 2. Perturbation loop
    rank_hist = {r.instance_id: [0] * n for r in rows}
    top1_count = {r.instance_id: 0 for r in rows}
    top3_count = {r.instance_id: 0 for r in rows}
    spearman_to_default: list[float] = []
    jaccard_top3: list[float] = []
    seeds_used: list[int] = []

    for seed_i in range(n_seeds):
        seed = rng_seed + seed_i + 1
        seeds_used.append(seed)
        prng = random.Random(seed)

        # weight jitter (Gaussian then renormalize)
        w_jit = {
            k: max(1e-3, v + prng.gauss(0.0, weight_jitter_sigma))
            for k, v in DEFAULT_WEIGHTS.items()
        }
        s = sum(w_jit.values())
        w_jit = {k: v / s for k, v in w_jit.items()}

        # per-candidate sub-score jitter (Gaussian)
        scores = []
        for cand in rows:
            jit = {
                k: prng.gauss(0.0, sub_score_jitter_sigma)
                for k in (
                    "mechanism_fit",
                    "evidence_quality",
                    "formulation_completeness",
                    "low_temperature_plausibility",
                    "processability",
                    "citation",
                    "novelty",
                    "risk",
                )
            }
            scores.append(cand.base_score(w_jit, sub_score_jitter=jit))

        ranks = _rank(scores)
        for i, cand in enumerate(rows):
            rank_hist[cand.instance_id][ranks[i] - 1] += 1
        top1_idx = scores.index(max(scores))
        top1_count[rows[top1_idx].instance_id] += 1
        top3_set = {
            rows[i].instance_id
            for i in sorted(range(n), key=lambda i: -scores[i])[:3]
        }
        for iid in top3_set:
            top3_count[iid] += 1

        spearman_to_default.append(_spearman(default_ranks, ranks))
        inter = default_top3 & top3_set
        union = default_top3 | top3_set
        jaccard_top3.append(len(inter) / len(union) if union else 1.0)

    # 3. Per-candidate summary
    per_candidate = []
    for i, cand in enumerate(rows):
        hist = rank_hist[cand.instance_id]
        total = sum(hist) or 1
        mean_rank = sum((r + 1) * c for r, c in enumerate(hist)) / total
        var_rank = sum(((r + 1) - mean_rank) ** 2 * c for r, c in enumerate(hist)) / total
        per_candidate.append(
            {
                "instance_id": cand.instance_id,
                "instance_name": cand.instance_name,
                "default_rank": default_ranks[i],
                "default_score": round(default_scores[i], 4),
                "rank_histogram": hist,
                "top1_freq": round(top1_count[cand.instance_id] / n_seeds, 4),
                "top3_freq": round(top3_count[cand.instance_id] / n_seeds, 4),
                "mean_rank": round(mean_rank, 3),
                "std_rank": round(math.sqrt(var_rank), 3),
            }
        )
    per_candidate.sort(key=lambda r: r["default_rank"])

    # 4. Aggregate summary
    spear_mean = sum(spearman_to_default) / len(spearman_to_default)
    spear_min = min(spearman_to_default)
    spear_p05 = sorted(spearman_to_default)[max(0, int(0.05 * len(spearman_to_default)))]
    jacc_mean = sum(jaccard_top3) / len(jaccard_top3)
    top1_stability = top1_count.get(default_top1, 0) / n_seeds

    stability_class = _stability_class(top1_stability, jacc_mean, spear_mean)
    unstable_candidates = _unstable_candidates(per_candidate)
    rank_stds = [float(c["std_rank"]) for c in per_candidate]
    summary = {
        "method": "ranking_robustness_v2",
        "status": "ok",
        "n_candidates": n,
        "n_seeds": n_seeds,
        "rng_seed": rng_seed,
        "weight_jitter_sigma": weight_jitter_sigma,
        "sub_score_jitter_sigma": sub_score_jitter_sigma,
        "source_term_ok_assumed": source_term_ok,
        "default_weights": DEFAULT_WEIGHTS,
        "default_top1": default_top1,
        "default_top3": sorted(default_top3),
        "top1_stability_rate": round(top1_stability, 4),
        "top3_jaccard_mean": round(jacc_mean, 4),
        "stability_class": stability_class,
        "rank_std_summary": {
            "mean": round(sum(rank_stds) / len(rank_stds), 4) if rank_stds else None,
            "max": round(max(rank_stds), 4) if rank_stds else None,
        },
        "unstable_candidates": unstable_candidates,
        "recommended_wording_hint": _wording_hint(stability_class),
        "spearman_to_default": {
            "mean": round(spear_mean, 4),
            "min": round(spear_min, 4),
            "p05": round(spear_p05, 4),
        },
        "per_candidate": per_candidate,
        "interpretation": _interpret(top1_stability, jacc_mean, spear_mean, per_candidate),
    }

    out_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("[robustness_v2] wrote %s", out_json)

    if plot:
        _plot_heatmap(per_candidate, n_seeds, output_dir / "09_ranking" / "ranking_robustness_v2_heatmap.png")

    return summary


def _stability_class(top1_stability: float, jacc_mean: float, spear_mean: float) -> str:
    if top1_stability >= 0.70 and jacc_mean >= 0.80 and spear_mean >= 0.85:
        return "stable"
    if jacc_mean >= 0.60 and spear_mean >= 0.70:
        return "moderately_stable"
    return "unstable"


def _unstable_candidates(per_candidate: list[dict]) -> list[dict]:
    unstable: list[dict] = []
    for row in per_candidate:
        default_rank = int(row.get("default_rank") or 999)
        std_rank = float(row.get("std_rank") or 0.0)
        top3_freq = float(row.get("top3_freq") or 0.0)
        if std_rank >= 1.0 or (default_rank <= 3 and top3_freq < 0.5):
            unstable.append(
                {
                    "instance_id": row.get("instance_id"),
                    "default_rank": default_rank,
                    "std_rank": row.get("std_rank"),
                    "top3_freq": row.get("top3_freq"),
                }
            )
    return unstable


def _wording_hint(stability_class: str) -> str:
    if stability_class == "stable":
        return "Single-winner wording is allowed with audit caveats."
    if stability_class == "moderately_stable":
        return "Prefer top-3 set wording; avoid implying a unique winner."
    if stability_class == "insufficient":
        return "Insufficient candidates for robustness; avoid single-winner claims."
    return "Ranking is unstable; report candidates as hypotheses requiring validation."


def _interpret(top1_stability: float, jacc_mean: float, spear_mean: float, per_candidate: list[dict]) -> str:
    parts = []
    if top1_stability >= 0.70:
        parts.append(f"top-1 is stable across perturbations ({top1_stability:.0%} of seeds keep the same winner)")
    elif top1_stability >= 0.40:
        parts.append(f"top-1 is moderately stable ({top1_stability:.0%}); report as 'top-3 set' instead of single winner")
    else:
        parts.append(f"top-1 is unstable ({top1_stability:.0%}); deterministic sub-scores are too tied to single out a winner")
    parts.append(f"top-3 Jaccard vs default = {jacc_mean:.2f}")
    parts.append(f"mean Spearman to default ranks = {spear_mean:.2f}")
    n_tied = sum(1 for c in per_candidate if c["std_rank"] >= 1.0)
    if n_tied > 0:
        parts.append(f"{n_tied}/{len(per_candidate)} candidates have rank std >= 1.0 (effectively tied)")
    return "; ".join(parts) + "."


def _plot_heatmap(per_candidate: list[dict], n_seeds: int, out_path: Path) -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
    except Exception as e:  # noqa: BLE001
        logger.warning("[robustness_v2] matplotlib unavailable, skipping heatmap: %s", e)
        return
    n = len(per_candidate)
    mat = np.array([c["rank_histogram"] for c in per_candidate], dtype=float) / max(1, n_seeds)
    labels = [f"{c['instance_id']}\n{c['instance_name'][:28]}" for c in per_candidate]

    fig, ax = plt.subplots(figsize=(max(6, 1.4 * n + 2), max(3, 0.6 * n + 1.5)))
    im = ax.imshow(mat, aspect="auto", cmap="viridis", vmin=0.0, vmax=1.0)
    ax.set_xticks(range(n))
    ax.set_xticklabels([f"rank {i+1}" for i in range(n)])
    ax.set_yticks(range(n))
    ax.set_yticklabels(labels, fontsize=8)
    ax.set_title(f"Ranking robustness v2 (rank frequency over {n_seeds} weight+score perturbations)")
    for i in range(n):
        for j in range(n):
            v = mat[i, j]
            if v > 0.02:
                ax.text(j, i, f"{v:.2f}", ha="center", va="center",
                        color="white" if v < 0.55 else "black", fontsize=8)
    fig.colorbar(im, ax=ax, label="frequency")
    fig.tight_layout()
    fig.savefig(out_path, dpi=160)
    plt.close(fig)
    logger.info("[robustness_v2] wrote %s", out_path)
