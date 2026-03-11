# -*- coding: utf-8 -*-
"""
Rb拟合核心模块 - 整合Phase 1的优化方法

整合自 eis_data_analysis/phase1/core/rb_fitting_core.py
包括：
1. Savitzky-Golay 预处理
2. X轴交点检测（最高优先级）
3. 整体/渐进线性拟合
4. IRLS圆弧拟合（放宽约束）
5. 宽松/最宽松线性拟合
6. 高频外推方法
7. 高频平均兜底方法

版本: 2.0.0 (Phase 1整合版)
日期: 2026-01-25
"""

import os
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
from sklearn.linear_model import LinearRegression
from scipy.optimize import minimize
import warnings

# 尝试导入 scipy.signal 用于滤波
try:
    from scipy.signal import savgol_filter
    HAS_SAVGOL = True
except ImportError:
    HAS_SAVGOL = False

warnings.filterwarnings('ignore')

# 全局设置matplotlib支持中文和负号
matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
matplotlib.rcParams['axes.unicode_minus'] = False


# ============================================================
# Phase 1 新增：数据预处理函数
# ============================================================

def filter_data_savgol(zreal, zimag, window=7, poly=3, thresh=3.0):
    """
    对阻抗数据执行 Savitzky-Golay 滤波，并剔除残差超阈值的异常点
    
    来源：eis_data_analysis/phase1/core/rb_fitting_core.py
    
    Args:
        zreal: 阻抗实部数组
        zimag: 阻抗虚部数组（绝对值）
        window: Savitzky-Golay 窗口大小（默认7）
        poly: 多项式阶数（默认3）
        thresh: 异常点阈值（默认3.0，即3σ）
        
    Returns:
        filtered_zreal: 过滤后的实部
        filtered_zimag: 过滤后的虚部
        report: 预处理报告
    """
    report = {
        'n_original': len(zreal),
        'n_removed': 0,
        'method': 'passthrough'
    }
    
    if len(zreal) < window:
        return zreal.copy(), zimag.copy(), report
    
    if not HAS_SAVGOL:
        report['method'] = 'no_scipy'
        return zreal.copy(), zimag.copy(), report
    
    try:
        # Savitzky-Golay 滤波
        smooth_zreal = savgol_filter(zreal, window_length=window, polyorder=poly, mode='interp')
        smooth_zimag = savgol_filter(zimag, window_length=window, polyorder=poly, mode='interp')
        
        # 计算残差
        resid_real = zreal - smooth_zreal
        resid_imag = zimag - smooth_zimag
        
        # 计算标准差
        std_real = np.nanstd(resid_real)
        std_imag = np.nanstd(resid_imag)
        
        if std_real == 0:
            std_real = 1e-10
        if std_imag == 0:
            std_imag = 1e-10
        
        # 异常点检测
        mask = (np.abs(resid_real) < thresh * std_real) & \
               (np.abs(resid_imag) < thresh * std_imag)
        
        n_removed = np.sum(~mask)
        
        report['n_removed'] = n_removed
        report['method'] = 'savgol_filter'
        
        return zreal[mask], zimag[mask], report
        
    except Exception as e:
        report['method'] = f'error: {str(e)}'
        return zreal.copy(), zimag.copy(), report


# ============================================================
# 基础函数
# ============================================================

def calculate_correlation(x, y):
    """计算两个数组的皮尔逊相关系数"""
    x_mean = np.mean(x)
    y_mean = np.mean(y)
    numerator = np.sum((x - x_mean) * (y - y_mean))
    denominator = np.sqrt(np.sum((x - x_mean)**2) * np.sum((y - y_mean)**2))
    return numerator / denominator if denominator != 0 else 0


def check_linearity(zreal, zimag, threshold):
    """判断zreal与zimag的相关性是否超过阈值"""
    if len(zreal) < 3:
        return False, 0.0
    r = calculate_correlation(zreal, zimag)
    return abs(r) >= threshold, abs(r)


