# -*- coding: utf-8 -*-
"""
Arrhenius分段拟合分析器
从V1.0-qianduan迁移核心功能
"""
import numpy as np
from scipy import stats
from scipy.stats import f as f_dist
from scipy.optimize import curve_fit
from typing import List, Dict, Tuple, Optional

# 物理常数
R_GAS = 8.314  # J/(mol·K)
kB = 8.617333e-5  # eV/K (Boltzmann constant)
EV_TO_KJ_MOL = 96.485  # 1 eV = 96.485 kJ/mol


def arrhenius_model(inv_T: np.ndarray, ea: float, ln_sigma0: float) -> np.ndarray:
    """Arrhenius模型: ln(σ) = ln(σ0) - Ea/(kB*T)"""
    return ln_sigma0 - ea / (kB * 1000) * inv_T


def perform_arrhenius_analysis(
    temperatures: List[float],
    conductivities: List[float],
    min_points: int = 5,
    max_segments: int = 3
) -> Dict:
    """
    执行Arrhenius分段分析
    
    Args:
        temperatures: 温度列表 (K)
        conductivities: 电导率列表 (S/cm)
        min_points: 每段最少数据点
        max_segments: 最大分段数
    
    Returns:
        分析结果字典
    """
    temps_K = np.array(temperatures)
    sigma = np.array(conductivities)
    
    # 过滤有效数据
    valid_mask = (temps_K > 0) & (sigma > 0)
    temps_K = temps_K[valid_mask]
    sigma = sigma[valid_mask]
    
    if len(temps_K) < min_points:
        return {
            'success': False,
            'n_segments': 0,
            'segments': [],
            'error': f'Too few valid points ({len(temps_K)})'
        }
    
    # 准备数据
    inv_T = 1000.0 / temps_K  # 1000/T
    ln_sigma = np.log(sigma)
    
    # 按1/T排序
    sorted_idx = np.argsort(inv_T)
    inv_T = inv_T[sorted_idx]
    ln_sigma = ln_sigma[sorted_idx]
    temps_K = temps_K[sorted_idx]
    
    # 迭代检测分段
    segments, breakpoints = _iterative_segmentation(
        inv_T, ln_sigma, temps_K, min_points, max_segments
    )
    
    if not segments:
        return {
            'success': False,
            'n_segments': 0,
            'segments': [],
            'error': 'Segmentation failed'
        }
    
    # 计算整体统计
    total_rss = sum(seg.get('rss', 0) for seg in segments)
    ss_tot = np.sum((ln_sigma - np.mean(ln_sigma))**2)
    r2_overall = 1 - total_rss / ss_tot if ss_tot > 0 else 0
    
    n_params = 2 * len(segments)
    n = len(inv_T)
    AIC = 2 * n_params + n * np.log(total_rss / n) if total_rss > 0 else float('inf')
    BIC = n_params * np.log(n) + n * np.log(total_rss / n) if total_rss > 0 else float('inf')
    
    return {
        'success': True,
        'n_segments': len(segments),
        'segments': segments,
        'breakpoints': breakpoints,
        'transition_temps_K': [float(temps_K[bp]) for bp in breakpoints if bp < len(temps_K)],
        'AIC': AIC,
        'BIC': BIC,
        'r_squared_overall': r2_overall,
    }


def _iterative_segmentation(
    inv_T: np.ndarray,
    ln_sigma: np.ndarray,
    temps_K: np.ndarray,
    min_points: int,
    max_segments: int
) -> Tuple[List[Dict], List[int]]:
    """迭代式分段检测"""
    n = len(inv_T)
    current_segments = [(0, n)]
    breakpoints = []
    
    for iteration in range(max_segments - 1):
        best_improvement = 0
        best_seg_idx = -1
        best_bp = -1
        
        for seg_idx, (start, end) in enumerate(current_segments):
            seg_len = end - start
            if seg_len < 2 * min_points:
                continue
            
            seg_inv_T = inv_T[start:end]
            seg_ln_sigma = ln_sigma[start:end]
            
            # 检测候选拐点
            candidates = _detect_breakpoint_candidates(seg_inv_T, seg_ln_sigma)
            if not candidates:
                continue
            
            # 单段拟合
            single_result = _fit_single_segment(seg_inv_T, seg_ln_sigma)
            if not single_result['success']:
                continue
            
            for candidate in candidates:
                if candidate < min_points or candidate > seg_len - min_points:
                    continue
                
                # 两段拟合
                two_seg_result = _fit_two_segments(seg_inv_T, seg_ln_sigma, candidate)
                if not two_seg_result['success']:
                    continue
                
                # F检验
                F, p_value, is_significant = _f_test(
                    single_result['rss'], two_seg_result['rss'], seg_len
                )
                
                # AIC改善
                AIC_single = 2 * 2 + seg_len * np.log(single_result['rss'] / seg_len)
                AIC_two = 2 * 4 + seg_len * np.log(two_seg_result['rss'] / seg_len)
                improvement = AIC_single - AIC_two
                
                if is_significant and improvement > best_improvement:
                    best_improvement = improvement
                    best_seg_idx = seg_idx
                    best_bp = start + candidate
        
        if best_seg_idx < 0:
            break
        
        # 添加拐点
        breakpoints.append(best_bp)
        
        # 更新分段
        old_start, old_end = current_segments[best_seg_idx]
        new_segments = []
        for i, (s, e) in enumerate(current_segments):
            if i == best_seg_idx:
                new_segments.append((old_start, best_bp))
                new_segments.append((best_bp, old_end))
            else:
                new_segments.append((s, e))
        current_segments = new_segments
    
    breakpoints.sort()
    
    # 拟合最终分段
    segments = []
    for seg_num, (start, end) in enumerate(current_segments):
        seg_inv_T = inv_T[start:end]
        seg_ln_sigma = ln_sigma[start:end]
        
        result = _fit_single_segment(seg_inv_T, seg_ln_sigma)
        if result['success']:
            result['segment'] = seg_num + 1
            result['n_points'] = end - start
            result['temp_range_K'] = [float(temps_K[end-1]), float(temps_K[start])]
            segments.append(result)
    
    return segments, breakpoints


