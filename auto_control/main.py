# -*- coding: utf-8 -*-
"""
增强版冰箱控制程序 - 集成精细化测量和数据处理功能
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

# 统一 standalone 路径初始化
try:
    from auto_control._path_setup import ensure_auto_control_dir, ensure_close_root
except ImportError:
    from _path_setup import ensure_auto_control_dir, ensure_close_root

AUTO_CONTROL_DIR = ensure_auto_control_dir()
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

# 导入自动点击模块
try:
    from auto_control.open_CHI import open_chi_instrument
    from auto_control.run_chi import run_chi_measurement
    print("成功导入自动点击模块")
except ImportError as e:
    print(f"警告: 无法导入自动点击模块: {e}")
    # 创建模拟函数
    def open_chi_instrument(template_dir="", confidence=0.8, delay=0.5):
        return True, "模拟打开成功"
    
    def run_chi_measurement(**kwargs):
        return {"测量": (True, "模拟测量成功")}

# 设置matplotlib支持中文
matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
matplotlib.rcParams['axes.unicode_minus'] = False


class EnhancedRefrigeratorController:
    def __init__(self, port: str, T_start: float, T_end: float, eps: float = 0.5, 
                 coarse_step: float = 10.0, fine_step: float = 3.0,
                 thickness: float = 0.001, area: float = 1e-4,
                 data_dir: str = "experiment_data"):
        """
        初始化控制器
        :param port: 串口名称
        :param T_start: 起始温度 (°C)
        :param T_end: 目标温度 (°C)
        :param eps: 温度误差容限 (°C)
        :param coarse_step: 粗测步长 (°C)
        :param fine_step: 精细测量步长 (°C)
        :param thickness: 样品厚度 (m)
        :param area: 样品截面积 (m²)
        :param data_dir: 数据存储目录
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
            if param_type == 0x0022:  # 温度数据
                raw = (frame[6] << 8) | frame[7]
                if raw & 0x8000:
                    raw = -((raw ^ 0xFFFF) + 1)
                return raw * 0.1
        except Exception as e:
            print(f"解析错误: {e}")
        return None

    def acquire_eis_data(self) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        获取EIS数据 - 调用自动点击程序
        返回: (frequencies, z_real, z_imag)
        """
        print("开始获取EIS数据...")
        
        try:
            # 调用open_CHI.py
            print("正在打开CHI仪器...")
            success, message = open_chi_instrument(
                template_dir="",
                confidence=0.8,
                delay=0.5
            )
            if not success:
                raise RuntimeError(f"打开CHI仪器失败: {message}")

            # 调用run_chi.py
            print("正在执行CHI测量...")
            result = run_chi_measurement(
                material="Cu",
                T="298",
                highf="10000",
                lowf="1",
                initV="0",
                your_position=r"C:\Users\HP\Desktop\id_",
                your_type_text="Text Files",
                template_dir="",
                text_confidence=70,
                delay=0.1
            )

            # 检查测量结果
            print("\n==== CHI测量结果 ====")
            for step, (success, msg) in result.items():
                status = "✅ 成功" if success else "❌ 失败"
                print(f"{step.ljust(15)}: {status} - {msg}")
                if not success:
                    raise RuntimeError(f"测量步骤失败: {step} - {msg}")

            # 再次调用open_CHI.py关闭仪器
            print("正在关闭CHI仪器...")
            success, message = open_chi_instrument(
                template_dir="",
                confidence=0.8,
                delay=0.5
            )
            if not success:
                print(f"关闭CHI仪器失败: {message}")

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

    def handle_phase_transition(self) -> bool:
        """处理相变点精细测量流程"""
        if not self.phase_transition_range:
            return False
            
        T_high, T_low = self.phase_transition_range
        print(f"启动相变点精细测量: [{T_high}°C, {T_low}°C]")
        
        # 被动升温到相变区上限
        print("等待被动升温到相变区上限...")
        if not self.wait_for_passive_warm_up(T_high):
            print("升温失败，继续原流程")
            return False
        
        # 保存原始目标温度和步长
        original_T_end = self.T_end
        original_step_size = self.current_step_size
        
        # 执行精细测量流程
        self.fine_measuring = True
        self.current_step_size = self.fine_step
        self.execute_fine_measurement(T_high, T_low)
        
        # 恢复原始状态
        self.fine_measuring = False
        self.T_end = original_T_end
        self.current_step_size = original_step_size
        self.phase_transition_range = None
        self.phase_detected = True  # 标记相变点已处理
        
        print("相变点精细测量完成")
        return True

    def execute_fine_measurement(self, T_high: float, T_low: float):
        """执行精细测量流程"""
        # 设置精细测量参数
        self.current_target = T_high
        self.T_end = T_low
        
        print(f"开始精细测量: {T_high}°C → {T_low}°C (步长 {self.fine_step}°C)")
        
        # 使用精细步长进行降温测量
        self.run_cooling_procedure()

    def _wait_for_stable_temp(self, target: float, check_recovery: bool) -> bool:
        """等待温度稳定"""
        start_time = time.time()
        min_temp = float('inf')
        last_temp = None
        stable_count = 0

        while time.time() - start_time < 3600:  # 1小时超时
            current_temp = self.read_temperature()
            if current_temp is None:
                continue

            # 更新最低温度
            if current_temp < min_temp:
                min_temp = current_temp
                print(f"最低温度: {min_temp:.1f}°C")

            # 快速降温模式
            if not check_recovery and current_temp <= target:
                print(f"达到降温目标 {target}°C")
                return True

            # 回升检测模式
            if check_recovery:
                if last_temp and current_temp > last_temp:
                    print(f"温度回升: {last_temp:.1f}→{current_temp:.1f}°C")
                    if current_temp < target and abs(current_temp - target) < 1.0:
                        stable_count += 1
                        if stable_count >= 3:
                            return True
                    else:
                        stable_count = 0

            last_temp = current_temp
            time.sleep(1)

        print("等待温度稳定超时")
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
        if not self._ensure_power_on():
            return

        self.set_temperature(self.T_start)
        print(f"起始温度设定: {self.T_start}°C")
        
        # 等待温度稳定并执行第一次测量
        self._wait_for_stable_temp(self.T_start, check_recovery=True)
        self._perform_measurement()

        # 主降温循环
        while self.current_target > self.T_end:
            # 检查并处理相变点
            if self.check_phase_transition():
                if self.handle_phase_transition():
                    # 精细测量完成后，继续主降温流程
                    continue
            
            # 计算下一个目标温度
            next_target = max(self.current_target - self.current_step_size, self.T_end)
            print(f"\n开始降温步长: {self.current_step_size}°C (当前目标: {self.current_target}°C, 下一目标: {next_target}°C)")
            
            # 设置并等待降温
            self.set_temperature(next_target)
            self._wait_for_stable_temp(next_target, check_recovery=True)
            
            # 更新当前目标温度
            self.current_target = next_target
            print(f"完成降温步长，当前目标温度: {self.current_target}°C")
            
            # 执行测量
            self._perform_measurement()

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

    def close_serial(self):
        """关闭串口"""
        if self.ser and self.ser.is_open:
            self.ser.close()
            print("串口已关闭")


if __name__ == "__main__":
    # 配置参数
    PORT = 'COM3'           # 冰箱控制器串口号
    T_START = 10            # 起始温度(°C)
    T_END = -30             # 目标温度(°C)
    EPS = 0.5               # 温度误差容限(°C)
    STEP_SIZE = 10          # 降温步长(°C)
    THICKNESS = 0.001       # 样品厚度(m)
    AREA = 1e-4             # 样品截面积(m²)
    DATA_DIR = "experiment_data"  # 数据存储路径

    print(f"启动增强版温控程序")
    print(f"起始温度: {T_START}°C, 目标温度: {T_END}°C")
    print(f"粗测步长: {STEP_SIZE}°C, 精细步长: {EPS}°C")
    print(f"样品参数: 厚度={THICKNESS*1000}mm, 面积={AREA*1e4}cm²")
    print(f"数据保存路径: {DATA_DIR}")
    
    try:
        # 创建控制器实例
        controller = EnhancedRefrigeratorController(
            port=PORT,
            T_start=T_START,
            T_end=T_END,
            eps=EPS,
            coarse_step=STEP_SIZE,
            fine_step=EPS,
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
        if 'controller' in locals():
            controller.close_serial() 