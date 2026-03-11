# -*- coding: utf-8 -*-
"""
Distribution of Relaxation Times (DRT) 分析模块

基于 Ridge 回归的 DRT 最小可用版本：
- 使用 log(tau) 网格 + 核矩阵 K(ω,τ)=1/(1+jωτ)
- 非负约束 + L2 平滑（二阶差分正则）
- 峰值检测与参数提取

参考文献:
Wan et al. (2015) "Influence of the Discretization Methods on the Distribution 
of Relaxation Times Deconvolution" Electrochimica Acta, 184, 483-499.

作者: Cursor AI Agent
日期: 2025-12-28
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
from scipy.optimize import nnls
from scipy.signal import find_peaks


class DRTAnalyzer:
    """Distribution of Relaxation Times 分析器（Ridge 回归版本）"""
    
    def __init__(self, 
                 tau_decades: float = 8.0,
                 tau_n_points: int = 100,
                 regularization: float = 1e-3):
        """
        初始化 DRT 分析器
        
        Args:
            tau_decades: tau 网格跨度（decade）
            tau_n_points: tau 网格点数
            regularization: L2 正则化强度
        """
        self.tau_decades = tau_decades
        self.tau_n_points = tau_n_points
        self.regularization = regularization
    
    def compute_drt(self, freq: np.ndarray, zreal: np.ndarray, zimag: np.ndarray) -> Dict:
        """
        计算 DRT
        
        Args:
            freq: 频率数组 (Hz)
            zreal: 阻抗实部 (Ω)
            zimag: 阻抗虚部 (Ω)，遵循 EIS 约定（通常为负值）
        
        Returns:
            {
                'ok': bool,
                'tau': np.ndarray,  # 松弛时间网格
                'gamma': np.ndarray,  # DRT 分布 gamma(tau)
                'recon_rmse': float,  # 重构 RMSE
                'peaks': List[Dict],  # 峰值信息
                'n_peaks': int,
                'message': str
            }
        """
        try:
            # 1. 构建 tau 网格（基于频率范围）
            omega = 2 * np.pi * freq
            tau_min = 1.0 / omega.max() / 10  # 比最高频小一个数量级
            tau_max = 1.0 / omega.min() * 10  # 比最低频大一个数量级
            
            # 确保跨度足够
            if np.log10(tau_max / tau_min) < self.tau_decades:
                tau_center = np.sqrt(tau_min * tau_max)
                tau_min = tau_center * 10**(-self.tau_decades/2)
                tau_max = tau_center * 10**(self.tau_decades/2)
            
            log_tau = np.linspace(np.log10(tau_min), np.log10(tau_max), self.tau_n_points)
            tau = 10**log_tau
            
            # 2. 构建核矩阵 K(ω, τ)
            # 对于 DRT，Z'' = ∫ gamma(tau) * K(ω, τ) d(ln tau)
            # 其中 K(ω, τ) = (ω*τ) / (1 + (ω*τ)^2)
            kernel_matrix = self._build_kernel_matrix(omega, tau)
            
            # 3. Ridge 回归求解（非负最小二乘 + L2 正则）
            # 使用虚部（因为 DRT 主要反映在虚部）
            zimag_abs = np.abs(zimag)  # 取绝对值，因为约定可能是负值
            
            gamma, residual = self._solve_ridge_nnls(
                kernel_matrix, zimag_abs, self.regularization
            )
            
            # 4. 重构阻抗并计算 RMSE
            zimag_recon = kernel_matrix @ gamma
            recon_rmse = np.sqrt(np.mean((zimag_abs - zimag_recon)**2))
            recon_rmse_relative = recon_rmse / np.mean(zimag_abs) if np.mean(zimag_abs) > 0 else 1.0
            
            # 5. 峰值检测
            peaks_info = self._detect_peaks(tau, gamma)
            
            # 6. 判断成功
            ok = recon_rmse_relative < 0.5  # 相对 RMSE < 50%
            
            return {
                'ok': ok,
                'tau': tau,
                'gamma': gamma,
                'recon_rmse': float(recon_rmse),
                'recon_rmse_relative': float(recon_rmse_relative),
                'peaks': peaks_info,
                'n_peaks': len(peaks_info),
                'message': 'DRT 计算成功' if ok else f'DRT 重构误差较大 ({recon_rmse_relative:.1%})'
            }
            
        except Exception as e:
            return {
                'ok': False,
                'tau': None,
                'gamma': None,
                'recon_rmse': None,
                'recon_rmse_relative': None,
                'peaks': [],
                'n_peaks': 0,
                'message': f'DRT 计算异常: {str(e)}'
            }
    
    def _build_kernel_matrix(self, omega: np.ndarray, tau: np.ndarray) -> np.ndarray:
        """
        构建 DRT 核矩阵 K(ω, τ)
        
        对于虚部:
        K(ω, τ) = (ω*τ) / (1 + (ω*τ)^2)
        
        Args:
            omega: 角频率数组
            tau: 松弛时间网格
        
        Returns:
            kernel_matrix: shape (n_freq, n_tau)
        """
        omega_2d = omega[:, np.newaxis]  # (n_freq, 1)
        tau_2d = tau[np.newaxis, :]  # (1, n_tau)
        
        omega_tau = omega_2d * tau_2d  # (n_freq, n_tau)
        
        # K(ω, τ) = (ω*τ) / (1 + (ω*τ)^2)
        kernel = omega_tau / (1 + omega_tau**2)
        
        # 乘以 d(ln tau)，对于等间距 log(tau)，这是常数
        d_log_tau = np.log(tau[-1] / tau[0]) / (len(tau) - 1)
        kernel *= d_log_tau * np.log(10)  # 从 log10 转换到 ln
        
        return kernel
    
    def _solve_ridge_nnls(self, A: np.ndarray, b: np.ndarray, 
                          regularization: float) -> Tuple[np.ndarray, float]:
        """
        求解带 L2 正则的非负最小二乘问题
        
        min ||A*x - b||^2 + lambda * ||L*x||^2
        s.t. x >= 0
        
        其中 L 是二阶差分矩阵（平滑约束）
        
        Args:
            A: 系数矩阵
            b: 目标向量
            regularization: 正则化强度
        
        Returns:
            (x, residual): 解向量和残差
        """
        n = A.shape[1]
        
        # 构建二阶差分矩阵 L
        L = self._build_second_order_diff_matrix(n)
        
        # 增广系统: [A; sqrt(lambda)*L] * x = [b; 0]
        sqrt_lambda = np.sqrt(regularization)
        A_aug = np.vstack([A, sqrt_lambda * L])
        b_aug = np.concatenate([b, np.zeros(L.shape[0])])
        
        # 非负最小二乘求解
        x, residual = nnls(A_aug, b_aug)
        
        return x, residual
    
    def _build_second_order_diff_matrix(self, n: int) -> np.ndarray:
        """
        构建二阶差分矩阵（用于平滑约束）
        
        L[i, :] = [0, ..., 0, 1, -2, 1, 0, ..., 0]
                           i-1  i  i+1
        
        Args:
            n: 向量长度
        
        Returns:
            L: shape (n-2, n)
        """
        if n < 3:
            return np.zeros((0, n))
        
        L = np.zeros((n - 2, n))
        for i in range(n - 2):
            L[i, i] = 1
            L[i, i + 1] = -2
            L[i, i + 2] = 1
        
        return L
    
    def _detect_peaks(self, tau: np.ndarray, gamma: np.ndarray, 
                     min_prominence: float = 0.05) -> List[Dict]:
        """
        检测 DRT 峰值
        
        Args:
            tau: 松弛时间网格
            gamma: DRT 分布
            min_prominence: 最小峰显著性（相对于最大值）
        
        Returns:
            peaks_info: 峰值信息列表
        """
        if len(gamma) < 3 or np.max(gamma) == 0:
            return []
        
        # 归一化显著性阈值
        prominence_threshold = min_prominence * np.max(gamma)
        
        # 峰值检测
        peak_indices, properties = find_peaks(
            gamma, 
            prominence=prominence_threshold,
            width=1
        )
        
        # 提取峰值信息
        peaks_info = []
        for i, idx in enumerate(peak_indices):
            # 峰值高度
            height = gamma[idx]
            
            # 峰值位置（tau）
            tau_peak = tau[idx]
            
            # 峰值面积（近似）
            # 使用峰宽范围内的梯形积分
            left_idx = max(0, idx - 5)
            right_idx = min(len(tau) - 1, idx + 5)
            area = np.trapz(gamma[left_idx:right_idx+1], np.log(tau[left_idx:right_idx+1]))
            
            peaks_info.append({
                'tau': float(tau_peak),
                'height': float(height),
                'area': float(area),
                'log_tau': float(np.log10(tau_peak))
            })
        
        # 按高度排序
        peaks_info.sort(key=lambda x: x['height'], reverse=True)
        
        return peaks_info


def compute_drt(freq: np.ndarray, zreal: np.ndarray, zimag: np.ndarray,
                tau_decades: float = 8.0, tau_n_points: int = 100,
                regularization: float = 1e-3) -> Dict:
    """
    便捷函数：计算 DRT
    
    Args:
        freq: 频率数组 (Hz)
        zreal: 阻抗实部 (Ω)
        zimag: 阻抗虚部 (Ω)
        tau_decades: tau 网格跨度
        tau_n_points: tau 网格点数
        regularization: L2 正则化强度
    
    Returns:
        DRT 结果字典
    """
    analyzer = DRTAnalyzer(tau_decades, tau_n_points, regularization)
    return analyzer.compute_drt(freq, zreal, zimag)

