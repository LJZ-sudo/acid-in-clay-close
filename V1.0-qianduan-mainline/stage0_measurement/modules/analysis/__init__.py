# -*- coding: utf-8 -*-
"""
Analysis 模块：科学计算与核心算法

子模块：
- algorithms: 核心算法（纯函数）
  - rb_fitting: Rb 拟合
  - kk_validation: KK 验证
  - drt_analysis: DRT 分析
  - arrhenius: Arrhenius 分析
- eis_pipeline: EIS 分析管线（门面）
- data_quality: 数据质量评估
- phase_detect: 相变检测

核心原则：
1. 纯函数化 - 无状态、无副作用
2. 无 I/O 操作 - 不读写文件
3. 无绘图操作 - 绘图由 reporting 模块负责
4. 标准错误字典 - {"success": False, "error": "..."}

版本：2.0.0 (重构版)
"""

# 导出主要接口
from . import eis_pipeline
from . import data_quality
from . import phase_detect
from . import algorithms

__all__ = [
    'eis_pipeline',
    'data_quality',
    'phase_detect',
    'algorithms',
]
