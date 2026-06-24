# -*- coding: utf-8 -*-
"""噪声感知 MOBO（M2-3，特性开关）。

现有 MOBOOptimizer(ParEGO) 用 skopt GP 但 alpha 固定为 1e-6（视观测无噪），无法消费
M2-2 的逐观测方差。本模块提供噪声感知后端,可由 `optimizer_backend` 选择:

  * legacy            -> 现有 MOBOOptimizer（不变,默认)
  * noise_aware_skopt -> NoiseAwareParEGO(本模块):skopt GP 逐点 alpha=观测方差 +
                         P_valid(x) 可行性加权(失败实验不当低性能,而是降低采集) + 噪声来源标注
  * botorch_v2        -> build_botorch_mobo() → BotorchMOBO:真实多输出
                         SingleTaskGP(train_Yvar)+qLogNEHVI(真多目标 hypervolume),
                         **需 `pip install botorch torch`**;缺失则抛 ImportError(不伪造回退)

诚实标注:G1 前观测方差是 CROSS_SYSTEM_PROXY(LRS 代理);G1 后应换 LINE_B_LOCAL_DIRECT。
不改写冻结闭环;由 v2 runner 显式选择 backend。
"""
from __future__ import annotations

import math
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from .base_optimizer import BaseOptimizer
from .mobo_optimizer import (
    Objective, locked_v2_objectives, _to_minimization_matrix,
    parego_scalarize, pareto_front_indices,
)

OPTIMIZER_BACKENDS = ("legacy", "noise_aware_skopt", "botorch_v2")

try:  # 真实 botorch 路径的可用性探测(不安装、不伪造)
    import botorch  # noqa: F401
    import torch  # noqa: F401
    _BOTORCH_AVAILABLE = True
except Exception:
    _BOTORCH_AVAILABLE = False


def botorch_available() -> bool:
    return _BOTORCH_AVAILABLE


