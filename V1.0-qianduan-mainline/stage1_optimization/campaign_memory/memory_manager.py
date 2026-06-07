"""
Campaign Memory Manager
实验战役记忆管理器：负责实验数据的持久化与冷启动逻辑
"""
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Set
from datetime import datetime


class MemoryManager:
    """
    实验战役记忆管理器：负责实验数据的持久化与冷启动逻辑
    
    职责：
    1. 持久化存储所有实验的参数和结果
    2. 提供冷启动检测（去重后的配方数不足时触发 LHS/随机采样）
    3. 为贝叶斯优化提供训练数据 (X, y)
    4. 查询历史最优实验
    """
    
    def __init__(self, db_path: str, campaign_name: str):
        """
        初始化记忆管理器
        
        Args:
            db_path: 数据库文件路径 (JSON)
            campaign_name: 实验战役名称
        """
        self.db_path = Path(db_path)
        self.campaign_name = campaign_name
        self._ensure_db_exists()
    
    def _ensure_db_exists(self) -> None:
        """初始化数据库文件，如果不存在则创建"""
        if not self.db_path.exists():
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._atomic_save_database({
                "campaign_name": self.campaign_name,
                "trials": [],
            })

    def _load_database(self) -> Dict[str, Any]:
        try:
            with open(self.db_path, 'r', encoding='utf-8-sig') as f:
                db = json.load(f)
        except json.JSONDecodeError as e:
            raise json.JSONDecodeError(
                f"数据库文件损坏: {self.db_path}",
                e.doc,
                e.pos
            )
        if "trials" not in db or not isinstance(db["trials"], list):
            raise ValueError(f"history_db 缺少 trials 列表: {self.db_path}")
        self._assert_campaign(db)
        return db

    def _atomic_save_database(self, db: Dict[str, Any]) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.db_path.with_name(f"{self.db_path.name}.tmp")
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(db, f, indent=2, ensure_ascii=False)
        tmp_path.replace(self.db_path)

    def _assert_campaign(self, db: Dict[str, Any]) -> None:
        existing = db.get("campaign_name")
        if existing is None:
            db["campaign_name"] = self.campaign_name
            return
        if existing != self.campaign_name:
            raise ValueError(
                f"history_db campaign mismatch: file={existing}, expected={self.campaign_name}"
            )

    def _find_duplicate_trial(
        self,
        db: Dict[str, Any],
        metadata: Optional[Dict[str, Any]],
    ) -> Optional[int]:
        if not metadata:
            return None
        sample_id = metadata.get("sample_id")
        input_bundle_hash = metadata.get("input_bundle_hash")
        for trial in db.get("trials", []):
            trial_meta = trial.get("metadata") or {}
            if sample_id and trial_meta.get("sample_id") == sample_id:
                trial_id = trial.get("trial_id")
                return int(trial_id) if trial_id is not None else None
            if input_bundle_hash and trial_meta.get("input_bundle_hash") == input_bundle_hash:
                trial_id = trial.get("trial_id")
                return int(trial_id) if trial_id is not None else None
        return None
    
    def add_trial(
        self, 
        parameters: Dict[str, Any], 
        objectives: Dict[str, float], 
        metadata: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        记录一次实验结果
        
        Args:
            parameters: 实验参数字典 (如 {"doping_concentration": 0.3, ...})
            objectives: 目标值字典 (如 {"conductivity_room_temp_S_cm": 1.2e-4})
            metadata: 可选的元数据 (如实验员、设备编号、原始数据路径等)
            
        Returns:
            trial_id: 新增实验的 ID
            
        Raises:
            json.JSONDecodeError: 数据库文件损坏
            IOError: 文件读写错误
        """
        db = self._load_database()
        duplicate_trial_id = self._find_duplicate_trial(db, metadata)
        if duplicate_trial_id is not None:
            return duplicate_trial_id
        
        trial_id = len(db["trials"]) + 1
        trial = {
            "trial_id": trial_id,
            "timestamp": datetime.now().isoformat(),
            "parameters": parameters,
            "objectives": objectives,
            "metadata": metadata or {}
        }
        db["trials"].append(trial)
        
        self._atomic_save_database(db)
        
        return trial_id
    
    def get_history(self) -> List[Dict[str, Any]]:
        """
        获取完整的历史实验列表
        
        Returns:
            实验列表，每个元素包含 trial_id, timestamp, parameters, objectives, metadata
        """
        try:
            return self._load_database()["trials"]
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            raise ValueError(f"无法读取历史数据: {e}")
    
    def get_training_data(
        self, 
        param_names: List[str], 
        objective_name: str
    ) -> Tuple[List[List[float]], List[float]]:
        """
        提取用于机器学习训练的 X (参数) 和 y (目标值)
        
        Args:
            param_names: 参数名称列表，必须与 Campaign Config 一致
            objective_name: 目标指标名称 (如 "conductivity_room_temp_S_cm")
            
        Returns:
            (X, y): X 是参数矩阵，y 是目标值列表
            
        Notes:
            - 只返回成功的实验（objectives 中包含目标值）
            - 参数顺序严格按照 param_names 排列
        """
        trials = self.get_history()
        X = []
        y = []
        
        for t in trials:
            # 确保只有成功的实验进入训练集
            if objective_name in t["objectives"]:
                try:
                    # 按照指定顺序提取参数
                    x_row = [t["parameters"][p] for p in param_names]
                    X.append(x_row)
                    y.append(t["objectives"][objective_name])
                except KeyError as e:
                    # 如果某个参数缺失，跳过这条记录
                    print(f"警告: Trial {t.get('trial_id', '?')} 缺少参数 {e}，已跳过")
                    continue
        
        return X, y

    def count_distinct_parameter_sets(
        self,
        param_names: Tuple[str, ...],
        decimals: int = 3,
    ) -> int:
        """历史中去重后的配方数量（对给定参数名做四舍五入后当同一配方）。

        仅统计 ``parameters`` 里能完整取出 ``param_names`` 且可转为 float 的 trial；
        缺字段或无法解析的条目跳过。
        """
        if not param_names:
            return len(self.get_history())
        seen: Set[Tuple[float, ...]] = set()
        for t in self.get_history():
            p = t.get("parameters") or {}
            try:
                key = tuple(round(float(p[name]), decimals) for name in param_names)
            except (KeyError, TypeError, ValueError):
                continue
            seen.add(key)
        return len(seen)

    def is_cold_start(
        self,
        threshold: int,
        param_names: Tuple[str, ...],
        decimals: int = 3,
    ) -> bool:
        """
        判断是否处于冷启动阶段（去重后的配方数不足以支撑 GP+EI）。

        Args:
            threshold: 最少需要多少个**互不重复**（按 decimals 合并）的参数点
            param_names: 参与去重的参数名，与战役 JSON 中 ``parameters`` 键一致
                         （凹凸棒 AiCE 为 ``("R", "N")``）。传空元组则退化为
                         ``len(history) < threshold``（兼容非 R/N 战役）。
            decimals: R、N 比较前四舍五入到的小数位

        Returns:
            True 时应走 LHS/随机探索；False 时用历史点训练 GP。
        """
        if not param_names:
            return len(self.get_history()) < threshold
        return self.count_distinct_parameter_sets(param_names, decimals) < threshold

    def get_best_trial(
        self, 
        objective_name: str, 
        goal: str = "maximize"
    ) -> Optional[Dict[str, Any]]:
        """
        获取历史最优实验
        
        Args:
            objective_name: 目标指标名称
            goal: "maximize" 或 "minimize"
            
        Returns:
            最优实验的完整记录，如果没有有效实验则返回 None
            
        Raises:
            ValueError: goal 参数不合法
        """
        if goal not in ["maximize", "minimize"]:
            raise ValueError(f"goal 必须是 'maximize' 或 'minimize'，当前值: {goal}")
        
        trials = [
            t for t in self.get_history() 
            if objective_name in t["objectives"]
        ]
        
        if not trials:
            return None
        
        if goal == "maximize":
            return max(trials, key=lambda x: x["objectives"][objective_name])
        else:
            return min(trials, key=lambda x: x["objectives"][objective_name])
    
    def get_statistics(self, objective_name: str) -> Dict[str, float]:
        """
        获取目标值的统计信息
        
        Args:
            objective_name: 目标指标名称
            
        Returns:
            包含 mean, std, min, max, count 的字典
        """
        trials = [
            t["objectives"][objective_name] 
            for t in self.get_history() 
            if objective_name in t["objectives"]
        ]
        
        if not trials:
            return {
                "count": 0,
                "mean": None,
                "std": None,
                "min": None,
                "max": None
            }
        
        import statistics
        
        return {
            "count": len(trials),
            "mean": statistics.mean(trials),
            "std": statistics.stdev(trials) if len(trials) > 1 else 0.0,
            "min": min(trials),
            "max": max(trials)
        }
    
    def export_for_visualization(self, output_path: Optional[str] = None) -> str:
        """
        导出数据用于可视化（如 Plotly、Matplotlib）
        
        Args:
            output_path: 可选的输出路径，如果为 None 则返回 JSON 字符串
            
        Returns:
            JSON 字符串或文件路径
        """
        data = {
            "campaign_name": self.campaign_name,
            "num_trials": len(self.get_history()),
            "trials": self.get_history()
        }
        
        if output_path:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return output_path
        else:
            return json.dumps(data, indent=2, ensure_ascii=False)
    
    def clear_history(self, confirm: bool = False) -> None:
        """
        清空所有历史数据（危险操作，需要确认）
        
        Args:
            confirm: 必须显式设置为 True 才能执行
            
        Raises:
            ValueError: 未确认操作
        """
        if not confirm:
            raise ValueError(
                "清空历史数据是危险操作，请设置 confirm=True"
            )
        
        self._atomic_save_database({
            "campaign_name": self.campaign_name,
            "trials": [],
        })
