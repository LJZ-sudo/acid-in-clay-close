# -*- coding: utf-8 -*-
"""
实验状态管理器（纯数据层）

核心原则：
1. 纯数据结构 - 只管理状态，不包含业务逻辑
2. 封装修改 - 禁止外部直接赋值，必须通过方法修改
3. 无外部依赖 - 不引入 hardware/analysis/reporting 模块
4. 类型安全 - 完整的类型注解
5. 线程安全 - 关键操作使用锁保护

职责：
- 硬件状态：温度、目标温度、冷却/加热状态、暂停状态
- 实验进度：测量历史记录、相变记录、实验元数据
- 相变检测：相变检测队列、当前相变范围、相变候选
- Agent 决策上下文：深度物理特征（v3.0.0 新增）

版本：3.2.0 (断点续测 save/load + resume_workflow 快照)
"""

from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime
from threading import Lock
import copy
import json

import numpy as np


# ============================================================
# 数据类：核心状态定义
# ============================================================

@dataclass
class HardwareState:
    """
    硬件状态（温度控制相关）
    
    Attributes:
        current_temp_C: 当前温度 (°C)
        target_temp_C: 目标温度 (°C)
        is_cooling: 是否正在冷却
        is_heating: 是否正在加热
        is_paused: 是否暂停
        is_stable: 温度是否稳定
        temperature_stable_count: 连续稳定次数
        last_temperature_update: 最后一次温度更新时间
    """
    current_temp_C: float = 25.0
    target_temp_C: Optional[float] = None
    is_cooling: bool = False
    is_heating: bool = False
    is_paused: bool = False
    is_stable: bool = False
    temperature_stable_count: int = 0
    last_temperature_update: Optional[datetime] = None


@dataclass
class MeasurementRecord:
    """
    单次测量记录
    
    Attributes:
        temperature_C: 测量温度 (°C)
        temperature_K: 测量温度 (K)
        timestamp: 测量时间戳
        timestamp_str: 时间戳字符串
        step_type: 步骤类型 ('coarse' | 'fine')
        
        raw_data_path: CHI 原始数据路径
        raw_data_exists: 原始数据文件是否存在
        eis_saved_path: 标准化 EIS 数据路径
        eis_saved: 是否保存成功
        
        eis_data: EIS 原始数据 (frequencies, z_real, z_imag, filtered)
        
        analysis: 单点 EIS 分析快照（与 analyze_eis_point 契约一致的可序列化子集：
            quality_result / rb_result / kk_result、status、kk_warning、
            conductivity_s_per_cm、rb_ohm 等；不含原始阻抗大数组）
        
        rb_ohm: 块体电阻 (Ω)
        rb_method: Rb 拟合方法
        fit_quality: 拟合质量指标
        r_squared: R² 值
        
        conductivity_S_per_cm: 电导率 (S/cm)
        
        success: 是否成功
        failure_reason: 失败原因
        
        phase_jump_detected: 是否检测到相跳
        phase_transition_range: 相变范围
        phase_detection: 相变检测详细信息
        
        debug_artifacts: 调试文件列表（如失败截图）
    """
    temperature_C: float
    temperature_K: float
    timestamp: float
    timestamp_str: str
    step_type: str  # 'coarse' | 'fine'
    
    raw_data_path: Optional[str] = None
    raw_data_exists: bool = False
    eis_saved_path: Optional[str] = None
    eis_saved: bool = False
    
    eis_data: Dict[str, Any] = field(default_factory=dict)
    
    analysis: Dict[str, Any] = field(default_factory=dict)
    
    rb_ohm: Optional[float] = None
    rb_method: Optional[str] = None
    fit_quality: Optional[float] = None
    r_squared: Optional[float] = None
    
    conductivity_S_per_cm: Optional[float] = None
    
    success: bool = False
    failure_reason: Optional[str] = None
    
    phase_jump_detected: bool = False
    phase_transition_range: Optional[Tuple[float, float]] = None
    phase_detection: Dict[str, Any] = field(default_factory=dict)
    
    debug_artifacts: List[str] = field(default_factory=list)


@dataclass
class PhaseTransitionRecord:
    """
    相变记录
    
    Attributes:
        transition_index: 相变序号（从 0 开始）
        temperature_range_C: 温度范围 (°C)
        temperature_range_K: 温度范围 (K)
        detection_method: 检测方法
        confidence_score: 置信度分数
        detected_at: 检测时间
        related_measurements: 关联的测量记录索引
    """
    transition_index: int
    temperature_range_C: Tuple[float, float]
    temperature_range_K: Tuple[float, float]
    detection_method: str
    confidence_score: float
    detected_at: datetime
    related_measurements: List[int] = field(default_factory=list)


@dataclass
class PhaseTransitionCandidate:
    """
    相变候选（待确认的相变）
    
    Attributes:
        start_temp_C: 起始温度 (°C)
        end_temp_C: 结束温度 (°C)
        detection_scores: 检测分数字典
        pending_confirmations: 待确认次数
        first_detected_at: 首次检测时间
    """
    start_temp_C: float
    end_temp_C: float
    detection_scores: Dict[str, float] = field(default_factory=dict)
    pending_confirmations: int = 0
    first_detected_at: Optional[datetime] = None


