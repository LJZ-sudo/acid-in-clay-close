# -*- coding: utf-8 -*-
"""
Arrhenius 分段拟合分析 - 终极多段解算引擎 (Ultimate Multi-Segment Solver)

核心思想：
竞争性多模型框架，最多支持 3 段（2 个相变点），让数据通过 AICc 统计学"竞标"。

支持模型：
- 1段模型（k=2）：单相态
- 2段连续模型（k=4）：一个相变点，连续
- 3段连续模型（k=6）：两个相变点，连续
- 2段非连续模型（k=5）：一个相变点，非连续（需通过 Chow Test）

统计方法：
- AICc: 带小样本校正的信息准则
- Chow Test: 结构突变检验（防止非连续模型过拟合）
- AICc Weights (Burnham & Anderson, 2002): 返回模型概率分布

版本：v4.0.0 (Ultimate Multi-Segment Solver)
日期：2026-04-10
"""

import logging

import numpy as np
from scipy import stats
from typing import Dict, List, Optional, Tuple
import pwlf

logger = logging.getLogger(__name__)

# 物理常数
kB = 8.617333262e-5  # 玻尔兹曼常数 (eV/K)
EV_TO_KJ_MOL = 96.485  # eV 转 kJ/mol
R_GAS = 8.314  # 气体常数 (J/(mol·K))


# ============================================================
# 辅助函数：Ea 计算
# ============================================================

def _calculate_activation_energy(slope: float) -> Tuple[float, float]:
    """
    从 Arrhenius 斜率计算活化能（同时返回 kJ/mol 和 eV）
    
    公式推导：
    - σ = σ0 * exp(-Ea/(R*T))
    - ln(σ) = ln(σ0) - Ea/(R*T)
    - ln(σ) = ln(σ0) - Ea/(R*1000) * (1000/T)
    - slope = d(ln_σ) / d(1000/T) = -Ea / (R*1000)
    - Ea = -slope * R * 1000 (J/mol)
    - Ea = -slope * R (kJ/mol)
    
    Args:
        slope: Arrhenius 斜率 (d(ln_σ) / d(1000/T))
    
    Returns:
        tuple: (Ea_kJ_mol, Ea_eV)
            - Ea_kJ_mol: 活化能 (kJ/mol)
            - Ea_eV: 活化能 (eV)
    """
    # Ea (J/mol) = -slope * R * 1000
    # Ea (kJ/mol) = -slope * R
    Ea_kJ_mol = -slope * R_GAS
    
    # 转换为 eV（固体物理学家常用单位）
    # 1 eV = 96.485 kJ/mol
    Ea_eV = Ea_kJ_mol / EV_TO_KJ_MOL
    
    return Ea_kJ_mol, Ea_eV


# ============================================================
# 核心函数：单段拟合
# ============================================================

def _fit_single_segment(x: np.ndarray, y: np.ndarray) -> Dict:
    """
    模型：单段线性回归（无相变）
    
    模型：y = a * x + b
    自由度：k = 2
    """
    if len(x) < 3:
        return {'success': False, 'error': f'Insufficient points: {len(x)} < 3'}
    
    try:
        slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)
        y_pred = slope * x + intercept
        rss = np.sum((y - y_pred)**2)
        
        return {
            'success': True,
            'k': 2,
            'rss': float(rss),
            'slope': float(slope),
            'intercept': float(intercept),
            'r_squared': float(r_value**2),
            'breakpoints': [],
            'y_pred': y_pred
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}


# ============================================================
# 核心函数：多段连续拟合（使用 pwlf）
# ============================================================

