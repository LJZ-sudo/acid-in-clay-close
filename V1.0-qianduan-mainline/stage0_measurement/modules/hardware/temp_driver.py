# -*- coding: utf-8 -*-
"""
温度控制驱动（纯函数版）

独立的温度控制器驱动，只负责串口通信和基础温控操作

核心原则：
1. 独立初始化 - 只需串口参数，不依赖控制器状态
2. 原子操作 - 提供基础读写功能，不保存历史数据
3. 无业务回调 - 不触发任何外部回调，只返回结果
4. 标准错误字典 - 失败时返回规范格式

版本：3.0.0 (重构版)
"""

import time
import threading
from collections import deque
from typing import Optional, Tuple

import serial


# ============================================================
# 公共接口：温度驱动类
# ============================================================

class TemperatureDriver:
    """
    温度控制器驱动（纯函数版）
    
    独立的硬件驱动类，不依赖控制器状态，不保存历史数据
    """
    
    def __init__(
        self,
        port,
        baudrate=19200,
        timeout=0.1,
        temp_min=-120.0,
        temp_max=25.0
    ):
        """
        初始化温度驱动
        
        Args:
            port: 串口名称（如 'COM3'）
            baudrate: 波特率（默认 19200）
            timeout: 串口超时（秒）
            temp_min: 有效温度下限 (°C)
            temp_max: 有效温度上限 (°C)
        """
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.temp_min = temp_min
        self.temp_max = temp_max
        
        # 串口对象
        self.ser = None
        self.serial_lock = threading.Lock()
        
        # 帧解析缓冲区
        self.buffer = bytearray()
        self.frame_queue = deque(maxlen=100)
        
        # 连接串口
        self._connect()
    
    def _connect(self):
        """连接串口"""
        try:
            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_TWO,
                timeout=self.timeout
            )
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
        except serial.SerialException as e:
            raise ConnectionError(f'Failed to open serial port {self.port}: {e}')
    
    def close(self):
        """关闭串口连接"""
        if self.ser and self.ser.is_open:
            self.ser.close()
    
    def is_connected(self):
        """检查串口是否连接"""
        return self.ser and self.ser.is_open
    
    # ========================================================
    # 原子操作：读取温度
    # ========================================================
    
    def read_temperature(self):
        """
        读取当前温度（原子操作）
        
        Returns:
            dict: 包含以下字段
                - success: bool
                - temperature: float or None，温度 (°C)
                - error: str or None
        """
        if not self.is_connected():
            return {
                'success': False,
                'temperature': None,
                'error': 'Serial port not connected'
            }
        
        with self.serial_lock:
            try:
                # 清空所有缓冲区（软件+硬件）
                self.frame_queue.clear()
                self.buffer.clear()
                self.ser.reset_input_buffer()  # ✅ 关键修复：清空串口硬件接收缓冲区
                
                latest_temp = None
                start_time = time.time()
                
                # 读取数据，最多等待 5 秒
                while time.time() - start_time < 5.0:
                    if self.ser.in_waiting > 0:
                        data = self.ser.read(min(self.ser.in_waiting, 500))
                        self.buffer.extend(data)
                        self._process_buffer()
                        
                        # 解析所有帧，取最新温度
                        while self.frame_queue:
                            frame = self.frame_queue.popleft()
                            temp = self._parse_frame(frame)
                            if temp is not None:
                                latest_temp = temp
                        
                        if latest_temp is not None:
                            break
                    
                    time.sleep(0.1)
                
                if latest_temp is not None:
                    return {
                        'success': True,
                        'temperature': latest_temp,
                        'error': None
                    }
                else:
                    return {
                        'success': False,
                        'temperature': None,
                        'error': 'No valid temperature reading within timeout'
                    }
            
            except Exception as e:
                return {
                    'success': False,
                    'temperature': None,
                    'error': f'Failed to read temperature: {str(e)}'
                }
    
    # ========================================================
    # 原子操作：设置温度
    # ========================================================
    
    def set_temperature(self, target_temp, is_cooling=True, retries=3):
        """
        设置目标温度（原子操作）
        
        Args:
            target_temp: 目标温度 (°C)
            is_cooling: 是否为降温模式（需要+1°C补偿）
            retries: 重试次数
        
        Returns:
            dict: 包含以下字段
                - success: bool
                - actual_temp: float，实际设置的温度（包含补偿）
                - error: str or None
        """
        if not self.is_connected():
            return {
                'success': False,
                'actual_temp': None,
                'error': 'Serial port not connected'
            }
        
        with self.serial_lock:
            try:
                # 构建命令
                actual_temp = target_temp + 1.0 if is_cooling else target_temp
                cmd = self._build_temperature_command(actual_temp)
                
                # 发送命令（重试机制）
                for _ in range(retries):
                    self.ser.write(cmd)
                    time.sleep(0.2)
                
                return {
                    'success': True,
                    'actual_temp': actual_temp,
                    'error': None
                }
            
            except Exception as e:
                return {
                    'success': False,
                    'actual_temp': None,
                    'error': f'Failed to set temperature: {str(e)}'
                }
    
    # ========================================================
    # 原子操作：等待温度稳定
    # ========================================================
    
    def wait_for_stable(
        self,
        target_temp,
        epsilon=0.5,
        stable_count=3,
        timeout=3600,
        poll_interval=5.0,
        check_overshoot=False
    ):
        """
        等待温度稳定（原子操作）
        
        Args:
            target_temp: 目标温度 (°C)
            epsilon: 温度稳定阈值 (°C)
            stable_count: 连续稳定次数
            timeout: 超时时间（秒）
            poll_interval: 轮询间隔（秒）
            check_overshoot: 是否检查过冲（温度低于目标时重新设置）
        
        Returns:
            dict: 包含以下字段
                - success: bool
                - final_temp: float or None，最终温度
                - elapsed_time: float，耗时（秒）
                - stable_readings: int，稳定读数次数
                - error: str or None
        """
        start_time = time.time()
        stable_readings = 0
        readings = []
        
        while time.time() - start_time < timeout:
            # 读取温度
            result = self.read_temperature()
            if not result['success']:
                time.sleep(poll_interval)
                continue
            
            current_temp = result['temperature']
            readings.append((time.time() - start_time, current_temp))
            
            # 计算温差
            temp_diff = abs(current_temp - target_temp)
            
            # 检查过冲
            if check_overshoot and current_temp < target_temp - epsilon:
                # 温度过低，重新设置
                self.set_temperature(target_temp, is_cooling=False)
                stable_readings = 0
            elif temp_diff <= epsilon:
                # 温度稳定
                stable_readings += 1
                if stable_readings >= stable_count:
                    elapsed = time.time() - start_time
                    return {
                        'success': True,
                        'final_temp': current_temp,
                        'elapsed_time': elapsed,
                        'stable_readings': stable_readings,
                        'error': None
                    }
            else:
                # 温度不稳定
                stable_readings = 0
            
            time.sleep(poll_interval)
        
        # 超时
        final_temp = readings[-1][1] if readings else None
        elapsed = time.time() - start_time
        
        return {
            'success': False,
            'final_temp': final_temp,
            'elapsed_time': elapsed,
            'stable_readings': stable_readings,
            'error': f'Timeout waiting for stable temperature (target={target_temp}°C, epsilon={epsilon}°C)'
        }
    
    # ========================================================
    # 原子操作：开机
    # ========================================================
    
    def power_on(self, max_attempts=3):
        """
        设备开机（原子操作）
        
        Args:
            max_attempts: 最大尝试次数
        
        Returns:
            dict: 包含以下字段
                - success: bool
                - method: str，成功方式（'command' / 'temperature_check'）
                - error: str or None
        """
        if not self.is_connected():
            return {
                'success': False,
                'method': None,
                'error': 'Serial port not connected'
            }
        
        # 构建开机命令
        cmd = bytes.fromhex("A5 5A 06 83 50 00 01 00 01")
        
        with self.serial_lock:
            for attempt in range(max_attempts):
                try:
                    self.ser.write(cmd)
                    time.sleep(3)
                    
                    # 检查响应
                    if self.ser.in_waiting > 0:
                        resp = self.ser.read(8)
                        if resp == bytes.fromhex("A5 5A 05 82 01 30 00 01"):
                            return {
                                'success': True,
                                'method': 'command',
                                'error': None
                            }
                
                except Exception:
                    pass
        
        # 开机命令失败，尝试直接读取温度
        result = self.read_temperature()
        if result['success']:
            return {
                'success': True,
                'method': 'temperature_check',
                'error': None
            }
        
        return {
            'success': False,
            'method': None,
            'error': f'Failed to power on device after {max_attempts} attempts'
        }
    
    # ========================================================
    # 内部函数：协议解析
    # ========================================================
    
    def _process_buffer(self):
        """处理缓冲区，解析完整帧"""
        # 防止缓冲区无限增长
        if len(self.buffer) > 5000:
            self.buffer.clear()
            return
        
        while len(self.buffer) >= 2:
            # 查找帧头 0xA5 0x5A
            start_pos = -1
            for i in range(len(self.buffer) - 1):
                if self.buffer[i] == 0xA5 and self.buffer[i + 1] == 0x5A:
                    start_pos = i
                    break
            
            if start_pos == -1:
                # 没有找到帧头，保留最后一个字节
                if len(self.buffer) > 1:
                    self.buffer = self.buffer[-1:]
                return
            
            if start_pos > 0:
                # 丢弃帧头前的数据
                self.buffer = self.buffer[start_pos:]
            
            if len(self.buffer) < 3:
                return
            
            # 获取数据长度
            data_len = self.buffer[2]
            
            if len(self.buffer) < 3 + data_len:
                # 数据不完整
                return
            
            # 提取完整帧
            frame = bytes(self.buffer[:3 + data_len])
            self.buffer = self.buffer[3 + data_len:]
            self.frame_queue.append(frame)
    
    def _parse_frame(self, frame):
        """解析数据帧获取温度"""
        try:
            if len(frame) < 8:
                return None
            
            if frame[0] != 0xA5 or frame[1] != 0x5A:
                return None
            
            # 参数类型
            param_type = (frame[4] << 8) | frame[5]
            
            if param_type == 0x0022:
                # 温度数据
                raw = (frame[6] << 8) | frame[7]
                
                # 处理负数（补码）
                if raw & 0x8000:
                    raw = -((raw ^ 0xFFFF) + 1)
                
                temp = raw * 0.1
                
                # 验证温度范围
                if self.temp_min <= temp <= self.temp_max:
                    return temp
                else:
                    return None
            else:
                return None
        
        except Exception:
            return None
    
    def _build_temperature_command(self, temp):
        """构建设置温度的命令"""
        temp_int = int(temp * 10)
        if temp_int < 0:
            temp_int = (1 << 16) + temp_int
        
        high_byte = (temp_int >> 8) & 0xFF
        low_byte = temp_int & 0xFF
        
        return bytes([0xA5, 0x5A, 0x06, 0x83, 0x00, 0x26, 0x01, high_byte, low_byte])
    
    def __enter__(self):
        """上下文管理器入口"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器退出"""
        self.close()
        return False
