"""
Bayesian Optimizer
贝叶斯优化器：使用高斯过程回归进行策略寻优，自动处理冷启动
"""
import numpy as np
import time
from typing import Dict, Any, List, Optional
from .base_optimizer import BaseOptimizer
from canonical_input.design_space import ParameterSpace
from campaign_memory.memory_manager import MemoryManager


class BayesianOptimizer(BaseOptimizer):
    """
    贝叶斯优化器：
    1. 数据不足时，自动退化为随机采样（冷启动策略）
    2. 数据充足时，使用高斯过程回归进行策略寻优
    
    核心特性：
    - 使用 Gaussian Process (GP) 作为代理模型
    - 使用 Expected Improvement (EI) 作为采集函数
    - 自动处理连续、离散、整数参数
    - 冷启动时使用随机采样或 Latin Hypercube Sampling
    """
    
    def __init__(
        self, 
        parameter_space: ParameterSpace, 
        memory_manager: MemoryManager, 
        cold_start_threshold: int = 5,
        acq_func: str = "EI",
        random_state: Optional[int] = None
    ):
        """
        初始化贝叶斯优化器
        
        Args:
            parameter_space: 参数空间定义
            memory_manager: 记忆管理器（提供历史数据）
            cold_start_threshold: 去重配方数 < 此阈值时走冷启动（默认 5，适合 2D R/N）
            acq_func: 采集函数 ("EI", "PI", "LCB")
            random_state: 随机种子。None=使用时间戳（推荐），整数=固定种子（可复现）
        """
        self.parameter_space = parameter_space
        self.memory_manager = memory_manager
        self.threshold = cold_start_threshold
        self.acq_func = acq_func
        
        # 使用高精度时间戳 + 历史数据量作为随机种子，确保每次运行都产生不同的探索序列
        # 这对于自驱动实验室的参数空间探索至关重要
        if random_state is None:
            # 使用 perf_counter() 获得更高精度（微秒级），避免连续调用时种子相同
            # 同时混入历史数据量，确保即使在同一秒内多次调用也能产生不同种子
            history_count = len(memory_manager.get_history())
            base_seed = int(time.perf_counter() * 1000000)
            random_state = (base_seed + history_count * 10000) % (2**31)
            print(f"[Bayesian Optimizer] Using dynamic random seed: {random_state} (history_count={history_count})")
        
        self.random_state = random_state
        
        # 获取 skopt 格式的搜索空间
        self.sk_space = self.parameter_space.get_skopt_space()
        
        # 缓存优化器实例（避免重复创建）
        self._sk_optimizer = None
        self.last_training_info: Dict[str, Any] = {}
        # Tier2 (issue 6 / B3): cache the most recent suggestion so get_provenance()
        # can persist its GP predicted_std into round_*_suggestion.json. The
        # termination evaluator's B3 rule reads bo_provenance.predicted_std; without
        # this it never had a value to read and stayed inert.
        self._last_suggestion: Optional[Dict[str, Any]] = None
    
    def _clip_training_X_to_space(
        self, X_train: List[List[float]], param_names: List[str]
    ) -> List[List[float]]:
        """
        将历史参数裁剪到 skopt 搜索空间内。
        Virtual Oracle 使用真实样品 R/N，可能略高于/低于战役 JSON 旧版边界，会导致 tell() 报错。
        """
        bounds = self.parameter_space.get_bounds()
        configs = list(self.parameter_space.campaign_config.parameters.items())
        clipped: List[List[float]] = []
        clip_events = []
        for row in X_train:
            new_row: List[float] = []
            for i, name in enumerate(param_names):
                cfg = configs[i][1]
                if cfg.get("type") != "continuous":
                    new_row.append(row[i])
                    continue
                lo, hi = bounds[i]
                v = float(row[i])
                vc = float(np.clip(v, lo, hi))
                if vc != v:
                    clip_events.append({
                        "parameter": name,
                        "original": v,
                        "clipped": vc,
                        "bounds": [lo, hi],
                    })
                    print(
                        f"[Bayesian Optimizer] 警告: 历史点 {name}={v} 超出搜索空间 "
                        f"[{lo}, {hi}]，已裁剪为 {vc}（与实样/战役边界不一致时请检查 campaigns JSON）"
                    )
                new_row.append(vc)
            clipped.append(new_row)
        self.last_training_info["clip_events"] = clip_events
        return clipped
    
    def _create_sk_optimizer(self):
        """
        按需创建 skopt 优化器实例
        
        Returns:
            scikit-optimize Optimizer 对象
            
        Raises:
            ImportError: scikit-optimize 未安装
        """
        try:
            from skopt import Optimizer as SkOptimizer
            from skopt.learning import GaussianProcessRegressor
            from sklearn.gaussian_process.kernels import Matern
        except ImportError:
            raise ImportError(
                "请安装 scikit-optimize: pip install scikit-optimize"
            )
        
        # 创建带噪声的 GP 模型（防止重复样品导致奇异矩阵）
        # skopt 0.10.x 不支持 base_estimator_kwargs，需要显式创建 GP 对象
        gp = GaussianProcessRegressor(
            kernel=Matern(nu=2.5),
            alpha=1e-6,  # 添加噪声，防止奇异矩阵
            normalize_y=True,  # 归一化目标值
            n_restarts_optimizer=5,
            random_state=self.random_state
        )
        
        # 使用 GP (高斯过程) 作为基学习器，EI (期望增量) 作为采集函数
        return SkOptimizer(
            dimensions=self.sk_space,
            base_estimator=gp,  # 传入 GP 对象而非字符串
            acq_func=self.acq_func,  # Expected Improvement
            acq_optimizer="sampling",  # 采集函数优化方式
            acq_optimizer_kwargs={"n_points": 10000},  # 增加采样点数（默认10000），提高 exploration
            random_state=self.random_state,
            n_initial_points=self.threshold  # 初始随机点数量
        )
    
    def suggest_next(self) -> Dict[str, Any]:
        """
        建议下一组参数
        
        Returns:
            参数字典，键为参数名，值为建议的参数值
            
        Raises:
            ValueError: 配置错误或数据异常
        """
        param_names = list(self.parameter_space.campaign_config.parameters.keys())
        param_names_t = tuple(param_names)
        objective_name = self.parameter_space.campaign_config.get_objective_target()
        goal = self.parameter_space.campaign_config.get_objective_goal()
        
        # 1. 检查是否为冷启动（按去重后的配方数，而非 trial 条数）
        n_distinct = self.memory_manager.count_distinct_parameter_sets(param_names_t)
        is_cold_start = self.memory_manager.is_cold_start(self.threshold, param_names_t)
        self.last_training_info = {
            "objective_name": objective_name,
            "objective_goal": goal,
            "cold_start": is_cold_start,
            "history_count": len(self.memory_manager.get_history()),
            "n_distinct_param_sets": n_distinct,
            "distinct_param_names": list(param_names_t),
            "n_train_points": 0,
            "clip_events": [],
        }

        if is_cold_start:
            print(
                f"[Cold Start] 去重后配方数 {n_distinct} < {self.threshold}，"
                f"执行随机采样（Latin Hypercube Sampling）。"
            )
            sk_opt = self._create_sk_optimizer()
            next_values = sk_opt.ask()
        else:
            print(
                f"[Bayesian Optimization] 正在基于 "
                f"{len(self.memory_manager.get_history())} 条历史、"
                f"{n_distinct} 个去重配方寻优。"
            )
            
            # 提取历史数据 X 和 y
            X_train, y_train = self.memory_manager.get_training_data(
                param_names, 
                objective_name
            )
            
            if not X_train or not y_train:
                raise ValueError(
                    f"无法提取训练数据。请检查历史记录中是否包含目标值 '{objective_name}'"
                )
            
            X_train = self._clip_training_X_to_space(X_train, param_names)
            self.last_training_info["n_train_points"] = len(X_train)
            
            # 如果目标是最大化，y 需要取负值（因为 skopt 默认最小化目标）
            if goal == "maximize":
                y_train = [-val for val in y_train]
            
            sk_opt = self._create_sk_optimizer()
            
            # 将所有历史数据告知优化器
            try:
                sk_opt.tell(X_train, y_train)
            except Exception as e:
                raise ValueError(
                    f"贝叶斯优化器训练失败: {e}\n"
                    f"X_train shape: {np.array(X_train).shape}, "
                    f"y_train shape: {np.array(y_train).shape}"
                )
            
            # 询问下一个建议点
            next_values = sk_opt.ask()
            
            # 缓存优化器实例（用于获取采集函数值等）
            self._sk_optimizer = sk_opt
        
        # 2. 将列表格式的结果转回字典
        suggestion = dict(zip(param_names, next_values))
        
        # 3. 解码离散参数（如果优化器返回的是索引）
        suggestion = self.parameter_space.decode_discrete_indices(suggestion)
        
        print(f"[Suggestion] 建议参数: {suggestion}")

        self._last_suggestion = dict(suggestion)
        return suggestion

    def get_provenance(self) -> Dict[str, Any]:
        """返回本次优化器配置与训练摘要，用于 recipe metadata。"""
        prov = {
            "optimizer": "skopt.Optimizer",
            "surrogate_model": "GaussianProcessRegressor",
            "kernel": "Matern(nu=2.5)",
            "alpha": 1e-6,
            "normalize_y": True,
            "n_restarts_optimizer": 5,
            "acq_func": self.acq_func,
            "acq_optimizer": "sampling",
            "acq_optimizer_n_points": 10000,
            "random_state": self.random_state,
            "cold_start_threshold": self.threshold,
            **self.last_training_info,
        }
        # Tier2 (B3): persist GP predicted_mean/std for the last suggestion so the
        # termination evaluator can act on convergence uncertainty. Only available
        # once a surrogate is trained (not cold start); stays absent otherwise.
        if self._last_suggestion is not None:
            try:
                prediction = self.get_model_prediction(self._last_suggestion)
            except Exception:  # pragma: no cover - defensive
                prediction = None
            if prediction is not None:
                mean, std = prediction
                prov["predicted_mean"] = float(mean)
                prov["predicted_std"] = float(std)
                prov["predicted_for"] = dict(self._last_suggestion)
        return prov
    
    def get_acquisition_function_value(self, params: Dict[str, Any]) -> Optional[float]:
        """Return the acquisition score for a proposed point, when available."""
        if self._sk_optimizer is None:
            return None

        try:
            from skopt.acquisition import gaussian_ei, gaussian_lcb, gaussian_pi

            param_names = list(self.parameter_space.campaign_config.parameters.keys())
            param_values = [params[name] for name in param_names]
            transformed = self._sk_optimizer.space.transform([param_values])
            if not self._sk_optimizer.models:
                return None
            model = self._sk_optimizer.models[-1]
            y_opt = min(self._sk_optimizer.yi) if self._sk_optimizer.yi else 0.0

            if self.acq_func == "EI":
                acq_value = gaussian_ei(transformed, model, y_opt=y_opt)
            elif self.acq_func == "PI":
                acq_value = gaussian_pi(transformed, model, y_opt=y_opt)
            elif self.acq_func == "LCB":
                acq_value = gaussian_lcb(transformed, model)
            else:
                return None
            return float(np.asarray(acq_value).ravel()[0])
        except Exception as e:
            print(f"Warning: could not compute acquisition value: {e}")
            return None

    def get_expected_improvement(self, params: Dict[str, Any]) -> Optional[float]:
        """
        获取期望改进值（Expected Improvement）
        
        Args:
            params: 参数字典
            
        Returns:
            EI 值，如果不可用则返回 None
        """
        if self.acq_func != "EI":
            print(f"警告: 当前采集函数为 {self.acq_func}，不是 EI")
        
        return self.get_acquisition_function_value(params)
    
    def get_model_prediction(self, params: Dict[str, Any]) -> Optional[tuple]:
        """
        获取高斯过程模型的预测值和不确定性
        
        Args:
            params: 参数字典
            
        Returns:
            (mean, std) 元组，如果模型未训练则返回 None
        """
        if self._sk_optimizer is None or self.memory_manager.is_cold_start(
            self.threshold, tuple(self.parameter_space.campaign_config.parameters.keys())
        ):
            return None
        
        try:
            # 将参数字典转换为列表
            param_names = list(self.parameter_space.campaign_config.parameters.keys())
            param_values = [params[name] for name in param_names]
            
            # 获取 GP 模型
            gp_model = self._sk_optimizer.models[-1]  # 最新的模型
            
            # 预测
            mean, std = gp_model.predict([param_values], return_std=True)
            
            # 如果目标是最大化，需要将预测值转回正值
            goal = self.parameter_space.campaign_config.get_objective_goal()
            if goal == "maximize":
                mean = -mean
            
            return float(mean[0]), float(std[0])
        except Exception as e:
            print(f"警告: 无法获取模型预测: {e}")
            return None
    
    def validate_suggestion(self, suggestion: Dict[str, Any]) -> bool:
        """
        验证建议的参数是否在合法范围内
        
        Args:
            suggestion: 建议的参数字典
            
        Returns:
            True 如果参数合法
        """
        try:
            self.parameter_space.campaign_config.validate_parameters(suggestion)
            return True
        except ValueError as e:
            print(f"❌ 参数验证失败: {e}")
            return False
