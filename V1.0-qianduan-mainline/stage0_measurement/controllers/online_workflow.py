# -*- coding: utf-8 -*-
"""
在线实验工作流控制器（Agent 驱动的动态闭环版）

职责：
1. 编排 Agent 驱动的动态降温循环（温度控制 + 测量 + 实时决策）
2. 组装单点测量事务（CHI 自动化 + EIS 分析 + 状态更新）
3. 集成智能决策环（analyze_experiment_state）
4. 执行 Agent 指令（CONTINUE/FINE_GRAINED_SCAN/ABORT）
5. 异常与暂停接管

依赖注入：
- TemperatureDriver: 硬件驱动
- ChiExecutor: GUI 自动化
- StateController: 状态管理

核心改进（v3.0.0）：
- 从静态温度列表改为动态 while 循环
- 每个点完成后立即调用 Agent 决策
- 支持动态步长切换和回温
- 持久化 Agent 决策结果

版本：3.4.0 (细扫区 Agent 静音 + 自动密集采样)
"""

import os
import time
from typing import Optional, Dict, Any, Callable, Set, Tuple
from datetime import datetime
from dataclasses import dataclass, field


@dataclass
class CoolingConfig:
    """
    降温配置参数
    
    Attributes:
        T_start: 起始温度 (°C)
        T_end: 结束温度 (°C)
        coarse_step: 粗扫步长 (°C)
        fine_step: 细扫步长 (°C)
        eps: 温度容差 (°C)
        
        stability_duration: 稳定性验证时长 (秒)
        stability_check_interval: 稳定性检查间隔 (秒)
        stability_max_retry: 稳定性验证最大重试次数
        
        measurement_max_retry: 测量最大重试次数
        cooling_timeout: 单次降温超时时间 (秒)
        max_cooling_iterations: 最大降温迭代次数
        
        max_measurement_points: 最大测量点数（防止 Agent 死循环）
        enable_agent_decision: 是否启用 Agent 决策（默认 True）
        agent_api_key: PoloAPI Key（可选；未设置时由 phase_detect 从环境变量 POLOAPI_KEY 读取）
        
        fine_scan_window_C: 细扫区间跨度（°C），触发精细扫描后固定往下扫描的温度跨度
    """
    T_start: float = 25.0
    T_end: float = -120.0
    coarse_step: float = 5.0
    fine_step: float = 1.0
    eps: float = 0.5
    
    stability_duration: int = 40
    stability_check_interval: int = 5
    stability_max_retry: int = 3
    
    measurement_max_retry: int = 3
    cooling_timeout: int = 3600
    max_cooling_iterations: int = 100
    
    max_measurement_points: int = 200  # 新增：防止 Agent 死循环
    enable_agent_decision: bool = True  # 新增：是否启用 Agent 决策
    agent_api_key: Optional[str] = None  # 新增：PoloAPI Key（可选；未设则用环境变量 POLOAPI_KEY）
    fine_scan_window_C: float = 10.0  # 新增：细扫区间跨度（°C）


@dataclass
class ChiConfig:
    """
    CHI 测量配置参数
    
    Attributes:
        material: 材料名称
        highf: 高频 (Hz)
        lowf: 低频 (Hz)
        initV: 初始电位 (V)
        your_position: 数据保存目录
        template_dir: 模板目录
        thickness_cm: 样品厚度 (cm)
        area_cm2: 样品面积 (cm²)
    """
    material: str = "Sample"
    highf: str = "1000000"
    lowf: str = "0.1"
    initV: str = "0"
    # Tier1 fix (2026-06-01): no longer a hardcoded machine path. Defaults to the
    # STAGE0_CHI_DATA_DIR env var (same override used by stage0 config.py), and
    # falls back to the previous "E:\\chi_data" when the var is unset, so default
    # behavior is unchanged.
    your_position: str = field(
        default_factory=lambda: os.getenv("STAGE0_CHI_DATA_DIR", "E:\\chi_data")
    )
    template_dir: str = "controllers/templates"
    thickness_cm: float = 0.1
    area_cm2: float = 1.96


@dataclass
class ExperimentConfig:
    """
    实验配置（总配置）
    
    Attributes:
        cooling: 降温配置
        chi: CHI 配置
        enable_phase_detection: 是否启用相变检测
        enable_auto_stop: 是否启用自动停止
        enable_fine_scan: 是否启用精细扫描
        
        thickness_cm: 样品厚度 (cm)，与 chi 同步，供 EIS 电导率计算
        area_cm2: 电极面积 (cm²)，与 chi 同步
        min_conductivity_threshold: 电导率硬熔断阈值 (S/cm)，低于则自动停止
        state_persistence_path: 状态 JSON 路径；None 表示不写盘
    """
    cooling: CoolingConfig = field(default_factory=CoolingConfig)
    chi: ChiConfig = field(default_factory=ChiConfig)
    enable_phase_detection: bool = True
    enable_auto_stop: bool = True
    enable_fine_scan: bool = True
    
    thickness_cm: float = 0.1
    area_cm2: float = 1.96
    min_conductivity_threshold: float = 1e-8
    state_persistence_path: Optional[str] = None


# ============================================================
# 在线实验工作流
# ============================================================

