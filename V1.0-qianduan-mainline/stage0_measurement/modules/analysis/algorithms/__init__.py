# -*- coding: utf-8 -*-
"""
核心算法模块（纯函数）

子模块：
- rb_fitting: Rb 拟合算法
- kk_validation: Kramers-Kronig 验证
- arrhenius: Arrhenius 分析

注：drt_analysis 已于 2026-07-05 下线归档（本数据上 DRT 重构 R² 全部 < 0，不可作证据；
见 archive/drt_decommissioned_20260705/）。

核心原则：
1. 纯函数 - 相同输入产生相同输出
2. 无状态 - 不依赖全局变量
3. 无副作用 - 不修改输入参数
4. 无 I/O - 不读写文件、不绘图
5. 标准错误 - 返回标准化错误字典

版本：2.0.0 (重构版)
"""

from . import rb_fitting
from . import kk_validation
from . import arrhenius

__all__ = [
    'rb_fitting',
    'kk_validation',
    'arrhenius',
]