def _fit_continuous_multi_segments(
    x: np.ndarray, 
    y: np.ndarray, 
    n_segments: int,
    min_segment_points: int = 4
) -> Dict:
    """
    使用 pwlf 库进行连续多段拟合
    
    Args:
        x: 横轴数据（1000/T）
        y: 纵轴数据（ln_sigma）
        n_segments: 段数（2 或 3）
        min_segment_points: 每段最小点数
    
    Returns:
        dict: 拟合结果
    """
    if n_segments < 2 or n_segments > 3:
        return {'success': False, 'error': f'Invalid n_segments: {n_segments}'}
    
    n_breakpoints = n_segments - 1
    min_points_required = n_segments * min_segment_points
    
    if len(x) < min_points_required:
        return {
            'success': False,
            'error': f'Insufficient points: {len(x)} < {min_points_required}'
        }
    
    try:
        # 使用 pwlf 进行连续分段拟合
        model = pwlf.PiecewiseLinFit(x, y)
        
        # 自动寻找最优断点
        breaks = model.fit(n_segments)
        
        # 获取拟合结果
        y_pred = model.predict(x)
        rss = np.sum((y - y_pred)**2)
        
        # 提取断点（排除端点）
        breakpoints = breaks[1:-1].tolist()  # 去掉首尾
        
        # 提取各段的斜率和截距
        slopes = model.slopes
        intercepts = model.intercepts  # ✅ 修复：提取截距
        
        # 计算各段的起止索引
        segment_indices = []
        for i in range(n_segments):
            if i == 0:
                start_x = x[0]
            else:
                start_x = breakpoints[i-1]
            
            if i == n_segments - 1:
                end_x = x[-1]
            else:
                end_x = breakpoints[i]
            
            # ✅ 修复：使用 searchsorted 代替 argmin（更精确）
            start_idx = int(np.searchsorted(x, start_x, side='left'))
            end_idx = int(np.searchsorted(x, end_x, side='right'))
            
            # 边界保护
            start_idx = max(0, min(start_idx, len(x) - 1))
            end_idx = max(1, min(end_idx, len(x)))
            
            segment_indices.append({
                'start_idx': int(start_idx),
                'end_idx': int(end_idx),
                'slope': float(slopes[i]),
                'intercept': float(intercepts[i])  # ✅ 修复：添加截距
            })
        
        return {
            'success': True,
            'k': 2 * n_segments,  # 连续 n 段：k = 2n (斜率 + 截距，连续性减少自由度)
            'rss': float(rss),
            'breakpoints': breakpoints,
            'slopes': slopes.tolist(),
            'intercepts': intercepts.tolist(),  # ✅ 修复：返回截距
            'segment_indices': segment_indices,
            'y_pred': y_pred,
            'n_segments': n_segments
        }
    
    except Exception as e:
        return {'success': False, 'error': str(e)}


# ============================================================
# 核心函数：2段非连续拟合 + Chow Test
# ============================================================