class NoiseAwareParEGO(BaseOptimizer):
    """噪声感知 ParEGO：skopt GP 逐点 alpha=观测方差 + P_valid 可行性加权。

    与 MOBOOptimizer 同构造签名(parameter_space / memory_manager),可直接替换。
    观测方差来源(优先级):trial.metadata['objective_variance'] → 构造时 default_obs_variance。
    """

    def __init__(
        self,
        parameter_space,
        memory_manager,
        objectives: Optional[Sequence[Objective]] = None,
        cold_start_threshold: int = 5,
        rho: float = 0.05,
        random_state: Optional[int] = None,
        default_obs_variance: float = 1e-3,
        noise_source: str = "CROSS_SYSTEM_PROXY",
        n_candidates: int = 4000,
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
        self.default_obs_variance = float(default_obs_variance)
        self.noise_source = noise_source
        self.n_candidates = int(n_candidates)
        self._last_info: Dict[str, Any] = {}

    # -- history → (X, P, variances, valid_mask) -------------------------- #
    def _extract(self, param_names: List[str]):
        X: List[List[float]] = []
        P: List[Dict[str, float]] = []
        var: List[float] = []
        X_all: List[List[float]] = []
        valid: List[int] = []
        for t in self.memory_manager.get_history():
            params = t.get("parameters") or {}
            try:
                x_row = [float(params[name]) for name in param_names]
            except (KeyError, TypeError, ValueError):
                continue
            objs = t.get("objectives") or {}
            is_valid = all(o.key in objs for o in self.objectives)
            X_all.append(x_row)
            valid.append(1 if is_valid else 0)
            if not is_valid:
                continue
            X.append(x_row)
            P.append({o.key: float(objs[o.key]) for o in self.objectives})
            md = t.get("metadata") or {}
            v = md.get("objective_variance")
            var.append(float(v) if isinstance(v, (int, float)) and v > 0 else self.default_obs_variance)
        return X, P, var, X_all, valid

    def _bounds(self) -> List[Tuple[float, float]]:
        return [tuple(b) for b in self.parameter_space.get_bounds()]

    def _normalize(self, X: np.ndarray, bounds) -> np.ndarray:
        lo = np.array([b[0] for b in bounds]); hi = np.array([b[1] for b in bounds])
        span = np.where(hi > lo, hi - lo, 1.0)
        return (X - lo) / span

    def _p_valid(self, X_all, valid, cand_norm, bounds):
        """可行性概率 P_valid(x):失败实验降低采集而非当低性能。全有效则恒 1。"""
        if not X_all or len(set(valid)) < 2:
            return np.ones(len(cand_norm))
        try:
            from sklearn.linear_model import LogisticRegression
            Xn = self._normalize(np.asarray(X_all, float), bounds)
            clf = LogisticRegression(max_iter=1000).fit(Xn, np.asarray(valid))
            return clf.predict_proba(cand_norm)[:, list(clf.classes_).index(1)]
        except Exception:
            return np.ones(len(cand_norm))

    def suggest_next(self) -> Dict[str, Any]:
        param_names = list(self.parameter_space.campaign_config.parameters.keys())
        bounds = self._bounds()
        X, P, var, X_all, valid = self._extract(param_names)

        # 候选采样(归一空间均匀)
        cand_norm = self._rng.random((self.n_candidates, len(bounds)))
        lo = np.array([b[0] for b in bounds]); hi = np.array([b[1] for b in bounds])
        cand_real = lo + cand_norm * (hi - lo)

        if len(P) < self.threshold:
            idx = int(self._rng.integers(self.n_candidates))
            self._last_info = {"mode": "cold_start", "n_train_points": len(P),
                               "noise_aware": True, "noise_source": self.noise_source}
            suggestion = dict(zip(param_names, cand_real[idx].tolist()))
            return self.parameter_space.decode_discrete_indices(suggestion)

        # ParEGO 标量化 + 噪声感知 GP
        from skopt.learning import GaussianProcessRegressor
        from sklearn.gaussian_process.kernels import Matern

        Xn = self._normalize(np.asarray(X, float), bounds)
        Y_min = _to_minimization_matrix(P, self.objectives)
        weights = self._rng.dirichlet(np.ones(len(self.objectives)))
        y = parego_scalarize(Y_min, weights, rho=self.rho)        # 越小越好
        alpha = np.asarray(var, float)                            # 逐点观测方差(噪声感知核心)

        gp = GaussianProcessRegressor(kernel=Matern(nu=2.5), alpha=alpha,
                                      normalize_y=True, n_restarts_optimizer=3,
                                      random_state=self.random_state)
        gp.fit(Xn, y)
        mu, sd = gp.predict(cand_norm, return_std=True)
        best = float(np.min(y))
        # EI(最小化):improvement = best - mu
        sd = np.maximum(sd, 1e-9)
        z = (best - mu) / sd
        from scipy.stats import norm
        ei = (best - mu) * norm.cdf(z) + sd * norm.pdf(z)
        ei = np.maximum(ei, 0.0)

        # P_valid 可行性加权
        p_valid = self._p_valid(X_all, valid, cand_norm, bounds)
        acq = ei * p_valid

        idx = int(np.argmax(acq))
        self._last_info = {
            "mode": "noise_aware_parego",
            "n_train_points": len(P),
            "noise_aware": True,
            "noise_source": self.noise_source,
            "mean_obs_variance": float(np.mean(alpha)),
            "weights": [float(w) for w in weights],
            "pareto_front_size": len(pareto_front_indices(P, self.objectives)),
            "feasibility_weighting_active": bool(len(set(valid)) >= 2),
        }
        suggestion = dict(zip(param_names, cand_real[idx].tolist()))
        return self.parameter_space.decode_discrete_indices(suggestion)

    def get_model_prediction(self, params: Dict[str, Any]) -> None:
        return None

    def get_provenance(self) -> Dict[str, Any]:
        return {
            "optimizer": "NoiseAwareParEGO",
            "backend": "noise_aware_skopt",
            "method": "ParEGO_augmented_tchebycheff_noise_aware",
            "reference": "Knowles 2006 + per-observation noise (skopt GP alpha)",
            "surrogate_model": "GaussianProcessRegressor(Matern2.5, per-point alpha)",
            "noise_aware": True,
            "default_obs_variance": self.default_obs_variance,
            "objectives": [{"key": o.key, "direction": o.direction} for o in self.objectives],
            **self._last_info,
        }


class BotorchMOBO(NoiseAwareParEGO):
    """真实 botorch 后端:多输出 SingleTaskGP(train_Yvar) + qLogNEHVI。

    相对 NoiseAwareParEGO(ParEGO 标量化)的升级:**真多目标 hypervolume 采集**,
    并把 M2-2 的逐观测方差作为 `train_Yvar` 直接喂进高斯过程(异方差噪声),
    用 qLogNoisyExpectedHypervolumeImprovement 在含噪历史上选下一点。

    诚实标注(同 NoiseAwareParEGO):G1 前 train_Yvar 来源是 CROSS_SYSTEM_PROXY;
    单一标量观测方差按目标广播(缺逐目标方差时的近似),provenance 显式记 noise_source。
    复用父类的历史抽取 / 边界 / 归一化逻辑,仅重写 suggest_next / get_provenance。
    """

    def _ref_point(self, Y_max: "np.ndarray", margin: float = 0.1) -> "np.ndarray":
        """参考点:比每个目标的最差观测再差一个 margin(最大化空间,越大越好)。"""
        worst = Y_max.min(axis=0)
        span = np.where(Y_max.max(axis=0) > worst, Y_max.max(axis=0) - worst, 1.0)
        return worst - margin * span

    def suggest_next(self) -> Dict[str, Any]:
        if not _BOTORCH_AVAILABLE:
            raise ImportError(
                "botorch backend requires `pip install botorch torch`."
            )
        param_names = list(self.parameter_space.campaign_config.parameters.keys())
        bounds = self._bounds()
        X, P, var, X_all, valid = self._extract(param_names)

        lo = np.array([b[0] for b in bounds], float)
        hi = np.array([b[1] for b in bounds], float)

        # 冷启动:训练点不足,均匀采样一个(与 NoiseAwareParEGO 行为一致)
        if len(P) < self.threshold:
            cand = lo + self._rng.random(len(bounds)) * (hi - lo)
            self._last_info = {"mode": "cold_start", "n_train_points": len(P),
                               "noise_aware": True, "noise_source": self.noise_source,
                               "backend": "botorch_v2"}
            return self.parameter_space.decode_discrete_indices(
                dict(zip(param_names, cand.tolist())))

        import torch
        from botorch.models import SingleTaskGP
        from botorch.models.transforms.input import Normalize
        from botorch.models.transforms.outcome import Standardize
        from botorch.fit import fit_gpytorch_mll
        from gpytorch.mlls import ExactMarginalLogLikelihood
        from botorch.acquisition.multi_objective.logei import (
            qLogNoisyExpectedHypervolumeImprovement,
        )
        from botorch.optim import optimize_acqf
        from botorch.sampling.normal import SobolQMCNormalSampler

        torch.manual_seed(self.random_state)
        dtype = torch.double

        # 目标转最大化形式:sigma↑ 保持,ea↓ 取负 → Y_max 越大越好
        Y_max = np.empty((len(P), len(self.objectives)), float)
        for j, o in enumerate(self.objectives):
            col = np.array([row[o.key] for row in P], float)
            Y_max[:, j] = col if o.direction == "maximize" else -col

        X_t = torch.tensor(np.asarray(X, float), dtype=dtype)
        Y_t = torch.tensor(Y_max, dtype=dtype)
        # 逐观测方差(异方差);单标量按目标广播(诚实近似,见类 docstring)
        Yvar_t = torch.tensor(
            np.tile(np.asarray(var, float).reshape(-1, 1), (1, len(self.objectives))),
            dtype=dtype,
        ).clamp_min(1e-9)
        bounds_t = torch.tensor(np.vstack([lo, hi]), dtype=dtype)

        model = SingleTaskGP(
            X_t, Y_t, train_Yvar=Yvar_t,
            input_transform=Normalize(d=X_t.shape[1], bounds=bounds_t),
            outcome_transform=Standardize(m=Y_t.shape[1]),
        )
        mll = ExactMarginalLogLikelihood(model.likelihood, model)
        fit_gpytorch_mll(mll)

        ref_point = torch.tensor(self._ref_point(Y_max), dtype=dtype)
        sampler = SobolQMCNormalSampler(sample_shape=torch.Size([128]))
        acqf = qLogNoisyExpectedHypervolumeImprovement(
            model=model, ref_point=ref_point, X_baseline=X_t,
            sampler=sampler, prune_baseline=True,
        )
        candidate, _ = optimize_acqf(
            acq_function=acqf, bounds=bounds_t, q=1,
            num_restarts=10, raw_samples=256,
        )
        cand = candidate.detach().cpu().numpy().reshape(-1)

        self._last_info = {
            "mode": "botorch_qlognehvi",
            "backend": "botorch_v2",
            "n_train_points": len(P),
            "noise_aware": True,
            "noise_source": self.noise_source,
            "mean_obs_variance": float(np.mean(var)),
            "pareto_front_size": len(pareto_front_indices(P, self.objectives)),
            "ref_point": [float(v) for v in ref_point.tolist()],
            "botorch_version": getattr(__import__("botorch"), "__version__", "unknown"),
        }
        return self.parameter_space.decode_discrete_indices(
            dict(zip(param_names, cand.tolist())))

    def get_provenance(self) -> Dict[str, Any]:
        return {
            "optimizer": "BotorchMOBO",
            "backend": "botorch_v2",
            "method": "qLogNEHVI (true multi-objective hypervolume, noisy)",
            "reference": "Daulton et al. 2021 (NEHVI) + Ament et al. 2023 (LogEI)",
            "surrogate_model": "SingleTaskGP(train_Yvar) multi-output, Standardize+Normalize",
            "noise_aware": True,
            "default_obs_variance": self.default_obs_variance,
            "objectives": [{"key": o.key, "direction": o.direction} for o in self.objectives],
            **self._last_info,
        }


def build_botorch_mobo(parameter_space=None, memory_manager=None, *args, **kwargs):
    """真实 botorch 后端:SingleTaskGP(train_Yvar)+qLogNEHVI。

    需 `pip install botorch torch`;未安装则抛 ImportError(不伪造回退、不静默降级)。
    """
    if not _BOTORCH_AVAILABLE:
        raise ImportError(
            "botorch backend requires `pip install botorch torch`. "
            "It is intentionally NOT auto-installed (torch is a heavy dependency). "
            "Use backend='noise_aware_skopt' for a noise-aware MOBO on the existing stack."
        )
    return BotorchMOBO(parameter_space, memory_manager, *args, **kwargs)


def build_noise_aware_optimizer(backend: str, parameter_space, memory_manager, **kwargs):
    """按 backend 选择优化器(特性开关)。"""
    if backend == "legacy":
        from .mobo_optimizer import MOBOOptimizer
        return MOBOOptimizer(parameter_space, memory_manager,
                             cold_start_threshold=kwargs.get("cold_start_threshold", 5),
                             random_state=kwargs.get("random_state"))
    if backend == "noise_aware_skopt":
        return NoiseAwareParEGO(parameter_space, memory_manager, **kwargs)
    if backend == "botorch_v2":
        return build_botorch_mobo(parameter_space, memory_manager, **kwargs)
    raise ValueError(f"unknown optimizer_backend '{backend}'; expected {OPTIMIZER_BACKENDS}")
