# -*- coding: utf-8 -*-
"""
Kramers-Kronig (KK) 一致性校验算法（基于 impedance 库）

这是一个纯粹的算法模块，遵循以下原则：
1. 所有函数都是纯函数，只接受参数输入，返回计算结果
2. 无全局副作用（无 warnings、无状态修改）
3. 绝对禁止画图操作（由 reporting 模块负责可视化）
4. 统一错误抛出：返回规范的字典格式
5. 配置参数作为函数参数，便于后续从统一配置传入

使用 impedance 库的 linKK 方法（基于 Schönleber 2014）：
- 标准的 lin-KK 实现，无需手写积分
- 通过残差分析评估数据质量
- 输出 KK 一致性评分和通过/失败状态

优化设计（v5.0.0）：
- 使用中位数（median）代替最大值评估，增强抗噪点能力
- 计算 RMSE 和中位数，提供更鲁棒的质量指标
- 放宽阈值默认值至 0.2（20%），适应深冷固态电池数据
- 剥离"计算失败"与"验证失败"：linKK 执行成功即返回 success=True

参考文献:
Schönleber et al. (2014) "A Method for Improving the Robustness of linear 
Kramers-Kronig Validity Tests" Electrochimica Acta, 131, 20-27.

版本：5.0.0 (深冷固态电池优化版)
"""

import numpy as np
from typing import Dict, Optional

try:
    from impedance.validation import linKK
    IMPEDANCE_AVAILABLE = True
except ImportError:
    IMPEDANCE_AVAILABLE = False


# ============================================================
# 公共接口：KK 校验
# ============================================================

