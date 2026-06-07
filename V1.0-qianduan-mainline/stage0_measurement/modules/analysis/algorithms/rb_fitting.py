# -*- coding: utf-8 -*-
"""
Rb 拟合与电导率计算算法（逆向搜索版）

这是一个纯粹的算法模块，遵循以下原则：
1. 所有函数都是纯函数，只接受参数输入，返回计算结果
2. 无全局副作用（无 sys.path.insert、无 warnings.filterwarnings）
3. 绝对禁止画图操作（由 reporting 模块负责可视化）
4. 统一错误抛出：返回规范的字典格式
5. 硬编码阈值作为函数默认参数，便于后续从统一配置传入

核心策略：低频逆向倒推法 (Reverse Search)
- 从最可靠的低频端（0.1 Hz）向高频端（1 MHz）倒推
- 完美绕开高频寄生谐振（> 100 kHz）和假过零点
- 动态路由：过零点 -> 寻谷 -> Bode 平台 -> 等效电路兜底

主要功能：
- Rb（体相电阻）拟合：逆向动态路由（4 个分支）
- 电导率计算：σ = L / (Rb × A)
- 数据质量评估：相位分析、形态识别

版本：4.0.0 (低频逆向倒推法)
"""

import numpy as np
from scipy.signal import savgol_filter, find_peaks
from scipy.optimize import curve_fit
from scipy.interpolate import interp1d


# ============================================================
# 公共接口：拟合参数
# ============================================================

def get_default_fit_params():
    """
    获取默认拟合参数（逆向搜索版）
    
    Returns:
        dict: 拟合参数字典
            - smooth_window: 平滑窗口大小（奇数）
            - smooth_poly: 平滑多项式阶数
            - phase_threshold_deep_cold: 深冷高阻判定阈值（相位角）
            - phase_threshold_stable: 低频平台稳定判定阈值
            - valley_prominence: 谷底显著性阈值（相对深度）
            - zero_crossing_tol: 过零点判定容差
            - low_freq_plateau_points: 低频平台取点数
            - high_freq_cutoff_khz: 高频截止频率（kHz，忽略更高频）
    """
    return {
        # 平滑参数
        'smooth_window': 9,  # 奇数
        'smooth_poly': 3,
        
        # 相位判定阈值
        'phase_threshold_deep_cold': -50.0,  # 度，深冷高阻判定
        'phase_threshold_stable': 10.0,      # 度，低频平台稳定判定
        
        # 谷底识别
        'valley_prominence': 0.15,  # 谷深度至少为峰值的 15%
        
        # 过零点判定
        'zero_crossing_tol': 0.5,  # Ω，过零点附近容差
        
        # 平台识别
        'low_freq_plateau_points': 5,  # 低频平台取多少点平均
        
        # 高频截止
        'high_freq_cutoff_khz': 500.0,  # kHz，忽略 > 500 kHz 的数据
    }


# ============================================================
# 公共接口：Rb 拟合 + 电导率计算
# ============================================================

