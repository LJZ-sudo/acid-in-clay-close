# -*- coding: utf-8 -*-
"""
电导率计算模块
"""


def calculate_conductivity(rb: float, thickness: float, area: float) -> float:
    """
    计算电导率
    
    σ = L / (Rb × S)
    
    Args:
        rb: 体相电阻 (Ω)
        thickness: 样品厚度 L (cm)
        area: 电极面积 S (cm²)
    
    Returns:
        conductivity: 电导率 (S/cm)
    """
    if rb is None or rb <= 0:
        return None
    if thickness <= 0 or area <= 0:
        return None
    
    return thickness / (rb * area)