def validate_kk_consistency(
    frequencies,
    z_real,
    z_imag,
    residual_threshold=0.2,
    min_points=10,
    c=0.5,
    max_M=100,
    fit_type='complex',
    preprocess=True,
    trim_inductive_tail=True
):
    """
    执行 Kramers-Kronig 一致性校验（基于 impedance 库，深冷固态电池优化版）
    
    检查 EIS 数据是否满足 KK 关系（因果性、线性、稳态性检验）
    
    优化特性：
    1. 使用中位数（median）代替最大值，增强抗边缘噪点能力
    2. 计算 RMSE 和中位数，提供更鲁棒的质量指标
    3. 放宽阈值默认值至 0.2（20%），适应深冷固态电池数据
    4. 剥离"计算失败"与"验证失败"：只要 linKK 执行成功，就返回 success=True
    
    Args:
        frequencies: 频率数组 (Hz)
        z_real: 阻抗实部 (Ω)
        z_imag: 阻抗虚部 (Ω)
        residual_threshold: 残差阈值（默认 0.2，即 20%）
        min_points: 最小数据点数（默认 10）
        c: linKK 正则化参数（默认 0.5，用于控制 μ 阈值）
        max_M: linKK 最大基函数数量（默认 100）
        fit_type: linKK 拟合类型（'complex', 'real', 'imag'，默认 'complex'）
        preprocess: 是否预处理（排序 + 离群点剔除）
    
    Returns:
        dict: 包含以下字段
            - success: bool，是否成功执行校验（linKK 计算成功即为 True）
            - passed: bool，是否通过 KK 校验（基于 median_mu）
            - score: float (0-1)，越高越好（基于 median_mu）
            - mu_mean: float，平均相对残差
            - mu_median: float，中位数相对残差（新增，核心指标）
            - mu_max: float，最大相对残差
            - mu_rmse: float，RMSE 相对残差（新增）
            - mu_std: float，残差标准差
            - is_valid: bool，数据是否有效（同 passed，基于 median_mu）
            - method: str，使用的方法
            - message: str，结果描述
            - error: str or None，失败原因（仅输入错误或 linKK 崩溃）
            - details: dict，详细信息（包含拟合的 M 值）
    """
    # 检查 impedance 库是否可用
    if not IMPEDANCE_AVAILABLE:
        return {
            'success': False,
            'passed': False,
            'score': 0.0,
            'mu_mean': None,
            'mu_median': None,
            'mu_max': None,
            'mu_rmse': None,
            'mu_std': None,
            'is_valid': False,
            'method': 'linKK_impedance',
            'message': 'impedance 库未安装',
            'error': 'impedance library not available. Install with: pip install impedance',
            'details': {}
        }
    
    # 输入验证
    try:
        freq = np.array(frequencies, dtype=float)
        zreal = np.array(z_real, dtype=float)
        zimag = np.array(z_imag, dtype=float)
    except Exception as e:
        return {
            'success': False,
            'passed': False,
            'score': 0.0,
            'mu_mean': None,
            'mu_median': None,
            'mu_max': None,
            'mu_rmse': None,
            'mu_std': None,
            'is_valid': False,
            'method': 'linKK_impedance',
            'message': f'输入数据格式错误: {str(e)}',
            'error': f'Input data format error: {str(e)}',
            'details': {}
        }
    
    if len(freq) != len(zreal) or len(freq) != len(zimag):
        return {
            'success': False,
            'passed': False,
            'score': 0.0,
            'mu_mean': None,
            'mu_median': None,
            'mu_max': None,
            'mu_rmse': None,
            'mu_std': None,
            'is_valid': False,
            'method': 'linKK_impedance',
            'message': '数据长度不匹配',
            'error': f'Array length mismatch: freq={len(freq)}, zreal={len(zreal)}, zimag={len(zimag)}',
            'details': {}
        }
    
    if len(freq) < min_points:
        # 点数不足不是计算失败，而是数据不满足前置条件
        return {
            'success': True,
            'passed': False,
            'score': 0.0,
            'mu_mean': None,
            'mu_median': None,
            'mu_max': None,
            'mu_rmse': None,
            'mu_std': None,
            'is_valid': False,
            'method': 'linKK_impedance',
            'message': f'数据点不足（需要至少 {min_points} 个，实际 {len(freq)}）',
            'error': None,  # 不是错误，只是条件不满足
            'details': {'n_points': len(freq), 'reason': 'insufficient_points'}
        }
    
    preprocess_info = None
    
    # 预处理（如果启用）
    if preprocess:
        try:
            freq, zreal, zimag, preprocess_info = preprocess_eis_data(freq, zreal, zimag)
        except Exception as e:
            return {
                'success': False,
                'passed': False,
                'score': 0.0,
                'mu_mean': None,
                'mu_median': None,
                'mu_max': None,
                'mu_rmse': None,
                'mu_std': None,
                'is_valid': False,
                'method': 'linKK_impedance',
                'message': f'预处理失败: {str(e)}',
                'error': f'Preprocessing error: {str(e)}',
                'details': {}
            }
    
    # 执行 linKK 校验
    try:
        # 符号约定（修正版）：本项目解析器（chi_parser）把数据文件第 3 列原样读入 z_imag，
        # 该列即真实虚部 Im(Z)——容抗弧区为负、(高频)感抗尾为正。lin-KK 以因果 RC(Voigt)
        # 串联拟合，要求容性数据 Im(Z)<0，故正确的复数阻抗为 Z = zreal + 1j*zimag。
        #   历史 bug：曾用 Z = zreal - 1j*zimag，等于把每条谱翻成反因果共轭，使 lin-KK
        #   残差被系统性抬高、产生大量假 KK 警告（实测全样 220 条谱中 133 条假报警，
        #   符号修正后 μ_median 由 ~0.21-0.28 降至 ~0.005-0.010）。已修正。
        # 本修复仅影响 KK 质检；Rb/σ/Arrhenius 用过零点/相位拟合，不受符号影响。
        freq_fit = freq
        zreal_fit = zreal
        zimag_fit = zimag
        n_inductive_trimmed = 0
        if trim_inductive_tail:
            # 高频感抗尾(Im(Z)>0)与非物理负实部(Zr<=0)无法由容性 RC 模型表达，
            # KK 校验前剔除（仅用于 KK，不改变上游 Rb/σ 计算所用的原始谱）。
            cap_mask = (zimag_fit < 0) & (zreal_fit > 0)
            if int(np.sum(cap_mask)) >= min_points:
                n_inductive_trimmed = int(len(freq_fit) - int(np.sum(cap_mask)))
                freq_fit = freq_fit[cap_mask]
                zreal_fit = zreal_fit[cap_mask]
                zimag_fit = zimag_fit[cap_mask]

        Z = zreal_fit + 1j * zimag_fit

        # 调用 impedance.validation.linKK
        # 返回：M (基函数数量), mu (总残差), Z_fit (拟合的阻抗), 
        #       res_real (实部残差数组), res_imag (虚部残差数组)
        M, mu, Z_fit, res_real, res_imag = linKK(freq_fit, Z, c=c, max_M=max_M, fit_type=fit_type)
        
        # ===== 增强残差统计（使用残差数组而非单个 mu 值） =====
        
        # 合并实部和虚部残差（取绝对值）
        residuals_combined = np.concatenate([np.abs(res_real), np.abs(res_imag)])
        
        # 计算多种统计量
        mu_mean = float(np.mean(residuals_combined))
        mu_median = float(np.median(residuals_combined))  # 新增：中位数（核心指标）
        mu_max = float(np.max(residuals_combined))
        mu_rmse = float(np.sqrt(np.mean(residuals_combined**2)))  # 新增：RMSE
        mu_std = float(np.std(residuals_combined))
        
        # 保留分量统计（用于详细分析）
        mu_mean_real = float(np.mean(np.abs(res_real)))
        mu_mean_imag = float(np.mean(np.abs(res_imag)))
        mu_median_real = float(np.median(np.abs(res_real)))
        mu_median_imag = float(np.median(np.abs(res_imag)))
        mu_max_real = float(np.max(np.abs(res_real)))
        mu_max_imag = float(np.max(np.abs(res_imag)))
        
        # ===== 修改判定逻辑：使用中位数代替最大值 =====
        # 这样可以极大地增强抗边缘噪点能力
        passed = mu_median < residual_threshold
        is_valid = passed
        
        # 计算评分（0-1，基于中位数）
        score = max(0.0, 1.0 - mu_median / residual_threshold)
        
        # 生成消息
        if passed:
            message = f'KK 校验通过 (μ_median={mu_median:.4f} < {residual_threshold:.4f})'
        else:
            message = f'KK 校验失败 (μ_median={mu_median:.4f} > {residual_threshold:.4f})'
        
        # ===== 关键：只要 linKK 执行成功，就返回 success=True =====
        # 即使 is_valid=False，也代表计算成功了，只是数据质量不佳
        return {
            'success': True,  # linKK 计算成功
            'passed': passed,
            'score': float(score),
            'mu_mean': mu_mean,
            'mu_median': mu_median,  # 新增：中位数（核心指标）
            'mu_max': mu_max,
            'mu_rmse': mu_rmse,  # 新增：RMSE
            'mu_std': mu_std,
            'is_valid': is_valid,
            'method': 'linKK_impedance',
            'message': message,
            'error': None,
            'details': {
                'M': int(M),
                'mu_total': float(mu),  # linKK 返回的总 μ 值
                'mu_mean_real': mu_mean_real,
                'mu_mean_imag': mu_mean_imag,
                'mu_median_real': mu_median_real,
                'mu_median_imag': mu_median_imag,
                'mu_max_real': mu_max_real,
                'mu_max_imag': mu_max_imag,
                'n_points': len(freq_fit),
                'n_points_input': len(freq),
                'n_inductive_trimmed': n_inductive_trimmed,
                'sign_convention': 'Z = Zr + 1j*Zi (Im(Z)<0 capacitive)',
                'threshold': residual_threshold,
                'fit_type': fit_type,
                'c': c,
                'preprocess': preprocess_info,
                'validation_metric': 'median'  # 标记使用中位数判定
            }
        }
        
    except Exception as e:
        # 只有 linKK 真正崩溃时才返回 success=False
        return {
            'success': False,
            'passed': False,
            'score': 0.0,
            'mu_mean': None,
            'mu_median': None,
            'mu_max': None,
            'mu_rmse': None,
            'mu_std': None,
            'is_valid': False,
            'method': 'linKK_impedance',
            'message': f'linKK 计算失败: {str(e)}',
            'error': f'linKK computation error: {str(e)}',
            'details': {'exception': str(e)}
        }