class OnlineExperimentWorkflow:
    """
    在线实验工作流控制器（Agent 驱动版）
    
    编排 Agent 驱动的动态降温循环 + 单点测量事务 + 实时决策 + 异常处理
    """
    
    def __init__(
        self,
        temp_driver,  # TemperatureDriver
        chi_executor,  # ChiExecutor
        state_controller,  # StateController
        config: ExperimentConfig,
        eis_analyzer: Optional[Callable] = None,
        phase_detector: Optional[Callable] = None,
    ):
        """
        初始化工作流
        
        Args:
            temp_driver: 温度驱动器
            chi_executor: CHI 执行器
            state_controller: 状态控制器
            config: 实验配置
            eis_analyzer: EIS 分析函数 (可选)
            phase_detector: 相变检测函数 (可选，已弃用，使用 Agent 决策)
        """
        self.temp_driver = temp_driver
        self.chi_executor = chi_executor
        self.state = state_controller
        self.config = config
        self.eis_analyzer = eis_analyzer
        self.phase_detector = phase_detector
        
        # 运行时状态
        self._is_running = False
        self._should_stop = False
        self._stop_reason: Optional[str] = None
        
        # Agent 驱动的动态状态（新增）
        self._current_target_temp: float = config.cooling.T_start
        self._current_step_size: float = config.cooling.coarse_step
        self._measurement_count_in_loop: int = 0
        self._resume_skip_initial_cool: bool = False
        self._last_action_was_heating: bool = False
        
        # 细扫区 Agent 静音机制
        self._fine_scan_target_end_C: Optional[float] = None
        self._current_scan_mode: str = 'coarse'

    def _interruptible_sleep(self, seconds: float, chunk_s: float = 1.0) -> bool:
        """Sleep in short chunks so stop/pause requests are observed promptly."""
        deadline = time.time() + max(0.0, float(seconds))
        while time.time() < deadline:
            if self._should_stop or not self._is_running:
                return False
            time.sleep(min(chunk_s, max(0.0, deadline - time.time())))
        return True
    
    # ========================================================
    # 主入口：降温循环
    # ========================================================
    
    def run_cooling_loop(self) -> Dict[str, Any]:
        """
        运行 Agent 驱动的动态降温循环
        
        核心改进：
        1. 从静态温度列表改为动态 while 循环
        2. 每个点完成后立即调用 Agent 决策
        3. 根据 Agent 指令动态调整步长、目标温度
        4. 支持回温和细扫
        
        Returns:
            dict: 实验结果
                - success: bool
                - measurement_count: int
                - phase_count: int
                - stop_reason: str or None
                - error: str or None
                - agent_decisions: list[dict]（新增：记录所有 Agent 决策）
        """
        print("=" * 60)
        print("🤖 开始 Agent 驱动的在线实验流程")
        print("=" * 60)
        print(f"📍 起始温度: {self.config.cooling.T_start}°C")
        print(f"🎯 截止温度: {self.config.cooling.T_end}°C")
        print(f"📏 初始步长: {self.config.cooling.coarse_step}°C（动态调整）")
        print(f"🎯 温度容差: ±{self.config.cooling.eps}°C")
        print(f"🔒 最大测量点: {self.config.cooling.max_measurement_points}")
        print(f"🤖 Agent 决策: {'启用' if self.config.cooling.enable_agent_decision else '禁用'}")
        print("=" * 60)
        
        agent_decisions = []  # 记录所有 Agent 决策
        
        try:
            hist = self.state.get_measurement_history()
            self._resume_skip_initial_cool = len(hist) > 0
            
            if self._resume_skip_initial_cool:
                snap = self.state.get_resume_workflow_snapshot()
                prog = self.state.get_progress_state()
                if snap.get('next_target_temp_C') is not None:
                    self._current_target_temp = float(snap['next_target_temp_C'])
                    self._current_step_size = float(
                        snap.get('step_size_C', self.config.cooling.coarse_step)
                    )
                    self._measurement_count_in_loop = int(
                        snap.get('measurement_count_in_loop', len(hist))
                    )
                else:
                    last = hist[-1]
                    step = (
                        self.config.cooling.fine_step
                        if prog.current_scan_mode == 'fine'
                        else self.config.cooling.coarse_step
                    )
                    self._current_target_temp = last.temperature_C - step
                    self._current_step_size = step
                    self._measurement_count_in_loop = len(hist)
                print(f"\n⏯️ 断点续测：已有 {len(hist)} 条测量记录，跳过起始降温/第一点")
                print(f"   恢复下一目标约: {self._current_target_temp:.1f}°C "
                      f"(步长 {self._current_step_size:.1f}°C)")
            
            # 1. 初始化实验（续测时保留扫描模式与历史）
            self._initialize_experiment(preserve_progress=self._resume_skip_initial_cool)
            
            # 2. 验证硬件
            if not self._verify_hardware():
                return {
                    'success': False,
                    'error': 'Hardware verification failed',
                    'measurement_count': 0,
                    'phase_count': 0,
                    'agent_decisions': agent_decisions,
                }
            
            # 3. 降温到起始温度并测量（续测跳过）
            if not self._resume_skip_initial_cool:
                if not self._cool_to_start_and_measure():
                    return {
                        'success': False,
                        'error': 'Failed to reach start temperature',
                        'measurement_count': self.state.get_measurement_count(),
                        'phase_count': len(self.state.get_phase_transitions()),
                        'agent_decisions': agent_decisions,
                    }
            # 4. Agent 驱动的动态降温循环（新核心逻辑）
            agent_decisions = self._run_agent_driven_loop()
            
            # 5. 完成实验
            self._finalize_experiment()
            
            return {
                'success': True,
                'measurement_count': self.state.get_measurement_count(),
                'phase_count': len(self.state.get_phase_transitions()),
                'stop_reason': self._stop_reason,
                'error': None,
                'agent_decisions': agent_decisions
            }
        
        except Exception as e:
            print(f"\n❌ 实验异常: {str(e)}")
            import traceback
            traceback.print_exc()
            
            self._finalize_experiment()
            
            return {
                'success': False,
                'error': str(e),
                'measurement_count': self.state.get_measurement_count(),
                'phase_count': len(self.state.get_phase_transitions()),
                'agent_decisions': agent_decisions,
            }
    
    # ========================================================
    # 内部流程：实验初始化
    # ========================================================
    
    def _initialize_experiment(self, preserve_progress: bool = False) -> None:
        """初始化实验"""
        print("\n📋 初始化实验...")
        
        # 启动实验
        self.state.start_experiment(metadata={
            'material': self.config.chi.material,
            'T_start': self.config.cooling.T_start,
            'T_end': self.config.cooling.T_end,
            'coarse_step': self.config.cooling.coarse_step,
            'fine_step': self.config.cooling.fine_step,
            'thickness_cm': self.config.thickness_cm,
            'area_cm2': self.config.area_cm2,
        })
        
        if not preserve_progress:
            self.state.set_scan_mode('coarse')
        
        self._is_running = True
        self._should_stop = False
        self._stop_reason = None
        
        print("✅ 实验初始化完成")
    
    def _maybe_persist_state(self) -> None:
        """将当前状态写入 state_persistence_path（若已配置）。"""
        path = self.config.state_persistence_path
        if not path:
            return
        try:
            self.state.save_state(path)
        except OSError as e:
            print(f"⚠️ 状态持久化失败: {e}")
    
    def _sync_resume_and_persist(self) -> None:
        """更新断点快照中的下一目标温/步长/循环计数并写盘。"""
        self.state.update_resume_workflow_snapshot(
            self._current_target_temp,
            self._current_step_size,
            self._measurement_count_in_loop,
        )
        self._maybe_persist_state()
    
    def persist_checkpoint(self) -> None:
        """供外部（如 run_online 退出时）写入断点文件。"""
        self._sync_resume_and_persist()
    
    def _verify_hardware(self) -> bool:
        """验证硬件状态"""
        print("\n🔧 验证硬件状态...")
        
        try:
            # 检查温度驱动器连接
            if not self.temp_driver.is_connected():
                print("❌ 温度驱动器未连接")
                return False
            
            # 尝试读取温度
            temp_result = self.temp_driver.read_temperature()
            if not temp_result['success']:
                print(f"❌ 无法读取温度: {temp_result['error']}")
                return False
            
            current_temp = temp_result['temperature']
            print(f"✅ 当前温度: {current_temp}°C")
            
            # 更新状态
            self.state.update_temperature(current_temp)
            
            return True
        
        except Exception as e:
            print(f"❌ 硬件验证异常: {str(e)}")
            return False
    
    # ========================================================
    # 内部流程：降温到起始温度
    # ========================================================
    
    def _cool_to_start_and_measure(self) -> bool:
        """降温到起始温度并测量"""
        print(f"\n📉 降温到起始温度: {self.config.cooling.T_start}°C")
        
        # 降温
        reached = self._precise_cool_to_target(self.config.cooling.T_start)
        
        if not reached:
            print(f"❌ 未能到达起始温度")
            return False
        
        print(f"✅ 到达起始温度: {self.config.cooling.T_start}°C")
        
        # 测量
        print(f"\n🧪 [第1次测量] 起始温度 {self.config.cooling.T_start}°C")
        
        for retry in range(self.config.cooling.measurement_max_retry):
            if self._perform_single_measurement(self.config.cooling.T_start, step_type='coarse'):
                print(f"✅ 起始温度测量完成")
                return True
            
            if retry < self.config.cooling.measurement_max_retry - 1:
                print(f"⚠️ 测量失败，重试 ({retry + 1}/{self.config.cooling.measurement_max_retry})...")
                # 重新稳定温度
                self._wait_for_stable(self.config.cooling.T_start)
        
        print(f"❌ 起始温度测量失败")
        return False
    
    # ========================================================
    # 核心：Agent 驱动的动态降温循环（v3.0.0 新增）
    # ========================================================
    
    def _run_agent_driven_loop(self) -> list:
        """
        Agent 驱动的动态降温循环（核心重构）
        
        核心逻辑：
        1. while 循环代替静态温度列表
        2. 每个点完成后调用 Agent 决策
        3. 根据 Agent 指令动态调整步长、目标温度
        4. 持久化 Agent 决策结果
        
        Returns:
            list[dict]: Agent 决策记录列表
        """
        print(f"\n🤖 ========== Agent 驱动的动态降温循环开始 ==========")
        
        agent_decisions = []
        
        # 初始化动态变量（断点续测时已在 run_cooling_loop 中恢复）
        if not self._resume_skip_initial_cool:
            self._current_target_temp = self.config.cooling.T_start - self._current_step_size
            self._measurement_count_in_loop = 0
            self._current_scan_mode = 'coarse'
            self._fine_scan_target_end_C = None
        self._resume_skip_initial_cool = False
        
        self._sync_resume_and_persist()
        
        while True:
            # ===== 安全检查 =====
            # 1. 检查最大测量点数（防止 Agent 死循环）
            if self._measurement_count_in_loop >= self.config.cooling.max_measurement_points:
                print(f"\n🛑 达到最大测量点数 ({self.config.cooling.max_measurement_points})，停止实验")
                self._stop_reason = 'Max measurement points reached'
                break
            
            # 2. 检查手动停止信号
            if self._should_stop:
                print(f"\n🛑 检测到停止信号: {self._stop_reason}")
                break
            
            # 3. 检查暂停
            self._handle_pause_if_needed()
            
            if not self._is_running:
                break
            
            # ===== 降温到目标温度 =====
            print(f"\n[{self._measurement_count_in_loop + 1}] 准备降温到: {self._current_target_temp:.1f}°C")
            
            reached = self._precise_cool_to_target(self._current_target_temp)
            
            if not reached:
                print(f"⚠️ 未能到达目标温度 {self._current_target_temp:.1f}°C")
            
            # ===== 执行测量 =====
            print(f"🧪 在 {self._current_target_temp:.1f}°C 进行测量...")
            
            measurement_success = False
            for retry in range(self.config.cooling.measurement_max_retry):
                step_type = 'coarse' if self._current_step_size >= 3.0 else 'fine'
                
                if self._perform_single_measurement(self._current_target_temp, step_type=step_type):
                    measurement_success = True
                    break
                
                if retry < self.config.cooling.measurement_max_retry - 1:
                    print(f"⚠️ 测量失败，重试 ({retry + 1}/{self.config.cooling.measurement_max_retry})...")
                    self._wait_for_stable(self._current_target_temp)
            
            if not measurement_success:
                print(f"❌ 测量多次失败，继续下一个点")
            
            self._measurement_count_in_loop += 1
            
            # ===== 硬性物理熔断：电导率低于阈值 =====
            last_rec = self.state.get_last_measurement()
            if (
                last_rec is not None
                and last_rec.conductivity_S_per_cm is not None
                and last_rec.conductivity_S_per_cm < self.config.min_conductivity_threshold
            ):
                print(f"\n🛑 电导率硬熔断触发:")
                print(f"   当前电导率: {last_rec.conductivity_S_per_cm:.2e} S/cm")
                print(f"   阈值: {self.config.min_conductivity_threshold:.2e} S/cm")
                print(f"   样品已失去研究价值，安全结束实验")
                self.stop(reason=f"电导率低于设定阈值 ({last_rec.conductivity_S_per_cm:.2e} < {self.config.min_conductivity_threshold:.2e} S/cm)")
                break
            
            # ===== Agent 静音机制：细扫区间自动密集采样 =====
            if self._current_scan_mode == 'fine' and self._fine_scan_target_end_C is not None:
                current_temp = self.state.get_current_temperature()
                
                # 检查是否已到达细扫区间终点
                if current_temp <= self._fine_scan_target_end_C:
                    print(f"\n🔊 [系统] 密集测量区间结束 ({self._fine_scan_target_end_C:.1f}°C)")
                    print(f"   恢复 Agent 监控模式")
                    
                    # 清除细扫终点标记
                    self._fine_scan_target_end_C = None
                    
                    # 切回粗扫模式
                    self._current_scan_mode = 'coarse'
                    self.state.set_scan_mode('coarse')
                    self._current_step_size = self.config.cooling.coarse_step
                    
                    print(f"   切回粗扫模式 (步长: {self._current_step_size:.1f}°C)")
                else:
                    # 仍在细扫区间内，静音 Agent，自动执行细扫步长
                    print(f"\n🔇 [系统] 当前处于密集测量区间，静音 Agent")
                    print(f"   区间终点: {self._fine_scan_target_end_C:.1f}°C")
                    print(f"   当前温度: {current_temp:.1f}°C")
                    print(f"   自动执行细扫步长: {self.config.cooling.fine_step}°C")
                    
                    # 计算下一个目标温度
                    self._current_target_temp = current_temp - self.config.cooling.fine_step
                    self.state.set_target_temperature(
                        self._current_target_temp,
                        is_cooling=True
                    )
                    
                    # 检查是否低于截止温度
                    if self._current_target_temp < self.config.cooling.T_end:
                        print(f"\n✅ 达到截止温度 ({self.config.cooling.T_end}°C)，停止实验")
                        self._stop_reason = 'Reached target temperature'
                        self._sync_resume_and_persist()
                        break
                    
                    # 跳过 Agent 调用，直接进入下一轮测量
                    self._sync_resume_and_persist()
                    continue
            
            # ===== 核心：调用 Agent 决策 =====
            # 注：已移除全局 Arrhenius 实时拟合，Agent 现在基于局部斜率
            decision = self._call_agent_decision()
            
            if decision:
                agent_decisions.append(decision)
                
                # 执行 Agent 指令
                should_continue = self._execute_agent_action(decision)
                
                if not should_continue:
                    self._sync_resume_and_persist()
                    break
            else:
                # Agent 调用失败，使用默认策略
                print(f"⚠️ Agent 决策失败，使用默认策略：继续当前步长")
                self._current_target_temp -= self._current_step_size
                
                # ✅ 修复 LOGIC-1：调用硬件驱动
                result = self.temp_driver.set_temperature(
                    self._current_target_temp,
                    is_cooling=True
                )
                
                if result['success']:
                    self.state.set_target_temperature(
                        self._current_target_temp,
                        is_cooling=True,
                    )
                else:
                    print(f"   ❌ 温度设置失败: {result.get('error')}，保持原目标温度")
                    # 恢复原温度
                    self._current_target_temp += self._current_step_size
                
                # 检查是否低于截止温度
                if self._current_target_temp < self.config.cooling.T_end:
                    print(f"\n✅ 达到截止温度 ({self.config.cooling.T_end}°C)，停止实验")
                    self._stop_reason = 'Reached target temperature'
                    self._sync_resume_and_persist()
                    break
            
            self._sync_resume_and_persist()
        
        print(f"\n✅ Agent 驱动的动态降温循环完成")
        print(f"   总测量点数: {self._measurement_count_in_loop}")
        print(f"   Agent 决策次数: {len(agent_decisions)}")
        
        return agent_decisions
    
    def _call_agent_decision(self) -> Optional[Dict[str, Any]]:
        """
        调用 Agent 决策（核心集成点）
        
        Returns:
            dict or None: Agent 决策结果
        """
        # 如果禁用 Agent 决策，返回 None
        if not self.config.cooling.enable_agent_decision:
            return None
        
        try:
            print(f"\n🤖 调用 Agent 决策...")
            
            # 1. 构建 Agent 上下文（新格式：直接传递 measurement_history）
            agent_context = {
                'measurement_history': self.state.get_measurement_history()
            }
            
            # 2. 调用 Agent
            from modules.analysis.phase_detect import analyze_experiment_state
            
            decision = analyze_experiment_state(
                agent_context=agent_context,
                api_key=self.config.cooling.agent_api_key
            )
            
            # 3. 打印决策结果
            print(f"   数据质量: {decision.get('data_quality', 'UNKNOWN')}")
            print(f"   决策动作: {decision.get('action', 'UNKNOWN')}")
            print(f"   置信度: {decision.get('confidence', 0):.2f}")
            print(f"   推理: {decision.get('reasoning', 'N/A')[:100]}...")
            
            if decision.get('warnings'):
                for warning in decision['warnings']:
                    print(f"   ⚠️ {warning}")
            
            return decision
        
        except Exception as e:
            print(f"❌ Agent 决策异常: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
    
    def _execute_agent_action(self, decision: Dict[str, Any]) -> bool:
        """
        执行 Agent 指令
        
        Args:
            decision: Agent 决策结果
        
        Returns:
            bool: 是否继续实验（False 表示停止）
        """
        action = decision.get('action', 'CONTINUE')
        action_params = decision.get('action_params', {})
        
        print(f"\n🎯 执行 Agent 指令: {action}")
        
        # ===== 动作 1: CONTINUE =====
        if action == 'CONTINUE':
            next_temp_K = action_params.get('next_temp_target_K')
            step_size_K = action_params.get('step_size_K', self._current_step_size)
            
            if next_temp_K is not None:
                target_C = float(next_temp_K) - 273.15
                cur_C = self.state.get_current_temperature()
                self.state.set_target_temperature(target_C, is_cooling=(target_C < cur_C))
                self._current_target_temp = target_C
                self._last_action_was_heating = False
            else:
                self._current_target_temp -= self._current_step_size
                
                # ✅ 修复 LOGIC-2：调用硬件驱动
                result = self.temp_driver.set_temperature(
                    self._current_target_temp,
                    is_cooling=True
                )
                
                if result['success']:
                    self.state.set_target_temperature(
                        self._current_target_temp,
                        is_cooling=True
                    )
                    self._last_action_was_heating = False
                else:
                    print(f"   ❌ 温度设置失败: {result.get('error')}，保持原目标温度")
                    # 恢复原温度
                    self._current_target_temp += self._current_step_size
            
            if step_size_K:
                self._current_step_size = float(step_size_K)
            
            print(f"   ➡️ 下一目标: {self._current_target_temp:.1f}°C (步长: {self._current_step_size:.1f}K)")
            
            if self._current_target_temp < self.config.cooling.T_end:
                print(f"\n✅ 达到截止温度 ({self.config.cooling.T_end}°C)")
                self._stop_reason = 'Reached target temperature'
                return False
            
            return True
        
        # ===== 动作 2: FINE_GRAINED_SCAN =====
        elif action == 'FINE_GRAINED_SCAN':
            next_temp_K = action_params.get('next_temp_target_K')
            step_size_K = action_params.get('step_size_K', 1.0)
            
            if next_temp_K is not None:
                new_target_C = float(next_temp_K) - 273.15
                cur_C = self.state.get_current_temperature()
                
                # ===== 硬编码安全护栏：限制回温范围 =====
                temp_change = new_target_C - cur_C
                MAX_REHEAT_RANGE = 15.0  # 最大回温范围：15K
                
                if temp_change > MAX_REHEAT_RANGE:
                    print(f"   ⚠️ Agent要求回温 {temp_change:.1f}°C，超出安全范围（最大{MAX_REHEAT_RANGE}K）")
                    print(f"   🔧 自动限制：{new_target_C:.1f}°C → {cur_C + MAX_REHEAT_RANGE:.1f}°C")
                    new_target_C = cur_C + MAX_REHEAT_RANGE
                    next_temp_K = new_target_C + 273.15
                elif temp_change < -10.0:
                    print(f"   ⚠️ Agent要求降温过多 ({temp_change:.1f}°C)，FINE_GRAINED_SCAN应该回温")
                    print(f"   🔧 改为向上回温5K: {cur_C:.1f}°C → {cur_C + 5.0:.1f}°C")
                    new_target_C = cur_C + 5.0
                    next_temp_K = new_target_C + 273.15
                
                # 回温：必须驱动硬件并等待稳定 + 热惰性惩罚
                if new_target_C > self._current_target_temp:
                    print(f"   🔙 回温到: {new_target_C:.1f}°C")
                    print(f"   ⚠️ 升温后转降温拐点，将执行增强稳定性验证")
                    
                    result = self.temp_driver.set_temperature(new_target_C, is_cooling=False)
                    if result['success']:
                        self.state.set_target_temperature(new_target_C, is_cooling=False)
                        
                        print(f"   ⏰ 等待回温稳定（热惰性惩罚：额外 3 分钟均温化）...")
                        if not self._interruptible_sleep(180):
                            return False
                        
                        print(f"   🔍 开始增强稳定性验证（2 倍标准次数）...")
                        if not self._wait_for_stable_enhanced(new_target_C, multiplier=2.0):
                            print(f"   ⚠️ 回温后增强稳定验证未完全满足，仍采用 Agent 给定目标")
                        
                        self._current_target_temp = new_target_C
                        self._last_action_was_heating = True
                    else:
                        print(f"   ❌ 回温失败: {result.get('error')}，保持原目标温度")
                
                # 降温或保持：也需要驱动硬件（修复：原来缺少硬件调用）
                else:
                    is_cooling_down = (new_target_C < cur_C)
                    
                    if is_cooling_down:
                        print(f"   📉 继续降温到: {new_target_C:.1f}°C")
                    else:
                        print(f"   ➡️ 保持温度: {new_target_C:.1f}°C")
                    
                    result = self.temp_driver.set_temperature(new_target_C, is_cooling=is_cooling_down)
                    if result['success']:
                        self.state.set_target_temperature(new_target_C, is_cooling=is_cooling_down)
                        self._current_target_temp = new_target_C
                        self._last_action_was_heating = False
                    else:
                        print(f"   ❌ 温度设置失败: {result.get('error')}，保持原目标温度")
            
            # 切换细扫 + 设定静音区间终点
            self._current_step_size = float(step_size_K)
            self._current_scan_mode = 'fine'
            self.state.set_scan_mode('fine')
            
            # 计算并记录细扫区间终点
            self._fine_scan_target_end_C = self._current_target_temp - self.config.cooling.fine_scan_window_C
            
            print(f"   🔍 切换到细扫模式 (步长: {self._current_step_size:.1f}K)")
            print(f"   📍 密集测量区间: {self._current_target_temp:.1f}°C → {self._fine_scan_target_end_C:.1f}°C")
            print(f"   🔇 Agent 将在此区间静音，自动执行密集采样")
            print(f"   ➡️ 下一目标: {self._current_target_temp:.1f}°C")
            
            return True
        
        # ===== 动作 3: ABORT =====
        elif action == 'ABORT':
            print(f"   🛑 Agent 指令：停止实验")
            print(f"   原因: {decision.get('reasoning', 'Unknown')}")
            
            self._stop_reason = f"Agent ABORT: {decision.get('reasoning', 'Unknown')}"
            self._should_stop = True
            
            # 安全关闭硬件
            print(f"   🔒 安全关闭硬件...")
            try:
                close = getattr(self.chi_executor, "close", None)
                if callable(close):
                    close()
                print(f"   ✅ CHI 连接已关闭")
            except Exception as e:
                print(f"   ⚠️ CHI 关闭异常: {e}")
            
            try:
                current_temp_result = self.temp_driver.read_temperature()
                if current_temp_result['success']:
                    current_temp = current_temp_result['temperature']
                    self.temp_driver.set_temperature(current_temp + 5, is_cooling=False)
                    print(f"   ✅ 温控已停止")
            except Exception as e:
                print(f"   ⚠️ 温控停止异常: {e}")
            
            return False
        
        else:
            print(f"   ⚠️ 未知动作: {action}，默认继续")
            self._current_target_temp -= self._current_step_size
            self._last_action_was_heating = False
            return True
    
    # ========================================================
    # 内部流程：计算测量点（已弃用，保留兼容性）
    # ========================================================
    
    def _calculate_measurement_points(self) -> list:
        """计算测量点列表（已弃用，Agent 版不使用）"""
        points = []
        temp = self.config.cooling.T_start - self.config.cooling.coarse_step
        
        while temp > self.config.cooling.T_end:
            points.append(temp)
            temp -= self.config.cooling.coarse_step
        
        # 确保终点温度包含
        if not points or points[-1] != self.config.cooling.T_end:
            points.append(self.config.cooling.T_end)
        
        return points
    
    # ========================================================
    # 内部流程：主降温循环
    # ========================================================
    
    def _run_main_cooling_loop(self, measurement_points: list) -> None:
        """运行主降温循环"""
        print(f"\n🔄 ========== 主降温循环开始 ==========")
        
        for i, target_temp in enumerate(measurement_points):
            # 检查停止条件
            if self._should_stop:
                print(f"\n🛑 检测到停止信号: {self._stop_reason}")
                break
            
            # 检查暂停
            self._handle_pause_if_needed()
            
            if not self._is_running:
                break
            
            print(f"\n[{i + 2}/{len(measurement_points) + 1}] 准备降温到: {target_temp}°C")
            
            # 降温
            reached = self._precise_cool_to_target(target_temp)
            
            if not reached:
                print(f"⚠️ 未能到达目标温度 {target_temp}°C，继续...")
                continue
            
            # 测量
            print(f"🧪 在 {target_temp}°C 进行测量...")
            
            for retry in range(self.config.cooling.measurement_max_retry):
                if self._perform_single_measurement(target_temp, step_type='coarse'):
                    break
                
                if retry < self.config.cooling.measurement_max_retry - 1:
                    print(f"⚠️ 测量失败，重试 ({retry + 1}/{self.config.cooling.measurement_max_retry})...")
                    self._wait_for_stable(target_temp)
            
            # 相变检测
            if self.config.enable_phase_detection and self.phase_detector:
                self._check_and_handle_phase_transition()
        
        print(f"\n✅ 主降温循环完成")
    
    # ========================================================
    # 内部流程：精确降温
    # ========================================================
    
    def _precise_cool_to_target(self, target_temp: float) -> bool:
        """
        精确降温到目标温度（改进版：一次性设置+耐心等待）
        
        策略：
        1. 一次性设置目标温度
        2. 每60秒检查一次温度
        3. 当接近目标（±1.5°C）时，改为每30秒检查
        4. 当达到目标范围（±0.5°C）时，开始严格的稳定性验证
        5. 如果过降（< 目标-0.5°C），等待自然回温
        
        Args:
            target_temp: 目标温度 (°C)
        
        Returns:
            bool: 是否成功到达目标
        """
        print(f"\n📉 精确降温到: {target_temp}°C ± {self.config.cooling.eps}°C")
        
        # 读取当前温度
        temp_result = self.temp_driver.read_temperature()
        if not temp_result['success']:
            print(f"❌ 无法读取当前温度")
            return False
        
        current_temp = temp_result['temperature']
        print(f"📍 当前温度: {current_temp:.1f}°C")
        
        temp_diff = current_temp - target_temp
        
        # 情况 A: 已在目标范围内
        if abs(temp_diff) <= self.config.cooling.eps:
            print(f"✅ 温度已在目标范围内 (差值: {temp_diff:+.2f}°C)")
            return self._wait_for_stable(target_temp)
        
        # ========== 关键改进：一次性设置目标温度 ==========
        # 【重要】精细测量时不加1°C补偿，直接设置到目标温度
        is_fine_scan = (self._current_scan_mode == 'fine')
        
        if is_fine_scan:
            print(f"🎯 设置目标温度（精细模式，无补偿）: {target_temp}°C")
            result = self.temp_driver.set_temperature(target_temp, is_cooling=False)
        else:
            print(f"🎯 设置目标温度（粗扫模式，+1°C补偿）: {target_temp}°C")
            result = self.temp_driver.set_temperature(target_temp, is_cooling=True)
        
        if not result['success']:
            print(f"❌ 设置温度失败: {result['error']}")
            return False
        
        self.state.set_target_temperature(target_temp, is_cooling=(not is_fine_scan))
        
        # ========== 耐心等待温度变化 ==========
        # 估算等待时间（每度约3-10分钟）
        if temp_diff > 0:
            estimated_min = abs(temp_diff) * 3
            estimated_max = abs(temp_diff) * 10
            print(f"⏳ 等待降温... (预计需要 {estimated_min:.0f}-{estimated_max:.0f} 分钟)")
        else:
            print(f"⏳ 检测到过降，等待自然回温...")
        
        max_wait_time = 3600  # 最长等待1小时
        normal_check_interval = 60  # 正常情况每60秒检查一次
        approach_check_interval = 30  # 接近目标时每30秒检查一次
        approach_threshold = 1.5  # 接近阈值：±1.5°C
        eps = self.config.cooling.eps  # 目标容差：±0.5°C
        
        start_time = time.time()
        check_interval = normal_check_interval
        is_approaching = False
        
        while time.time() - start_time < max_wait_time:
            if not self._interruptible_sleep(check_interval):
                return False
            
            # 读取当前温度
            temp_result = self.temp_driver.read_temperature()
            if not temp_result['success']:
                print(f"   ⚠️ 无法读取温度，继续等待...")
                continue
            
            current_temp = temp_result['temperature']
            diff = current_temp - target_temp
            elapsed_min = (time.time() - start_time) / 60
            
            # 判断温度状态
            if abs(diff) <= eps:
                # ✅ 进入目标范围，开始稳定性验证
                print(f"   ✅ 进入目标范围！{elapsed_min:.1f}分钟: 当前 {current_temp:.1f}°C, 差值 {diff:+.2f}°C")
                print(f"   🔍 开始稳定性验证...")
                return self._wait_for_stable(target_temp)
            
            elif diff < -eps:
                # ⚠️ 过降！温度低于目标，需要等待回温
                if not is_approaching:
                    print(f"   ⚠️ 检测到过降！当前 {current_temp:.1f}°C < 目标 {target_temp:.1f}°C")
                    print(f"   ⏰ 等待自然回温（回温速度较慢）...")
                    check_interval = approach_check_interval  # 改为30秒检查
                    is_approaching = True
                else:
                    print(f"   🔄 {elapsed_min:.1f}分钟: 当前 {current_temp:.1f}°C, 差值 {diff:+.2f}°C (回温中)")
            
            elif abs(diff) <= approach_threshold:
                # 🎯 接近目标范围，加密监控
                if not is_approaching:
                    print(f"   🎯 接近目标！改为每{approach_check_interval}秒监控")
                    check_interval = approach_check_interval
                    is_approaching = True
                print(f"   📊 {elapsed_min:.1f}分钟: 当前 {current_temp:.1f}°C, 差值 {diff:+.2f}°C")
            
            else:
                # 📉 正常降温中
                print(f"   📊 {elapsed_min:.1f}分钟: 当前 {current_temp:.1f}°C, 差值 {diff:+.2f}°C")
        
        print(f"   ⚠️ 等待超时 ({max_wait_time/60:.0f}分钟)，当前温度 {current_temp:.1f}°C")
        return False
    
    # ========================================================
    # 旧降温方法（已废弃，被新策略替代）
    # ========================================================
    # 
    # def _step_by_step_cooling(self, start_temp: float, target_temp: float) -> bool:
    #     """
    #     【已废弃】一度一度缓慢降温
    #     
    #     问题：
    #     1. 每次设置温度后立即检查稳定性，太着急
    #     2. 物理降温需要时间，频繁设置温度会导致不稳定
    #     3. 等待时间不足，无法让系统充分降温/回温
    #     
    #     已被 _precise_cool_to_target 的新策略替代：
    #     - 一次性设置目标温度
    #     - 耐心等待（每60秒检查）
    #     - 接近目标时加密监控（每30秒）
    #     - 处理过降情况（等待回温）
    #     """
    #     pass
    
    # ========================================================
    # 内部流程：等待温度稳定
    # ========================================================
    
    def _wait_for_stable(self, target_temp: float, check_recovery: bool = True) -> bool:
        """
        等待温度稳定
        
        Args:
            target_temp: 目标温度 (°C)
            check_recovery: 是否检查回温
        
        Returns:
            bool: 是否稳定
        """
        duration = self.config.cooling.stability_duration
        interval = self.config.cooling.stability_check_interval
        max_retry = self.config.cooling.stability_max_retry
        eps = self.config.cooling.eps
        
        checks_needed = duration // interval
        
        for retry in range(max_retry):
            stable_count = 0
            all_stable = True
            
            for check_num in range(checks_needed):
                temp_result = self.temp_driver.read_temperature()
                
                if not temp_result['success']:
                    print(f"   ⚠️ 第{check_num + 1}次检查：无法读取温度")
                    all_stable = False
                    break
                
                temp = temp_result['temperature']
                diff = temp - target_temp
                abs_diff = abs(diff)
                
                if abs_diff <= eps:
                    stable_count += 1
                    elapsed = (check_num + 1) * interval
                    print(f"   ✅ 稳定性检查 {check_num + 1}/{checks_needed}: "
                          f"{temp:.1f}°C (差值 {diff:+.2f}°C, {elapsed}秒)")
                    
                    # 更新状态
                    self.state.update_temperature(temp, is_stable=True, stable_count=stable_count)
                else:
                    print(f"   ❌ 稳定性检查 {check_num + 1}/{checks_needed}: "
                          f"{temp:.1f}°C (差值 {diff:+.2f}°C > ±{eps}°C)")
                    all_stable = False
                    break
                
                if check_num < checks_needed - 1:
                    if not self._interruptible_sleep(interval):
                        return False
            
            if all_stable and stable_count == checks_needed:
                print(f"   ✅ 温度稳定验证通过 ({duration}秒内均在±{eps}°C范围)")
                return True
            else:
                if retry < max_retry - 1:
                    print(f"   🔄 温度不稳定，重试 ({retry + 1}/{max_retry})...")
                    if not self._interruptible_sleep(10):
                        return False
        
        print(f"   ❌ 温度稳定验证失败")
        return False
    
    def _wait_for_stable_enhanced(
        self,
        target_temp: float,
        multiplier: float = 2.0,
        check_recovery: bool = True
    ) -> bool:
        """
        增强稳定性验证（用于回温后转降温拐点，克服热惰性）
        
        Args:
            target_temp: 目标温度 (°C)
            multiplier: 连续稳定次数倍数（默认 2.0）
            check_recovery: 是否检查回温
        
        Returns:
            bool: 是否稳定
        """
        duration = self.config.cooling.stability_duration
        interval = self.config.cooling.stability_check_interval
        max_retry = self.config.cooling.stability_max_retry
        eps = self.config.cooling.eps
        
        checks_needed = int((duration // interval) * multiplier)
        
        print(f"   🔍 增强稳定验证：需连续 {checks_needed} 次检查（标准 × {multiplier:.1f}）")
        
        for retry in range(max_retry):
            stable_count = 0
            all_stable = True
            
            for check_num in range(checks_needed):
                temp_result = self.temp_driver.read_temperature()
                
                if not temp_result['success']:
                    print(f"   ⚠️ 第{check_num + 1}次检查：无法读取温度")
                    all_stable = False
                    break
                
                temp = temp_result['temperature']
                diff = temp - target_temp
                abs_diff = abs(diff)
                
                if abs_diff <= eps:
                    stable_count += 1
                    elapsed = (check_num + 1) * interval
                    if (check_num + 1) % 4 == 0 or check_num == checks_needed - 1:
                        print(f"   ✅ 增强检查 {check_num + 1}/{checks_needed}: "
                              f"{temp:.1f}°C (差值 {diff:+.2f}°C, {elapsed}秒)")
                    
                    self.state.update_temperature(temp, is_stable=True, stable_count=stable_count)
                else:
                    print(f"   ❌ 增强检查 {check_num + 1}/{checks_needed}: "
                          f"{temp:.1f}°C (差值 {diff:+.2f}°C > ±{eps}°C)")
                    all_stable = False
                    break
                
                if check_num < checks_needed - 1:
                    if not self._interruptible_sleep(interval):
                        return False
            
            if all_stable and stable_count == checks_needed:
                total_time = checks_needed * interval
                print(f"   ✅ 增强稳定验证通过 ({total_time}秒内均在±{eps}°C范围)")
                return True
            else:
                if retry < max_retry - 1:
                    print(f"   🔄 温度不稳定，重试 ({retry + 1}/{max_retry})...")
                    if not self._interruptible_sleep(10):
                        return False
        
        print(f"   ❌ 增强稳定验证失败")
        return False
    
    # ========================================================
    # 内部流程：单点测量事务
    # ========================================================
    
    # 注：_sync_arrhenius_before_agent() 函数已废弃
    # Agent 现在基于局部斜率监测，不再需要全局 Arrhenius 实时拟合
    # Arrhenius 分析保留用于实验完成后的离线批处理
    
    def _perform_single_measurement(self, target_temp: float, step_type: str) -> bool:
        """
        执行单点测量事务（CHI + EIS + 状态更新）
        
        Args:
            target_temp: 目标温度 (°C)
            step_type: 步骤类型 ('coarse' | 'fine')
        
        Returns:
            bool: 是否成功
        """
        print(f"\n🔬 开始测量事务 (T={target_temp}°C, 类型={step_type})")
        
        # 1. 验证温度稳定性
        print(f"🔍 验证温度稳定性 ({self.config.cooling.stability_duration}秒)...")
        
        if not self._wait_for_stable(target_temp):
            print(f"❌ 温度不稳定，测量失败")
            return False
        
        # 2. 执行 CHI 测量
        print(f"🤖 执行 CHI GUI 自动化...")
        
        chi_params = {
            'material': self.config.chi.material,
            'highf': self.config.chi.highf,
            'lowf': self.config.chi.lowf,
            'initV': self.config.chi.initV,
            'your_position': self.config.chi.your_position,
            'template_dir': self.config.chi.template_dir,
        }
        
        chi_result = self.chi_executor.execute_measurement(
            chi_params=chi_params,
            output_dir=self.config.chi.your_position,
            current_temperature_C=target_temp
        )
        
        if not chi_result['success']:
            print(f"❌ CHI 测量失败: {chi_result['error']}")
            return False
        
        print(f"✅ CHI 测量成功，获得 {len(chi_result['frequencies']) if chi_result['frequencies'] is not None else 0} 个数据点")
        
        # 3. EIS 分析
        print(f"🧮 执行 EIS 分析...")
        
        if self.eis_analyzer and chi_result['frequencies'] is not None:
            eis_result = self.eis_analyzer(
                frequencies=chi_result['frequencies'],
                z_real=chi_result['z_real'],
                z_imag=chi_result['z_imag'],
                temperature_K=target_temp + 273.15,
                thickness_cm=self.config.thickness_cm,
                area_cm2=self.config.area_cm2,
            )
            
            # 从嵌套的 rb_result 中提取数据
            rb_result = eis_result.get('rb_result', {})
            rb_ohm = rb_result.get('rb_ohm') if rb_result else None
            conductivity = rb_result.get('conductivity_s_per_cm') if rb_result else None
            rb_method = rb_result.get('method') if rb_result else None
            r_squared = rb_result.get('fit_quality') if rb_result else None
            
            from modules.analysis.eis_pipeline import make_json_safe
            # 完整单点分析契约（QA/KK/Rb 等）入库，numpy 等转为 JSON 安全结构
            analysis_payload = make_json_safe(eis_result)
            
            print(f"✅ EIS 分析完成")
            if eis_result.get('success'):
                print(f"   Rb: {rb_ohm} Ω")
                print(f"   电导率: {conductivity} S/cm")
        else:
            # 无分析器或无数据，创建占位结果
            eis_result = {
                'success': False,
                'error': 'No analyzer or no data'
            }
            rb_ohm = None
            conductivity = None
            rb_method = None
            r_squared = None
            analysis_payload = {}
        
        # 4. 创建测量记录
        from controllers import create_measurement_record
        
        record = create_measurement_record(
            temperature_C=target_temp,
            timestamp=time.time(),
            step_type=step_type,
            raw_data_path=chi_result.get('output_file'),
            raw_data_exists=chi_result.get('output_file') is not None,
            eis_data={
                'frequencies': chi_result.get('frequencies'),
                'z_real': chi_result.get('z_real'),
                'z_imag': chi_result.get('z_imag'),
            },
            analysis=analysis_payload,
            rb_ohm=rb_ohm,
            rb_method=rb_method,
            conductivity_S_per_cm=conductivity,
            fit_quality=r_squared,
            r_squared=r_squared,
            success=eis_result.get('success', False),
            failure_reason=eis_result.get('error') if not eis_result.get('success') else None,
        )
        
        # 5. 添加到状态（全局 Arrhenius 在 Agent 调用前的 _sync_arrhenius_before_agent 中刷新）
        record_index = self.state.add_measurement_record(record)
        print(f"✅ 测量记录已保存 (索引: {record_index})")
        
        # 6. 自动停止检测
        if self.config.enable_auto_stop:
            should_stop, reason = self._check_auto_stop_condition(record)
            if should_stop:
                self._should_stop = True
                self._stop_reason = reason
                print(f"\n⚠️ 触发自动停止: {reason}")
        
        return True
    
    # ========================================================
    # 内部流程：相变检测
    # ========================================================
    
    def _check_and_handle_phase_transition(self) -> None:
        """检查并处理相变"""
        if not self.phase_detector:
            return
        
        # 获取最近的测量记录
        recent = self.state.get_recent_measurements(5)
        
        if len(recent) < 3:
            return  # 数据点不足
        
        # 调用相变检测
        try:
            detection_result = self.phase_detector(recent)
            
            if detection_result.get('phase_detected'):
                temp_range = detection_result.get('temperature_range')
                scores = detection_result.get('scores', {})
                
                print(f"\n🔍 检测到相变候选: {temp_range[0]:.1f}°C ~ {temp_range[1]:.1f}°C")
                
                # 添加到相变候选队列
                self.state.add_phase_candidate(
                    start_temp_C=temp_range[0],
                    end_temp_C=temp_range[1],
                    detection_scores=scores
                )
                
                # 如果启用精细扫描，可以在这里触发精细测量
                # ...
        
        except Exception as e:
            print(f"⚠️ 相变检测异常: {str(e)}")
    
    # ========================================================
    # 内部流程：自动停止检测
    # ========================================================
    
    def _check_auto_stop_condition(self, record) -> Tuple[bool, Optional[str]]:
        """
        检查是否满足自动停止条件
        
        Args:
            record: 测量记录
        
        Returns:
            Tuple[bool, Optional[str]]: (是否停止, 原因)
        """
        # 示例：Rb 过大
        if record.rb_ohm is not None and record.rb_ohm > 1e6:
            return True, f"Rb 过大 ({record.rb_ohm:.2e} Ω > 1e6 Ω)"
        
        thr = self.config.min_conductivity_threshold
        if record.conductivity_S_per_cm is not None and record.conductivity_S_per_cm < thr:
            return True, (
                f"电导率硬熔断 ({record.conductivity_S_per_cm:.2e} S/cm < {thr:.2e} S/cm)"
            )
        
        # 示例：连续失败
        recent = self.state.get_recent_measurements(3)
        if len(recent) == 3 and all(not r.success for r in recent):
            return True, "连续 3 次测量失败"
        
        return False, None
    
    # ========================================================
    # 内部流程：暂停处理
    # ========================================================
    
    def _handle_pause_if_needed(self) -> None:
        """处理暂停"""
        if not self.state.is_paused():
            return
        
        print(f"\n⏸️ 实验已暂停")
        print(f"💡 等待恢复...")
        
        # 保持当前温度
        current_temp = self.state.get_current_temperature()
        
        while self.state.is_paused():
            # 定期检查温度，防止漂移
            temp_result = self.temp_driver.read_temperature()
            if temp_result['success']:
                temp = temp_result['temperature']
                diff = abs(temp - current_temp)
                
                if diff > self.config.cooling.eps * 2:
                    print(f"📉 温度漂移，重新设置: {current_temp:.1f}°C")
                    self.temp_driver.set_temperature(current_temp, is_cooling=False)
            
            if not self._interruptible_sleep(5):
                break
        
        print(f"▶️ 实验恢复")
    
    # ========================================================
    # 内部流程：完成实验
    # ========================================================
    
    def _finalize_experiment(self) -> None:
        """完成实验"""
        print(f"\n✅ 实验流程完成")
        
        self.persist_checkpoint()
        
        # 完成实验
        self.state.complete_experiment()
        
        # 打印统计
        print(f"\n📊 实验统计:")
        print(f"   总测量次数: {self.state.get_measurement_count()}")
        print(f"   检测到相变: {len(self.state.get_phase_transitions())} 个")
        
        if self._stop_reason:
            print(f"   停止原因: {self._stop_reason}")
        
        # ===== 新增：全局 Arrhenius 分段分析 =====
        print(f"\n" + "="*80)
        print(f"🔬 执行全局 Arrhenius 分段分析（实验完成后离线分析）")
        print(f"="*80)
        
        try:
            measurement_history = self.state.get_measurement_history()
            
            if len(measurement_history) < 5:
                print(f"⚠️ 测量点不足（{len(measurement_history)} < 5），跳过 Arrhenius 分析")
            else:
                # 准备数据格式
                measurement_records = []
                for rec in measurement_history:
                    if rec.conductivity_S_per_cm is not None and rec.conductivity_S_per_cm > 0:
                        measurement_records.append({
                            'success': True,
                            'temperature_K': rec.temperature_C + 273.15,
                            'conductivity_s_per_cm': rec.conductivity_S_per_cm
                        })
                
                print(f"   有效数据点: {len(measurement_records)}")
                
                if len(measurement_records) < 5:
                    print(f"   ⚠️ 有效数据点不足，无法分析")
                else:
                    # 调用 Arrhenius 分析
                    from modules.analysis.algorithms.arrhenius import analyze_arrhenius_series
                    
                    print(f"   开始竞争性多模型分析...")
                    arrhenius_result = analyze_arrhenius_series(
                        measurement_records,
                        min_points=5,
                        min_segment_points=4,
                        aic_improvement_threshold=5.0
                    )
                    
                    if arrhenius_result.get('success'):
                        print(f"\n   ✅ Arrhenius 分析完成")
                        print(f"      最佳模型: {arrhenius_result.get('best_model_type')}")
                        print(f"      段数: {arrhenius_result.get('n_segments', 0)}")
                        print(f"      置信度: {arrhenius_result.get('confidence', 0)*100:.1f}%")
                        
                        # 打印模型概率分布
                        print(f"\n   [模型概率分布]")
                        model_probs = arrhenius_result.get('model_probabilities', {})
                        for model_name, prob in model_probs.items():
                            print(f"      {model_name}: {prob*100:.1f}%")
                        
                        # 打印相变温度
                        transition_temps = arrhenius_result.get('transition_temps_K', [])
                        if transition_temps:
                            print(f"\n   [检测到的相变温度]")
                            for i, T_K in enumerate(transition_temps, 1):
                                print(f"      Tc{i} = {T_K:.2f} K ({T_K-273.15:.2f}°C)")
                        else:
                            print(f"\n   [未检测到相变]")
                        
                        # 打印各段活化能
                        print(f"\n   [各段活化能]")
                        segments = arrhenius_result.get('segments', [])
                        for i, seg in enumerate(segments):
                            Ea_kJ_mol = seg.get('Ea_kJ_per_mol')
                            if Ea_kJ_mol is not None:
                                print(f"      段 {i}: Ea = {Ea_kJ_mol:.2f} kJ/mol, 点数 = {seg.get('n_points', 0)}")
                            else:
                                print(f"      段 {i}: Ea = N/A, 点数 = {seg.get('n_points', 0)}")
                        
                        # 保存到状态（可选）
                        # self.state 可以添加一个方法来保存 arrhenius_result
                        print(f"\n   💾 Arrhenius 结果已生成（可后续保存到报告）")
                    
                    else:
                        print(f"   ⚠️ Arrhenius 分析失败: {arrhenius_result.get('error')}")
        
        except Exception as e:
            print(f"   ❌ Arrhenius 分析异常: {str(e)}")
            import traceback
            traceback.print_exc()
        
        print(f"\n" + "="*80)
        
        # 回温
        print(f"\n🔄 设置回温到 18°C...")
        self.temp_driver.set_temperature(18.0, is_cooling=False)
        
        self._is_running = False
    
    # ========================================================
    # 公共接口：暂停/恢复/停止
    # ========================================================
    
    def pause(self) -> None:
        """暂停实验"""
        print(f"\n⏸️ 暂停实验")
        self.state.pause_experiment()
    
    def resume(self) -> None:
        """恢复实验"""
        print(f"\n▶️ 恢复实验")
        self.state.resume_experiment()
    
    def stop(self, reason: str = "User requested") -> None:
        """停止实验"""
        print(f"\n🛑 停止实验: {reason}")
        self._should_stop = True
        self._stop_reason = reason
        self._is_running = False
    
    def get_status(self) -> Dict[str, Any]:
        """获取当前状态"""
        return {
            'is_running': self._is_running,
            'is_paused': self.state.is_paused(),
            'current_temperature': self.state.get_current_temperature(),
            'target_temperature': self.state.get_target_temperature(),
            'measurement_count': self.state.get_measurement_count(),
            'phase_count': len(self.state.get_phase_transitions()),
            'should_stop': self._should_stop,
            'stop_reason': self._stop_reason,
        }
