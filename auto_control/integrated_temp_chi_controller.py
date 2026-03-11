# -*- coding: utf-8 -*-
"""
集成版温控器 - 自动温度控制与CHI测量一体化
整合了temp_controller.py和run_chi.py的功能
"""

import sys
import os
import threading

# ==================== 日志捕获类 ====================
class TeeOutput:
    """
    同时输出到终端和WebSocket的包装器
    拦截所有print输出，同时推送到前端
    
    ✅ 修复：添加所有必要的stdout属性，避免文件操作失败
    """
    def __init__(self, original_stdout, log_callback=None):
        self.original_stdout = original_stdout
        self.log_callback = log_callback
        self.lock = threading.Lock()  # 线程安全
        
        # ✅ 添加必要的属性，委托给原始 stdout
        self.encoding = getattr(original_stdout, 'encoding', 'utf-8')
        self.errors = getattr(original_stdout, 'errors', 'strict')
        self.mode = getattr(original_stdout, 'mode', 'w')
        self.name = getattr(original_stdout, 'name', '<stdout>')
    
    def write(self, message):
        # 1. 输出到原始终端（保持原样）
        with self.lock:
            self.original_stdout.write(message)
            self.original_stdout.flush()
            
            # 2. 推送到WebSocket（如果有回调且消息不为空）
            if self.log_callback and message.strip():
                try:
                    self.log_callback(message.strip())
                except Exception as e:
                    # ✅ 不再静默吞掉异常，打印到原始 stdout
                    self.original_stdout.write(f"[TeeOutput Error] {e}\n")
                    self.original_stdout.flush()
    
    def flush(self):
        self.original_stdout.flush()
    
    def isatty(self):
        return self.original_stdout.isatty()
    
    def fileno(self):
        """返回文件描述符"""
        return self.original_stdout.fileno()
    
    def __getattr__(self, name):
        """
        魔法方法：对于任何未实现的属性，委托给原始 stdout
        这样可以确保所有 stdout 的属性和方法都能正常工作
        """
        return getattr(self.original_stdout, name)

# 设置控制台编码，解决中文输出乱码问题
if sys.platform.startswith('win'):
    # Windows系统
    import locale
    try:
        # 尝试设置控制台编码为UTF-8
        os.system('chcp 65001 > nul')
        sys.stdout.reconfigure(encoding='utf-8')  # type: ignore
        sys.stderr.reconfigure(encoding='utf-8')  # type: ignore
    except (AttributeError, Exception):
        try:
            # 备用方案：设置控制台编码为GBK
            os.system('chcp 936 > nul')
            sys.stdout.reconfigure(encoding='gbk')  # type: ignore
            sys.stderr.reconfigure(encoding='gbk')  # type: ignore
        except (AttributeError, Exception):
            pass
else:
    # Linux/Mac系统
    import locale
    try:
        locale.setlocale(locale.LC_ALL, 'zh_CN.UTF-8')
    except:
        try:
            locale.setlocale(locale.LC_ALL, 'C.UTF-8')
        except:
            pass

import serial
import time
import struct
import binascii
import json
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
import math
from collections import deque
from typing import Optional, Tuple, List, Dict
from datetime import datetime
import subprocess
import logging
import cv2
# ========== 添加这一行：禁用OpenCV警告 ==========
cv2.setLogLevel(0)  # 0=SILENT，禁用所有警告信息
# ==========================================
import pyautogui
from PIL import ImageGrab
import threading
import queue
import re

# 统一 standalone 路径初始化
try:
    from auto_control._path_setup import ensure_close_root
except ImportError:
    from _path_setup import ensure_close_root

CLOSE_ROOT = ensure_close_root()

try:
    from auto_control.modules.temp_control import TemperatureControlMixin
except Exception:
    from modules.temp_control import TemperatureControlMixin

try:
    from auto_control.modules.chi_test import ChiTestMixin
except Exception:
    from modules.chi_test import ChiTestMixin

try:
    from auto_control.modules.data_analysis import (
        try_parse_three_floats as analysis_try_parse_three_floats,
        read_chi_eis_file,
        analyze_one_point,
        analyze_arrays,
    )
except Exception:
    from modules.data_analysis import (
        try_parse_three_floats as analysis_try_parse_three_floats,
        read_chi_eis_file,
        analyze_one_point,
        analyze_arrays,
    )

# 设置matplotlib支持中文
matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
matplotlib.rcParams['axes.unicode_minus'] = False

# ==================== 严格分析模式配置 ====================
ALLOW_SIMULATION = os.environ.get('ALLOW_SIMULATION', '0') == '1'
STRICT_MODE = not ALLOW_SIMULATION  # 严格模式：禁止模拟数据
print(f"[配置] STRICT_MODE={STRICT_MODE}, ALLOW_SIMULATION={ALLOW_SIMULATION}")
# ========================================================

# 导入数据处理模块 - 强制导入，不使用模拟
from specific_conductance.data_processing import filter_data
from specific_conductance.rb_fitting import detect_phase_jump, calculate_rb
from specific_conductance.conductivity import calculate_conductivity, get_fit_params
print("[integrated_temp_chi_controller] ✅ 成功导入数据处理模块")

# CV2图像读取辅助函数
def cv2_imread_unicode(path, flags=cv2.IMREAD_COLOR):
    """支持中文路径的图像读取"""
    try:
        # 尝试使用OpenCV读取
        template = cv2.imread(path, flags)
        if template is None:
            # 尝试使用PIL作为备选方案
            from PIL import Image
            pil_image = Image.open(path)
            template = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
            print(f"[DEBUG] 使用PIL成功读取模板: {path}")
        return template
    except Exception as e:
        print(f"[DEBUG] 读取图像失败: {path}, 错误: {str(e)}")
        return None


