# -*- coding: utf-8 -*-
"""
DRT (Distribution of Relaxation Times) 分析算法（纯函数版）

这是一个纯粹的算法模块，遵循以下原则：
1. 所有函数都是纯函数，只接受参数输入，返回计算结果
2. 无全局副作用（无 warnings、无状态修改）
3. 绝对禁止画图操作（由 reporting 模块负责可视化）
4. 统一错误抛出：返回规范的字典格式
5. 配置参数作为函数参数，便于后续从统一配置传入

实现弛豫时间分布计算和峰识别：
- Tikhonov 正则化求解 DRT
- L 曲线法自动选择正则化参数
- 峰识别和特征提取
- 拟合质量评估

版本：3.0.0 (重构版)
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
from scipy.linalg import solve, svd


# ============================================================
# 公共接口：DRT 分析
# ============================================================

def analyze_drt(
    frequencies,
    z_real,
    z_imag,
    lambda_reg=None,
    tau_range=None,
    n_tau=100,
    min_points=10,
    min_prominence=0.02
):
    """
    执行 DRT（弛豫时间分布）分析（纯函数版主入口）
    
    Args:
        frequencies: 频率数组 (Hz)
        z_real: 阻抗实部 (Ω)
        z_imag: 阻抗虚部 (Ω)
        lambda_reg: 正则化参数，None 时自动选择（L 曲线法）
        tau_range: 弛豫时间范围 (s)，tuple (tau_min, tau_max)，None 时自动确定
        n_tau: 弛豫时间点数（默认 100）
        min_points: 最小数据点数（默认 10）
        min_prominence: 峰识别的最小突出度（相对于最大值，默认 0.02）
    
    Returns:
        dict: 包含以下字段
            - success: bool，是否成功
            - tau: np.ndarray，弛豫时间数组 (s)
            - G: np.ndarray，DRT 强度数组 (Ω)
            - R_inf: float，高频极限电阻 (Ω)
            - lambda_reg: float，使用的正则化参数
            - fit_quality: dict，拟合质量指标
            - peaks: list[dict]，识别的峰
            - Z_fit: np.ndarray，重构的阻抗（复数）
            - error: str or None，失败原因
            - details: dict，详细信息
    """
    # 输入验证
    if len(frequencies) < min_points:
        return {
            'success': False,
            'tau': None,
            'G': None,
            'R_inf': None,
            'lambda_reg': None,
            'fit_quality': None,
            'peaks': [],
            'Z_fit': None,
            'error': f'数据点过少（需要至少 {min_points} 个，实际 {len(frequencies)}）',
            'details': {'n_points': len(frequencies)}
        }
    
    try:
        # 计算 DRT 分布
        drt_result = compute_drt_distribution(
            frequencies=frequencies,
            z_real=z_real,
            z_imag=z_imag,
            lambda_reg=lambda_reg,
            tau_range=tau_range,
            n_tau=n_tau
        )
        
        if not drt_result['success']:
            return drt_result
        
        # 识别峰
        peaks = identify_drt_peaks(
            tau=drt_result['tau'],
            G=drt_result['G'],
            min_prominence=min_prominence
        )
        
        # 组合结果
        result = {
            'success': True,
            'tau': drt_result['tau'],
            'G': drt_result['G'],
            'R_inf': drt_result['R_inf'],
            'lambda_reg': drt_result['lambda_reg'],
            'fit_quality': drt_result['fit_quality'],
            'peaks': peaks,
            'Z_fit': drt_result['Z_fit'],
            'error': None,
            'details': drt_result['details']
        }
        
        return result
        
    except Exception as e:
        return {
            'success': False,
            'tau': None,
            'G': None,
            'R_inf': None,
            'lambda_reg': None,
            'fit_quality': None,
            'peaks': [],
            'Z_fit': None,
            'error': f'DRT 分析异常: {str(e)}',
            'details': {'exception': str(e)}
        }


def compute_drt_distribution(
    frequencies,
    z_real,
    z_imag,
    lambda_reg=None,
    tau_range=None,
    n_tau=100,
    lambda_0=5e-4
):
    """
    计算 DRT 分布（纯函数）
    
    使用 Tikhonov 正则化求解 DRT，可选 L 曲线法自动选择正则化参数
    
    Args:
        frequencies: 频率数组 (Hz)
        z_real: 阻抗实部 (Ω)
        z_imag: 阻抗虚部 (Ω)
        lambda_reg: 正则化参数，None 时自动选择
        tau_range: 弛豫时间范围 (s)，None 时自动确定
        n_tau: 弛豫时间点数
        lambda_0: 默认正则化参数（自动选择失败时使用）
    
    Returns:
        dict: 规范的结果字典
    """
    freq = np.array(frequencies, dtype=float)
    zreal = np.array(z_real, dtype=float)
    zimag = np.array(z_imag, dtype=float)
    
    omega = 2 * np.pi * freq
    Z_data = zreal + 1j * zimag
    
    # 确定弛豫时间范围
    if tau_range is None:
        tau_min = 1 / (2 * np.pi * freq.max()) / 5
        tau_max = 1 / (2 * np.pi * freq.min()) * 5
        tau_range = (tau_min, tau_max)
    
    try:
        tau = np.logspace(np.log10(tau_range[0]), np.log10(tau_range[1]), n_tau)
    except Exception as e:
        return {
            'success': False,
            'tau': None,
            'G': None,
            'R_inf': None,
            'lambda_reg': None,
            'fit_quality': None,
            'Z_fit': None,
            'error': f'弛豫时间范围无效: {str(e)}',
            'details': {'tau_range': tau_range}
        }
    
    # 构建系数矩阵
    try:
        A_real, A_imag = _build_coefficient_matrix(omega, tau)
        A = np.vstack([A_real, A_imag])
    except Exception as e:
        return {
            'success': False,
            'tau': None,
            'G': None,
            'R_inf': None,
            'lambda_reg': None,
            'fit_quality': None,
            'Z_fit': None,
            'error': f'系数矩阵构建失败: {str(e)}',
            'details': {}
        }
    
    # 计算 R_inf（高频极限电阻）
    try:
        high_freq_mask = freq > np.percentile(freq, 85)
        if np.sum(high_freq_mask) >= 3:
            R_inf = float(np.median(zreal[high_freq_mask]))
        else:
            R_inf = float(zreal[-1])
    except Exception:
        R_inf = float(np.min(zreal))
    
    # 构建右端项
    b_real = zreal - R_inf
    b_imag = -zimag
    b = np.hstack([b_real, b_imag])
    
    # 自动选择正则化参数
    if lambda_reg is None:
        try:
            lambda_reg = _select_regularization_parameter(A, b, tau, lambda_0)
        except Exception as e:
            lambda_reg = lambda_0
    
    # 求解 Tikhonov 正则化问题
    try:
        G = _solve_tikhonov_regularization(A, b, tau, lambda_reg)
    except Exception as e:
        return {
            'success': False,
            'tau': None,
            'G': None,
            'R_inf': R_inf,
            'lambda_reg': lambda_reg,
            'fit_quality': None,
            'Z_fit': None,
            'error': f'Tikhonov 求解失败: {str(e)}',
            'details': {'R_inf': R_inf}
        }
    
    # 重构阻抗
    try:
        Z_fit = _reconstruct_impedance(omega, tau, G, R_inf)
    except Exception as e:
        return {
            'success': False,
            'tau': tau,
            'G': G,
            'R_inf': R_inf,
            'lambda_reg': lambda_reg,
            'fit_quality': None,
            'Z_fit': None,
            'error': f'阻抗重构失败: {str(e)}',
            'details': {}
        }
    
    # 计算拟合质量
    try:
        fit_quality = _calculate_fit_quality(Z_data, Z_fit)
    except Exception as e:
        fit_quality = {
            'chi_squared': None,
            'chi_squared_reduced': None,
            'r_squared': None,
            'rmse': None,
            'quality_rating': 'unknown',
            'is_reliable': False,
            'error': str(e)
        }
    
    return {
        'success': True,
        'tau': tau,
        'G': G,
        'R_inf': R_inf,
        'lambda_reg': lambda_reg,
        'fit_quality': fit_quality,
        'Z_fit': Z_fit,
        'error': None,
        'details': {
            'tau_range': tau_range,
            'n_tau': n_tau,
            'n_freq': len(freq)
        }
    }


def identify_drt_peaks(tau, G, min_prominence=0.02):
    """
    识别 DRT 峰（纯函数）
    
    Args:
        tau: 弛豫时间数组 (s)
        G: DRT 强度数组 (Ω)
        min_prominence: 最小峰突出度（相对于最大值）
    
    Returns:
        list[dict]: 峰列表，每个峰包含 tau, G, frequency, relative_intensity
    """
    if tau is None or G is None or len(tau) < 3 or len(G) < 3:
        return []
    
    peaks = []
    G_max = np.max(G)
    
    if G_max <= 0:
        return []
    
    threshold = G_max * min_prominence
    
    # 简单峰检测：找局部最大值
    for i in range(1, len(G) - 1):
        if G[i] > G[i-1] and G[i] > G[i+1] and G[i] > threshold:
            try:
                peak_freq = 1 / (2 * np.pi * tau[i])
                peaks.append({
                    'tau': float(tau[i]),
                    'G': float(G[i]),
                    'frequency': float(peak_freq),
                    'relative_intensity': float(G[i] / G_max)
                })
            except Exception:
                continue
    
    # 按强度排序（降序）
    peaks.sort(key=lambda x: x['G'], reverse=True)
    
    return peaks


# ============================================================
# 内部函数：系数矩阵构建
# ============================================================

def _build_coefficient_matrix(omega, tau):
    """
    构建 DRT 系数矩阵（内部函数）
    
    阻抗模型：Z(ω) = R_inf + ∫ G(τ) / (1 + jωτ) d(ln τ)
    
    离散化后：
        Z_real[i] = R_inf + Σ_j G[j] * Δ(ln τ) / (1 + (ω[i]τ[j])²)
        Z_imag[i] = -Σ_j G[j] * Δ(ln τ) * ω[i]τ[j] / (1 + (ω[i]τ[j])²)
    
    Args:
        omega: 角频率数组 (rad/s)
        tau: 弛豫时间数组 (s)
    
    Returns:
        tuple: (A_real, A_imag)
    """
    n_freq = len(omega)
    n_tau = len(tau)
    
    A_real = np.zeros((n_freq, n_tau))
    A_imag = np.zeros((n_freq, n_tau))
    
    for i, w in enumerate(omega):
        for j, t in enumerate(tau):
            wt = w * t
            denominator = 1 + (wt)**2
            A_real[i, j] = 1 / denominator
            A_imag[i, j] = wt / denominator
    
    # 计算对数间距 Δ(ln τ)
    d_ln_tau = np.diff(np.log(tau))
    d_ln_tau = np.append(d_ln_tau, d_ln_tau[-1])
    
    # 乘以对数间距
    A_real = A_real * d_ln_tau[np.newaxis, :]
    A_imag = A_imag * d_ln_tau[np.newaxis, :]
    
    return A_real, A_imag


# ============================================================
# 内部函数：正则化参数选择（L 曲线法）
# ============================================================

def _select_regularization_parameter(A, b, tau, lambda_0=5e-4):
    """
    使用 L 曲线法自动选择正则化参数（SVD 加速版）
    
    L 曲线法：在对数坐标系中绘制 ||Ax - b|| vs ||Lx||，
    选择曲率最大的点对应的 λ
    
    优化策略：
    1. 构建增广矩阵进行一次 SVD 分解
    2. 利用 SVD 的标准 Tikhonov 正则化闭式解
    3. λ 循环内仅使用向量和标量运算，无矩阵乘法
    
    Args:
        A: 系数矩阵 (2*n_freq, n_tau)
        b: 右端项 (2*n_freq,)
        tau: 弛豫时间数组
        lambda_0: 默认值（L 曲线法失败时使用）
    
    Returns:
        float: 最优正则化参数
    """
    lambda_candidates = np.logspace(-8, -2, 80)
    
    # 构建正则化矩阵
    L = _build_regularization_matrix(len(tau))
    
    # ===== SVD 前置分解（循环外部，仅执行一次）=====
    try:
        # 对增广矩阵进行 SVD：[A; sqrt(λ)*L]
        # 这里先对 A 和 L 分别 SVD，然后利用 Tikhonov 的标准形式
        # 
        # 标准 Tikhonov: min ||Ax - b||² + λ||Lx||²
        # 等价于求解: (A^T A + λ L^T L) x = A^T b
        # 
        # 使用 A 的 SVD: A = U S V^T
        # 解为: x = V * diag(f_i) * U^T b
        # 其中 f_i = S_i / (S_i² + λ * ||L*V[:,i]||²)
        
        # 对 A 进行 SVD（经济型，只保留非零奇异值）
        U, S, Vt = svd(A, full_matrices=False)
        V = Vt.T  # 转置得到 V
        
        # 预计算 L*V（形状：(n-1, n_tau)）
        LV = L @ V  # 这是循环外的一次矩阵乘法，可接受
        
        # 计算每个奇异向量在 L 空间的范数平方
        # ||L*V[:,i]||² for each i
        LV_norms_sq = np.sum(LV**2, axis=0)  # 形状：(n_tau,)
        
        # 计算 U^T * b（形状：(n_tau,)）
        Utb = U.T @ b
        
    except np.linalg.LinAlgError:
        # SVD 失败，返回默认值
        return lambda_0
    
    # ===== 快速循环：仅使用向量运算 =====
    residual_norms = []
    solution_norms = []
    
    for lam in lambda_candidates:
        try:
            # 计算过滤因子（Tikhonov 正则化的标准公式）
            # f_i = S_i² / (S_i² + λ * ||L*V[:,i]||²)
            filter_factors = S**2 / (S**2 + lam * LV_norms_sq)
            
            # 计算解：x = V * diag(f_i * S_i^(-1)) * U^T b
            # 分解为：x = V * (filter_factors * S^(-1) * Utb)
            coeffs = (filter_factors / S) * Utb  # 逐元素乘法
            x_lambda = V @ coeffs  # 一次矩阵-向量乘法
            
            # 计算残差范数：||A*x - b||
            # A*x = U * S * V^T * x = U * S * V^T * V * coeffs = U * S * coeffs
            Ax = U @ (S * coeffs)  # 向量运算
            residual = Ax - b
            residual_norm = np.linalg.norm(residual)
            
            # 计算解的范数（正则化项）：||L*x||
            # L*x = L * V * coeffs = LV * coeffs
            Lx = LV @ coeffs  # 向量运算
            solution_norm = np.linalg.norm(Lx)
            
            residual_norms.append(residual_norm)
            solution_norms.append(solution_norm)
            
        except Exception:
            residual_norms.append(np.inf)
            solution_norms.append(np.inf)
    
    residual_norms = np.array(residual_norms)
    solution_norms = np.array(solution_norms)
    
    # 过滤无效值
    valid_mask = np.isfinite(residual_norms) & np.isfinite(solution_norms) & (residual_norms > 0) & (solution_norms > 0)
    if not np.any(valid_mask):
        return lambda_0
    
    log_residual = np.log10(residual_norms[valid_mask])
    log_solution = np.log10(solution_norms[valid_mask])
    
    if len(log_residual) < 3:
        return lambda_0
    
    # 计算曲率找拐点（L-curve corner）
    curvatures = []
    for i in range(1, len(log_residual) - 1):
        dx1 = log_residual[i] - log_residual[i-1]
        dx2 = log_residual[i+1] - log_residual[i]
        dy1 = log_solution[i] - log_solution[i-1]
        dy2 = log_solution[i+1] - log_solution[i]
        
        dx_prime = (dx1 + dx2) / 2
        dy_prime = (dy1 + dy2) / 2
        dx_second = dx2 - dx1
        dy_second = dy2 - dy1
        
        numerator = abs(dx_second * dy_prime - dy_second * dx_prime)
        denominator = (dx_prime**2 + dy_prime**2)**(3/2) + 1e-10
        curvatures.append(numerator / denominator)
    
    if curvatures:
        best_idx = np.argmax(curvatures) + 1
        valid_indices = np.where(valid_mask)[0]
        return float(lambda_candidates[valid_indices[best_idx]])
    
    return lambda_0


def _build_regularization_matrix(n):
    """
    构建一阶差分正则化矩阵（内部函数）
    
    L * G 计算相邻点的差分，用于平滑约束
    
    Args:
        n: 矩阵维度
    
    Returns:
        np.ndarray: (n-1, n) 差分矩阵
    """
    L = np.zeros((n-1, n))
    for i in range(n-1):
        L[i, i] = -1
        L[i, i+1] = 1
    return L


# ============================================================
# 内部函数：Tikhonov 正则化求解
# ============================================================

def _solve_tikhonov_regularization(A, b, tau, lambda_reg):
    """
    求解 Tikhonov 正则化问题（内部函数）
    
    min ||Ax - b||² + λ ||Lx||²
    
    正规方程：(A^T A + λ L^T L) x = A^T b
    
    Args:
        A: 系数矩阵
        b: 右端项
        tau: 弛豫时间数组
        lambda_reg: 正则化参数
    
    Returns:
        np.ndarray: DRT 分布 G
    """
    L = _build_regularization_matrix(len(tau))
    AtA = A.T @ A
    Atb = A.T @ b
    LtL = L.T @ L
    
    try:
        G = solve(AtA + lambda_reg * LtL, Atb)
    except np.linalg.LinAlgError:
        # 如果直接求解失败，使用伪逆
        try:
            G = np.linalg.pinv(A) @ b
        except Exception:
            raise ValueError("正则化求解失败（矩阵奇异）")
    
    # 强制非负约束（物理意义：G ≥ 0）
    G = np.maximum(G, 0)
    
    return G


# ============================================================
# 内部函数：阻抗重构
# ============================================================

def _reconstruct_impedance(omega, tau, G, R_inf):
    """
    根据 DRT 重构阻抗（内部函数）
    
    Z(ω) = R_inf + ∫ G(τ) / (1 + jωτ) d(ln τ)
    
    Args:
        omega: 角频率数组 (rad/s)
        tau: 弛豫时间数组 (s)
        G: DRT 分布 (Ω)
        R_inf: 高频极限电阻 (Ω)
    
    Returns:
        np.ndarray: 复数阻抗
    """
    n_freq = len(omega)
    Z_fit = np.zeros(n_freq, dtype=complex)
    
    d_ln_tau = np.diff(np.log(tau))
    d_ln_tau = np.append(d_ln_tau, d_ln_tau[-1])
    
    for i, w in enumerate(omega):
        Z_real = R_inf
        Z_imag = 0
        
        for j, (t, g, dt) in enumerate(zip(tau, G, d_ln_tau)):
            wt = w * t
            denominator = 1 + (wt)**2
            Z_real += g * dt / denominator
            Z_imag += g * dt * wt / denominator
        
        Z_fit[i] = Z_real - 1j * Z_imag
    
    return Z_fit


# ============================================================
# 内部函数：拟合质量评估
# ============================================================

def _calculate_fit_quality(Z_data, Z_fit):
    """
    计算 DRT 拟合质量指标（内部函数）
    
    Args:
        Z_data: 实测阻抗（复数）
        Z_fit: 拟合阻抗（复数）
    
    Returns:
        dict: 拟合质量指标
    """
    residual = Z_data - Z_fit
    n_data = len(Z_data)
    
    Z_magnitude = np.abs(Z_data)
    
    # 防止除零
    Z_magnitude_safe = np.where(Z_magnitude > 0, Z_magnitude, 1.0)
    
    residual_real_normalized = residual.real / Z_magnitude_safe
    residual_imag_normalized = residual.imag / Z_magnitude_safe
    
    # χ² (chi-squared)
    chi_squared = np.sum(residual_real_normalized**2 + residual_imag_normalized**2)
    chi_squared_reduced = chi_squared / n_data if n_data > 0 else np.inf
    
    # R² (coefficient of determination)
    ss_res = np.sum(np.abs(residual)**2)
    ss_tot = np.sum(np.abs(Z_data - np.mean(Z_data))**2)
    r_squared = 1 - ss_res / ss_tot if ss_tot > 0 else 0
    
    # RMSE
    rmse = np.sqrt(np.mean(np.abs(residual)**2))
    
    # 质量评级
    if chi_squared_reduced < 1.5:
        quality_rating = 'excellent'
    elif chi_squared_reduced < 3.0:
        quality_rating = 'good'
    elif chi_squared_reduced < 5.0:
        quality_rating = 'acceptable'
    else:
        quality_rating = 'poor'
    
    return {
        'chi_squared': float(chi_squared),
        'chi_squared_reduced': float(chi_squared_reduced),
        'r_squared': float(r_squared),
        'rmse': float(rmse),
        'quality_rating': quality_rating,
        'is_reliable': chi_squared_reduced < 5.0 and r_squared > 0.80
    }


# ============================================================
# 向后兼容接口（可选）
# ============================================================

def drt_analyze(freq, zreal, zimag):
    """
    便捷函数：执行 DRT 分析（向后兼容接口）
    
    Args:
        freq: 频率数组 (Hz)
        zreal: 阻抗实部 (Ω)
        zimag: 阻抗虚部 (Ω)
    
    Returns:
        dict: DRT 分析结果字典
    """
    return analyze_drt(
        frequencies=freq,
        z_real=zreal,
        z_imag=zimag
    )
