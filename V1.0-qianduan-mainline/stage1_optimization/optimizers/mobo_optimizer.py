"""Multi-objective Bayesian optimization (Tier 3 / v2 capability upgrade).

This module is an **independent v2 capability**. It is intentionally NOT wired
into the frozen single-objective closed loop (`bayesian_opt.py` /
`closed_loop/`), so it cannot change any frozen campaign result. It exists so a
future ``attapulgite_aice_v2_locked`` campaign can pursue a Pareto front instead
of the historical scalar ``combined_score``.

It implements the objective contract locked in
``experiments/three_pillars/pillar3_eis_in_the_loop/bo_v2_objective_spec_20260527.md``:

  * ``sigma_RT``       maximize  (near-room-temperature proton conductivity)
  * ``Ea_high``        minimize  (high-segment apparent activation energy, eV)
  * ``ea_low_excess``  minimize  (low-temperature degradation penalty, eV)

Two layers are provided:

1. Pure Pareto utilities (dependency-free): dominance, Pareto-front extraction,
   ``score_v3`` secondary scalar, and a Monte-Carlo dominated-hypervolume
   estimator. These are deterministic and unit-testable without any optimizer.

2. :class:`MOBOOptimizer`, a ParEGO-style suggester (Knowles 2006): each call
   draws a random weight vector, builds an augmented Tchebycheff scalarization of
   the normalized historical objectives, and fits the existing skopt GP backend
   on that scalar to propose the next design point. This reuses ``scikit-optimize``
   (already a project dependency) rather than pulling in botorch.

No timestamps, no fabricated results: everything is derived from the supplied
history and a (optionally fixed) random seed.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from .base_optimizer import BaseOptimizer


# --------------------------------------------------------------------------- #
# Objective model + Pareto utilities (pure, dependency-free)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Objective:
    """A single optimization objective.

    Attributes:
        key: the key inside each trial's ``objectives`` dict.
        direction: ``"max"`` or ``"min"``.
    """

    key: str
    direction: str

    def __post_init__(self) -> None:
        if self.direction not in ("max", "min"):
            raise ValueError(f"direction must be 'max' or 'min', got {self.direction!r}")


def locked_v2_objectives(
    sigma_key: str = "sigma_RT",
    ea_high_key: str = "Ea_high",
    ea_low_excess_key: str = "ea_low_excess",
) -> List[Objective]:
    """Return the 3 objectives from the locked v2 objective spec."""
    return [
        Objective(sigma_key, "max"),
        Objective(ea_high_key, "min"),
        Objective(ea_low_excess_key, "min"),
    ]


def _better_or_equal(a: float, b: float, direction: str) -> bool:
    return a >= b if direction == "max" else a <= b


def _strictly_better(a: float, b: float, direction: str) -> bool:
    return a > b if direction == "max" else a < b


def dominates(a: Dict[str, float], b: Dict[str, float], objectives: Sequence[Objective]) -> bool:
    """True if point ``a`` Pareto-dominates point ``b`` under ``objectives``.

    Matches the locked spec rule: ``a`` is at least as good as ``b`` on every
    objective and strictly better on at least one.
    """
    at_least_as_good = all(
        _better_or_equal(a[o.key], b[o.key], o.direction) for o in objectives
    )
    strictly_better = any(
        _strictly_better(a[o.key], b[o.key], o.direction) for o in objectives
    )
    return at_least_as_good and strictly_better


def pareto_front_indices(
    points: Sequence[Dict[str, float]], objectives: Sequence[Objective]
) -> List[int]:
    """Indices of non-dominated points (the Pareto front)."""
    front: List[int] = []
    for i, pi in enumerate(points):
        dominated = False
        for j, pj in enumerate(points):
            if i == j:
                continue
            if dominates(pj, pi, objectives):
                dominated = True
                break
        if not dominated:
            front.append(i)
    return front


def score_v3(
    point: Dict[str, float],
    sigma_key: str = "sigma_RT",
    ea_high_key: str = "Ea_high",
    ea_low_excess_key: str = "ea_low_excess",
) -> float:
    """Secondary scalar summary from the locked spec.

    ``score_v3 = log10(sigma_RT) - 1.0 * Ea_high - 0.2 * ea_low_excess``.
    The spec explicitly marks this as a *secondary* summary; the Pareto
    interpretation is primary.
    """
    sigma = float(point[sigma_key])
    if sigma <= 0:
        raise ValueError("sigma_RT must be positive for log10 in score_v3")
    return math.log10(sigma) - 1.0 * float(point[ea_high_key]) - 0.2 * float(point[ea_low_excess_key])


def annotate_pareto(
    points: Sequence[Dict[str, float]], objectives: Sequence[Objective]
) -> List[Dict[str, Any]]:
    """Tag each point with ``pareto_status`` and (when computable) ``score_v3``."""
    front = set(pareto_front_indices(points, objectives))
    keys = {o.key for o in objectives}
    out: List[Dict[str, Any]] = []
    for i, p in enumerate(points):
        row: Dict[str, Any] = {**p, "pareto_status": "pareto" if i in front else "dominated"}
        if {"sigma_RT", "Ea_high", "ea_low_excess"}.issubset(keys):
            try:
                row["score_v3"] = score_v3(p)
            except (KeyError, ValueError):
                row["score_v3"] = None
        out.append(row)
    return out


def _to_minimization_matrix(
    points: Sequence[Dict[str, float]], objectives: Sequence[Objective]
) -> np.ndarray:
    """Return an (n, m) matrix where every column is to be MINIMIZED.

    ``max`` objectives are negated so the whole matrix is minimization-sense.
    """
    rows = []
    for p in points:
        row = []
        for o in objectives:
            v = float(p[o.key])
            row.append(-v if o.direction == "max" else v)
        rows.append(row)
    return np.asarray(rows, dtype=float)


def dominated_hypervolume(
    points: Sequence[Dict[str, float]],
    objectives: Sequence[Objective],
    ref_point: Optional[Sequence[float]] = None,
    n_samples: int = 20000,
    seed: int = 0,
) -> float:
    """Monte-Carlo estimate of the dominated hypervolume (minimization sense).

    The Pareto front is mapped to minimization space (negating ``max``
    objectives). ``ref_point`` must be a worse-than-all point in that same
    minimization space; if omitted it is derived from the data with a 10% margin.
    Deterministic for a fixed ``seed``. Returned value is in the (transformed)
    objective units' product space and is only meaningful as a *relative*
    progress metric across rounds.
    """
    if not points:
        return 0.0
    Y = _to_minimization_matrix(points, objectives)
    front_idx = pareto_front_indices(points, objectives)
    F = Y[front_idx]
    mins = Y.min(axis=0)
    if ref_point is None:
        maxs = Y.max(axis=0)
        span = np.where(maxs > mins, maxs - mins, 1.0)
        ref = maxs + 0.1 * span
    else:
        ref = np.asarray(ref_point, dtype=float)
    box = ref - mins
    if np.any(box <= 0):
        return 0.0
    rng = np.random.default_rng(seed)
    samples = mins + rng.random((n_samples, Y.shape[1])) * box
    # a sample is "dominated" by the front if some front point is <= it on all dims
    dominated = np.zeros(n_samples, dtype=bool)
    for f in F:
        dominated |= np.all(f <= samples, axis=1)
    frac = float(dominated.mean())
    return frac * float(np.prod(box))


def parego_scalarize(Y_min: np.ndarray, weights: np.ndarray, rho: float = 0.05) -> np.ndarray:
    """Augmented Tchebycheff scalarization (ParEGO, Knowles 2006).

    Args:
        Y_min: (n, m) objectives already in MINIMIZATION sense.
        weights: (m,) non-negative weights summing to 1.
        rho: small augmentation coefficient.

    Returns:
        (n,) scalarized values to be MINIMIZED.
    """
    Y_min = np.asarray(Y_min, dtype=float)
    weights = np.asarray(weights, dtype=float)
    # normalize each column to [0, 1] to make weights comparable
    mins = Y_min.min(axis=0)
    maxs = Y_min.max(axis=0)
    span = np.where(maxs > mins, maxs - mins, 1.0)
    Z = (Y_min - mins) / span
    wz = Z * weights
    return wz.max(axis=1) + rho * wz.sum(axis=1)


# --------------------------------------------------------------------------- #
# ParEGO-based multi-objective optimizer
# --------------------------------------------------------------------------- #
class MOBOOptimizer(BaseOptimizer):
    """ParEGO-style multi-objective suggester over the skopt GP backend.

    Mirrors :class:`BayesianOptimizer`'s constructor (same ``parameter_space`` /
    ``memory_manager``) so it can be slotted into a v2 runner, but optimizes a
    randomly-scalarized multi-objective target instead of a single metric.
    """

    def __init__(
        self,
        parameter_space,
        memory_manager,
        objectives: Optional[Sequence[Objective]] = None,
        cold_start_threshold: int = 5,
        rho: float = 0.05,
        random_state: Optional[int] = None,
        fixed_weights: Optional[Sequence[float]] = None,
    ):
        self.parameter_space = parameter_space
        self.memory_manager = memory_manager
        self.objectives: List[Objective] = list(objectives) if objectives else locked_v2_objectives()
        self.threshold = cold_start_threshold
        self.rho = rho
        if random_state is None:
            random_state = int(time.perf_counter() * 1_000_000) % (2**31)
        self.random_state = random_state
        self._rng = np.random.default_rng(random_state)
        self._fixed_weights = (
            np.asarray(fixed_weights, dtype=float) if fixed_weights is not None else None
        )
        self.sk_space = self.parameter_space.get_skopt_space()
        self._last_weights: Optional[List[float]] = None
        self._last_info: Dict[str, Any] = {}

    # -- history extraction -------------------------------------------------- #
    def _extract_multiobjective_training(
        self, param_names: List[str]
    ) -> Tuple[List[List[float]], List[Dict[str, float]]]:
        X: List[List[float]] = []
        P: List[Dict[str, float]] = []
        for t in self.memory_manager.get_history():
            objs = t.get("objectives") or {}
            params = t.get("parameters") or {}
            if not all(o.key in objs for o in self.objectives):
                continue
            try:
                x_row = [float(params[name]) for name in param_names]
            except (KeyError, TypeError, ValueError):
                continue
            X.append(x_row)
            P.append({o.key: float(objs[o.key]) for o in self.objectives})
        return X, P

    def _draw_weights(self) -> np.ndarray:
        if self._fixed_weights is not None:
            w = self._fixed_weights
        else:
            # ParEGO: uniform random weights on the simplex (Dirichlet(1,...,1))
            w = self._rng.dirichlet(np.ones(len(self.objectives)))
        return np.asarray(w, dtype=float)

    def _create_sk_optimizer(self):
        try:
            from skopt import Optimizer as SkOptimizer
            from skopt.learning import GaussianProcessRegressor
            from sklearn.gaussian_process.kernels import Matern
        except ImportError as exc:  # pragma: no cover
            raise ImportError("MOBOOptimizer requires scikit-optimize") from exc

        gp = GaussianProcessRegressor(
            kernel=Matern(nu=2.5),
            alpha=1e-6,
            normalize_y=True,
            n_restarts_optimizer=5,
            random_state=self.random_state,
        )
        return SkOptimizer(
            dimensions=self.sk_space,
            base_estimator=gp,
            acq_func="EI",
            acq_optimizer="sampling",
            acq_optimizer_kwargs={"n_points": 10000},
            random_state=self.random_state,
            n_initial_points=self.threshold,
        )

    def suggest_next(self) -> Dict[str, Any]:
        param_names = list(self.parameter_space.campaign_config.parameters.keys())
        X, P = self._extract_multiobjective_training(param_names)

        sk_opt = self._create_sk_optimizer()
        weights = self._draw_weights()
        self._last_weights = [float(w) for w in weights]

        if len(P) < self.threshold:
            # cold start: explore via LHS/random ask (no scalarization yet)
            next_values = sk_opt.ask()
            self._last_info = {
                "mode": "cold_start",
                "n_train_points": len(P),
                "weights": self._last_weights,
            }
        else:
            Y_min = _to_minimization_matrix(P, self.objectives)
            scalar = parego_scalarize(Y_min, weights, rho=self.rho)
            sk_opt.tell([list(map(float, row)) for row in X], [float(s) for s in scalar])
            next_values = sk_opt.ask()
            self._last_info = {
                "mode": "parego",
                "n_train_points": len(P),
                "weights": self._last_weights,
                "pareto_front_size": len(pareto_front_indices(P, self.objectives)),
            }

        suggestion = dict(zip(param_names, next_values))
        suggestion = self.parameter_space.decode_discrete_indices(suggestion)
        return suggestion

    def get_model_prediction(self, params: Dict[str, Any]) -> None:
        """No single-objective scalar prediction exists for a multi-objective
        suggester. Returns ``None`` so the runner's optional prediction log is
        skipped (the loop guards with ``if prediction:``). Pareto status /
        ``score_v3`` are reported per-round from measured objectives instead.
        """
        return None

    def get_provenance(self) -> Dict[str, Any]:
        prov: Dict[str, Any] = {
            "optimizer": "MOBOOptimizer(ParEGO)",
            "method": "ParEGO_augmented_tchebycheff",
            "reference": "Knowles 2006",
            "surrogate_model": "GaussianProcessRegressor",
            "kernel": "Matern(nu=2.5)",
            "rho": self.rho,
            "random_state": self.random_state,
            "cold_start_threshold": self.threshold,
            "objectives": [{"key": o.key, "direction": o.direction} for o in self.objectives],
            "objective_spec_ref": "experiments/three_pillars/pillar3_eis_in_the_loop/bo_v2_objective_spec_20260527.md",
            **self._last_info,
        }
        return prov
