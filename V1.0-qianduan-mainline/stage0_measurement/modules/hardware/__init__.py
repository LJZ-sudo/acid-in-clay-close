# -*- coding: utf-8 -*-
"""
Hardware 模块：硬件驱动与通信

子模块：
- temp_driver: 独立的温度控制器驱动
- monitor: 通用的后台监控器

核心原则：
1. 独立初始化 - 驱动类不依赖控制器状态
2. 原子操作 - 每个函数只做一件事，返回标准字典
3. 无业务逻辑 - 不保存历史数据，不触发业务回调
4. 线程安全 - 使用锁和队列保证并发安全

版本：3.0.0 (重构版)
"""

from .temp_driver import TemperatureDriver
from .monitor import TemperatureMonitor, create_callback_wrapper

__all__ = [
    'TemperatureDriver',
    'TemperatureMonitor',
    'create_callback_wrapper',
]