def fit_rb_and_conductivity(
    frequencies,
    z_real,
    z_imag,
    thickness_cm,
    area_cm2,
    temperature_K,
    fit_params=None
):
    """
    执行 Rb 拟合并计算电导率（逆向搜索版主入口）
    
    Args:
        frequencies: 频率数组 (Hz)
        z_real: 阻抗实部 (Ω)
        z_imag: 阻抗虚部 (Ω)
        thickness_cm: 样品厚度 (cm)
        area_cm2: 样品面积 (cm²)
        temperature_K: 温度 (K)
        fit_params: 拟合参数（None 使用默认值）
    
    Returns:
        dict: 包含以下字段
            - success: bool，是否成功
            - rb_ohm: float，Rb 值 (Ω)
            - conductivity_s_per_cm: float，电导率 (S/cm)
            - method: str，使用的方法（'reverse_zero_crossing', 'reverse_valley', 'low_freq_plateau', 'equivalent_circuit'）
            - fit_quality: float (0-1)，拟合质量评分
            - error: str or None，失败原因
            - details: dict，详细信息
    """
    # 输入验证
    try:
        freq = np.array(frequencies, dtype=float)
        zreal = np.array(z_real, dtype=float)
        zimag = np.array(z_imag, dtype=float)
        
        if len(freq) != len(zreal) or len(freq) != len(zimag):
            return {
                'success': False,
                'rb_ohm': None,
                'conductivity_s_per_cm': None,
                'method': None,
                'fit_quality': 0.0,
                'error': 'Array length mismatch',
                'details': {}
            }
        
        if len(freq) < 5:
            return {
                'success': False,
                'rb_ohm': None,
                'conductivity_s_per_cm': None,
                'method': None,
                'fit_quality': 0.0,
                'error': f'Insufficient data points: {len(freq)} < 5',
                'details': {}
            }
        
        if thickness_cm <= 0 or area_cm2 <= 0:
            return {
                'success': False,
                'rb_ohm': None,
                'conductivity_s_per_cm': None,
                'method': None,
                'fit_quality': 0.0,
                'error': f'Invalid geometry: thickness={thickness_cm}, area={area_cm2}',
                'details': {}
            }
    
    except Exception as e:
        return {
            'success': False,
            'rb_ohm': None,
            'conductivity_s_per_cm': None,
            'method': None,
            'fit_quality': 0.0,
            'error': f'Input validation error: {str(e)}',
            'details': {}
        }
    
    # 获取拟合参数
    if fit_params is None:
        fit_params = get_default_fit_params()
    
    # ===== 步骤 1: 全局平滑与基础判定 =====
    try:
        prep_result = _preprocess_and_analyze(freq, zreal, zimag, fit_params)
        
        if not prep_result['success']:
            return {
                'success': False,
                'rb_ohm': None,
                'conductivity_s_per_cm': None,
                'method': None,
                'fit_quality': 0.0,
                'error': prep_result['error'],
                'details': prep_result
            }
    
    except Exception as e:
        return {
            'success': False,
            'rb_ohm': None,
            'conductivity_s_per_cm': None,
            'method': None,
            'fit_quality': 0.0,
            'error': f'Preprocessing failed: {str(e)}',
            'details': {}
        }
    
    # ===== 步骤 2: 动态路由提取 Rb（从高频向低频逆向搜索） =====
    try:
        rb_result = _reverse_search_rb(
            freq=prep_result['freq_filtered'],
            zreal=prep_result['zreal_filtered'],
            zimag_smooth=prep_result['zimag_smooth'],
            zimag_raw=prep_result['zimag_raw'],
            phase=prep_result['phase'],
            z_magnitude=prep_result['z_magnitude'],
            fit_params=fit_params
        )
        
        if not rb_result['success']:
            return {
                'success': False,
                'rb_ohm': None,
                'conductivity_s_per_cm': None,
                'method': rb_result.get('method'),
                'fit_quality': 0.0,
                'error': rb_result['error'],
                'details': {**prep_result, **rb_result}
            }
        
        rb_ohm = rb_result['rb_ohm']
        method = rb_result['method']
        fit_quality = rb_result['fit_quality']
    
    except Exception as e:
        return {
            'success': False,
            'rb_ohm': None,
            'conductivity_s_per_cm': None,
            'method': None,
            'fit_quality': 0.0,
            'error': f'Rb fitting failed: {str(e)}',
            'details': prep_result
        }
    
    # ===== 步骤 3: 计算电导率 =====
    try:
        conductivity = thickness_cm / (rb_ohm * area_cm2)
        
        return {
            'success': True,
            'rb_ohm': float(rb_ohm),
            'conductivity_s_per_cm': float(conductivity),
            'method': method,
            'fit_quality': float(fit_quality),
            'error': None,
            'details': {
                'preprocessing': prep_result,
                'rb_fitting': rb_result,
                'thickness_cm': thickness_cm,
                'area_cm2': area_cm2,
                'temperature_K': temperature_K
            }
        }
    
    except Exception as e:
        return {
            'success': False,
            'rb_ohm': rb_ohm,
            'conductivity_s_per_cm': None,
            'method': method,
            'fit_quality': fit_quality,
            'error': f'Conductivity calculation failed: {str(e)}',
            'details': {**prep_result, **rb_result}
        }


# ============================================================
# 内部函数：步骤 1 - 全局平滑与基础判定
# ============================================================