# ============================================================
# 数据预处理
# ============================================================

def preprocess_eis_data(
    frequencies,
    z_real,
    z_imag,
    remove_outliers=True,
    outlier_iqr_factor=1.5
):
    """
    EIS 数据预处理：频率排序 + 离群点剔除（纯函数）
    
    Args:
        frequencies: 频率数组 (Hz)
        z_real: 阻抗实部 (Ω)
        z_imag: 阻抗虚部 (Ω)
        remove_outliers: 是否剔除离群点
        outlier_iqr_factor: IQR 倍数（默认 1.5）
    
    Returns:
        tuple: (freq, zreal, zimag, preprocess_info)
    """
    freq = np.array(frequencies, dtype=float)
    zreal = np.array(z_real, dtype=float)
    zimag = np.array(z_imag, dtype=float)
    
    preprocess_info = {
        'original_points': len(freq),
        'freq_sorted': False,
        'outliers_removed': 0,
        'final_points': len(freq)
    }
    
    # 频率排序（升序：低频 → 高频，linKK 通常期望这个顺序）
    if not np.all(np.diff(freq) >= 0):
        sort_idx = np.argsort(freq)
        freq = freq[sort_idx]
        zreal = zreal[sort_idx]
        zimag = zimag[sort_idx]
        preprocess_info['freq_sorted'] = True
    
    # 离群点剔除（基于阻抗模的 IQR）
    if remove_outliers and len(freq) > 10:
        z_magnitude = np.sqrt(zreal**2 + zimag**2)
        q1, q3 = np.percentile(z_magnitude, [25, 75])
        iqr = q3 - q1
        
        if iqr > 0:
            lower = q1 - outlier_iqr_factor * iqr
            upper = q3 + outlier_iqr_factor * iqr
            mask = (z_magnitude >= lower) & (z_magnitude <= upper)
            
            # 确保至少保留 80% 的数据
            if np.sum(mask) >= len(freq) * 0.8:
                n_removed = len(freq) - np.sum(mask)
                freq = freq[mask]
                zreal = zreal[mask]
                zimag = zimag[mask]
                preprocess_info['outliers_removed'] = int(n_removed)
    
    preprocess_info['final_points'] = len(freq)
    
    return freq, zreal, zimag, preprocess_info


# ============================================================
# 向后兼容接口（可选）
# ============================================================

def kk_check(freq, zreal, zimag, residual_threshold=0.2, preprocess=True):
    """
    便捷函数：执行 KK 一致性校验（向后兼容接口）
    
    Args:
        freq: 频率数组 (Hz)
        zreal: 阻抗实部 (Ω)
        zimag: 阻抗虚部 (Ω)
        residual_threshold: 残差阈值（默认 0.2，即 20%）
        preprocess: 是否进行预处理
    
    Returns:
        dict: KK 校验结果字典（包含 'ok' 字段以兼容旧代码）
    """
    result = validate_kk_consistency(
        frequencies=freq,
        z_real=zreal,
        z_imag=zimag,
        residual_threshold=residual_threshold,
        preprocess=preprocess
    )
    
    # 添加 'ok' 字段以兼容旧代码
    result['ok'] = result['passed']
    
    return result