class IntegratedTemperatureCHIController(TemperatureControlMixin, ChiTestMixin):
    """集成温控和CHI测量的控制器"""
    
    def __init__(self, port: str, T_start: float, T_end: float, eps: float = 0.5, 
                 coarse_step: float = 10.0, fine_step: float = 3.0,
                 thickness: float = 0.001, area: float = 0.000196,
                 data_dir: str = "experiment_data", 
                 chi_params: Optional[Dict] = None,
                 auto_stop_config: Optional[Dict] = None):
        """
        初始化集成控制器
        :param port: 串口名称
        :param T_start: 起始温度 (°C)
        :param T_end: 目标温度 (°C)
        :param eps: 温度误差容限 (°C)
        :param coarse_step: 粗测步长 (°C)
        :param fine_step: 精细测量步长 (°C)
        :param thickness: 样品厚度 (m)
        :param area: 样品截面积 (m²)
        :param data_dir: 数据存储目录
        :param chi_params: CHI测量参数
        :param auto_stop_config: 自动停止配置（材料性能检测）
        """
        # 温控参数
        self.ser = self._init_serial(port)
        self.T_start = T_start
        self.T_end = T_end
        self.eps = eps
        self.coarse_step = coarse_step
        self.fine_step = fine_step
        self.current_step_size = coarse_step
        self.current_target = T_start
        
        # 样品参数
        self.thickness = thickness
        self.area = area
        
        # 实验数据记录
        self.data_dir = data_dir
        self.eis_data_dir = os.path.join(data_dir, "eis_data")
        os.makedirs(data_dir, exist_ok=True)
        os.makedirs(self.eis_data_dir, exist_ok=True)
        
        # 配置日志系统
        log_file = os.path.join(data_dir, f"experiment_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"日志文件已创建: {log_file}")
        
        # CHI测量参数
        default_chi_params = {
            "material": "LRS-P10+ao3-2",
            "highf": "1000000",
            "lowf": "0.1",
            "initV": "0",
            "your_position": "E:\\chi_data",
            "your_type_text": "Text Files",
            "template_dir": current_dir,  # 使用当前目录作为模板目录
            "confidence": 0.6,
            "text_confidence": 70,
            "delay": 0.5
        }
        
        # 确保CHI数据保存目录存在
        chi_save_dir = default_chi_params.get("your_position", "E:\\chi_data")
        if not os.path.exists(chi_save_dir):
            os.makedirs(chi_save_dir, exist_ok=True)
            self.logger.info(f"✅ 创建CHI数据保存目录: {chi_save_dir}")
        else:
            self.logger.info(f"✅ CHI数据保存目录已存在: {chi_save_dir}")
        self.chi_params = default_chi_params.copy()
        if chi_params:
            self.chi_params.update(chi_params)
            # 如果用户提供了新的保存路径，也要确保其存在
            if "your_position" in chi_params:
                os.makedirs(chi_params["your_position"], exist_ok=True)
                self.logger.info(f"✅ 确保用户指定的CHI数据保存目录存在: {chi_params['your_position']}")
        
        # 状态跟踪
        self.power_on = False
        self.current_temp = None
        self.buffer = bytearray()
        self.frame_queue = deque()
        
        # 相变点检测相关（支持多相变）
        self.phase_transition_range = None  # 当前待处理的相变区间
        self.phase_transition_queue = []    # 待处理的相变队列（支持多相变）
        self.phase_detected = False         # 当前相变是否已处理
        self.phase_count = 0                # 已处理的相变计数
        self.fine_measuring = False
        self.last_measurement_temp = T_start
        self.last_phase_end_temp = None     # 上一个相变精测结束的温度（用于冷却间隔）
        self.phase_cooldown_interval = 5.0  # 相变检测冷却间隔（°C）
        
        # 数据记录
        self.temperature_history = []
        self.measurement_history = []
        self.phase_transition_points = []   # 所有已处理的相变记录
        
        # 拟合参数
        self.fit_params = get_fit_params()
        
        # 实时数据队列
        self.realtime_data_queue = queue.Queue()
        self.is_monitoring = False
        self.monitoring_thread = None
        
        # 控制状态
        self.control_active = False
        self.control_thread = None
        
        # 暂停/恢复功能
        self.paused = False
        self.pause_target_temp = None
        self.saved_original_target = None  # 暂停前保存的原始目标温度
        
        # 串口访问锁
        self.serial_lock = threading.Lock()
        
        # 周期性暂停降温的时间戳
        self.last_periodic_pause_time = time.time()
        
        # WebSocket回调函数（用于前端实时推送）
        self.temperature_update_callback = None
        self.measurement_complete_callback = None
        self.phase_transition_callback = None
        self.status_change_callback = None
        self.log_callback = None  # 日志推送回调
        self.offline_analysis_complete_callback = None  # 离线分析完成回调
        
        # 执行ID（用于前端追踪）
        self.execution_id = None
        
        # 日志捕获相关
        self._original_stdout = None
        self._tee_output = None
        
        # 确保目标温度正确初始化
        self.next_target = T_start
        
        # CHI测量状态
        self.chi_measuring = False
        self.chi_measurement_count = 0
        
        # 测量点列表
        self.measurement_points = []
        self.current_measurement_index = 0
        self.next_target = T_start  # 下一个目标温度

        # ========== 自动停止配置（材料性能检测） ==========
        # 默认配置：当Rb值过高或电导率过低时自动停止测试
        # 阈值基于项目历史数据分析得出：
        # - 正常材料：Rb < 10^5 Ω, σ > 10^-5 S/cm
        # - 边界区域：Rb ~ 10^6 Ω, σ ~ 10^-7 S/cm  
        # - 性能不佳：Rb > 10^7 Ω, σ < 10^-8 S/cm
        default_auto_stop_config = {
            'enabled': True,                    # 是否启用自动停止
            'rb_threshold': 1e7,                # Rb阈值（欧姆），基于历史数据分析，10^7Ω是合理的停止点
            'conductivity_threshold': 1e-8,     # 电导率阈值（S/cm），10^-8是实际有效测量的下限
            'consecutive_failures': 2,          # 连续N次超标后停止（2次可更快响应）
            'check_fit_quality': True,          # 是否检查拟合质量
            'fit_quality_threshold': 0.6,       # 拟合质量阈值（0.6确保数据可靠性）
        }
        self.auto_stop_config = default_auto_stop_config.copy()
        if auto_stop_config:
            self.auto_stop_config.update(auto_stop_config)
        
        # 自动停止状态
        self.should_stop_due_to_poor_performance = False
        self.poor_performance_count = 0  # 连续性能不佳的计数
        self.stop_reason = None  # 停止原因
        self.last_valid_temperature = None  # 最后一个有效测量的温度

        # ========== 两段降温流程参数 ==========
        # 是否启用两段降温（第一段仅粗测，第二段回温后在相变区精细测量）
        # 注意：回温需要制冷器能够加热，否则会长时间等待
        self.two_phase_mode = False  # 默认禁用，避免回温超时
        # 第一段是否将精细测量延后到第二段（默认是）
        self.defer_fine_to_second_pass = True
        # 第二段回温的室温目标（单位°C）
        self.second_pass_warm_temp = 30.0
        # 第二段快速降温的大步长（单位°C）
        self.fast_coarse_step = 20.0
        # 仅在指定相变区间内进行测量（用于第二段快速降温阶段）
        self.only_measure_in_region = False
        # 指定第二段的相变区覆盖（可由外部覆盖设置），格式 (T_high, T_low)
        self.second_phase_region_override = None

    def _ensure_power_on(self) -> bool:
        """确保设备开机"""
        if self.power_on:
            print("设备已开机，跳过开机步骤")
            return True

        print("尝试开机设备...")
        cmd = bytes.fromhex('A5 5A 06 83 50 00 01 00 01')
        
        for attempt in range(3):
            print(f"开机尝试 {attempt + 1}/3...")
            self.ser.write(cmd)
            time.sleep(3)  # 增加等待时间

            if self.ser.in_waiting > 0:
                resp = self.ser.read(8)
                print(f"收到响应: {resp.hex()}")
                if resp == bytes.fromhex('A5 5A 05 82 01 30 00 01'):
                    self.power_on = True
                    print("开机成功")
                    return True
            else:
                print("未收到响应")

        # 如果开机失败，但能读取温度，说明设备可能已经开机了
        print("开机命令失败，但尝试直接读取温度...")
        temp = self.read_temperature()
        if temp is not None:
            print(f"能读取到温度 {temp}°C，设备可能已经开机")
            self.power_on = True
            return True

        print("开机失败且无法读取温度")
        return False


    def _process_buffer(self):
        """
        处理串口缓冲区数据
        
        策略：
        1. 查找帧头 0xA5 0x5A
        2. 解析完整帧后，从buffer中删除
        3. 保留未完成的帧（最多1个字节）
        4. 防止buffer无限增长
        """
        # ✅ 安全保护：如果buffer异常增长，强制清理
        if len(self.buffer) > 5000:
            print(f"⚠️ 内部缓冲区异常增长({len(self.buffer)}字节)，强制清理")
            self.buffer.clear()
            return
        
        while len(self.buffer) >= 2:
            start_pos = -1
            for i in range(len(self.buffer) - 1):
                if self.buffer[i] == 0xA5 and self.buffer[i + 1] == 0x5A:
                    start_pos = i
                    break

            if start_pos == -1:
                # 没找到帧头，保留最后1个字节（可能是0xA5）
                if len(self.buffer) > 1:
                    self.buffer = self.buffer[-1:]
                return

            # 丢弃帧头之前的垃圾数据
            if start_pos > 0:
                self.buffer = self.buffer[start_pos:]

            # 检查是否有完整的帧长度字段
            if len(self.buffer) < 3:
                return

            data_len = self.buffer[2]
            
            # 检查是否有完整的帧
            if len(self.buffer) < 3 + data_len:
                return

            # 提取完整帧
            frame = self.buffer[:3 + data_len]
            # ✅ 关键：删除已处理的帧，防止内存泄漏
            self.buffer = self.buffer[3 + data_len:]
            self.frame_queue.append(frame)

    def _parse_frame(self, frame) -> Optional[float]:
        """解析数据帧获取温度"""
        try:
            if len(frame) < 8:
                return None

            if frame[0] != 0xA5 or frame[1] != 0x5A:
                return None

            param_type = (frame[4] << 8) | frame[5]

            if param_type == 0x0022:
                raw = (frame[6] << 8) | frame[7]
                
                if raw & 0x8000:
                    raw = -((raw ^ 0xFFFF) + 1)
                
                temp = raw * 0.1
                
                # ✅ 扩大温度范围：-120℃ ~ 120℃（支持低温实验）
                if -120 <= temp <= 25:
                    return temp
                else:
                    print(f"⚠️ 温度超出有效范围: {temp:.1f}°C")
                    return None
            else:
                return None
                    
        except Exception as e:
            return None

    # ==================== CHI测量集成功能 ====================
    
    def _try_parse_three_floats(self, line: str):
        """
        尝试从一行文本中解析出3个浮点数
        支持分隔符：逗号、制表符、空白
        """
        return analysis_try_parse_three_floats(line)

    def _read_chi_data_file(self, filepath: str) -> Tuple[Optional[np.ndarray], Optional[np.ndarray], Optional[np.ndarray]]:
        """读取CHI保存的数据文件"""
        try:
            return read_chi_eis_file(filepath, strict_mode=STRICT_MODE)
        except Exception as e:
            print(f"❌ 读取数据文件失败: {e}")
            import traceback
            traceback.print_exc()
            if STRICT_MODE:
                raise
            return None, None, None

    # ==================== 测量和数据处理功能 ====================
    
    def _perform_measurement(self) -> bool:
        """
        执行完整的测量流程 - 集成CHI测量
        
        Returns:
            bool: True=测量成功, False=温度不稳定需要重新降温
        """
        print(">>> 开始执行测量函数 <<<")
        
        # 🔒 防止重复测量：检查是否已经在测量中
        if self.chi_measuring:
            print("⚠️ CHI测量正在进行中，跳过重复调用")
            return False
        
        # 读取最新温度（read_temperature内部已优化为自动取最新值）
        fresh_temp = self.read_temperature()
        if fresh_temp is None:
            print("❌ 无法读取温度，跳过本次测量")
            return False
        
        self.current_temp = fresh_temp
        
        print(f"- 当前温度: {self.current_temp:.1f}°C")
        print(f"- 目标温度: {self.current_target}°C")
        print(f"- 处于{'精细' if self.fine_measuring else '粗测'}测量模式")
        
        # ✅ 新增：确保测量前40秒内温度都在目标±EPS范围内
        print(f"\n🔍 测量前温度稳定性验证（40秒）...")
        print(f"   要求：40秒内所有温度读数都必须在 {self.current_target - self.eps:.1f}°C ~ {self.current_target + self.eps:.1f}°C 范围内")
        
        stability_duration = 40  # 稳定性检查时长（秒）
        check_interval = 5  # 每5秒检查一次
        checks_needed = stability_duration // check_interval  # 需要检查8次
        max_retry = 3  # 最多重试3次
        
        for retry in range(max_retry):
            stable_checks = 0
            all_stable = True
            
            for check_num in range(checks_needed):
                # 读取温度
                temp = self.read_temperature()
                if temp is None:
                    print(f"   ⚠️ 第{check_num + 1}次检查：无法读取温度")
                    all_stable = False
                    break
                
                # 计算温度差（带符号）
                temp_diff_signed = temp - self.current_target
                temp_diff = abs(temp_diff_signed)
                
                # 检查是否在范围内
                if temp_diff <= self.eps:
                    stable_checks += 1
                    elapsed = (check_num + 1) * check_interval
                    print(f"   ✅ 第{check_num + 1}/{checks_needed}次检查通过: {temp:.1f}°C "
                          f"(差值 {temp_diff_signed:+.2f}°C, 已验证 {elapsed}秒)")
                else:
                    # 温度不稳定（无论过高还是过低）
                    print(f"   ❌ 第{check_num + 1}次检查失败: {temp:.1f}°C 超出范围 "
                          f"(差值 {temp_diff_signed:+.2f}°C > ±{self.eps}°C)")
                    all_stable = False
                    break
                
                # 等待下一次检查
                if check_num < checks_needed - 1:
                    time.sleep(check_interval)
            
            # 检查是否全部通过
            if all_stable and stable_checks == checks_needed:
                print(f"✅ 温度稳定性验证通过！40秒内所有读数都在±{self.eps}°C范围内\n")
                break
            else:
                if retry < max_retry - 1:
                    print(f"   🔄 温度不稳定，等待10秒后重新开始验证（第{retry + 1}/{max_retry}次尝试）...")
                    time.sleep(10)
                else:
                    print(f"❌ 经过{max_retry}次尝试，温度仍未完全稳定（通过 {stable_checks}/{checks_needed} 次检查）")
                    print(f"   🔄 温度不满足测量条件，返回主流程重新降温\n")
                    return False  # ← 返回False，让主流程重新调用 execute_precise_cooling

        # 若仅在指定区间内测量且当前温度不在区间内，则跳过测量
        print(f"DEBUG: only_measure_in_region = {self.only_measure_in_region}")
        if self.only_measure_in_region:
            region = None
            if self.second_phase_region_override:
                region = self.second_phase_region_override
                print(f"DEBUG: 使用second_phase_region_override: {region}")
            elif self.phase_transition_range:
                region = self.phase_transition_range
                print(f"DEBUG: 使用phase_transition_range: {region}")
            if region and len(region) == 2:
                T_high, T_low = region
                if T_high is not None and T_low is not None and self.current_temp is not None:
                    print(f"DEBUG: 检查温度范围: {T_low - self.eps} <= {self.current_temp} <= {T_high + self.eps}")
                    if not (T_low - self.eps <= self.current_temp <= T_high + self.eps):
                        print(f"⏭️ 跳过测量（仅在相变区{region}内测量，当前{self.current_temp:.1f}°C不在范围）")
                        return True  # 跳过测量也算成功（不需要重试）
            else:
                print(f"DEBUG: 没有设置测量区间，但only_measure_in_region=True")
        else:
            print(f"DEBUG: only_measure_in_region=False，正常进行测量")
        
        # 暂停降温
        print("\n⏸️ 暂停降温，准备进行CHI测量...")
        print("DEBUG: 设置chi_measuring = True")
        self.chi_measuring = True
        print("DEBUG: chi_measuring设置完成")
        
        # 直接开始测量，不额外设置温度
        print("DEBUG: 直接开始测量，保持当前温度设置")
        
        # 执行CHI测量
        print("DEBUG: 准备执行CHI测量")
        try:
            print("DEBUG: 增加测量计数")
            self.chi_measurement_count += 1
            print(f"DEBUG: 测量计数增加到 {self.chi_measurement_count}")
            
            print(f"\n🔬 第 {self.chi_measurement_count} 次CHI测量")
            print("DEBUG: 调用模块化的CHI测量流程（来自ChiTestMixin）")
            
            # 直接调用模块化后的CHI测量方法（来自ChiTestMixin）
            results, frequencies, z_real, z_imag = self.run_chi_measurement()
            
            # 构建原始数据文件路径 - 使用与chi_test.py第231行一致的文件名格式
            raw_data_path = None
            if isinstance(results, dict) and results.get("save_file", (False, ""))[0]:
                # 使用目标温度构建文件名（格式必须与chi_test.py中CHI保存时一致）
                target_temp_for_filename = self.current_target if hasattr(self, 'current_target') else self.current_temp
                temp_str = f"{int(target_temp_for_filename)}" if target_temp_for_filename == int(target_temp_for_filename) else f"{target_temp_for_filename:.1f}"
                # 格式: 材料_T温度_f低频_高频_V电位 （与chi_test.py第231行一致）
                filename = f"{self.chi_params.get('material', 'Sample')}_T{temp_str}_f{self.chi_params.get('lowf')}_{self.chi_params.get('highf')}_V{self.chi_params.get('initV')}.txt"
                raw_data_path = os.path.join(self.chi_params.get('your_position', 'E:\\chi_data'), filename)
                print(f"✅ CHI数据文件路径: {raw_data_path}")
            else:
                print("⚠️ CHI测量未成功保存文件")
            
            print("DEBUG: 模块化CHI测量流程完成")
            
            # 显示测量结果
            print("\n==== CHI测量结果 ====")
            if isinstance(results, dict):
                for step, (success, msg) in results.items():
                    if step != "error":  # 跳过错误信息的重复显示
                        status = "✅ 成功" if success else "❌ 失败"
                        print(f"{step.ljust(15)}: {status} - {msg}")
            else:
                print(f"[WARNING] results类型异常: {type(results)}")
            
            # 处理EIS数据（传递raw_data_path）
            result = self.process_eis_data(frequencies, z_real, z_imag, raw_data_path=raw_data_path or "")
            
            # 保存测量数据
            self.save_measurement_data(result)
            
            # ========== 自动停止检测（材料性能检测） ==========
            if self.auto_stop_config.get('enabled', True):
                should_stop, reason = self._check_material_performance(result)
                if should_stop:
                    self.should_stop_due_to_poor_performance = True
                    self.stop_reason = reason
                    print(f"\n{'='*60}")
                    print(f"⚠️  材料性能检测触发自动停止")
                    print(f"{'='*60}")
                    print(f"📍 停止温度: {self.current_temp:.1f}°C")
                    print(f"🔍 停止原因: {reason}")
                    print(f"📊 最后测量Rb: {result.get('rb', 'N/A')} Ω")
                    print(f"⚡ 最后测量电导率: {result.get('conductivity', 'N/A')} S/cm")
                    print(f"{'='*60}")
                    print(f"💡 系统将停止降温测试，自动进入后续分析流程...")
                    print(f"{'='*60}\n")
            
            # 调用测量完成回调（用于WebSocket实时推送）
            if hasattr(self, 'measurement_complete_callback') and callable(self.measurement_complete_callback):
                try:
                    measurement_data = {
                        'temperature_C': result.get('temperature'),
                        'temperature_K': result.get('temperature', 0) + 273.15 if result.get('temperature') is not None else None,
                        'rb_ohm': result.get('rb'),
                        'conductivity_S_per_cm': result.get('conductivity'),
                        'fit_method': result.get('fit_method'),
                        'phase_jump_detected': result.get('phase_jump_detected', False),
                        'timestamp': time.time(),
                        'auto_stop_triggered': self.should_stop_due_to_poor_performance,
                        'stop_reason': self.stop_reason
                    }
                    self.measurement_complete_callback(measurement_data)
                except Exception as e:
                    print(f"[回调错误] 测量完成回调失败: {e}")
            
            # 更新上次测量温度
            self.last_measurement_temp = self.current_temp
            
        except Exception as e:
            print(f"❌ CHI测量失败: {str(e)}")
            print(f"⚠️ 温度稳定但CHI测量出错，跳过此测量点，继续下一个")
            return True  # ← 修复：CHI测量失败不是温度问题，返回True跳过此点
        finally:
            # 恢复降温
            print("\n▶️ CHI测量完成，恢复降温控制")
            self.chi_measuring = False
            # 不额外设置温度，让系统继续原有的降温流程
        
        return True  # 测量成功

    def _check_material_performance(self, result: Dict) -> tuple:
        """
        检测材料性能是否已经不可用
        
        Args:
            result: 测量结果字典，包含rb、conductivity、fit_quality等
            
        Returns:
            (should_stop: bool, reason: str): 是否应该停止及原因
        """
        rb = result.get('rb')
        conductivity = result.get('conductivity')
        fit_quality = result.get('fit_quality') or result.get('r_squared')
        
        rb_threshold = self.auto_stop_config.get('rb_threshold', 1e8)
        cond_threshold = self.auto_stop_config.get('conductivity_threshold', 1e-9)
        fit_threshold = self.auto_stop_config.get('fit_quality_threshold', 0.5)
        consecutive_required = self.auto_stop_config.get('consecutive_failures', 3)
        check_fit = self.auto_stop_config.get('check_fit_quality', True)
        
        reasons = []
        is_poor = False
        
        # 检测Rb值是否过高
        if rb is not None and rb > rb_threshold:
            is_poor = True
            reasons.append(f"Rb值过高 ({rb:.2e} Ω > {rb_threshold:.0e} Ω)")
        
        # 检测电导率是否过低
        if conductivity is not None and conductivity < cond_threshold:
            is_poor = True
            reasons.append(f"电导率过低 ({conductivity:.2e} S/cm < {cond_threshold:.0e} S/cm)")
        
        # 检测拟合质量是否太差
        if check_fit and fit_quality is not None and fit_quality < fit_threshold:
            is_poor = True
            reasons.append(f"拟合质量过低 (R²={fit_quality:.4f} < {fit_threshold})")
        
        if is_poor:
            self.poor_performance_count += 1
            print(f"⚠️ 检测到材料性能不佳 ({self.poor_performance_count}/{consecutive_required})")
            
            if self.poor_performance_count >= consecutive_required:
                # 记录最后有效温度（前一个测量点）
                if self.measurement_history and len(self.measurement_history) > 1:
                    self.last_valid_temperature = self.measurement_history[-2].get('temperature_C')
                
                combined_reason = "; ".join(reasons)
                return True, f"连续{consecutive_required}次性能不佳: {combined_reason}"
        else:
            # 重置连续计数
            self.poor_performance_count = 0
            self.last_valid_temperature = self.current_temp
        
        return False, None

    def process_eis_data(self, frequencies: np.ndarray, z_real: np.ndarray, z_imag: np.ndarray, raw_data_path: Optional[str] = None) -> Dict:
        """处理EIS数据，检测相变点（增强版：完整拟合信息 + 失败追溯）"""
        print("开始处理EIS数据...")
        
        try:
            circle_dir = os.path.join(self.data_dir, 'circle_fits')
            analysis = None
            current_temp = self.current_temp if self.current_temp is not None else 298.15

            if raw_data_path and os.path.exists(raw_data_path):
                analysis = analyze_one_point(
                    raw_data_path,
                    current_temp,
                    self.thickness * 100,
                    self.area * 1e4,
                    STRICT_MODE,
                )
            else:
                analysis = analyze_arrays(
                    frequencies,
                    z_real,
                    z_imag,
                    current_temp,
                    self.thickness * 100,
                    self.area * 1e4,
                    STRICT_MODE,
                    circle_dir=circle_dir,
                    filepath=raw_data_path,
                )

            details = analysis.get('details', {}) if analysis else {}
            rb_value = analysis.get('rb_ohm') if analysis else None
            conductivity = analysis.get('sigma_s_per_cm') if analysis else None
            fit_method = details.get('fit_method', '未知')
            fit_params = details.get('fit_params')
            phase_jump_detected = details.get('phase_jump_detected', False)

            # ===== 多相变检测逻辑（优化版） =====
            # 检查是否可以检测新相变（冷却间隔检查）
            can_detect = self.can_detect_new_phase()
            new_phase_detected = False
            detection_method = None
            
            if can_detect and self.last_measurement_temp is not None:
                # 方法1：相位突变检测
                if phase_jump_detected:
                    new_phase_detected = True
                    detection_method = 'phase_jump'
                
                # 方法2：圆弧拟合检测
                elif fit_method == 'circle':
                    new_phase_detected = True
                    detection_method = 'circle_fit'
                
                # 方法3：电导率变化率检测（补充机制）
                elif conductivity is not None:
                    if self._detect_conductivity_change(conductivity):
                        new_phase_detected = True
                        detection_method = 'conductivity_change'
            
            # 处理新检测到的相变
            if new_phase_detected:
                new_phase_range = (self.last_measurement_temp, self.current_temp)
                
                # 如果当前没有待处理的相变，直接设置
                if self.phase_transition_range is None:
                    self.phase_transition_range = new_phase_range
                    self.phase_detected = False
                    print(f"[相变检测] 检测到相变区间: {new_phase_range}，方法: {detection_method}")
                else:
                    # 如果当前有待处理的相变，加入队列
                    self.phase_transition_queue.append(new_phase_range)
                    print(f"[相变检测] 检测到新相变区间: {new_phase_range}，已加入队列")
                    print(f"[相变检测] 当前队列长度: {len(self.phase_transition_queue)}")
                
                # 调用相变检测回调（用于WebSocket实时推送）
                if hasattr(self, 'phase_transition_callback') and callable(self.phase_transition_callback):
                    try:
                        transition_data = {
                            'T_high': self.last_measurement_temp,
                            'T_low': self.current_temp,
                            'detection_method': detection_method,
                            'phase_index': self.phase_count + len(self.phase_transition_queue),
                            'timestamp': time.time()
                        }
                        self.phase_transition_callback(transition_data)
                    except Exception as e:
                        print(f"[回调错误] 相变检测回调失败: {e}")

            freq_filtered = details.get('freq_filtered')
            zreal_filtered = details.get('zreal_filtered')
            zimag_filtered = details.get('zimag_filtered')

            freq_out = analysis.get('freq_hz') if analysis else frequencies
            zreal_out = analysis.get('z_real_ohm') if analysis else z_real
            zimag_out = analysis.get('z_imag_ohm') if analysis else z_imag

            # ===== 计算相变检测分数 =====
            phase_detection_scores = self._calculate_phase_detection_scores(
                z_real=zreal_out if zreal_out is not None else z_real,
                z_imag=zimag_out if zimag_out is not None else z_imag,
                fit_method=fit_method,
                phase_jump_detected=phase_jump_detected,
                conductivity=conductivity
            )

            result = {
                'temperature': self.current_temp,
                'rb': rb_value,
                'conductivity': conductivity,
                'fit_method': fit_method,
                'fit_params': fit_params,
                'phase_jump_detected': phase_jump_detected,
                'phase_transition_range': self.phase_transition_range,
                'raw_data_path': analysis.get('filepath', raw_data_path) if analysis else raw_data_path,
                'phase_detection': phase_detection_scores,  # 新增：相变检测分数
                'eis_data': {
                    'frequencies': freq_out,
                    'z_real': zreal_out,
                    'z_imag': zimag_out,
                    'filtered': {
                        'frequencies': freq_filtered if freq_filtered is not None else (freq_out if freq_out is not None else np.array([])),
                        'z_real': zreal_filtered if zreal_filtered is not None else (zreal_out if zreal_out is not None else np.array([])),
                        'z_imag': zimag_filtered if zimag_filtered is not None else (zimag_out if zimag_out is not None else np.array([]))
                    }
                }
            }

            if rb_value is not None:
                print(f"✅ 温度 {self.current_temp}°C: Rb = {rb_value:.2f} Ω, 电导率 = {conductivity:.4e} S/cm, 方法 = {fit_method}")
            else:
                print(f"❌ 温度 {self.current_temp}°C: 拟合失败 (method={fit_method})")

            return result
            
        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            print(f"❌ 数据处理失败: {str(e)}")
            print(f"详细错误:\n{error_detail}")
            
            return {
                'temperature': self.current_temp,
                'rb': None,
                'conductivity': None,
                'fit_method': '处理失败',
                'fit_params': None,
                'phase_jump_detected': False,
                'phase_transition_range': None,
                'error': str(e),
                'error_detail': error_detail,
                'raw_data_path': raw_data_path,
                'phase_detection': {  # 新增：错误情况下的默认值
                    'phase_jump_score': 0.0,
                    'linear_to_circle_score': 0.0,
                    'is_phase_transition': False
                },
                'eis_data': {
                    'frequencies': frequencies if frequencies is not None else np.array([]),
                    'z_real': z_real if z_real is not None else np.array([]),
                    'z_imag': z_imag if z_imag is not None else np.array([]),
                    'filtered': {
                        'frequencies': np.array([]),
                        'z_real': np.array([]),
                        'z_imag': np.array([])
                    }
                }
            }

    # ==================== 相变检测辅助功能 ====================
    
    def _calculate_phase_detection_scores(
        self,
        z_real,
        z_imag,
        fit_method: str,
        phase_jump_detected: bool,
        conductivity: Optional[float] = None,
        phase_threshold: float = 30.0
    ) -> Dict:
        """
        计算相变检测的量化分数（用于前端可视化）
        
        Args:
            z_real: 阻抗实部数组
            z_imag: 阻抗虚部数组
            fit_method: 拟合方法（'linear', 'circle', 'X轴交点' 等）
            phase_jump_detected: 是否检测到相位突变（布尔值）
            conductivity: 当前电导率
            phase_threshold: 相位突变阈值（度）
        
        Returns:
            dict: {
                'phase_jump_score': float (0~1),      # 相位跳变分数
                'linear_to_circle_score': float (0~1), # 线性→圆弧转换分数
                'is_phase_transition': bool           # 综合判断是否相变
            }
        """
        try:
            phase_jump_score = 0.0
            linear_to_circle_score = 0.0
            
            # ===== 1. 计算相位跳变分数 =====
            if z_real is not None and z_imag is not None:
                z_real_arr = np.array(z_real) if not isinstance(z_real, np.ndarray) else z_real
                z_imag_arr = np.array(z_imag) if not isinstance(z_imag, np.ndarray) else z_imag
                
                if len(z_real_arr) > 1 and len(z_imag_arr) > 1:
                    # 计算相位角（度）
                    Z = z_real_arr + 1j * z_imag_arr
                    phase = np.angle(Z, deg=True)
                    
                    # 计算相邻点相位差
                    dphase = np.abs(np.diff(phase))
                    max_dphase = np.max(dphase) if len(dphase) > 0 else 0
                    
                    # 映射到 0~1 分数（30度为阈值，60度为满分）
                    if max_dphase >= phase_threshold * 2:
                        phase_jump_score = 1.0
                    elif max_dphase >= phase_threshold:
                        # 线性映射: [threshold, 2*threshold] -> [0.5, 1.0]
                        phase_jump_score = 0.5 + 0.5 * (max_dphase - phase_threshold) / phase_threshold
                    elif max_dphase >= phase_threshold * 0.5:
                        # 线性映射: [0.5*threshold, threshold] -> [0.2, 0.5]
                        phase_jump_score = 0.2 + 0.3 * (max_dphase - phase_threshold * 0.5) / (phase_threshold * 0.5)
                    else:
                        # 小于0.5倍阈值，分数较低
                        phase_jump_score = 0.2 * max_dphase / (phase_threshold * 0.5) if phase_threshold > 0 else 0
            
            # 如果布尔检测器已触发，确保分数至少为0.6
            if phase_jump_detected and phase_jump_score < 0.6:
                phase_jump_score = 0.6
            
            # ===== 2. 计算线性→圆弧转换分数 =====
            fit_method_lower = (fit_method or '').lower()
            
            # 圆弧拟合方法的判断
            circle_methods = ['circle', 'cole-cole', '圆弧', 'semicircle', 'irls']
            linear_methods = ['linear', '线性', 'x轴交点', 'intercept', '渐进']
            
            if any(m in fit_method_lower for m in circle_methods):
                # 圆弧拟合，高分数
                linear_to_circle_score = 0.8
            elif any(m in fit_method_lower for m in linear_methods):
                # 线性拟合，低分数
                linear_to_circle_score = 0.1
            else:
                # 未知方法，中等分数
                linear_to_circle_score = 0.3
            
            # 如果电导率变化异常，增加分数
            if conductivity is not None and hasattr(self, 'measurement_history') and len(self.measurement_history) >= 2:
                last_cond = self.measurement_history[-1].get('conductivity_S_per_cm')
                if last_cond and last_cond > 0 and conductivity > 0:
                    # 计算电导率对数变化
                    log_change = abs(np.log10(conductivity) - np.log10(last_cond))
                    # 正常变化约0.05，相变区域约0.1以上
                    if log_change > 0.1:
                        linear_to_circle_score = min(linear_to_circle_score + 0.2, 1.0)
            
            # ===== 3. 综合判断 =====
            is_phase_transition = phase_jump_score > 0.5 or linear_to_circle_score > 0.5
            
            return {
                'phase_jump_score': round(min(max(phase_jump_score, 0), 1), 3),
                'linear_to_circle_score': round(min(max(linear_to_circle_score, 0), 1), 3),
                'is_phase_transition': is_phase_transition
            }
            
        except Exception as e:
            print(f"[相变检测分数] 计算失败: {e}")
            return {
                'phase_jump_score': 0.0,
                'linear_to_circle_score': 0.0,
                'is_phase_transition': False
            }
    
    def _detect_conductivity_change(self, current_conductivity, min_threshold=0.25, sigma_multiplier=5.0):
        """
        方案A（保守版）：基于电导率对数变化率检测相变
        
        设计原则（基于实际数据分析）：
        1. 正常Arrhenius温度依赖：log₁₀变化率约0.01-0.05/°C
        2. 相变区域（圆弧拟合开始）：log₁₀变化率约0.07/°C
        3. 为避免误触发，阈值设为0.25/°C（约每°C变化1.8倍）
        4. 只作为【补充】检测手段，主要依赖相位突变和圆弧拟合
        
        优化点：
        - 基线点数从10减少到4（适应30个测量点的实验）
        - 最小阈值从0.15提高到0.25（更保守）
        - σ倍数从3提高到5（更保守）
        - 增加连续异常检测（需要连续2个点都异常才触发）
        
        Args:
            current_conductivity: 当前电导率 (S/cm)
            min_threshold: 最小阈值（默认0.25/°C），10^0.25≈1.78倍/°C
            sigma_multiplier: σ倍数（默认5.0，即5σ原则，更保守）
        
        Returns:
            bool: 是否检测到相变
        """
        import numpy as np
        
        if current_conductivity is None or current_conductivity <= 0:
            return False
        
        # 至少需要3个测量点才能判断（当前+前2个）
        if len(self.measurement_history) < 3:
            return False
        
        # 获取最近2个有效测量的电导率和温度
        recent_data = []
        for meas in reversed(self.measurement_history[:-1]):
            cond = meas.get('conductivity_S_per_cm') or meas.get('conductivity')
            temp = meas.get('temperature_C') or meas.get('temperature')
            if cond and cond > 0 and temp is not None:
                recent_data.append({'cond': cond, 'temp': temp})
            if len(recent_data) >= 2:
                break
        
        if len(recent_data) < 1:
            return False
        
        prev_cond = recent_data[0]['cond']
        prev_temp = recent_data[0]['temp']
        
        # 计算温度差
        dT = abs(self.current_temp - prev_temp)
        if dT < 0.5:  # 温度差太小，无法判断
            return False
        
        # 计算当前电导率对数变化率
        try:
            current_change_rate = abs(np.log10(current_conductivity / prev_cond)) / dT
        except (ValueError, ZeroDivisionError):
            return False
        
        # ===== 动态阈值计算：基于最近4个点的5σ原则 =====
        # 收集历史变化率（只取最近4个点，适应小样本实验）
        historical_rates = []
        for i in range(len(self.measurement_history) - 1, 1, -1):
            meas_curr = self.measurement_history[i]
            meas_prev = self.measurement_history[i - 1]
            
            cond_curr = meas_curr.get('conductivity_S_per_cm') or meas_curr.get('conductivity')
            cond_prev = meas_prev.get('conductivity_S_per_cm') or meas_prev.get('conductivity')
            temp_curr = meas_curr.get('temperature_C') or meas_curr.get('temperature')
            temp_prev = meas_prev.get('temperature_C') or meas_prev.get('temperature')
            
            if (cond_curr and cond_prev and cond_curr > 0 and cond_prev > 0 and
                temp_curr is not None and temp_prev is not None):
                dt = abs(temp_curr - temp_prev)
                if dt >= 0.5:
                    try:
                        rate = abs(np.log10(cond_curr / cond_prev)) / dt
                        historical_rates.append(rate)
                    except (ValueError, ZeroDivisionError):
                        pass
            
            # 最多取最近4个点（适应30个测量点的小样本实验）
            if len(historical_rates) >= 4:
                break
        
        # 计算动态阈值
        if len(historical_rates) >= 2:
            baseline_mean = np.mean(historical_rates)
            baseline_std = np.std(historical_rates)
            # 使用5σ原则，更保守
            dynamic_threshold = baseline_mean + sigma_multiplier * baseline_std
            # 确保不低于最小阈值
            threshold = max(float(dynamic_threshold), min_threshold)
            threshold_type = f"dynamic_{sigma_multiplier}sigma"
        else:
            # 数据不足，使用固定阈值
            threshold = min_threshold
            threshold_type = "fixed_min"
            baseline_mean = 0
            baseline_std = 0
        
        # 判断是否超过阈值
        if current_change_rate > threshold:
            # 额外检查：如果有第二个历史数据点，检查前一个变化率是否也异常
            # 这样可以避免单点噪声导致的误触发
            if len(recent_data) >= 2:
                prev_prev_cond = recent_data[1]['cond']
                prev_prev_temp = recent_data[1]['temp']
                dT_prev = abs(prev_temp - prev_prev_temp)
                if dT_prev >= 0.5:
                    try:
                        prev_change_rate = abs(np.log10(prev_cond / prev_prev_cond)) / dT_prev
                        # 如果前一个变化率正常（<阈值的60%），则认为当前可能是噪声
                        if prev_change_rate < threshold * 0.6:
                            print(f"[电导率分析] 变化率异常但前一点正常，可能是噪声，不触发")
                            print(f"   当前变化率: {current_change_rate:.4f}/C > 阈值{threshold:.4f}")
                            print(f"   前一变化率: {prev_change_rate:.4f}/C < 阈值60%({threshold*0.6:.4f})")
                            return False
                    except (ValueError, ZeroDivisionError):
                        pass
            
            print(f"[电导率分析-相变检测] 检测到异常变化!")
            print(f"   当前变化率: {current_change_rate:.4f}/C > 阈值{threshold:.4f}")
            print(f"   阈值类型: {threshold_type}")
            print(f"   基线统计: 均值={baseline_mean:.4f}, std={baseline_std:.4f}")
            print(f"   当前电导率: {current_conductivity:.4e} S/cm @ {self.current_temp}C")
            print(f"   前一电导率: {prev_cond:.4e} S/cm @ {prev_temp}C")
            return True
        
        return False

    # ==================== 温度控制功能 ====================

    def check_phase_transition(self) -> bool:
        """
        检查是否有待处理的相变点（支持多相变）
        
        新逻辑：
        1. 检查当前是否有待处理的相变 (phase_transition_range)
        2. 不再使用 phase_detected 作为永久锁定
        3. 每个相变处理完成后，重置状态，允许检测下一个相变
        """
        # 如果当前有待处理的相变且未处理完成
        if self.phase_transition_range is not None and not self.phase_detected:
            return True
        
        # 如果队列中还有待处理的相变
        if self.phase_transition_queue:
            # 取出下一个相变
            self.phase_transition_range = self.phase_transition_queue.pop(0)
            self.phase_detected = False
            print(f"[多相变] 从队列取出下一个相变: {self.phase_transition_range}")
            return True
        
        return False
    
    def can_detect_new_phase(self) -> bool:
        """
        检查当前是否可以检测新的相变（冷却间隔检查）
        
        避免在刚刚完成精细测量的区域内再次检测到相变
        """
        if self.last_phase_end_temp is None:
            return True
        
        if self.current_temp is None:
            return True
        
        # 检查距离上一个相变结束点是否足够远
        distance = abs(self.current_temp - self.last_phase_end_temp)
        if distance >= self.phase_cooldown_interval:
            return True
        
        return False
    
    def calculate_fine_measurement_params(self):
        """
        根据粗测步长和相变区间，计算精细测量参数（按用户优化方案）
        
        优化策略（用户方案B）：
        - 精细测量上限：T_high + 2°C（向上扩展2°C）
        - 精细测量下限：T_low - coarse_step - 2°C（向下扩展一个粗测步长+2°C）
        - 精细步长固定为1°C（设备精度限制）
        - 跳过已经测量过的温度点，避免文件覆盖
        - 精细测量完成后，继续下一个粗测点
        
        示例：检测到-3°C出现相变，步长3°C
            相变区间: [0°C, -3°C]（T_high=0, T_low=-3）
            精细测量上限: 0 + 2 = 2°C
            精细测量下限: -3 - 3 - 2 = -8°C
            精细测量点: 2,1,0,-1,-2,-3,-4,-5,-6,-7,-8（跳过已测的0和-3）
            精细测量后下一个粗测点: -9°C, -12°C, ...
        
        返回:
            dict: {
                'fine_step': float,        # 精细步长（固定1°C）
                'T_upper': float,          # 精细测量上限
                'T_lower': float,          # 精细测量下限
                'measured_temps': set,     # 已测量的温度点（需跳过）
                'next_coarse_temp': float, # 精细测量后的下一个粗测点
                'should_execute': bool     # 是否应该执行
            }
            None: 不需要精细测量
        """
        if not self.phase_transition_range:
            return None
        
        T_high, T_low = self.phase_transition_range
        
        # 判断是否需要精细测量
        if self.coarse_step <= 1.0:
            print(f"[精细测量] 粗测步长({self.coarse_step}C)已足够精细(<=1C)，跳过精细测量")
            return None
        
        # 精细步长固定为1°C（设备精度限制0.5-1°C）
        fine_step = 1.0
        
        # ===== 按用户方案计算精细测量范围 =====
        # 上限 = T_high + 2°C（向上扩展2°C）
        T_upper = T_high + 2.0
        
        # 下限 = T_low - coarse_step - 2°C（向下扩展一个粗测步长+2°C）
        T_lower = T_low - self.coarse_step - 2.0
        
        # 确保不超出实验范围
        T_upper = min(T_upper, self.T_start)  # 不超过起始温度
        T_lower = max(T_lower, self.T_end)    # 不低于终止温度
        
        # 四舍五入到整数（用户示例中都是整数温度）
        T_upper = round(T_upper)
        T_lower = round(T_lower)
        
        # ===== 收集已测量的温度点（需要跳过） =====
        measured_temps = set()
        for meas in self.measurement_history:
            temp = meas.get('temperature_C') or meas.get('temperature')
            if temp is not None:
                # 四舍五入到整数，便于比较
                measured_temps.add(round(temp))
        
        # ===== 计算精细测量后的下一个粗测点 =====
        # 找到比 T_lower 小的第一个属于原粗测序列的点
        # 原粗测序列：T_start, T_start-step, T_start-2*step, ...
        # 例如：T_start=30, step=3 → 30, 27, 24, ..., 0, -3, -6, -9, -12, ...
        # T_lower=-8 → 下一个粗测点是 -9（属于原序列）
        
        # 计算方法：找到第一个 <= T_lower 且属于粗测序列的点
        # 粗测点公式：T_start - n * coarse_step (n=0,1,2,...)
        # 找到满足 T_start - n * coarse_step <= T_lower 的最小 n
        import math
        n = math.ceil((self.T_start - T_lower) / self.coarse_step)
        next_coarse_temp = self.T_start - n * self.coarse_step
        
        # 如果 next_coarse_temp 刚好等于 T_lower，则取下一个
        if abs(next_coarse_temp - T_lower) < 0.5:
            next_coarse_temp = next_coarse_temp - self.coarse_step
        
        next_coarse_temp = round(next_coarse_temp)
        
        # ===== 打印详细信息 =====
        print(f"\n[精细测量参数计算]")
        print(f"   相变区间: [{T_high}C, {T_low}C]")
        print(f"   粗测步长: {self.coarse_step}C")
        print(f"   精细步长: {fine_step}C（设备精度限制）")
        print(f"   精细测量上限: T_high({T_high}) + 2 = {T_upper}C")
        print(f"   精细测量下限: T_low({T_low}) - step({self.coarse_step}) - 2 = {T_lower}C")
        print(f"   已测量温度点: {sorted(measured_temps, reverse=True)}")
        print(f"   精细测量后下一个粗测点: {next_coarse_temp}C")
        
        # 计算预期测量点数
        expected_points = []
        temp = T_upper
        while temp >= T_lower:
            if round(temp) not in measured_temps:
                expected_points.append(round(temp))
            temp -= fine_step
        print(f"   预期精细测量点（排除已测）: {expected_points}")
        print(f"   预期测量次数: {len(expected_points)}")
        
        return {
            'fine_step': fine_step,
            'T_upper': T_upper,
            'T_lower': T_lower,
            'measured_temps': measured_temps,
            'next_coarse_temp': next_coarse_temp,
            'should_execute': True
        }

    def handle_phase_transition(self) -> bool:
        """
        处理相变点精细测量流程（用户优化版）
        
        优化策略：
        1. 精细测量范围扩大：T_high+2 到 T_low-step-2
        2. 跳过所有已测量的温度点
        3. 精细测量完成后，继续正确的粗测序列
        """
        if not self.phase_transition_range:
            return False
        
        # ===== 步骤1：计算精细测量参数 =====
        params = self.calculate_fine_measurement_params()
        
        if params is None:
            # 不需要精细测量，但仍需记录相变
            T_high, T_low = self.phase_transition_range
            print(f"[精细测量] 跳过精细测量（粗测步长已足够精细），继续主流程")
            
            # 记录相变（即使跳过精细测量）
            phase_record = {
                'range': (T_high, T_low),
                'fine_range': None,  # 未执行精细测量
                'detection_temp': T_low,
                'phase_index': self.phase_count + 1,
                'skipped': True,
                'timestamp': time.time()
            }
            self.phase_transition_points.append(phase_record)
            self.phase_count += 1
            self.last_phase_end_temp = T_low
            
            # 重置状态（允许继续检测新相变）
            self.phase_transition_range = None
            self.phase_detected = False
            return False
        
        T_high, T_low = self.phase_transition_range
        fine_step = params['fine_step']
        T_upper = params['T_upper']
        T_lower = params['T_lower']
        measured_temps = params.get('measured_temps', set())
        next_coarse_temp = params.get('next_coarse_temp', T_lower - self.coarse_step)
        
        print(f"\n========== 启动相变点精细测量（用户优化版） ==========")
        print(f"   相变区间: [{T_high}C, {T_low}C]")
        print(f"   精细测量区间: [{T_upper}C, {T_lower}C]")
        print(f"   精细步长: {fine_step}C (原粗测步长: {self.coarse_step}C)")
        print(f"   已测量点（将跳过）: {sorted(measured_temps, reverse=True)}")
        print(f"   精细测量后下一个粗测点: {next_coarse_temp}C")

        # ===== 步骤2：检查两段模式 =====
        if self.two_phase_mode and self.defer_fine_to_second_pass:
            # 记录相变但不执行精细测量
            phase_record = {
                'range': (T_high, T_low),
                'fine_range': (T_upper, T_lower),  # 计划的精细测量范围
                'detection_temp': T_low,
                'phase_index': self.phase_count + 1,
                'deferred': True,  # 标记为延迟执行
                'timestamp': time.time()
            }
            self.phase_transition_points.append(phase_record)
            self.phase_count += 1
            
            print(f"[两段模式] 第一段检测到相变#{self.phase_count}，精细测量推迟到第二段执行")
            # 不永久锁定，允许继续检测其他相变
            self.phase_transition_range = None
            self.phase_detected = False
            self.last_phase_end_temp = T_low
            return True
        
        # ===== 步骤3：主动升温到精细测量上限 =====
        print(f"\n[第一步] 主动升温到精细测量上限 {T_upper}C...")
        if not self.active_warm_up(T_upper):
            print("[错误] 升温失败，继续原流程")
            return False
        
        # ===== 步骤4：保存原始状态 =====
        original_T_end = self.T_end
        original_step_size = self.current_step_size
        original_fine_step = self.fine_step
        
        # ===== 步骤5：切换到精细测量模式 =====
        self.fine_measuring = True
        self.fine_step = fine_step
        self.current_step_size = fine_step
        self.current_target = T_upper
        
        print(f"\n[第二步] 开始精细测量流程")
        print(f"   - 精细步长: {fine_step}C")
        print(f"   - 测量区间: {T_upper}C -> {T_lower}C")
        
        # ===== 步骤6：执行精细测量（传递已测量点） =====
        self.execute_fine_measurement(T_upper, T_lower, measured_temps)
        
        # ===== 步骤7：恢复原始状态 =====
        self.fine_measuring = False
        self.T_end = original_T_end
        self.current_step_size = original_step_size
        self.fine_step = original_fine_step
        
        # ===== 步骤8：记录相变并重置状态（支持多相变） =====
        # 记录已处理的相变
        phase_record = {
            'range': (T_high, T_low),
            'fine_range': (T_upper, T_lower),
            'detection_temp': T_low,
            'phase_index': self.phase_count + 1,
            'timestamp': time.time()
        }
        self.phase_transition_points.append(phase_record)
        self.phase_count += 1
        
        # 设置冷却间隔起点（精细测量结束温度）
        self.last_phase_end_temp = T_lower
        
        # 清除当前相变（但不永久锁定，允许检测下一个相变）
        self.phase_transition_range = None
        self.phase_detected = False  # 重置为False，允许继续检测新相变
        
        # ===== 步骤9：设置下一个粗测点（关键！） =====
        self.next_target = next_coarse_temp
        self.current_target = T_lower  # 当前位置在精测下限
        
        print(f"\n[精细测量完成 - 相变#{self.phase_count}]")
        print(f"   数据收集: 在相变区间内完成了高密度温度点测量")
        print(f"   精细测量最后一点: {T_lower}C")
        print(f"   恢复粗测步长: {original_step_size}C")
        print(f"   下一个粗测点: {next_coarse_temp}C")
        print(f"   后续粗测序列: {next_coarse_temp}C, {next_coarse_temp - self.coarse_step}C, ...")
        print(f"   [多相变支持] 冷却间隔: {self.phase_cooldown_interval}C")
        print(f"   [多相变支持] 总检测相变数: {self.phase_count}")
        print(f"   [多相变支持] 队列中待处理: {len(self.phase_transition_queue)}")
        print("=" * 50)
        
        return True

    def execute_fine_measurement(self, T_high: float, T_low: float, measured_temps: Optional[set] = None):
        """
        执行精细测量流程（用户优化版）
        
        Args:
            T_high: 精细测量上限温度
            T_low: 精细测量下限温度
            measured_temps: 已测量的温度点集合（需要跳过）
        """
        print(f"\n========== 精细测量流程（用户优化版） ==========")
        print(f"   测量区间: {T_high}C -> {T_low}C")
        print(f"   精细步长: {self.fine_step}C")
        
        # 初始化已测量温度点集合
        if measured_temps is None:
            measured_temps = set()
        
        # 计算所有精细测量点
        all_temp_points = []
        temp = T_high
        while temp >= T_low:
            all_temp_points.append(round(temp))
            temp -= self.fine_step
        
        # 筛选出需要测量的点（排除已测量的）
        temp_points_to_measure = [t for t in all_temp_points if round(t) not in measured_temps]
        skipped_points = [t for t in all_temp_points if round(t) in measured_temps]
        
        print(f"   所有精细点: {all_temp_points}")
        print(f"   跳过（已测）: {skipped_points}")
        print(f"   实际测量点: {temp_points_to_measure}")
        print(f"   实际测量次数: {len(temp_points_to_measure)}")
        
        # 确保当前温度已稳定在起始点
        current_temp = self.read_temperature()
        if current_temp is None or abs(current_temp - T_high) > self.eps:
            print(f"[稳温] 当前温度({current_temp}C)与起始点({T_high}C)偏差较大，重新稳定...")
            self._wait_for_stable_temp(T_high, check_recovery=True)
        
        max_retries = 3
        measurement_count = 0
        actual_measured = []
        
        # 在起始点检查是否需要测量
        if round(T_high) not in measured_temps:
            measurement_count += 1
            print(f"\n[{measurement_count}/{len(temp_points_to_measure)}] 在起始点 {T_high}C 进行精细测量...")
            for retry in range(max_retries):
                if self._perform_measurement():
                    actual_measured.append(T_high)
                    break
                elif retry < max_retries - 1:
                    print(f"[重试] 测量失败，重新稳定温度（第{retry+1}/{max_retries}次）...")
                    self._wait_for_stable_temp(T_high, check_recovery=True)
        else:
            print(f"[跳过] 起始点 {T_high}C（已在粗测中测量）")
        
        # 精细降温循环
        temp = T_high
        
        while temp > T_low:
            # 计算下一个测量点
            next_temp = max(temp - self.fine_step, T_low)
            next_temp_rounded = round(next_temp)
            
            print(f"\n[精细降温] 当前: {temp}C -> 目标: {next_temp_rounded}C")
            
            # 设置温度并严格等待（精细测量不使用+1°C补偿，确保能达到精确目标温度）
            self.set_temperature(next_temp, is_cooling=False)
            print(f"[等待] 精细降温中...")
            self._wait_for_stable_temp(next_temp, check_recovery=True)
            
            # 更新当前目标温度
            self.current_target = next_temp
            temp = next_temp
            
            print(f"[完成] 精细降温到: {next_temp_rounded}C")
            
            # 检查是否需要测量（跳过已测量的温度点）
            if next_temp_rounded in measured_temps:
                print(f"[跳过] {next_temp_rounded}C（已在粗测中测量，避免文件覆盖）")
                continue
            
            # 执行精细测量（带重试）
            measurement_count += 1
            print(f"[{measurement_count}/{len(temp_points_to_measure)}] 在 {next_temp_rounded}C 进行精细测量...")
            for retry in range(max_retries):
                if self._perform_measurement():
                    actual_measured.append(next_temp_rounded)
                    break
                elif retry < max_retries - 1:
                    print(f"[重试] 测量失败，重新稳定温度（第{retry+1}/{max_retries}次）...")
                    self._wait_for_stable_temp(next_temp, check_recovery=True)
        
        print(f"\n========== 精细测量流程完成 ==========")
        print(f"   预期测量点数: {len(temp_points_to_measure)}")
        print(f"   实际完成测量: {measurement_count}")
        print(f"   测量温度点: {sorted(actual_measured, reverse=True)}")
        print(f"   最终温度: {T_low}C")
        print("=" * 40)


    def execute_precise_cooling(self, target_temp: float):
        """
        执行精确降温：先降温到目标温度以上3度（无回温检测），
        然后一度一度降温，每一步都要回温检测，直到达到目标温度
        
        Args:
            target_temp: 目标温度
        """
        print(f"\n🔄 ========== 开始精确降温 ==========")
        print(f"🎯 目标温度: {target_temp}°C")
        
        # 设置精确降温标志，禁用自动测量触发
        self.segmented_cooling_active = True
        
        try:
            # 获取当前温度
            current_temp = self.read_temperature()
            if current_temp is None:
                print("❌ 无法读取当前温度，退出精确降温")
                return False
            
            print(f"📍 当前温度: {current_temp:.1f}°C")
            print(f"🎯 目标温度: {target_temp}°C ± {self.eps}°C（范围：{target_temp - self.eps:.1f}°C ~ {target_temp + self.eps:.1f}°C）")
            
            # 计算温差
            temp_diff = abs(current_temp - target_temp)
            
            # ========== 情况A：温度在范围内（±0.8°C） ==========
            if temp_diff <= self.eps:
                print(f"\n【情况A：温度在范围内】")
                print(f"✅ 当前温度 {current_temp:.1f}°C 已在目标范围内")
                print(f"   温差: {temp_diff:.1f}°C <= EPS({self.eps}°C)")
                print(f"⏰ 开始40秒稳定性验证...")
                if self._wait_for_stable_temp(target_temp, check_recovery=True):
                    print(f"✅ 温度稳定性验证通过，可以开始测量")
                    return True
                else:
                    print(f"⚠️ 温度稳定性验证失败，继续精确降温流程")
                    # ✅ 修复bug：初始化temp变量
                    temp = current_temp
            
            # ========== 情况B：温度过低（< target - 0.8°C） ==========
            elif current_temp < target_temp - self.eps:
                print(f"\n【情况B：温度过低】")
                print(f"⚠️ 当前温度 {current_temp:.1f}°C < 目标下限 {target_temp - self.eps:.1f}°C")
                print(f"   温差: {temp_diff:.1f}°C > EPS({self.eps}°C)")
                print(f"🛑 停止降温，等待温度回温到目标范围...")
                if self._wait_for_stable_temp(target_temp, check_recovery=True):
                    print(f"✅ 回温完成，温度已进入目标范围，可以开始测量")
                    return True
                else:
                    print(f"⚠️ 回温超时（1小时）")
                    return False
            
            # ========== 情况C：温度过高（> target + 0.8°C） ==========
            else:  # current_temp > target_temp + self.eps
                print(f"\n【情况C：温度过高】")
                print(f"⚠️ 当前温度 {current_temp:.1f}°C > 目标上限 {target_temp + self.eps:.1f}°C")
                print(f"   温差: {temp_diff:.1f}°C > EPS({self.eps}°C)")
                
                # 判断是C1还是C2
                if current_temp > target_temp + 3:
                    # ===== 情况C1：温度高很多（> target + 3°C） =====
                    print(f"\n【情况C1：温度高很多，需要分两步降温】")
                    print(f"   当前 {current_temp:.1f}°C > 目标+3°C = {target_temp + 3:.1f}°C")
                    
                    # 第一步：快速降温到 target + 3°C
                    first_target = target_temp + 3
                    print(f"\n📉 第一步：快速降温到目标温度以上3度 {first_target}°C（无回温检测）")
                    self.set_temperature(first_target, is_cooling=True)  # 降温需要补偿
                    print(f"⏰ 等待降温到 {first_target}°C...")
                    self._wait_for_stable_temp(first_target, check_recovery=False)
                    
                    # 获取实际达到的温度
                    actual_temp = self.read_temperature()
                    if actual_temp is None:
                        print("❌ 无法读取温度，使用设定值")
                        temp = first_target
                    else:
                        temp = actual_temp
                        print(f"✅ 第一步完成，已降温到 {temp:.1f}°C")
                else:
                    # ===== 情况C2：温度稍高（target + 0.8 < temp <= target + 3） =====
                    print(f"\n【情况C2：温度稍高，直接缓慢降温】")
                    print(f"   {target_temp + self.eps:.1f}°C < 当前 {current_temp:.1f}°C <= {target_temp + 3:.1f}°C")
                    temp = current_temp
                
                # 第二步：一度一度缓慢降温到目标范围
                print(f"\n📉 第二步：一度一度缓慢降温到目标范围 {target_temp}°C ± {self.eps}°C")
            
            # ✅ 添加温度异常检测：检查temp变量是否已定义
            if 'temp' not in locals():
                print(f"⚠️ 内部错误：temp变量未定义，使用当前温度")
                temp = self.read_temperature()
                if temp is None:
                    print(f"❌ 无法读取温度，精确降温失败")
                    return False
            
            # 循环降温，直到温度进入目标范围（±0.8°C）
            loop_timeout = 3600  # 1小时超时保护
            loop_start = time.time()
            loop_iterations = 0
            max_iterations = 100  # 最多迭代100次
            
            while time.time() - loop_start < loop_timeout and loop_iterations < max_iterations:
                loop_iterations += 1
                
                # 检查当前温度是否已进入范围
                current_check = self.read_temperature()
                if current_check is None:
                    print(f"⚠️ 无法读取温度（第{loop_iterations}次尝试）")
                    time.sleep(5)
                    continue
                
                check_diff = abs(current_check - target_temp)
                if check_diff <= self.eps:
                    print(f"✅ 温度 {current_check:.1f}°C 已进入目标范围（温差{check_diff:.1f}°C <= {self.eps}°C）")
                    print(f"⏰ 开始最终40秒稳定性验证...")
                    if self._wait_for_stable_temp(target_temp, check_recovery=True):
                        print(f"✅ 最终稳定性验证通过，可以开始测量")
                        return True
                    else:
                        print(f"⚠️ 最终验证失败，继续降温")
                
                # 如果温度还在范围外，继续降温（不需要每次都40秒验证）
                if temp > target_temp + self.eps:
                    next_temp = max(temp - 1, target_temp)  # 每次降温1度
                    print(f"📉 精细降温: {temp:.1f}°C → {next_temp:.1f}°C")
                    self.set_temperature(next_temp, is_cooling=False)  # 精细降温不使用补偿
                    print(f"⏰ 等待降温到 {next_temp}°C...")
                    # 使用普通降温模式（无回温检测，只要温度达到即可）
                    self._wait_for_stable_temp(next_temp, check_recovery=False)
                    temp = next_temp
                    print(f"✅ 已降温到 {temp:.1f}°C，继续检查是否进入目标范围")
                else:
                    # 温度已经 <= target + 0.8，应该已经在范围内了
                    print(f"✅ 温度已降至目标范围附近，退出降温循环")
                    break
            
            # 检查是否超时或超过最大迭代次数
            if loop_iterations >= max_iterations:
                print(f"⚠️ 精确降温超过最大迭代次数（{max_iterations}次）")
                return False
            elif time.time() - loop_start >= loop_timeout:
                print(f"⚠️ 精确降温超时（{loop_timeout}秒）")
                return False
            
            print(f"✅ 精确降温完成，已到达目标温度范围 {target_temp}°C ± {self.eps}°C")
            return True
            
        finally:
            # 清除精确降温标志
            self.segmented_cooling_active = False

    def run_cooling_procedure(self):
        """主降温控制流程 - 集成CHI测量"""
        print(f"🔧 {datetime.now().strftime('%H:%M:%S')} | 降温流程 | 开始执行 run_cooling_procedure()")
        
        # 检查是否处于暂停状态
        if self.paused:
            print(f"⏸️ {datetime.now().strftime('%H:%M:%S')} | 降温流程 | 检测到暂停状态，跳过降温流程")
            print(f"💡 系统当前处于暂停状态，保持温度: {self.pause_target_temp:.1f}°C")
            print(f"🔄 如需恢复降温，请调用 resume_cooling() 方法")
            return
            
        print(f"🔧 {datetime.now().strftime('%H:%M:%S')} | 降温流程 | 检查设备开机状态...")
        if not self._ensure_power_on():
            print(f"❌ {datetime.now().strftime('%H:%M:%S')} | 降温流程 | 设备开机失败，退出程序")
            return
        print(f"✅ {datetime.now().strftime('%H:%M:%S')} | 降温流程 | 设备开机成功，继续执行")
            
        # 确保控制状态正确设置
        self.control_active = True
        print(f"✅ 温度控制已激活，control_active = {self.control_active}")

        # 检查当前温度
        print("检查当前温度...")
        current_temp = self.read_temperature()
        if current_temp is None:
            print("无法读取当前温度，退出程序")
            return
            
        print(f"当前温度: {current_temp:.1f}°C, 初始温度: {self.T_start}°C")
        
        # 执行精确降温到初始温度
        print(f"\n📉 开始精确降温到初始温度: {self.T_start}°C")
        reached = self.execute_precise_cooling(self.T_start)
        
        if reached:
            print(f"✅ 精确降温完成，已到达初始温度 {self.T_start}°C")
            # 执行第一次测量（带重试机制）
            print(f"\n{'='*60}")
            print(f"🧪 [第1次测量] 开始在初始温度 {self.T_start}°C 下进行CHI+EIS测量...")
            print(f"{'='*60}\n")
            
            # 循环直到测量成功
            max_measurement_retries = 5
            for retry in range(max_measurement_retries):
                measurement_success = self._perform_measurement()
                if measurement_success:
                    print(f"\n{'='*60}")
                    print(f"✅ [第1次测量完成] 初始温度 {self.T_start}°C 的测量已完成")
                    print(f"{'='*60}\n")
                    break
                else:
                    if retry < max_measurement_retries - 1:
                        print(f"\n⚠️ 测量失败（温度不稳定），重新执行精确降温（第{retry + 1}/{max_measurement_retries}次重试）...")
                        reached = self.execute_precise_cooling(self.T_start)
                        if not reached:
                            print(f"❌ 重新降温失败，但继续尝试测量")
                    else:
                        print(f"\n❌ 经过{max_measurement_retries}次尝试，仍无法完成测量，跳过此测量点")
        else:
            print(f"❌ 精确降温失败，跳过初始温度测量")

        # 计算所有测量点
        self.measurement_points = []
        temp = self.T_start
        while temp > self.T_end:
            temp -= self.current_step_size
            if temp >= self.T_end:
                self.measurement_points.append(temp)
        
        # 确保最终温度也在测量点中
        if not self.measurement_points or self.measurement_points[-1] != self.T_end:
            self.measurement_points.append(self.T_end)
            
        # 设置完整的测量点列表（包括起始点）
        self.all_measurement_points = [self.T_start] + self.measurement_points
        self.current_measurement_index = 0
        
        # 设置下一个目标温度
        if len(self.measurement_points) > 0:
            self.next_target = self.measurement_points[0]
            print(f"🎯 下一个目标温度设置为: {self.next_target}°C")
        else:
            self.next_target = self.T_end
            print(f"🎯 最终目标温度设置为: {self.T_end}°C")
            
        print(f"\n📊 计划测量点: {self.all_measurement_points}")
        print(f"📏 总测量点数: {len(self.all_measurement_points)}")
        print(f"🎯 测量点列表: {self.measurement_points}")

        # 主降温循环（第一段）
        print(f"\n🔄 ========== 开始第一段主降温循环 ==========")
        print(f"🎯 目标路径: {self.T_start}°C → {self.T_end}°C")
        print(f"📏 当前步长: {self.current_step_size}°C")
        
        # 处理所有测量点
        for i, target_temp in enumerate(self.measurement_points):
            if not self.control_active:
                break
            
            # ========== 自动停止检测 ==========
            if self.should_stop_due_to_poor_performance:
                print(f"\n{'='*60}")
                print(f"🛑 由于材料性能不佳，自动终止测试")
                print(f"{'='*60}")
                print(f"📍 最后测量温度: {self.current_temp:.1f}°C")
                print(f"🔍 停止原因: {self.stop_reason}")
                print(f"📊 已完成测量点数: {len(self.measurement_history)}")
                print(f"{'='*60}")
                break
                
            print(f"\n[{i+2}/{len(self.measurement_points)+1}] 准备降温到测量点: {target_temp}°C")
            
            # 更新当前测量索引和下一个目标
            self.current_measurement_index = i + 1  # +1因为已经测了起始点
            
            # 更新下一个目标温度（用于前端显示，仅在未暂停时）
            if not self.paused:
                if i + 1 < len(self.measurement_points):
                    self.next_target = self.measurement_points[i + 1]
                else:
                    self.next_target = self.T_end
            
            # 检查当前实际温度是否已经到达或低于目标
            current_actual_temp = self.read_temperature()
            if current_actual_temp and current_actual_temp <= target_temp + self.eps:
                print(f"📊 当前温度 {current_actual_temp:.1f}°C 已达到目标 {target_temp}°C")
                # 执行测量（带重试）
                self.current_target = target_temp
                print(f"🧪 在 {target_temp}°C 执行CHI+EIS测量...")
                
                max_retries = 3
                measurement_done = False
                for retry in range(max_retries):
                    if self._perform_measurement():
                        measurement_done = True
                        break
                    elif retry < max_retries - 1:
                        print(f"⚠️ 测量失败，重新稳定温度（第{retry+1}/{max_retries}次）...")
                        self.set_temperature(target_temp, is_cooling=False)  # 保持温度不需要补偿
                        time.sleep(10)
                
                if measurement_done:
                    # 更新下一个目标温度（仅在未暂停时）
                    if not self.paused:
                        if i + 1 < len(self.measurement_points):
                            self.next_target = self.measurement_points[i + 1]
                            print(f"🎯 下一个目标温度设置为: {self.next_target}°C")
                        else:
                            self.next_target = self.T_end
                            print(f"🎯 已到达最终目标温度: {self.T_end}°C")
                    
                    continue  # 跳到下一个测量点
                else:
                    print(f"❌ 经过{max_retries}次尝试仍无法完成测量，跳过此测量点")
                    continue
                
            # 需要降温到目标
            self.current_target = target_temp
                
            # 检查暂停状态
            if self.paused:
                print(f"\n⏸️ 降温已暂停，保持温度: {self.pause_target_temp:.1f}°C")
                print("💡 等待用户恢复降温控制...")
                
                while self.paused and self.control_active:
                    current_temp = self.read_temperature()
                    if current_temp is not None and self.pause_target_temp is not None:
                        temp_diff = abs(current_temp - self.pause_target_temp)
                        if temp_diff > self.eps * 2:
                            print(f"📉 温度偏离暂停目标，重新设置: {self.pause_target_temp:.1f}°C")
                            self.set_temperature(self.pause_target_temp, is_cooling=False)  # 保持温度不需要补偿
                        
                    time.sleep(5)
                
                if not self.paused and self.control_active:
                    print(f"▶️ 恢复降温控制，继续向 {self.T_end}°C 降温")
            
            # 检查并处理相变点（支持多相变）
            if self.check_phase_transition():
                if self.two_phase_mode and self.defer_fine_to_second_pass:
                    # 两段模式：第一段仅记录，不做精细测量
                    # 注意：handle_phase_transition() 内部会处理两段模式的逻辑
                    self.handle_phase_transition()
                    print(f"[多相变] 继续降温，已检测到 {self.phase_count} 个相变")
                else:
                    if self.handle_phase_transition():
                        # ✅ 修复Bug 1: 精细测量已完成，不需要再次测量
                        # 精细测量中已经测量了所有精细点（包括最后一点T_lower）
                        # 直接continue到主流程下一个点即可
                        print(f"✅ 精细测量完成，继续主流程")
                        print(f"🎯 主流程下一个目标: {self.measurement_points[i+1] if i+1 < len(self.measurement_points) else self.T_end}°C")
                        continue
            
            # 执行分段降温到目标温度
            print(f"\n📉 开始分段降温到目标: {target_temp}°C")
            reached = self.execute_segmented_cooling(target_temp, self.current_step_size)
            
            if reached:
                print(f"✅ 成功到达目标温度: {target_temp}°C")
                
                # 执行CHI测量（带重试机制）
                print(f"🧪 开始在 {target_temp}°C 下进行CHI+EIS测量...")
                
                # 循环直到测量成功
                max_measurement_retries = 5
                for retry in range(max_measurement_retries):
                    measurement_success = self._perform_measurement()
                    if measurement_success:
                        print(f"✅ 测量点 {target_temp}°C 完成，继续下一个测量点...")
                        break
                    else:
                        if retry < max_measurement_retries - 1:
                            print(f"\n⚠️ 测量失败（温度不稳定），重新执行降温（第{retry + 1}/{max_measurement_retries}次重试）...")
                            reached = self.execute_segmented_cooling(target_temp, self.current_step_size)
                            if not reached:
                                print(f"❌ 重新降温失败，但继续尝试测量")
                        else:
                            print(f"\n❌ 经过{max_measurement_retries}次尝试，仍无法完成测量，跳过此测量点")
            else:
                print(f"⚠️ 未能达到目标温度 {target_temp}°C，继续尝试...")
                time.sleep(5)

        # ========== 检测自动停止触发的情况 ==========
        if self.should_stop_due_to_poor_performance:
            print(f"\n{'='*60}")
            print(f"✅ 材料性能自动停止 - 进入后续分析流程")
            print(f"{'='*60}")
            print(f"📍 停止温度: {self.current_temp:.1f}°C (原目标: {self.T_end}°C)")
            print(f"🔍 停止原因: {self.stop_reason}")
            print(f"📊 有效测量点数: {len(self.measurement_history)}")
            print(f"🌡️  最后有效温度: {self.last_valid_temperature}°C" if self.last_valid_temperature else "")
            print(f"{'='*60}")
            
            # 保存实验报告（包含停止原因）
            self.save_experiment_report()
            self.plot_results()
            
            # 🎯 自动触发离线批量分析
            print("\n" + "="*70)
            print("🚀 测试已自动停止！启动离线批量分析...")
            print("="*70)
            self._auto_run_offline_analysis()
            
            # 通知前端
            if hasattr(self, 'status_change_callback') and callable(self.status_change_callback):
                try:
                    self.status_change_callback('auto_stopped', 
                        f'材料性能不佳自动停止 ({self.stop_reason}), 已完成{len(self.measurement_history)}个测量点')
                except Exception as e:
                    print(f"[回调错误] 状态变化回调失败: {e}")
            return
        
        print(f"\n第一段最终温度 {self.T_end}°C 已达成")

        # 若启用两段模式，则执行回温+第二段快速降温与精细测量
        if self.two_phase_mode:
            # 检查当前温度，如果太低则跳过回温
            current_temp = self.read_temperature()
            if current_temp and current_temp < self.second_pass_warm_temp - 15:
                print(f"\n⚠️ 当前温度 {current_temp:.1f}°C 距离回温目标 {self.second_pass_warm_temp}°C 超过15°C")
                print(f"⚠️ 为避免长时间等待，跳过第二段回温测量")
                print("✅ 第一段降温测量已完成，流程结束")
                self.save_experiment_report()
                self.plot_results()
                # 🎯 自动触发离线批量分析
                print("\n" + "="*70)
                print("🚀 数据采集完成！自动启动离线批量分析...")
                print("="*70)
                self._auto_run_offline_analysis()
                return
            
            # 回温到室温
            print(f"\n🔁 回温到室温 {self.second_pass_warm_temp}°C，准备第二段降温...")
            self.set_temperature(self.second_pass_warm_temp, is_cooling=False)  # 回温不需要补偿
            
            # 设置回温超时（10分钟）
            warmup_start = time.time()
            warmup_timeout = 600  # 10分钟
            while time.time() - warmup_start < warmup_timeout:
                current_temp = self.read_temperature()
                if current_temp and abs(current_temp - self.second_pass_warm_temp) <= self.eps:
                    print(f"✅ 已回温到 {current_temp:.1f}°C")
                    break
                time.sleep(5)
            else:
                print(f"⚠️ 回温超时（10分钟），跳过第二段测量")
                print("✅ 第一段降温测量已完成，流程结束")
                self.save_experiment_report()
                self.plot_results()
                # 🎯 自动触发离线批量分析
                print("\n" + "="*70)
                print("🚀 数据采集完成！自动启动离线批量分析...")
                print("="*70)
                self._auto_run_offline_analysis()
                return

            # 确定相变区间
            region = self.second_phase_region_override or self.phase_transition_range
            if not region:
                print("⚠️ 未检测到相变区间，第二段将不进行精细测量，流程结束")
                self.save_experiment_report()
                self.plot_results()
                # 🎯 自动触发离线批量分析
                print("\n" + "="*70)
                print("🚀 数据采集完成！自动启动离线批量分析...")
                print("="*70)
                self._auto_run_offline_analysis()
                return

            T_high, T_low = region
            print(f"🧭 第二段目标相变区间: [{T_high}°C, {T_low}°C]")

            # 第二段：精细降温测量流程
            print(f"\n🚀 第二段：精细降温测量流程")
            self.only_measure_in_region = True
            original_step = self.current_step_size

            # 第一步：降温到相变区间上界+3度
            first_target = T_high + 3
            print(f"📉 第一步：降温到相变区间上界+3度 {first_target}°C")
            self.set_temperature(first_target, is_cooling=True)  # 降温需要补偿
            print(f"⏰ 等待降温到 {first_target}°C...")
            self._wait_for_stable_temp(first_target, check_recovery=True)
            print(f"✅ 已降温到 {first_target}°C")

            # 第二步：一度一度降温到区间上界-3度，然后测量
            current_temp = self.read_temperature()
            temp = current_temp if current_temp is not None else first_target
            
            print(f"📉 第二步：一度一度降温到区间上界-3度 {T_high - 3}°C")
            while temp > T_high - 3:
                next_temp = max(temp - 1, T_high - 3)  # 每次降温1度
                print(f"📉 精细降温: {temp:.1f}°C → {next_temp:.1f}°C")
                self.set_temperature(next_temp, is_cooling=False)  # 精细降温不使用补偿
                print(f"⏰ 等待温度稳定到 {next_temp}°C（回温检测）...")
                self._wait_for_stable_temp(next_temp, check_recovery=True)
                print(f"✅ 温度已稳定在 {next_temp}°C")
                temp = next_temp
            
            # 在区间上界-3度进行测量（带重试）
            print(f"🧪 在 {T_high - 3}°C 进行测量...")
            self.current_target = T_high - 3
            max_retries = 3
            for retry in range(max_retries):
                if self._perform_measurement():
                    break
                elif retry < max_retries - 1:
                    print(f"⚠️ 测量失败，重新稳定温度（第{retry+1}/{max_retries}次）...")
                    self._wait_for_stable_temp(T_high - 3, check_recovery=True)

            # 第三步：一度一度降温到区间上界-6度，然后测量
            print(f"📉 第三步：一度一度降温到区间上界-6度 {T_high - 6}°C")
            while temp > T_high - 6:
                next_temp = max(temp - 1, T_high - 6)  # 每次降温1度
                print(f"📉 精细降温: {temp:.1f}°C → {next_temp:.1f}°C")
                self.set_temperature(next_temp, is_cooling=False)  # 精细降温不使用补偿
                print(f"⏰ 等待温度稳定到 {next_temp}°C（回温检测）...")
                self._wait_for_stable_temp(next_temp, check_recovery=True)
                print(f"✅ 温度已稳定在 {next_temp}°C")
                temp = next_temp
            
            # 在区间上界-6度进行测量（带重试）
            print(f"🧪 在 {T_high - 6}°C 进行测量...")
            self.current_target = T_high - 6
            for retry in range(max_retries):
                if self._perform_measurement():
                    break
                elif retry < max_retries - 1:
                    print(f"⚠️ 测量失败，重新稳定温度（第{retry+1}/{max_retries}次）...")
                    self._wait_for_stable_temp(T_high - 6, check_recovery=True)

            # 第四步：一度一度降温到区间上界-8度，然后测量
            print(f"📉 第四步：一度一度降温到区间上界-8度 {T_high - 8}°C")
            while temp > T_high - 8:
                next_temp = max(temp - 1, T_high - 8)  # 每次降温1度
                print(f"📉 精细降温: {temp:.1f}°C → {next_temp:.1f}°C")
                self.set_temperature(next_temp, is_cooling=False)  # 精细降温不使用补偿
                print(f"⏰ 等待温度稳定到 {next_temp}°C（回温检测）...")
                self._wait_for_stable_temp(next_temp, check_recovery=True)
                print(f"✅ 温度已稳定在 {next_temp}°C")
                temp = next_temp
            
            # 在区间上界-8度进行测量（带重试）
            print(f"🧪 在 {T_high - 8}°C 进行测量...")
            self.current_target = T_high - 8
            for retry in range(max_retries):
                if self._perform_measurement():
                    break
                elif retry < max_retries - 1:
                    print(f"⚠️ 测量失败，重新稳定温度（第{retry+1}/{max_retries}次）...")
                    self._wait_for_stable_temp(T_high - 8, check_recovery=True)

            # 恢复状态
            self.only_measure_in_region = False
            self.current_step_size = original_step
            # 不设置 phase_detected = True，保持多相变支持的状态

        print(f"\n第二段（如启用）完成，流程结束")
        print(f"[多相变统计] 总共检测到 {self.phase_count} 个相变点")
        self.save_experiment_report()
        
        # 🔄 先执行回温到18°C
        print(f"\n🔄 设置回温到18°C...")
        self.set_temperature(18.0, is_cooling=False)  # 回温不需要补偿
        print(f"✅ 已设置制冷器温度为18°C，将自动回温")
        
        # 绘制温度曲线
        self.plot_results()
        
        # 🎯 然后自动触发离线批量分析
        print("\n" + "="*70)
        print("🚀 数据采集完成！自动启动离线批量分析...")
        print("="*70)
        self._auto_run_offline_analysis()
        
        # 更新控制状态为已完成
        self.control_active = False
        print(f"✅ 温度控制流程已完成，control_active = {self.control_active}")
        
        # 如果有温度更新回调，通知完成状态
        if hasattr(self, 'temperature_update_callback') and self.temperature_update_callback:
            try:
                self.temperature_update_callback(self.current_temp)
            except Exception as e:
                print(f"⚠️ 温度更新回调执行失败: {e}")

    # ==================== 自动触发离线分析 ====================
    
    def _auto_run_offline_analysis(self):
        """
        数据采集完成后，自动触发离线批量分析
        包括：Rb拟合、Arrhenius分析、报告生成、AI机理分析
        """
        # 在函数开始时导入所有需要的模块，避免作用域问题
        import os as os_local
        import sys
        import glob
        
        try:
            print("\n" + "🔍 正在导入离线分析模块...")
            
            # 动态导入 run_closed_loop
            try:
                from auto_control.run_closed_loop import run_closed_loop
            except ImportError:
                if str(CLOSE_ROOT) not in sys.path:
                    sys.path.insert(0, str(CLOSE_ROOT))
                from auto_control.run_closed_loop import run_closed_loop
            
            print("✅ 离线分析模块导入成功")
            
            # 🎯 优先使用CHI原始数据，fallback到标准化EIS数据
            print("\n" + "🔍 正在查找数据文件...")
            chi_data_dir = self.chi_params.get('your_position', 'E:\\chi_data')
            print(f"[优先] 检查CHI原始数据目录: {chi_data_dir}")
            
            # 检查CHI原始数据
            chi_files = glob.glob(os_local.path.join(chi_data_dir, "*.txt"))
            
            if not chi_files:
                print(f"⚠️ 在 {chi_data_dir} 中未找到CHI原始数据文件")
                print(f"🔄 切换到标准化EIS数据目录: {self.eis_data_dir}")
                chi_data_dir = self.eis_data_dir
                chi_files = glob.glob(os_local.path.join(chi_data_dir, "*.txt"))
                
                if not chi_files:
                    print(f"❌ 在 {chi_data_dir} 中也未找到EIS数据文件(.txt)，跳过离线分析")
                    return
                else:
                    print(f"✅ 找到 {len(chi_files)} 个标准化EIS数据文件")
            else:
                print(f"✅ 找到 {len(chi_files)} 个CHI原始数据文件（优先使用）")
            
            # 调用离线分析
            print("\n" + "="*70)
            print("📊 开始离线批量分析（Rb拟合 + Arrhenius + 报告生成）")
            print("="*70)
            
            report = run_closed_loop(
                data_dir=chi_data_dir,
                config_file=None,
                thickness=self.thickness * 100,  # m -> cm
                area=self.area * 10000,          # m² -> cm²
                min_arrhenius_points=3,          # 降低最小点数要求
                output_dir=self.data_dir,
                bundle_report=True,               # 🎯 生成高级报告和图表
                ai_eval=True,                     # 🎯 生成AI机理分析报告
                export_pdf=False                  # PDF可选
            )
            
            if report:
                print("\n" + "="*70)
                print("✅ 离线批量分析完成！")
                print("="*70)
                print("\n📁 生成的文件：")
                print(f"  ✅ {self.data_dir}/report.json - 完整结构化数据")
                print(f"  ✅ {self.data_dir}/report.md - 基础Markdown报告")
                print(f"  ✅ {self.data_dir}/conductivity_plot.png - 电导率图表")
                print(f"  ✅ {self.data_dir}/analysis_report.md - 详细分析报告")
                print(f"  ⭐ {self.data_dir}/mechanism_report.md - AI机理分析报告")
                print("\n💡 提示：可以直接查看 mechanism_report.md 获取实验建议！")
                
                # ✅ 推送离线分析完成事件到前端
                if self.offline_analysis_complete_callback:
                    try:
                        self.offline_analysis_complete_callback({
                            'status': 'completed',
                            'timestamp': time.time(),
                            'report_path': os.path.join(self.data_dir, 'report.json'),
                            'message': '离线批量分析完成'
                        })
                        print("📡 [WebSocket] 已推送离线分析完成事件")
                    except Exception as e:
                        print(f"⚠️ 推送离线分析完成事件失败: {e}")
            else:
                print("\n⚠️ 离线分析未能完成，请检查数据文件")
                
        except Exception as e:
            print(f"\n❌ 自动离线分析失败: {e}")
            print("💡 你可以手动运行离线分析：")
            print(f"   python auto_control/run_closed_loop.py \\")
            print(f"     --data-dir {self.chi_params.get('your_position', 'E:chi_data')} \\")
            print(f"     --thickness {self.thickness * 100:.4f} \\")
            print(f"     --area {self.area * 10000:.4f} \\")
            print(f"     --bundle-report --ai-eval")
            import traceback
            traceback.print_exc()
    
    # ==================== 数据保存和可视化功能 ====================
    
    def save_experiment_data(self):
        """实时保存实验数据"""
        # 保存温度历史
        temp_file = os.path.join(self.data_dir, "temperature_history.json")
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(self.temperature_history, f, indent=2, ensure_ascii=False)
        
        # 保存测量记录
        meas_file = os.path.join(self.data_dir, "measurement_history.json")
        with open(meas_file, 'w', encoding='utf-8') as f:
            json.dump(self.measurement_history, f, indent=2, ensure_ascii=False)
        
        # 保存相变点
        if self.phase_transition_range:
            phase_transition = {
                'range': self.phase_transition_range,
                'detected_at': self.current_temp,
                'timestamp': time.time()
            }
            self.phase_transition_points.append(phase_transition)
            phase_file = os.path.join(self.data_dir, "phase_transitions.json")
            with open(phase_file, 'w', encoding='utf-8') as f:
                json.dump(self.phase_transition_points, f, indent=2, ensure_ascii=False)
        
        print(f"实验数据已保存到 {self.data_dir}")

    def save_experiment_report(self):
        """生成并保存实验报告"""
        # 确定最终状态
        if self.should_stop_due_to_poor_performance:
            final_status = "auto_stopped_poor_performance"
        elif self.paused:
            final_status = "paused"
        elif not self.control_active:
            final_status = "stopped"
        else:
            final_status = "completed"
        
        report = {
            "experiment_start": datetime.now().isoformat(),
            "start_temperature": self.T_start,
            "end_temperature": self.T_end,
            "actual_end_temperature": self.current_temp,  # 实际结束温度
            "coarse_step_size": self.coarse_step,
            "fine_step_size": self.fine_step,
            "num_measurements": len(self.measurement_history),
            "num_chi_measurements": self.chi_measurement_count,
            "phase_transitions": self.phase_transition_points,
            "chi_params": self.chi_params,
            "final_status": final_status,
            # 自动停止相关信息
            "auto_stop_info": {
                "triggered": self.should_stop_due_to_poor_performance,
                "reason": self.stop_reason,
                "last_valid_temperature": self.last_valid_temperature,
                "config": self.auto_stop_config
            } if self.should_stop_due_to_poor_performance else None
        }
        
        report_file = os.path.join(self.data_dir, "experiment_report.json")
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"实验报告已保存: {report_file}")

    def plot_results(self):
        """绘制实验结果"""
        self.plot_temperature_profile()
        self.plot_conductivity()

    def plot_temperature_profile(self):
        """绘制温度变化曲线 - 文献风格"""
        if not self.temperature_history:
            times = [m['timestamp'] for m in self.measurement_history]
            temps = [m['temperature_C'] for m in self.measurement_history]
        else:
            times, temps = zip(*self.temperature_history)
            
        if not times:
            print("无温度数据可绘制")
            return
        
        # 以测量历史的最早时间为基准
        if self.measurement_history:
            start_time = min(m['timestamp'] for m in self.measurement_history)
        else:
            start_time = min(times)
        
        # 过滤掉测量开始前的温度数据，确保时间非负
        filtered_data = [(t - start_time, temp) for t, temp in zip(times, temps) if t >= start_time]
        
        if filtered_data:
            timestamps, temps = zip(*filtered_data)
        else:
            timestamps = [max(0, t - start_time) for t in times]
        
        # 获取材料名称
        material_name = self.chi_params.get('material', 'Sample')
        
        # === 文献风格绘图 ===
        # 设置字体和风格
        plt.rcParams['font.family'] = 'Arial'
        plt.rcParams['font.size'] = 12
        plt.rcParams['axes.linewidth'] = 1.5
        
        fig, ax = plt.subplots(figsize=(10, 6))
        
        # 设置背景
        ax.set_facecolor('white')
        fig.patch.set_facecolor('white')
        
        # 将时间转换为小时
        timestamps_hours = [t / 3600 for t in timestamps]
        
        # 绘制温度曲线 - 使用渐变色
        line, = ax.plot(timestamps_hours, temps, 
                        color='#2E86AB',  # 深蓝色
                        linewidth=2.0, 
                        label='Temperature',
                        zorder=5)
        
        # 标记测量点
        meas_times_hours = [max(0, m['timestamp'] - start_time) / 3600 for m in self.measurement_history]
        meas_temps = [m['temperature_C'] for m in self.measurement_history]
        ax.scatter(meas_times_hours, meas_temps, 
                   c='#E74C3C',  # 红色
                   s=80, 
                   marker='o',
                   edgecolors='white',
                   linewidths=1.5,
                   label='EIS Measurement',
                   zorder=10)
        
        # 标记相变点（去重 + 格式化）
        plotted_phases = set()
        phase_colors = ['#27AE60', '#9B59B6', '#F39C12', '#1ABC9C']  # 多色方案
        
        for idx, phase in enumerate(self.phase_transition_points):
            T_high, T_low = phase['range']
            phase_key = (round(T_high, 1), round(T_low, 1))
            
            if phase_key in plotted_phases:
                continue
            
            plotted_phases.add(phase_key)
            
            # 寻找相变点对应的时刻
            mid_temp = (T_high + T_low) / 2
            min_diff = float('inf')
            phase_time = None
            
            for t, temp in zip(times, temps):
                if t >= start_time:
                    diff = abs(temp - mid_temp)
                    if diff < min_diff:
                        min_diff = diff
                        phase_time = t
            
            # 绘制阴影区域表示相变
            if phase_time is not None:
                phase_time_hours = max(0, phase_time - start_time) / 3600
                color = phase_colors[idx % len(phase_colors)]
                
                # 用细虚线标记相变点
                ax.axvline(x=phase_time_hours, 
                          color=color, 
                          linestyle='--', 
                          linewidth=1.5,
                          alpha=0.8,
                          label=f"Phase transition ({phase_key[1]:.0f} to {phase_key[0]:.0f} °C)")
        
        # 坐标轴设置
        ax.set_xlabel('Time (h)', fontsize=14, fontweight='bold')
        ax.set_ylabel('Temperature (°C)', fontsize=14, fontweight='bold')
        ax.set_title(f'Temperature Profile - {material_name}', fontsize=16, fontweight='bold', pad=15)
        
        # 坐标轴刻度
        ax.tick_params(axis='both', which='major', labelsize=12, width=1.5, length=6, direction='in')
        ax.tick_params(axis='both', which='minor', width=1.0, length=3, direction='in')
        
        # 网格 - 淡灰色虚线
        ax.grid(True, which='major', linestyle='--', linewidth=0.5, alpha=0.5, color='gray')
        
        # 设置X轴从0开始
        ax.set_xlim(left=0)
        
        # 图例
        handles, labels = ax.get_legend_handles_labels()
        by_label = dict(zip(labels, handles))
        ax.legend(by_label.values(), by_label.keys(), 
                  loc='upper right', 
                  framealpha=0.95, 
                  edgecolor='gray',
                  fontsize=10)
        
        # 边框加粗
        for spine in ax.spines.values():
            spine.set_linewidth(1.5)
        
        plt.tight_layout()
        
        plot_file = os.path.join(self.data_dir, "temperature_profile.png")
        plt.savefig(plot_file, dpi=300, bbox_inches='tight', facecolor='white')
        print(f"温度曲线已保存: {plot_file}")
        plt.close()

    def plot_conductivity(self):
        """绘制电导率-温度曲线 - Arrhenius文献风格（双横坐标）"""
        if not self.measurement_history:
            print("无电导率数据可绘制")
            return
        
        temps_C = []
        conds_S_cm = []
        for meas in self.measurement_history:
            conductivity = meas.get('conductivity_S_per_cm') or meas.get('conductivity')
            temperature = meas.get('temperature_C') or meas.get('temperature')
            
            if conductivity is not None and conductivity > 0 and temperature is not None:
                temps_C.append(temperature)
                conds_S_cm.append(conductivity)
        
        if not temps_C:
            print("无有效电导率数据")
            return
        
        # 转换为numpy数组
        temps_C = np.array(temps_C)
        conds_S_cm = np.array(conds_S_cm)
        
        # 转换单位
        temps_K = temps_C + 273.15
        inv_T_1000 = 1000.0 / temps_K  # 1000/T (K^-1)
        conds_mS_cm = conds_S_cm * 1000  # S/cm -> mS/cm
        log_sigma = np.log10(conds_mS_cm)  # log10(σ)
        
        # 获取材料名称
        material_name = self.chi_params.get('material', 'Sample')
        
        # === 文献风格绘图（双横坐标）===
        plt.rcParams['font.family'] = 'Arial'
        plt.rcParams['font.size'] = 12
        plt.rcParams['axes.linewidth'] = 1.5
        
        fig, ax1 = plt.subplots(figsize=(10, 8))
        
        # 设置背景
        ax1.set_facecolor('white')
        fig.patch.set_facecolor('white')
        
        # 排序数据（按1000/T从小到大）
        sort_idx = np.argsort(inv_T_1000)
        inv_T_sorted = inv_T_1000[sort_idx]
        log_sigma_sorted = log_sigma[sort_idx]
        temps_C_sorted = temps_C[sort_idx]
        
        # 绘制数据点
        scatter = ax1.scatter(inv_T_sorted, log_sigma_sorted, 
                             c='#E74C3C',  # 红色
                             s=120,
                             marker='*',  # 星形
                             edgecolors='#8B0000',
                             linewidths=0.8,
                             label=material_name,
                             zorder=10)
        
        # 线性拟合（Arrhenius关系）
        try:
            from scipy.stats import linregress
            slope, intercept, r_value, _, _ = linregress(inv_T_sorted, log_sigma_sorted)
            
            # 计算活化能 Ea (kJ/mol)
            # log10(σ) = -Ea/(2.303*R*T) + log10(σ0)
            # 斜率 = -Ea*1000/(2.303*R) (因为x轴是1000/T)
            R = 8.314  # J/(mol·K)
            Ea_J_mol = -float(slope) * 2.303 * R * 1000  # 转换为 J/mol
            Ea_kJ_mol = Ea_J_mol / 1000  # kJ/mol
            
            # 绘制拟合线（灰色虚线）
            x_fit = np.linspace(inv_T_sorted.min(), inv_T_sorted.max(), 100)
            y_fit = slope * x_fit + intercept
            ax1.plot(x_fit, y_fit, 
                    color='gray', 
                    linestyle='--', 
                    linewidth=2.0,
                    alpha=0.8,
                    label=f'Linear fit (Ea = {Ea_kJ_mol:.1f} kJ/mol)')
        except Exception as e:
            print(f"线性拟合失败: {e}")
        
        # 标记相变点
        plotted_phases = set()
        
        for phase in self.phase_transition_points:
            T_high, T_low = phase['range']
            phase_key = (round(T_high, 1), round(T_low, 1))
            
            if phase_key in plotted_phases:
                continue
            plotted_phases.add(phase_key)
            
            # 计算相变区间对应的1000/T范围
            inv_T_high = 1000.0 / (T_high + 273.15)
            inv_T_low = 1000.0 / (T_low + 273.15)
            
            # 用红色半透明区域标记相变
            ax1.axvspan(min(inv_T_high, inv_T_low), max(inv_T_high, inv_T_low), 
                       alpha=0.15, color='red', 
                       label=f'Phase transition ({T_low:.0f} to {T_high:.0f} °C)')
        
        # === 底部X轴: 1000/T (K^-1) ===
        ax1.set_xlabel(r'$1000/T$ (K$^{-1}$)', fontsize=14, fontweight='bold')
        ax1.set_ylabel(r'log $\sigma$ (mS cm$^{-1}$)', fontsize=14, fontweight='bold')
        
        # 设置X轴范围和刻度
        x_min, x_max = inv_T_sorted.min() - 0.2, inv_T_sorted.max() + 0.2
        ax1.set_xlim(x_min, x_max)
        
        # Y轴范围
        y_min, y_max = log_sigma_sorted.min() - 0.5, log_sigma_sorted.max() + 0.5
        ax1.set_ylim(y_min, y_max)
        
        # === 顶部X轴: T (°C) ===
        ax2 = ax1.twiny()
        ax2.set_xlim(ax1.get_xlim())
        
        # 计算温度刻度位置
        # 选择一些典型的温度值
        typical_temps_C = np.array([60, 25, 0, -25, -50, -75, -100, -125])
        typical_temps_C = typical_temps_C[(typical_temps_C >= temps_C.min() - 10) & 
                                          (typical_temps_C <= temps_C.max() + 10)]
        
        if len(typical_temps_C) < 3:
            typical_temps_C = np.linspace(temps_C.min(), temps_C.max(), 5)
        
        typical_inv_T = 1000.0 / (typical_temps_C + 273.15)
        
        ax2.set_xticks(typical_inv_T)
        ax2.set_xticklabels([f'{int(t)}' for t in typical_temps_C])
        ax2.set_xlabel(r'$T$ (°C)', fontsize=14, fontweight='bold')
        
        # 刻度样式
        ax1.tick_params(axis='both', which='major', labelsize=12, width=1.5, length=6, direction='in')
        ax2.tick_params(axis='x', which='major', labelsize=12, width=1.5, length=6, direction='in')
        
        # 网格
        ax1.grid(True, which='major', linestyle='--', linewidth=0.5, alpha=0.5, color='gray')
        
        # 图例
        handles, labels = ax1.get_legend_handles_labels()
        by_label = dict(zip(labels, handles))
        ax1.legend(by_label.values(), by_label.keys(), 
                  loc='upper right', 
                  framealpha=0.95, 
                  edgecolor='gray',
                  fontsize=10)
        
        # 标题
        ax1.set_title(f'Arrhenius Plot - {material_name}', fontsize=16, fontweight='bold', pad=35)
        
        # 边框加粗
        for spine in ax1.spines.values():
            spine.set_linewidth(1.5)
        for spine in ax2.spines.values():
            spine.set_linewidth(1.5)
        
        plt.tight_layout()
        
        cond_file = os.path.join(self.data_dir, "conductivity_profile.png")
        plt.savefig(cond_file, dpi=300, bbox_inches='tight', facecolor='white')
        print(f"电导率曲线已保存: {cond_file}")
        plt.close()

    # ==================== 实时监控功能 ====================
    
    def start_realtime_monitoring(self):
        """启动实时温度监控"""
        if self.is_monitoring:
            return False
            
        self.is_monitoring = True
        self.monitoring_thread = threading.Thread(target=self._monitoring_worker)
        self.monitoring_thread.daemon = True
        self.monitoring_thread.start()
        print("实时温度监控已启动")
        return True

    def stop_realtime_monitoring(self):
        """停止实时温度监控"""
        self.is_monitoring = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5)
        print("实时温度监控已停止")

    def _monitoring_worker(self):
        """实时监控工作线程"""
        error_count = 0
        max_errors = 5
        
        while self.is_monitoring:
            try:
                if not hasattr(self, 'ser') or not self.ser or not self.ser.is_open:
                    print("监控线程: 串口连接无效，停止监控")
                    break
                
                current_temp = self.read_temperature()
                if current_temp is not None:
                    error_count = 0
                    
                    realtime_data = {
                        'timestamp': time.time(),
                        'temperature': current_temp,
                        'target_temperature': self.current_target,
                        'control_status': 'active' if self.control_active else 'idle',
                        'chi_measuring': self.chi_measuring,
                        'measurement_count': self.chi_measurement_count
                    }
                    self.realtime_data_queue.put(realtime_data)
                    
                    # ✅ 关键修复：调用WebSocket回调，实时推送温度到前端
                    if hasattr(self, 'temperature_update_callback') and callable(self.temperature_update_callback):
                        try:
                            self.temperature_update_callback(current_temp)
                        except Exception as cb_err:
                            pass  # 静默处理回调错误，不影响监控
                    
                    while self.realtime_data_queue.qsize() > 1000:
                        try:
                            self.realtime_data_queue.get_nowait()
                        except queue.Empty:
                            break
                else:
                    error_count += 1
                    if error_count >= max_errors:
                        print(f"监控线程: 连续{max_errors}次读取失败，停止监控")
                        break
                            
                time.sleep(1)
            except Exception as e:
                error_count += 1
                if error_count >= max_errors:
                    print(f"监控线程: 连续{max_errors}次错误，停止监控: {e}")
                    break
                else:
                    print(f"监控线程错误 ({error_count}/{max_errors}): {e}")
                    time.sleep(2)

    def get_realtime_data(self) -> List[Dict]:
        """获取实时数据"""
        data = []
        while not self.realtime_data_queue.empty():
            try:
                data.append(self.realtime_data_queue.get_nowait())
            except queue.Empty:
                break
        return data

    # ==================== 控制功能 ====================
    
    def start_temperature_control(self, start_temp: float, end_temp: float, 
                                coarse_step: float = 10.0, fine_step: float = 3.0,
                                thickness: Optional[float] = None, area: Optional[float] = None,
                                material: Optional[str] = None, **chi_params):
        """
        启动温度控制（允许修改参数）
        
        Args:
            start_temp: 起始温度（°C）
            end_temp: 终止温度（°C）
            coarse_step: 粗测步长（°C）
            fine_step: 精细步长（°C）
            thickness: 样品厚度（m），可选，不提供则不更新
            area: 样品截面积（m²），可选，不提供则不更新
            material: 样品名称，可选，不提供则不更新
            **chi_params: 其他CHI参数（highf, lowf, initV等）
        """
        print(f"🔧 {datetime.now().strftime('%H:%M:%S')} | 启动控制 | 开始启动温度控制")
        print(f"🔧 {datetime.now().strftime('%H:%M:%S')} | 启动控制 | 温度参数: start_temp={start_temp}°C, end_temp={end_temp}°C, coarse_step={coarse_step}°C, fine_step={fine_step}°C")
        
        if self.control_active:
            print(f"⚠️ {datetime.now().strftime('%H:%M:%S')} | 启动控制 | 温度控制已激活，返回False")
            return False
            
        # 检查是否已经有控制线程在运行
        if hasattr(self, 'control_thread') and self.control_thread and self.control_thread.is_alive():
            print(f"⚠️ {datetime.now().strftime('%H:%M:%S')} | 启动控制 | 控制线程已在运行，返回False")
            return False
            
        # 检查是否处于暂停状态，如果是暂停状态，不允许重新启动
        if hasattr(self, 'paused') and self.paused:
            print(f"⚠️ {datetime.now().strftime('%H:%M:%S')} | 启动控制 | 温度控制处于暂停状态，请使用恢复功能继续控制，返回False")
            return False
            
        print(f"🔧 {datetime.now().strftime('%H:%M:%S')} | 启动控制 | 设置控制参数...")
        # 更新温度参数
        self.T_start = start_temp
        self.T_end = end_temp
        self.coarse_step = coarse_step
        self.fine_step = fine_step
        self.current_step_size = coarse_step
        
        # 更新样品参数（如果提供）
        if thickness is not None:
            self.thickness = thickness
            print(f"🔧 {datetime.now().strftime('%H:%M:%S')} | 启动控制 | 更新样品厚度: {thickness} m")
        
        if area is not None:
            self.area = area
            print(f"🔧 {datetime.now().strftime('%H:%M:%S')} | 启动控制 | 更新样品截面积: {area} m²")
        
        # 更新CHI参数（如果提供）
        if material is not None:
            self.chi_params['material'] = material
            print(f"🔧 {datetime.now().strftime('%H:%M:%S')} | 启动控制 | 更新样品名称: {material}")
        
        # 更新其他CHI参数
        if chi_params:
            for key, value in chi_params.items():
                if key in ['highf', 'lowf', 'initV', 'your_position', 'your_type_text', 'confidence', 'text_confidence', 'delay']:
                    self.chi_params[key] = value
                    print(f"🔧 {datetime.now().strftime('%H:%M:%S')} | 启动控制 | 更新CHI参数 {key}: {value}")
        
        print(f"🔧 {datetime.now().strftime('%H:%M:%S')} | 启动控制 | 当前样品参数: thickness={self.thickness}m, area={self.area}m², material={self.chi_params.get('material')}")
        
        # 设置初始目标温度为起始温度
        self.current_target = start_temp
        print(f"🔧 {datetime.now().strftime('%H:%M:%S')} | 启动控制 | 设置初始目标温度: {start_temp}°C")
        
        # 清空之前保存的目标温度，因为这是新的启动
        if hasattr(self, 'saved_original_target'):
            self.saved_original_target = None
            print(f"🔧 {datetime.now().strftime('%H:%M:%S')} | 启动控制 | 清空之前保存的目标温度")
        
        print(f"🔧 {datetime.now().strftime('%H:%M:%S')} | 启动控制 | 设置 control_active = True")
        self.control_active = True
        
        print(f"🔧 {datetime.now().strftime('%H:%M:%S')} | 启动控制 | 创建并启动控制线程...")
        self.control_thread = threading.Thread(target=self._control_worker)
        self.control_thread.daemon = True
        self.control_thread.start()
        
        print(f"✅ {datetime.now().strftime('%H:%M:%S')} | 启动控制 | 温度控制已启动: {start_temp}°C → {end_temp}°C")
        
        # 调用状态变化回调（用于WebSocket实时推送）
        if hasattr(self, 'status_change_callback') and callable(self.status_change_callback):
            try:
                self.status_change_callback('running', f'实验已启动: {start_temp}°C → {end_temp}°C')
            except Exception as e:
                print(f"[回调错误] 状态变化回调失败: {e}")
        
        return True

    def stop_temperature_control(self):
        """停止温度控制"""
        self.control_active = False
        if self.control_thread:
            self.control_thread.join(timeout=5)
        print("温度控制已停止")
        
        # 调用状态变化回调（用于WebSocket实时推送）
        if hasattr(self, 'status_change_callback') and callable(self.status_change_callback):
            try:
                self.status_change_callback('stopped', '实验已停止')
            except Exception as e:
                print(f"[回调错误] 状态变化回调失败: {e}")
        
        # 禁用日志捕获，恢复正常输出
        self.disable_log_capture()

    def pause_cooling(self) -> bool:
        """暂停降温控制，保存当前目标温度并设置当前温度为新目标温度"""
        print(f"🔍 [调用] pause_cooling | control_active: {self.control_active} | paused: {self.paused}")
        
        if not self.control_active:
            print("❌ 温度控制未启动，无法暂停")
            return False
            
        if self.paused:
            print("⚠️ 温度控制已处于暂停状态")
            return True
            
        current_temp = self.read_temperature()
        print(f"🌡️ 当前读取温度: {current_temp}")
        
        if current_temp is None:
            print("❌ 无法读取当前温度，暂停失败")
            return False
            
        # 保存当前的目标温度（不是当前温度），用于恢复时使用
        # 只有在第一次暂停时才保存原始目标温度
        if not hasattr(self, 'saved_original_target') or self.saved_original_target is None:
            self.saved_original_target = self.current_target
            print(f"💾 保存原始目标温度: {self.saved_original_target:.1f}°C")
        else:
            print(f"💾 已保存原始目标温度: {self.saved_original_target:.1f}°C")
        
        self.paused = True
        self.pause_target_temp = current_temp
        
        # 设置当前温度为新的目标温度，发送给硬件端以暂停降温
        self.current_target = current_temp
        
        # 同时更新next_target为当前温度，避免控制逻辑继续使用旧的next_target
        if hasattr(self, 'next_target'):
            self.next_target = current_temp
            print(f"🔄 下一个目标温度也设置为: {current_temp:.1f}°C")
            
        self.set_temperature(current_temp, is_cooling=False)  # 暂停保持温度不需要补偿
        
        print(f"✅ 🔄 降温已暂停，目标温度从 {self.saved_original_target:.1f}°C 更改为当前温度 {current_temp:.1f}°C")
        print("💡 系统将保持当前温度稳定，方便进行电化学测量")
        
        # 调用状态变化回调（用于WebSocket实时推送）
        if hasattr(self, 'status_change_callback') and callable(self.status_change_callback):
            try:
                self.status_change_callback('paused', f'实验已暂停，保持在 {current_temp:.1f}°C')
            except Exception as e:
                print(f"[回调错误] 状态变化回调失败: {e}")
        
        return True

    def resume_cooling(self) -> bool:
        """恢复降温控制，恢复保存的原始目标温度"""
        print(f"🔍 [调用] resume_cooling | control_active: {self.control_active} | paused: {self.paused}")
        
        if not self.control_active:
            print("❌ 温度控制未启动，无法恢复")
            return False
            
        if not self.paused:
            print("⚠️ 温度控制未暂停，无需恢复")
            return True
            
        # 恢复保存的原始目标温度
        if self.saved_original_target is not None:
            self.current_target = self.saved_original_target
            print(f"🔄 恢复原始目标温度: {self.saved_original_target:.1f}°C")
            
            # 发送恢复的目标温度到硬件端（恢复降温，需要补偿）
            self.set_temperature(self.saved_original_target, is_cooling=True)  # 恢复降温需要补偿
            print(f"📤 已向硬件发送恢复的目标温度: {self.saved_original_target:.1f}°C")
            
            # 同时更新next_target，确保控制逻辑使用正确的目标温度
            if hasattr(self, 'next_target'):
                self.next_target = self.saved_original_target
                print(f"🔄 下一个目标温度也设置为: {self.saved_original_target:.1f}°C")
        else:
            print("⚠️ 未找到保存的原始目标温度，使用最终目标温度")
            self.current_target = self.T_end
            self.set_temperature(self.T_end, is_cooling=True)  # 恢复降温需要补偿
            if hasattr(self, 'next_target'):
                self.next_target = self.T_end
                print(f"🔄 下一个目标温度设置为最终目标: {self.T_end:.1f}°C")
            
        self.paused = False
        self.pause_target_temp = None
        # 不清空保存的目标温度，保持用于后续暂停/恢复操作
        # self.saved_original_target = None
        
        print(f"✅ 🔄 降温已恢复，继续向目标温度 {self.current_target:.1f}°C 降温")
        print(f"📉 当前目标: {self.current_target}°C → 最终目标: {self.T_end}°C")
        
        # 调用状态变化回调（用于WebSocket实时推送）
        if hasattr(self, 'status_change_callback') and callable(self.status_change_callback):
            try:
                self.status_change_callback('resumed', f'实验已恢复，继续向 {self.current_target:.1f}°C 降温')
            except Exception as e:
                print(f"[回调错误] 状态变化回调失败: {e}")
        
        return True

    def is_paused(self) -> bool:
        """检查是否处于暂停状态"""
        return self.paused

    def _control_worker(self):
        """温度控制工作线程"""
        print(f"🔧 {datetime.now().strftime('%H:%M:%S')} | 控制线程 | 开始执行温度控制工作线程")
        try:
            print(f"🔧 {datetime.now().strftime('%H:%M:%S')} | 控制线程 | 准备调用 run_cooling_procedure()")
            self.run_cooling_procedure()
            print(f"✅ {datetime.now().strftime('%H:%M:%S')} | 控制线程 | run_cooling_procedure() 执行完成")
        except Exception as e:
            print(f"❌ {datetime.now().strftime('%H:%M:%S')} | 控制线程 | 温度控制错误: {e}")
            import traceback
            traceback.print_exc()
        finally:
            print(f"🔧 {datetime.now().strftime('%H:%M:%S')} | 控制线程 | 设置 control_active = False")
            self.control_active = False

    def close_serial(self):
        """关闭串口"""
        if self.ser and self.ser.is_open:
            self.ser.close()
            print("串口已关闭")
    
    def enable_log_capture(self):
        """
        启用日志捕获，将所有print输出推送到WebSocket
        """
        if self.log_callback and not self._tee_output:
            self._original_stdout = sys.stdout
            self._tee_output = TeeOutput(self._original_stdout, self.log_callback)
            sys.stdout = self._tee_output
            print("[日志捕获] ✅ 已启用，所有终端输出将推送到前端")
    
    def disable_log_capture(self):
        """
        禁用日志捕获，恢复正常stdout
        """
        if self._tee_output:
            sys.stdout = self._original_stdout
            self._tee_output = None
            print("[日志捕获] ❌ 已禁用，恢复正常输出")

    def get_status(self) -> Dict:
        """获取控制器状态"""
        return {
            'power_on': self.power_on,
            'current_temp': self.current_temp,
            'target_temp': self.current_target,
            'next_target': self.next_target,  # 添加下一个目标温度
            'control_active': self.control_active,
            'is_monitoring': self.is_monitoring,
            'measurement_count': len(self.measurement_history),
            'chi_measurement_count': self.chi_measurement_count,
            'phase_transitions': len(self.phase_transition_points),
            'paused': self.paused,
            'pause_target_temp': self.pause_target_temp,
            'chi_measuring': self.chi_measuring,
            'measurement_points': self.all_measurement_points if hasattr(self, 'all_measurement_points') else [],
            'current_measurement_index': self.current_measurement_index
        }


