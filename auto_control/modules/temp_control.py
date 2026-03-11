import serial
import time
from datetime import datetime
from typing import Optional, Tuple, List, Dict
from collections import deque

class TemperatureControlMixin:
    """控温功能 Mixin 模块"""

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

    def _ensure_serial_connected(self) -> bool:
        """确保串口已连接"""
        if self.ser and self.ser.is_open:
            return True
        try:
            self.ser = self._init_serial(self.ser.port)
            return True
        except Exception:
            return False

    def send_command(self, cmd_hex: str) -> bool:
        """发送十六进制命令"""
        if not self._ensure_serial_connected():
            return False
        try:
            cmd_bytes = bytes.fromhex(cmd_hex.replace(' ', ''))
            self.ser.write(cmd_bytes)
            return True
        except Exception as e:
            print(f"发送命令失败: {e}")
            return False

    def set_temperature(self, temp: float, is_cooling: bool = True) -> bool:
        """设置目标温度"""
        with self.serial_lock:
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
            msg = f"温度已设置为: {actual_temp:.1f}°C"
            if is_cooling and actual_temp != temp:
                msg += f" (目标{temp:.1f}°C + 1°C补偿)"
            print(msg)
            return True

    def read_temperature(self) -> Optional[float]:
        """读取当前温度"""
        with self.serial_lock:
            self.frame_queue.clear()
            latest_temp = None
            start_time = time.time()
            while time.time() - start_time < 5:
                if self.ser.in_waiting > 0:
                    data = self.ser.read(min(self.ser.in_waiting, 500))
                    self.buffer.extend(data)
                    self._process_buffer()
                    while self.frame_queue:
                        frame = self.frame_queue.popleft()
                        temp = self._parse_frame(frame)
                        if temp is not None:
                            latest_temp = temp
                    if latest_temp is not None:
                        break
                time.sleep(0.1)
            if latest_temp is not None:
                self.temperature_history.append((time.time(), latest_temp))
                self.current_temp = latest_temp
                if len(self.temperature_history) > 1000:
                    self.temperature_history = self.temperature_history[-1000:]
                print(f"当前温度: {latest_temp:.1f}°C")
                
                # 调用温度更新回调（用于WebSocket实时推送）
                if hasattr(self, 'temperature_update_callback') and callable(self.temperature_update_callback):
                    try:
                        self.temperature_update_callback(latest_temp)
                    except Exception as e:
                        print(f"[回调错误] 温度更新回调失败: {e}")
                
                return latest_temp
            return None

    def stop_temperature_control(self):
        """停止温度控制"""
        self.control_active = False
        if hasattr(self, 'control_thread') and self.control_thread:
            self.control_thread.join(timeout=5)
        print("温度控制已停止")

    def _wait_for_stable_temp(self, target: float, check_recovery: bool = False, strict_cooling: bool = False) -> bool:
        """等待温度稳定"""
        start_time = time.time()
        min_temp = float('inf')
        stable_count = 0
        timeout = 7200 if strict_cooling else 3600
        print(f"等待温度{'严格' if strict_cooling else '普通'}降温到 {target}°C...")
        while time.time() - start_time < timeout:
            current_time = time.time()
            if current_time - self.last_periodic_pause_time >= 2:
                self.last_periodic_pause_time = current_time
                time.sleep(0.3)
            current_temp = self.read_temperature()
            if current_temp is None: continue
            if current_temp < min_temp: min_temp = current_temp
            if strict_cooling:
                if current_temp <= target:
                    stable_count += 1
                    if stable_count >= 8: return True
                else:
                    stable_count = 0
            elif not check_recovery and current_temp <= target:
                return True
            elif check_recovery:
                temp_diff = abs(current_temp - target)
                if temp_diff <= self.eps:
                    stable_count += 1
                    if stable_count >= 8: return True
                else:
                    stable_count = 0
            time.sleep(5.0)
        return False

    def _need_strict_cooling(self, step_size: float) -> bool:
        """判断是否需要严格降温"""
        return step_size >= 10.0 or (self.current_target >= 0 and not self.fine_measuring)

    def active_warm_up(self, target_temp: float, timeout: int = 3600) -> bool:
        """主动升温到目标温度"""
        print(f"🔥 主动升温到 {target_temp}°C...")
        self.set_temperature(target_temp, is_cooling=False)
        start_time = time.time()
        stable_count = 0
        while time.time() - start_time < timeout:
            current_temp = self.read_temperature()
            if current_temp is None:
                time.sleep(1); continue
            if abs(current_temp - target_temp) <= self.eps:
                stable_count += 1
                if stable_count >= 5: return True
            else:
                stable_count = 0
            time.sleep(2)
        return False

    def execute_precise_cooling(self, target_temp: float):
        """执行精确降温"""
        print(f"\n🔄 ========== 开始精确降温 ==========\n🎯 目标: {target_temp}°C")
        self.segmented_cooling_active = True
        try:
            current_temp = self.read_temperature()
            if current_temp is None: return False
            if abs(current_temp - target_temp) <= self.eps:
                if self._wait_for_stable_temp(target_temp, check_recovery=True): return True
            elif current_temp < target_temp - self.eps:
                if self._wait_for_stable_temp(target_temp, check_recovery=True): return True
            else:
                if current_temp > target_temp + 3:
                    first_target = target_temp + 3
                    self.set_temperature(first_target, is_cooling=True)
                    self._wait_for_stable_temp(first_target, check_recovery=False)
                temp = self.read_temperature() or current_temp
                while temp > target_temp + self.eps:
                    next_temp = max(temp - 1, target_temp)
                    self.set_temperature(next_temp, is_cooling=False)  # 精确降温不使用补偿
                    self._wait_for_stable_temp(next_temp, check_recovery=True)
                    temp = self.read_temperature() or next_temp
                return self._wait_for_stable_temp(target_temp, check_recovery=True, strict_cooling=True)
            return False
        finally:
            self.segmented_cooling_active = False

    def execute_segmented_cooling_old(self, target_temp: float, main_step: float = 10.0):
        """旧版分段降温"""
        self.segmented_cooling_active = True
        try:
            split_point = target_temp if main_step <= 5.0 else target_temp + main_step * 0.8
            temp_target = self.read_temperature()
            if temp_target is None: return False
            while temp_target > target_temp:
                in_fine = temp_target <= split_point
                D = 1 if in_fine else 2
                next_t = max(temp_target - D, target_temp)
                self.set_temperature(next_t, is_cooling=True)
                if self._wait_for_stable_temp(next_t, check_recovery=in_fine):
                    temp_target = next_t
                else:
                    temp_target = next_t
                if temp_target <= target_temp + self.eps: break
            return True
        finally:
            self.segmented_cooling_active = False

    def execute_segmented_cooling(self, target_temp: float, main_step: float = 10.0):
        """简化版降温函数"""
        self.segmented_cooling_active = True
        try:
            current_temp = self.read_temperature()
            if current_temp is None: return False
            if abs(current_temp - target_temp) <= self.eps: return True
            self.set_temperature(target_temp, is_cooling=True)
            start_time = time.time()
            stable_count = 0
            while time.time() - start_time < 3600:
                if hasattr(self, 'paused') and self.paused:
                    time.sleep(5); continue
                current_temp = self.read_temperature()
                if current_temp is None: continue
                temp_diff = current_temp - target_temp
                if abs(temp_diff) <= self.eps:
                    stable_count += 1
                    if stable_count >= 3: return True
                elif temp_diff < -self.eps:
                    stable_count = 0
                    self.set_temperature(target_temp, is_cooling=False)
                else:
                    stable_count = 0
                time.sleep(5)
            return False
        finally:
            self.segmented_cooling_active = False