def fit_line_with_progressive_removal(zreal, zimag, threshold, max_remove_ratio):
    """逐步移除低频端数据，寻找最佳线性区间"""
    best_r = 0
    best_idx = 0
    best_rb = None
    best_reg = None
    max_remove = int(len(zreal) * max_remove_ratio)
    
    for i in range(0, max_remove + 1):
        subset_zreal = zreal[:len(zreal)-i] if i > 0 else zreal
        subset_zimag = zimag[:len(zimag)-i] if i > 0 else zimag
        
        is_linear, r = check_linearity(subset_zreal, subset_zimag, threshold)
        r = abs(r)
        
        if r > best_r:
            best_r = r
            best_idx = i
            if is_linear:
                X = subset_zreal.reshape(-1, 1)
                reg = LinearRegression().fit(X, subset_zimag)
                rb = -reg.intercept_ / reg.coef_[0] if reg.coef_[0] != 0 else subset_zreal[0]
                best_rb = rb
                best_reg = reg
    
    return best_rb, best_idx, best_r, best_reg


def find_high_freq_data(zreal, zimag, threshold):
    """排除线性区间，寻找高频端非线性区间"""
    high_freq_idx = len(zreal)
    
    for i in range(int(len(zreal)*0.1)+1, len(zreal), 2):
        subset_zreal = zreal[i:]
        subset_zimag = zimag[i:]
        is_linear, _ = check_linearity(subset_zreal, subset_zimag, threshold)
        if is_linear:
            high_freq_idx = i
            break
    
    return high_freq_idx


def huber_weight(residuals, tau):
    """Huber损失对应的权重函数"""
    weights = np.ones_like(residuals, dtype=float)
    mask = np.abs(residuals) > tau
    weights[mask] = tau / np.abs(residuals[mask])
    return weights


def detect_phase_jump(zreal, zimag, threshold=30):
    """
    检测Bode图相位是否存在突变点
    
    Args:
        zreal, zimag: 阻抗数据
        threshold: 判定突变的相位差阈值(度)
    
    Returns:
        1: 存在突变点
        0: 未发现突变
    """
    Z = zreal + 1j * zimag
    phase = np.angle(Z, deg=True)
    dphase = np.diff(phase)
    if np.any(np.abs(dphase) > threshold):
        return 1
    return 0


def fit_circle_irls(x, y, tau, max_iter, tol):
    """用IRLS(加权最小二乘)拟合圆，鲁棒处理异常点"""
    def calc_residuals(params):
        xc, yc, r = params
        return np.sqrt((x - xc)**2 + (y - yc)**2) - r
    
    # 初始值
    xc = np.mean(x)
    yc = np.mean(y)
    r = np.mean(np.sqrt((x - xc)**2 + (y - yc)**2))
    params = np.array([xc, yc, r])
    
    for i in range(max_iter):
        residuals = calc_residuals(params)
        weights = huber_weight(residuals, tau)
        
        def weighted_objective(params):
            return np.sum(weights * calc_residuals(params)**2)
        
        result = minimize(weighted_objective, params, method='Nelder-Mead')
        new_params = result.x
        
        if np.all(np.abs(new_params - params) < tol):
            break
        params = new_params
    
    return params[0], params[1], params[2]


# ============================================================
# X轴交点检测
# ============================================================

