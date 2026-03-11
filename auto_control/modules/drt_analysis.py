# -*- coding: utf-8 -*-
"""
DRT (Distribution of Relaxation Times) 分析模块 - 精简版
实现弛豫时间分布计算和峰识别

从 eis_data_analysis/phase1/core/drt_analysis.py 移植
"""
import numpy as np
from typing import Dict, List, Tuple, Optional
from scipy.linalg import solve
import warnings


class DRTAnalyzer:
    """弛豫时间分布分析器"""
    
    def __init__(self, lambda_0: float = 5e-4):
        """
        初始化DRT分析器
        
        Args:
            lambda_0: 默认正则化参数
        """
        self.lambda_0 = lambda_0
        self.tau_range = None
        self.G_drt = None
    
    def compute_drt_distribution(self, freq: np.ndarray, zreal: np.ndarray, 
                               zimag: np.ndarray, lambda_reg: Optional[float] = None,
                               tau_range: Optional[Tuple[float, float]] = None,
                               n_tau: int = 100) -> Dict:
        """
        计算DRT分布
        
        Args:
            freq: 频率数组 (Hz)
            zreal: 阻抗实部数组 (Ω)
            zimag: 阻抗虚部数组 (Ω)
            lambda_reg: 正则化参数，None时自动选择
            tau_range: 弛豫时间范围 (s)，None时自动确定
            n_tau: 弛豫时间点数
            
        Returns:
            DRT分布结果字典
        """
        if len(freq) < 10:
            warnings.warn(f"DRT分析数据点过少({len(freq)})，结果可能不可靠")
        
        omega = 2 * np.pi * freq
        Z_data = zreal + 1j * zimag
        
        # 确定弛豫时间范围
        if tau_range is None:
            tau_min = 1 / (2 * np.pi * freq.max()) / 5
            tau_max = 1 / (2 * np.pi * freq.min()) * 5
            tau_range = (tau_min, tau_max)
        
        tau = np.logspace(np.log10(tau_range[0]), np.log10(tau_range[1]), n_tau)
        
        # 构建系数矩阵
        A_real, A_imag = self._build_coefficient_matrix(omega, tau)
        A = np.vstack([A_real, A_imag])
        
        # 计算R_inf
        high_freq_mask = freq > np.percentile(freq, 85)
        if np.sum(high_freq_mask) >= 3:
            R_inf = np.median(zreal[high_freq_mask])
        else:
            R_inf = zreal[-1]
        
        b_real = zreal - R_inf
        b_imag = -zimag
        b = np.hstack([b_real, b_imag])
        
        # 自动选择正则化参数
        if lambda_reg is None:
            lambda_reg = self._select_regularization_parameter(A, b, tau)
        
        # 求解正则化问题
        G = self._solve_tikhonov_regularization(A, b, tau, lambda_reg)
        
        # 计算拟合质量
        Z_fit = self._reconstruct_impedance(omega, tau, G, R_inf)
        fit_quality = self._calculate_fit_quality(Z_data, Z_fit)
        
        self.tau_range = tau
        self.G_drt = G
        
        return {
            'tau': tau,
            'G': G,
            'R_inf': R_inf,
            'lambda_reg': lambda_reg,
            'Z_fit': Z_fit,
            'fit_quality': fit_quality,
            'tau_range': tau_range,
            'n_tau': n_tau
        }
    
    def _build_coefficient_matrix(self, omega: np.ndarray, tau: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """构建DRT系数矩阵"""
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
        
        d_ln_tau = np.diff(np.log(tau))
        d_ln_tau = np.append(d_ln_tau, d_ln_tau[-1])
        
        A_real = A_real * d_ln_tau[np.newaxis, :]
        A_imag = A_imag * d_ln_tau[np.newaxis, :]
        
        return A_real, A_imag
    
    def _select_regularization_parameter(self, A: np.ndarray, b: np.ndarray, 
                                       tau: np.ndarray) -> float:
        """使用L曲线法自动选择正则化参数"""
        lambda_candidates = np.logspace(-8, -2, 80)
        
        residual_norms = []
        solution_norms = []
        L = self._build_regularization_matrix(len(tau))
        
        for lam in lambda_candidates:
            try:
                AtA = A.T @ A
                Atb = A.T @ b
                LtL = L.T @ L
                G = solve(AtA + lam * LtL, Atb)
                
                residual = A @ G - b
                residual_norm = np.linalg.norm(residual)
                solution_norm = np.linalg.norm(L @ G)
                
                residual_norms.append(residual_norm)
                solution_norms.append(solution_norm)
            except np.linalg.LinAlgError:
                residual_norms.append(np.inf)
                solution_norms.append(np.inf)
        
        residual_norms = np.array(residual_norms)
        solution_norms = np.array(solution_norms)
        
        valid_mask = np.isfinite(residual_norms) & np.isfinite(solution_norms)
        if not np.any(valid_mask):
            return self.lambda_0
        
        log_residual = np.log10(residual_norms[valid_mask])
        log_solution = np.log10(solution_norms[valid_mask])
        
        if len(log_residual) < 3:
            return self.lambda_0
        
        # 计算曲率找拐点
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
            return lambda_candidates[valid_mask][best_idx]
        
        return self.lambda_0
    
    def _build_regularization_matrix(self, n: int) -> np.ndarray:
        """构建一阶差分正则化矩阵"""
        L = np.zeros((n-1, n))
        for i in range(n-1):
            L[i, i] = -1
            L[i, i+1] = 1
        return L
    
    def _solve_tikhonov_regularization(self, A: np.ndarray, b: np.ndarray, 
                                     tau: np.ndarray, lambda_reg: float) -> np.ndarray:
        """求解Tikhonov正则化问题"""
        L = self._build_regularization_matrix(len(tau))
        AtA = A.T @ A
        Atb = A.T @ b
        LtL = L.T @ L
        
        try:
            G = solve(AtA + lambda_reg * LtL, Atb)
        except np.linalg.LinAlgError:
            warnings.warn("正则化求解失败，使用伪逆解")
            G = np.linalg.pinv(A) @ b
        
        G = np.maximum(G, 0)
        return G
    
    def _reconstruct_impedance(self, omega: np.ndarray, tau: np.ndarray, 
                             G: np.ndarray, R_inf: float) -> np.ndarray:
        """根据DRT重构阻抗"""
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
    
    def _calculate_fit_quality(self, Z_data: np.ndarray, Z_fit: np.ndarray) -> Dict:
        """计算DRT拟合质量指标"""
        residual = Z_data - Z_fit
        n_data = len(Z_data)
        
        Z_magnitude = np.abs(Z_data)
        residual_real_normalized = residual.real / Z_magnitude
        residual_imag_normalized = residual.imag / Z_magnitude
        
        chi_squared = np.sum(residual_real_normalized**2 + residual_imag_normalized**2)
        chi_squared_reduced = chi_squared / n_data if n_data > 0 else np.inf
        
        ss_res = np.sum(np.abs(residual)**2)
        ss_tot = np.sum(np.abs(Z_data - np.mean(Z_data))**2)
        r_squared = 1 - ss_res / ss_tot if ss_tot > 0 else 0
        
        rmse = np.sqrt(np.mean(np.abs(residual)**2))
        
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
    
    def identify_peaks(self, tau: np.ndarray = None, G: np.ndarray = None,
                      min_prominence: float = 0.02) -> List[Dict]:
        """
        识别DRT峰
        
        Args:
            tau: 弛豫时间数组
            G: DRT强度数组
            min_prominence: 最小峰突出度（相对于最大值）
        
        Returns:
            峰列表
        """
        if tau is None:
            tau = self.tau_range
        if G is None:
            G = self.G_drt
        
        if tau is None or G is None:
            return []
        
        peaks = []
        G_max = np.max(G)
        threshold = G_max * min_prominence
        
        # 简单峰检测：找局部最大值
        for i in range(1, len(G) - 1):
            if G[i] > G[i-1] and G[i] > G[i+1] and G[i] > threshold:
                peaks.append({
                    'tau': float(tau[i]),
                    'G': float(G[i]),
                    'frequency': float(1 / (2 * np.pi * tau[i])),
                    'relative_intensity': float(G[i] / G_max)
                })
        
        # 按强度排序
        peaks.sort(key=lambda x: x['G'], reverse=True)
        
        return peaks


def drt_analyze(freq: np.ndarray, zreal: np.ndarray, zimag: np.ndarray) -> Dict:
    """
    便捷函数：执行DRT分析
    
    Args:
        freq: 频率数组 (Hz)
        zreal: 阻抗实部 (Ω)
        zimag: 阻抗虚部 (Ω)
    
    Returns:
        DRT分析结果字典，包含分布和峰信息
    """
    analyzer = DRTAnalyzer()
    result = analyzer.compute_drt_distribution(freq, zreal, zimag)
    result['peaks'] = analyzer.identify_peaks()
    return result
