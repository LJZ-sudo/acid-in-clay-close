# -*- coding: utf-8 -*-
"""
EIS 数据质量评估算法（纯函数版）

这是一个纯粹的算法模块，遵循以下原则：
1. 所有函数都是纯函数，只接受参数输入，返回计算结果
2. 无全局副作用（无 print、无状态修改）
3. 绝对禁止画图操作（由 reporting 模块负责可视化）
4. 统一错误抛出：返回规范的字典格式
5. 配置参数作为函数参数，便于后续从统一配置传入

主要功能：
- 噪声水平评估
- Nyquist 图质量评估
- 频率覆盖评估
- 数据连续性评估
- 综合质量评分与评级（A-F）

版本：3.0.0 (重构版)
"""

import numpy as np
from typing import Dict


# ============================================================
# 默认质量配置
# ============================================================

DEFAULT_QUALITY_CONFIG = {
    # 权重配置
    'noise_weight': 0.25,
    'nyquist_weight': 0.35,
    'freq_coverage_weight': 0.20,
    'continuity_weight': 0.20,
    
    # 阈值配置
    'min_quality_threshold': 0.75,
    'min_points': 5,
    
    # 致命错误阈值（一票否决）
    'max_impedance_fatal': 250000.0,  # 250 kΩ，超过此值表明微电流触及仪器噪声底线
    'noise_reversal_fatal': 3,         # 允许低频区 Z_real 反向减小的最大次数
}


# ============================================================
# 公共接口：数据质量评估
# ============================================================

