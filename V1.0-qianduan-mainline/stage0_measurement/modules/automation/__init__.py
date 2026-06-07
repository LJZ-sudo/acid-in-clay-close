# -*- coding: utf-8 -*-
"""
Automation 模块：桌面 GUI 自动化

子模块：
- chi_executor: CHI 仪器桌面自动化执行器

核心原则：
1. 纯执行 - 只负责 UI 自动化，不生成模拟数据
2. 标准错误字典 - 失败时如实返回，绝不伪造数据
3. 参数化配置 - 所有硬编码提取为配置字典
4. 无业务逻辑 - 不保存历史，不触发回调

关键安全约束：
- 禁止生成随机模拟数据
- UI 操作失败时必须如实返回错误
- 不污染真实数据流

版本：3.0.0 (重构版)
"""

from .chi_executor import (
    ChiExecutor,
    calculate_chi_measurement_time,
)

__all__ = [
    'ChiExecutor',
    'calculate_chi_measurement_time',
]
