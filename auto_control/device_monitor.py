# -*- coding: utf-8 -*-
"""
设备监控模块
@author: 25862
"""

import serial
import time
import threading
import queue
import json
import os
from datetime import datetime
from typing import Dict, List, Optional

class DeviceMonitor:
    """设备监控器"""
    
    def __init__(self, port: str = 'COM3'):
        """
        初始化设备监控器
        
        Args:
            port: 串口号
        """
        self.port = port
        self.ser = None
        self.is_monitoring = False
        self.monitoring_thread = None
        self.data_queue = queue.Queue()
        self.status = {
            'connected': False,
            'power_on': False,
            'temperature': None,
            'last_update': None,
            'error_count': 0,
            'data_count': 0
        }
        
        # 数据缓存
        self.temperature_history = []
        self.max_history_size = 1000
        
    def start_monitoring(self) -> bool:
        """启动设备监控"""
        if self.is_monitoring:
            print("设备监控已在运行中")
            return True
            
        try:
            # 尝试连接设备
            self.ser = serial.Serial(
                port=self.port,
                baudrate=19200,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_TWO,
                timeout=0.1
            )
            
            self.is_monitoring = True
            self.monitoring_thread = threading.Thread(target=self._monitoring_worker)
            self.monitoring_thread.daemon = True
            self.monitoring_thread.start()
            
            print(f"✅ 设备监控已启动 - 串口: {self.port}")
            return True
            
        except serial.SerialException as e:
            print(f"❌ 设备监控启动失败: {e}")
            return False
        except Exception as e:
            print(f"❌ 设备监控异常: {e}")
            return False
    
    def stop_monitoring(self):
        """停止设备监控"""
        self.is_monitoring = False
        
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5)
        
        if self.ser and self.ser.is_open:
            self.ser.close()
        
        print("设备监控已停止")
    
    def _monitoring_worker(self):
        """监控工作线程"""
        error_count = 0
        max_errors = 10
        
        while self.is_monitoring:
            try:
                # 检查串口连接
                if not self.ser or not self.ser.is_open:
                    print("串口连接断开，尝试重新连接...")
                    self._reconnect()
                    continue
                
                # 读取数据
                if self.ser.in_waiting > 0:
                    data = self.ser.read(self.ser.in_waiting)
                    if len(data) > 0:
                        self._process_data(data)
                        error_count = 0  # 重置错误计数
                
                # 定期更新状态
                self._update_status()
                
                time.sleep(0.1)  # 100ms更新间隔
                
            except Exception as e:
                error_count += 1
                print(f"监控线程错误 ({error_count}/{max_errors}): {e}")
                
                if error_count >= max_errors:
                    print("错误次数过多，停止监控")
                    break
                
                time.sleep(1)
    
    def _reconnect(self):
        """重新连接设备"""
        try:
            if self.ser:
                self.ser.close()
            
            time.sleep(2)
            
            self.ser = serial.Serial(
                port=self.port,
                baudrate=19200,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_TWO,
                timeout=0.1
            )
            
            print("设备重新连接成功")
            
        except Exception as e:
            print(f"设备重新连接失败: {e}")
    
    def _process_data(self, data: bytes):
        """处理接收到的数据"""
        try:
            # 解析数据帧
            if len(data) >= 8:
                if data[0] == 0xA5 and data[1] == 0x5A:
                    param_type = (data[4] << 8) | data[5]
                    
                    if param_type == 0x0022:  # 温度传感器
                        # 解析温度数据
                        raw = (data[6] << 8) | data[7]
                        if raw & 0x8000:
                            raw = -((raw ^ 0xFFFF) + 1)
                        temperature = raw * 0.1
                        
                        # 更新状态
                        self.status['temperature'] = temperature
                        self.status['connected'] = True
                        self.status['power_on'] = True
                        self.status['last_update'] = datetime.now().isoformat()
                        self.status['data_count'] += 1
                        
                        # 添加到历史记录
                        self.temperature_history.append({
                            'timestamp': time.time(),
                            'temperature': temperature
                        })
                        
                        # 限制历史记录大小
                        if len(self.temperature_history) > self.max_history_size:
                            self.temperature_history.pop(0)
                        
                        # 将数据放入队列
                        self.data_queue.put({
                            'type': 'temperature',
                            'temperature': temperature,
                            'timestamp': time.time()
                        })
                        
                        print(f"🌡️ 温度: {temperature:.1f}°C")
                    
                    elif param_type == 0x0030:  # 开机响应
                        self.status['power_on'] = True
                        self.status['last_update'] = datetime.now().isoformat()
                        print("🔌 设备开机状态确认")
                        
                        self.data_queue.put({
                            'type': 'power_on',
                            'timestamp': time.time()
                        })
            
        except Exception as e:
            print(f"数据处理错误: {e}")
    
    def _update_status(self):
        """更新设备状态"""
        current_time = time.time()
        
        # 检查连接超时
        if self.status['last_update']:
            last_update = datetime.fromisoformat(self.status['last_update']).timestamp()
            if current_time - last_update > 30:  # 30秒无数据则认为断开
                self.status['connected'] = False
                self.status['temperature'] = None
    
    def get_status(self) -> Dict:
        """获取设备状态"""
        return self.status.copy()
    
    def get_temperature_history(self, limit: int = 100) -> List[Dict]:
        """获取温度历史数据"""
        return self.temperature_history[-limit:] if self.temperature_history else []
    
    def get_latest_data(self) -> Optional[Dict]:
        """获取最新数据"""
        try:
            return self.data_queue.get_nowait()
        except queue.Empty:
            return None
    
    def send_power_on_command(self) -> bool:
        """发送开机命令"""
        try:
            if not self.ser or not self.ser.is_open:
                print("串口未连接，无法发送开机命令")
                return False
            
            cmd = bytes.fromhex('A5 5A 06 83 50 00 01 00 01')
            self.ser.write(cmd)
            
            print("开机命令已发送")
            return True
            
        except Exception as e:
            print(f"发送开机命令失败: {e}")
            return False
    
    def set_temperature(self, temperature: float) -> bool:
        """设置目标温度"""
        try:
            if not self.ser or not self.ser.is_open:
                print("串口未连接，无法设置温度")
                return False
            
            temp_int = int(temperature * 10)
            if temp_int < 0:
                temp_int = (1 << 16) + temp_int
            
            high_byte = (temp_int >> 8) & 0xFF
            low_byte = temp_int & 0xFF
            
            cmd = bytes([0xA5, 0x5A, 0x06, 0x83, 0x00, 0x26, 0x01, high_byte, low_byte])
            self.ser.write(cmd)
            
            print(f"温度设置命令已发送: {temperature}°C")
            return True
            
        except Exception as e:
            print(f"设置温度失败: {e}")
            return False


# ==================== 全局监控实例 ====================
_global_device_monitor = None

def get_global_device_monitor() -> Optional[DeviceMonitor]:
    """获取全局设备监控实例"""
    return _global_device_monitor

def create_global_device_monitor(port: str = 'COM3') -> DeviceMonitor:
    """创建全局设备监控实例"""
    global _global_device_monitor
    if _global_device_monitor:
        _global_device_monitor.stop_monitoring()
    
    _global_device_monitor = DeviceMonitor(port=port)
    return _global_device_monitor


if __name__ == "__main__":
    # 测试设备监控
    monitor = create_global_device_monitor('COM3')
    
    try:
        if monitor.start_monitoring():
            print("设备监控启动成功")
            
            # 运行30秒
            for i in range(30):
                status = monitor.get_status()
                print(f"状态更新 {i+1}/30: {status}")
                
                # 获取最新数据
                latest_data = monitor.get_latest_data()
                if latest_data:
                    print(f"最新数据: {latest_data}")
                
                time.sleep(1)
            
            print("测试完成")
        else:
            print("设备监控启动失败")
            
    except KeyboardInterrupt:
        print("用户中断测试")
    finally:
        monitor.stop_monitoring() 