def _preprocess_and_analyze(freq, zreal, zimag, fit_params):
    """
    预处理与基础分析
    
    包括：
    1. 高频截止（忽略 > 500 kHz 的寄生谐振）
    2. 低频截止（忽略 < 1 Hz 的点，避免深冷判定受极低频扩散阻抗影响）
    3. 按频率升序排序
    4. 平滑 z_imag（Savitzky-Golay）
    5. 计算模值和相位角
    
    Returns:
        dict: 预处理结果
            - success: bool
            - freq_filtered: 过滤后的频率
            - zreal_filtered: 过滤后的实部
            - zimag_smooth: 平滑后的虚部
            - zimag_raw: 未平滑的原始虚部（用于精确过零点检测）
            - phase: 相位角（度）
            - z_magnitude: 阻抗模值
            - error: 错误信息
    """
    try:
        # 高频截止（忽略 > cutoff_khz 的数据）
        cutoff_hz = fit_params['high_freq_cutoff_khz'] * 1000
        mask_high = freq <= cutoff_hz
        
        # 低频截止（忽略 < 1 Hz 的数据，避免极低频扩散阻抗影响深冷判定）
        mask_low = freq >= 1.0
        
        # 综合掩码：保留 [1 Hz, cutoff_hz] 的数据
        mask = mask_high & mask_low
        
        freq_filt = freq[mask]
        zreal_filt = zreal[mask]
        zimag_filt = zimag[mask]
        
        if len(freq_filt) < 5:
            return {
                'success': False,
                'error': f'Too few points after freq cutoff: {len(freq_filt)} < 5'
            }
        
        # 按频率升序排序
        sort_idx = np.argsort(freq_filt)
        freq_filt = freq_filt[sort_idx]
        zreal_filt = zreal_filt[sort_idx]
        zimag_filt = zimag_filt[sort_idx]
        
        # 平滑 z_imag（使用 Savitzky-Golay 滤波器）
        window = fit_params['smooth_window']
        poly = fit_params['smooth_poly']
        
        if len(zimag_filt) >= window:
            zimag_smooth = savgol_filter(zimag_filt, window_length=window, polyorder=poly)
        else:
            # 点数不足，使用简单移动平均
            zimag_smooth = zimag_filt.copy()
        
        # 计算模值和相位角（修复符号：使用正确的物理相位）
        z_magnitude = np.sqrt(zreal_filt**2 + zimag_filt**2)
        phase = np.degrees(np.arctan2(zimag_filt, zreal_filt))
        
        return {
            'success': True,
            'freq_filtered': freq_filt,
            'zreal_filtered': zreal_filt,
            'zimag_smooth': zimag_smooth,
            'zimag_raw': zimag_filt,  # 保留原始未平滑数据用于精确插值
            'phase': phase,
            'z_magnitude': z_magnitude,
            'n_points': len(freq_filt),
            'freq_range_hz': (freq_filt[0], freq_filt[-1]),
            'error': None
        }
    
    except Exception as e:
        return {
            'success': False,
            'error': f'Preprocessing exception: {str(e)}'
        }


# ============================================================
# 内部函数：步骤 2 - 动态路由 Rb 提取（逆向搜索）
# ============================================================

