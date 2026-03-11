# -*- coding: utf-8 -*-
"""
集成温控相变点检测和精细化测量工作流系统
@author: 25862
"""

import os
import sys
import time
import json
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import threading
import queue
import cv2
import pyautogui
from PIL import ImageGrab

# 设置matplotlib支持中文
matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
matplotlib.rcParams['axes.unicode_minus'] = False

# 统一 standalone 路径初始化
try:
    from auto_control._path_setup import ensure_auto_control_dir, ensure_close_root
except ImportError:
    from _path_setup import ensure_auto_control_dir, ensure_close_root

AUTO_CONTROL_DIR = ensure_auto_control_dir()
CLOSE_ROOT = ensure_close_root()

# 导入相关模块
try:
    from auto_control.temp_controller import EnhancedRefrigeratorController
    from auto_control.run_chi import run_chi_measurement
    from specific_conductance.plot_bode import plot_bode_diagrams
    from auto_control.rb_fitting import calculate_rb, visualize_fitting
    from auto_control.data_processing import filter_data, detect_phase_jump
    from auto_control.conductivity import calculate_conductivity, plot_conductivity_vs_temperature
    print("成功导入所有模块")
except ImportError as e:
    print(f"警告: 无法导入某些模块: {e}")
    # 创建模拟函数避免崩溃
    def plot_bode_diagrams(data_dict, save_dir):
        print("Bode图绘制功能不可用")
    
    def calculate_conductivity(rb, thickness, area):
        return 0.01 if rb > 0 else 0.0


