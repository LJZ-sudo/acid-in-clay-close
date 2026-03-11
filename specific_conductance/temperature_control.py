# -*- coding: utf-8 -*-
"""
模块化温控系统 - 支持相变点精细测量
@author: 25862
"""

import serial
import time
import binascii
import queue
from collections import deque
import json
import os
import matplotlib.pyplot as plt
from datetime import datetime

# 导入同学A的分析模块
try:
    import tongxuea  # 同学A的数据分析模块
    print("成功导入同学A的分析模块")
except ImportError:
    print("警告: 无法导入同学A的分析模块")
    # 创建空模块避免崩溃
    class tongxuea:
        @staticmethod
        def analyze_eis_data(eis_data, current_temp):
            """
            同学A的数据分析接口
            参数:
                eis_data: EIS测量数据字典
                current_temp: 当前温度(°C)
            返回:
                phase_transition_range: 相变温度区间元组 (T_high, T_low) 或 None
            """
            print("使用模拟的同学A分析函数")
            return None

# 全局消息队列, 用于接收同学A发现的相变点信息
phase_transition_queue = queue.Queue()

class RefrigeratorController:
    def __init__(self, port, T_start, T_end, eps, step_size=10,
                 thickness=0.001, area=1e-4, data_dir="experiment_data",
                 chi_params=None):
        """
        初始化温度控制器
        :param port: 串口名称
        :param T_start: 起始温度 (°C)
        :param T_end: 目标温度 (°C)
        :param eps: 温度误差容限 (°C)
        :param step_size: 降温步长 (°C)
        :param thickness: 样品厚度 (m)
        :param area: 样品截面积 (m²)
        :param data_dir: 数据存储目录
        :param chi_params: CHI测量参数
        """
        self.port = port
        self.ser = None
        self.initialize_serial()
        
        # 温度参数
        self.T_start = T_start
        self.T_end = T_end
        self.eps = eps
        self.base_step_size = step_size
        self.T_tar = T_start
        
        # 样品参数
        self.thickness = thickness
        self.area = area
        
        # 实验数据记录
        self.data_dir = data_dir
        self.measurement_history = []
        self.temperature_history = []
        self.phase_transition_points = []
        os.makedirs(data_dir, exist_ok=True)
        
        # 状态标志
        self.power_on = False
        self.current_temp = None
        self.fine_measuring = False
        self.phase_transition_range = None
        
        # 串口数据缓冲区
        self.buffer = bytearray()
        self.frame_queue = deque()

    def initialize_serial(self):
        """初始化串口连接"""
        try:
            self.ser = serial.Serial(
                port=self.port,
                baudrate=19200,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_TWO,
                timeout=0.1
            )
            print(f"已成功打开串口 {self.port}")
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
        except serial.SerialException as e:
            print(f"无法打开串口 {self.port}: {str(e)}")
            raise

    def check_phase_transition(self):
        """检查同学A是否发送了相变点信息"""
        try:
            if not phase_transition_queue.empty():
                self.phase_transition_range = phase_transition_queue.get_nowait()
                print(f"收到相变点信息: {self.phase_transition_range}")
                return True
        except queue.Empty:
            pass
        return False

    def handle_phase_transition(self):
        """处理相变点精细测量流程"""
        if not self.phase_transition_range:
            return False
            
        T_high, T_low = self.phase_transition_range
        print(f"启动相变点精细测量: [{T_high}°C, {T_low}°C]")
        
        # 被动升温到相变区上限
        print("等待被动升温到相变区上限...")
        if not self.wait_for_passive_warm_up(T_high):
            print("升温失败, 继续原流程")
            return False
        
        # 保存原始目标温度
        original_T_end = self.T_end
        
        # 执行精细测量流程
        self.fine_measuring = True
        self.execute_fine_measurement(T_high, T_low)
        
        # 恢复原始状态
        self.fine_measuring = False
        self.T_end = original_T_end
        self.phase_transition_range = None
        
        print("相变点精细测量完成")
        return True

    def wait_for_passive_warm_up(self, target_temp, timeout=36000):
        """等待被动升温到目标温度(10小时超时)"""
        print(f"等待温度回升到 {target_temp}°C (被动升温)...")
        start_time = time.time()
        
        # 记录升温开始温度
        start_temp = self.current_temp if self.current_temp is not None else target_temp - 20
        print(f"升温起始温度: {start_temp:.1f}°C")
        
        while time.time() - start_time < timeout:
            current_temp = self.read_temperature()
            if current_temp is None:
                time.sleep(1)
                continue
                
            print(f"当前温度: {current_temp:.1f}°C, 目标: {target_temp}°C")
            
            # 检查是否达到目标温度(考虑容差)
            if current_temp >= target_temp - self.eps:
                print(f"已达到升温目标 {target_temp}°C")
                return True
                
            time.sleep(10)  # 每10秒检查一次
            
        print("升温超时")
        return False

    def execute_fine_measurement(self, T_high, T_low):
        """执行精细测量流程(3°C步长)"""
        # 设置精细测量参数
        self.T_tar = T_high
        self.T_end = T_low
        fine_step_size = 3
        
        print(f"开始精细测量: {T_high}°C → {T_low}°C (步长 3°C)")
        
        # 使用3度步长进行降温测量
        self.run_cooling_procedure(step_size=fine_step_size)

    def send_power_on(self):
        """发送开机指令并验证回复"""
        if self.power_on:
            print("设备已开机, 跳过开机指令")
            return True

        cmd = bytes.fromhex('A5 5A 06 83 50 00 01 00 01')
        self.ser.write(cmd)
        print(f"已发送开机指令: {cmd.hex().upper()}")

        time.sleep(2)

        responses = []
        while self.ser.in_waiting > 0:
            resp = self.ser.read(8)
            responses.append(resp)
            print(f"收到响应: {resp.hex().upper()}")

        expected_resp = bytes.fromhex('A5 5A 05 82 01 30 00 01')
        for resp in responses:
            if resp == expected_resp:
                print("开机成功")
                self.power_on = True
                return True

        print(f"开机失败, 未收到预期回复。期望: {expected_resp.hex().upper()}")
        return False

    def set_temperature(self, temp):
        """设置冰箱制冷温度"""
        temp_int = int(temp * 10)
        if temp_int < 0:
            temp_int = (1 << 16) + temp_int

        high_byte = (temp_int >> 8) & 0xFF
        low_byte = temp_int & 0xFF
        cmd = bytes([0xA5, 0x5A, 0x06, 0x83, 0x00, 0x26, 0x01, high_byte, low_byte])

        for i in range(3):
            self.ser.write(cmd)
            print(f"已发送温度设置指令({i + 1}/3): {cmd.hex().upper()} (目标温度: {temp}°C)")
            time.sleep(0.2)

        self.ser.reset_input_buffer()
        self.buffer = bytearray()
        time.sleep(0.5)
        return True

    def process_buffer(self):
        """处理串口缓冲区中的数据, 提取完整帧"""
        while len(self.buffer) >= 2:
            start_pos = -1
            for i in range(len(self.buffer) - 1):
                if self.buffer[i] == 0xA5 and self.buffer[i + 1] == 0x5A:
                    start_pos = i
                    break

            if start_pos == -1:
                if len(self.buffer) > 1:
                    self.buffer = self.buffer[-1:]
                return

            if start_pos > 0:
                discarded = self.buffer[:start_pos]
                print(f"丢弃无效数据: {binascii.hexlify(discarded).decode().upper()}")
                self.buffer = self.buffer[start_pos:]

            if len(self.buffer) < 3:
                return

            data_length = self.buffer[2]
            total_length = 3 + data_length

            if len(self.buffer) < total_length:
                return

            frame = self.buffer[:total_length]
            self.buffer = self.buffer[total_length:]
            self.frame_queue.append(frame)
            self.process_buffer()
            return

    def read_temperature(self):
        """读取实时温度值(带超时)"""
        start_time = time.time()
        timeout = 30

        while self.frame_queue:
            frame = self.frame_queue.popleft()
            temperature = self.parse_frame(frame)
            if temperature is not None:
                # 记录温度历史
                self.temperature_history.append((time.time(), temperature))
                return temperature

        while time.time() - start_time < timeout:
            if self.ser.in_waiting > 0:
                data = self.ser.read(self.ser.in_waiting)
                self.buffer.extend(data)
                print(f"收到数据: {binascii.hexlify(data).decode().upper()}")
                self.process_buffer()

                while self.frame_queue:
                    frame = self.frame_queue.popleft()
                    temperature = self.parse_frame(frame)
                    if temperature is not None:
                        self.temperature_history.append((time.time(), temperature))
                        return temperature

            time.sleep(0.05)

        print("读取温度超时")
        return None

    def parse_frame(self, frame):
        """解析数据帧, 提取温度值"""
        try:
            hex_frame = binascii.hexlify(frame).decode().upper()
            if frame[0] != 0xA5 or frame[1] != 0x5A:
                return None

            data_length = frame[2]
            if len(frame) != 3 + data_length:
                return None

            param_type = (frame[4] << 8) | frame[5]
            if param_type == 0x0022:
                raw_value = (frame[6] << 8) | frame[7]
                if raw_value & 0x8000:
                    raw_value = -((raw_value ^ 0xFFFF) + 1)
                temperature = raw_value * 0.1
                self.current_temp = temperature
                print(f"解析到温度: {temperature}°C")
                return temperature
            
            print(f"收到非温度数据帧: 类型 0x{param_type:04X}")
            return None
        except Exception as e:
            print(f"解析帧错误: {str(e)}")
            return None

    def get_D(self, target_temp, step_size):
        """
        根据当前目标温度计算D值(分段降温步长)
        :param target_temp: 当前目标温度 (°C)
        :param step_size: 当前步长
        :return: D值 (温度变化步长)
        """
        if step_size == 3:
            return 1
        return 2 if target_temp >= -20 else 1

    def wait_for_temperature_drop(self, target_temp, recovery_phase=False):
        """等待温度下降到目标温度并稳定"""
        min_temp = float('inf')
        prev_temp = None
        start_time = time.time()

        print(f"等待温度稳定到 {target_temp}°C (模式: {'回升阶段' if recovery_phase else '快速降温'})")

        while time.time() - start_time < 3600:
            current_temp = self.read_temperature()
            if current_temp is None:
                time.sleep(0.5)
                continue

            print(f"当前温度: {current_temp:.1f}°C, 目标: {target_temp}°C")

            if current_temp < min_temp:
                min_temp = current_temp
                print(f"最低温度更新: {min_temp:.1f}°C")

            if not recovery_phase and current_temp <= target_temp:
                print(f"达到快速降温目标 {target_temp}°C")
                return True

            if recovery_phase:
                if prev_temp is not None and current_temp > prev_temp:
                    print(f"温度回升: {prev_temp:.1f}→{current_temp:.1f}°C")
                    if (current_temp < target_temp and 
                        abs(current_temp - target_temp) < 1.0):
                        print("满足测量条件, 启动测量...")
                        return True
                
                prev_temp = current_temp
            
            time.sleep(1)

        print("等待超时")
        return False

    def perform_measurement(self):
        """执行完整的测量流程"""
        print(">>> 开始执行测量函数 <<<")
        print(f"- 当前温度: {self.current_temp:.1f}°C")
        print(f"- 目标温度: {self.T_tar}°C")
        print(f"- 处于回升阶段")

        # 同学B的测量区域 - 实际EIS测量
        #######################################################################
        # ===================== 同学B的EIS测量接口区域 ===================== #
        # 此处由同学B实现电化学工作站控制代码
        #
        # 需要填充的变量:
        #   eis_data = {
        #       'frequencies': [1e6, 5e5, ...],  # 频率列表 (Hz)
        #       'z_real': [100, 98, ...],         # 实部阻抗列表 (Ω)
        #       'z_imag': [-5, -4.8, ...],        # 虚部阻抗列表 (Ω)
        #       'temperature': self.current_temp,  # 当前测量温度 (°C)
        #       'timestamp': time.time()           # 时间戳
        #   }
        #
        # 伪代码示例:
        #   eis_data = {
        #       'frequencies': [],
        #       'z_real': [],
        #       'z_imag': [],
        #       'temperature': self.current_temp,
        #       'timestamp': time.time()
        #   }
        #   
        #   # 初始化电化学工作站
        #   gamry_initialize()
        #   
        #   # 设置测量参数
        #   set_frequency_range(1e6, 1)  # 1MHz到1Hz
        #   set_amplitude(0.01)          # 10mV
        #   
        #   # 执行扫描
        #   start_time = time.time()
        #   while time.time() - start_time < 180:  # 3分钟
        #       data_point = acquire_data_point()
        #       eis_data['frequencies'].append(data_point.freq)
        #       eis_data['z_real'].append(data_point.z_real)
        #       eis_data['z_imag'].append(data_point.z_imag)
        #       time.sleep(0.1)
        # ================================================================ #
        print("执行EIS测量中...")
        eis_data = None  # 实际应由同学B的代码填充
        
        # 模拟EIS测量等待3分钟
        for remaining in range(180, 0, -1):
            # 实时显示温度
            current_temp = self.read_temperature()
            if current_temp is not None:
                print(f"\rEIS测量中... 剩余时间: {remaining}秒 | 当前温度: {current_temp:.1f}°C", end='', flush=True)
            else:
                print(f"\rEIS测量中... 剩余时间: {remaining}秒", end='', flush=True)
            time.sleep(1)
        print("\nEIS测量完成")

        # 调用同学A的分析函数
        #######################################################################
        # ===================== 同学A的数据分析接口调用 ===================== #
        # 调用同学A的模块分析EIS数据
        #
        # 参数要求:
        #   eis_data: 同学B提供的EIS数据字典
        #   current_temp: 当前测量温度
        #
        # 返回值:
        #   phase_transition_range: 相变温度区间 (T_high, T_low) 或 None
        # ================================================================ #
        print("调用同学A的分析模块...")
        if eis_data is not None:
            try:
                # 调用同学A的分析函数
                phase_transition_range = tongxuea.analyze_eis_data(
                    eis_data=eis_data,
                    current_temp=self.current_temp
                )
            except Exception as e:
                print(f"同学A的分析函数出错: {str(e)}")
                phase_transition_range = None
        else:
            print("无有效的EIS数据可供分析")
            phase_transition_range = None
        
        # 相变点处理
        #######################################################################
        # ===================== 相变点处理区域 ===================== #
        # 如果检测到相变点, 将信息加入队列
        if phase_transition_range is not None:
            T_high, T_low = phase_transition_range
            print(f"检测到相变区间: [{T_high}, {T_low}], 已加入队列")
            
            # 将相变信息加入全局队列
            phase_transition_queue.put((T_high, T_low))
            
            # 保存相变点信息
            self.phase_transition_points.append({
                'range': (T_high, T_low),
                'detected_at': self.current_temp,
                'timestamp': time.time()
            })
        
        print("测量与分析完成")
        
        # 保存测量结果
        self.measurement_history.append({
            'temperature': self.current_temp,
            'eis_data': eis_data,
            'time': time.time(),
            'step_type': 'fine' if self.fine_measuring else 'coarse',
            'phase_transition': phase_transition_range
        })
        
        # 实时保存数据
        self.save_experiment_data()

    def run_cooling_procedure(self, step_size=None):
        """主降温控制流程"""
        if step_size is None:
            step_size = self.base_step_size
            
        if not self.send_power_on():
            print("无法开机, 退出流程")
            self.ser.close()
            return

        self.set_temperature(self.T_tar)
        print(f"初始目标温度: {self.T_tar}°C")
        self.wait_for_temperature_drop(self.T_tar, recovery_phase=True)

        # 主降温循环
        while self.T_tar > self.T_end:
            # 检查并处理相变点
            if self.phase_transition_range:
                if self.handle_phase_transition():
                    continue
            
            print(f"\n开始降温步长: {step_size}°C (当前目标: {self.T_tar}°C, 最终目标: {self.T_end}°C)")
            split_point = self.T_tar - step_size * 0.8
            current_target = self.T_tar

            # 分段降温
            while current_target > (self.T_tar - step_size):
                D = self.get_D(current_target, step_size)
                next_target = max(current_target - D, self.T_tar - step_size, self.T_end)
                recovery_phase = (next_target <= split_point)

                self.set_temperature(next_target)
                print(f"设置分段目标温度: {next_target}°C (D={D}, {'后20%' if recovery_phase else '前80%'})")
                self.wait_for_temperature_drop(next_target, recovery_phase=recovery_phase)
                current_target = next_target

            # 完成整个步长
            self.T_tar = max(self.T_tar - step_size, self.T_end)
            print(f"完成降温步长, 当前目标温度: {self.T_tar}°C")
            
            # 等待稳定并测量
            self.wait_for_temperature_drop(self.T_tar, recovery_phase=True)
            self.perform_measurement()

        print(f"\n最终温度 {self.T_end}°C 已达成, 流程结束")
        self.save_experiment_report()
        self.ser.close()

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
            "step_size": self.base_step_size,
            "num_measurements": len(self.measurement_history),
            "phase_transitions": self.phase_transition_points,
            "final_status": "completed"
        }
        
        report_file = os.path.join(self.data_dir, "experiment_report.json")
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"实验报告已保存: {report_file}")

    def plot_temperature_profile(self):
        """绘制温度变化曲线"""
        if not self.temperature_history:
            print("无温度数据可绘制")
            return
        
        times, temps = zip(*self.temperature_history)
        timestamps = [t - times[0] for t in times]  # 转换为相对时间
        
        plt.figure(figsize=(12, 6))
        plt.plot(timestamps, temps, 'b-', label='实际温度')
        
        # 标记测量点
        meas_times = []
        meas_temps = []
        for meas in self.measurement_history:
            for t, temp in self.temperature_history:
                if abs(t - meas['time']) < 1:  # 找到测量时的温度
                    meas_times.append(t - times[0])
                    meas_temps.append(temp)
                    break
        
        plt.scatter(meas_times, meas_temps, c='red', s=50, label='测量点')
        
        # 标记相变点
        for phase in self.phase_transition_points:
            plt.axvline(x=phase['timestamp'] - times[0], color='g', linestyle='--', 
                       label=f"相变点 {phase['range']}")
        
        plt.xlabel('时间 (秒)')
        plt.ylabel('温度 (°C)')
        plt.title('温度变化曲线')
        plt.legend()
        plt.grid(True)
        
        # 保存图像
        plot_file = os.path.join(self.data_dir, "temperature_profile.png")
        plt.savefig(plot_file)
        print(f"温度曲线已保存: {plot_file}")
        plt.show()


