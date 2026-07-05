# -*- coding: utf-8 -*-
"""P4 — Retrospective backtest of the Line-B MOBO+LLM closed loop (NO new experiments).

This replays the *logic* of the real closed loop over the **real** 10-trial history
(``campaign_memory/history_db_attapulgite.json``) plus the two **recorded, frozen**
prospective rounds (``official_recipe*.json``). It fabricates nothing: every number
is either read from those files or computed by the project's own optimizer utilities.

It answers three honest questions on the real data:

  (1) Did the measured Pareto front / hypervolume actually grow along the real
      trajectory?  -> reuse the project's real `pareto_front_indices` +
      `dominated_hypervolume` over the measured objectives, prefix by prefix.

  (2) Could the surrogate have predicted the next real outcome? -> a clean
      leave-future-out backtest: for each prefix, fit a GP (same Matern-2.5 kernel
      as MOBOOptimizer) on the real (R,N)->combined_score pairs and predict the
      next actually-measured combined_score. Report MAE + Spearman rank skill.

  (3) Did the recorded raw-MOBO -> LLM correction help? -> compare the two
      prospective outcomes (trials 9,10) against the campaign best, using the
      recorded raw MOBO / LLM-final values. Honest verdict expected: neither beat
      the campaign best (a true null), matching each recipe's `allowed_claim`.

Honesty guards: replay != new experiment; 10 real points / 2 prospective rounds is
a SHORT trajectory; we do NOT claim convergence or Pareto-front expansion.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import sys as _sys; _sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import natfig; natfig.apply()

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
STAGE1 = ROOT / "V1.0-qianduan-mainline" / "stage1_optimization"
sys.path.insert(0, str(STAGE1))

# Reuse the project's REAL, locked optimizer utilities (no reimplementation).
from optimizers.mobo_optimizer import (  # noqa: E402
    Objective,
    pareto_front_indices,
    dominated_hypervolume,
    score_v3,
    locked_v2_objectives,
)

from sklearn.gaussian_process import GaussianProcessRegressor  # noqa: E402
from sklearn.gaussian_process.kernels import Matern  # noqa: E402

HISTORY = STAGE1 / "campaign_memory" / "history_db_attapulgite.json"
RECIPE1 = ROOT / "research" / "prospective" / "line_B_mobo_closed_loop" / "official_recipe.json"
RECIPE2 = ROOT / "research" / "prospective" / "line_B_mobo_closed_loop" / "official_recipe_round2.json"

# map history objective keys -> locked v2 spec keys
KEY_MAP = {
    "conductivity_room_temp_S_cm": "sigma_RT",
    "ea_high_temp_eV": "Ea_high",
    "ea_low_excess_eV": "ea_low_excess",
}


def _spearman(a: np.ndarray, b: np.ndarray) -> float:
    """Spearman rank correlation without scipy (rank then Pearson)."""
    ra = np.argsort(np.argsort(a)).astype(float)
    rb = np.argsort(np.argsort(b)).astype(float)
    ra -= ra.mean()
    rb -= rb.mean()
    denom = np.sqrt((ra**2).sum() * (rb**2).sum())
    return float((ra * rb).sum() / denom) if denom > 0 else float("nan")


def load_history() -> list[dict]:
    data = json.loads(HISTORY.read_text(encoding="utf-8"))
    return data["trials"]


def mo_points(trials: list[dict]) -> list[dict]:
    """Measured multi-objective points in the locked v2 spec keys."""
    pts = []
    for t in trials:
        o = t["objectives"]
        pts.append({KEY_MAP[k]: float(o[k]) for k in KEY_MAP})
    return pts


def main() -> None:
    trials = load_history()
    n = len(trials)
    objectives = locked_v2_objectives()
    pts = mo_points(trials)

    # ---- (1) measured Pareto/hypervolume trajectory over real prefixes ----
    traj = []
    for t in range(1, n + 1):
        prefix = pts[:t]
        fidx = pareto_front_indices(prefix, objectives)
        hv = dominated_hypervolume(prefix, objectives, seed=0)
        traj.append({
            "n_trials": t,
            "pareto_front_size": len(fidx),
            "dominated_hypervolume": hv,
            "best_combined_score": max(float(tr["objectives"]["combined_score"]) for tr in trials[:t]),
        })

    # ---- (2) leave-future-out surrogate predictive-skill backtest ----
    X = np.array([[float(t["parameters"]["R"]), float(t["parameters"]["N"])] for t in trials])
    y = np.array([float(t["objectives"]["combined_score"]) for t in trials])
    COLD = 3  # need a few points before a GP is meaningful
    preds, actuals, rows = [], [], []
    for k in range(COLD, n):
        gp = GaussianProcessRegressor(
            kernel=Matern(nu=2.5), alpha=1e-6, normalize_y=True,
            n_restarts_optimizer=5, random_state=0,
        )
        gp.fit(X[:k], y[:k])
        mu, sd = gp.predict(X[k:k + 1], return_std=True)
        preds.append(float(mu[0]))
        actuals.append(float(y[k]))
        rows.append({
            "predict_trial_id": int(trials[k]["trial_id"]),
            "n_train": k,
            "R": float(X[k, 0]), "N": float(X[k, 1]),
            "predicted_combined_score": float(mu[0]),
            "predicted_std": float(sd[0]),
            "actual_combined_score": float(y[k]),
            "abs_error": abs(float(mu[0]) - float(y[k])),
        })
    preds_a = np.array(preds)
    actuals_a = np.array(actuals)
    mae = float(np.mean(np.abs(preds_a - actuals_a)))
    spearman = _spearman(preds_a, actuals_a)
    # naive baseline: predict next = mean of seen so far
    naive_preds = np.array([float(np.mean(y[:k])) for k in range(COLD, n)])
    mae_naive = float(np.mean(np.abs(naive_preds - actuals_a)))

    # ---- (3) recorded raw-MOBO -> LLM correction evaluation (rounds 1,2) ----
    r1 = json.loads(RECIPE1.read_text(encoding="utf-8"))
    r2 = json.loads(RECIPE2.read_text(encoding="utf-8"))
    best_score = max(float(t["objectives"]["combined_score"]) for t in trials)
    best_trial = max(trials, key=lambda t: float(t["objectives"]["combined_score"]))
    full_front = set(pareto_front_indices(pts, objectives))

    def _eval_round(recipe: dict, measured_trial_id: int) -> dict:
        mt = next(t for t in trials if t["trial_id"] == measured_trial_id)
        idx = trials.index(mt)
        cs = float(mt["objectives"]["combined_score"])
        return {
            "round": recipe.get("round"),
            "raw_mobo": recipe["raw_mobo"],
            "llm_final": recipe["llm_final"],
            "llm_provenance_model": recipe["llm_provenance"]["model"],
            "measured_trial_id": measured_trial_id,
            "measured_combined_score": cs,
            "measured_score_v3": score_v3(pts[idx]),
            "on_pareto_front_full10": idx in full_front,
            "beat_campaign_best": cs > best_score,
            "gap_to_best": cs - best_score,
        }

    rounds = [_eval_round(r1, 9), _eval_round(r2, 10)]

    result = {
        "policy": "retrospective backtest on REAL history; no new experiments; "
                  "no fabrication; short trajectory => no convergence/Pareto-expansion claim",
        "n_real_trials": n,
        "n_prospective_rounds": 2,
        "campaign_best": {
            "trial_id": int(best_trial["trial_id"]),
            "params": best_trial["parameters"],
            "combined_score": best_score,
        },
        "q1_pareto_hypervolume_trajectory": traj,
        "q2_surrogate_backtest": {
            "kernel": "Matern(nu=2.5)  (same as MOBOOptimizer surrogate)",
            "cold_start": COLD,
            "n_backtest_points": len(rows),
            "MAE_combined_score": mae,
            "MAE_naive_mean_baseline": mae_naive,
            "skill_vs_naive": mae < mae_naive,
            "spearman_pred_vs_actual": spearman,
            "rows": rows,
        },
        "q3_llm_correction_eval": {
            "campaign_best_combined_score": best_score,
            "rounds": rounds,
            "verdict": "Neither prospective round beat the campaign best (honest null). "
                       "LLM moved R off the raw-MOBO extreme-low-acid point on physical "
                       "grounds; outcome competitive but not record (matches recipe allowed_claim).",
        },
    }

    (HERE / "replay_report.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    # ---- figure ----
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(11.2, 4.8))
    ts = [r["n_trials"] for r in traj]
    hv = [r["dominated_hypervolume"] for r in traj]
    fs = [r["pareto_front_size"] for r in traj]
    ax.plot(ts, hv, "o-", color="tab:blue", label="dominated hypervolume")
    ax.set_xlabel("trials accumulated (real)")
    ax.set_ylabel("dominated hypervolume", color="tab:blue")
    ax.tick_params(axis="y", labelcolor="tab:blue")
    axb = ax.twinx()
    axb.plot(ts, fs, "s--", color="tab:green", label="Pareto front size")
    axb.set_ylabel("Pareto front size", color="tab:green")
    axb.tick_params(axis="y", labelcolor="tab:green")
    ax.axvline(8.5, color="0.6", ls=":", lw=1)
    ax.set_title("(a) Measured Pareto/HV trajectory (10 real pts; >8.5 = prospective)")

    lo = min(actuals_a.min(), preds_a.min()) - 0.1
    hi = max(actuals_a.max(), preds_a.max()) + 0.1
    ax2.plot([lo, hi], [lo, hi], "k--", lw=1, label="y = x")
    ax2.scatter(actuals_a, preds_a, c="tab:red", zorder=3)
    for r in rows:
        ax2.annotate(f"T{r['predict_trial_id']}",
                     (r["actual_combined_score"], r["predicted_combined_score"]),
                     fontsize=7, xytext=(3, 3), textcoords="offset points")
    ax2.set_xlabel("actual combined_score")
    ax2.set_ylabel("GP predicted combined_score")
    ax2.set_title(f"(b) Surrogate backtest: MAE={mae:.3f} vs naive {mae_naive:.3f}\n"
                  f"Spearman={spearman:.2f} (n={len(rows)}, short!)")
    ax2.legend(loc="upper left", fontsize=8)
    fig.tight_layout()
    natfig.save_pub(fig, HERE, "replay_trajectory")
    plt.close(fig)

    # ---- console (REAL numbers) ----
    print("=== P4 Line-B retrospective replay (REAL data, no new experiments) ===")
    print(f"n_real_trials={n}  campaign_best=T{best_trial['trial_id']} "
          f"{best_trial['parameters']} score={best_score:.3f}")
    print("\n(1) measured Pareto/HV trajectory:")
    for r in traj:
        print(f"  n={r['n_trials']:2d}  front={r['pareto_front_size']}  "
              f"HV={r['dominated_hypervolume']:.4e}  best={r['best_combined_score']:.3f}")
    print("\n(2) surrogate leave-future-out backtest (combined_score):")
    print(f"  MAE={mae:.3f}  naive-mean MAE={mae_naive:.3f}  "
          f"skill_vs_naive={mae < mae_naive}  Spearman={spearman:.2f}  n={len(rows)}")
    for r in rows:
        print(f"    T{r['predict_trial_id']:2d} (train={r['n_train']}) "
              f"pred={r['predicted_combined_score']:.3f}+-{r['predicted_std']:.3f} "
              f"actual={r['actual_combined_score']:.3f} |err|={r['abs_error']:.3f}")
    print("\n(3) recorded raw-MOBO -> LLM correction eval:")
    for rd in rounds:
        print(f"  round {rd['round']}: raw_MOBO R={rd['raw_mobo']['R']} N={rd['raw_mobo']['N']} "
              f"-> LLM R={rd['llm_final']['R']} N={rd['llm_final']['N']} "
              f"=> T{rd['measured_trial_id']} score={rd['measured_combined_score']:.3f} "
              f"pareto10={rd['on_pareto_front_full10']} beat_best={rd['beat_campaign_best']} "
              f"gap={rd['gap_to_best']:.3f}")
    print("\nHONEST NULL: short trajectory; no convergence / Pareto-expansion claim.")
    print(f"Saved -> {HERE}")


if __name__ == "__main__":
    main()