def assess_data_quality(
    frequencies,
    z_real,
    z_imag,
    temperature=None,
    config=None
):
    """
    评估 EIS 数据质量（纯函数版主入口）
    
    包含仪器量程物理极限的"一票否决"拦截规则：
    1. 阻抗模超过 250 kΩ → 微电流触及仪器噪声底线，数据失去拟合意义
    2. 低频区 Z_real 逆向减小超过 3 次 → 严重失真
    
    Args:
        frequencies: 频率数组 (Hz)
        z_real: 阻抗实部 (Ω)
        z_imag: 阻抗虚部 (Ω)
        temperature: 温度 (K)，可选
        config: 质量配置字典（None 时使用默认配置）
            - noise_weight: 噪声权重（默认 0.25）
            - nyquist_weight: Nyquist 图质量权重（默认 0.35）
            - freq_coverage_weight: 频率覆盖权重（默认 0.20）
            - continuity_weight: 连续性权重（默认 0.20）
            - min_quality_threshold: 最低质量阈值（默认 0.75）
            - max_impedance_fatal: 致命阻抗极限（默认 250000 Ω）
            - noise_reversal_fatal: 致命逆向次数（默认 3）
    
    Returns:
        dict: 包含以下字段
            - valid: bool，是否有效
            - quality_score: float (0-1)，质量分数
            - grade: str，评级（A/B/C/D/F）
            - message: str，结果描述
            - details: dict，详细信息
    """
    # 合并配置
    if config is None:
        config = DEFAULT_QUALITY_CONFIG.copy()
    else:
        merged_config = DEFAULT_QUALITY_CONFIG.copy()
        merged_config.update(config)
        config = merged_config
    
    # 输入验证
    freq = np.array(frequencies, dtype=float)
    zreal = np.array(z_real, dtype=float)
    zimag = np.array(z_imag, dtype=float)
    
    min_points = config.get('min_points', 5)
    
    if len(freq) < min_points:
        return {
            'valid': False,
            'quality_score': 0.0,
            'grade': 'F',
            'message': f'数据点不足（< {min_points}）',
            'details': {'n_points': len(freq)}
        }
    
    if len(freq) != len(zreal) or len(freq) != len(zimag):
        return {
            'valid': False,
            'quality_score': 0.0,
            'grade': 'F',
            'message': '数据长度不一致',
            'details': {
                'n_freq': len(freq),
                'n_zreal': len(zreal),
                'n_zimag': len(zimag)
            }
        }
    
    # ===== 致命错误检查（一票否决）=====
    
    # 1. 检查阻抗模是否超过仪器量程极限
    z_magnitude = np.sqrt(zreal**2 + zimag**2)
    max_impedance = float(np.max(z_magnitude))
    max_impedance_fatal = config.get('max_impedance_fatal', 250000.0)
    
    if max_impedance > max_impedance_fatal:
        return {
            'valid': False,
            'quality_score': 0.0,
            'grade': 'F',
            'message': f'致命错误: 阻抗超量程极限 ({max_impedance:.1f} Ω > {max_impedance_fatal:.1f} Ω)',
            'details': {
                'fatal_check': 'impedance_overflow',
                'max_impedance': max_impedance,
                'threshold': max_impedance_fatal,
                'n_points': len(freq)
            }
        }
    
    # 2. 检查低频区 Z_real 逆向减小（噪声失真）
    # 按频率降序排列（高频在前，低频在后）
    sort_idx = np.argsort(freq)[::-1]  # 降序
    freq_sorted = freq[sort_idx]
    zreal_sorted = zreal[sort_idx]
    
    # 检查最后 20 个点（最低频区）
    # 物理预期：随频率降低（数组索引增加），Z_real 应该单调递增或稳定（趋于极化电阻）
    # 如果反而减小，说明低频噪声严重
    n_check = min(20, len(zreal_sorted))
    low_freq_zreal = zreal_sorted[-n_check:] if len(zreal_sorted) >= n_check else zreal_sorted
    
    # 计算逆向减小的次数（随频率降低，Z_real 应该增加或稳定，但反而减小 > 5%）
    reversal_count = 0
    for i in range(1, len(low_freq_zreal)):
        # 如果后一个点（更低频率）的 Z_real 反而减小，且降幅 > 5%
        if low_freq_zreal[i] < low_freq_zreal[i-1] * 0.95:
            reversal_count += 1
    
    noise_reversal_fatal = config.get('noise_reversal_fatal', 3)
    
    if reversal_count > noise_reversal_fatal:
        return {
            'valid': False,
            'quality_score': 0.0,
            'grade': 'F',
            'message': f'致命错误: 低频严重失真（逆向减小 {reversal_count} 次 > {noise_reversal_fatal}）',
            'details': {
                'fatal_check': 'noise_reversal',
                'reversal_count': reversal_count,
                'threshold': noise_reversal_fatal,
                'n_points': len(freq),
                'low_freq_checked': len(low_freq_zreal)
            }
        }
    
    # ===== 通过致命检查后，执行常规质量评估 =====
    
    # 计算各项指标
    try:
        noise_level = _calculate_noise_level(freq, zreal, zimag)
        nyquist_quality = _check_nyquist_quality(zreal, zimag)
        freq_coverage = _check_frequency_coverage(freq)
        continuity = _check_data_continuity(freq, zreal, zimag)
    except Exception as e:
        return {
            'valid': False,
            'quality_score': 0.0,
            'grade': 'F',
            'message': f'质量评估失败: {str(e)}',
            'details': {'exception': str(e)}
        }
    
    # 综合质量分数
    noise_weight = config.get('noise_weight', 0.25)
    nyquist_weight = config.get('nyquist_weight', 0.35)
    freq_coverage_weight = config.get('freq_coverage_weight', 0.20)
    continuity_weight = config.get('continuity_weight', 0.20)
    
    quality_score = (
        (1 - min(1.0, noise_level)) * noise_weight +
        nyquist_quality * nyquist_weight +
        freq_coverage * freq_coverage_weight +
        continuity * continuity_weight
    )
    
    # 评级
    if quality_score >= 0.9:
        grade = 'A'
    elif quality_score >= 0.75:
        grade = 'B'
    elif quality_score >= 0.6:
        grade = 'C'
    elif quality_score >= 0.4:
        grade = 'D'
    else:
        grade = 'F'
    
    # 判断是否有效
    min_quality_threshold = config.get('min_quality_threshold', 0.75)
    valid = quality_score >= min_quality_threshold
    
    return {
        'valid': bool(valid),
        'quality_score': float(quality_score),
        'grade': grade,
        'message': f'数据质量评级: {grade} ({quality_score:.2f})',
        'details': {
            'noise_level': float(noise_level),
            'nyquist_quality': float(nyquist_quality),
            'freq_coverage': float(freq_coverage),
            'continuity': float(continuity),
            'n_points': int(len(freq)),
            'freq_range': (float(freq.min()), float(freq.max())),
            'max_impedance': max_impedance,
            'reversal_count': reversal_count,
            'temperature': temperature
        }
    }


# ============================================================
# 内部函数：噪声水平评估
# ============================================================