def find_x_axis_intercept(zreal, zimag, freq=None):
    """
    检测Nyquist图与实轴(X轴)的交点，作为Rb的直接测量
    
    物理背景：当高频存在感性响应时，阻抗谱虚部会穿过实轴，
    交点的实部直接给出Rb，无需复杂拟合。
    """
    report = {
        'method': 'X轴交点',
        'found': False,
        'intercept_index': None,
        'rb': None,
        'n_inductive': 0
    }
    
    if len(zreal) < 5:
        report['fail_reason'] = '数据点太少'
        return None, report
    
    # 统计感性响应点（Zimag > 0）
    n_inductive = np.sum(zimag > 0)
    report['n_inductive'] = int(n_inductive)
    
    if n_inductive == 0:
        report['fail_reason'] = 'Z\'\'无感性响应'
        return None, report
    
    # 查找符号变化点
    sign_changes = []
    for i in range(len(zimag) - 1):
        if (zimag[i] > 0 and zimag[i + 1] < 0) or (zimag[i] < 0 and zimag[i + 1] > 0):
            sign_changes.append(i)
    
    if not sign_changes:
        report['fail_reason'] = '未找到符号变化点'
        return None, report
    
    # 取第一个符号变化点（高频端）
    idx = sign_changes[0]
    
    # 线性插值求交点
    zimag_1, zimag_2 = zimag[idx], zimag[idx + 1]
    zreal_1, zreal_2 = zreal[idx], zreal[idx + 1]
    
    delta_zimag = zimag_2 - zimag_1
    if abs(delta_zimag) < 1e-15:
        rb = (zreal_1 + zreal_2) / 2
    else:
        t = -zimag_1 / delta_zimag
        rb = zreal_1 + t * (zreal_2 - zreal_1)
    
    if rb <= 0:
        report['fail_reason'] = f'交点Rb={rb:.2f}Ω ≤ 0'
        return None, report
    
    report.update({
        'found': True,
        'intercept_index': idx,
        'rb': rb
    })
    
    if freq is not None and len(freq) > idx:
        report['intercept_freq'] = freq[idx]
    
    return rb, report


# ============================================================
# Phase 1 新增：高频外推方法
# ============================================================

def fit_hf_extrapolation(zreal, freq, n_hf_ratio=0.2, r2_threshold=0.7):
    """
    高频外推方法：Zreal vs log(freq) 线性拟合并外推
    
    物理基础：高频段阻抗与频率的对数呈线性关系
    
    Args:
        zreal: 阻抗实部数组
        freq: 频率数组
        n_hf_ratio: 高频点比例（默认20%）
        r2_threshold: R²阈值（默认0.7）
    
    Returns:
        rb: 外推得到的Rb值
        report: 拟合报告
    """
    report = {
        'method': 'hf_extrapolation',
        'success': False,
        'r2': None,
        'n_points': 0
    }
    
    if freq is None or len(freq) < 5:
        report['fail_reason'] = '频率数据不足'
        return None, report
    
    try:
        # 选择高频段（前n_hf_ratio的点，至少5个）
        n_hf = max(5, int(len(zreal) * n_hf_ratio))
        
        # 找到 zreal 最小的 n_hf 个点（对应高频）
        sorted_indices = np.argsort(zreal)
        hf_indices = sorted_indices[:n_hf]
        
        freq_hf = freq[hf_indices]
        zreal_hf = zreal[hf_indices]
        
        # 确保频率递增
        sort_by_freq = np.argsort(freq_hf)
        freq_hf = freq_hf[sort_by_freq]
        zreal_hf = zreal_hf[sort_by_freq]
        
        # 线性拟合：Zreal = a * log10(freq) + b
        log_freq = np.log10(freq_hf)
        X = log_freq.reshape(-1, 1)
        reg = LinearRegression().fit(X, zreal_hf)
        
        slope = reg.coef_[0]
        intercept = reg.intercept_
        r_squared = reg.score(X, zreal_hf)
        
        report['r2'] = r_squared
        report['n_points'] = n_hf
        report['slope'] = slope
        report['intercept'] = intercept
        
        # 外推到10倍最高频率
        log_freq_extrap = np.log10(freq_hf.max() * 10)
        rb_extrap = slope * log_freq_extrap + intercept
        
        if rb_extrap > 0 and r_squared > r2_threshold and not np.isnan(rb_extrap):
            report['success'] = True
            return rb_extrap, report
        else:
            report['fail_reason'] = f'R²={r_squared:.3f}<{r2_threshold} 或 Rb={rb_extrap:.2f}无效'
            return None, report
            
    except Exception as e:
        report['fail_reason'] = str(e)
        return None, report


# ============================================================
# Phase 1 新增：高频平均兜底方法
# ============================================================

