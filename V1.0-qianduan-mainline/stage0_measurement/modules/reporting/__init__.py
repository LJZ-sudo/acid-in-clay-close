# -*- coding: utf-8 -*-
"""
Reporting 模块：当前仅导出科研级绘图工具。

核心原则：
1. 纯函数 - 只接受数据和配置参数，返回结果字典
2. 标准错误字典 - 失败时返回 {"success": False, "error": "..."}
3. 配置外部化 - API Key、模型名称等作为参数传入
4. 无全局副作用 - 不修改 matplotlib.rcParams（使用上下文管理器）

版本：3.0.0 (重构版)
"""

from .plotter import (
    plot_conductivity_arrhenius,
    plot_temperature_profile,
    plot_r_squared_distribution,
    plot_conductivity_trend,
)

__all__ = [
    # 绘图工具
    'plot_conductivity_arrhenius',
    'plot_temperature_profile',
    'plot_r_squared_distribution',
    'plot_conductivity_trend',
]
