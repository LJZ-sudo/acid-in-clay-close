# -*- coding: utf-8 -*-
"""
Specific Conductance Analysis Module
用于固体电解质电导率分析的完整工具包

主要功能:
- data_processing: 数据读取、滤波、预处理
- rb_fitting: Rb拟合（线性拟合、圆弧拟合）
- conductivity: 电导率计算和Arrhenius分析
"""

__version__ = "1.0.0"
__author__ = "Research Team"

# 导入主要功能模块
from .data_processing import filter_data, read_csv_files
from .rb_fitting import calculate_rb, check_linearity, detect_phase_jump
from .conductivity import calculate_conductivity, get_fit_params

__all__ = [
    'filter_data',
    'read_csv_files',
    'calculate_rb',
    'check_linearity',
    'detect_phase_jump',
    'calculate_conductivity',
    'get_fit_params',
]