@dataclass
class ExperimentProgress:
    """
    实验进度状态
    
    Attributes:
        measurement_history: 测量历史记录列表
        phase_transitions: 已确认的相变列表
        
        coarse_measurement_count: 粗扫测量次数
        fine_measurement_count: 细扫测量次数
        total_measurement_count: 总测量次数
        
        experiment_start_time: 实验开始时间
        experiment_end_time: 实验结束时间
        is_running: 是否正在运行
        is_completed: 是否已完成
        
        current_scan_mode: 当前扫描模式 ('coarse' | 'fine' | 'idle')
        
        metadata: 实验元数据（材料、参数等）
        
        latest_arrhenius_result: 最近一次基于 measurement_history 的
            analyze_arrhenius_series 结果（全局实时 Arrhenius 快照）
        
        resume_workflow: 在线工作流断点信息（下一目标温、步长、循环内计数）
    """
    measurement_history: List[MeasurementRecord] = field(default_factory=list)
    phase_transitions: List[PhaseTransitionRecord] = field(default_factory=list)
    
    coarse_measurement_count: int = 0
    fine_measurement_count: int = 0
    total_measurement_count: int = 0
    
    experiment_start_time: Optional[datetime] = None
    experiment_end_time: Optional[datetime] = None
    is_running: bool = False
    is_completed: bool = False
    
    current_scan_mode: str = 'idle'  # 'coarse' | 'fine' | 'idle'
    
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    latest_arrhenius_result: Optional[Dict[str, Any]] = None
    
    resume_workflow: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PhaseDetectionQueue:
    """
    相变检测队列
    
    Attributes:
        candidates: 相变候选列表
        current_phase_range: 当前正在检测的相变范围
        detection_window_size: 检测窗口大小
        confirmation_threshold: 确认阈值
    """
    candidates: List[PhaseTransitionCandidate] = field(default_factory=list)
    current_phase_range: Optional[Tuple[float, float]] = None
    detection_window_size: int = 5
    confirmation_threshold: int = 3


@dataclass
class ExperimentState:
    """
    完整的实验状态（数据大本营）
    
    Attributes:
        hardware: 硬件状态
        progress: 实验进度
        phase_queue: 相变检测队列
    """
    hardware: HardwareState = field(default_factory=HardwareState)
    progress: ExperimentProgress = field(default_factory=ExperimentProgress)
    phase_queue: PhaseDetectionQueue = field(default_factory=PhaseDetectionQueue)