def _fit_discontinuous_2_segments(
    x: np.ndarray, 
    y: np.ndarray,
    min_segment_points: int = 4
) -> Dict:
    """
    2段非连续拟合（允许断崖跳跃）+ Chow Test 验证
    
    Args:
        x: 横轴数据
        y: 纵轴数据
        min_segment_points: 每段最小点数
    
    Returns:
        dict: 拟合结果（如果未通过 Chow Test，返回 success=False）
    """
    n = len(x)
    if n < 2 * min_segment_points:
        return {
            'success': False,
            'error': f'Insufficient points: {n} < {2 * min_segment_points}'
        }
    
    best_rss = np.inf
    best_breakpoint_idx = None
    best_fit_result = None
    
    # 遍历所有可能的断点
    for bp_idx in range(min_segment_points, n - min_segment_points):
        # 左段
        x1 = x[:bp_idx]
        y1 = y[:bp_idx]
        
        # 右段
        x2 = x[bp_idx:]
        y2 = y[bp_idx:]
        
        try:
            # 分别拟合两段
            slope1, intercept1, _, _, _ = stats.linregress(x1, y1)
            slope2, intercept2, _, _, _ = stats.linregress(x2, y2)
            
            # 计算总残差
            y_pred1 = slope1 * x1 + intercept1
            y_pred2 = slope2 * x2 + intercept2
            rss = np.sum((y1 - y_pred1)**2) + np.sum((y2 - y_pred2)**2)
            
            if rss < best_rss:
                best_rss = rss
                best_breakpoint_idx = bp_idx
                best_fit_result = {
                    'slope1': slope1,
                    'intercept1': intercept1,
                    'slope2': slope2,
                    'intercept2': intercept2,
                    'breakpoint_idx': bp_idx,
                    'breakpoint_x': float(x[bp_idx]),
                    'rss': float(rss)
                }
        
        except Exception:
            continue
    
    if best_fit_result is None:
        return {'success': False, 'error': 'Failed to find valid breakpoint'}
    
    # ===== Chow Test 验证 =====
    # 检验断崖跳跃是否显著
    bp_idx = best_fit_result['breakpoint_idx']
    
    # 1. 全局单段拟合（pooled regression）
    slope_pool, intercept_pool, _, _, _ = stats.linregress(x, y)
    y_pred_pool = slope_pool * x + intercept_pool
    rss_pool = np.sum((y - y_pred_pool)**2)
    
    # 2. 分段拟合的总 RSS
    rss_segments = best_rss
    
    # 3. Chow Test F统计量
    # F = ((RSS_pool - RSS_segments) / q) / (RSS_segments / (n - 2k))
    # q = 额外参数数 = 2（一个断点增加一个截距和一个斜率）
    # n - 2k = n - 4（两段独立拟合，各2个参数）
    q = 2
    df1 = q
    df2 = n - 4
    
    if df2 <= 0:
        return {'success': False, 'error': 'Insufficient degrees of freedom for Chow Test'}
    
    F_stat = ((rss_pool - rss_segments) / q) / (rss_segments / df2)
    p_value = stats.f.sf(F_stat, df1, df2)
    
    # 4. 判断跳跃显著性
    # 如果 p_value > 0.05，说明分段并不显著优于单段，拒绝非连续模型
    if p_value > 0.05:
        return {
            'success': False,
            'error': f'Chow Test failed: p={p_value:.4f} > 0.05 (jump not significant)'
        }
    
    # 5. 额外验证：跳跃幅度
    # 计算断点处的跳跃距离
    left_pred = best_fit_result['slope1'] * best_fit_result['breakpoint_x'] + best_fit_result['intercept1']
    right_pred = best_fit_result['slope2'] * best_fit_result['breakpoint_x'] + best_fit_result['intercept2']
    jump_distance = abs(right_pred - left_pred)
    
    # 计算残差标准差
    residual_std = np.sqrt(rss_segments / (n - 4))
    
    # 跳跃必须 > 2 * 残差标准差
    if jump_distance < 2 * residual_std:
        return {
            'success': False,
            'error': f'Jump too small: {jump_distance:.4f} < 2*std ({2*residual_std:.4f})'
        }
    
    # 通过所有检验
    return {
        'success': True,
        'k': 5,  # 非连续2段：4个参数（2个斜率+2个截距）+ 1个断点
        'rss': float(best_rss),
        'breakpoints': [best_fit_result['breakpoint_x']],
        'slopes': [best_fit_result['slope1'], best_fit_result['slope2']],
        'intercepts': [best_fit_result['intercept1'], best_fit_result['intercept2']],
        'segment_indices': [
            {
                'start_idx': 0, 
                'end_idx': bp_idx, 
                'slope': best_fit_result['slope1'],
                'intercept': best_fit_result['intercept1']  # ✅ 修复：添加截距
            },
            {
                'start_idx': bp_idx, 
                'end_idx': n, 
                'slope': best_fit_result['slope2'],
                'intercept': best_fit_result['intercept2']  # ✅ 修复：添加截距
            }
        ],
        'n_segments': 2,
        'chow_test': {
            'F_stat': float(F_stat),
            'p_value': float(p_value),
            'jump_distance': float(jump_distance),
            'residual_std': float(residual_std)
        }
    }


# ============================================================
# 核心函数：AICc 计算
# ============================================================

def _calculate_aicc(n: int, rss: float, k: int) -> float:
    """
    计算小样本校正的 Akaike 信息准则
    
    AICc = n*ln(RSS/n) + 2k + (2k*(k+1)) / (n - k - 1)
    
    Args:
        n: 样本量
        rss: 残差平方和
        k: 参数个数
    
    Returns:
        float: AICc 值（越小越好）
    """
    if n <= k + 1:
        return np.inf  # 自由度不足
    
    if rss <= 0:
        return np.inf
    
    aicc = n * np.log(rss / n) + 2 * k + (2 * k * (k + 1)) / (n - k - 1)
    
    return float(aicc)


