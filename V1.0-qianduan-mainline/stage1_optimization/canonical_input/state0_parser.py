"""
Stage 0 Results Parser
解析 Stage 0 测试结果，提取目标指标用于优化

深度重构版本：
- 支持宽温域数据解析（aggregated_results.json）
- 支持 Arrhenius 分析结果解析（arrhenius_analysis.json）
- 支持基于公式的目标计算（eval with math module）
- (P-Stage1-C) 优先尝试读取新的 stage0_result_bundle.json，缺失时回退到 legacy 路径
"""
import ast
import hashlib
import json
import logging
import math
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


_ALLOWED_FORMULA_NODES = (
    ast.Expression,
    ast.BinOp,
    ast.UnaryOp,
    ast.Call,
    ast.Name,
    ast.Load,
    ast.Constant,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.Pow,
    ast.Mod,
    ast.USub,
    ast.UAdd,
    ast.Attribute,
)


def _safe_eval_formula(formula: str, variables: Dict[str, Any]) -> float:
    """Evaluate campaign objective formulas with an AST allowlist."""
    allowed_math = {
        name: getattr(math, name)
        for name in (
            "log",
            "log10",
            "exp",
            "sqrt",
            "sin",
            "cos",
            "tan",
            "fabs",
            "floor",
            "ceil",
        )
    }
    allowed_names: Dict[str, Any] = {"math": math, **allowed_math}
    allowed_names.update(variables)

    tree = ast.parse(formula, mode="eval")
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_FORMULA_NODES):
            raise ValueError(f"disallowed formula syntax: {type(node).__name__}")
        if isinstance(node, ast.Name) and node.id not in allowed_names:
            raise ValueError(f"unknown formula variable: {node.id}")
        if isinstance(node, ast.Attribute):
            if not isinstance(node.value, ast.Name) or node.value.id != "math":
                raise ValueError("only math.<function> attributes are allowed")
            if node.attr not in allowed_math and node.attr not in {"pi", "e"}:
                raise ValueError(f"disallowed math attribute: {node.attr}")
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                if func.id not in allowed_math:
                    raise ValueError(f"disallowed function call: {func.id}")
            elif isinstance(func, ast.Attribute):
                if not isinstance(func.value, ast.Name) or func.value.id != "math":
                    raise ValueError("only math.<function>() calls are allowed")
                if func.attr not in allowed_math:
                    raise ValueError(f"disallowed math function: {func.attr}")
            else:
                raise ValueError("disallowed formula call target")

    return float(eval(compile(tree, "<objective_formula>", "eval"), {"__builtins__": {}}, allowed_names))