def _detect_breakpoint_candidates(
    inv_T: np.ndarray, 
    ln_sigma: np.ndarray,
    window_size: int = 5,
    threshold: float = 0.5
) -> List[int]:
    """使用滑动窗口检测候选拐点"""
    n = len(inv_T)
    if n < 2 * window_size:
        return []
    
    slopes = []
    for i in range(n - window_size + 1):
        x_win = inv_T[i:i+window_size]
        y_win = ln_sigma[i:i+window_size]
        slope, _ = np.polyfit(x_win, y_win, 1)
        slopes.append(slope)
    
    slopes = np.array(slopes)
    slope_diff = np.abs(np.diff(slopes))
    
    if len(slope_diff) == 0 or np.std(slope_diff) == 0:
        return []
    
    threshold_value = threshold * np.std(slope_diff)
    candidates_raw = np.where(slope_diff > threshold_value)[0]
    
    # 合并相近的候选点
    candidates = []
    if len(candidates_raw) > 0:
        current_group = [candidates_raw[0]]
        for bp in candidates_raw[1:]:
            if bp - current_group[-1] < window_size:
                current_group.append(bp)
            else:
                candidates.append(int(np.median(current_group)) + window_size // 2)
                current_group = [bp]
        candidates.append(int(np.median(current_group)) + window_size // 2)
    
    return candidates


def _fit_single_segment(inv_T: np.ndarray, ln_sigma: np.ndarray) -> Dict:
    """单段Arrhenius拟合"""
    try:
        # 使用curve_fit带物理约束
        bounds = ([0, -np.inf], [2.0, np.inf])  # Ea必须为正
        
        popt, pcov = curve_fit(
            arrhenius_model, inv_T, ln_sigma,
            bounds=bounds, maxfev=10000
        )
        
        ea, ln_sigma0 = popt
        perr = np.sqrt(np.diag(pcov))
        ea_error = perr[0]
        
        y_pred = arrhenius_model(inv_T, ea, ln_sigma0)
        ss_res = np.sum((ln_sigma - y_pred)**2)
        ss_tot = np.sum((ln_sigma - np.mean(ln_sigma))**2)
        r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0
        
        return {
            'success': True,
            'Ea_eV': float(ea),
            'Ea_kJ_per_mol': float(ea * EV_TO_KJ_MOL),
            'ln_sigma0': float(ln_sigma0),
            'sigma0_S_per_cm': float(np.exp(ln_sigma0)),
            'r_squared': float(r2),
            'rss': float(ss_res),
        }
    except Exception:
        # 回退到简单线性回归
        try:
            slope, intercept, r_value, _, std_err = stats.linregress(inv_T, ln_sigma)
            
            ea = -slope * kB * 1000
            y_pred = slope * inv_T + intercept
            ss_res = np.sum((ln_sigma - y_pred)**2)
            
            return {
                'success': True,
                'Ea_eV': float(ea),
                'Ea_kJ_per_mol': float(ea * EV_TO_KJ_MOL),
                'ln_sigma0': float(intercept),
                'sigma0_S_per_cm': float(np.exp(intercept)),
                'r_squared': float(r_value**2),
                'rss': float(ss_res),
            }
        except:
            return {'success': False}


def _fit_two_segments(inv_T: np.ndarray, ln_sigma: np.ndarray, breakpoint: int) -> Dict:
    """两段拟合"""
    result1 = _fit_single_segment(inv_T[:breakpoint], ln_sigma[:breakpoint])
    result2 = _fit_single_segment(inv_T[breakpoint:], ln_sigma[breakpoint:])
    
    if not result1['success'] or not result2['success']:
        return {'success': False}
    
    total_rss = result1['rss'] + result2['rss']
    
    return {
        'success': True,
        'rss': total_rss,
        'segments': [result1, result2],
    }


def _f_test(rss_simple: float, rss_complex: float, n: int) -> Tuple[float, float, bool]:
    """F检验"""
    if rss_complex >= rss_simple or rss_complex == 0:
        return 0.0, 1.0, False
    
    k_simple = 2
    k_complex = 4
    
    numerator = (rss_simple - rss_complex) / (k_complex - k_simple)
    denominator = rss_complex / (n - k_complex)
    
    if denominator == 0:
        return float('inf'), 0.0, True
    
    F = numerator / denominator
    
    df1 = k_complex - k_simple
    df2 = n - k_complex
    
    if df2 <= 0:
        return F, 1.0, False
    
    p_value = 1 - f_dist.cdf(F, df1, df2)
    is_significant = p_value < 0.05
    
    return F, p_value, is_significant