def export_experiment_state_json_dict(state: ExperimentState) -> Dict[str, Any]:
    """将 ExperimentState 转为可 json.dump 的纯数据结构。"""
    def walk(obj: Any) -> Any:
        # 优先处理 numpy 类型（在处理容器类型之前）
        # 处理 numpy 标量（np.float64, np.int64 等）
        if isinstance(obj, (np.integer, np.floating)):
            return obj.item()
        # 处理 numpy 通用标量
        if isinstance(obj, np.generic):
            return obj.item()
        # 处理 numpy 数组
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        # 处理有 item() 方法的对象（兼容其他类似 numpy 的类型）
        if hasattr(obj, 'item') and callable(getattr(obj, 'item')):
            try:
                return obj.item()
            except (TypeError, AttributeError):
                pass  # 如果 item() 调用失败，继续处理
        
        # 处理容器类型
        if isinstance(obj, dict):
            return {str(k): walk(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [walk(x) for x in obj]
        if isinstance(obj, tuple):
            return [walk(x) for x in obj]
        
        # 处理其他类型
        if isinstance(obj, datetime):
            return obj.isoformat()
        
        return obj
    
    return walk(asdict(state))


def _parse_dt_opt(value: Any) -> Optional[datetime]:
    if value is None or value == '':
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


def _float_pair(value: Any) -> Optional[Tuple[float, float]]:
    if value is None:
        return None
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        return (float(value[0]), float(value[1]))
    return None


def _measurement_record_from_dict(m: Dict[str, Any]) -> MeasurementRecord:
    return MeasurementRecord(
        temperature_C=float(m['temperature_C']),
        temperature_K=float(m['temperature_K']),
        timestamp=float(m['timestamp']),
        timestamp_str=str(m.get('timestamp_str', '')),
        step_type=str(m.get('step_type', 'coarse')),
        raw_data_path=m.get('raw_data_path'),
        raw_data_exists=bool(m.get('raw_data_exists', False)),
        eis_saved_path=m.get('eis_saved_path'),
        eis_saved=bool(m.get('eis_saved', False)),
        eis_data=dict(m.get('eis_data') or {}),
        analysis=dict(m.get('analysis') or {}),
        rb_ohm=m.get('rb_ohm'),
        rb_method=m.get('rb_method'),
        fit_quality=m.get('fit_quality'),
        r_squared=m.get('r_squared'),
        conductivity_S_per_cm=m.get('conductivity_S_per_cm'),
        success=bool(m.get('success', False)),
        failure_reason=m.get('failure_reason'),
        phase_jump_detected=bool(m.get('phase_jump_detected', False)),
        phase_transition_range=_float_pair(m.get('phase_transition_range')),
        phase_detection=dict(m.get('phase_detection') or {}),
        debug_artifacts=list(m.get('debug_artifacts') or []),
    )


def _phase_transition_record_from_dict(p: Dict[str, Any]) -> PhaseTransitionRecord:
    trc = _float_pair(p.get('temperature_range_C'))
    trk = _float_pair(p.get('temperature_range_K'))
    if trc is None or trk is None:
        raise ValueError('PhaseTransitionRecord missing temperature ranges')
    return PhaseTransitionRecord(
        transition_index=int(p['transition_index']),
        temperature_range_C=trc,
        temperature_range_K=trk,
        detection_method=str(p.get('detection_method', '')),
        confidence_score=float(p.get('confidence_score', 0.0)),
        detected_at=_parse_dt_opt(p.get('detected_at')) or datetime.now(),
        related_measurements=list(p.get('related_measurements') or []),
    )


def _phase_candidate_from_dict(c: Dict[str, Any]) -> PhaseTransitionCandidate:
    scores = c.get('detection_scores') or {}
    return PhaseTransitionCandidate(
        start_temp_C=float(c['start_temp_C']),
        end_temp_C=float(c['end_temp_C']),
        detection_scores={str(k): float(v) for k, v in scores.items()},
        pending_confirmations=int(c.get('pending_confirmations', 0)),
        first_detected_at=_parse_dt_opt(c.get('first_detected_at')),
    )


def _phase_queue_from_dict(d: Dict[str, Any]) -> PhaseDetectionQueue:
    candidates = [_phase_candidate_from_dict(x) for x in (d.get('candidates') or [])]
    cpr = _float_pair(d.get('current_phase_range'))
    return PhaseDetectionQueue(
        candidates=candidates,
        current_phase_range=cpr,
        detection_window_size=int(d.get('detection_window_size', 5)),
        confirmation_threshold=int(d.get('confirmation_threshold', 3)),
    )


def _experiment_progress_from_dict(d: Dict[str, Any]) -> ExperimentProgress:
    history = [_measurement_record_from_dict(x) for x in (d.get('measurement_history') or [])]
    transitions = []
    for x in (d.get('phase_transitions') or []):
        try:
            transitions.append(_phase_transition_record_from_dict(x))
        except (KeyError, TypeError, ValueError):
            continue
    
    return ExperimentProgress(
        measurement_history=history,
        phase_transitions=transitions,
        coarse_measurement_count=int(d.get('coarse_measurement_count', 0)),
        fine_measurement_count=int(d.get('fine_measurement_count', 0)),
        total_measurement_count=int(d.get('total_measurement_count', 0)),
        experiment_start_time=_parse_dt_opt(d.get('experiment_start_time')),
        experiment_end_time=_parse_dt_opt(d.get('experiment_end_time')),
        is_running=bool(d.get('is_running', False)),
        is_completed=bool(d.get('is_completed', False)),
        current_scan_mode=str(d.get('current_scan_mode', 'idle')),
        metadata=dict(d.get('metadata') or {}),
        latest_arrhenius_result=d.get('latest_arrhenius_result'),
        resume_workflow=dict(d.get('resume_workflow') or {}),
    )


def import_experiment_state_from_dict(data: Dict[str, Any]) -> ExperimentState:
    hw = data.get('hardware') or {}
    target_c = hw.get('target_temp_C')
    if target_c is not None:
        target_c = float(target_c)
    hardware = HardwareState(
        current_temp_C=float(hw.get('current_temp_C', 25.0)),
        target_temp_C=target_c,
        is_cooling=bool(hw.get('is_cooling', False)),
        is_heating=bool(hw.get('is_heating', False)),
        is_paused=bool(hw.get('is_paused', False)),
        is_stable=bool(hw.get('is_stable', False)),
        temperature_stable_count=int(hw.get('temperature_stable_count', 0)),
        last_temperature_update=_parse_dt_opt(hw.get('last_temperature_update')),
    )
    progress = _experiment_progress_from_dict(data.get('progress') or {})
    phase_queue = _phase_queue_from_dict(data.get('phase_queue') or {})
    return ExperimentState(hardware=hardware, progress=progress, phase_queue=phase_queue)


# ============================================================
# 状态控制器：封装所有状态修改操作
# ============================================================

class StateController:
    """
    实验状态控制器
    
    职责：
    1. 管理 ExperimentState
    2. 提供封装的状态修改方法
    3. 保证线程安全
    4. 禁止外部直接修改状态
    
    使用方式：
        controller = StateController()
        controller.update_temperature(25.5)
        controller.add_measurement_record(record)
        controller.pause_experiment()
    """
    
    def __init__(self, initial_state: Optional[ExperimentState] = None):
        """
        初始化状态控制器
        
        Args:
            initial_state: 初始状态（可选）
        """
        self._state = initial_state or ExperimentState()
        self._lock = Lock()
    
    # ========================================================
    # 状态访问（只读）
    # ========================================================
    
    def get_state_snapshot(self) -> ExperimentState:
        """
        获取状态快照（深拷贝）
        
        Returns:
            ExperimentState: 状态快照
        """
        with self._lock:
            return copy.deepcopy(self._state)
    
    def get_hardware_state(self) -> HardwareState:
        """获取硬件状态快照"""
        with self._lock:
            return copy.deepcopy(self._state.hardware)
    
    def get_progress_state(self) -> ExperimentProgress:
        """获取实验进度快照"""
        with self._lock:
            return copy.deepcopy(self._state.progress)
    
    def get_phase_queue_state(self) -> PhaseDetectionQueue:
        """获取相变检测队列快照"""
        with self._lock:
            return copy.deepcopy(self._state.phase_queue)
    
    def get_current_temperature(self) -> float:
        """获取当前温度"""
        with self._lock:
            return self._state.hardware.current_temp_C
    
    def get_target_temperature(self) -> Optional[float]:
        """获取目标温度"""
        with self._lock:
            return self._state.hardware.target_temp_C
    
    def is_paused(self) -> bool:
        """是否暂停"""
        with self._lock:
            return self._state.hardware.is_paused
    
    def is_temperature_stable(self) -> bool:
        """温度是否稳定"""
        with self._lock:
            return self._state.hardware.is_stable
    
    def get_measurement_count(self) -> int:
        """获取总测量次数"""
        with self._lock:
            return self._state.progress.total_measurement_count
    
    def get_measurement_history(self) -> List[MeasurementRecord]:
        """获取测量历史（深拷贝）"""
        with self._lock:
            return copy.deepcopy(self._state.progress.measurement_history)
    
    def get_phase_transitions(self) -> List[PhaseTransitionRecord]:
        """获取相变记录（深拷贝）"""
        with self._lock:
            return copy.deepcopy(self._state.progress.phase_transitions)
    
    # ========================================================
    # 硬件状态修改
    # ========================================================
    
    def update_temperature(
        self,
        temperature_C: float,
        is_stable: bool = False,
        stable_count: int = 0
    ) -> None:
        """
        更新当前温度
        
        Args:
            temperature_C: 温度 (°C)
            is_stable: 是否稳定
            stable_count: 连续稳定次数
        """
        with self._lock:
            self._state.hardware.current_temp_C = temperature_C
            self._state.hardware.is_stable = is_stable
            self._state.hardware.temperature_stable_count = stable_count
            self._state.hardware.last_temperature_update = datetime.now()
    
    def set_target_temperature(
        self,
        target_temp_C: float,
        is_cooling: bool = True
    ) -> None:
        """
        设置目标温度
        
        Args:
            target_temp_C: 目标温度 (°C)
            is_cooling: 是否冷却模式
        """
        with self._lock:
            self._state.hardware.target_temp_C = target_temp_C
            self._state.hardware.is_cooling = is_cooling
            self._state.hardware.is_heating = not is_cooling
    
    def clear_target_temperature(self) -> None:
        """清除目标温度"""
        with self._lock:
            self._state.hardware.target_temp_C = None
            self._state.hardware.is_cooling = False
            self._state.hardware.is_heating = False
    
    def pause_experiment(self) -> None:
        """暂停实验"""
        with self._lock:
            self._state.hardware.is_paused = True
    
    def resume_experiment(self) -> None:
        """恢复实验"""
        with self._lock:
            self._state.hardware.is_paused = False
    
    def reset_hardware_state(self) -> None:
        """重置硬件状态"""
        with self._lock:
            self._state.hardware = HardwareState()
    
    # ========================================================
    # 实验进度修改
    # ========================================================
    
    def start_experiment(self, metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        开始实验
        
        Args:
            metadata: 实验元数据（材料、参数等）
        """
        with self._lock:
            self._state.progress.is_running = True
            self._state.progress.is_completed = False
            self._state.progress.experiment_start_time = datetime.now()
            if metadata:
                self._state.progress.metadata = metadata
    
    def complete_experiment(self) -> None:
        """完成实验"""
        with self._lock:
            self._state.progress.is_running = False
            self._state.progress.is_completed = True
            self._state.progress.experiment_end_time = datetime.now()
    
    def set_scan_mode(self, mode: str) -> None:
        """
        设置扫描模式
        
        Args:
            mode: 'coarse' | 'fine' | 'idle'
        """
        if mode not in ['coarse', 'fine', 'idle']:
            raise ValueError(f"Invalid scan mode: {mode}")
        
        with self._lock:
            self._state.progress.current_scan_mode = mode
    
    def add_measurement_record(self, record: MeasurementRecord) -> int:
        """
        添加测量记录
        
        Args:
            record: 测量记录
        
        Returns:
            int: 记录索引
        """
        with self._lock:
            # 添加记录
            self._state.progress.measurement_history.append(record)
            
            # 更新计数
            self._state.progress.total_measurement_count += 1
            
            if record.step_type == 'coarse':
                self._state.progress.coarse_measurement_count += 1
            elif record.step_type == 'fine':
                self._state.progress.fine_measurement_count += 1
            
            # 返回索引
            return len(self._state.progress.measurement_history) - 1
    
    def update_measurement_record(
        self,
        index: int,
        updates: Dict[str, Any]
    ) -> bool:
        """
        更新测量记录
        
        Args:
            index: 记录索引
            updates: 更新字典
        
        Returns:
            bool: 是否成功
        """
        with self._lock:
            if index < 0 or index >= len(self._state.progress.measurement_history):
                return False
            
            record = self._state.progress.measurement_history[index]
            for key, value in updates.items():
                if hasattr(record, key):
                    setattr(record, key, value)
            
            return True
    
    def get_last_measurement(self) -> Optional[MeasurementRecord]:
        """获取最后一次测量记录"""
        with self._lock:
            if not self._state.progress.measurement_history:
                return None
            return copy.deepcopy(self._state.progress.measurement_history[-1])
    
    def get_recent_measurements(self, count: int) -> List[MeasurementRecord]:
        """
        获取最近 N 次测量记录
        
        Args:
            count: 数量
        
        Returns:
            List[MeasurementRecord]: 测量记录列表
        """
        with self._lock:
            history = self._state.progress.measurement_history
            return copy.deepcopy(history[-count:] if len(history) >= count else history)
    
    def set_latest_arrhenius_result(self, result: Optional[Dict[str, Any]]) -> None:
        """写入最近一次序列 Arrhenius 分析结果（由工作流在追加测量后更新）。"""
        with self._lock:
            self._state.progress.latest_arrhenius_result = (
                copy.deepcopy(result) if result is not None else None
            )
    
    def get_latest_arrhenius_result(self) -> Optional[Dict[str, Any]]:
        """获取最近一次序列 Arrhenius 分析结果（深拷贝）。"""
        with self._lock:
            if self._state.progress.latest_arrhenius_result is None:
                return None
            return copy.deepcopy(self._state.progress.latest_arrhenius_result)
    
    # ========================================================
    # 相变管理
    # ========================================================
    
    def add_phase_candidate(
        self,
        start_temp_C: float,
        end_temp_C: float,
        detection_scores: Optional[Dict[str, float]] = None
    ) -> int:
        """
        添加相变候选
        
        Args:
            start_temp_C: 起始温度 (°C)
            end_temp_C: 结束温度 (°C)
            detection_scores: 检测分数字典
        
        Returns:
            int: 候选索引
        """
        with self._lock:
            candidate = PhaseTransitionCandidate(
                start_temp_C=start_temp_C,
                end_temp_C=end_temp_C,
                detection_scores=detection_scores or {},
                pending_confirmations=1,
                first_detected_at=datetime.now()
            )
            self._state.phase_queue.candidates.append(candidate)
            return len(self._state.phase_queue.candidates) - 1
    
    def update_phase_candidate(
        self,
        index: int,
        detection_scores: Optional[Dict[str, float]] = None,
        increment_confirmation: bool = False
    ) -> bool:
        """
        更新相变候选
        
        Args:
            index: 候选索引
            detection_scores: 检测分数字典
            increment_confirmation: 是否增加确认次数
        
        Returns:
            bool: 是否成功
        """
        with self._lock:
            if index < 0 or index >= len(self._state.phase_queue.candidates):
                return False
            
            candidate = self._state.phase_queue.candidates[index]
            
            if detection_scores:
                candidate.detection_scores.update(detection_scores)
            
            if increment_confirmation:
                candidate.pending_confirmations += 1
            
            return True
    
    def confirm_phase_transition(
        self,
        candidate_index: int,
        detection_method: str,
        confidence_score: float,
        related_measurements: Optional[List[int]] = None
    ) -> int:
        """
        确认相变（从候选转为正式记录）
        
        Args:
            candidate_index: 候选索引
            detection_method: 检测方法
            confidence_score: 置信度分数
            related_measurements: 关联的测量记录索引列表
        
        Returns:
            int: 相变记录索引
        """
        with self._lock:
            if candidate_index < 0 or candidate_index >= len(self._state.phase_queue.candidates):
                raise ValueError(f"Invalid candidate index: {candidate_index}")
            
            candidate = self._state.phase_queue.candidates[candidate_index]
            
            # 创建正式记录
            transition = PhaseTransitionRecord(
                transition_index=len(self._state.progress.phase_transitions),
                temperature_range_C=(candidate.start_temp_C, candidate.end_temp_C),
                temperature_range_K=(
                    candidate.start_temp_C + 273.15,
                    candidate.end_temp_C + 273.15
                ),
                detection_method=detection_method,
                confidence_score=confidence_score,
                detected_at=candidate.first_detected_at or datetime.now(),
                related_measurements=related_measurements or []
            )
            
            self._state.progress.phase_transitions.append(transition)
            
            # 从候选列表移除
            self._state.phase_queue.candidates.pop(candidate_index)
            
            return len(self._state.progress.phase_transitions) - 1
    
    def remove_phase_candidate(self, index: int) -> bool:
        """
        移除相变候选
        
        Args:
            index: 候选索引
        
        Returns:
            bool: 是否成功
        """
        with self._lock:
            if index < 0 or index >= len(self._state.phase_queue.candidates):
                return False
            
            self._state.phase_queue.candidates.pop(index)
            return True
    
    def clear_phase_candidates(self) -> None:
        """清空相变候选"""
        with self._lock:
            self._state.phase_queue.candidates.clear()
    
    def set_current_phase_range(
        self,
        start_temp_C: Optional[float],
        end_temp_C: Optional[float]
    ) -> None:
        """
        设置当前相变范围
        
        Args:
            start_temp_C: 起始温度 (°C)，None 表示清除
            end_temp_C: 结束温度 (°C)
        """
        with self._lock:
            if start_temp_C is None:
                self._state.phase_queue.current_phase_range = None
            else:
                self._state.phase_queue.current_phase_range = (start_temp_C, end_temp_C)
    
    def clear_current_phase_range(self) -> None:
        """清除当前相变范围"""
        with self._lock:
            self._state.phase_queue.current_phase_range = None
    
    def get_phase_candidates(self) -> List[PhaseTransitionCandidate]:
        """获取相变候选列表（深拷贝）"""
        with self._lock:
            return copy.deepcopy(self._state.phase_queue.candidates)
    
    def get_current_phase_range(self) -> Optional[Tuple[float, float]]:
        """获取当前相变范围"""
        with self._lock:
            return self._state.phase_queue.current_phase_range
    
    # ========================================================
    # Agent 决策上下文（深度物理特征）
    # ========================================================
    
    def get_agent_context(self) -> Dict[str, Any]:
        """
        生成用于大模型决策的深度上下文（纯特征值，无原始阻抗数组）
        
        核心设计：
        1. 当前点快照：最新的 QA/KK/Rb/电导率状态
        2. 深度历史趋势：Arrhenius 分段 + 阻抗演变序列（5-8 点）
        3. 实验控制状态：截止温度、步长模式
        
        绝对禁止：
        - 不包含原始 z_real/z_imag 数组（Agent 只需特征值）
        - 实验刚开始时返回部分数据，不报错
        
        Returns:
            dict: 包含以下三大维度
                - current_point: 当前点快照
                - history_trend: 深度历史趋势（Arrhenius + 阻抗演变）
                - experiment_status: 实验控制状态
        
        版本：1.0.0
        """
        with self._lock:
            # ===== 维度 1: 当前点快照 =====
            current_point = self._extract_current_point_snapshot()
            
            # ===== 维度 2: 深度历史趋势 =====
            history_trend = self._extract_history_trend()
            
            # ===== 维度 3: 实验控制状态 =====
            experiment_status = self._extract_experiment_status()
            
            return {
                'current_point': current_point,
                'history_trend': history_trend,
                'experiment_status': experiment_status,
                'metadata': {
                    'total_measurements': self._state.progress.total_measurement_count,
                    'phase_transitions_detected': len(self._state.progress.phase_transitions),
                    'context_version': '1.1.0',
                    'generated_at': datetime.now().isoformat()
                }
            }
    
    def _extract_current_point_snapshot(self) -> Dict[str, Any]:
        """
        提取当前点快照（内部方法）
        
        Returns:
            dict: 当前点特征
                - temperature_C: 当前温度 (°C)
                - temperature_K: 当前温度 (K)
                - qa_status: 数据质量状态 ('A'/'B'/'C'/'F'/None)，来自 analysis.quality_result.grade
                - kk_warning: KK 验证警告标记
                - rb_ohm: 块体电阻 (Ω)
                - conductivity_S_per_cm: 电导率 (S/cm)
                - conductivity: 与 conductivity_S_per_cm 相同（便于 Agent 字段名对齐）
                - fit_quality: 拟合质量 (0-1)
                - rb_method: Rb 拟合方法
                - success: 当前点是否成功
                - failure_reason: 失败原因（如有）
        """
        # 实验刚开始，没有测量记录
        if not self._state.progress.measurement_history:
            return {
                'temperature_C': self._state.hardware.current_temp_C,
                'temperature_K': self._state.hardware.current_temp_C + 273.15,
                'qa_status': None,
                'kk_warning': False,
                'rb_ohm': None,
                'conductivity_S_per_cm': None,
                'conductivity': None,
                'fit_quality': None,
                'rb_method': None,
                'success': False,
                'failure_reason': 'No measurements yet'
            }
        
        # 获取最后一次测量
        last_record = self._state.progress.measurement_history[-1]
        
        eis_analysis = (
            last_record.eis_data.get('analysis')
            if isinstance(last_record.eis_data, dict)
            else None
        )
        if not isinstance(eis_analysis, dict):
            eis_analysis = {}
        rec_analysis = last_record.analysis if isinstance(last_record.analysis, dict) else {}
        # 单点 analysis 字段优先于历史 eis_data['analysis'] 嵌套
        analysis = {**eis_analysis, **rec_analysis}
        
        qa_status = None
        kk_warning = bool(analysis.get('kk_warning', False))
        
        qa_src = analysis.get('quality_result') or analysis.get('qa_result')
        if qa_src is None and isinstance(analysis.get('quality'), dict):
            qa_src = analysis['quality']
        if isinstance(qa_src, dict):
            qa_status = qa_src.get('grade') or qa_src.get('rating')
        
        rb_src = analysis.get('rb_result') or analysis.get('rb')
        rb_ohm = last_record.rb_ohm
        conductivity_S_per_cm = last_record.conductivity_S_per_cm
        if isinstance(rb_src, dict):
            if rb_src.get('rb_ohm') is not None:
                rb_ohm = rb_src.get('rb_ohm')
            ckey = rb_src.get('conductivity_s_per_cm')
            if ckey is not None:
                conductivity_S_per_cm = ckey
        
        return {
            'temperature_C': last_record.temperature_C,
            'temperature_K': last_record.temperature_K,
            'qa_status': qa_status,
            'kk_warning': kk_warning,
            'rb_ohm': rb_ohm,
            'conductivity_S_per_cm': conductivity_S_per_cm,
            'conductivity': conductivity_S_per_cm,
            'fit_quality': last_record.fit_quality,
            'rb_method': last_record.rb_method,
            'success': last_record.success,
            'failure_reason': last_record.failure_reason
        }
    
    def _extract_history_trend(self) -> Dict[str, Any]:
        """
        提取深度历史趋势（内部方法）
        
        核心：阻抗演变序列（用于判断 Rb 随温度变化是否符合指数规律）
        
        Returns:
            dict: 历史趋势特征
                - arrhenius_status: Arrhenius 分段状态（优先 progress.latest_arrhenius_result）
                    - n_segments: 分段数
                    - current_segment_ea_kJ_per_mol: 当前段活化能 (kJ/mol)
                    - anomalous_ea: 是否检测到异常负活化能
                    - last_transition_temp_K: 最后一次相变温度 (K)
                - rb_history_sequence: 阻抗演变序列（最近 5-8 点）
                    - 每点包含：temp_K, rb_ohm, conductivity, fit_quality
                    - 按温度降序排列（高温->低温）
                - statistics: 统计信息
                    - valid_points: 有效点数
                    - rb_growth_rate: Rb 增长率（相对首末点）
                    - conductivity_drop_rate: 电导率下降率
        """
        history = self._state.progress.measurement_history
        
        # 实验刚开始，历史数据不足
        if len(history) == 0:
            return {
                'arrhenius_status': {
                    'n_segments': 0,
                    'current_segment_ea_kJ_per_mol': None,
                    'anomalous_ea': False,
                    'last_transition_temp_K': None
                },
                'rb_history_sequence': [],
                'statistics': {
                    'valid_points': 0,
                    'rb_growth_rate': None,
                    'conductivity_drop_rate': None
                }
            }
        
        # ===== 提取所有有效测量点（完整历史数据，供 Agent 全面分析） =====
        valid_records = [
            rec for rec in history 
            if rec.success and rec.rb_ohm is not None and rec.conductivity_S_per_cm is not None
        ]
        
        # 传递所有有效点（不限制数量）
        # Agent 需要完整的温度-电导率演变曲线才能准确判断相变
        all_valid = valid_records
        
        # 构建阻抗演变序列（精简特征，无原始阻抗数组）
        rb_sequence = []
        for rec in all_valid:
            rb_sequence.append({
                'temp_K': rec.temperature_K,
                'temp_C': rec.temperature_C,
                'rb_ohm': rec.rb_ohm,
                'conductivity_S_per_cm': rec.conductivity_S_per_cm,
                'fit_quality': rec.fit_quality if rec.fit_quality is not None else 0.0
            })
        
        # ===== 统计信息（用于判断趋势） =====
        statistics = {
            'valid_points': len(rb_sequence),
            'rb_growth_rate': None,
            'conductivity_drop_rate': None
        }
        
        if len(rb_sequence) >= 2:
            # Rb 增长率（相对首末点）
            rb_first = rb_sequence[0]['rb_ohm']
            rb_last = rb_sequence[-1]['rb_ohm']
            if rb_first > 0:
                statistics['rb_growth_rate'] = (rb_last - rb_first) / rb_first
            
            # 电导率下降率
            cond_first = rb_sequence[0]['conductivity_S_per_cm']
            cond_last = rb_sequence[-1]['conductivity_S_per_cm']
            if cond_first > 0:
                statistics['conductivity_drop_rate'] = (cond_first - cond_last) / cond_first
        
        # ===== Arrhenius 分段状态：优先全局 latest_arrhenius_result，其次末点嵌套 =====
        def _arrhenius_status_from_result(arr_result: Optional[Dict[str, Any]]) -> Dict[str, Any]:
            base = {
                'n_segments': 0,
                'current_segment_ea_kJ_per_mol': None,
                'anomalous_ea': False,
                'last_transition_temp_K': None,
                'confidence': None,
                'model_probabilities': None,
                'best_model': None,
                'n_points_used': None,
            }
            if not arr_result or not isinstance(arr_result, dict):
                return base
            
            # 基础信息
            base['n_segments'] = int(arr_result.get('n_segments', 0) or 0)
            base['n_points_used'] = arr_result.get('n_points_used')
            
            # 多模型竞争信息
            base['confidence'] = arr_result.get('confidence')
            base['model_probabilities'] = arr_result.get('model_probabilities')
            base['best_model'] = arr_result.get('best_model')
            
            # 分段信息
            segments = arr_result.get('segments') or []
            if segments:
                last_segment = segments[-1]
                if isinstance(last_segment, dict):
                    base['current_segment_ea_kJ_per_mol'] = last_segment.get('ea_kJ_per_mol')
                    base['anomalous_ea'] = bool(last_segment.get('anomalous_ea', False))
            
            # 相变温度
            transition_temps = arr_result.get('transition_temps_K') or []
            if transition_temps:
                base['last_transition_temp_K'] = transition_temps[-1]
            elif arr_result.get('transition_temp_K') is not None:
                base['last_transition_temp_K'] = arr_result.get('transition_temp_K')
            elif arr_result.get('breakpoint_K') is not None:
                base['last_transition_temp_K'] = arr_result.get('breakpoint_K')
            
            return base
        
        arr_src: Optional[Dict[str, Any]] = self._state.progress.latest_arrhenius_result
        if arr_src is None and history:
            last = history[-1]
            eis_a = (
                last.eis_data.get('analysis')
                if isinstance(last.eis_data, dict)
                else None
            )
            if not isinstance(eis_a, dict):
                eis_a = {}
            rec_a = last.analysis if isinstance(last.analysis, dict) else {}
            merged_last = {**eis_a, **rec_a}
            arr_src = merged_last.get('arrhenius_result')
        
        arrhenius_status = _arrhenius_status_from_result(arr_src)
        
        return {
            'arrhenius_status': arrhenius_status,
            'rb_history_sequence': rb_sequence,
            'statistics': statistics
        }
    
    def _extract_experiment_status(self) -> Dict[str, Any]:
        """
        提取实验控制状态（内部方法）
        
        Returns:
            dict: 实验控制特征
                - target_temp_C: 截止温度 (°C)
                - current_scan_mode: 当前步长模式 ('coarse'/'fine'/'idle')
                - is_running: 实验是否运行中
                - is_paused: 实验是否暂停
                - temperature_stable: 温度是否稳定
                - coarse_count: 粗扫次数
                - fine_count: 细扫次数
        """
        return {
            'target_temp_C': self._state.hardware.target_temp_C,
            'current_scan_mode': self._state.progress.current_scan_mode,
            'is_running': self._state.progress.is_running,
            'is_paused': self._state.hardware.is_paused,
            'temperature_stable': self._state.hardware.is_stable,
            'coarse_count': self._state.progress.coarse_measurement_count,
            'fine_count': self._state.progress.fine_measurement_count
        }
    
    # ========================================================
    # 批量操作与重置
    # ========================================================
    
    def reset_progress(self) -> None:
        """重置实验进度（保留元数据）"""
        with self._lock:
            metadata = self._state.progress.metadata
            self._state.progress = ExperimentProgress(metadata=metadata)
    
    def reset_all(self) -> None:
        """重置所有状态"""
        with self._lock:
            self._state = ExperimentState()
    
    def update_resume_workflow_snapshot(
        self,
        next_target_temp_C: float,
        step_size_C: float,
        measurement_count_in_loop: int,
    ) -> None:
        """持久化在线工作流断点（与 save_state 配合）。"""
        with self._lock:
            self._state.progress.resume_workflow = {
                'next_target_temp_C': float(next_target_temp_C),
                'step_size_C': float(step_size_C),
                'measurement_count_in_loop': int(measurement_count_in_loop),
            }
    
    def get_resume_workflow_snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return copy.deepcopy(self._state.progress.resume_workflow)
    
    def save_state(self, path: str) -> None:
        """
        将完整实验状态写入 JSON（断点续测）。
        
        Args:
            path: 文件路径
        """
        with self._lock:
            payload = export_experiment_state_json_dict(self._state)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
    
    def load_state(self, path: str) -> bool:
        """
        从 JSON 恢复实验状态。
        
        Returns:
            bool: 是否成功（文件不存在或解析失败时返回 False）
        """
        try:
            with open(path, encoding='utf-8') as f:
                data = json.load(f)
            state = import_experiment_state_from_dict(data)
            with self._lock:
                self._state = state
            return True
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
            return False
    
    def export_to_dict(self) -> Dict[str, Any]:
        """
        导出状态为字典（用于序列化）
        
        Returns:
            Dict[str, Any]: 状态字典
        """
        with self._lock:
            state_snapshot = copy.deepcopy(self._state)
            
            # 转换 datetime 为字符串
            def convert_datetime(obj):
                if isinstance(obj, datetime):
                    return obj.isoformat()
                elif isinstance(obj, dict):
                    return {k: convert_datetime(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [convert_datetime(item) for item in obj]
                elif hasattr(obj, '__dict__'):
                    return convert_datetime(obj.__dict__)
                else:
                    return obj
            
            return convert_datetime(state_snapshot.__dict__)


# ============================================================
# 工具函数
# ============================================================

def create_measurement_record(
    temperature_C: float,
    timestamp: float,
    step_type: str,
    **kwargs
) -> MeasurementRecord:
    """
    创建测量记录（工厂函数）
    
    Args:
        temperature_C: 温度 (°C)
        timestamp: 时间戳
        step_type: 步骤类型 ('coarse' | 'fine')
        **kwargs: 其他字段（可含 analysis= 单点 EIS 分析快照字典）
    
    Returns:
        MeasurementRecord: 测量记录
    """
    from datetime import datetime
    
    return MeasurementRecord(
        temperature_C=temperature_C,
        temperature_K=temperature_C + 273.15,
        timestamp=timestamp,
        timestamp_str=datetime.fromtimestamp(timestamp).strftime('%Y%m%d_%H%M%S'),
        step_type=step_type,
        **kwargs
    )


def validate_state_integrity(state: ExperimentState) -> Tuple[bool, List[str]]:
    """
    验证状态完整性
    
    Args:
        state: 实验状态
    
    Returns:
        Tuple[bool, List[str]]: (是否有效, 错误列表)
    """
    errors = []
    
    # 检查硬件状态
    if state.hardware.current_temp_C < -273.15:
        errors.append(f"Invalid current temperature: {state.hardware.current_temp_C}")
    
    if state.hardware.target_temp_C is not None:
        if state.hardware.target_temp_C < -273.15:
            errors.append(f"Invalid target temperature: {state.hardware.target_temp_C}")
    
    # 检查实验进度
    if state.progress.total_measurement_count < 0:
        errors.append(f"Invalid measurement count: {state.progress.total_measurement_count}")
    
    expected_total = (
        state.progress.coarse_measurement_count +
        state.progress.fine_measurement_count
    )
    actual_total = len(state.progress.measurement_history)
    
    if expected_total != actual_total:
        errors.append(
            f"Measurement count mismatch: expected {expected_total}, "
            f"but found {actual_total} records"
        )
    
    # 检查相变记录
    for i, transition in enumerate(state.progress.phase_transitions):
        if transition.transition_index != i:
            errors.append(
                f"Phase transition index mismatch at position {i}: "
                f"expected {i}, got {transition.transition_index}"
            )
    
    return len(errors) == 0, errors