def _reverse_search_rb(freq, zreal, zimag_smooth, zimag_raw, phase, z_magnitude, fit_params):
    """
    从高频向低频逆向搜索 Rb（动态路由）
    
    路由优先级：
    1. 分支 A：逆向过零点法（从高频向低频遍历，使用原始数据精确插值）
    2. 分支 C：逆向寻谷法（使用 find_peaks 找局部极大值）
    3. 分支 B：低频 Bode 平台法（深冷高阻区）
    4. 分支 D：等效电路兜底（残缺半圆）
    
    Returns:
        dict: Rb 拟合结果
            - success: bool
            - rb_ohm: float or None
            - method: str
            - fit_quality: float (0-1)
            - error: str or None
    """
    # ===== 分支判定：深冷高阻 vs 常规 =====
    # 深冷高阻特征：
    # 1. 高频端相位角极负（< -50°）
    # 2. 低频端相位角接近 0°
    # 3. 阻抗幅度较大（> 1 kΩ，表明高阻抗）
    phase_high_freq = phase[-min(5, len(phase)):].mean()
    phase_low_freq = phase[:min(5, len(phase))].mean()
    z_magnitude_mean = np.mean(z_magnitude)
    
    is_deep_cold = (
        phase_high_freq < fit_params['phase_threshold_deep_cold'] and
        abs(phase_low_freq) < fit_params['phase_threshold_stable'] and
        z_magnitude_mean > 1000.0 and  # 阻抗 > 1 kΩ
        len(phase) >= 10
    )
    
    if is_deep_cold:
        # ===== 分支 B：低频 Bode 平台法 =====
        return _method_low_freq_plateau(freq, zreal, phase, fit_params)
    
    # ===== 分支 A：逆向过零点法（优先，使用原始数据精确插值） =====
    zero_crossing_result = _method_reverse_zero_crossing(freq, zreal, zimag_raw, fit_params)
    if zero_crossing_result['success']:
        return zero_crossing_result
    
    # ===== 分支 C：逆向寻谷法（使用 find_peaks 找局部极大值） =====
    valley_result = _method_reverse_valley(freq, zreal, zimag_smooth, fit_params)
    if valley_result['success']:
        return valley_result
    
    # ===== 分支 B：低频平台法（深冷高阻区） =====
    plateau_result = _method_low_freq_plateau(freq, zreal, phase, fit_params)
    if plateau_result['success']:
        return plateau_result
    
    # ===== 分支 D：等效电路兜底 =====
    return _method_equivalent_circuit(freq, zreal, zimag_smooth, fit_params)


# ============================================================
# 方法 A：逆向过零点法（从高频向低频精确插值）
# ============================================================

def _method_reverse_zero_crossing(freq, zreal, zimag_raw, fit_params):
    """
    从低频向高频搜索过零点（使用原始数据，精确插值）
    
    逻辑：
    - 从低频向高频遍历（freq 是升序，从前往后）
    - 寻找 zimag 从负（低频容抗）变为正（高频感抗）的过零点
    - 选择频率最低的过零点（Nyquist 图右侧交点，即 Rb）
    - 使用线性插值精确计算 X 轴交点对应的 Z' 作为 Rb
    
    Returns:
        dict: 拟合结果
    """
    try:
        # 从低频向高频遍历（从数组开头到末尾）
        for i in range(len(zimag_raw) - 1):
            zimag_low = zimag_raw[i]       # 当前点（较低频）
            zimag_high = zimag_raw[i + 1]  # 下一点（较高频）
            
            # 检测过零点：从低频容抗（负）到高频感抗（正）
            if zimag_low < 0 and zimag_high > 0:
                # 找到过零点，使用线性插值求准确的 X 轴交点
                # t ∈ [0, 1]，表示零点在 i 和 i+1 之间的位置
                t = -zimag_low / (zimag_high - zimag_low)
                rb_ohm = zreal[i] + t * (zreal[i + 1] - zreal[i])
                
                # 质量评分（第一个过零点即最低频，为 Rb）
                fit_quality = 0.95
                
                return {
                    'success': True,
                    'rb_ohm': float(rb_ohm),
                    'method': 'reverse_zero_crossing',
                    'fit_quality': fit_quality,
                    'error': None,
                    'zero_crossing_index': i,
                    'zero_crossing_freq': float(freq[i]),
                    'interpolation_parameter': float(t)
                }
        
        # 未找到过零点
        return {
            'success': False,
            'rb_ohm': None,
            'method': 'reverse_zero_crossing',
            'fit_quality': 0.0,
            'error': 'No zero crossing found in zimag'
        }
    
    except Exception as e:
        return {
            'success': False,
            'rb_ohm': None,
            'method': 'reverse_zero_crossing',
            'fit_quality': 0.0,
            'error': f'Zero crossing exception: {str(e)}'
        }


# ============================================================
# 方法 C：逆向寻谷法（使用 find_peaks 找局部极大值）
# ============================================================

