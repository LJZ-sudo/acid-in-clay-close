# -*- coding: utf-8 -*-
"""
智能自适应冰箱控制程序 - 改进版（无步长限制）
@author: YourName
"""

import serial
import time
import struct
import binascii
from collections import deque
from typing import Optional, Tuple
import random  # 用于模拟测量结果


class RefrigeratorController:
    def __init__(self, port: str, T_start: float, T_end: float, eps: float = 0.5):
        """
        初始化冰箱控制器
        :param port: 串口名称 (如 'COM3')
        :param T_start: 起始温度 (°C)
        :param T_end: 目标温度 (°C)
        :param eps: 温度误差容限 (°C)
        """
        self.ser = self._initialize_serial(port)
        self.T_start = T_start
        self.T_end = T_end
        self.eps = eps
        self.current_target = T_start
        self.measurement_results = []  # 存储测量结果历史
        self.last_fit_type = None  # 上次拟合类型
        self.recovery_mode = False  # 是否处于回温模式
        self.adjusted_target = None  # 调整后的目标温度
        self.special_cooling_count = 0  # 特殊降温计数

        # 设备状态
        self.power_on = False
        self.current_temp = None
        self.buffer = bytearray()
        self.frame_queue = deque()

    def _initialize_serial(self, port: str) -> serial.Serial:
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

    def run_cooling_procedure(self):
        """执行完整的降温控制流程"""
        if not self.send_power_on():
            print("无法开机，退出流程")
            self.close_serial()
            return

        # 初始温度设置
        self.set_temperature(self.T_start)
        print(f"初始目标温度: {self.current_target}°C")

        # 主控制循环
        while self.current_target > self.T_end:
            if not self.recovery_mode:
                # 正常降温模式 - 动态计算主步长
                step = 10  # 默认步长
            else:
                # 回温后的特殊降温模式
                if self.special_cooling_count < 2:
                    step = 3  # 前两次特殊降温
                else:
                    # 第三次开始按T-10的剩余温差
                    step = self.adjusted_target - self.current_target
                print(f"特殊降温模式[{self.special_cooling_count}]，步长: {step}°C")

            # 执行降温段
            self.execute_cooling_segment(step)

        print(f"\n最终温度 {self.T_end}°C 已达成，流程结束")
        self.close_serial()

    def execute_cooling_segment(self, main_step: float):
        """执行一个降温段"""
        print(f"\n=== 开始新降温段 ===")
        print(f"当前目标: {self.current_target}°C → {self.current_target - main_step}°C")

        # 计算分段点 (80%位置)
        split_point = self.current_target - main_step * 0.8

        # 逐步降温
        temp_target = self.current_target
        while temp_target > (self.current_target - main_step):
            # 获取动态步长（统一规则：前80%用2°C，后20%用1°C）
            D = 2 if temp_target > split_point else 1
            next_target = max(temp_target - D, self.current_target - main_step, self.T_end)

            # 设置温度并等待稳定
            self.set_temperature(next_target)
            recovery_phase = (next_target <= split_point)  # 后20%开启回温检测
            self.wait_for_temperature_drop(next_target, recovery_phase)

            temp_target = next_target

        # 更新当前目标温度
        self.current_target = max(self.current_target - main_step, self.T_end)

        # 执行测量并处理结果
        fit_type = self.perform_measurement()
        self.process_measurement_result(fit_type)

    def process_measurement_result(self, fit_type: int):
        """
        处理测量结果并调整降温策略
        :param fit_type: 测量返回的拟合类型
        """
        current_temp = self.read_temperature()
        if current_temp is None:
            print("无法读取当前温度，跳过本次结果处理")
            return

        if not self.measurement_results:  # 第一次测量
            self.measurement_results.append(fit_type)
            self.last_fit_type = fit_type
            return

        print(f"测量结果比对: 前次={self.last_fit_type}, 本次={fit_type}")

        if fit_type == self.last_fit_type:
            # 结果相同 - 继续正常模式
            self.recovery_mode = False
            self.adjusted_target = None
            self.special_cooling_count = 0
            print("拟合类型未变化，继续正常降温模式")
        else:
            # 结果不同 - 进入回温模式
            self.recovery_mode = True
            self.adjusted_target = current_temp - 10
            self.special_cooling_count = 0  # 重置特殊降温计数

            print(f"拟合类型变化，进入回温模式: {current_temp}°C → {current_temp + 10}°C")

            # 执行回温
            self.execute_recovery_phase(current_temp)

        self.last_fit_type = fit_type
        self.measurement_results.append(fit_type)

        # 特殊降温计数
        if self.recovery_mode:
            self.special_cooling_count += 1

    def execute_recovery_phase(self, current_temp: float):
        """执行回温阶段"""
        print("\n=== 开始回温阶段 ===")
        recovery_target = current_temp + 10
        print(f"回温目标: {current_temp}°C → {recovery_target}°C")

        # 设置回温温度
        self.set_temperature(recovery_target)
        self.wait_for_temperature_drop(recovery_target, recovery_phase=False)  # 回温时不检测回升

        # 更新当前目标
        self.current_target = recovery_target
        print("回温完成，准备特殊降温流程")

    def perform_measurement(self) -> int:
        """
        执行测量并返回拟合类型
        :return: 拟合类型 (示例用随机数模拟)
        """
        print("\n>>> 开始测量 <<<")
        current_temp = self.read_temperature()
        print(f"当前温度: {current_temp:.1f}°C")

        # 模拟3分钟测量过程
        for remaining in range(3, 0, -1):  # 缩短为3秒便于测试
            print(f"\r测量中... 剩余时间: {remaining}秒", end='')
            time.sleep(1)
        print("\n测量完成")

        # 模拟返回拟合类型 (实际应替换为您的测量函数)
        fit_type = random.choice([1, 2, 3])  # 示例: 随机返回1/2/3
        print(f"测量返回拟合类型: {fit_type}")
        return fit_type

    # 以下是需要您实现的硬件控制方法
    def send_power_on(self) -> bool:
        """发送开机指令（需实现）"""
        cmd = bytes.fromhex('A5 5A 06 83 50 00 01 00 01')
        self.ser.write(cmd)
        time.sleep(2)
        return True

    def set_temperature(self, temp: float) -> bool:
        """设置目标温度（需实现）"""
        temp_int = int(temp * 10)
        if temp_int < 0:
            temp_int = (1 << 16) + temp_int
        cmd = bytes([0xA5, 0x5A, 0x06, 0x83, 0x00, 0x26, 0x01,
                     (temp_int >> 8) & 0xFF, temp_int & 0xFF])
        self.ser.write(cmd)
        return True

    def wait_for_temperature_drop(self, target_temp: float, recovery_phase: bool = False) -> bool:
        """等待温度稳定（需实现）"""
        print(f"等待稳定到{target_temp}°C (检测回温: {'是' if recovery_phase else '否'})")
        time.sleep(2)  # 模拟等待
        return True

    def read_temperature(self) -> Optional[float]:
        """读取当前温度（需实现）"""
        # 模拟返回当前目标温度±随机波动
        if self.current_target is None:
            return None
        return self.current_target + random.uniform(-0.5, 0.5)

    def close_serial(self):
        """关闭串口"""
        if self.ser and self.ser.is_open:
            self.ser.close()


if __name__ == "__main__":
    # 配置参数 - 请根据您的实际串口号修改
    PORT = 'COM3'  # 串口号，请检查设备管理器确认实际串口号
    INITIAL_TEMP = -20.0  # 起始温度 (°C)
    TARGET_TEMP = -80.0  # 目标温度 (°C)

    print("启动改进版降温控制程序")
    print(f"起始温度: {INITIAL_TEMP}°C")
    print(f"目标温度: {TARGET_TEMP}°C")

    try:
        controller = RefrigeratorController(PORT, INITIAL_TEMP, TARGET_TEMP)
        controller.run_cooling_procedure()
    except Exception as e:
        print(f"程序运行出错: {str(e)}")