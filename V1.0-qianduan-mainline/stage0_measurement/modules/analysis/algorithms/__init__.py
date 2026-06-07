# -*- coding: utf-8 -*-
"""
核心算法模块（纯函数）

子模块：
- rb_fitting: Rb 拟合算法
- kk_validation: Kramers-Kronig 验证
- drt_analysis: 弛豫时间分布分析
- arrhenius: Arrhenius 分析

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
from . import drt_analysis
from . import arrhenius

__all__ = [
    'rb_fitting',
    'kk_validation',
    'drt_analysis',
    'arrhenius',
]