def _calculate_noise_level(freq, zreal, zimag):
    """
    计算噪声水平（内部函数）
    
    基于相邻点差分的标准差来评估噪声
    
    Args:
        freq: 频率数组
        zreal: 阻抗实部
        zimag: 阻抗虚部
    
    Returns:
        float: 噪声水平 (0-1)，0 表示无噪声，1 表示高噪声
    """
    if len(freq) < 5:
        return 1.0
    
    # 按频率排序
    sort_idx = np.argsort(freq)
    zreal_sorted = zreal[sort_idx]
    zimag_sorted = zimag[sort_idx]
    
    # 计算相邻点差分的标准差
    zreal_diff = np.diff(zreal_sorted)
    zimag_diff = np.diff(zimag_sorted)
    
    mean_zreal = np.mean(np.abs(zreal))
    mean_zimag = np.mean(np.abs(zimag))
    
    if mean_zreal > 0 and mean_zimag > 0:
        noise_real = np.std(zreal_diff) / mean_zreal
        noise_imag = np.std(zimag_diff) / mean_zimag
        noise_level = (noise_real + noise_imag) / 2
    else:
        noise_level = 1.0
    
    return float(min(1.0, noise_level))


# ============================================================
# 内部函数：Nyquist 图质量评估
# ============================================================

def _check_nyquist_quality(zreal, zimag):
    """
    检查 Nyquist 图质量（内部函数）
    
    评估是否有完整的半圆特征
    
    Args:
        zreal: 阻抗实部
        zimag: 阻抗虚部
    
    Returns:
        float: 质量分数 (0-1)
    """
    # 检查是否有完整的半圆
    zreal_range = zreal.max() - zreal.min()
    zimag_max = np.abs(zimag).max()
    
    if zreal_range <= 0:
        return 0.0
    
    # 理想半圆的高度应该约为直径的一半
    # semicircle_ratio = (高度 / 直径) * 2，理想值为 1
    semicircle_ratio = (zimag_max / zreal_range) * 2
    
    # 评分：比值接近 1 为最佳
    if semicircle_ratio > 0.3 and semicircle_ratio < 2.0:
        if semicircle_ratio < 1:
            quality = semicircle_ratio
        else:
            quality = 2 - semicircle_ratio
        quality = min(1.0, quality)
    else:
        quality = 0.3
    
    return float(quality)


# ============================================================
# 内部函数：频率覆盖评估
# ============================================================

def _check_frequency_coverage(freq):
    """
    检查频率覆盖范围（内部函数）
    
    Args:
        freq: 频率数组 (Hz)
    
    Returns:
        float: 覆盖分数 (0-1)
    """
    try:
        freq_decades = np.log10(freq.max()) - np.log10(freq.min())
    except Exception:
        return 0.0
    
    # 理想覆盖：5 个数量级
    coverage = min(1.0, freq_decades / 5.0)
    
    return float(coverage)


# ============================================================
# 内部函数：数据连续性评估
# ============================================================

def _check_data_continuity(freq, zreal, zimag):
    """
    检查数据连续性（内部函数）
    
    检测是否存在异常跳变
    
    Args:
        freq: 频率数组
        zreal: 阻抗实部
        zimag: 阻抗虚部
    
    Returns:
        float: 连续性分数 (0-1)
    """
    if len(freq) < 3:
        return 0.5
    
    # 检查是否有异常跳变
    z_magnitude = np.sqrt(zreal**2 + zimag**2)
    z_diff = np.abs(np.diff(z_magnitude))
    z_mean = np.mean(z_magnitude)
    
    if z_mean > 0:
        jump_ratio = z_diff / z_mean
        n_jumps = np.sum(jump_ratio > 0.5)  # 超过 50% 的跳变视为异常
        continuity = 1.0 - (n_jumps / len(z_diff))
    else:
        continuity = 0.5
    
    return float(max(0.0, continuity))


# ============================================================
# 辅助函数：质量报告
# ============================================================

def get_quality_summary(quality_result):
    """
    生成质量评估的可读摘要（纯函数）
    
    Args:
        quality_result: assess_data_quality 返回的结果
    
    Returns:
        str: 可读摘要
    """
    if not quality_result.get('valid', False):
        return f"❌ {quality_result.get('message', '数据无效')}"
    
    grade = quality_result.get('grade', 'F')
    score = quality_result.get('quality_score', 0.0)
    details = quality_result.get('details', {})
    
    summary_lines = [
        f"✅ 数据质量：{grade} ({score:.2%})",
        f"  • 噪声水平：{details.get('noise_level', 0):.3f}",
        f"  • Nyquist 质量：{details.get('nyquist_quality', 0):.3f}",
        f"  • 频率覆盖：{details.get('freq_coverage', 0):.3f}",
        f"  • 数据连续性：{details.get('continuity', 0):.3f}"
    ]
    
    return "\n".join(summary_lines)
