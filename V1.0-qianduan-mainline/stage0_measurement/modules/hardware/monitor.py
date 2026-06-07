# -*- coding: utf-8 -*-
"""
通用温度监控器（纯函数版）

通用的后台轮询器，定期读取数据并放入线程安全队列

核心原则：
1. 通用化 - 接受任何读取函数，不关心具体硬件
2. 无业务逻辑 - 只负责轮询和队列管理
3. 线程安全 - 使用标准库 queue.Queue
4. 无回调 - 不触发任何业务回调，只提供数据获取接口

版本：3.0.0 (重构版)
"""

import queue
import threading
import time
from typing import Callable, Optional, Any, List, Dict


# ============================================================
# 公共接口：温度监控器
# ============================================================

class TemperatureMonitor:
    """
    通用温度监控器（纯函数版）
    
    后台线程定期调用读取函数，将结果放入队列供外层消费
    """
    
    def __init__(
        self,
        read_func,
        poll_interval=1.0,
        max_queue_size=1000,
        max_consecutive_errors=5
    ):
        """
        初始化监控器
        
        Args:
            read_func: 读取函数，返回 dict: {"success": bool, "temperature": float, ...}
            poll_interval: 轮询间隔（秒）
            max_queue_size: 队列最大容量
            max_consecutive_errors: 最大连续错误次数（超过后停止监控）
        """
        self.read_func = read_func
        self.poll_interval = poll_interval
        self.max_queue_size = max_queue_size
        self.max_consecutive_errors = max_consecutive_errors
        
        # 数据队列（线程安全）。必须传入 maxsize，否则 queue.Full 分支不会触发。
        self.data_queue = queue.Queue(maxsize=max_queue_size)
        
        # 控制标志
        self.is_running = False
        self.worker_thread = None
    
    def start(self):
        """
        启动监控
        
        Returns:
            dict: 包含以下字段
                - success: bool
                - error: str or None
        """
        if self.is_running:
            return {
                'success': False,
                'error': 'Monitor is already running'
            }
        
        self.is_running = True
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()
        
        return {
            'success': True,
            'error': None
        }
    
    def stop(self, timeout=5.0):
        """
        停止监控
        
        Args:
            timeout: 等待工作线程结束的超时时间（秒）
        
        Returns:
            dict: 包含以下字段
                - success: bool
                - error: str or None
        """
        if not self.is_running:
            return {
                'success': False,
                'error': 'Monitor is not running'
            }
        
        self.is_running = False
        
        if self.worker_thread:
            self.worker_thread.join(timeout=timeout)
            
            if self.worker_thread.is_alive():
                return {
                    'success': False,
                    'error': f'Worker thread did not stop within {timeout}s'
                }
        
        return {
            'success': True,
            'error': None
        }
    
    def get_data(self, timeout=None):
        """
        获取所有待处理的数据（非阻塞）
        
        Args:
            timeout: 获取单个数据项的超时时间（秒），None 表示立即返回
        
        Returns:
            list[dict]: 数据列表，每个元素为读取函数返回的字典
        """
        data_items = []
        
        while True:
            try:
                item = self.data_queue.get(block=False, timeout=timeout)
                data_items.append(item)
            except queue.Empty:
                break
        
        return data_items
    
    def get_latest(self, block=False, timeout=None):
        """
        获取最新的一条数据
        
        Args:
            block: 是否阻塞等待
            timeout: 超时时间（秒），仅在 block=True 时有效
        
        Returns:
            dict or None: 最新数据，队列为空时返回 None
        """
        try:
            return self.data_queue.get(block=block, timeout=timeout)
        except queue.Empty:
            return None
    
    def clear_queue(self):
        """
        清空队列
        
        Returns:
            int: 清除的数据项数量
        """
        count = 0
        while True:
            try:
                self.data_queue.get_nowait()
                count += 1
            except queue.Empty:
                break
        
        return count
    
    def get_status(self):
        """
        获取监控器状态
        
        Returns:
            dict: 包含以下字段
                - is_running: bool
                - queue_size: int
                - queue_full: bool
        """
        return {
            'is_running': self.is_running,
            'queue_size': self.data_queue.qsize(),
            'queue_full': self.data_queue.qsize() >= self.max_queue_size
        }
    
    # ========================================================
    # 内部函数：工作线程
    # ========================================================
    
    def _worker_loop(self):
        """工作线程主循环"""
        consecutive_errors = 0
        
        while self.is_running:
            try:
                # 调用读取函数
                result = self.read_func()
                
                # 检查结果
                if isinstance(result, dict):
                    if result.get('success', False):
                        # 读取成功，重置错误计数
                        consecutive_errors = 0
                        
                        # 添加时间戳
                        data_item = {
                            'timestamp': time.time(),
                            **result
                        }
                        
                        # 放入队列
                        try:
                            self.data_queue.put_nowait(data_item)
                        except queue.Full:
                            # 队列满，丢弃最旧的数据
                            try:
                                self.data_queue.get_nowait()
                                self.data_queue.put_nowait(data_item)
                            except (queue.Empty, queue.Full):
                                pass
                    else:
                        # 读取失败
                        consecutive_errors += 1
                else:
                    # 返回格式不正确
                    consecutive_errors += 1
                
                # 检查连续错误次数
                if consecutive_errors >= self.max_consecutive_errors:
                    self.is_running = False
                    break
                
                # 等待下次轮询
                time.sleep(self.poll_interval)
            
            except Exception as e:
                consecutive_errors += 1
                
                if consecutive_errors >= self.max_consecutive_errors:
                    self.is_running = False
                    break
                
                time.sleep(self.poll_interval)


# ============================================================
# 辅助函数：包装回调
# ============================================================

def create_callback_wrapper(read_func, callback_func):
    """
    创建带回调的读取函数包装器
    
    注意：这违反了"无回调"原则，仅在必要时使用（如 WebSocket 推送）
    
    Args:
        read_func: 原始读取函数
        callback_func: 回调函数，接受温度值作为参数
    
    Returns:
        包装后的读取函数
    """
    def wrapped_read_func():
        result = read_func()
        
        # 如果读取成功且有温度值，调用回调
        if result.get('success') and 'temperature' in result:
            try:
                callback_func(result['temperature'])
            except Exception:
                pass  # 忽略回调错误
        
        return result
    
    return wrapped_read_func