# ============================================================
# 核心函数：AICc Weights 计算
# ============================================================

def _calculate_model_weights(aicc_values: List[float]) -> List[float]:
    """
    计算 AICc Weights (Burnham & Anderson, 2002)
    
    Args:
        aicc_values: 各模型的 AICc 值列表
    
    Returns:
        list: 各模型的概率（归一化权重）
    """
    aicc_array = np.array(aicc_values)
    
    # 找到最小值
    min_aicc = np.min(aicc_array)
    
    # 计算 delta_i
    delta_i = aicc_array - min_aicc
    
    # 相对似然
    likelihood = np.exp(-delta_i / 2)
    
    # 归一化
    weights = likelihood / np.sum(likelihood)
    
    return weights.tolist()


# ============================================================
# 主函数：竞争性多模型 Arrhenius 分析
# ============================================================

def analyze_arrhenius(
    x_data: np.ndarray,
    y_data: np.ndarray,
    min_segment_points: int = 4,
    aic_improvement_threshold: float = 5.0
) -> Dict:
    """
    终极多段 Arrhenius 分析（支持最多 3 段）
    
    核心流程：
    1. 预处理数据
    2. 拟合所有候选模型（1段、2段连续、3段连续、2段非连续）
    3. 计算各模型的 AICc
    4. 计算 AICc Weights（模型概率）
    5. 选择最佳模型（带改善阈值保护）
    
    Args:
        x_data: 横轴数据（1000/T，K^-1）
        y_data: 纵轴数据（ln_sigma 或 log10_Rb）
        min_segment_points: 每段最小点数（默认 4）
        aic_improvement_threshold: AICc 改善阈值（默认 5.0）
    
    Returns:
        dict: {
            'success': bool,
            'best_model_type': str ('single', 'continuous_2', 'continuous_3', 'discontinuous_2'),
            'confidence': float (最佳模型的 AICc Weight, 0-1),
            'n_segments': int (1, 2, or 3),
            'transition_temps_K': list (相变温度列表，K),
            'segments': list (各段的详细信息),
            'model_probabilities': dict (所有模型的概率),
            'model_details': dict (各模型的详细结果),
            'n_points_used': int
        }
    """
    # ===== 步骤 1: 预处理 =====
    x = np.asarray(x_data, dtype=float)
    y = np.asarray(y_data, dtype=float)
    
    # ✅ 修复：数据排序（pwlf 强依赖单调递增的 x）
    # 虽然降温实验中 1000/T 自然递增，但如果有温度波动或升温数据，必须排序
    sort_indices = np.argsort(x)
    x = x[sort_indices]
    y = y[sort_indices]
    
    n = len(x)
    
    if n < 5:
        return {
            'success': False,
            'n_segments': 0,
            'segments': [],
            'has_transition': False,
            'transition_temps_K': [],
            'n_points_used': n,
            'error': f'Insufficient data points: {n} < 5'
        }
    
    # 检查数据有效性
    if np.any(~np.isfinite(x)) or np.any(~np.isfinite(y)):
        return {
            'success': False,
            'error': 'Data contains NaN or Inf',
            'n_points_used': n
        }
    
    # ===== 步骤 2: 拟合所有候选模型 =====
    models = {}
    
    # 模型 A：单段
    logger.debug(f"  [Model A] 拟合单段模型...")
    models['single'] = _fit_single_segment(x, y)
    
    # 模型 B：2段连续
    if n >= 2 * min_segment_points:
        logger.debug(f"  [Model B] 拟合 2 段连续模型...")
        models['continuous_2'] = _fit_continuous_multi_segments(x, y, n_segments=2, min_segment_points=min_segment_points)
    else:
        models['continuous_2'] = {'success': False, 'error': f'Insufficient points for 2 segments: {n}'}
    
    # 模型 C：3段连续
    if n >= 3 * min_segment_points:
        logger.debug(f"  [Model C] 拟合 3 段连续模型...")
        models['continuous_3'] = _fit_continuous_multi_segments(x, y, n_segments=3, min_segment_points=min_segment_points)
    else:
        models['continuous_3'] = {'success': False, 'error': f'Insufficient points for 3 segments: {n}'}
    
    # 模型 D：2段非连续（需通过 Chow Test）
    if n >= 2 * min_segment_points:
        logger.debug(f"  [Model D] 拟合 2 段非连续模型...")
        models['discontinuous_2'] = _fit_discontinuous_2_segments(x, y, min_segment_points=min_segment_points)
    else:
        models['discontinuous_2'] = {'success': False, 'error': f'Insufficient points for discontinuous model: {n}'}
    
    # ===== 步骤 3: 计算 AICc =====
    valid_models = {}
    aicc_values = {}
    
    for model_name, result in models.items():
        if result.get('success'):
            k = result['k']
            rss = result['rss']
            aicc = _calculate_aicc(n, rss, k)
            
            aicc_values[model_name] = aicc
            valid_models[model_name] = result
            
            logger.debug(f"    {model_name}: AICc = {aicc:.2f}, RSS = {rss:.6f}, k = {k}")
    
    if not valid_models:
        return {
            'success': False,
            'error': 'No valid models found',
            'n_points_used': n
        }
    
    # ===== 步骤 4: 计算 AICc Weights =====
    model_names = list(aicc_values.keys())
    aicc_list = [aicc_values[name] for name in model_names]
    weights = _calculate_model_weights(aicc_list)
    
    model_probabilities = {name: round(w, 4) for name, w in zip(model_names, weights)}
    
    logger.debug(f"\n  [AICc Weights]")
    for name, prob in model_probabilities.items():
        logger.debug(f"    {name}: {prob*100:.1f}%")
    
    # ===== 步骤 5: 选择最佳模型（带改善阈值保护）=====
    # 找到 AICc 最低的模型
    best_model_name = min(aicc_values, key=aicc_values.get)
    best_aicc = aicc_values[best_model_name]
    
    # 防过拟合保护：如果最佳模型是复杂模型，检查 AICc 改善是否显著
    single_aicc = aicc_values.get('single', np.inf)
    
    # 按复杂度排序的模型列表
    complexity_order = ['single', 'continuous_2', 'discontinuous_2', 'continuous_3']
    
    # 找到第一个满足改善阈值的模型
    final_model_name = 'single'  # 默认最简单
    
    for model_name in complexity_order:
        if model_name not in aicc_values:
            continue
        
        delta_aicc = single_aicc - aicc_values[model_name]
        
        if delta_aicc >= aic_improvement_threshold:
            final_model_name = model_name
            logger.debug(f"\n  [Model Selection] {model_name}: AICc 改善 {delta_aicc:.2f} >= {aic_improvement_threshold:.2f}，接受")
        elif model_name == 'single':
            final_model_name = 'single'
            logger.debug(f"\n  [Model Selection] {model_name}: 基准模型")
        else:
            logger.debug(f"  [Model Selection] {model_name}: AICc 改善 {delta_aicc:.2f} < {aic_improvement_threshold:.2f}，拒绝（过拟合风险）")
    
    logger.debug(f"\n  [Final Choice] 最佳模型: {final_model_name}")
    
    best_result = valid_models[final_model_name]
    confidence = model_probabilities[final_model_name]
    
    # ===== 步骤 6: 构建返回结果 =====
    # 提取断点（转换为温度 K）
    breakpoints_x = best_result.get('breakpoints', [])
    transition_temps_K = [1000.0 / bp_x for bp_x in breakpoints_x]
    
    # 构建 segments 信息
    segments = []
    
    if final_model_name == 'single':
        # 单段
        slope = best_result['slope']
        intercept = best_result['intercept']
        Ea_kJ, Ea_eV = _calculate_activation_energy(slope)  # ✅ 修复：解包 tuple
        
        # 计算温度范围
        temp_range_K = [1000.0 / x[-1], 1000.0 / x[0]]  # [T_min, T_max]
        
        segments.append({
            'segment_id': 0,
            'start_idx': 0,
            'end_idx': n,
            'n_points': n,
            'slope': slope,
            'intercept': intercept,
            'Ea_kJ_per_mol': Ea_kJ,
            'Ea_eV': Ea_eV,  # ✅ 修复：添加 eV 单位
            'temp_range_K': temp_range_K,  # ✅ 修复：添加温度范围（plotter 需要）
            'r_squared': best_result.get('r_squared', None)
        })
    else:
        # 多段
        n_segments = best_result.get('n_segments', 2)
        slopes = best_result.get('slopes', [])
        segment_indices = best_result.get('segment_indices', [])
        
        for i, seg_info in enumerate(segment_indices):
            slope = seg_info['slope']
            intercept = seg_info.get('intercept', None)  # ✅ 修复：从 seg_info 读取截距
            Ea_kJ, Ea_eV = _calculate_activation_energy(slope)  # ✅ 修复：解包 tuple
            
            # 计算该段的温度范围
            start_idx = seg_info['start_idx']
            end_idx = seg_info['end_idx']
            temp_range_K = [1000.0 / x[min(end_idx-1, len(x)-1)], 1000.0 / x[start_idx]]
            
            segments.append({
                'segment_id': i,
                'start_idx': start_idx,
                'end_idx': end_idx,
                'n_points': end_idx - start_idx,
                'slope': slope,
                'intercept': intercept,
                'Ea_kJ_per_mol': Ea_kJ,
                'Ea_eV': Ea_eV,  # ✅ 修复：添加 eV 单位
                'temp_range_K': temp_range_K,  # ✅ 修复：添加温度范围（plotter 需要）
                'r_squared': None
            })
    
    return {
        'success': True,
        'best_model_type': final_model_name,
        'confidence': confidence,
        'n_segments': len(segments),
        'transition_temps_K': transition_temps_K,
        'segments': segments,
        'model_probabilities': model_probabilities,
        'model_details': {
            name: {
                'aicc': aicc_values[name],
                'rss': result['rss'],
                'k': result['k']
            } for name, result in valid_models.items()
        },
        'n_points_used': n,
        'has_transition': len(segments) > 1,
        'chow_test': best_result.get('chow_test') if final_model_name == 'discontinuous_2' else None
    }