class IntegratedPhaseTransitionWorkflow:
    """
    集成相变点检测和精细化测量工作流
    """
    
    def __init__(self, 
                 port: str = 'COM3',
                 T_start: float = 20.0,
                 T_end: float = -30.0,
                 coarse_step: float = 10.0,
                 fine_step: float = 3.0,
                 eps: float = 0.5,
                 thickness: float = 0.001,
                 area: float = 1e-4,
                 data_dir: str = "experiment_data",
                 chi_params: Dict = None):
        """
        初始化工作流系统
        
        Args:
            port: 串口名称
            T_start: 起始温度 (°C)
            T_end: 目标温度 (°C)
            coarse_step: 粗测步长 (°C)
            fine_step: 精细测量步长 (°C)
            eps: 温度误差容限 (°C)
            thickness: 样品厚度 (m)
            area: 样品截面积 (m²)
            data_dir: 数据存储目录
            chi_params: CHI测量参数
        """
        self.port = port
        self.T_start = T_start
        self.T_end = T_end
        self.coarse_step = coarse_step
        self.fine_step = fine_step
        self.eps = eps
        self.thickness = thickness
        self.area = area
        self.data_dir = data_dir
        
        # 创建子目录
        self.eis_data_dir = os.path.join(data_dir, "eis_data")
        self.bode_plots_dir = os.path.join(data_dir, "bode_plots")
        self.rb_fitting_dir = os.path.join(data_dir, "rb_fitting")
        self.conductivity_dir = os.path.join(data_dir, "conductivity")
        
        for dir_path in [data_dir, self.eis_data_dir, self.bode_plots_dir, 
                        self.rb_fitting_dir, self.conductivity_dir]:
            os.makedirs(dir_path, exist_ok=True)
        
        # CHI测量参数
        self.chi_params = chi_params or {
            "material": "Sample",
            "T": "298",
            "highf": "10000",
            "lowf": "1",
            "initV": "0",
            "your_position": self.eis_data_dir,
            "your_type_text": "Text Files",
            "template_dir": os.path.join(current_dir, "templates"),
            "text_confidence": 70,
            "delay": 0.1
        }
        
        # 工作流状态
        self.workflow_active = False
        self.phase_transition_detected = False
        self.phase_transition_range = None
        self.fine_measurement_completed = False
        
        # 数据记录
        self.measurement_history = []
        self.phase_transition_points = []
        self.current_measurement = None
        
        # 实时监控
        self.monitoring_queue = queue.Queue()
        self.monitoring_thread = None
        self.is_monitoring = False
        
        # 初始化温控器
        self.controller = None
        self._init_controller()
        
        print(f"工作流系统初始化完成")
        print(f"温度范围: {T_start}°C → {T_end}°C")
        print(f"粗测步长: {coarse_step}°C, 精细步长: {fine_step}°C")
        print(f"数据存储: {data_dir}")

    def _init_controller(self):
        """初始化温控器"""
        try:
            # 首先确保设备开机
            print(f"🔌 确保设备 {self.port} 开机...")
            if not self._ensure_device_power_on():
                print(f"⚠️ 设备 {self.port} 开机失败，尝试继续初始化...")
            
            self.controller = EnhancedRefrigeratorController(
                port=self.port,
                T_start=self.T_start,
                T_end=self.T_end,
                eps=self.eps,
                coarse_step=self.coarse_step,
                fine_step=self.fine_step,
                thickness=self.thickness,
                area=self.area,
                data_dir=self.data_dir,
                chi_params=self.chi_params
            )
            print("温控器初始化成功")
        except Exception as e:
            print(f"温控器初始化失败: {e}")
            self.controller = None
    
    def _ensure_device_power_on(self) -> bool:
        """确保设备开机"""
        try:
            import serial
            import time
            
            print(f"🔌 正在确保设备 {self.port} 开机...")
            
            # 尝试打开串口
            ser = serial.Serial(
                port=self.port,
                baudrate=19200,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_TWO,
                timeout=0.1
            )
            
            # 检查设备是否已经开机
            if self._check_device_status(ser):
                print(f"✅ 设备 {self.port} 已经开机")
                ser.close()
                return True
            
            # 发送开机命令
            cmd = bytes.fromhex('A5 5A 06 83 50 00 01 00 01')
            ser.write(cmd)
            time.sleep(2)
            
            # 检查响应
            if ser.in_waiting > 0:
                resp = ser.read(8)
                expected_resp = bytes.fromhex('A5 5A 05 82 01 30 00 01')
                
                if resp == expected_resp:
                    print(f"✅ 设备 {self.port} 开机成功")
                    ser.close()
                    return True
                else:
                    print(f"⚠️ 设备 {self.port} 开机响应异常: {resp.hex()}")
            
            ser.close()
            return False
            
        except serial.SerialException as e:
            print(f"❌ 串口 {self.port} 连接失败: {e}")
            return False
        except Exception as e:
            print(f"❌ 设备开机过程异常: {e}")
            return False
    
    def _check_device_status(self, ser) -> bool:
        """检查设备状态"""
        try:
            # 尝试读取温度数据来检查设备是否在线
            start_time = time.time()
            while time.time() - start_time < 3:  # 3秒超时
                if ser.in_waiting > 0:
                    data = ser.read(ser.in_waiting)
                    if len(data) > 0:
                        print(f"✅ 设备 {self.port} 在线，检测到数据")
                        return True
                time.sleep(0.1)
            
            print(f"⚠️ 设备 {self.port} 无数据响应")
            return False
            
        except Exception as e:
            print(f"❌ 检查设备 {self.port} 状态失败: {e}")
            return False

    def start_workflow(self):
        """启动完整工作流"""
        if self.workflow_active:
            print("工作流已在运行中")
            return False
        
        if not self.controller:
            print("温控器未初始化，无法启动工作流")
            return False
        
        self.workflow_active = True
        print("启动集成相变点检测工作流...")
        
        try:
            # 启动实时监控
            self.start_monitoring()
            
            # 执行主工作流
            self._execute_main_workflow()
            
            return True
            
        except Exception as e:
            print(f"工作流执行失败: {e}")
            self.workflow_active = False
            return False
        finally:
            self.stop_monitoring()

    def _execute_main_workflow(self):
        """执行主工作流"""
        print("=== 开始主工作流 ===")
        
        # 1. 初始温度测量
        print(f"1. 初始温度测量: {self.T_start}°C")
        self._perform_measurement_at_temperature(self.T_start)
        
        # 2. 粗测降温循环
        current_temp = self.T_start
        while current_temp > self.T_end:
            # 计算下一个目标温度
            next_temp = max(current_temp - self.coarse_step, self.T_end)
            print(f"\n2. 粗测降温: {current_temp}°C → {next_temp}°C")
            
            # 设置温度并等待稳定
            self._set_temperature_and_wait(next_temp)
            
            # 执行测量
            measurement_result = self._perform_measurement_at_temperature(next_temp)
            
            # 检查相变点
            if self._check_phase_transition(measurement_result):
                print(f"⚠️ 检测到相变点！温度区间: {self.phase_transition_range}")
                self._handle_phase_transition()
                break
            
            current_temp = next_temp
        
        # 3. 完成工作流
        print("=== 主工作流完成 ===")
        self._generate_final_report()

    def _perform_measurement_at_temperature(self, temperature: float) -> Dict:
        """在指定温度下执行完整测量"""
        print(f"在温度 {temperature}°C 执行测量...")
        
        # 1. 等待温度稳定
        self._wait_for_temperature_stable(temperature)
        
        # 2. 执行CHI测量
        chi_result = self._execute_chi_measurement(temperature)
        
        # 3. 处理EIS数据
        eis_result = self._process_eis_data(temperature, chi_result)
        
        # 4. 生成Bode图
        self._generate_bode_plots(temperature, eis_result)
        
        # 5. 执行Rb拟合
        rb_result = self._perform_rb_fitting(temperature, eis_result)
        
        # 6. 计算电导率
        conductivity = self._calculate_conductivity(rb_result)
        
        # 7. 保存测量结果
        measurement_result = {
            'temperature': temperature,
            'timestamp': time.time(),
            'chi_result': chi_result,
            'eis_result': eis_result,
            'rb_result': rb_result,
            'conductivity': conductivity,
            'phase_jump_detected': eis_result.get('phase_jump_detected', False)
        }
        
        self.measurement_history.append(measurement_result)
        self.current_measurement = measurement_result
        
        print(f"温度 {temperature}°C 测量完成")
        print(f"  - Rb: {rb_result.get('rb', 'N/A'):.2f} Ω")
        print(f"  - 电导率: {conductivity:.4e} S/cm")
        print(f"  - 相变检测: {'是' if measurement_result['phase_jump_detected'] else '否'}")
        
        return measurement_result

    def _execute_chi_measurement(self, temperature: float) -> Dict:
        """执行CHI测量"""
        print(f"执行CHI测量 (温度: {temperature}°C)...")
        
        try:
            # 更新CHI参数
            chi_params = self.chi_params.copy()
            chi_params['T'] = str(int(temperature))
            chi_params['material'] = f"Sample_T{int(temperature)}"
            
            # 执行CHI测量
            result = run_chi_measurement(**chi_params)
            
            # 检查测量结果
            success_count = sum(1 for success, _ in result.values() if success)
            total_count = len(result)
            success_rate = (success_count / total_count) * 100
            
            print(f"CHI测量完成 - 成功率: {success_rate:.1f}%")
            
            return {
                'success_rate': success_rate,
                'steps': result,
                'temperature': temperature,
                'timestamp': time.time()
            }
            
        except Exception as e:
            print(f"CHI测量失败: {e}")
            return {
                'success_rate': 0,
                'error': str(e),
                'temperature': temperature,
                'timestamp': time.time()
            }

    def _process_eis_data(self, temperature: float, chi_result: Dict) -> Dict:
        """处理EIS数据"""
        print(f"处理EIS数据 (温度: {temperature}°C)...")
        
        try:
            # 模拟EIS数据处理（实际应用中需要从文件读取）
            # 这里生成模拟数据用于演示
            frequencies = np.logspace(0, 4, 50)  # 1-10000 Hz
            z_real = 100 + 50 * np.exp(-frequencies/1000) + np.random.normal(0, 2, 50)
            z_imag = -30 * np.exp(-frequencies/500) + np.random.normal(0, 1, 50)
            
            # 数据滤波
            freq_filtered, zreal_filtered, zimag_filtered = filter_data(
                frequencies, z_real, z_imag
            )
            
            # 检测相位突变
            phase_jump_detected = detect_phase_jump(zreal_filtered, zimag_filtered, threshold=20)
            
            result = {
                'temperature': temperature,
                'frequencies': frequencies,
                'z_real': z_real,
                'z_imag': z_imag,
                'filtered': {
                    'frequencies': freq_filtered,
                    'z_real': zreal_filtered,
                    'z_imag': zimag_filtered
                },
                'phase_jump_detected': phase_jump_detected
            }
            
            print(f"EIS数据处理完成 - 相位突变检测: {'是' if phase_jump_detected else '否'}")
            return result
            
        except Exception as e:
            print(f"EIS数据处理失败: {e}")
            return {
                'temperature': temperature,
                'error': str(e),
                'phase_jump_detected': False
            }

    def _generate_bode_plots(self, temperature: float, eis_result: Dict):
        """生成Bode图"""
        print(f"生成Bode图 (温度: {temperature}°C)...")
        
        try:
            if 'error' in eis_result:
                print("EIS数据有错误，跳过Bode图生成")
                return
            
            # 创建数据字典用于Bode图绘制
            data_dict = {
                temperature: {
                    'Freq': eis_result['frequencies'],
                    'Zreal': eis_result['z_real'],
                    'Zimag': eis_result['z_imag']
                }
            }
            
            # 生成Bode图
            plot_bode_diagrams(data_dict, self.bode_plots_dir)
            
            print(f"Bode图已保存到: {self.bode_plots_dir}")
            
        except Exception as e:
            print(f"Bode图生成失败: {e}")

    def _perform_rb_fitting(self, temperature: float, eis_result: Dict) -> Dict:
        """执行Rb拟合"""
        print(f"执行Rb拟合 (温度: {temperature}°C)...")
        
        try:
            if 'error' in eis_result:
                print("EIS数据有错误，跳过Rb拟合")
                return {'rb': 100, 'method': '默认值', 'error': 'EIS数据错误'}
            
            # 获取拟合参数
            fit_params = {
                'linear_threshold': 0.8,
                'linear_progressive_threshold': 0.7,
                'circle_linear_threshold': 0.6,
                'relaxed_threshold': 0.5,
                'max_remove_ratio': 0.3,
                'huber_tau': 0.1,
                'circle_max_iter': 50,
                'circle_tol': 1e-6
            }
            
            # 执行Rb拟合
            rb_result = calculate_rb(
                eis_result['filtered']['z_real'],
                eis_result['filtered']['z_imag'],
                temperature,
                fit_params
            )
            
            # 生成拟合可视化
            self._generate_rb_fitting_plot(temperature, eis_result, rb_result)
            
            print(f"Rb拟合完成 - 方法: {rb_result.get('method', '未知')}")
            return rb_result
            
        except Exception as e:
            print(f"Rb拟合失败: {e}")
            return {'rb': 100, 'method': '拟合失败', 'error': str(e)}

    def _generate_rb_fitting_plot(self, temperature: float, eis_result: Dict, rb_result: Dict):
        """生成Rb拟合图"""
        try:
            if 'error' in eis_result or 'error' in rb_result:
                return
            
            # 调用可视化函数
            visualize_fitting(
                eis_result['filtered']['z_real'],
                eis_result['filtered']['z_imag'],
                rb_result,
                self.rb_fitting_dir
            )
            
            print(f"Rb拟合图已保存到: {self.rb_fitting_dir}")
            
        except Exception as e:
            print(f"Rb拟合图生成失败: {e}")

    def _calculate_conductivity(self, rb_result: Dict) -> float:
        """计算电导率"""
        try:
            rb = rb_result.get('rb', 100)
            conductivity = calculate_conductivity(rb, self.thickness, self.area)
            return conductivity
            
        except Exception as e:
            print(f"电导率计算失败: {e}")
            return 0.0

    def _check_phase_transition(self, measurement_result: Dict) -> bool:
        """检查是否检测到相变点"""
        # 检查相位突变
        if measurement_result.get('phase_jump_detected', False):
            return True
        
        # 检查Rb拟合方法（圆弧拟合可能表示相变）
        rb_result = measurement_result.get('rb_result', {})
        if rb_result.get('method') == '圆弧拟合':
            return True
        
        # 检查电导率突变
        conductivity = measurement_result.get('conductivity', 0)
        if conductivity > 0:
            # 与历史数据比较
            if len(self.measurement_history) > 1:
                prev_conductivity = self.measurement_history[-2].get('conductivity', 0)
                if prev_conductivity > 0:
                    change_ratio = abs(conductivity - prev_conductivity) / prev_conductivity
                    if change_ratio > 0.5:  # 电导率变化超过50%
                        return True
        
        return False

    def _handle_phase_transition(self):
        """处理相变点精细化测量"""
        if not self.phase_transition_detected:
            return
        
        print("=== 启动相变点精细化测量 ===")
        
        # 确定相变区间
        if len(self.measurement_history) >= 2:
            prev_temp = self.measurement_history[-2]['temperature']
            current_temp = self.current_measurement['temperature']
            self.phase_transition_range = (max(prev_temp, current_temp), min(prev_temp, current_temp))
        
        if not self.phase_transition_range:
            print("无法确定相变区间")
            return
        
        T_high, T_low = self.phase_transition_range
        print(f"相变区间: [{T_high}°C, {T_low}°C]")
        
        # 执行精细化测量
        self._execute_fine_measurement(T_high, T_low)
        
        # 标记相变点已处理
        self.phase_transition_detected = False
        self.fine_measurement_completed = True
        
        print("=== 相变点精细化测量完成 ===")

    def _execute_fine_measurement(self, T_high: float, T_low: float):
        """执行精细化测量"""
        print(f"执行精细化测量: {T_high}°C → {T_low}°C (步长: {self.fine_step}°C)")
        
        # 升温到相变区上限
        print(f"升温到 {T_high}°C...")
        self._set_temperature_and_wait(T_high)
        
        # 精细化降温测量
        current_temp = T_high
        while current_temp > T_low:
            next_temp = max(current_temp - self.fine_step, T_low)
            print(f"精细化测量: {current_temp}°C → {next_temp}°C")
            
            # 设置温度并等待稳定
            self._set_temperature_and_wait(next_temp)
            
            # 执行测量
            measurement_result = self._perform_measurement_at_temperature(next_temp)
            
            # 记录精细化测量点
            measurement_result['measurement_type'] = 'fine'
            measurement_result['phase_transition_range'] = self.phase_transition_range
            
            current_temp = next_temp
        
        print("精细化测量完成")

    def _set_temperature_and_wait(self, target_temp: float):
        """设置温度并等待稳定"""
        if not self.controller:
            print("温控器不可用，跳过温度设置")
            return
        
        print(f"设置温度: {target_temp}°C")
        self.controller.set_temperature(target_temp)
        self._wait_for_temperature_stable(target_temp)

    def _wait_for_temperature_stable(self, target_temp: float, timeout: int = 1800):
        """等待温度稳定"""
        if not self.controller:
            print("温控器不可用，跳过温度等待")
            return
        
        print(f"等待温度稳定到 {target_temp}°C...")
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            current_temp = self.controller.read_temperature()
            if current_temp is not None:
                print(f"当前温度: {current_temp:.1f}°C, 目标: {target_temp}°C")
                
                # 检查是否达到目标温度（考虑容差）
                if abs(current_temp - target_temp) <= self.eps:
                    print(f"温度已稳定到 {target_temp}°C")
                    return True
            
            time.sleep(10)  # 每10秒检查一次
        
        print("温度稳定等待超时")
        return False

    def start_monitoring(self):
        """启动实时监控"""
        if self.is_monitoring:
            return
        
        self.is_monitoring = True
        self.monitoring_thread = threading.Thread(target=self._monitoring_worker)
        self.monitoring_thread.daemon = True
        self.monitoring_thread.start()
        print("实时监控已启动")

    def stop_monitoring(self):
        """停止实时监控"""
        self.is_monitoring = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5)
        print("实时监控已停止")

    def _monitoring_worker(self):
        """监控工作线程"""
        while self.is_monitoring:
            try:
                if self.controller:
                    current_temp = self.controller.read_temperature()
                    if current_temp is not None:
                        monitoring_data = {
                            'timestamp': time.time(),
                            'temperature': current_temp,
                            'workflow_status': 'active' if self.workflow_active else 'idle',
                            'phase_transition_detected': self.phase_transition_detected
                        }
                        self.monitoring_queue.put(monitoring_data)
                
                time.sleep(5)  # 每5秒更新一次
                
            except Exception as e:
                print(f"监控线程错误: {e}")
                time.sleep(10)

    def get_monitoring_data(self) -> List[Dict]:
        """获取监控数据"""
        data = []
        while not self.monitoring_queue.empty():
            try:
                data.append(self.monitoring_queue.get_nowait())
            except queue.Empty:
                break
        return data

    def _generate_final_report(self):
        """生成最终报告"""
        print("生成最终实验报告...")
        
        # 收集数据
        temperatures = [m['temperature'] for m in self.measurement_history]
        conductivities = [m.get('conductivity', 0) for m in self.measurement_history]
        rb_values = [m.get('rb_result', {}).get('rb', 0) for m in self.measurement_history]
        
        # 生成电导率图
        if len(temperatures) > 1:
            plot_path = os.path.join(self.conductivity_dir, "conductivity_vs_temperature.png")
            plot_conductivity_vs_temperature(temperatures, conductivities, plot_path)
        
        # 生成报告
        report = {
            'experiment_info': {
                'start_time': datetime.now().isoformat(),
                'temperature_range': f"{self.T_start}°C → {self.T_end}°C",
                'coarse_step': self.coarse_step,
                'fine_step': self.fine_step,
                'sample_thickness': self.thickness,
                'sample_area': self.area
            },
            'measurement_summary': {
                'total_measurements': len(self.measurement_history),
                'coarse_measurements': len([m for m in self.measurement_history if m.get('measurement_type') != 'fine']),
                'fine_measurements': len([m for m in self.measurement_history if m.get('measurement_type') == 'fine']),
                'phase_transitions_detected': len(self.phase_transition_points)
            },
            'phase_transitions': self.phase_transition_points,
            'measurements': self.measurement_history
        }
        
        # 保存报告
        report_path = os.path.join(self.data_dir, "experiment_report.json")
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"实验报告已保存: {report_path}")
        print("=== 工作流完成 ===")

    def get_status(self) -> Dict:
        """获取工作流状态"""
        return {
            'workflow_active': self.workflow_active,
            'phase_transition_detected': self.phase_transition_detected,
            'phase_transition_range': self.phase_transition_range,
            'fine_measurement_completed': self.fine_measurement_completed,
            'measurement_count': len(self.measurement_history),
            'current_temperature': self.controller.read_temperature() if self.controller else None,
            'is_monitoring': self.is_monitoring
        }

    def stop_workflow(self):
        """停止工作流"""
        self.workflow_active = False
        self.stop_monitoring()
        if self.controller:
            self.controller.close_serial()
        print("工作流已停止")