def fit_hf_average_fallback(zreal, hf_ratio=0.2):
    """
    高频平均兜底方法：取高频段Zreal的中位数作为Rb估计
    
    这是最后的兜底方法，当所有拟合方法都失败时使用
    
    Args:
        zreal: 阻抗实部数组
        hf_ratio: 高频段数据比例（默认20%）
    
    Returns:
        rb: 估计的Rb值
        report: 报告
    """
    report = {
        'method': 'hf_average_fallback',
        'success': False
    }
    
    n_hf = max(3, int(len(zreal) * hf_ratio))
    
    # 取zreal最小的点（对应高频）
    sorted_indices = np.argsort(zreal)
    hf_indices = sorted_indices[:n_hf]
    hf_zreal = zreal[hf_indices]
    
    rb_median = np.median(hf_zreal)
    
    if rb_median > 0 and not np.isnan(rb_median):
        report['success'] = True
        report['n_points'] = n_hf
        report['median'] = rb_median
        report['mean'] = np.mean(hf_zreal)
        return rb_median, report
    
    report['fail_reason'] = f'中位数无效: {rb_median}'
    return None, report


# ============================================================
# 主拟合函数 (Phase 1 整合版)
# ============================================================

def calculate_rb(zreal, zimag, temp, params, circle_dir=None, freq=None):
    """
    主拟合流程 (Phase 1 整合版)
    
    拟合策略（按优先级）：
    0. X轴交点检测（最高优先级）
    1. 数据预处理（Savitzky-Golay）
    2. 整体线性拟合
    3. 渐进移除低频端线性拟合
    4. IRLS圆弧拟合（放宽约束）
    5. 宽松线性拟合
    6. 最宽松线性拟合
    7. 高频外推
    8. 高频平均兜底
    9. 失败（返回None）
    
    Args:
        zreal, zimag: 阻抗数据
        temp: 当前温度
        params: 拟合参数
        circle_dir: 图片保存目录
        freq: 频率数组
    
    Returns:
        result: 包含rb、方法、相关系数等信息的字典
    """
    result = {
        'temperature': temp,
        'rb': None,
        'method': None,
        'r': None,
        'fit_params': None,
        'ok': False
    }
    
    fail_msgs = []
    
    # ========================================
    # 方法0: X轴交点检测 (最高优先级)
    # ========================================
    try:
        rb_intercept, intercept_report = find_x_axis_intercept(zreal, zimag, freq)
        
        if rb_intercept is not None and rb_intercept > 0:
            result.update({
                'rb': rb_intercept,
                'method': 'X轴交点',
                'r': 1.0,
                'fit_params': {
                    'intercept_index': intercept_report.get('intercept_index'),
                    'n_inductive': intercept_report.get('n_inductive', 0)
                },
                'ok': True
            })
            if circle_dir:
                try:
                    visualize_fitting(zreal, zimag, result, circle_dir)
                except:
                    pass
            return result
        else:
            fail_msgs.append(f"X轴交点: {intercept_report.get('fail_reason', '未找到')}")
    except Exception as e:
        fail_msgs.append(f"X轴交点异常: {str(e)}")
    
    # ========================================
    # 步骤1: 数据预处理 (Phase 1新增)
    # ========================================
    zimag_abs = np.abs(zimag)
    
    if params.get('enable_preprocessing', True):
        zreal_work, zimag_work, preprocess_report = filter_data_savgol(
            zreal, zimag_abs,
            window=params.get('filter_window', 7),
            poly=params.get('filter_poly', 3),
            thresh=params.get('outlier_threshold', 3.0)
        )
        result['preprocessing'] = preprocess_report
    else:
        zreal_work = zreal
        zimag_work = zimag_abs
    
    if len(zreal_work) < 5:
        result['method'] = '拟合失败'
        result['fail_reason'] = '数据点不足'
        return result
    
    # ========================================
    # 方法1: 整体线性拟合
    # ========================================
    is_linear, r = check_linearity(zreal_work, zimag_work, params['linear_threshold'])
    if is_linear:
        X = zreal_work.reshape(-1, 1)
        reg = LinearRegression().fit(X, zimag_work)
        rb = -reg.intercept_ / reg.coef_[0] if reg.coef_[0] != 0 else zreal_work[0]
        
        if rb > 0:
            result.update({
                'rb': rb,
                'method': '直线拟合',
                'r': r,
                'fit_params': {'slope': reg.coef_[0], 'intercept': reg.intercept_},
                'ok': True
            })
            if circle_dir:
                try:
                    visualize_fitting(zreal, zimag, result, circle_dir)
                except:
                    pass
            return result
    
    fail_msgs.append(f"直线拟合: r={r:.4f} < {params['linear_threshold']}")
    
    # ========================================
    # 方法2: 渐进线性拟合
    # ========================================
    rb, removed, r, reg = fit_line_with_progressive_removal(
        zreal_work, zimag_work, 
        params['linear_progressive_threshold'], 
        params['max_remove_ratio']
    )
    if rb is not None and rb > 0:
        result.update({
            'rb': rb,
            'method': '切线拟合',
            'r': r,
            'fit_params': {'slope': reg.coef_[0], 'intercept': reg.intercept_},
            'removed_points': removed,
            'ok': True
        })
        if circle_dir:
            try:
                visualize_fitting(zreal, zimag, result, circle_dir)
            except:
                pass
        return result
    
    fail_msgs.append(f"渐进线性: r={r:.4f}")
    
    # ========================================
    # 方法3: IRLS圆弧拟合 (Phase 1放宽约束)
    # ========================================
    high_freq_idx = find_high_freq_data(zreal_work, zimag_work, params['circle_linear_threshold'])
    found_circle = False
    
    while high_freq_idx >= 5:  # 至少5个点
        high_freq_zreal = zreal_work[:high_freq_idx]
        high_freq_zimag = zimag_work[:high_freq_idx]
        
        cx, cy, radius = fit_circle_irls(
            high_freq_zreal, high_freq_zimag,
            params['huber_tau'],
            params['circle_max_iter'],
            params['circle_tol'],
        )
        
        # Phase 1 放宽约束
        if radius <= 0 or np.isnan(radius) or np.isinf(radius):
            high_freq_idx -= 1
            continue
        # 放宽：半径只需大于0.3×|圆心y| (原来是1.0×)
        if radius <= 0.3 * abs(cy):
            high_freq_idx -= 1
            continue
        # 放宽：圆心y可达2倍平均虚部 (原来是1.0×)
        if abs(cy) >= 2.0 * np.mean(high_freq_zimag):
            high_freq_idx -= 1
            continue
        # 圆心x坐标不应超过数据最大值的1.5倍
        if cx > 1.5 * np.max(high_freq_zreal):
            break
        
        # 计算 Rb = 右交点
        try:
            discriminant = radius**2 - cy**2
            if discriminant < 0:
                high_freq_idx -= 1
                continue
            rb = cx + np.sqrt(discriminant)
        except:
            high_freq_idx -= 1
            continue
        
        if rb <= 0:
            high_freq_idx -= 1
            continue
        
        # 计算拟合质量
        distances = np.sqrt((high_freq_zreal - cx)**2 + (high_freq_zimag - cy)**2)
        fit_quality = max(0.0, min(1.0, 1.0 - np.mean(np.abs(distances - radius) / radius)))
        
        result.update({
            'rb': rb,
            'method': '圆弧拟合',
            'r': fit_quality,
            'fit_params': {
                'center': (cx, cy),
                'radius': radius,
                'nonlinear_part_end': high_freq_idx
            },
            'ok': True
        })
        found_circle = True
        break
    
    if found_circle:
        if circle_dir:
            try:
                visualize_fitting(zreal, zimag, result, circle_dir)
            except:
                pass
        return result
    
    fail_msgs.append("圆弧拟合: 未通过约束")
    
    # ========================================
    # 方法4: 宽松线性拟合
    # ========================================
    rb, removed, r, reg = fit_line_with_progressive_removal(
        zreal_work, zimag_work,
        params['relaxed_threshold'],
        params['max_remove_ratio']
    )
    if rb is not None and rb > 0:
        result.update({
            'rb': rb,
            'method': '宽松线性拟合',
            'r': r,
            'fit_params': {'slope': reg.coef_[0], 'intercept': reg.intercept_},
            'removed_points': removed,
            'ok': True
        })
        if circle_dir:
            try:
                visualize_fitting(zreal, zimag, result, circle_dir)
            except:
                pass
        return result
    
    fail_msgs.append(f"宽松线性: r={r:.4f}")
    
    # ========================================
    # 方法5: 最宽松线性拟合 (Phase 1新增)
    # ========================================
    very_relaxed_threshold = params.get('very_relaxed_threshold', 0.85)
    rb, removed, r, reg = fit_line_with_progressive_removal(
        zreal_work, zimag_work,
        very_relaxed_threshold,
        params['max_remove_ratio'] * 1.5  # 允许移除更多
    )
    if rb is not None and rb > 0:
        result.update({
            'rb': rb,
            'method': '最宽松线性拟合',
            'r': r,
            'fit_params': {'slope': reg.coef_[0], 'intercept': reg.intercept_},
            'removed_points': removed,
            'ok': True
        })
        if circle_dir:
            try:
                visualize_fitting(zreal, zimag, result, circle_dir)
            except:
                pass
        return result
    
    fail_msgs.append(f"最宽松线性: r={r:.4f}")
    
    # ========================================
    # 方法6: 高频外推 (Phase 1新增)
    # ========================================
    if freq is not None:
        rb_extrap, extrap_report = fit_hf_extrapolation(zreal_work, freq)
        if rb_extrap is not None:
            result.update({
                'rb': rb_extrap,
                'method': '高频外推',
                'r': extrap_report.get('r2', 0),
                'fit_params': extrap_report,
                'ok': True
            })
            if circle_dir:
                try:
                    visualize_fitting(zreal, zimag, result, circle_dir)
                except:
                    pass
            return result
        fail_msgs.append(f"高频外推: {extrap_report.get('fail_reason', '失败')}")
    
    # ========================================
    # 方法7: 高频平均兜底 (Phase 1新增)
    # ========================================
    rb_fallback, fallback_report = fit_hf_average_fallback(zreal_work)
    if rb_fallback is not None:
        result.update({
            'rb': rb_fallback,
            'method': '高频平均兜底',
            'r': 0.0,
            'fit_params': fallback_report,
            'ok': True
        })
        if circle_dir:
            try:
                visualize_fitting(zreal, zimag, result, circle_dir)
            except:
                pass
        return result
    
    # ========================================
    # 全部失败 - 返回None而不是0.1！
    # ========================================
    result['method'] = '拟合失败'
    result['fail_msgs'] = fail_msgs
    result['ok'] = False
    # 注意：rb保持为None，不再返回0.1
    
    return result