# ==================== 全局控制器实例 ====================
_global_controller = None

def get_global_controller() -> Optional[IntegratedTemperatureCHIController]:
    """获取全局控制器实例"""
    return _global_controller

def create_global_controller(port: str, **kwargs) -> IntegratedTemperatureCHIController:
    """创建全局控制器实例"""
    global _global_controller
    if _global_controller:
        _global_controller.close_serial()
    
    print(f"[DEBUG] 创建全局控制器，参数: {kwargs}")
    _global_controller = IntegratedTemperatureCHIController(port=port, **kwargs)
    print(f"[DEBUG] 全局控制器创建成功")
    return _global_controller


if __name__ == "__main__":
    # 配置参数
    PORT = 'COM3'           # 冰箱控制器串口号
    T_START = 18   
    T_END = -100         # 目标温度(°C)
    EPS = 0.6               # 温度误差容限(°C)
    COARSE_STEP = 3        # 粗测步长(°C)
    FINE_STEP = 3           # 精细测量步长(°C)
    THICKNESS = 0.001       # 样品厚度(m)
    AREA = 0.000196             # 样品截面积(m²)
    DATA_DIR = "experiment_data"  # 数据存储路径

    print(f"启动集成版温控CHI测量程序")
    print(f"起始温度: {T_START}°C, 目标温度: {T_END}°C")
    print(f"粗测步长: {COARSE_STEP}°C, 精细步长: {FINE_STEP}°C")
    print(f"样品参数: 厚度={THICKNESS*1000}mm, 面积={AREA*1e4}cm²")
    print(f"数据保存路径: {DATA_DIR}")
    
    try:
        # 创建控制器实例
        controller = create_global_controller(
            port=PORT,
            T_start=T_START,
            T_end=T_END,
            eps=EPS,
            coarse_step=COARSE_STEP,
            fine_step=FINE_STEP,
            thickness=THICKNESS,
            area=AREA,
            data_dir=DATA_DIR
        )
        

        
        # 启动主控制流程
        controller.run_cooling_procedure()
        
    except Exception as e:
        print(f"程序运行出错: {str(e)}")
    finally:
        # 确保程序结束时串口关闭
        if _global_controller:
            _global_controller.close_serial()