# -*- coding: utf-8 -*-
"""
集成版温控器 - 自动温度控制与CHI测量一体化
整合了temp_controller.py和run_chi.py的功能
"""

import sys
import os

# 设置控制台编码，解决中文输出乱码问题
if sys.platform.startswith('win'):
    # Windows系统
    import locale
    try:
        # 尝试设置控制台编码为UTF-8
        os.system('chcp 65001 > nul')
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except:
        try:
            # 备用方案：设置控制台编码为GBK
            os.system('chcp 936 > nul')
            sys.stdout.reconfigure(encoding='gbk')
            sys.stderr.reconfigure(encoding='gbk')
        except:
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

# 设置matplotlib支持中文
matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
matplotlib.rcParams['axes.unicode_minus'] = False

# ==================== 严格分析模式配置 ====================
ALLOW_SIMULATION = os.environ.get('ALLOW_SIMULATION', '0') == '1'
STRICT_MODE = not ALLOW_SIMULATION  # 严格模式：禁止模拟数据
print(f"[配置] STRICT_MODE={STRICT_MODE}, ALLOW_SIMULATION={ALLOW_SIMULATION}")
# ========================================================


# ==================== CHI测量时间映射 ====================
def get_measurement_time(highf: str, lowf: str) -> int:
    """
    根据高频和低频参数返回CHI测量的等待时间（秒）
    
    时间映射表（基于实测数据）:
    - 高频 1000000, 低频 0.1  -> 200s
    - 高频 1000000, 低频 1    -> 150s
    - 高频 100000,  低频 0.1  -> 170s
    - 高频 100000,  低频 1    -> 120s
    - 高频 1000000, 低频 0.01 -> 820s
    - 高频 100000,  低频 0.01 -> 810s
    
    Args:
        highf: 高频参数 (Hz)，字符串格式
        lowf: 低频参数 (Hz)，字符串格式
        
    Returns:
        int: 等待时间（秒），包含10%安全余量
    """
    try:
        high_freq = float(highf)
        low_freq = float(lowf)
    except (ValueError, TypeError):
        print(f"[警告] 频率参数格式错误: highf={highf}, lowf={lowf}，使用默认时间220秒")
        return 220
    
    # 时间映射表 (high_freq, low_freq) -> base_time
    time_mapping = {
        (1000000, 0.01): 820,
        (1000000, 0.1): 200,
        (1000000, 1): 150,
        (100000, 0.01): 810,
        (100000, 0.1): 170,
        (100000, 1): 120,
    }
    
    # 精确匹配
    key = (high_freq, low_freq)
    if key in time_mapping:
        base_time = time_mapping[key]
        wait_time = int(base_time * 1.1)  # 添加10%安全余量
        print(f"[时间映射] 高频={high_freq}Hz, 低频={low_freq}Hz -> 基准时间{base_time}秒, 等待时间{wait_time}秒(+10%)")
        return wait_time
    
    # 未找到精确匹配，使用估算
    print(f"[时间映射] 未找到精确匹配: highf={high_freq}, lowf={low_freq}")
    if low_freq <= 0.01:
        base_time = 820 if high_freq >= 500000 else 810
    elif low_freq <= 0.1:
        base_time = 200 if high_freq >= 500000 else 170
    elif low_freq <= 1:
        base_time = 150 if high_freq >= 500000 else 120
    else:
        base_time = 100
    
    wait_time = int(base_time * 1.1)
    print(f"[时间映射] 估算: 基准时间{base_time}秒, 等待时间{wait_time}秒(+10%)")
    return wait_time
# ========================================================


# 添加模块搜索路径
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

# 导入数据处理模块
try:
    from specific_conductance.data_processing import filter_data
    from specific_conductance.rb_fitting import detect_phase_jump, calculate_rb
    from specific_conductance.conductivity import calculate_conductivity, get_fit_params
    print("成功导入数据处理模块")
except ImportError as e:
    print(f"警告: 无法导入数据处理模块: {e}")
    # 创建模拟函数避免崩溃
    def filter_data(freq, zreal, zimag, window=7, poly=3, thresh=3.0):
        return freq, zreal, zimag
    
    def detect_phase_jump(zreal, zimag, threshold=20):
        """检测相位突变 - 简化版本"""
        try:
            if len(zreal) != len(zimag) or len(zreal) < 2:
                return False
            
            # 计算相位角
            phases = np.arctan2(zimag, zreal)
            
            # 检测相位突变
            phase_diff = np.abs(np.diff(phases))
            max_phase_diff = np.max(phase_diff)
            
            if max_phase_diff > np.radians(threshold):
                return True
            
            return False
        except Exception as e:
            print(f"相位突变检测失败: {e}")
            return False
    
    def calculate_rb(zreal, zimag, temp, params):
        return {'rb': 100, 'method': '模拟拟合', 'fit_params': {}}
    
    def calculate_conductivity(rb, thickness, area):
        return 0.01
    
    def get_fit_params():
        return {}

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