# ============================================================
# 可视化函数
# ============================================================

def visualize_fitting(zreal, zimag, result, save_dir):
    """拟合结果可视化"""
    temp = result['temperature']
    method = result['method']
    zimag_plot = np.abs(zimag)
    
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    axes[0].plot(zreal, zimag_plot, 'bo-', markersize=4, label='原始数据')
    
    if method == 'X轴交点':
        params = result.get('fit_params', {})
        intercept_idx = params.get('intercept_index')
        if intercept_idx is not None and intercept_idx < len(zreal) - 1:
            axes[0].plot([zreal[intercept_idx], zreal[intercept_idx+1]], 
                        [zimag_plot[intercept_idx], zimag_plot[intercept_idx+1]], 
                        'rs', markersize=8, label='X轴交点区域')
        if result['rb'] is not None:
            axes[0].plot([result['rb'], result['rb']], [0, max(zimag_plot)*0.1], 
                        'r--', linewidth=2, alpha=0.5)
        axes[0].axhline(y=0, color='gray', linestyle='--', linewidth=1, alpha=0.5)
        
    elif method in ['直线拟合', '切线拟合', '宽松线性拟合', '最宽松线性拟合']:
        params = result.get('fit_params', {})
        if params and 'slope' in params:
            z_fit = np.linspace(min(zreal), max(zreal), 100)
            zimag_fit = params['slope'] * z_fit + params['intercept']
            axes[0].plot(z_fit, zimag_fit, 'r--', linewidth=2, label=f"拟合直线 r={result['r']:.4f}")
            removed = result.get('removed_points', 0)
            if removed and removed > 0:
                axes[0].plot(zreal[:-removed], zimag_plot[:-removed], 'gs', markersize=6, label='线性区间')
                
    elif method == '圆弧拟合':
        params = result.get('fit_params', {})
        if params and 'center' in params:
            cx, cy = params['center']
            r = params['radius']
            theta = np.linspace(0, 2*np.pi, 200)
            circle_x = cx + r * np.cos(theta)
            circle_y = cy + r * np.sin(theta)
            axes[0].plot(circle_x, circle_y, 'r-', linewidth=2, label='拟合圆')
            axes[0].plot(cx, cy, 'r+', markersize=10, label=f"圆心({cx:.2f},{cy:.2f})")
            nonlinear_end = params.get('nonlinear_part_end', 0)
            if nonlinear_end > 0:
                axes[0].plot(zreal[:nonlinear_end], zimag_plot[:nonlinear_end], 'ms', markersize=6, label='圆拟合区间')
    
    if result['rb'] is not None:
        axes[0].axvline(x=result['rb'], color='g', linestyle='--', label=f"Rb={result['rb']:.2f}Ω")
    
    axes[0].set_title(f"{method} T={int(temp)}K")
    axes[0].set_xlabel("Z' (Ω)")
    axes[0].set_ylabel("|Z''| (Ω)")
    axes[0].legend(fontsize=8)
    axes[0].grid(True)
    axes[0].set_aspect('equal', adjustable='box')
    
    # 残差图
    if result['method'] != '拟合失败' and result.get('fit_params'):
        if method == 'X轴交点':
            axes[1].plot(zimag, 'bo-', markersize=3, label='Z\'\'')
            axes[1].axhline(y=0, color='r', linestyle='--', label='实轴')
            params = result.get('fit_params', {})
            intercept_idx = params.get('intercept_index')
            if intercept_idx is not None:
                axes[1].axvline(x=intercept_idx, color='g', linestyle='--', label='交点位置')
            axes[1].set_xlabel("数据点索引")
            axes[1].set_ylabel("Z'' (Ω)")
            axes[1].set_title("虚部vs数据点")
            axes[1].legend()
            axes[1].grid(True)
        elif method == '圆弧拟合':
            params = result['fit_params']
            cx, cy, r = params['center'][0], params['center'][1], params['radius']
            nonlinear_end = params.get('nonlinear_part_end', len(zreal))
            true_r = np.sqrt((zreal[:nonlinear_end] - cx)**2 + (zimag_plot[:nonlinear_end] - cy)**2)
            residuals = true_r - r
            axes[1].plot(residuals, 'bo-', markersize=3)
            axes[1].axhline(y=0, color='r', linestyle='--')
            axes[1].set_xlabel("数据点")
            axes[1].set_ylabel("残差")
            axes[1].set_title("拟合残差")
            axes[1].grid(True)
        elif 'slope' in result.get('fit_params', {}):
            params = result['fit_params']
            predicted_zimag = params['slope'] * zreal + params['intercept']
            residuals = zimag_plot - predicted_zimag
            axes[1].plot(residuals, 'bo-', markersize=3)
            axes[1].axhline(y=0, color='r', linestyle='--')
            axes[1].set_xlabel("数据点")
            axes[1].set_ylabel("残差")
            axes[1].set_title("拟合残差")
            axes[1].grid(True)
        else:
            axes[1].text(0.5, 0.5, f'方法: {method}', ha='center', va='center', transform=axes[1].transAxes)
            axes[1].set_title("无残差信息")
    else:
        axes[1].text(0.5, 0.5, '拟合失败', ha='center', va='center', transform=axes[1].transAxes, fontsize=14, color='red')
    
    plt.tight_layout()
    save_path = os.path.join(save_dir, f'fit_{int(temp)}K.png')
    plt.savefig(save_path, dpi=150, bbox_inches='tight')
    plt.close()
