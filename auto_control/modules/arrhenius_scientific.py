# -*- coding: utf-8 -*-
"""
科学版分段Arrhenius拟合分析器
移植自 eis_data_analysis/phase1/analysis/arrhenius_piecewise_scientific.py

2026-01-23: 移植到V1.0-qianduan，与eis_data_analysis保持一致

主要特点:
1. 滑动窗口快速筛选候选拐点
2. 穷举搜索精确定位转折点
3. F-test统计检验显著性
4. AIC/BIC模型选择准则
5. 物理约束（Ea > 0）
6. 完整的不确定度估计
7. 支持3段及以上的多分段检测
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
    """
    Arrhenius模型: ln(σ) = ln(σ0) - Ea/(kB*T)
    
    Args:
        inv_T: 1000/T数组 (1000*K^-1)
        ea: 活化能 (eV)
        ln_sigma0: ln(σ0)
    
    Returns:
        ln(σ)数组
    """
    return ln_sigma0 - ea / (kB * 1000) * inv_T


def detect_candidates_sliding_window(
    inv_T: np.ndarray, 
    ln_sigma: np.ndarray, 
    window_size: int = 5,
    threshold: float = 0.5
) -> List[int]:
    """
    使用滑动窗口法快速筛选候选拐点
    
    Args:
        inv_T: 1/T数组
        ln_sigma: ln(σ)数组
        window_size: 窗口大小
        threshold: 斜率变化阈值（相对标准差的倍数）
    
    Returns:
        候选拐点索引列表
    """
    n = len(inv_T)
    if n < 2 * window_size:
        return []
    
    slopes = []
    
    # 计算每个窗口的斜率
    for i in range(n - window_size + 1):
        x_window = inv_T[i:i+window_size]
        y_window = ln_sigma[i:i+window_size]
        slope, _ = np.polyfit(x_window, y_window, 1)
        slopes.append(slope)
    
    slopes = np.array(slopes)
    
    # 计算斜率的一阶差分
    slope_diff = np.abs(np.diff(slopes))
    
    if len(slope_diff) == 0:
        return []
    
    # 识别显著变化点
    threshold_value = threshold * np.std(slope_diff)
    if threshold_value == 0:
        return []
    
    breakpoint_candidates = np.where(slope_diff > threshold_value)[0]
    
    # 合并接近的拐点
    candidates = []
    if len(breakpoint_candidates) > 0:
        current_group = [breakpoint_candidates[0]]
        for bp in breakpoint_candidates[1:]:
            if bp - current_group[-1] < window_size:
                current_group.append(bp)
            else:
                candidates.append(int(np.median(current_group)) + window_size // 2)
                current_group = [bp]
        candidates.append(int(np.median(current_group)) + window_size // 2)
    
    return candidates


def exhaustive_search_around_candidate(
    inv_T: np.ndarray,
    ln_sigma: np.ndarray,
    candidate_idx: int,
    search_radius: int = 5,
    min_points_per_segment: int = 5
) -> Tuple[int, float]:
    """
    在候选点附近进行穷举搜索，精确定位最佳转折点
    """
    n = len(inv_T)
    start = max(min_points_per_segment, candidate_idx - search_radius)
    end = min(n - min_points_per_segment, candidate_idx + search_radius + 1)
    
    best_r2 = -np.inf
    best_idx = candidate_idx
    
    for i in range(start, end):
        try:
            x_high = inv_T[:i]
            y_high = ln_sigma[:i]
            slope_high, intercept_high, r_high, _, _ = stats.linregress(x_high, y_high)
            
            x_low = inv_T[i:]
            y_low = ln_sigma[i:]
            slope_low, intercept_low, r_low, _, _ = stats.linregress(x_low, y_low)
            
            y_pred_high = slope_high * x_high + intercept_high
            y_pred_low = slope_low * x_low + intercept_low
            y_pred = np.concatenate([y_pred_high, y_pred_low])
            
            ss_res = np.sum((ln_sigma - y_pred)**2)
            ss_tot = np.sum((ln_sigma - np.mean(ln_sigma))**2)
            r2 = 1 - ss_res / ss_tot
            
            if r2 > best_r2:
                best_r2 = r2
                best_idx = i
        except:
            continue
    
    return best_idx, best_r2


def fit_single_segment(inv_T: np.ndarray, ln_sigma: np.ndarray) -> Dict:
    """
    单段Arrhenius拟合（带物理约束）
    """
    try:
        bounds = ([0, -np.inf], [2.0, np.inf])
        
        popt, pcov = curve_fit(
            arrhenius_model, 
            inv_T, 
            ln_sigma,
            bounds=bounds,
            maxfev=10000
        )
        
        ea, ln_sigma0 = popt
        perr = np.sqrt(np.diag(pcov))
        ea_error = perr[0]
        
        y_pred = arrhenius_model(inv_T, ea, ln_sigma0)
        ss_res = np.sum((ln_sigma - y_pred)**2)
        ss_tot = np.sum((ln_sigma - np.mean(ln_sigma))**2)
        r2 = 1 - ss_res / ss_tot
        
        ea_kJ = ea * EV_TO_KJ_MOL
        ea_error_kJ = ea_error * EV_TO_KJ_MOL
        
        return {
            'success': True,
            'ea_eV': ea,
            'ea_kJ_per_mol': ea_kJ,
            'ea_error_kJ_per_mol': ea_error_kJ,
            'ln_sigma0': ln_sigma0,
            'sigma0_S_per_cm': np.exp(ln_sigma0),
            'r_squared': r2,
            'rss': ss_res,
            'n_params': 2,
            'slope': -ea,
            'intercept': ln_sigma0
        }
    except Exception as e:
        try:
            slope, intercept, r_value, p_value, std_err = stats.linregress(inv_T, ln_sigma)
            
            ea = -slope * kB * 1000
            ea_kJ = ea * EV_TO_KJ_MOL
            
            y_pred = slope * inv_T + intercept
            ss_res = np.sum((ln_sigma - y_pred)**2)
            
            ea_error = std_err * kB * 1000
            ea_error_kJ = ea_error * EV_TO_KJ_MOL
            
            return {
                'success': True,
                'ea_eV': ea,
                'ea_kJ_per_mol': ea_kJ,
                'ea_error_kJ_per_mol': ea_error_kJ,
                'ln_sigma0': intercept,
                'sigma0_S_per_cm': np.exp(intercept),
                'r_squared': r_value**2,
                'rss': ss_res,
                'n_params': 2,
                'slope': slope,
                'intercept': intercept,
                'warning': 'Used unconstrained fit'
            }
        except:
            return {'success': False, 'error': str(e)}


def fit_two_segments(inv_T: np.ndarray, ln_sigma: np.ndarray, breakpoint: int) -> Dict:
    """两段Arrhenius拟合"""
    segments = []
    total_rss = 0
    
    for seg_idx, (start, end) in enumerate([(0, breakpoint), (breakpoint, len(inv_T))]):
        x_seg = inv_T[start:end]
        y_seg = ln_sigma[start:end]
        
        seg_result = fit_single_segment(x_seg, y_seg)
        
        if not seg_result['success']:
            return {'success': False, 'error': f'Segment {seg_idx+1} fit failed'}
        
        seg_result['segment'] = seg_idx + 1
        seg_result['start_idx'] = start
        seg_result['end_idx'] = end
        seg_result['n_points'] = len(x_seg)
        
        segments.append(seg_result)
        total_rss += seg_result['rss']
    
    y_pred_all = np.concatenate([
        arrhenius_model(inv_T[seg['start_idx']:seg['end_idx']], seg['ea_eV'], seg['ln_sigma0'])
        for seg in segments
    ])
    ss_tot = np.sum((ln_sigma - np.mean(ln_sigma))**2)
    r2_overall = 1 - total_rss / ss_tot
    
    return {
        'success': True,
        'segments': segments,
        'rss': total_rss,
        'r_squared': r2_overall,
        'n_params': 4,
        'breakpoint': breakpoint
    }


def f_test_piecewise(
    rss_simple: float,
    rss_complex: float,
    n_points: int,
    k_simple: int = 2,
    k_complex: int = 4
) -> Tuple[float, float, bool]:
    """F-test检验分段拟合是否显著改善"""
    if rss_complex >= rss_simple or rss_complex == 0:
        return 0.0, 1.0, False
    
    numerator = (rss_simple - rss_complex) / (k_complex - k_simple)
    denominator = rss_complex / (n_points - k_complex)
    
    if denominator == 0:
        return float('inf'), 0.0, True
    
    F = numerator / denominator
    
    df1 = k_complex - k_simple
    df2 = n_points - k_complex
    
    if df2 <= 0:
        return F, 1.0, False
    
    p_value = 1 - f_dist.cdf(F, df1, df2)
    is_significant = p_value < 0.05
    
    return F, p_value, is_significant


def calculate_aic_bic(rss: float, n_points: int, n_params: int) -> Tuple[float, float]:
    """计算AIC和BIC准则"""
    if rss <= 0 or n_points <= n_params:
        return float('inf'), float('inf')
    
    AIC = 2 * n_params + n_points * np.log(rss / n_points)
    BIC = n_params * np.log(n_points) + n_points * np.log(rss / n_points)
    
    return AIC, BIC


class ScientificArrheniusAnalyzer:
    """
    科学版分段Arrhenius分析器 (v2.0)
    
    特点:
    1. 滑动窗口快速筛选
    2. 穷举搜索精确定位
    3. F-test统计检验
    4. AIC/BIC模型选择
    5. 物理约束（Ea > 0）
    6. 完整不确定度估计
    7. 支持3段及以上的多分段检测
    """
    
    def __init__(
        self,
        window_size: int = 5,
        threshold: float = 0.5,
        min_segment_points: int = 5,
        search_radius: int = 5,
        alpha: float = 0.05,
        max_segments: int = 4
    ):
        self.window_size = window_size
        self.threshold = threshold
        self.min_segment_points = min_segment_points
        self.search_radius = search_radius
        self.alpha = alpha
        self.max_segments = max_segments
    
    def analyze(self, temperatures: np.ndarray, conductivities: np.ndarray) -> Dict:
        """
        执行完整的分段Arrhenius分析
        
        Args:
            temperatures: 温度数组 (K)
            conductivities: 电导率数组 (S/cm)
        
        Returns:
            分析结果字典
        """
        # 数据预处理
        valid_mask = (temperatures > 0) & (conductivities > 0)
        temps_K = temperatures[valid_mask]
        sigma = conductivities[valid_mask]
        
        if len(temps_K) < 2 * self.min_segment_points:
            return {
                'success': False,
                'error': f'Too few points ({len(temps_K)}), need at least {2*self.min_segment_points}'
            }
        
        inv_T = 1000.0 / temps_K
        ln_sigma = np.log(sigma)
        
        sorted_idx = np.argsort(inv_T)
        inv_T = inv_T[sorted_idx]
        ln_sigma = ln_sigma[sorted_idx]
        temps_K_sorted = temps_K[sorted_idx]
        
        # 迭代式多分段检测
        breakpoints, segment_results = self._iterative_segment_detection(
            inv_T, ln_sigma, temps_K_sorted
        )
        
        n_segments = len(segment_results)
        
        if n_segments == 1:
            seg = segment_results[0]
            return {
                'success': True,
                'has_transition': False,
                'num_segments': 1,
                'single_segment': seg,
                'segments': segment_results,
                'AIC': seg.get('AIC', float('inf')),
                'BIC': seg.get('BIC', float('inf')),
                'reason': 'No significant breakpoints detected'
            }
        
        total_rss = sum(seg.get('rss', 0) for seg in segment_results)
        ss_tot = np.sum((ln_sigma - np.mean(ln_sigma))**2)
        r2_overall = 1 - total_rss / ss_tot if ss_tot > 0 else 0
        
        n_params = 2 * n_segments
        AIC_multi, BIC_multi = calculate_aic_bic(total_rss, len(inv_T), n_params)
        
        return {
            'success': True,
            'has_transition': True,
            'num_segments': n_segments,
            'segments': segment_results,
            'breakpoints': breakpoints,
            'transition_temps_K': [float(temps_K_sorted[bp]) for bp in breakpoints if bp < len(temps_K_sorted)],
            'AIC': AIC_multi,
            'BIC': BIC_multi,
            'r_squared_overall': r2_overall,
            'total_rss': total_rss
        }
    
    def _iterative_segment_detection(
        self,
        inv_T: np.ndarray,
        ln_sigma: np.ndarray,
        temps_K_sorted: np.ndarray
    ) -> Tuple[List[int], List[Dict]]:
        """迭代式多分段检测"""
        n = len(inv_T)
        current_segments = [(0, n)]
        breakpoints = []
        
        for iteration in range(self.max_segments - 1):
            best_improvement = 0
            best_segment_idx = -1
            best_bp = -1
            best_f_stat = 0
            best_p_value = 1.0
            
            for seg_idx, (start, end) in enumerate(current_segments):
                seg_len = end - start
                
                if seg_len < 2 * self.min_segment_points:
                    continue
                
                seg_inv_T = inv_T[start:end]
                seg_ln_sigma = ln_sigma[start:end]
                
                candidates = detect_candidates_sliding_window(
                    seg_inv_T, seg_ln_sigma, 
                    self.window_size, self.threshold
                )
                
                if not candidates:
                    continue
                
                single_result = fit_single_segment(seg_inv_T, seg_ln_sigma)
                if not single_result['success']:
                    continue
                
                for candidate in candidates:
                    global_candidate = start + candidate
                    
                    refined_bp, r2 = exhaustive_search_around_candidate(
                        seg_inv_T, seg_ln_sigma, candidate,
                        self.search_radius, self.min_segment_points
                    )
                    
                    if refined_bp < self.min_segment_points or refined_bp > seg_len - self.min_segment_points:
                        continue
                    
                    two_seg_result = fit_two_segments(seg_inv_T, seg_ln_sigma, refined_bp)
                    if not two_seg_result['success']:
                        continue
                    
                    F_stat, p_value, is_significant = f_test_piecewise(
                        single_result['rss'],
                        two_seg_result['rss'],
                        seg_len,
                        single_result['n_params'],
                        two_seg_result['n_params']
                    )
                    
                    AIC_single, _ = calculate_aic_bic(single_result['rss'], seg_len, 2)
                    AIC_two, _ = calculate_aic_bic(two_seg_result['rss'], seg_len, 4)
                    
                    improvement = AIC_single - AIC_two
                    
                    if is_significant and improvement > best_improvement:
                        best_improvement = improvement
                        best_segment_idx = seg_idx
                        best_bp = start + refined_bp
                        best_f_stat = F_stat
                        best_p_value = p_value
            
            if best_segment_idx < 0 or best_improvement <= 0:
                break
            
            breakpoints.append(best_bp)
            
            old_start, old_end = current_segments[best_segment_idx]
            new_segments = []
            for i, (s, e) in enumerate(current_segments):
                if i == best_segment_idx:
                    new_segments.append((old_start, best_bp))
                    new_segments.append((best_bp, old_end))
                else:
                    new_segments.append((s, e))
            current_segments = new_segments
        
        breakpoints.sort()
        segment_results = []
        
        for seg_num, (start, end) in enumerate(current_segments):
            seg_inv_T = inv_T[start:end]
            seg_ln_sigma = ln_sigma[start:end]
            
            seg_result = fit_single_segment(seg_inv_T, seg_ln_sigma)
            
            if seg_result['success']:
                seg_result['segment'] = seg_num + 1
                seg_result['start_idx'] = start
                seg_result['end_idx'] = end
                seg_result['n_points'] = end - start
                seg_result['T_range_K'] = (
                    float(temps_K_sorted[start]),
                    float(temps_K_sorted[end - 1])
                )
                seg_result['temp_range_K'] = [
                    float(temps_K_sorted[end - 1]),
                    float(temps_K_sorted[start])
                ]
                
                # 兼容性字段
                seg_result['Ea'] = seg_result.get('ea_eV', 0)
                seg_result['Ea_eV'] = seg_result.get('ea_eV', 0)
                seg_result['Ea_kJ_mol'] = seg_result.get('ea_kJ_per_mol', 0)
                seg_result['Ea_kJ_per_mol'] = seg_result.get('ea_kJ_per_mol', 0)
                seg_result['sigma0'] = seg_result.get('sigma0_S_per_cm', 0)
                seg_result['sigma0_S_per_cm'] = seg_result.get('sigma0_S_per_cm', 0)
                
                r2 = seg_result.get('r_squared', 0)
                if r2 >= 0.99:
                    seg_result['quality'] = 'excellent'
                elif r2 >= 0.95:
                    seg_result['quality'] = 'good'
                elif r2 >= 0.90:
                    seg_result['quality'] = 'fair'
                else:
                    seg_result['quality'] = 'poor'
                
                segment_results.append(seg_result)
        
        return breakpoints, segment_results


def perform_arrhenius_analysis_scientific(
    temperatures: List[float],
    conductivities: List[float],
    **kwargs
) -> Dict:
    """
    执行科学版Arrhenius分析的便捷函数
    
    Args:
        temperatures: 温度列表 (K)
        conductivities: 电导率列表 (S/cm)
        **kwargs: 传递给ScientificArrheniusAnalyzer的参数
    
    Returns:
        分析结果字典，格式与旧版兼容
    """
    analyzer = ScientificArrheniusAnalyzer(**kwargs)
    result = analyzer.analyze(
        np.array(temperatures),
        np.array(conductivities)
    )
    
    if not result.get('success', False):
        return {
            'success': False,
            'n_segments': 0,
            'segments': [],
            'error': result.get('error', 'Unknown error')
        }
    
    # 转换为兼容旧格式
    segments = result.get('segments', [])
    
    return {
        'success': True,
        'n_segments': len(segments),
        'segments': segments,
        'has_transition': result.get('has_transition', False),
        'transition_temps_K': result.get('transition_temps_K', []),
        'AIC': result.get('AIC', float('inf')),
        'BIC': result.get('BIC', float('inf')),
        'r_squared_overall': result.get('r_squared_overall', 0)
    }


if __name__ == '__main__':
    print("Scientific Arrhenius Piecewise Fitting Module")
    print("Ported to V1.0-qianduan on 2026-01-23")
    print()
    print("Features:")
    print("  - Sliding window for candidate detection")
    print("  - Exhaustive search for precise localization")
    print("  - F-test statistical validation")
    print("  - AIC/BIC model selection")
    print("  - Physical constraints (Ea > 0)")
    print("  - Multi-segment detection (up to 4 segments)")