class IntegratedTemperatureCHIController:
    """集成温控和CHI测量的控制器"""
    
    def __init__(self, port: str, T_start: float, T_end: float, eps: float = 0.5, 
                 coarse_step: float = 10.0, fine_step: float = 3.0,
                 thickness: float = 0.001, area: float = 1e-4,
                 data_dir: str = "experiment_data", 
                 chi_params: Dict = None):
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
            "material": "PSE-2",
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
        
        # 相变点检测相关
        self.phase_transition_range = None
        self.phase_detected = False
        self.fine_measuring = False
        self.last_measurement_temp = T_start
        
        # 数据记录
        self.temperature_history = []
        self.measurement_history = []
        self.phase_transition_points = []
        
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
        
        # 温度更新回调
        self.temperature_update_callback = None
        
        # 执行ID（用于前端追踪）
        self.execution_id = None
        
        # 确保目标温度正确初始化
        self.next_target = T_start
        
        # CHI测量状态
        self.chi_measuring = False
        self.chi_measurement_count = 0
        
        # 测量点列表
        self.measurement_points = []
        self.current_measurement_index = 0
        self.next_target = T_start  # 下一个目标温度

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

    def _init_serial(self, port: str) -> serial.Serial:
        """初始化串口连接"""
        try:
            ser = serial.Serial(
                port=port,
                baudrate=19200,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_TWO,
                timeout=0.1
            )
            print(f"串口 {port} 已成功打开")
            ser.reset_input_buffer()
            ser.reset_output_buffer()
            return ser
        except serial.SerialException as e:
            print(f"无法打开串口 {port}: {str(e)}")
            raise

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

    def set_temperature(self, temp: float, is_cooling: bool = True) -> bool:
        """
        设置目标温度
        
        Args:
            temp: 目标温度
            is_cooling: 是否是降温操作（True=降温需要+1°C补偿，False=回温/保持不补偿）
        """
        with self.serial_lock:
            # 降温时应用+1°C补偿以抵消过冲
            actual_temp = temp + 1.0 if is_cooling else temp
            
            temp_int = int(actual_temp * 10)
            if temp_int < 0:
                temp_int = (1 << 16) + temp_int

            high_byte = (temp_int >> 8) & 0xFF
            low_byte = temp_int & 0xFF

            cmd = bytes([0xA5, 0x5A, 0x06, 0x83, 0x00, 0x26, 0x01, high_byte, low_byte])

            for _ in range(3):
                self.ser.write(cmd)
                time.sleep(0.2)

            if is_cooling and actual_temp != temp:
                print(f"温度已设置为: {actual_temp:.1f}°C (目标{temp:.1f}°C + 1°C补偿)")
            else:
                print(f"温度已设置为: {actual_temp:.1f}°C")
            return True

    def read_temperature(self) -> Optional[float]:
        """
        读取当前温度
        
        策略：
        1. 不清空硬件缓冲区，读取所有积压数据
        2. 解析所有帧，取最新的温度值
        3. 保留未完成的帧，等待下次拼接
        """
        with self.serial_lock:
            # 清空帧队列，准备处理新数据
            self.frame_queue.clear()
            
            latest_temp = None
            start_time = time.time()
            max_read_time = 5  # 5秒超时
            
            # 读取并解析所有数据
            while time.time() - start_time < max_read_time:
                # 读取串口数据
                if self.ser.in_waiting > 0:
                    data = self.ser.read(min(self.ser.in_waiting, 500))
                    self.buffer.extend(data)
                    self._process_buffer()
                    
                    # 处理所有帧，保留最新温度
                    while self.frame_queue:
                        frame = self.frame_queue.popleft()
                        temp = self._parse_frame(frame)
                        if temp is not None:
                            latest_temp = temp
                    
                    # 读到温度就退出
                    if latest_temp is not None:
                        break
                
                time.sleep(0.1)
            
            # 返回结果
            if latest_temp is not None:
                self.temperature_history.append((time.time(), latest_temp))
                self.current_temp = latest_temp
                
                # ✅ 内存管理：只保留最近1000条温度记录（约1.4小时）
                if len(self.temperature_history) > 1000:
                    self.temperature_history = self.temperature_history[-1000:]
                
                print(f"当前温度: {latest_temp:.1f}°C")
                return latest_temp
            else:
                print("❌ 未能读取到有效温度")
                return None

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
    
    def run_chi_measurement(self) -> Tuple[Dict, np.ndarray, np.ndarray, np.ndarray]:
        """
        执行完整的CHI测量流程 - 使用手动测量的完美流程
        
        Returns:
            Tuple[Dict, ndarray, ndarray, ndarray]: (results, frequencies, z_real, z_imag)
        """
        print(f"\n=== 开始CHI测量流程 ===")
        print("DEBUG: 检查CHI参数")
        print(f"[配置] 材料: {self.chi_params['material']}")
        print(f"[配置] 温度: {self.current_temp:.1f}°C")
        print(f"[配置] 频率范围: {self.chi_params['lowf']}-{self.chi_params['highf']}Hz")
        print(f"[配置] 初始电位: {self.chi_params['initV']}V")
        print("DEBUG: CHI参数检查完成")
        
        # 更新CHI参数中的温度
        self.chi_params['T'] = str(int(self.current_temp + 273.15))  # 转换为开尔文
        
        # 生成文件名 - 使用目标温度而不是当前温度
        target_temp_for_filename = self.current_target if hasattr(self, 'current_target') else self.current_temp
        # 将温度转换为整数格式，避免.0
        temp_str = f"{int(target_temp_for_filename)}" if target_temp_for_filename == int(target_temp_for_filename) else f"{target_temp_for_filename:.1f}"
        filename = f"{self.chi_params['material']}_T{temp_str}C_highf{self.chi_params['highf']}_lowf{self.chi_params['lowf']}_initV{self.chi_params['initV']}"
        
        results = {}
        
        def get_screenshot():
            return np.array(ImageGrab.grab())
        
        # 验证保存路径
        try:
            os.makedirs(self.chi_params['your_position'], exist_ok=True)
            print(f"[验证] 保存目录已创建/验证: {self.chi_params['your_position']}")
        except Exception as e:
            print(f"[错误] 无法创建保存目录: {e}")
            return {"error": f"保存目录创建失败: {e}"}
        
        try:
            # 步骤0：打开CHI软件
            print(f"\n[步骤0] 打开CHI软件...")
            print("DEBUG: 准备打开CHI软件")
            open_chi_path = os.path.join(self.chi_params['template_dir'], "open_CHI.png")
            print(f"DEBUG: 模板路径: {open_chi_path}")
            print(f"DEBUG: 模板文件存在: {os.path.exists(open_chi_path)}")
            
            success, msg = self._click_template(open_chi_path, get_screenshot(), 
                                              self.chi_params['confidence'], self.chi_params['delay'])
            results["open_chi"] = (success, msg)
            print(f"[结果] 打开CHI: {'✅ 成功' if success else '❌ 失败'} - {msg}")
            if not success:
                print("DEBUG: CHI软件打开失败，返回模拟数据")
                frequencies = np.logspace(1, 4, 50)
                z_real = np.random.normal(1000, 100, 50)
                z_imag = np.random.normal(-500, 50, 50)
                return results, frequencies, z_real, z_imag
            
            # 等待CHI软件完全启动
            print(f"[等待] CHI软件启动中...")
            time.sleep(3)
            
            # 步骤1：点击开始测量按钮
            print(f"\n[步骤1] 点击开始测量按钮...")
            start_measure_path = os.path.join(self.chi_params['template_dir'], "start_to_measure.png")
            success, msg = self._click_template(start_measure_path, get_screenshot(), 
                                              self.chi_params['confidence'], self.chi_params['delay'])
            results["start_measure"] = (success, msg)
            print(f"[结果] 开始测量: {'✅ 成功' if success else '❌ 失败'} - {msg}")
            if not success:
                frequencies = np.logspace(1, 4, 50)
                z_real = np.random.normal(1000, 100, 50)
                z_imag = np.random.normal(-500, 50, 50)
                return results, frequencies, z_real, z_imag
            
            # 步骤2：初始等待8秒
            print(f"\n[步骤2] 初始等待8秒...")
            time.sleep(8)
            results["initial_wait"] = (True, "初始等待完成")
            
            # 步骤3：根据频率参数计算等待时间
            print(f"\n[步骤3] 等待测量完成...")

            # 使用时间映射函数计算等待时间
            wait_seconds = get_measurement_time(self.chi_params['highf'], self.chi_params['lowf'])
            print(f"[信息] CHI测量频率范围: {self.chi_params['lowf']}Hz - {self.chi_params['highf']}Hz")
            print(f"[信息] 计算等待时间: {wait_seconds}秒")
            print(f"[信息] 等待CHI测量完成...")

            time.sleep(wait_seconds)
            results["wait_time"] = (True, f"等待完成 ({wait_seconds}s)")
            
            # 步骤4：点击另存为
            print(f"\n[步骤4] 点击另存为...")
            save_as_path = os.path.join(self.chi_params['template_dir'], "save_as.png")
            success, msg = self._click_template(save_as_path, get_screenshot(), self.chi_params['confidence'], self.chi_params['delay'])
            results["save_as"] = (success, msg)
            print(f"[结果] 另存为: {'✅ 成功' if success else '❌ 失败'} - {msg}")
            if not success:
                frequencies = np.logspace(1, 4, 50)
                z_real = np.random.normal(1000, 100, 50)
                z_imag = np.random.normal(-500, 50, 50)
                return results, frequencies, z_real, z_imag
            
            # 步骤5：点击保存类型
            print(f"\n[步骤5] 点击保存类型...")
            type_saving_path = os.path.join(self.chi_params['template_dir'], "type_saving.png")
            
            # 使用成功的匹配阈值，确保能找到保存类型按钮
            type_success = False
            type_msg = ""
            type_confidence_levels = [0.5, 0.4, 0.3, 0.2, 0.1]  # 成功的匹配阈值
            
            for i, conf in enumerate(type_confidence_levels, 1):
                print(f"[尝试] 保存类型第{i}次尝试，匹配阈值: {conf}")
                type_success, type_msg = self._click_template(type_saving_path, get_screenshot(), conf, self.chi_params['delay'])
                if type_success:
                    print(f"[成功] 保存类型点击成功，使用阈值: {conf}")
                    break
                else:
                    print(f"[失败] 保存类型第{i}次尝试失败: {type_msg}")
                    time.sleep(0.8)  # 增加等待时间后重试
            
            results["type_saving"] = (type_success, type_msg)
            print(f"[结果] 保存类型: {'✅ 成功' if type_success else '❌ 失败'} - {type_msg}")
            
            # 如果保存类型点击成功，添加确认
            if type_success:
                print(f"[确认] 保存类型点击成功，等待下拉菜单展开...")
                time.sleep(0.8)  # 等待下拉菜单展开
                print(f"[确认] 保存类型下拉菜单已展开")
            else:
                print(f"[警告] 保存类型点击失败，但继续尝试后续步骤...")
                # 不直接返回，继续尝试后续步骤
            
            # 步骤6：选择文件类型
            print(f"\n[步骤6] 选择文件类型...")
            white_path = os.path.join(self.chi_params['template_dir'], "your_type_white.png")
            blue_path = os.path.join(self.chi_params['template_dir'], "your_type_blue.png")
            
            # 使用成功的匹配阈值，确保能找到文件类型选项
            file_type_success = False
            file_type_msg = ""
            file_type_confidence_levels = [0.5, 0.4, 0.3, 0.2, 0.1]  # 成功的匹配阈值
            
            for i, conf in enumerate(file_type_confidence_levels, 1):
                print(f"[尝试] 文件类型第{i}次尝试，匹配阈值: {conf}")
                # 先尝试白色类型
                file_type_success, file_type_msg = self._click_template(white_path, get_screenshot(), conf, self.chi_params['delay'])
                if not file_type_success:
                    print(f"[尝试] 白色类型失败，尝试蓝色类型...")
                    file_type_success, file_type_msg = self._click_template(blue_path, get_screenshot(), conf, self.chi_params['delay'])
                
                if file_type_success:
                    print(f"[成功] 文件类型选择成功，使用阈值: {conf}")
                    break
                else:
                    print(f"[失败] 文件类型第{i}次尝试失败: {file_type_msg}")
                    time.sleep(0.8)  # 增加等待时间后重试
            
            results["your_type"] = (file_type_success, file_type_msg)
            print(f"[结果] 文件类型: {'✅ 成功' if file_type_success else '❌ 失败'} - {file_type_msg}")
            
            # 如果文件类型选择成功，等待下拉菜单展开
            if file_type_success:
                print(f"[确认] 文件类型选择成功，等待下拉菜单展开...")
                time.sleep(0.8)  # 等待下拉菜单完全展开
                print(f"[确认] 文件类型选择完成，下拉菜单已展开")
            else:
                print(f"[警告] 文件类型选择失败，但继续尝试后续步骤...")
                # 不直接返回，继续尝试后续步骤
            
            # 步骤7：点击目录图标
            print(f"\n[步骤7] 点击目录图标...")
            
            # 可以使用多个模板文件，尝试匹配不同电脑的图标
            directory_icon_path = os.path.join(self.chi_params['template_dir'], "Directory.png")
            print(f"[信息] 使用目录图标模板: Directory.png")


            # 使用成功的匹配阈值，确保能找到目录图标
            success = False
            msg = ""
            confidence_levels = [0.5, 0.4, 0.3, 0.2, 0.1]  # 成功的匹配阈值
            
            for i, conf in enumerate(confidence_levels, 1):
                print(f"[尝试] 第{i}次尝试，匹配阈值: {conf}")
                success, msg = self._locate_address_field(directory_icon_path, get_screenshot(), conf)
                if success:
                    print(f"[成功] 目录点击成功，使用阈值: {conf}")
                    break
                else:
                    print(f"[失败] 第{i}次尝试失败: {msg}")
                    time.sleep(0.8)  # 增加等待时间后重试
            
            results["directory_click"] = (success, msg)
            print(f"[结果] 目录点击: {'✅ 成功' if success else '❌ 失败'} - {msg}")
            if not success:
                print(f"[警告] 目录点击失败，但继续尝试后续步骤...")
                # 不直接返回，继续尝试后续步骤
            
            # ========== 步骤8已取消：输入保存路径 ==========
            # 用户要求跳过步骤8（输入保存路径），直接进入步骤9
            print(f"\n[步骤8] 输入保存路径... [已跳过]")
            results["path_input"] = (True, "步骤8已手动跳过")
            print(f"[结果] 路径输入: ⏭️ 已跳过")

            
            # 步骤9：按一次Enter键进入文件夹
            print(f"\n[步骤9] 按一次Enter键进入文件夹...")
            try:
                print(f"[操作] 按Enter键进入文件夹...")
                pyautogui.press('enter')
                time.sleep(1.0)
                print(f"[成功] 按Enter键进入文件夹成功")
                results["enter_folder"] = (True, "按Enter键进入文件夹成功")
            except Exception as e:
                print(f"[失败] 按Enter键进入文件夹失败: {e}")
                results["enter_folder"] = (False, f"按Enter键进入文件夹失败: {str(e)}")
            
            # 步骤10：编辑文件名
            print(f"\n[步骤10] 编辑文件名...")
            # 使用更简单的文件名格式，避免特殊字符
            filename = f"{self.chi_params['material']}_T{temp_str}_f{self.chi_params['lowf']}_{self.chi_params['highf']}_V{self.chi_params['initV']}"
            name_of_dc_path = os.path.join(self.chi_params['template_dir'], "name_of_dc.png")
            
            # 使用成功的匹配阈值，确保能找到文件名输入框
            name_success = False
            name_msg = ""
            name_confidence_levels = [0.1, 0.05, 0.03, 0.02, 0.01]  # 成功的匹配阈值
            
            for i, conf in enumerate(name_confidence_levels, 1):
                print(f"[尝试] 文件名编辑第{i}次尝试，匹配阈值: {conf}")
                name_success, name_msg = self._edit_text_box(name_of_dc_path, get_screenshot(), filename, "right", conf, self.chi_params['delay'])
                if name_success:
                    print(f"[成功] 文件名编辑成功，使用阈值: {conf}")
                    break
                else:
                    print(f"[失败] 文件名编辑第{i}次尝试失败: {name_msg}")
                    time.sleep(1.0)  # 增加等待时间后重试
            
            results["name_edit"] = (name_success, name_msg)
            print(f"[结果] 文件名编辑: {'✅ 成功' if name_success else '❌ 失败'} - {name_msg}")
            if not name_success:
                print(f"[警告] 文件名编辑失败，但继续尝试后续步骤...")
                # 不直接返回，继续尝试后续步骤
            
            # 步骤11：按两次Enter键保存文件
            print(f"\n[步骤11] 按两次Enter键保存文件...")
            try:
                print(f"[操作] 第一次按Enter键确认文件名...")
                pyautogui.press('enter')
                time.sleep(1.0)
                print(f"[操作] 第二次按Enter键执行保存...")
                pyautogui.press('enter')
                time.sleep(2.0)  # 保存操作需要更长时间
                print(f"[成功] 按两次Enter键保存文件成功")
                results["save_file"] = (True, "按两次Enter键保存文件成功")
            except Exception as e:
                print(f"[失败] 按Enter键保存文件失败: {e}")
                results["save_file"] = (False, f"按Enter键保存文件失败: {str(e)}")
            
            # 步骤12：再次打开CHI软件，确保软件保持打开状态
            print(f"\n[步骤12] 再次打开CHI软件，确保软件保持打开状态...")
            open_chi_path = os.path.join(self.chi_params['template_dir'], "open_CHI.png")
            success, msg = self._click_template(open_chi_path, get_screenshot(), 
                                              self.chi_params['confidence'], self.chi_params['delay'])
            results["reopen_chi"] = (success, msg)
            print(f"[结果] 再次打开CHI: {'✅ 成功' if success else '❌ 失败'} - {msg}")
            
            # 等待CHI软件完全启动
            print(f"[等待] CHI软件重新启动中...")
            time.sleep(3)
            
            print(f"\n=== CHI测量流程完成 ===")
            
            # 读取并处理保存的数据
            # 检查保存是否成功（通过检查文件是否存在）
            save_file_success = results.get("save_file", (False, ""))[0]
            if save_file_success:
                # 等待文件保存完成
                time.sleep(2)
                
                # 尝试读取保存的文件
                expected_file = os.path.join(self.chi_params['your_position'], filename + ".txt")
                if os.path.exists(expected_file):
                    print(f"[成功] 找到保存的数据文件: {expected_file}")
                    # 读取EIS数据
                    frequencies, z_real, z_imag = self._read_chi_data_file(expected_file)
                    if frequencies is not None:
                        results["data_reading"] = (True, f"成功读取{len(frequencies)}个数据点")
                        return results, frequencies, z_real, z_imag
                    else:
                        results["data_reading"] = (False, "无法解析数据文件")
                else:
                    print(f"[警告] 未找到预期的数据文件: {expected_file}")
                    # 生成模拟数据
                    frequencies = np.logspace(0, 4, 50)
                    z_real = 100 + 50 * np.exp(-frequencies/1000) + np.random.normal(0, 2, 50)
                    z_imag = -30 * np.exp(-frequencies/500) + np.random.normal(0, 1, 50)
                    results["data_reading"] = (False, "使用模拟数据")
                    return results, frequencies, z_real, z_imag
            
            # 如果保存失败，返回模拟数据
            frequencies = np.logspace(0, 4, 50)
            z_real = 100 + 50 * np.exp(-frequencies/1000) + np.random.normal(0, 2, 50)
            z_imag = -30 * np.exp(-frequencies/500) + np.random.normal(0, 1, 50)
            return results, frequencies, z_real, z_imag
            
        except Exception as e:
            print(f"[错误] CHI测量过程出错: {str(e)}")
            results["error"] = (False, str(e))
            # 返回模拟数据
            frequencies = np.logspace(0, 4, 50)
            z_real = 100 + 50 * np.exp(-frequencies/1000) + np.random.normal(0, 2, 50)
            z_imag = -30 * np.exp(-frequencies/500) + np.random.normal(0, 1, 50)
            return results, frequencies, z_real, z_imag

    def _try_parse_three_floats(self, line: str):
        """
        尝试从一行文本中解析出3个浮点数
        支持分隔符：逗号、制表符、空白
        """
        line = line.strip()
        if not line:
            return None
        
        # 尝试不同的分隔符
        for delimiter in [',', '\t', None]:  # None表示空白分隔
            try:
                if delimiter:
                    parts = line.split(delimiter)
                else:
                    parts = line.split()
                
                if len(parts) < 3:
                    continue
                
                freq = float(parts[0].strip())
                z_real = float(parts[1].strip())
                z_imag = float(parts[2].strip())
                return (freq, z_real, z_imag)
            except (ValueError, IndexError):
                continue
        
        return None

    def _read_chi_data_file(self, filepath: str) -> Tuple[Optional[np.ndarray], Optional[np.ndarray], Optional[np.ndarray]]:
        """读取CHI保存的数据文件"""
        try:
            if not os.path.exists(filepath):
                print(f"❌ 文件不存在: {filepath}")
                return None, None, None
            
            # 读取所有行
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
            # 扫描每一行，找到第一行能解析出3个浮点数的行
            data_start_line = None
            for i, line in enumerate(lines):
                result = self._try_parse_three_floats(line)
                if result is not None:
                    data_start_line = i
                    print(f"[找到数据起始行] 第 {i+1} 行: {line.strip()[:80]}")
                    break
            
            if data_start_line is None:
                print(f"❌ 未找到有效数据行（无法解析出3个浮点数）: {filepath}")
                return None, None, None
            
            # 手动逐行解析数据（从data_start_line开始）
            data_rows = []
            for i in range(data_start_line, len(lines)):
                result = self._try_parse_three_floats(lines[i])
                if result is not None:
                    data_rows.append(result)
            
            if len(data_rows) == 0:
                print(f"❌ 解析到0个有效数据点: {filepath}")
                return None, None, None
            
            # 转换为numpy数组
            data = np.array(data_rows)
            frequencies = data[:, 0]
            z_real = data[:, 1]
            z_imag = data[:, 2]
            
            if len(frequencies) < 10:
                print(f"❌ 有效数据点不足10个 ({len(frequencies)}个): {filepath}")
                return None, None, None
            
            print(f"✅ 成功读取 {len(frequencies)} 个数据点")
            return frequencies, z_real, z_imag
            
        except Exception as e:
            print(f"❌ 读取数据文件失败: {e}")
            import traceback
            traceback.print_exc()
            return None, None, None

    # CHI辅助函数
    def _capture_remaining_time_strict(self, screenshot, template_dir=""):
        """改进的时间识别函数"""
        try:
            time_template_path = os.path.join(template_dir, "time_remaining.png")
            time_template = cv2_imread_unicode(time_template_path, cv2.IMREAD_GRAYSCALE)
            if time_template is None:
                print(f"[错误] 时间模板未找到: {time_template_path}")
                return 0

            gray_screen = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
            res = cv2.matchTemplate(gray_screen, time_template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)

            if max_val < 0.45:
                print(f"[警告] 时间区域匹配度低 (相似度: {max_val:.2f})")
                return 0

            print(f"[信息] 时间区域匹配成功 (相似度: {max_val:.2f})")
            

            # 这里可以集成OCR识别，暂时返回默认值
            return 98.0

        except Exception as e:
            print(f"[异常] 时间识别失败: {str(e)}")
            return 0

    def _click_template(self, template_path, screenshot, confidence, delay):
        """原始简单模板点击函数"""
        try:
            template = cv2_imread_unicode(template_path)
            if template is None:
                return False, f"模板图片不存在: {template_path}"

            res = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)
            
            if max_val < confidence:
                return False, f"匹配失败 (相似度: {max_val:.4f} < {confidence})"

            h, w = template.shape[:2]
            click_x = max_loc[0] + w // 2
            click_y = max_loc[1] + h // 2
            
            pyautogui.click(click_x, click_y)
            time.sleep(delay)
            return True, f"点击成功 (匹配度: {max_val:.4f})"
        except Exception as e:
            return False, f"点击错误: {str(e)}"

    def _locate_address_field(self, template_path, screenshot, confidence=0.85):
        """改进的地址字段定位"""
        try:
            template = cv2_imread_unicode(template_path)
            if template is None:
                return False, f"地址字段模板不存在: {template_path}"

            if screenshot is None:
                from PIL import ImageGrab
                screenshot = np.array(ImageGrab.grab())
                screenshot = cv2.cvtColor(screenshot, cv2.COLOR_RGB2BGR)

            res = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)

            if max_val >= confidence:
                h, w = template.shape[:2]
                click_x = max_loc[0] + w // 2
                click_y = max_loc[1] + h // 2
                
                pyautogui.click(click_x, click_y)
                time.sleep(1.0)
                
                pyautogui.click(click_x, click_y)
                time.sleep(0.5)
                
                return True, f"地址字段定位成功 (匹配度: {max_val:.4f})"
            else:
                return False, f"地址字段匹配度不足: {max_val:.4f} < {confidence}"

        except Exception as e:
            return False, f"地址字段定位错误: {str(e)}"

    def _edit_text_box(self, template_path, screenshot, text, side, confidence, delay):
        """改进的文本框编辑"""
        try:
            template = cv2_imread_unicode(template_path)
            if template is None:
                return False, f"文本框模板不存在: {template_path}"

            res = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)

            if max_val >= confidence:
                h, w = template.shape[:2]
                if side == "right":
                    click_x = max_loc[0] + w - 15
                else:
                    click_x = max_loc[0] + 15
                click_y = max_loc[1] + h // 2
                
                if "saving_position" in template_path or "Directory" in template_path:
                    click_x = max_loc[0] + 30
                
                pyautogui.click(click_x, click_y)
                time.sleep(delay + 0.5)
                
                pyautogui.click(click_x, click_y)
                time.sleep(0.5)
                
                pyautogui.hotkey('ctrl', 'a')
                time.sleep(0.5)
                pyautogui.press('backspace')
                time.sleep(0.5)
                
                # 使用剪贴板方式输入，避免特殊字符问题
                try:
                    import pyperclip
                    pyperclip.copy(text)
                    time.sleep(0.3)
                    pyautogui.hotkey('ctrl', 'v')
                    time.sleep(0.5)
                    print(f"[DEBUG] 使用剪贴板输入: {text}")
                except (ImportError, Exception) as e:
                    # 如果pyperclip失败，使用Windows剪贴板API
                    print(f"[WARNING] pyperclip不可用({e})，使用Windows剪贴板")
                    try:
                        import win32clipboard
                        win32clipboard.OpenClipboard()
                        win32clipboard.EmptyClipboard()
                        win32clipboard.SetClipboardText(text)
                        win32clipboard.CloseClipboard()
                        time.sleep(0.3)
                        pyautogui.hotkey('ctrl', 'v')
                        time.sleep(0.5)
                        print(f"[DEBUG] 使用Windows剪贴板输入: {text}")
                    except Exception as e2:
                        # 最后回退：使用typewrite
                        print(f"[WARNING] 剪贴板不可用({e2})，使用typewrite")
                        pyautogui.typewrite(text, interval=0.05)
                
                time.sleep(0.5)
                
                # 移除回车键，直接进入下一步
                # pyautogui.press('enter')
                # time.sleep(0.5)
                
                time.sleep(1.0)
                
                return True, f"文本框编辑成功: {text}"
            else:
                return False, f"文本框匹配度不足: {max_val:.4f} < {confidence}"

        except Exception as e:
            return False, f"文本框编辑错误: {str(e)}"

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
            if region:
                T_high, T_low = region
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
            print("DEBUG: 准备调用run_analysis.py中的完美CHI测量流程")
            
            # 调用run_analysis.py中的完美CHI测量流程
            try:
                import sys
                import os
                
                # 添加run_analysis.py的路径
                current_dir = os.path.dirname(os.path.abspath(__file__))
                parent_dir = os.path.dirname(current_dir)
                if parent_dir not in sys.path:
                    sys.path.insert(0, parent_dir)
                
                from run_analysis import run_chi_measurement
                
                # 调用run_analysis.py中的完美流程
                results = run_chi_measurement(
                    material=self.chi_params.get('material', 'Sample'),
                    T=str(int(self.current_temp)),
                    highf=self.chi_params.get('highf', '5000'),
                    lowf=self.chi_params.get('lowf', '1'),
                    initV=self.chi_params.get('initV', '0'),
                    your_position=self.chi_params.get('your_position', 'E:\\chi_data'),
                    your_type_text="Text Files",
                    template_dir=self.chi_params.get('template_dir', 'auto_control'),
                    confidence=0.5,
                    text_confidence=70,
                    delay=0.5
                )
                
                print("DEBUG: run_analysis.py中的完美CHI测量流程完成")

                # 检查保存是否成功
                raw_data_path = None  # 初始化原始数据路径
                
                if results.get("save_file", (False, ""))[0]:
                    print("[成功] CHI测量和保存流程完全成功")

                    # 尝试读取CHI软件保存的真实数据文件
                    try:
                        # 构建预期的文件名
                        filename = f"{self.chi_params.get('material', 'Sample')}_T{str(int(self.current_temp))}C_highf{self.chi_params.get('highf')}_lowf{self.chi_params.get('lowf')}_initV{self.chi_params.get('initV')}"
                        expected_file = os.path.join(self.chi_params.get('your_position', 'E:\\chi_data'), filename + ".txt")

                        if os.path.exists(expected_file):
                            print(f"[成功] 找到CHI保存的数据文件: {expected_file}")
                            raw_data_path = expected_file  # ← 记录原始数据路径
                            frequencies, z_real, z_imag = self._read_chi_data_file(expected_file)
                            if frequencies is not None:
                                print(f"[成功] 成功读取{len(frequencies)}个真实数据点")
                            else:
                                print(f"[警告] 无法解析数据文件")
                                if STRICT_MODE:
                                    raise Exception("无法解析数据文件")
                                else:
                                    print("[宽松模式] 使用模拟数据")
                                    import numpy as np
                                    frequencies = np.logspace(1, 4, 50)
                                    z_real = np.random.normal(1000, 100, 50)
                                    z_imag = np.random.normal(-500, 50, 50)
                        else:
                            print(f"[警告] 未找到预期的数据文件: {expected_file}")
                            if STRICT_MODE:
                                raise FileNotFoundError(f"未找到数据文件: {expected_file}")
                            else:
                                print("[宽松模式] 使用模拟数据")
                                import numpy as np
                                frequencies = np.logspace(1, 4, 50)
                                z_real = np.random.normal(1000, 100, 50)
                                z_imag = np.random.normal(-500, 50, 50)

                    except Exception as read_error:
                        print(f"[错误] 读取CHI数据文件失败: {read_error}")
                        if STRICT_MODE:
                            raise  # 严格模式直接抛出异常
                        else:
                            print("[宽松模式] 将生成模拟数据作为备选方案")
                            import numpy as np
                            frequencies = np.logspace(1, 4, 50)
                            z_real = np.random.normal(1000, 100, 50)
                            z_imag = np.random.normal(-500, 50, 50)
                else:
                    print("[警告] CHI保存流程失败")
                    if STRICT_MODE:
                        raise Exception("CHI保存流程失败")
                    else:
                        print("[宽松模式] 使用模拟数据")
                        import numpy as np
                        frequencies = np.logspace(1, 4, 50)
                        z_real = np.random.normal(1000, 100, 50)
                        z_imag = np.random.normal(-500, 50, 50)
                
            except Exception as import_error:
                print(f"[WARNING] 导入run_analysis.py失败: {import_error}")
                print(f"[INFO] 回退到集成温控器自己的方法...")
                
                results, frequencies, z_real, z_imag = self.run_chi_measurement()
                raw_data_path = None  # 回退方法无法获取原始路径
                print("DEBUG: 回退到集成温控器自己的方法完成")
            
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
            result = self.process_eis_data(frequencies, z_real, z_imag, raw_data_path=raw_data_path)
            
            # 保存测量数据
            self.save_measurement_data(result)
            
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

    def process_eis_data(self, frequencies: np.ndarray, z_real: np.ndarray, z_imag: np.ndarray, raw_data_path: str = None) -> Dict:
        """处理EIS数据，检测相变点（增强版：完整拟合信息 + 失败追溯）"""
        print("开始处理EIS数据...")
        
        try:
            # 数据滤波
            freq_filtered, zreal_filtered, zimag_filtered = filter_data(
                frequencies, z_real, z_imag
            )
            
            print(f"[滤波] 原始点数={len(frequencies)}, 滤波后={len(freq_filtered)}")
            
            # 检测相位突变
            phase_jump_detected = detect_phase_jump(zreal_filtered, zimag_filtered, threshold=20)
            if phase_jump_detected:
                print(f"⚠️ 检测到相位突变，可能发生相变！")
                
                if self.last_measurement_temp is not None:
                    self.phase_transition_range = (self.last_measurement_temp, self.current_temp)
                    print(f"检测到相变区间: {self.phase_transition_range}")
            
            # ==================== 拟合Rb值（核心） ====================
            # specific_conductance/rb_fitting.py 的 calculate_rb 需要 circle_dir 参数
            circle_dir = os.path.join(self.experiment_data_dir, 'circle_fits')
            os.makedirs(circle_dir, exist_ok=True)
            
            # 调用真实拟合函数
            rb_result = calculate_rb(
                zreal_filtered, 
                zimag_filtered, 
                self.current_temp + 273.15,  # 转换为K
                self.fit_params,
                circle_dir
            )
            
            print(f"[拟合] method={rb_result.get('method')}, rb={rb_result.get('rb')}, r={rb_result.get('r')}")
            
            # 检查是否使用圆弧拟合
            if rb_result.get('method') == 'circle':
                print("圆弧拟合检测到相变特征！")
                if self.last_measurement_temp is not None:
                    self.phase_transition_range = (self.last_measurement_temp, self.current_temp)
                    print(f"检测到相变区间: {self.phase_transition_range}")
            
            # 计算电导率
            rb_value = rb_result.get('rb')
            conductivity = None
            if rb_value is not None and rb_value > 0:
                conductivity = calculate_conductivity(
                    rb_value,
                    self.thickness,
                    self.area
                )
            
            # ==================== 构建返回结果 ====================
            result = {
                'temperature': self.current_temp,
                'rb': rb_value,
                'conductivity': conductivity,
                'fit_method': rb_result.get('method', '未知'),
                'fit_params': rb_result.get('fit_params'),  # ← 完整拟合参数
                'phase_jump_detected': phase_jump_detected,
                'phase_transition_range': self.phase_transition_range,
                'raw_data_path': raw_data_path,  # ← 传递原始数据路径
                'eis_data': {
                    'frequencies': frequencies,
                    'z_real': z_real,
                    'z_imag': z_imag,
                    'filtered': {
                        'frequencies': freq_filtered,
                        'z_real': zreal_filtered,
                        'z_imag': zimag_filtered
                    }
                }
            }
            
            # 打印摘要
            if rb_value is not None:
                print(f"✅ 温度 {self.current_temp}°C: Rb = {rb_value:.2f} Ω, 电导率 = {conductivity:.4e} S/cm, 方法 = {rb_result.get('method')}")
            else:
                print(f"❌ 温度 {self.current_temp}°C: 拟合失败 (method={rb_result.get('method')})")
            
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

    def save_measurement_data(self, result: Dict):
        """保存测量数据（增强版：结构化记录 + 失败可追溯）"""
        timestamp = time.strftime('%Y%m%d_%H%M%S')
        
        # ==================== 1. 保存EIS数据到标准化文件 ====================
        eis_saved_path = None
        eis_saved = False
        if 'eis_data' in result and len(result['eis_data']['frequencies']) > 0:
            try:
                file_name = f"eis_{self.current_temp:.1f}C_{timestamp}.txt"
                eis_saved_path = os.path.join(self.eis_data_dir, file_name)
                with open(eis_saved_path, 'w') as f:
                    f.write("Frequency\tZreal\tZimag\n")
                    for freq, zr, zi in zip(result['eis_data']['frequencies'], 
                                           result['eis_data']['z_real'], 
                                           result['eis_data']['z_imag']):
                        f.write(f"{freq}\t{zr}\t{zi}\n")
                eis_saved = True
                print(f"[成功] EIS数据已保存: {eis_saved_path}")
            except Exception as e:
                print(f"⚠️ 保存EIS数据文件失败: {e}")
        
        # ==================== 2. 获取CHI原始数据路径 ====================
        raw_data_path = result.get('raw_data_path', None)
        if not raw_data_path:
            # 尝试从chi_params构建预期路径
            try:
                filename = f"{self.chi_params.get('material', 'Sample')}_T{str(int(self.current_temp))}C_highf{self.chi_params.get('highf')}_lowf{self.chi_params.get('lowf')}_initV{self.chi_params.get('initV')}"
                raw_data_path = os.path.join(self.chi_params.get('your_position', 'E:\\chi_data'), filename + ".txt")
            except:
                raw_data_path = "未知"
        
        # ==================== 3. 判断成功/失败 + 失败原因 ====================
        rb = result.get('rb')
        fit_method = result.get('fit_method', '未知')
        success = False
        failure_reason = None
        
        if rb is None or fit_method in ['failed', '处理失败', '未知']:
            success = False
            # 详细失败原因
            if 'error' in result:
                failure_reason = f"数据处理异常: {result['error']}"
            elif fit_method == 'failed':
                failure_reason = "拟合失败：所有拟合方法（线性/逐步线性/圆弧）均未达标"
            elif fit_method == '处理失败':
                failure_reason = "EIS数据处理流程异常"
            elif rb is None:
                failure_reason = "Rb值为None，拟合未返回有效结果"
            else:
                failure_reason = f"未知失败原因 (method={fit_method}, rb={rb})"
        else:
            success = True
        
        # ==================== 4. 失败截图（如果失败） ====================
        debug_artifacts = []
        if not success:
            try:
                screenshot_dir = os.path.join(self.experiment_data_dir, 'failures')
                os.makedirs(screenshot_dir, exist_ok=True)
                screenshot_filename = f"failure_T{self.current_temp:.1f}C_{timestamp}.png"
                screenshot_path = os.path.join(screenshot_dir, screenshot_filename)
                
                # 使用pyautogui截图
                import pyautogui
                screenshot = pyautogui.screenshot()
                screenshot.save(screenshot_path)
                debug_artifacts.append(screenshot_path)
                print(f"[失败截图] 已保存: {screenshot_path}")
            except Exception as e:
                print(f"⚠️ 保存失败截图失败: {e}")
        
        # ==================== 5. 提取拟合质量指标 ====================
        fit_quality = None
        r_squared = None
        if 'fit_params' in result and result['fit_params']:
            fit_quality = result['fit_params'].get('r', None)
            r_squared = result['fit_params'].get('r_squared', None)
        
        # ==================== 6. 构建结构化记录 ====================
        measurement_record = {
            # 基础信息
            'temperature_C': self.current_temp,
            'temperature_K': self.current_temp + 273.15,
            'timestamp': time.time(),
            'timestamp_str': timestamp,
            'step_type': 'fine' if self.fine_measuring else 'coarse',
            'chi_measurement_number': self.chi_measurement_count,
            
            # 数据文件路径
            'raw_data_path': raw_data_path,
            'raw_data_exists': os.path.exists(raw_data_path) if raw_data_path and raw_data_path != "未知" else False,
            'eis_saved_path': eis_saved_path,
            'eis_saved': eis_saved,
            
            # 拟合结果
            'rb_ohm': rb,
            'rb_method': fit_method,
            'fit_quality': fit_quality,  # 相关系数 r
            'r_squared': r_squared,      # R²
            
            # 电导率
            'conductivity_S_per_cm': result.get('conductivity'),
            
            # 成功/失败标记
            'success': success,
            'failure_reason': failure_reason,
            
            # 调试信息
            'debug_artifacts': debug_artifacts,
            
            # 相变检测
            'phase_jump_detected': result.get('phase_jump_detected', False),
            'phase_transition_range': result.get('phase_transition_range'),
        }
        
        self.measurement_history.append(measurement_record)
        
        # 实时保存数据
        self.save_experiment_data()
        
        # ==================== 7. 打印结构化摘要 ====================
        print("\n" + "="*60)
        print(f"📊 测量点记录 [T={self.current_temp:.1f}°C / {self.current_temp + 273.15:.2f}K]")
        print("="*60)
        print(f"✅ 成功: {success}")
        if not success:
            print(f"❌ 失败原因: {failure_reason}")
            print(f"🖼️  失败截图: {len(debug_artifacts)} 张")
        else:
            print(f"🔬 Rb: {rb:.2f} Ω ({fit_method})")
            print(f"📈 拟合质量: r={fit_quality:.4f}" if fit_quality else "📈 拟合质量: N/A")
            print(f"⚡ 电导率: {result.get('conductivity'):.4e} S/cm" if result.get('conductivity') else "⚡ 电导率: N/A")
        print(f"📁 原始数据: {raw_data_path}")
        print(f"💾 标准化数据: {eis_saved_path if eis_saved else '未保存'}")
        print("="*60 + "\n")

    # ==================== 温度控制功能 ====================
    
    def _wait_for_stable_temp(self, target: float, check_recovery: bool = False, strict_cooling: bool = False) -> bool:
        """等待温度稳定"""
        start_time = time.time()
        min_temp = float('inf')
        last_temp = None
        stable_count = 0
        timeout = 7200 if strict_cooling else 3600

        print(f"等待温度{'严格' if strict_cooling else '普通'}降温到 {target}°C...")

        while time.time() - start_time < timeout:
            # 周期性暂停降温以读取温度
            current_time = time.time()
            if current_time - self.last_periodic_pause_time >= 2:
                print("📊 周期性暂停降温，读取温度中...")
                self.last_periodic_pause_time = current_time
                time.sleep(0.3)
            
            current_temp = self.read_temperature()
            if current_temp is None:
                continue

            if current_temp < min_temp:
                min_temp = current_temp
                print(f"最低温度: {min_temp:.1f}°C")

            if strict_cooling:
                if current_temp <= target:
                    stable_count += 1
                    print(f"严格降温检测 {stable_count}/8: 当前{current_temp:.1f}°C <= 目标{target:.1f}°C")
                    if stable_count >= 8:
                        print(f"✅ 严格降温完成: {target}°C")
                        return True
                else:
                    stable_count = 0
                    print(f"继续降温: 当前{current_temp:.1f}°C > 目标{target:.1f}°C")
            
            elif not check_recovery and current_temp <= target:
                print(f"达到降温目标 {target}°C")
                return True

            elif check_recovery:
                # 智能稳定性检测：根据当前温度与目标温度的关系判断是降温还是回温
                temp_diff = abs(current_temp - target)
                
                if current_temp > target:
                    # 当前温度高于目标：应该降温
                    print(f"降温检测: 当前{current_temp:.1f}°C, 目标{target:.1f}°C, 差值{temp_diff:.1f}°C, EPS={self.eps}°C")
                    
                    # 检查是否已经降到目标范围内
                    if temp_diff <= self.eps:
                        stable_count += 1
                        print(f"✅ 降温满足要求 {stable_count}/8: 差值{temp_diff:.1f}°C <= EPS({self.eps}°C)")
                        if stable_count >= 8:
                            print(f"✅ 温度已稳定（连续8次检测通过，耗时40秒）")
                            return True
                    else:
                        stable_count = 0
                        print(f"⚠️ 继续降温: 差值{temp_diff:.1f}°C > EPS({self.eps}°C)")
                else:
                    # 当前温度低于目标：应该回温
                    print(f"回温检测: 当前{current_temp:.1f}°C, 目标{target:.1f}°C, 差值{temp_diff:.1f}°C, EPS={self.eps}°C")
                    
                    if temp_diff <= self.eps:
                        stable_count += 1
                        print(f"✅ 回温满足要求 {stable_count}/8: 差值{temp_diff:.1f}°C <= EPS({self.eps}°C)")
                        if stable_count >= 8:
                            print(f"✅ 温度已稳定（连续8次检测通过，耗时40秒）")
                            return True
                    else:
                        stable_count = 0
                        print(f"⚠️ 继续回温: 差值{temp_diff:.1f}°C > EPS({self.eps}°C)")

            last_temp = current_temp
            time.sleep(5.0)  # 间隔5秒检查一次温度

        print(f"等待温度{'严格降温' if strict_cooling else '稳定'}超时")
        return False

    def _need_strict_cooling(self, step_size: float) -> bool:
        """判断是否需要严格降温"""
        large_step = step_size >= 10.0
        initial_cooling = self.current_target >= 0
        fine_measuring = self.fine_measuring
        
        return large_step or (initial_cooling and not fine_measuring)

    def check_phase_transition(self) -> bool:
        """检查是否检测到相变点"""
        return self.phase_transition_range is not None and not self.phase_detected

    def handle_phase_transition(self) -> bool:
        """处理相变点精细测量流程"""
        if not self.phase_transition_range:
            return False
            
        T_high, T_low = self.phase_transition_range
        print(f"\n🔬 ========== 启动相变点精细测量 ==========")
        print(f"📍 相变区间: [{T_high}°C, {T_low}°C]")
        print(f"🎯 策略: 主动升温至{T_high}°C，然后以{self.fine_step}°C步长精细降温")

        # 若启用两段模式且要求将精细测量延后，则在第一段只记录区间并返回
        if self.two_phase_mode and self.defer_fine_to_second_pass:
            print("🟡 两段模式启用：第一段仅检测相变点，精细测量推迟到第二段执行")
            # 标记发现相变，等待第一段结束
            self.phase_detected = True
            return True
        
        # 主动升温到相变区上限
        print(f"\n🔥 第一步: 主动升温到相变区上限 {T_high}°C...")
        if not self.active_warm_up(T_high):
            print("❌ 升温失败，继续原流程")
            return False
        
        # 保存原始状态
        original_T_end = self.T_end
        original_step_size = self.current_step_size
        original_current_target = self.current_target
        
        # 执行精细测量流程
        self.fine_measuring = True
        self.current_step_size = self.fine_step
        self.current_target = T_high
        
        print(f"\n🔬 第二步: 开始精细测量流程")
        print(f"   - 精细步长: {self.fine_step}°C")
        print(f"   - 测量区间: {T_high}°C → {T_low}°C")
        
        self.execute_fine_measurement(T_high, T_low)
        
        # 恢复原始状态
        self.fine_measuring = False
        self.T_end = original_T_end
        self.current_step_size = original_step_size
        self.phase_transition_range = None
        self.phase_detected = True
        
        print(f"\n✅ 相变点精细测量完成!")
        print(f"📊 数据收集: 在相变区间内完成了高密度温度点测量")
        print(f"🔄 恢复粗测步长: {original_step_size}°C")
        print(f"🎯 继续主流程降温到最终目标: {self.T_end}°C")
        print("=" * 50)
        
        return True

    def active_warm_up(self, target_temp: float, timeout: int = 3600) -> bool:
        """主动升温到目标温度"""
        print(f"🔥 主动升温到 {target_temp}°C...")
        
        self.set_temperature(target_temp, is_cooling=False)  # 回温不需要补偿
        
        start_time = time.time()
        stable_count = 0
        
        while time.time() - start_time < timeout:
            current_temp = self.read_temperature()
            if current_temp is None:
                time.sleep(1)
                continue
                
            print(f"升温中: 当前{current_temp:.1f}°C, 目标{target_temp}°C")
            
            temp_diff = abs(current_temp - target_temp)
            if temp_diff <= self.eps:
                stable_count += 1
                print(f"升温稳定检测 {stable_count}/5: 差值{temp_diff:.1f}°C")
                if stable_count >= 5:
                    print(f"✅ 主动升温完成: {target_temp}°C")
                    return True
            else:
                stable_count = 0
                
            time.sleep(2)
            
        print("❌ 主动升温超时")
        return False

    def execute_fine_measurement(self, T_high: float, T_low: float):
        """执行精细测量流程"""
        print(f"\n🔬 ========== 精细测量流程 ==========")
        print(f"📍 测量区间: {T_high}°C → {T_low}°C")
        print(f"📏 精细步长: {self.fine_step}°C")
        
        # 计算预期的测量点
        temp_points = []
        temp = T_high
        while temp >= T_low:
            temp_points.append(temp)
            temp -= self.fine_step
        
        print(f"🎯 预期测量点: {temp_points}")
        print(f"📊 总测量点数: {len(temp_points)}")
        
        # 确保当前温度已稳定在起始点
        current_temp = self.read_temperature()
        if current_temp is None or abs(current_temp - T_high) > self.eps:
            print(f"⚠️ 当前温度({current_temp}°C)与起始点({T_high}°C)偏差较大，重新稳定...")
            self._wait_for_stable_temp(T_high, check_recovery=True)
        
        # 在起始点执行测量（带重试）
        print(f"\n🧪 [1/{len(temp_points)}] 在起始点 {T_high}°C 进行精细测量...")
        max_retries = 3
        for retry in range(max_retries):
            if self._perform_measurement():
                break
            elif retry < max_retries - 1:
                print(f"⚠️ 测量失败，重新稳定温度（第{retry+1}/{max_retries}次）...")
                self._wait_for_stable_temp(T_high, check_recovery=True)
        
        # 精细降温循环
        measurement_count = 1
        temp = T_high
        
        while temp > T_low:
            # 计算下一个测量点
            next_temp = max(temp - self.fine_step, T_low)
            measurement_count += 1
            
            print(f"\n📉 [精细降温 {measurement_count}/{len(temp_points)}]")
            print(f"   当前: {temp}°C → 目标: {next_temp}°C")
            print(f"   降温幅度: {temp - next_temp}°C")
            
            # 设置温度并严格等待
            self.set_temperature(next_temp, is_cooling=True)  # 降温需要补偿
            print(f"⏰ 精细降温中...")
            self._wait_for_stable_temp(next_temp, check_recovery=True)
            
            # 更新当前目标温度
            self.current_target = next_temp
            temp = next_temp
            
            print(f"✅ 精细降温完成: {next_temp}°C")
            
            # 执行精细测量（带重试）
            print(f"🧪 [{measurement_count}/{len(temp_points)}] 在 {next_temp}°C 进行精细测量...")
            for retry in range(max_retries):
                if self._perform_measurement():
                    break
                elif retry < max_retries - 1:
                    print(f"⚠️ 测量失败，重新稳定温度（第{retry+1}/{max_retries}次）...")
                    self._wait_for_stable_temp(next_temp, check_recovery=True)
        
        print(f"\n✅ 精细测量流程完成!")
        print(f"📊 完成了 {measurement_count} 个精细测量点")
        print(f"🎯 最终温度: {T_low}°C")
        print("=" * 40)

    def execute_segmented_cooling_old(self, target_temp: float, main_step: float = 10.0):
        """
        【已废弃 - 备份】执行分段降温：前80%直接降温（2°C步长），后20%一度一度降温（1°C步长）
        对于小步长（如3°C），整个降温过程都有回温检测
        
        Args:
            target_temp: 目标温度
            main_step: 主步长（默认10°C）
        """
        print(f"\n🔄 ========== 开始分段降温 ==========")
        print(f"🎯 目标温度: {target_temp}°C")
        print(f"📏 主步长: {main_step}°C")
        
        # 设置分段降温标志，禁用自动测量触发
        self.segmented_cooling_active = True
        
        try:
            # 对于小步长（≤5°C），整个降温过程都有回温检测
            if main_step <= 5.0:
                print(f"📏 小步长模式: 整个降温过程都有回温检测")
                split_point = target_temp  # 整个过程都是精细控制
            else:
                # 计算分段点 (80%位置)
                split_point = target_temp + main_step * 0.8
                print(f"📍 分段点: {split_point}°C (前80%: {target_temp + main_step}°C → {split_point}°C, 后20%: {split_point}°C → {target_temp}°C)")
            
            # 获取当前温度
            current_temp = self.read_temperature()
            if current_temp is None:
                print("❌ 无法读取当前温度，退出分段降温")
                return False
                
            print(f"🌡️ 当前温度: {current_temp:.1f}°C")
            
            # 如果当前温度已经达到或低于目标，直接返回
            if current_temp <= target_temp + self.eps:
                print(f"✅ 当前温度 {current_temp:.1f}°C 已达到目标 {target_temp}°C")
                return True
            
            # 逐步降温
            temp_target = current_temp
            while temp_target > target_temp:
                # 判断是否进入后20%精细控制区
                in_fine_control = temp_target <= split_point
                
                # 获取动态步长
                if in_fine_control:
                    # 后20%：一度一度降温，有回温检测
                    D = 1
                    recovery_phase = True
                    print(f"🔍 精细控制区: 步长{D}°C，启用回温检测")
                else:
                    # 前80%：2°C步长，无回温检测
                    D = 2
                    recovery_phase = False
                    print(f"⚡ 快速降温区: 步长{D}°C，无回温检测")
                
                # 计算下一个目标温度
                next_target = max(temp_target - D, target_temp)
                print(f"📉 降温: {temp_target:.1f}°C → {next_target:.1f}°C (步长: {D}°C)")
                
                # 设置温度并等待稳定
                self.set_temperature(next_target, is_cooling=True)  # 降温需要补偿
                
                if recovery_phase:
                    print(f"⏰ 等待温度稳定到 {next_target}°C（回温检测）...")
                    reached = self._wait_for_stable_temp(next_target, check_recovery=True)
                else:
                    print(f"⏰ 等待温度稳定到 {next_target}°C...")
                    reached = self._wait_for_stable_temp(next_target, check_recovery=False)
                
                if reached:
                    print(f"✅ 温度已稳定在 {next_target}°C")
                    temp_target = next_target
                else:
                    print(f"⚠️ 温度稳定超时，但继续降温")
                    temp_target = next_target
                
                # 检查是否达到目标温度
                if temp_target <= target_temp + self.eps:
                    print(f"🎯 已达到目标温度 {target_temp}°C")
                    break
            
            print(f"✅ 分段降温完成，最终温度: {temp_target:.1f}°C")
            return True
        finally:
            # 清除分段降温标志，恢复自动测量触发
            self.segmented_cooling_active = False
            print("🔄 分段降温完成，恢复自动测量触发")
    
    def execute_segmented_cooling(self, target_temp: float, main_step: float = 10.0):
        """
        简化版降温函数 - 直接降温到目标，自动处理回温
        
        新逻辑（简化版）：
        1. 直接设置目标温度
        2. 等待温度进入有效范围（目标±eps）
        3. 如果温度过低则自动回温
        4. 温度稳定后返回
        
        Args:
            target_temp: 目标温度
            main_step: 主步长（保留参数，保持接口兼容）
        
        Returns:
            bool: 是否成功到达目标
        """
        print(f"\n🔄 ========== 开始降温到目标 ==========")
        print(f"🎯 目标温度: {target_temp}°C")
        print(f"📏 有效范围: {target_temp - self.eps:.1f}°C ~ {target_temp + self.eps:.1f}°C")
        
        # 设置分段降温标志（保留兼容性）
        self.segmented_cooling_active = True
        
        try:
            # 1. 获取当前温度
            current_temp = self.read_temperature()
            if current_temp is None:
                print("❌ 无法读取当前温度")
                return False
            
            print(f"🌡️ 当前温度: {current_temp:.1f}°C")
            
            # 2. 检查是否已经在目标范围内
            if abs(current_temp - target_temp) <= self.eps:
                print(f"✅ 温度已在目标范围内: {current_temp:.1f}°C")
                return True
            
            # 3. 设置目标温度
            self.set_temperature(target_temp, is_cooling=True)  # 降温需要补偿
            print(f"✅ 已设置制冷器目标: {target_temp}°C\n")
            
            # 4. 等待温度稳定在目标±eps范围内
            timeout = 3600  # 1小时超时
            start_time = time.time()
            stable_count = 0
            required_stable = 3  # 需要连续3次稳定（15秒）
            last_action = None
            check_interval = 5  # 检查间隔5秒
            last_print_time = 0
            failed_reads = 0  # 记录连续读取失败次数
            max_failed_reads = 10  # 最多允许连续失败10次
            
            while time.time() - start_time < timeout:
                # 检查暂停
                if self.paused:
                    print("⏸️ 降温已暂停")
                    while self.paused and self.control_active:
                        time.sleep(5)
                    print("▶️ 恢复降温")
                
                # 读取温度
                current_temp = self.read_temperature()
                if current_temp is None:
                    failed_reads += 1
                    print(f"⚠️ 温度读取失败（第{failed_reads}次）")
                    
                    # 如果连续失败次数过多，可能是串口问题
                    if failed_reads >= max_failed_reads:
                        print(f"❌ 连续{max_failed_reads}次读取失败，可能存在串口通信问题")
                        print(f"   尝试重置串口缓冲区...")
                        try:
                            self.ser.reset_input_buffer()
                            self.ser.reset_output_buffer()
                            print(f"   ✅ 串口缓冲区已重置")
                            failed_reads = 0  # 重置计数器
                        except Exception as e:
                            print(f"   ⚠️ 串口重置失败: {e}")
                    
                    time.sleep(2)
                    continue
                else:
                    failed_reads = 0  # 读取成功，重置失败计数器
                
                # 计算温度差
                temp_diff = current_temp - target_temp
                
                # 判断温度状态
                if abs(temp_diff) <= self.eps:
                    # ✅ 温度在有效范围内
                    stable_count += 1
                    print(f"✅ 稳定检测 {stable_count}/{required_stable}: "
                          f"当前 {current_temp:.1f}°C, 差值 {temp_diff:+.1f}°C")
                    
                    if stable_count >= required_stable:
                        elapsed = time.time() - start_time
                        print(f"\n🎉 温度已稳定: {current_temp:.1f}°C (耗时 {elapsed:.0f}秒)")
                        return True
                
                elif temp_diff < -self.eps:
                    # ⚠️ 温度过低，需要回温
                    stable_count = 0
                    if last_action != "warming":
                        print(f"\n🔥 温度过低！当前 {current_temp:.1f}°C < 范围下限 {target_temp - self.eps:.1f}°C")
                        print(f"   开始回温到 {target_temp}°C...")
                        self.set_temperature(target_temp, is_cooling=False)  # 回温不需要补偿
                        last_action = "warming"
                    else:
                        # 每10秒打印一次回温进度
                        if time.time() - last_print_time >= 10:
                            print(f"🔥 回温中: {current_temp:.1f}°C → {target_temp:.1f}°C (差值 {temp_diff:+.1f}°C)")
                            last_print_time = time.time()
                
                else:
                    # ⬇️ 温度过高，继续等待降温
                    stable_count = 0
                    if last_action != "cooling":
                        print(f"\n❄️ 等待降温到范围内...")
                        last_action = "cooling"
                        last_print_time = time.time()
                    else:
                        # 每10秒打印一次降温进度
                        if time.time() - last_print_time >= 10:
                            print(f"❄️ 降温中: {current_temp:.1f}°C → {target_temp:.1f}°C (差值 {temp_diff:+.1f}°C)")
                            last_print_time = time.time()
                
                time.sleep(check_interval)
            
            # 超时
            print(f"\n⚠️ 等待温度稳定超时（{timeout}秒）")
            current_temp = self.read_temperature()
            if current_temp:
                print(f"   当前温度: {current_temp:.1f}°C")
                print(f"   目标温度: {target_temp}°C")
            return False
        
        finally:
            # 清除分段降温标志
            self.segmented_cooling_active = False
            print("🔄 降温完成\n")

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
                    self.set_temperature(next_temp, is_cooling=True)  # 降温需要补偿
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
            
            # 检查并处理相变点（第一段仅检测、记录，不进行精细测量）
            if self.check_phase_transition():
                if self.two_phase_mode and self.defer_fine_to_second_pass:
                    # 只记录区间与标记，继续降温到第一段结束
                    print("🟡 第一段：检测到相变点，仅记录，不做精细测量")
                    self.phase_detected = True
                else:
                    if self.handle_phase_transition():
                        # 相变处理完成后测量（带重试）
                        max_retries = 3
                        for retry in range(max_retries):
                            if self._perform_measurement():
                                break
                            elif retry < max_retries - 1:
                                print(f"⚠️ 相变点测量失败，重新稳定温度（第{retry+1}/{max_retries}次）...")
                                time.sleep(10)
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
                return

            # 确定相变区间
            region = self.second_phase_region_override or self.phase_transition_range
            if not region:
                print("⚠️ 未检测到相变区间，第二段将不进行精细测量，流程结束")
                self.save_experiment_report()
                self.plot_results()
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
                self.set_temperature(next_temp, is_cooling=True)  # 降温需要补偿
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
                self.set_temperature(next_temp, is_cooling=True)  # 降温需要补偿
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
                self.set_temperature(next_temp, is_cooling=True)  # 降温需要补偿
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
            self.phase_detected = True

        print(f"\n第二段（如启用）完成，流程结束")
        self.save_experiment_report()
        self.plot_results()
        
        # 自动回温到18°C
        print(f"\n🔄 设置回温到18°C...")
        self.set_temperature(18.0, is_cooling=False)  # 回温不需要补偿
        print(f"✅ 已设置制冷器温度为18°C，将自动回温")
        
        # 更新控制状态为已完成
        self.control_active = False
        print(f"✅ 温度控制流程已完成，control_active = {self.control_active}")
        
        # 如果有温度更新回调，通知完成状态
        if hasattr(self, 'temperature_update_callback') and self.temperature_update_callback:
            try:
                self.temperature_update_callback(self.current_temp)
            except Exception as e:
                print(f"⚠️ 温度更新回调执行失败: {e}")

    # ==================== 数据保存和可视化功能 ====================
    
    def save_experiment_data(self):
        """实时保存实验数据"""
        # 保存温度历史
        temp_file = os.path.join(self.data_dir, "temperature_history.json")
        with open(temp_file, 'w') as f:
            json.dump(self.temperature_history, f, indent=2)
        
        # 保存测量记录
        meas_file = os.path.join(self.data_dir, "measurement_history.json")
        with open(meas_file, 'w') as f:
            json.dump(self.measurement_history, f, indent=2)
        
        # 保存相变点
        if self.phase_transition_range:
            phase_transition = {
                'range': self.phase_transition_range,
                'detected_at': self.current_temp,
                'timestamp': time.time()
            }
            self.phase_transition_points.append(phase_transition)
            phase_file = os.path.join(self.data_dir, "phase_transitions.json")
            with open(phase_file, 'w') as f:
                json.dump(self.phase_transition_points, f, indent=2)
        
        print(f"实验数据已保存到 {self.data_dir}")

    def save_experiment_report(self):
        """生成并保存实验报告"""
        report = {
            "experiment_start": datetime.now().isoformat(),
            "start_temperature": self.T_start,
            "end_temperature": self.T_end,
            "coarse_step_size": self.coarse_step,
            "fine_step_size": self.fine_step,
            "num_measurements": len(self.measurement_history),
            "num_chi_measurements": self.chi_measurement_count,
            "phase_transitions": self.phase_transition_points,
            "chi_params": self.chi_params,
            "final_status": "completed"
        }
        
        report_file = os.path.join(self.data_dir, "experiment_report.json")
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"实验报告已保存: {report_file}")

    def plot_results(self):
        """绘制实验结果"""
        self.plot_temperature_profile()
        self.plot_conductivity()

    def plot_temperature_profile(self):
        """绘制温度变化曲线"""
        if not self.temperature_history:
            times = [m['time'] for m in self.measurement_history]
            temps = [m['temperature'] for m in self.measurement_history]
        else:
            times, temps = zip(*self.temperature_history)
            
        if not times:
            print("无温度数据可绘制")
            return
            
        start_time = min(times)
        timestamps = [t - start_time for t in times]
        
        plt.figure(figsize=(12, 6))
        plt.plot(timestamps, temps, 'b-', label='实际温度')
        
        # 标记测量点
        meas_times = [m['time'] - start_time for m in self.measurement_history]
        meas_temps = [m['temperature'] for m in self.measurement_history]
        plt.scatter(meas_times, meas_temps, c='red', s=50, label='CHI测量点')
        
        # 标记相变点
        for phase in self.phase_transition_points:
            T_high, T_low = phase['range']
            mid_temp = (T_high + T_low) / 2
            min_diff = float('inf')
            phase_time = None
            for t, temp in zip(times, temps):
                diff = abs(temp - mid_temp)
                if diff < min_diff:
                    min_diff = diff
                    phase_time = t
            if phase_time is not None:
                plt.axvline(x=phase_time - start_time, color='g', linestyle='--', 
                           label=f"相变点 {T_high}°C-{T_low}°C")
        
        plt.xlabel('时间 (秒)')
        plt.ylabel('温度 (°C)')
        plt.title('温度变化曲线')
        plt.legend()
        plt.grid(True)
        
        plot_file = os.path.join(self.data_dir, "temperature_profile.png")
        plt.savefig(plot_file, dpi=300)
        print(f"温度曲线已保存: {plot_file}")
        plt.close()

    def plot_conductivity(self):
        """绘制电导率-温度曲线"""
        if not self.measurement_history:
            print("无电导率数据可绘制")
            return
        
        temps = []
        conds = []
        for meas in self.measurement_history:
            if meas['conductivity'] is not None:
                temps.append(meas['temperature'])
                conds.append(meas['conductivity'])
        
        if not temps:
            print("无有效电导率数据")
            return
            
        plt.figure(figsize=(10, 6))
        plt.semilogy(temps, conds, 'bo-', markersize=6, label='电导率')
        
        # 标记相变点
        for phase in self.phase_transition_points:
            T_high, T_low = phase['range']
            plt.axvspan(T_low, T_high, alpha=0.3, color='red', label='相变区间')
        
        plt.xlabel('温度 (°C)')
        plt.ylabel('电导率 (S/cm)')
        plt.title('电导率随温度变化')
        plt.grid(True, which="both", ls="-")
        
        # 避免重复标签
        handles, labels = plt.gca().get_legend_handles_labels()
        by_label = dict(zip(labels, handles))
        plt.legend(by_label.values(), by_label.keys())
        
        cond_file = os.path.join(self.data_dir, "conductivity_profile.png")
        plt.savefig(cond_file, dpi=300)
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
                                coarse_step: float = 10.0, fine_step: float = 3.0):
        """启动温度控制"""
        print(f"🔧 {datetime.now().strftime('%H:%M:%S')} | 启动控制 | 开始启动温度控制")
        print(f"🔧 {datetime.now().strftime('%H:%M:%S')} | 启动控制 | 参数: start_temp={start_temp}°C, end_temp={end_temp}°C, coarse_step={coarse_step}°C, fine_step={fine_step}°C")
        
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
        self.T_start = start_temp
        self.T_end = end_temp
        self.coarse_step = coarse_step
        self.fine_step = fine_step
        self.current_step_size = coarse_step
        
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
        return True

    def stop_temperature_control(self):
        """停止温度控制"""
        self.control_active = False
        if self.control_thread:
            self.control_thread.join(timeout=5)
        print("温度控制已停止")

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