def _probe_stage0_bundle(results_dir: Path) -> Optional[Path]:
    """在结果目录及上一级目录中查找 stage0_result_bundle.json。"""
    candidates = [
        results_dir / "stage0_result_bundle.json",
        results_dir.parent / "stage0_result_bundle.json",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def _bundle_to_legacy_aggregated(bundle: Dict[str, Any]) -> Dict[str, Any]:
    """把 Stage0ResultBundle.eis_points[] 投影回 legacy aggregated_results.json 形态。"""
    measurements = []
    for p in bundle.get("eis_points", []) or []:
        sigma = p.get("sigma_S_cm")
        T_K = p.get("T_K")
        T_C = p.get("T_C") if p.get("T_C") is not None else (T_K - 273.15 if T_K is not None else None)
        measurements.append({
            "filepath": p.get("scan_dir"),
            "temperature_C": T_C,
            "temperature_K": T_K,
            "status": p.get("status", "OK"),
            "kk_warning": bool(p.get("kk_warning")) if p.get("kk_warning") is not None else False,
            "rb_ohm": p.get("rb_ohm"),
            "conductivity_S_per_cm": sigma,
            "rb_method": p.get("rb_method"),
            "fit_quality": p.get("rb_confidence"),
            "success": (sigma is not None and sigma > 0 and p.get("status", "OK") == "OK"),
            "failure_reason": ";".join(p.get("quality_flags", []) or []) or None,
        })
    return {"measurements": measurements}


def _bundle_to_legacy_arrhenius(bundle: Dict[str, Any]) -> Dict[str, Any]:
    arr = bundle.get("arrhenius") or {}
    if not arr.get("success"):
        return {"success": False}
    if arr.get("segments"):
        return {
            "success": True,
            "best_model_type": arr.get("best_model_type"),
            "n_segments": arr.get("n_segments", len(arr.get("segments") or [])),
            "transition_temps_K": arr.get("transition_temps_K") or [],
            "segments": arr.get("segments") or [],
            "confidence": arr.get("confidence"),
        }
    eas = arr.get("ea_segments_eV") or []
    transitions = arr.get("transition_temps_K") or []
    segments = []
    for ea in eas:
        segments.append({"Ea_eV": ea, "n_points": 5, "temp_range_K": [None, None]})
    return {
        "success": True,
        "best_model_type": arr.get("best_model_type"),
        "n_segments": arr.get("n_segments", len(eas)),
        "transition_temps_K": transitions,
        "segments": segments,
        "confidence": arr.get("confidence"),
    }


class State0Parser:
    """
    Stage 0 结果解析器（深度重构版）
    
    职责：
    1. 从 stage0 的输出目录中读取测试结果（宽温域数据）
    2. 解析 Arrhenius 分析结果（活化能、相变温度）
    3. 提取丰富的物理特征（conductivity, Ea_high, Ea_low, transition_temps）
    4. 支持基于公式的目标计算（如 log10(σ) - 5.0 * Ea）
    5. 提取实验参数（R、N 等）
    6. 进行数据验证和清洗
    """
    
    def __init__(self, stage0_results_dir: str, campaign_config=None):
        """
        初始化解析器
        
        Args:
            stage0_results_dir: Stage 0 测试结果目录路径
            campaign_config: CampaignConfig 对象（可选，用于公式计算）
            
        Raises:
            FileNotFoundError: 结果目录不存在
        """
        self.results_dir = Path(stage0_results_dir)
        self.campaign_config = campaign_config
        self._cached_physical_features = None  # 缓存最近一次提取的物理特征
        self._parser_mode = "legacy"
        self._bundle_path: Optional[Path] = None
        self._bundle_validity_flags: List[str] = []
        self._stage0_data_validity: Dict[str, Any] = {}
        self._objective_invalid_reasons: List[str] = []
        self._parameter_invalid_reasons: List[str] = []
        
        if not self.results_dir.exists():
            raise FileNotFoundError(
                f"Stage 0 结果目录不存在: {stage0_results_dir}"
            )
        
        logger.info(f"Stage 0 解析器初始化 | 目录: {self.results_dir}")
    
    def extract_objective_metrics(
        self,
        aggregated_results_file: str = "aggregated_results.json",
        arrhenius_file: str = "arrhenius_analysis.json"
    ) -> Dict[str, float]:
        """
        提取目标指标（深度重构版：支持宽温域数据 + Arrhenius 分析 + 公式计算）
        
        Args:
            aggregated_results_file: 汇总结果文件名
            arrhenius_file: Arrhenius 分析结果文件名
            
        Returns:
            目标指标字典，例如:
            {
                "conductivity_room_temp_S_cm": 1.5e-4,
                "ea_high_temp_eV": 0.28,
                "ea_low_temp_eV": 0.45,
                "combined_score": -3.1  (如果有公式)
            }
            
        Raises:
            FileNotFoundError: 结果文件不存在
            json.JSONDecodeError: JSON 格式错误
            ValueError: 数据格式不符合预期
        """
        # P-Stage1-C: 优先尝试新版 stage0_result_bundle.json
        bundle_path = _probe_stage0_bundle(self.results_dir)
        aggregated_data: Optional[Dict[str, Any]] = None
        arrhenius_data: Optional[Dict[str, Any]] = None
        self._objective_invalid_reasons = []
        self._stage0_data_validity = {}

        if bundle_path is not None:
            logger.info(f"📦 检测到 Stage0 result bundle，优先使用: {bundle_path}")
            try:
                with open(bundle_path, "r", encoding="utf-8") as f:
                    bundle = json.load(f)
                aggregated_data = _bundle_to_legacy_aggregated(bundle)
                arrhenius_data = _bundle_to_legacy_arrhenius(bundle) or None
                self._parser_mode = "bundle"
                self._bundle_path = bundle_path
                bundle_limitations = bundle.get("limitations") or []
                if bundle_limitations:
                    self._bundle_validity_flags.extend(bundle_limitations)
                self._stage0_data_validity = bundle.get("data_validity") or {}
                if self._stage0_data_validity.get("objective_ready") is False:
                    reasons = self._stage0_data_validity.get("invalid_reasons") or [
                        "stage0_bundle_objective_not_ready"
                    ]
                    for reason in reasons:
                        self._mark_objective_invalid(str(reason))
            except Exception as e:
                logger.warning(f"⚠️ 读取 stage0_result_bundle 失败，回退到 legacy 路径: {e}")
                aggregated_data = None
                arrhenius_data = None
                self._parser_mode = "legacy"

        if aggregated_data is None:
            # Legacy: 读取 aggregated_results.json
            results_file = self.results_dir / aggregated_results_file
            if not results_file.exists():
                raise FileNotFoundError(
                    f"汇总结果文件不存在: {results_file}\n"
                    f"请确保 Stage 0 已完成测试并生成结果文件，或提供 stage0_result_bundle.json"
                )
            logger.info(f"📂 读取宽温域测试结果 (legacy): {results_file}")
            try:
                with open(results_file, 'r', encoding='utf-8') as f:
                    aggregated_data = json.load(f)
            except json.JSONDecodeError as e:
                raise json.JSONDecodeError(
                    f"结果文件 JSON 格式错误: {results_file}",
                    e.doc,
                    e.pos
                ) from e

        if arrhenius_data is None:
            arrhenius_path = self.results_dir / arrhenius_file
            if arrhenius_path.exists():
                logger.info(f"📂 读取 Arrhenius 分析结果 (legacy): {arrhenius_path}")
                try:
                    with open(arrhenius_path, 'r', encoding='utf-8') as f:
                        arrhenius_data = json.load(f)
                except json.JSONDecodeError as e:
                    logger.warning(f"⚠️ Arrhenius 文件 JSON 格式错误: {e}")
                    arrhenius_data = None
            else:
                logger.warning(f"⚠️ Arrhenius 分析文件不存在: {arrhenius_path}")
        
        # Step 3: 提取物理特征
        physical_features = self._extract_physical_features(
            aggregated_data, 
            arrhenius_data
        )
        
        # 缓存物理特征，供后续使用
        self._cached_physical_features = physical_features
        
        logger.info(f"✅ 成功提取 {len(physical_features)} 个物理特征")
        for key, value in physical_features.items():
            if isinstance(value, (int, float)):
                logger.info(f"  - {key}: {value:.4e}")
            elif isinstance(value, list):
                logger.info(f"  - {key}: {value}")
        
        # Step 4: 基于公式计算目标值（如果有）
        metrics = self._compute_objective_with_formula(physical_features)
        
        # Step 5: 验证指标有效性
        self._validate_metrics(metrics)
        
        return metrics
    
    def get_parser_mode(self) -> str:
        """返回当前 parse 路径：'bundle' (新版) 或 'legacy' (旧 aggregated_results.json)。"""
        return self._parser_mode

    def get_bundle_path(self) -> Optional[str]:
        return str(self._bundle_path) if self._bundle_path else None

    def get_validity_flags(self) -> List[str]:
        flags = list(self._bundle_validity_flags)
        flags.extend(self._objective_invalid_reasons)
        flags.extend(self._parameter_invalid_reasons)
        return list(dict.fromkeys(flags))

    def get_stage0_data_validity(self) -> Dict[str, Any]:
        return dict(self._stage0_data_validity)

    def get_input_bundle_hash(self) -> Optional[str]:
        if self._bundle_path and self._bundle_path.exists():
            return hashlib.sha256(self._bundle_path.read_bytes()).hexdigest()
        fallback_parts: List[bytes] = []
        for name in ("aggregated_results.json", "arrhenius_analysis.json", "experiment_metadata.json"):
            path = self.results_dir / name
            if path.exists():
                fallback_parts.append(path.read_bytes())
        if not fallback_parts:
            return None
        digest = hashlib.sha256()
        for part in fallback_parts:
            digest.update(part)
        return digest.hexdigest()

    def _mark_objective_invalid(self, reason: str) -> None:
        if reason and reason not in self._objective_invalid_reasons:
            self._objective_invalid_reasons.append(reason)

    def _mark_parameters_invalid(self, reason: str) -> None:
        if reason and reason not in self._parameter_invalid_reasons:
            self._parameter_invalid_reasons.append(reason)

    def get_physical_features(self) -> Optional[Dict[str, Any]]:
        """
        获取最近一次提取的物理特征
        
        Returns:
            物理特征字典，如果尚未调用 extract_objective_metrics 则返回 None
        """
        return self._cached_physical_features
    
    def extract_experiment_parameters(
        self,
        metadata_file: str = "experiment_metadata.json"
    ) -> Dict[str, Any]:
        """
        提取实验参数（从元数据文件）
        
        Args:
            metadata_file: 元数据文件名
            
        Returns:
            实验参数字典，例如:
            {
                "doping_concentration": 0.3,
                "sintering_temp_C": 1000,
                "ball_milling_time_h": 12.0
            }
            
        Raises:
            FileNotFoundError: 元数据文件不存在
        """
        self._parameter_invalid_reasons = []
        metadata_path = self.results_dir / metadata_file
        bundle_path = _probe_stage0_bundle(self.results_dir)
        metadata_parameters: Dict[str, Any] = {}
        bundle_parameters: Dict[str, Any] = {}

        if metadata_path.exists():
            logger.info(f"📂 读取实验参数: {metadata_path}")
            try:
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                metadata_parameters = self._normalize_experiment_parameters(
                    metadata.get("parameters") or {}
                )
            except json.JSONDecodeError as e:
                logger.error(f"❌ 元数据文件 JSON 格式错误: {e}")
                self._mark_parameters_invalid("metadata_json_invalid")
        else:
            logger.warning(f"⚠️ 元数据文件不存在: {metadata_path}")

        if bundle_path is not None:
            try:
                with open(bundle_path, "r", encoding="utf-8") as f:
                    bundle = json.load(f)
                bundle_parameters = self._normalize_experiment_parameters(
                    bundle.get("recipe") or {}
                )
            except Exception as e:
                logger.warning(f"⚠️ 读取 stage0_result_bundle recipe 失败: {e}")
                self._mark_parameters_invalid("bundle_recipe_unreadable")

        if metadata_parameters and bundle_parameters:
            for key, meta_value in metadata_parameters.items():
                bundle_value = bundle_parameters.get(key)
                if bundle_value is None:
                    continue
                if not math.isclose(float(meta_value), float(bundle_value), rel_tol=1e-9, abs_tol=1e-12):
                    reason = f"metadata_bundle_parameter_conflict:{key}"
                    self._mark_parameters_invalid(reason)
                    raise ValueError(
                        f"Stage0 parameter conflict for {key}: "
                        f"metadata={meta_value}, bundle={bundle_value}"
                    )

        metadata_complete = self._parameters_complete(metadata_parameters)
        bundle_complete = self._parameters_complete(bundle_parameters)
        if metadata_complete:
            parameters = metadata_parameters
        elif bundle_complete:
            parameters = bundle_parameters
        else:
            parameters = {}
        if not parameters:
            self._mark_parameters_invalid("experiment_parameters_missing")
            logger.error("❌ metadata parameters and bundle recipe are both missing or invalid")
            return {}

        logger.info(f"✅ 成功提取 {len(parameters)} 个实验参数")
        for key, value in parameters.items():
            logger.info(f"  - {key}: {value}")

        return parameters

    def _parameters_complete(self, parameters: Dict[str, Any]) -> bool:
        if not parameters:
            return False
        if self.campaign_config and hasattr(self.campaign_config, "get_parameter_names"):
            required = self.campaign_config.get_parameter_names()
            missing = [name for name in required if parameters.get(name) is None]
            for name in missing:
                self._mark_parameters_invalid(f"parameter_missing:{name}")
            return not missing
        return True

    def _normalize_experiment_parameters(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """Keep only campaign parameters with numeric, non-null values."""
        if not isinstance(raw, dict):
            return {}
        if self.campaign_config and hasattr(self.campaign_config, "get_parameter_names"):
            parameter_names = self.campaign_config.get_parameter_names()
        else:
            parameter_names = list(raw.keys())
        normalized: Dict[str, Any] = {}
        for name in parameter_names:
            value = raw.get(name)
            if value is None:
                continue
            try:
                normalized[name] = float(value)
            except (TypeError, ValueError):
                self._mark_parameters_invalid(f"parameter_not_numeric:{name}")
        return normalized
    
    def _extract_physical_features(
        self, 
        aggregated_data: Dict[str, Any],
        arrhenius_data: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        从宽温域数据和 Arrhenius 分析中提取丰富的物理特征
        
        Args:
            aggregated_data: aggregated_results.json 的数据
            arrhenius_data: arrhenius_analysis.json 的数据（可选）
            
        Returns:
            物理特征字典:
            {
                "conductivity_room_temp_S_cm": 1.5e-4,
                "ea_high_temp_eV": 0.28,
                "ea_low_temp_eV": 0.45,
                "transition_temps_K": [273.15, 323.15],
                "n_segments": 2
            }
        """
        features = {}
        
        # ===== 提取室温电导率 =====
        conductivity_room_temp = self._extract_room_temp_conductivity(aggregated_data)
        if conductivity_room_temp is not None:
            features["conductivity_room_temp_S_cm"] = conductivity_room_temp
        else:
            self._mark_objective_invalid("conductivity_room_temp_missing")
        
        # ===== 提取 Arrhenius 特征 =====
        if arrhenius_data and arrhenius_data.get("success"):
            segments = arrhenius_data.get("segments", [])
            
            if segments:
                # 使用智能策略提取主导传导机制的活化能
                ea_high, ea_low = self._extract_dominant_segment_ea(segments)
                if ea_high is not None:
                    features["ea_high_temp_eV"] = ea_high
                else:
                    self._mark_objective_invalid("ea_high_temp_eV_missing")
                if ea_low is not None:
                    features["ea_low_temp_eV"] = ea_low
                else:
                    self._mark_objective_invalid("ea_low_temp_eV_missing")
                
                # 分段数量
                features["n_segments"] = len(segments)
            else:
                self._mark_objective_invalid("arrhenius_segments_missing")
                features["n_segments"] = 0
            
            # 相变温度列表
            transition_temps = arrhenius_data.get("transition_temps_K", [])
            features["transition_temps_K"] = transition_temps
        else:
            logger.warning("⚠️ 未找到有效 Arrhenius 分析结果")
            self._mark_objective_invalid("arrhenius_missing_or_invalid")
            features["transition_temps_K"] = []
            features["n_segments"] = 0

        # ===== 派生量：低温段相对高温段的"超出活化能"（量化相变/体相冻结退化） =====
        # 公式: ea_low_excess_eV = max(0, Ea_low - 1.5 * Ea_high)
        # 用途: 公式 eval 时 __builtins__ 被禁用，无法直接用 max()/min()，所以把派生量提前算好。
        if "ea_high_temp_eV" in features and "ea_low_temp_eV" in features:
            ea_high_v = features.get("ea_high_temp_eV", 0.0) or 0.0
            ea_low_v = features.get("ea_low_temp_eV", 0.0) or 0.0
            excess = ea_low_v - 1.5 * ea_high_v
            features["ea_low_excess_eV"] = excess if excess > 0 else 0.0

        return features
    
    def _extract_dominant_segment_ea(self, segments: List[Dict]) -> tuple:
        """
        智能提取主导传导机制的活化能（修正版）

        策略（按 domain_knowledge "Grotthuss 高温端为主导传导机制" 优先）：
        1. 单段 → 直接用该段
        2. 多段 → 主段 = ``temp_range_K`` 上界最高的段（最贴近室温/操作温度）
        3. 上界相同 tiebreaker：数据点更多的段
        4. 异常保护：若主段 Ea < 0 或 n_points < 3 → 在剩余段中按 (n_points ≥ 3, T_high) 排序回退

        Args:
            segments: Arrhenius 分段列表，按低温→高温或高温→低温任意顺序皆可
            
        Returns:
            (ea_high_temp_eV, ea_low_temp_eV)
            
        Notes:
            - ea_high_temp_eV: 高温/室温段（主导 Grotthuss 跳跃）的活化能
            - ea_low_temp_eV: 全体分段中 temp_range_K 上界最低的段（最易出现相变 / 体相冻结）
            - 负 Ea 会被自动修正为 0.0（物理上不可能为负）
        """
        if not segments:
            return None, None

        def _ea_value(seg: Dict) -> Optional[float]:
            value = seg.get("Ea_eV")
            if value is None:
                return None
            try:
                return float(value)
            except (TypeError, ValueError):
                return None

        def _seg_t_hi(seg: Dict) -> float:
            tr = seg.get("temp_range_K") or [0.0, 0.0]
            try:
                hi = float(tr[1]) if len(tr) >= 2 else 0.0
            except (TypeError, ValueError):
                hi = 0.0
            return hi

        def _seg_t_lo(seg: Dict) -> float:
            tr = seg.get("temp_range_K") or [0.0, 0.0]
            try:
                lo = float(tr[0]) if len(tr) >= 1 else 0.0
            except (TypeError, ValueError):
                lo = 0.0
            return lo

        # 单段样品：直接使用
        if len(segments) == 1:
            ea = _ea_value(segments[0])
            if ea is None:
                return None, None
            return max(ea, 0.0), max(ea, 0.0)

        # 多段样品：主段 = T_high 最大、tiebreak 用 n_points
        ordered = sorted(
            enumerate(segments),
            key=lambda x: (_seg_t_hi(x[1]), x[1].get("n_points", 0)),
            reverse=True,
        )
        seg_id, main_seg = ordered[0]
        ea_high = _ea_value(main_seg)

        # 异常保护
        if ea_high is None or ea_high < 0 or main_seg.get("n_points", 0) < 3:
            logger.warning(
                f"⚠️ 主导段 (Seg{seg_id}) Ea 异常: {ea_high}, "
                f"n_points={main_seg.get('n_points', 0)}，尝试降级到次优段"
            )
            fallback = [
                (i, s) for i, s in ordered[1:]
                if _ea_value(s) is not None and _ea_value(s) >= 0 and s.get("n_points", 0) >= 3
            ]
            if fallback:
                seg_id, main_seg = fallback[0]
                ea_high = _ea_value(main_seg)
                logger.info(f"✅ 降级到 Seg{seg_id}, Ea={ea_high:.4f} eV")
            else:
                logger.warning("⚠️ 所有分段均缺失或异常，ea_high_temp_eV 无法计算")
                ea_high = None

        # 低温 Ea: T_low 最小的那段（不再假设 segments 顺序）
        low_idx, low_seg = min(enumerate(segments), key=lambda x: _seg_t_lo(x[1]))
        ea_low = _ea_value(low_seg)

        return (
            max(ea_high, 0.0) if ea_high is not None else None,
            max(ea_low, 0.0) if ea_low is not None else None,
        )
    
    def _extract_room_temp_conductivity(
        self, 
        aggregated_data: Dict[str, Any]
    ) -> Optional[float]:
        """
        从宽温域数据中提取室温（25°C / 298K）电导率
        
        Args:
            aggregated_data: aggregated_results.json 的数据
            
        Returns:
            室温电导率（S/cm），如果未找到则返回 None
        """
        # 策略 1: 从 measurements 数组中查找 25°C 附近的数据点
        if "measurements" in aggregated_data:
            measurements = aggregated_data["measurements"]
            
            # 过滤出成功的测量点
            valid_measurements = [
                m for m in measurements
                if m.get("success") and m.get("conductivity_S_per_cm") is not None
            ]
            
            if valid_measurements:
                # 找到最接近 25°C (298.15K) 的点
                target_temp_C = 25.0
                closest_measurement = min(
                    valid_measurements,
                    key=lambda m: abs(m.get("temperature_C", 999) - target_temp_C)
                )
                
                temp_diff = abs(closest_measurement.get("temperature_C", 999) - target_temp_C)
                
                if temp_diff < 10.0:  # 容差 ±10°C
                    conductivity = closest_measurement["conductivity_S_per_cm"]
                    logger.info(
                        f"✅ 提取室温电导率: {conductivity:.4e} S/cm "
                        f"(T={closest_measurement['temperature_C']:.1f}°C)"
                    )
                    return float(conductivity)
                else:
                    logger.warning(
                        f"⚠️ 最接近室温的测量点温度为 "
                        f"{closest_measurement.get('temperature_C')}°C，偏差过大"
                    )
        
        # 策略 2: 兼容旧格式（直接在根级别或 objectives 下）
        if "conductivity_room_temp_S_cm" in aggregated_data:
            return float(aggregated_data["conductivity_room_temp_S_cm"])
        
        if "objectives" in aggregated_data:
            objectives = aggregated_data["objectives"]
            if "conductivity_room_temp_S_cm" in objectives:
                return float(objectives["conductivity_room_temp_S_cm"])
        
        logger.error("❌ 未能从数据中提取室温电导率")
        return None
    
    def _compute_objective_with_formula(
        self, 
        physical_features: Dict[str, Any]
    ) -> Dict[str, float]:
        """
        基于公式计算目标值（如果 campaign_config 提供了公式）
        
        Args:
            physical_features: 物理特征字典
            
        Returns:
            包含计算结果的指标字典
        """
        metrics: Dict[str, Any] = {}
        
        # 将所有数值特征复制到 metrics
        for key, value in physical_features.items():
            if isinstance(value, (int, float)):
                metrics[key] = float(value)
        
        # 如果有 campaign_config 且定义了公式，则计算目标值
        if self.campaign_config:
            formula = self.campaign_config.get_objective_formula()
            
            if formula:
                logger.info(f"🧮 使用公式计算目标值: {formula}")
                
                # ===== 数据验证（防止 math.log10 等函数的定义域异常）=====
                validation_passed = True
                
                # 检查 conductivity_room_temp_S_cm（如果公式中使用了 log10）
                if 'log10' in formula and 'conductivity_room_temp_S_cm' in formula:
                    conductivity = physical_features.get('conductivity_room_temp_S_cm')
                    if conductivity is None:
                        logger.error("❌ 数据验证失败: conductivity_room_temp_S_cm 为 None")
                        validation_passed = False
                    elif conductivity <= 0:
                        logger.error(f"❌ 数据验证失败: conductivity_room_temp_S_cm = {conductivity} (必须 > 0)")
                        validation_passed = False
                
                # 检查 ea_high_temp_eV
                if 'ea_high_temp_eV' in formula:
                    ea = physical_features.get('ea_high_temp_eV')
                    if ea is None:
                        logger.error("❌ 数据验证失败: ea_high_temp_eV 缺失")
                        self._mark_objective_invalid("ea_high_temp_eV_missing")
                        validation_passed = False
                
                if validation_passed:
                    try:
                        # 安全的 eval：只允许 math 模块和 physical_features 变量
                        
                        # 计算公式
                        result = _safe_eval_formula(formula, physical_features.copy())
                        
                        # 获取目标名称
                        target_name = self.campaign_config.get_objective_target()
                        metrics[target_name] = float(result)
                        
                        logger.info(f"✅ 计算结果: {target_name} = {result:.4f}")
                        
                    except Exception as e:
                        logger.error(f"❌ 公式计算失败: {e}")
                        logger.error(f"   公式: {formula}")
                        logger.error(f"   可用变量: {list(physical_features.keys())}")
                        validation_passed = False
                
                if not validation_passed:
                    logger.warning("⚠️ 目标函数未计算；样品将被标记为 objective_valid=false")
                    self._mark_objective_invalid("objective_formula_inputs_invalid")
        
        objective_valid = len(self._objective_invalid_reasons) == 0
        metrics["objective_valid"] = objective_valid
        metrics["objective_invalid_reasons"] = list(self._objective_invalid_reasons)
        return metrics
    
    def _extract_metrics_from_data(self, data: Dict[str, Any]) -> Dict[str, float]:
        """
        从原始数据中提取指标（兼容旧格式，已被 _extract_physical_features 替代）
        
        Args:
            data: 原始 JSON 数据
            
        Returns:
            指标字典
        """
        metrics = {}
        
        # 尝试多种可能的数据结构
        
        # 格式 1: 直接在根级别
        if "conductivity_room_temp_S_cm" in data:
            metrics["conductivity_room_temp_S_cm"] = float(
                data["conductivity_room_temp_S_cm"]
            )
        
        # 格式 2: 在 "metrics" 或 "objectives" 字段下
        if "metrics" in data:
            for key, value in data["metrics"].items():
                if isinstance(value, (int, float)):
                    metrics[key] = float(value)
        
        if "objectives" in data:
            for key, value in data["objectives"].items():
                if isinstance(value, (int, float)):
                    metrics[key] = float(value)
        
        # 格式 3: 在 "results" 字段下
        if "results" in data:
            results = data["results"]
            if isinstance(results, dict):
                for key, value in results.items():
                    if isinstance(value, (int, float)):
                        metrics[key] = float(value)
        
        # 格式 4: 嵌套在 "eis_analysis" 或类似字段下
        if "eis_analysis" in data:
            eis = data["eis_analysis"]
            if "conductivity_room_temp_S_cm" in eis:
                metrics["conductivity_room_temp_S_cm"] = float(
                    eis["conductivity_room_temp_S_cm"]
                )
            if "activation_energy_eV" in eis:
                metrics["activation_energy_eV"] = float(
                    eis["activation_energy_eV"]
                )
        
        return metrics
    
    def _validate_metrics(self, metrics: Dict[str, float]) -> None:
        """
        验证指标的有效性
        
        Args:
            metrics: 指标字典
            
        Raises:
            ValueError: 指标无效
        """
        if not metrics:
            raise ValueError(
                "未能从结果文件中提取到任何有效指标\n"
                "请检查 Stage 0 的输出格式是否正确"
            )
        objective_valid = metrics.get("objective_valid", True)
        numeric_metrics = {
            key: value
            for key, value in metrics.items()
            if isinstance(value, (int, float)) and not isinstance(value, bool)
        }
        if objective_valid is False and not numeric_metrics:
            return
        
        # 检查是否有 NaN 或无穷大
        for key, value in metrics.items():
            if key in {"objective_valid", "objective_invalid_reasons"}:
                continue
            if not isinstance(value, (int, float)):
                raise ValueError(f"指标 {key} 的值不是数值类型: {value}")
            
            if value != value:  # NaN check
                raise ValueError(f"指标 {key} 的值为 NaN")
            
            if abs(value) == float('inf'):
                raise ValueError(f"指标 {key} 的值为无穷大")
            
            if value < 0:
                logger.warning(
                    f"⚠️ 指标 {key} 的值为负数: {value}，请确认是否合理"
                )
    
    def get_latest_sample_id(self) -> Optional[str]:
        """
        获取最新样品的 ID（从目录结构或文件名推断）
        
        Returns:
            样品 ID，如果无法推断则返回 None
        """
        # 优先从 experiment_metadata.json 读取；这是 Stage1 记忆库与
        # frontend sample bus 之间的稳定锚点。
        try:
            metadata_file = self.results_dir / "experiment_metadata.json"
            if metadata_file.exists():
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    sid = data.get("sample_id") or data.get("sample_name")
                    if sid:
                        return sid
        except Exception as e:
            logger.debug(f"无法从元数据文件读取样品 ID: {e}")

        # 尝试从 aggregated_results.json 中读取
        try:
            results_file = self.results_dir / "aggregated_results.json"
            if results_file.exists():
                with open(results_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    sid = data.get("sample_id") or data.get("sample_name")
                    if sid:
                        return sid
        except Exception as e:
            logger.debug(f"无法从结果文件读取样品 ID: {e}")
        
        # 尝试从目录名推断
        sample_id = self.results_dir.name
        logger.info(f"从目录名推断样品 ID: {sample_id}")
        
        return sample_id
    
    def validate_data_completeness(self) -> Dict[str, bool]:
        """
        验证数据完整性（检查必需文件是否存在）
        
        Returns:
            验证结果字典
        """
        checks = {
            "aggregated_results_exists": (
                self.results_dir / "aggregated_results.json"
            ).exists(),
            "metadata_exists": (
                self.results_dir / "experiment_metadata.json"
            ).exists(),
            "directory_readable": self.results_dir.exists() and self.results_dir.is_dir()
        }
        
        logger.info("📋 数据完整性检查:")
        for check_name, result in checks.items():
            status = "✅" if result else "❌"
            logger.info(f"  {status} {check_name}: {result}")
        
        return checks
    
    @staticmethod
    def create_mock_results(
        output_dir: str,
        sample_id: str = "LATP_001",
        conductivity: float = 1.2e-4,
        parameters: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        创建模拟测试结果（用于测试和开发）
        
        Args:
            output_dir: 输出目录
            sample_id: 样品 ID
            conductivity: 电导率值
            parameters: 实验参数
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # 创建汇总结果文件
        results = {
            "sample_id": sample_id,
            "objectives": {
                "conductivity_room_temp_S_cm": conductivity,
                "activation_energy_eV": 0.35,
                "grain_boundary_resistance_ohm": 1500.0
            },
            "timestamp": "2026-04-09T12:00:00"
        }
        
        with open(output_path / "aggregated_results.json", 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        # 创建元数据文件
        if parameters is None:
            parameters = {
                "doping_concentration": 0.3,
                "sintering_temp_C": 1000,
                "ball_milling_time_h": 12.0
            }
        
        metadata = {
            "sample_id": sample_id,
            "parameters": parameters,
            "timestamp": "2026-04-09T12:00:00"
        }
        
        with open(output_path / "experiment_metadata.json", 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        
        logger.info(f"✅ 模拟测试结果已创建: {output_path}")