# 程序入口
if __name__ == "__main__":
    # 配置参数(根据实际情况修改)
    PORT = 'COM6'       # 串口号
    T_START = -43       # 起始温度(°C)
    T_END = -80.0       # 目标温度(°C)
    EPS = 0.5           # 温度容差(°C)
    STEP_SIZE = 10      # 基础步长(°C)
    THICKNESS = 0.001   # 样品厚度(m)
    AREA = 1e-4         # 样品截面积(m²)
    DATA_DIR = "experiment_data"  # 数据存储目录

    print(f"启动模块化温控程序 (支持相变点精细测量)")
    print(f"起始温度: {T_START}°C, 目标温度: {T_END}°C")
    print(f"样品参数: 厚度={THICKNESS*1000}mm, 面积={AREA*1e4}cm²")
    
    try:
        # 创建控制器实例
        controller = RefrigeratorController(
            port=PORT,
            T_start=T_START,
            T_end=T_END,
            eps=EPS,
            step_size=STEP_SIZE,
            thickness=THICKNESS,
            area=AREA,
            data_dir=DATA_DIR
        )
        
        # 启动主控制流程
        controller.run_cooling_procedure()
        
        # 绘制温度曲线
        controller.plot_temperature_profile()
    except Exception as e:
        print(f"程序运行出错: {str(e)}")
    finally:
        # 确保程序结束时串口关闭
        if controller.ser and controller.ser.is_open:
            controller.ser.close()
            print("串口已关闭")