def _method_reverse_valley(freq, zreal, zimag_smooth, fit_params):
    """
    直接找全局最小 |Z''|（离 X 轴最近的点）
    
    逻辑：
    - 找到 |Z''| 最小的点（最接近实轴）
    - 如果存在多个相近的点（相差 < 1% 容差），选择频率最低的
    - 不再依赖 find_peaks 和 prominence 检查
    
    Returns:
        dict: 拟合结果
    """
    try:
        # 计算 |Z''|，找全局最小值
        abs_zimag = np.abs(zimag_smooth)
        min_value = np.min(abs_zimag)
        
        # 找到所有接近最小值的点（相差 < 1% 容差）
        tolerance = min_value * 0.01  # 1% 容差
        candidates = np.where(abs_zimag <= min_value + tolerance)[0]
        
        # 如果有多个候选，选频率最低的（索引最小）
        if len(candidates) > 1:
            valley_idx = candidates[0]  # 索引最小 = 频率最低
            multiple_candidates = True
        else:
            valley_idx = candidates[0]
            multiple_candidates = False
        
        # 取谷底对应的 zreal 作为 Rb
        rb_ohm = zreal[valley_idx]
        zimag_valley = zimag_smooth[valley_idx]
        
        # 质量评分（基于 |Z''| 的大小，越接近 0 质量越高）
        zimag_max = np.max(abs_zimag)
        normalized_valley = abs(zimag_valley) / zimag_max if zimag_max > 0 else 0
        fit_quality = 0.90 - normalized_valley * 0.1  # 0.80 到 0.90 之间
        
        return {
            'success': True,
            'rb_ohm': float(rb_ohm),
            'method': 'reverse_valley',
            'fit_quality': float(fit_quality),
            'error': None,
            'valley_index': int(valley_idx),
            'valley_freq': float(freq[valley_idx]),
            'valley_zimag': float(zimag_valley),
            'abs_zimag_valley': float(abs(zimag_valley)),
            'n_candidates': len(candidates),
            'multiple_candidates': multiple_candidates
        }
    
    except Exception as e:
        return {
            'success': False,
            'rb_ohm': None,
            'method': 'reverse_valley',
            'fit_quality': 0.0,
            'error': f'Valley search exception: {str(e)}'
        }


# ============================================================
# 方法 B：低频 Bode 平台法（深冷高阻区）
# ============================================================