# ============================================================
# 包装函数：批量序列分析
# ============================================================

def analyze_arrhenius_series(
    measurement_records: List[Dict],
    min_points: int = 5,
    min_segment_points: int = 4,
    aic_improvement_threshold: float = 5.0
) -> Dict:
    """
    批量 Arrhenius 序列分析（从测量记录中提取数据）
    
    Args:
        measurement_records: 测量记录列表，每条记录包含:
            - success: bool
            - temperature_K: float
            - conductivity_s_per_cm: float (或 rb_ohm)
        
        min_points: 最小点数要求
        min_segment_points: 每段最小点数
        aic_improvement_threshold: AICc 改善阈值
    
    Returns:
        dict: 分析结果（同 analyze_arrhenius）
    """
    # 提取有效数据
    temps_K = []
    conductivities = []
    
    for rec in measurement_records:
        if not isinstance(rec, dict):
            continue
        
        if not rec.get('success', False):
            continue
        
        T_K = rec.get('temperature_K')
        sigma = rec.get('conductivity_s_per_cm')
        
        if T_K is None or sigma is None:
            continue
        
        if T_K <= 0 or sigma <= 0:
            continue
        
        temps_K.append(float(T_K))
        conductivities.append(float(sigma))
    
    if len(temps_K) < min_points:
        return {
            'success': False,
            'n_segments': 0,
            'segments': [],
            'has_transition': False,
            'transition_temps_K': [],
            'n_points_used': len(temps_K),
            'error': f'Insufficient valid points: {len(temps_K)} < {min_points}'
        }
    
    # 计算 1000/T 和 ln(sigma)
    x_data = np.array([1000.0 / T for T in temps_K])
    y_data = np.log(conductivities)  # 自然对数
    
    # 调用核心分析函数
    return analyze_arrhenius(x_data, y_data, min_segment_points, aic_improvement_threshold)