# ==================== 全局工作流实例 ====================
_global_workflow = None

def get_global_workflow() -> Optional[IntegratedPhaseTransitionWorkflow]:
    """获取全局工作流实例"""
    return _global_workflow

def create_global_workflow(**kwargs) -> IntegratedPhaseTransitionWorkflow:
    """创建全局工作流实例"""
    global _global_workflow
    if _global_workflow:
        _global_workflow.stop_workflow()
    
    _global_workflow = IntegratedPhaseTransitionWorkflow(**kwargs)
    return _global_workflow


if __name__ == "__main__":
    # 配置参数
    CONFIG = {
        'port': 'COM3',
        'T_start': 20.0,
        'T_end': -30.0,
        'coarse_step': 10.0,
        'fine_step': 3.0,
        'eps': 1.0,
        'thickness': 0.001,
        'area': 1e-4,
        'data_dir': "experiment_data"
    }
    
    print("=== 集成相变点检测工作流系统 ===")
    print(f"配置参数: {CONFIG}")
    
    try:
        # 创建并启动工作流
        workflow = create_global_workflow(**CONFIG)
        success = workflow.start_workflow()
        
        if success:
            print("工作流执行成功")
        else:
            print("工作流执行失败")
            
    except Exception as e:
        print(f"程序运行出错: {str(e)}")
    finally:
        # 确保程序结束时清理资源
        if _global_workflow:
            _global_workflow.stop_workflow() 