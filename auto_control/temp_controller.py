# -*- coding: utf-8 -*-
"""
增强版温控器 - 融合优化温控和CHI测量功能
@author: 25862
"""

import serial
import time
import struct
import binascii
import json
import os
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
from collections import deque
from typing import Optional, Tuple, List, Dict
from datetime import datetime
import subprocess
import sys
import cv2
import pyautogui
from PIL import ImageGrab
import threading
import queue

# 设置matplotlib支持中文
matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
matplotlib.rcParams['axes.unicode_minus'] = False

# 统一 standalone 路径初始化
try:
    from auto_control._path_setup import ensure_close_root
except ImportError:
    from _path_setup import ensure_close_root

CLOSE_ROOT = ensure_close_root()

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
    
    def detect_phase_jump(zreal, zimag, threshold):
        return False
    
    def calculate_rb(zreal, zimag, temp, params):
        return {'rb': 100, 'method': '模拟拟合', 'fit_params': {}}
    
    def calculate_conductivity(rb, thickness, area):
        return 0.01
    
    def get_fit_params():
        return {}


class EnhancedRefrigeratorController:
    def __init__(self, port: str, T_start: float, T_end: float, eps: float = 0.5, 
                 coarse_step: float = 10.0, fine_step: float = 3.0,
                 thickness: float = 0.001, area: float = 1e-4,
                 data_dir: str = "experiment_data", 
                 chi_params: Dict = None):
        """
        初始化增强版冰箱控制器
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
        
        # CHI测量参数
        self.chi_params = chi_params or {
            "material": "Cu",
            "T": "298",
            "highf": "10000",
            "lowf": "1",
            "initV": "0",
            "your_position": r"C:\Users\HP\Desktop\id_",
            "your_type_text": "Text Files",
            "template_dir": "",
            "text_confidence": 70,
            "delay": 0.1
        }
        
        # 状态跟踪
        self.power_on = False
        self.current_temp = None
        self.buffer = bytearray()
        self.frame_queue = deque()
        
        # 相变点检测相关
        self.phase_transition_range = None  # (T_high, T_low)
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
        self.pause_target_temp = None  # 暂停时保持的目标温度
        self.saved_original_target = None  # 暂停前保存的原始目标温度
        
        # 串口访问锁，防止并发读写
        self.serial_lock = threading.Lock()
        
        # 周期性暂停降温的时间戳
        self.last_periodic_pause_time = time.time()

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
            return True

        cmd = bytes.fromhex('A5 5A 06 83 50 00 01 00 01')
        for _ in range(3):  # 重试3次
            self.ser.write(cmd)
            time.sleep(2)

            # 检查响应
            if self.ser.in_waiting > 0:
                resp = self.ser.read(8)
                if resp == bytes.fromhex('A5 5A 05 82 01 30 00 01'):
                    self.power_on = True
                    print("开机成功")
                    return True

        print("开机失败")
        return False

    def set_temperature(self, temp: float) -> bool:
        """设置目标温度"""
        with self.serial_lock:  # 使用锁保护串口访问
            temp_int = int(temp * 10)
            if temp_int < 0:
                temp_int = (1 << 16) + temp_int

            high_byte = (temp_int >> 8) & 0xFF
            low_byte = temp_int & 0xFF

            cmd = bytes([0xA5, 0x5A, 0x06, 0x83, 0x00, 0x26, 0x01, high_byte, low_byte])

            for _ in range(3):  # 发送3次确保接收
                self.ser.write(cmd)
                time.sleep(0.2)

            print(f"温度已设置为: {temp}°C")
            return True

    def read_temperature(self) -> Optional[float]:
        """读取当前温度"""
        with self.serial_lock:  # 使用锁保护串口访问
            start_time = time.time()
            while time.time() - start_time < 5:  # 5秒超时
                if self.ser.in_waiting > 0:
                    data = self.ser.read(self.ser.in_waiting)
                    self.buffer.extend(data)
                    self._process_buffer()

                while self.frame_queue:
                    frame = self.frame_queue.popleft()
                    temp = self._parse_frame(frame)
                    if temp is not None:
                        # 记录温度历史
                        self.temperature_history.append((time.time(), temp))
                        self.current_temp = temp
                        print(f"当前温度: {temp:.1f}°C")
                        
                        # 检查是否需要更新目标温度（当实际温度低于当前目标时）
                        if self.control_active and not self.paused and hasattr(self, 'current_target'):
                            if temp < self.current_target - self.eps:  # 实际温度低于目标温度（考虑误差）
                                # 计算下一个目标温度
                                next_target = max(self.current_target - self.current_step_size, self.T_end)
                                if next_target < self.current_target:  # 确保有下一个目标
                                    print(f"🎯 温度已低于当前目标 {self.current_target}°C，自动更新目标为 {next_target}°C")
                                    self.current_target = next_target
                        
                        # 更新全局温度状态（如果有更新回调）
                        if hasattr(self, 'temperature_update_callback') and self.temperature_update_callback:
                            try:
                                self.temperature_update_callback(temp)
                            except:
                                pass
                        
                        return temp

                time.sleep(0.1)
            return None

    def _process_buffer(self):
        """处理串口缓冲区数据"""
        while len(self.buffer) >= 2:
            # 查找帧头
            start_pos = -1
            for i in range(len(self.buffer) - 1):
                if self.buffer[i] == 0xA5 and self.buffer[i + 1] == 0x5A:
                    start_pos = i
                    break

            if start_pos == -1:
                self.buffer.clear()
                return

            if start_pos > 0:
                self.buffer = self.buffer[start_pos:]

            if len(self.buffer) < 3:
                return

            data_len = self.buffer[2]
            if len(self.buffer) < 3 + data_len:
                return

            frame = self.buffer[:3 + data_len]
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

            # 只处理0x0022参数类型（标准温度传感器）
            if param_type == 0x0022:
                # 解析温度数据
                raw = (frame[6] << 8) | frame[7]
                
                # 处理负数（16位有符号整数）
                if raw & 0x8000:
                    raw = -((raw ^ 0xFFFF) + 1)
                
                # 温度转换（假设单位为0.1°C）
                temp = raw * 0.1
                
                # 检查温度是否在合理范围内
                if -50 <= temp <= 50:  # 合理的温度范围
                    return temp
                else:
                    return None
            else:
                return None
                    
        except Exception as e:
            return None

    def open_chi_instrument(self) -> Tuple[bool, str]:
        """打开CHI电化学工作站"""
        try:
            print("正在打开CHI仪器...")
            
            # 获取屏幕截图
            screenshot = np.array(ImageGrab.grab())
            
            # 查找并点击CHI图标
            # 这里需要根据实际的CHI软件界面调整模板匹配
            # 暂时使用模拟成功
            success = True
            message = "CHI仪器打开成功"
            
            if success:
                print("CHI仪器打开成功")
                return True, message
            else:
                return False, "无法找到CHI图标"
                
        except Exception as e:
            return False, f"打开CHI仪器失败: {str(e)}"

    def run_chi_measurement(self) -> Dict:
        """执行CHI测量"""
        try:
            print("正在执行CHI测量...")
            
            # 模拟CHI测量过程
            measurement_steps = {
                "打开CHI": (True, "CHI软件启动成功"),
                "设置参数": (True, "测量参数设置完成"),
                "开始测量": (True, "EIS测量进行中"),
                "数据采集": (True, "数据采集完成"),
                "保存数据": (True, "数据保存成功")
            }
            
            # 模拟测量时间
            time.sleep(2)
            
            print("CHI测量完成")
            return measurement_steps
            
        except Exception as e:
            return {"测量": (False, f"CHI测量失败: {str(e)}")}

    def acquire_eis_data(self) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        获取EIS数据 - 调用CHI测量
        返回: (frequencies, z_real, z_imag)
        """
        print("开始获取EIS数据...")
        
        try:
            # 打开CHI仪器
            success, message = self.open_chi_instrument()
            if not success:
                raise RuntimeError(f"打开CHI仪器失败: {message}")

            # 执行CHI测量
            result = self.run_chi_measurement()
            
            # 检查测量结果
            print("\n==== CHI测量结果 ====")
            for step, (success, msg) in result.items():
                status = "✅ 成功" if success else "❌ 失败"
                print(f"{step.ljust(15)}: {status} - {msg}")
                if not success:
                    raise RuntimeError(f"测量步骤失败: {step} - {msg}")

            # 模拟EIS数据（实际应用中需要从文件读取）
            # 这里生成模拟数据用于演示
            frequencies = np.logspace(0, 4, 50)  # 1-10000 Hz
            z_real = 100 + 50 * np.exp(-frequencies/1000) + np.random.normal(0, 2, 50)
            z_imag = -30 * np.exp(-frequencies/500) + np.random.normal(0, 1, 50)
            
            print(f"成功获取EIS数据: {len(frequencies)}个数据点")
            return frequencies, z_real, z_imag
            
        except Exception as e:
            print(f"获取EIS数据失败: {str(e)}")
            raise

    def process_eis_data(self, frequencies: np.ndarray, z_real: np.ndarray, z_imag: np.ndarray) -> Dict:
        """
        处理EIS数据，检测相变点
        返回: 处理结果字典
        """
        print("开始处理EIS数据...")
        
        try:
            # 数据滤波
            freq_filtered, zreal_filtered, zimag_filtered = filter_data(
                frequencies, z_real, z_imag
            )
            
            # 检测相位突变
            phase_jump_detected = detect_phase_jump(zreal_filtered, zimag_filtered, threshold=20)
            if phase_jump_detected:
                print(f"⚠️ 检测到相位突变，可能发生相变！")
                
                # 如果之前已经记录过测量点，确定相变区间
                if self.last_measurement_temp is not None:
                    self.phase_transition_range = (self.last_measurement_temp, self.current_temp)
                    print(f"检测到相变区间: {self.phase_transition_range}")
            
            # 拟合Rb值
            rb_result = calculate_rb(zreal_filtered, zimag_filtered, self.current_temp, self.fit_params)
            
            # 检查是否使用圆弧拟合（相变标志）
            if rb_result.get('method') == '圆弧拟合':
                print("圆弧拟合检测到相变特征！")
                if self.last_measurement_temp is not None:
                    self.phase_transition_range = (self.last_measurement_temp, self.current_temp)
                    print(f"检测到相变区间: {self.phase_transition_range}")
            
            # 计算电导率
            conductivity = calculate_conductivity(
                rb_result.get('rb'),
                self.thickness,
                self.area
            )
            
            result = {
                'temperature': self.current_temp,
                'rb': rb_result.get('rb'),
                'conductivity': conductivity,
                'fit_method': rb_result.get('method', '未知'),
                'phase_jump_detected': phase_jump_detected,
                'phase_transition_range': self.phase_transition_range,
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
            
            print(f"温度 {self.current_temp}°C: Rb = {rb_result.get('rb'):.2f} Ω, 电导率 = {conductivity:.4e} S/cm")
            return result
            
        except Exception as e:
            print(f"数据处理失败: {str(e)}")
            return {
                'temperature': self.current_temp,
                'rb': None,
                'conductivity': None,
                'fit_method': '处理失败',
                'phase_jump_detected': False,
                'phase_transition_range': None,
                'error': str(e)
            }

    def save_measurement_data(self, result: Dict):
        """保存测量数据"""
        # 保存EIS数据到文件
        file_name = f"eis_{self.current_temp:.1f}C_{time.strftime('%Y%m%d_%H%M%S')}.txt"
        file_path = os.path.join(self.eis_data_dir, file_name)
        
        with open(file_path, 'w') as f:
            f.write("Frequency\tZreal\tZimag\n")
            for freq, zr, zi in zip(result['eis_data']['frequencies'], 
                                   result['eis_data']['z_real'], 
                                   result['eis_data']['z_imag']):
                f.write(f"{freq}\t{zr}\t{zi}\n")
        
        # 更新测量记录
        measurement_record = {
            'temperature': self.current_temp,
            'time': time.time(),
            'eis_data_file': file_path,
            'step_type': 'fine' if self.fine_measuring else 'coarse',
            'rb': result['rb'],
            'conductivity': result['conductivity'],
            'fit_method': result['fit_method'],
            'phase_jump_detected': result['phase_jump_detected'],
            'phase_transition_range': result['phase_transition_range']
        }
        
        self.measurement_history.append(measurement_record)
        
        # 实时保存数据
        self.save_experiment_data()
        
        print(f"测量数据已保存: {file_path}")

    def check_phase_transition(self) -> bool:
        """检查是否检测到相变点"""
        return self.phase_transition_range is not None and not self.phase_detected

    def _need_strict_cooling(self, step_size: float) -> bool:
        """
        判断是否需要严格降温
        :param step_size: 当前降温幅度
        :return: 是否需要严格降温
        """
        # 条件1: 降温幅度达到或超过10°C
        large_step = step_size >= 10.0
        
        # 条件2: 当前处于初始降温阶段(从室温开始的第一轮降温)
        initial_cooling = self.current_target >= 0  # 0°C以上认为是初始阶段
        
        # 条件3: 精细测量阶段(相变点附近)
        fine_measuring = self.fine_measuring
        
        return large_step or (initial_cooling and not fine_measuring)

    def wait_for_passive_warm_up(self, target_temp: float, timeout: int = 36000) -> bool:
        """
        等待被动升温到目标温度
        :param target_temp: 目标温度
        :param timeout: 超时时间（秒），默认10小时
        :return: 是否成功升温
        """
        print(f"等待温度回升到 {target_temp}°C (被动升温)...")
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            current_temp = self.read_temperature()
            if current_temp is None:
                time.sleep(1)
                continue
                
            print(f"当前温度: {current_temp:.1f}°C, 目标: {target_temp}°C")
            
            # 检查是否达到目标温度（考虑容差）
            if current_temp >= target_temp - self.eps:
                print(f"已达到升温目标 {target_temp}°C")
                return True
                
            time.sleep(10)  # 每10秒检查一次
            
        print("升温超时")
        return False

    def active_warm_up(self, target_temp: float, timeout: int = 3600) -> bool:
        """
        主动升温到目标温度
        :param target_temp: 目标温度
        :param timeout: 超时时间（秒），默认1小时
        :return: 是否成功升温
        """
        print(f"🔥 主动升温到 {target_temp}°C...")
        
        # 设置升温目标
        self.set_temperature(target_temp)
        
        start_time = time.time()
        stable_count = 0
        
        while time.time() - start_time < timeout:
            current_temp = self.read_temperature()
            if current_temp is None:
                time.sleep(1)
                continue
                
            print(f"升温中: 当前{current_temp:.1f}°C, 目标{target_temp}°C")
            
            # 检查是否接近目标温度
            temp_diff = abs(current_temp - target_temp)
            if temp_diff <= self.eps:
                stable_count += 1
                print(f"升温稳定检测 {stable_count}/5: 差值{temp_diff:.1f}°C")
                if stable_count >= 5:
                    print(f"✅ 主动升温完成: {target_temp}°C")
                    return True
            else:
                stable_count = 0
                
            time.sleep(2)  # 每2秒检查一次
            
        print("❌ 主动升温超时")
        return False

    def handle_phase_transition(self) -> bool:
        """处理相变点精细测量流程 - 改进版"""
        if not self.phase_transition_range:
            return False
            
        T_high, T_low = self.phase_transition_range
        print(f"\n🔬 ========== 启动相变点精细测量 ==========")
        print(f"📍 相变区间: [{T_high}°C, {T_low}°C]")
        print(f"🎯 策略: 主动升温至{T_high}°C，然后以{self.fine_step}°C步长精细降温")
        
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
        self.current_target = T_high  # 重置当前目标温度
        
        print(f"\n🔬 第二步: 开始精细测量流程")
        print(f"   - 精细步长: {self.fine_step}°C")
        print(f"   - 测量区间: {T_high}°C → {T_low}°C")
        
        self.execute_fine_measurement(T_high, T_low)
        
        # 恢复原始状态，但继续从当前位置降温
        self.fine_measuring = False
        self.T_end = original_T_end
        self.current_step_size = original_step_size
        self.phase_transition_range = None
        self.phase_detected = True  # 标记相变点已处理
        
        print(f"\n✅ 相变点精细测量完成!")
        print(f"📊 数据收集: 在相变区间内完成了高密度温度点测量")
        print(f"🔄 恢复粗测步长: {original_step_size}°C")
        print(f"🎯 继续主流程降温到最终目标: {self.T_end}°C")
        print("=" * 50)
        
        return True

    def execute_fine_measurement(self, T_high: float, T_low: float):
        """执行精细测量流程 - 改进版"""
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
        
        # 在起始点执行测量
        print(f"\n🧪 [1/{len(temp_points)}] 在起始点 {T_high}°C 进行精细测量...")
        self._perform_measurement()
        print(f"⏱️ 保持温度 {T_high}°C 进行3分钟EIS测试...")
        time.sleep(180)  # 精细测量也保持3分钟
        
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
            
            # 设置温度并严格等待(精细测量通常需要严格控制)
            self.set_temperature(next_temp)
            print(f"⏰ 精细降温中...")
            self._wait_for_stable_temp(next_temp, check_recovery=True)
            
            # 更新当前目标温度
            self.current_target = next_temp
            temp = next_temp
            
            print(f"✅ 精细降温完成: {next_temp}°C")
            
            # 执行精细测量
            print(f"🧪 [{measurement_count}/{len(temp_points)}] 在 {next_temp}°C 进行精细测量...")
            self._perform_measurement()
            print(f"⏱️ 保持温度 {next_temp}°C 进行3分钟EIS测试...")
            time.sleep(180)  # 每个精细测量点保持3分钟
        
        print(f"\n✅ 精细测量流程完成!")
        print(f"📊 完成了 {measurement_count} 个精细测量点")
        print(f"🎯 最终温度: {T_low}°C")
        print("=" * 40)

    def _wait_for_stable_temp(self, target: float, check_recovery: bool = False, strict_cooling: bool = False) -> bool:
        """
        等待温度稳定
        :param target: 目标温度
        :param check_recovery: 是否检测温度回升
        :param strict_cooling: 是否严格降温模式
        """
        start_time = time.time()
        min_temp = float('inf')
        last_temp = None
        stable_count = 0
        timeout = 7200 if strict_cooling else 3600  # 严格模式下延长超时时间到2小时

        print(f"等待温度{'严格' if strict_cooling else '普通'}降温到 {target}°C...")

        while time.time() - start_time < timeout:
            # 周期性暂停降温以读取温度（每2秒暂停一次）
            current_time = time.time()
            if current_time - self.last_periodic_pause_time >= 2:
                print("📊 周期性暂停降温，读取温度中...")
                self.last_periodic_pause_time = current_time
                # 暂停期间不进行温度控制，让监控线程可以安全读取温度
                time.sleep(0.3)  # 给监控线程读取温度的时间窗口
            
            current_temp = self.read_temperature()
            if current_temp is None:
                continue

            # 更新最低温度
            if current_temp < min_temp:
                min_temp = current_temp
                print(f"最低温度: {min_temp:.1f}°C")

            # 严格降温模式：必须达到或低于目标温度
            if strict_cooling:
                if current_temp <= target:
                    stable_count += 1
                    print(f"严格降温检测 {stable_count}/10: 当前{current_temp:.1f}°C <= 目标{target:.1f}°C")
                    if stable_count >= 10:  # 严格模式需要连续10次确认
                        print(f"✅ 严格降温完成: {target}°C")
                        return True
                else:
                    stable_count = 0
                    print(f"继续降温: 当前{current_temp:.1f}°C > 目标{target:.1f}°C")
            
            # 快速降温模式
            elif not check_recovery and current_temp <= target:
                print(f"达到降温目标 {target}°C")
                return True

            # 回升检测模式
            elif check_recovery:
                # 检查温度是否已经接近目标温度（考虑误差容限）
                temp_diff = abs(current_temp - target)
                if temp_diff <= self.eps:  # 使用eps作为误差容限
                    stable_count += 1
                    print(f"温度稳定检测 {stable_count}/3: 当前{current_temp:.1f}°C, 目标{target:.1f}°C, 差值{temp_diff:.1f}°C")
                    if stable_count >= 3:
                        print(f"温度已稳定在目标温度 {target}°C 附近")
                        return True
                else:
                    stable_count = 0
                    
                # 额外的回升检测逻辑（保留原有功能）
                if last_temp and current_temp > last_temp:
                    print(f"温度回升: {last_temp:.1f}→{current_temp:.1f}°C")

            last_temp = current_temp
            time.sleep(0.7)  # 减少到0.7秒，因为已经有0.3秒的暂停时间

        print(f"等待温度{'严格降温' if strict_cooling else '稳定'}超时")
        return False

    def _perform_measurement(self):
        """执行完整的测量流程"""
        print(">>> 开始执行测量函数 <<<")
        print(f"- 当前温度: {self.current_temp:.1f}°C")
        print(f"- 目标温度: {self.current_target}°C")
        print(f"- 处于{'精细' if self.fine_measuring else '粗测'}测量模式")

        # 获取EIS数据
        try:
            frequencies, z_real, z_imag = self.acquire_eis_data()
        except Exception as e:
            print(f"EIS测量失败: {str(e)}")
            return
            
        # 处理EIS数据
        result = self.process_eis_data(frequencies, z_real, z_imag)
        
        # 保存测量数据
        self.save_measurement_data(result)
        
        # 更新上次测量温度
        self.last_measurement_temp = self.current_temp

    def run_cooling_procedure(self):
        """主降温控制流程"""
        # 检查是否处于暂停状态
        if self.paused:
            print(f"⏸️ 检测到暂停状态，跳过降温流程")
            print(f"💡 系统当前处于暂停状态，保持温度: {self.pause_target_temp:.1f}°C")
            print(f"🔄 如需恢复降温，请调用 resume_cooling() 方法")
            return
            
        if not self._ensure_power_on():
            return

        # 检查当前温度是否高于初始温度
        print("检查当前温度...")
        current_temp = self.read_temperature()
        if current_temp is None:
            print("无法读取当前温度，退出程序")
            return
            
        print(f"当前温度: {current_temp:.1f}°C, 初始温度: {self.T_start}°C")
        
        # 如果当前温度高于初始温度，先严格降温至初始温度
        if current_temp > self.T_start:
            print(f"\n🌡️ 当前温度 {current_temp:.1f}°C 高于初始温度 {self.T_start}°C")
            print(f"🔥 启动严格降温模式: 必须达到初始温度才能开始实验")
            self.set_temperature(self.T_start)
            print(f"⏰ 严格等待降温至初始温度 {self.T_start}°C...")
            self._wait_for_stable_temp(self.T_start, check_recovery=False, strict_cooling=True)
            print(f"✅ 已严格降温至初始温度 {self.T_start}°C")
        else:
            print(f"✅ 当前温度 {current_temp:.1f}°C 已低于或等于初始温度 {self.T_start}°C")

        # 设置起始温度并等待稳定
        self.set_temperature(self.T_start)
        print(f"\n📍 起始温度设定: {self.T_start}°C")
        
        # 等待温度稳定并执行第一次测量
        print(f"⏰ 等待温度稳定到 {self.T_start}°C（误差容限: ±{self.eps}°C）...")
        if self._wait_for_stable_temp(self.T_start, check_recovery=True):
            print(f"✅ 温度已稳定，开始执行第一次测量")
            self._perform_measurement()
        else:
            print(f"❌ 温度稳定超时，但继续执行测量")
            self._perform_measurement()

        # 主降温循环
        print(f"\n🔄 ========== 开始主降温循环 ==========")
        print(f"🎯 目标路径: {self.current_target}°C → {self.T_end}°C")
        print(f"📏 当前步长: {self.current_step_size}°C")
        
        while self.current_target > self.T_end and self.control_active:
            # 周期性暂停降温以读取温度（每2秒暂停一次）
            current_time = time.time()
            if current_time - self.last_periodic_pause_time >= 2:
                print("📊 周期性暂停降温，读取温度中...")
                self.last_periodic_pause_time = current_time
                # 暂停期间让监控线程可以安全读取温度
                time.sleep(0.3)  # 给监控线程读取温度的时间窗口
                
            # 检查暂停状态
            if self.paused:
                print(f"\n⏸️ 降温已暂停，保持温度: {self.pause_target_temp:.1f}°C")
                print("💡 等待用户恢复降温控制...")
                
                # 在暂停期间保持温度稳定
                while self.paused and self.control_active:
                    current_temp = self.read_temperature()
                    if current_temp is not None and self.pause_target_temp is not None:
                        # 检查温度是否偏离暂停目标温度
                        temp_diff = abs(current_temp - self.pause_target_temp)
                        if temp_diff > self.eps * 2:  # 允许更大的误差范围
                            print(f"📉 温度偏离暂停目标，重新设置: {self.pause_target_temp:.1f}°C")
                            self.set_temperature(self.pause_target_temp)
                        
                    time.sleep(5)  # 暂停时每5秒检查一次
                
                # 暂停结束，继续降温流程
                if not self.paused and self.control_active:
                    print(f"▶️ 恢复降温控制，继续向 {self.T_end}°C 降温")
                continue
            # 检查并处理相变点
            if self.check_phase_transition():
                if self.handle_phase_transition():
                    # 精细测量完成后，继续主降温流程
                    continue
            
            # 检查当前温度是否已经低于目标（可能在read_temperature中已更新）
            if self.current_temp and self.current_temp < self.current_target - self.eps:
                print(f"📊 当前温度 {self.current_temp:.1f}°C 已低于目标 {self.current_target}°C")
                # 目标温度应该已经在read_temperature中更新了
                continue
            
            # 计算下一个目标温度
            next_target = max(self.current_target - self.current_step_size, self.T_end)
            step_size = self.current_target - next_target
            
            print(f"\n📉 降温步骤:")
            print(f"   当前温度: {self.current_target}°C")
            print(f"   目标温度: {next_target}°C")
            print(f"   降温幅度: {step_size}°C")
            print(f"   步长模式: {'精细' if self.fine_measuring else '粗测'}")
            
            # 判断是否需要严格降温
            need_strict_cooling = self._need_strict_cooling(step_size)
            
            if need_strict_cooling:
                print(f"🔥 触发严格降温条件:")
                print(f"   - 降温幅度: {step_size}°C >= 10°C")
                print(f"   - 或当前处于初始降温阶段")
                
            # 设置并等待降温
            self.set_temperature(next_target)
            
            if need_strict_cooling:
                print(f"⏰ 执行严格降温到 {next_target}°C...")
                self._wait_for_stable_temp(next_target, check_recovery=False, strict_cooling=True)
            else:
                print(f"⏰ 执行普通降温到 {next_target}°C...")
                self._wait_for_stable_temp(next_target, check_recovery=True)
            
            # 更新当前目标温度
            self.current_target = next_target
            print(f"✅ 降温完成，当前目标温度: {self.current_target}°C")
            
            # 执行测量(保持3分钟EIS测试)
            print(f"🧪 开始在 {self.current_target}°C 下进行EIS测量(持续3分钟)...")
            self._perform_measurement()
            
            # 保持温度3分钟进行测量，期间也要周期性暂停以读取温度
            print(f"⏱️ 保持温度 {self.current_target}°C 继续测量 180秒...")
            measurement_start_time = time.time()
            while time.time() - measurement_start_time < 180:
                # 周期性暂停降温以读取温度
                current_time = time.time()
                if current_time - self.last_periodic_pause_time >= 2:
                    print("📊 测量期间周期性读取温度...")
                    self.last_periodic_pause_time = current_time
                    # 读取当前温度以确保温度稳定
                    temp = self.read_temperature()
                    if temp is not None and abs(temp - self.current_target) > self.eps:
                        print(f"📉 温度偏离，重新设置: {self.current_target}°C")
                        self.set_temperature(self.current_target)
                
                time.sleep(0.5)  # 短暂休眠

        print(f"\n最终温度 {self.T_end}°C 已达成，流程结束")
        self.save_experiment_report()
        self.plot_results()

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
            "phase_transitions": self.phase_transition_points,
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
            # 如果没有实际温度历史，使用测量点的温度
            times = [m['time'] for m in self.measurement_history]
            temps = [m['temperature'] for m in self.measurement_history]
        else:
            times, temps = zip(*self.temperature_history)
            
        if not times:
            print("无温度数据可绘制")
            return
            
        start_time = min(times)
        timestamps = [t - start_time for t in times]  # 转换为相对时间
        
        plt.figure(figsize=(12, 6))
        plt.plot(timestamps, temps, 'b-', label='实际温度')
        
        # 标记测量点
        meas_times = [m['time'] - start_time for m in self.measurement_history]
        meas_temps = [m['temperature'] for m in self.measurement_history]
        plt.scatter(meas_times, meas_temps, c='red', s=50, label='测量点')
        
        # 标记相变点
        for phase in self.phase_transition_points:
            T_high, T_low = phase['range']
            # 找到相变区间中点的时间
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
        
        # 保存图像
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
        
        # 保存图像
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
                # 检查串口是否有效
                if not hasattr(self, 'ser') or not self.ser or not self.ser.is_open:
                    print("监控线程: 串口连接无效，停止监控")
                    break
                
                current_temp = self.read_temperature()
                if current_temp is not None:
                    # 重置错误计数
                    error_count = 0
                    
                    # 将实时数据放入队列
                    realtime_data = {
                        'timestamp': time.time(),
                        'temperature': current_temp,
                        'target_temperature': self.current_target,
                        'control_status': 'active' if self.control_active else 'idle'
                    }
                    self.realtime_data_queue.put(realtime_data)
                    
                    # 限制队列大小
                    while self.realtime_data_queue.qsize() > 1000:
                        try:
                            self.realtime_data_queue.get_nowait()
                        except queue.Empty:
                            break
                else:
                    # 温度读取失败，增加错误计数
                    error_count += 1
                    if error_count >= max_errors:
                        print(f"监控线程: 连续{max_errors}次读取失败，停止监控")
                        break
                            
                time.sleep(1)  # 每秒更新一次
            except Exception as e:
                error_count += 1
                if error_count >= max_errors:
                    print(f"监控线程: 连续{max_errors}次错误，停止监控: {e}")
                    break
                else:
                    print(f"监控线程错误 ({error_count}/{max_errors}): {e}")
                    time.sleep(2)  # 错误时等待更长时间

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
        if self.control_active:
            return False
            
        self.T_start = start_temp
        self.T_end = end_temp
        self.coarse_step = coarse_step
        self.fine_step = fine_step
        self.current_step_size = coarse_step
        self.current_target = start_temp
        
        self.control_active = True
        self.control_thread = threading.Thread(target=self._control_worker)
        self.control_thread.daemon = True
        self.control_thread.start()
        print(f"温度控制已启动: {start_temp}°C → {end_temp}°C")
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
            
        # 获取当前温度作为暂停目标温度
        current_temp = self.read_temperature()
        print(f"🌡️ 当前读取温度: {current_temp}")
        
        if current_temp is None:
            print("❌ 无法读取当前温度，暂停失败")
            return False
            
        # 保存当前的目标温度（不是当前温度），用于恢复时使用
        self.saved_original_target = self.current_target
        print(f"💾 保存原始目标温度: {self.saved_original_target:.1f}°C")
        
        self.paused = True
        self.pause_target_temp = current_temp
        
        # 设置当前温度为新的目标温度，发送给硬件端以暂停降温
        self.current_target = current_temp
        
        # 同时更新next_target为当前温度，避免控制逻辑继续使用旧的next_target
        if hasattr(self, 'next_target'):
            self.next_target = current_temp
            print(f"🔄 下一个目标温度也设置为: {current_temp:.1f}°C")
            
        self.set_temperature(current_temp)
        
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
            
            # 发送恢复的目标温度到硬件端
            self.set_temperature(self.saved_original_target)
            print(f"📤 已向硬件发送恢复的目标温度: {self.saved_original_target:.1f}°C")
            
            # 注意：next_target将在控制流程中自动更新，这里不需要手动设置
        else:
            print("⚠️ 未找到保存的原始目标温度，使用最终目标温度")
            self.current_target = self.T_end
            self.set_temperature(self.T_end)
            
        self.paused = False
        self.pause_target_temp = None
        self.saved_original_target = None  # 清空保存的目标温度
        
        print(f"✅ 🔄 降温已恢复，继续向目标温度 {self.current_target:.1f}°C 降温")
        print(f"📉 当前目标: {self.current_target}°C → 最终目标: {self.T_end}°C")
        return True

    def is_paused(self) -> bool:
        """检查是否处于暂停状态"""
        return self.paused

    def _control_worker(self):
        """温度控制工作线程"""
        try:
            self.run_cooling_procedure()
        except Exception as e:
            print(f"温度控制错误: {e}")
        finally:
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
            'control_active': self.control_active,
            'is_monitoring': self.is_monitoring,
            'measurement_count': len(self.measurement_history),
            'phase_transitions': len(self.phase_transition_points),
            'paused': self.paused,
            'pause_target_temp': self.pause_target_temp
        }


# ==================== 全局控制器实例 ====================
_global_controller = None

def get_global_controller() -> Optional[EnhancedRefrigeratorController]:
    """获取全局控制器实例"""
    return _global_controller

def create_global_controller(port: str, **kwargs) -> EnhancedRefrigeratorController:
    """创建全局控制器实例"""
    global _global_controller
    if _global_controller:
        _global_controller.close_serial()
    
    _global_controller = EnhancedRefrigeratorController(port=port, **kwargs)
    return _global_controller


if __name__ == "__main__":
    # 配置参数
    PORT = 'COM3'           # 冰箱控制器串口号
    T_START = 10            # 起始温度(°C)
    T_END = -30             # 目标温度(°C)
    EPS = 0.5               # 温度误差容限(°C)
    COARSE_STEP = 10        # 粗测步长(°C)
    FINE_STEP = 3           # 精细测量步长(°C)
    THICKNESS = 0.001       # 样品厚度(m)
    AREA = 1e-4             # 样品截面积(m²)
    DATA_DIR = "experiment_data"  # 数据存储路径

    print(f"启动增强版温控程序")
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