def _method_low_freq_plateau(freq, zreal, phase, fit_params):
    """
    低频 Bode 平台法
    
    适用于：
    1. 深冷高阻抗区（相位稳定在 0° 附近）
    2. 容抗主导的 RC 电路（低频阻抗趋于常数）
    
    逻辑：
    - 检查低频端（最低 N 个点）是否形成稳定平台
    - 如果相位角接近 0° 且稳定，取该区域 zreal 的最小值或平均值
    
    Returns:
        dict: 拟合结果
    """
    try:
        n_points = fit_params['low_freq_plateau_points']
        n_points = min(n_points, len(freq) // 2)  # 最多取一半
        
        # 最低频 n_points 个点
        phase_low = phase[:n_points]
        zreal_low = zreal[:n_points]
        
        # 检查相位稳定性
        phase_mean = np.mean(np.abs(phase_low))
        phase_std = np.std(phase_low)
        
        # 放宽判定条件：相位平均值 < 20° 即可（包含深冷高阻和容抗RC）
        if phase_mean > 20.0:
            return {
                'success': False,
                'rb_ohm': None,
                'method': 'low_freq_plateau',
                'fit_quality': 0.0,
                'error': f'Low-freq phase not near zero: mean={phase_mean:.1f}° > 20.0°'
            }
        
        # 增强抗噪性：使用中位数而非最小值
        rb_ohm = float(np.median(zreal_low))
        
        # 质量评分（基于相位稳定性）
        stability = 1.0 - min(phase_std / 10.0, 1.0)  # 标准差越小越好
        fit_quality = 0.85 * stability
        
        return {
            'success': True,
            'rb_ohm': float(rb_ohm),
            'method': 'low_freq_plateau',
            'fit_quality': float(fit_quality),
            'error': None,
            'plateau_points': int(n_points),
            'plateau_phase_mean': float(phase_mean),
            'plateau_phase_std': float(phase_std),
            'plateau_zreal_min': float(rb_ohm),
            'plateau_zreal_mean': float(np.mean(zreal_low))
        }
    
    except Exception as e:
        return {
            'success': False,
            'rb_ohm': None,
            'method': 'low_freq_plateau',
            'fit_quality': 0.0,
            'error': f'Plateau method exception: {str(e)}'
        }


# ============================================================
# 方法 D：等效电路兜底（R-CPE 拟合）
# ============================================================

def _method_equivalent_circuit(freq, zreal, zimag_smooth, fit_params):
    """
    等效电路拟合兜底方法（R-CPE 模型）
    
    模型：Z = Rs + Rp / (1 + (j*omega*tau)^alpha)
    Rb = Rs + Rp
    
    适用于：
    - 半圆未完整扫描
    - 无明显过零点或谷底
    
    Returns:
        dict: 拟合结果
    """
    try:
        omega = 2 * np.pi * freq
        Z_complex = zreal + 1j * zimag_smooth
        
        # R-CPE 模型函数
        def r_cpe_model(omega, Rs, Rp, tau, alpha):
            """R-CPE 等效电路模型"""
            Z = Rs + Rp / (1 + (1j * omega * tau)**alpha)
            return np.concatenate([Z.real, Z.imag])
        
        # 初始参数猜测
        Rs_guess = np.min(zreal)
        Rp_guess = np.max(zreal) - Rs_guess
        tau_guess = 1.0 / (2 * np.pi * freq[len(freq)//2])  # 中频对应时间常数
        alpha_guess = 0.9
        
        p0 = [Rs_guess, Rp_guess, tau_guess, alpha_guess]
        
        # 数据准备（加入模值加权）
        Z_data = np.concatenate([Z_complex.real, Z_complex.imag])
        
        # 计算权重（使用阻抗模值加权，避免高阻抗点主导拟合）
        sigma_weights = np.concatenate([np.abs(Z_complex), np.abs(Z_complex)])
        sigma_weights = np.maximum(sigma_weights, 1e-6)  # 防止分母为零
        
        # 拟合（使用加权最小二乘）
        try:
            popt, pcov = curve_fit(
                r_cpe_model,
                omega,
                Z_data,
                p0=p0,
                sigma=sigma_weights,
                absolute_sigma=False,
                bounds=([0, 0, 1e-6, 0.5], [np.inf, np.inf, 1e3, 1.0]),
                maxfev=5000
            )
            
            Rs, Rp, tau, alpha = popt
            rb_ohm = Rs + Rp
            
            # 计算拟合质量（R²）
            Z_fit = r_cpe_model(omega, *popt)
            residuals = Z_data - Z_fit
            ss_res = np.sum(residuals**2)
            ss_tot = np.sum((Z_data - np.mean(Z_data))**2)
            r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
            
            fit_quality = max(0.0, min(r_squared, 1.0)) * 0.7  # 兜底方法，最高 0.7
            
            return {
                'success': True,
                'rb_ohm': float(rb_ohm),
                'method': 'equivalent_circuit',
                'fit_quality': float(fit_quality),
                'error': None,
                'Rs': float(Rs),
                'Rp': float(Rp),
                'tau': float(tau),
                'alpha': float(alpha),
                'r_squared': float(r_squared)
            }
        
        except Exception as fit_error:
            return {
                'success': False,
                'rb_ohm': None,
                'method': 'equivalent_circuit',
                'fit_quality': 0.0,
                'error': f'Curve fit failed: {str(fit_error)}'
            }
    
    except Exception as e:
        return {
            'success': False,
            'rb_ohm': None,
            'method': 'equivalent_circuit',
            'fit_quality': 0.0,
            'error': f'Equivalent circuit exception: {str(e)}'
        }


# ============================================================
# 向后兼容接口（可选）
# ============================================================

def calculate_rb(frequencies, z_real, z_imag, fit_params=None):
    """
    便捷函数：仅计算 Rb（不计算电导率）
    
    Args:
        frequencies: 频率数组 (Hz)
        z_real: 阻抗实部 (Ω)
        z_imag: 阻抗虚部 (Ω)
        fit_params: 拟合参数（None 使用默认值）
    
    Returns:
        dict: Rb 拟合结果（包含 rb_ohm, method, fit_quality 等）
    """
    # 使用虚拟几何参数调用主函数
    result = fit_rb_and_conductivity(
        frequencies=frequencies,
        z_real=z_real,
        z_imag=z_imag,
        thickness_cm=1.0,  # 虚拟值
        area_cm2=1.0,      # 虚拟值
        temperature_K=298.15,  # 虚拟值
        fit_params=fit_params
    )
    
    # 移除电导率相关字段
    result.pop('conductivity_s_per_cm', None)
    
    return result
