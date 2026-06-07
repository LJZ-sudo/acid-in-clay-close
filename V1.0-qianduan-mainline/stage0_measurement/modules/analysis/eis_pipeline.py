# -*- coding: utf-8 -*-
"""
EIS 分析管线（纯函数版 Facade）

这是整个 Analysis 层的统一门面，负责协调调用各个纯函数算法。

核心原则：
1. 统一门面调度 - analyze_eis_point() 作为核心入口
2. 标准字典契约 - 返回统一的结果字典，子算法失败不导致崩溃
3. 绝对无副作用 - 无 print、无文件写入、无 sys.path 修改
4. 纯计算逻辑 - 只接受数据和参数，返回结果
5. 单安检门 + KK警告 - QA 熔断 + KK 警告机制，最大化数据利用率

执行顺序（严格）：
数据清洗 -> 质量分析(QA) -> KK验证 -> Rb拟合 -> DRT分析

熔断与警告规则：
- 第一道安检门（QA）：触发致命错误 -> 立即熔断，status='REJECTED_BY_QA'
- KK 校验（警告模式）：is_valid=False -> 继续执行，标记 'kk_warning': True

主要功能：
- 单点 EIS 分析（Rb 拟合、电导率、质量评估、KK 校验、DRT、相变检测）
- 多点 Arrhenius 分析（序列过滤、分段拟合）
- JSON 安全转换

版本：3.2.0 (KK 降级为警告版)
"""

import numpy as np
from typing import Dict, List, Optional, Tuple, Any

# 导入重构后的纯函数算法
from .algorithms.rb_fitting import fit_rb_and_conductivity, get_default_fit_params as get_rb_fit_params
from .algorithms.kk_validation import validate_kk_consistency
from .algorithms.drt_analysis import analyze_drt
from .algorithms.arrhenius import analyze_arrhenius
from .data_quality import assess_data_quality
# phase_detect 模块已重构为 Agent 决策专用，不再提供单点相变分数计算


# ============================================================
# 公共接口：单点 EIS 分析
# ============================================================

def analyze_eis_point(
    frequencies,
    z_real,
    z_imag,
    temperature_C,
    thickness_cm,
    area_cm2,
    run_rb=True,
    run_quality=True,
    run_kk=True,
    run_drt=False,
    run_phase_score=False,
    rb_fit_params=None,
    prev_conductivity=None,
    qa_config=None,
    kk_config=None
):
    """
    单温度点 EIS 统一分析（纯函数版主入口，QA 熔断 + KK 警告）
    
    执行顺序（严格）：
    1. 数据清洗（输入转换与验证）
    2. 【第一道安检门】质量分析 (QA)
       - 如果触发致命错误（F 级 + fatal_check），立即熔断，返回 status='REJECTED_BY_QA'
    3. KK 一致性校验（警告模式）
       - 如果 is_valid=False，继续执行，标记 'kk_warning': True
       - 只有 success=False（计算失败）才会影响流程
    4. Rb 拟合 + 电导率计算
    5. DRT 分析（可选）
    6. 相变检测分数（可选）
    
    Args:
        frequencies: 频率数组 (Hz)
        z_real: 阻抗实部 (Ω)
        z_imag: 阻抗虚部 (Ω)
        temperature_C: 温度 (°C)
        thickness_cm: 样品厚度 (cm)
        area_cm2: 电极面积 (cm²)
        run_rb: 是否运行 Rb 拟合（默认 True）
        run_quality: 是否运行质量评估（默认 True，强烈建议开启）
        run_kk: 是否运行 KK 校验（默认 True，强烈建议开启）
        run_drt: 是否运行 DRT 分析（默认 False，计算量大）
        run_phase_score: 是否运行相变检测分数（默认 False）
        rb_fit_params: Rb 拟合参数（None 使用默认值）
        prev_conductivity: 前一次电导率，用于相变检测（可选）
        qa_config: 质量评估配置（None 使用默认值）
        kk_config: KK 校验配置（None 使用默认值）
    
    Returns:
        dict: 统一结果字典，包含以下字段
            - success: bool，整体是否成功
            - status: str，处理状态
                - 'OK': 正常完成
                - 'REJECTED_BY_QA': 质量检查熔断
                - 'PARTIAL': 部分成功（Rb 或 DRT 失败）
            - kk_warning: bool，KK 校验警告标记
            - temperature_C: float，温度 (°C)
            - temperature_K: float，温度 (K)
            - rb_result: dict，Rb 拟合结果（熔断时为 None）
            - quality_result: dict，质量评估结果
            - kk_result: dict，KK 校验结果（QA 熔断时为 None）
            - drt_result: dict，DRT 分析结果（熔断时为 None）
            - phase_score_result: dict，相变检测分数结果（熔断时为 None）
            - error: str or None，整体失败原因
    """
    # ===== 步骤 1: 数据清洗（输入转换与验证） =====
    freq = np.array(frequencies, dtype=float)
    zreal = np.array(z_real, dtype=float)
    zimag = np.array(z_imag, dtype=float)
    
    temperature_K = float(temperature_C) + 273.15
    
    # 初始化结果容器
    result = {
        'success': False,
        'status': 'UNKNOWN',
        'kk_warning': False,  # KK 警告标记
        'temperature_C': float(temperature_C),
        'temperature_K': temperature_K,
        'rb_result': None,
        'quality_result': None,
        'kk_result': None,
        'drt_result': None,
        'phase_score_result': None,
        'error': None
    }
    
    # 基本输入验证
    if len(freq) < 5:
        result['error'] = f'数据点不足 ({len(freq)} < 5)'
        result['status'] = 'REJECTED_BY_INPUT'
        return result
    
    if len(freq) != len(zreal) or len(freq) != len(zimag):
        result['error'] = '数据长度不一致'
        result['status'] = 'REJECTED_BY_INPUT'
        return result
    
    # ===== 步骤 2: 【第一道安检门】质量分析 (QA) =====
    if run_quality:
        try:
            quality_result = assess_data_quality(
                frequencies=freq,
                z_real=zreal,
                z_imag=zimag,
                temperature=temperature_K,
                config=qa_config
            )
            result['quality_result'] = quality_result
            
            # 🚨 熔断检查：QA 失败（仅 F 级致命错误熔断）
            qa_grade = quality_result.get('grade', 'F')
            fatal_check = quality_result.get('details', {}).get('fatal_check')
            
            # 只熔断 F 级且触发致命检查的数据（阻抗超量程或低频失真）
            if qa_grade == 'F' and fatal_check:
                result['success'] = False
                result['status'] = 'REJECTED_BY_QA'
                result['error'] = f"QA 熔断: {quality_result.get('message', 'Quality check failed')}"
                # 立即返回，不执行后续任何分析
                return result
        
        except Exception as e:
            result['quality_result'] = {
                'valid': False,
                'quality_score': 0.0,
                'grade': 'F',
                'message': f'Quality assessment exception: {str(e)}',
                'details': {}
            }
            result['success'] = False
            result['status'] = 'REJECTED_BY_QA'
            result['error'] = f'QA 异常熔断: {str(e)}'
            return result
    
    # ===== 步骤 3: KK 一致性校验（警告模式，不熔断） =====
    if run_kk:
        try:
            # 准备 KK 配置参数
            kk_params = {} if kk_config is None else kk_config.copy()
            kk_params.setdefault('preprocess', True)
            
            kk_result = validate_kk_consistency(
                frequencies=freq,
                z_real=zreal,
                z_imag=zimag,
                **kk_params
            )
            result['kk_result'] = kk_result
            
            # ⚠️ 警告模式：仅记录，不熔断
            kk_success = kk_result.get('success', False)
            kk_valid = kk_result.get('is_valid', False)
            
            # 只有计算失败（success=False）才影响流程（极少发生）
            if not kk_success:
                # KK 计算本身出错（如 linKK 崩溃），这是程序问题
                result['kk_warning'] = True
                # 不熔断，但记录警告
                warning_msg = f"KK 计算异常: {kk_result.get('message', 'Unknown error')}"
                if result['error']:
                    result['error'] += f" | {warning_msg}"
                else:
                    result['error'] = warning_msg
            
            # is_valid=False 仅标记警告，继续执行
            if not kk_valid:
                result['kk_warning'] = True
                # 不覆盖 error，只在没有其他错误时添加警告
                if not result['error']:
                    result['error'] = f"KK 警告: {kk_result.get('message', 'Data does not satisfy KK relations')}"
        
        except Exception as e:
            # KK 校验异常也不熔断，标记警告
            result['kk_result'] = {
                'success': False,
                'passed': False,
                'is_valid': False,
                'score': 0.0,
                'mu_mean': None,
                'mu_median': None,
                'mu_max': None,
                'mu_rmse': None,
                'method': 'linKK_impedance',
                'message': f'KK validation exception: {str(e)}',
                'error': str(e)
            }
            result['kk_warning'] = True
            if not result['error']:
                result['error'] = f'KK 异常警告: {str(e)}'
    
    # ===== 步骤 4: Rb 拟合 + 电导率（继续执行，不受 KK 警告影响） =====
    if run_rb:
        try:
            if rb_fit_params is None:
                rb_fit_params = get_rb_fit_params()
            
            rb_result = fit_rb_and_conductivity(
                frequencies=freq,
                z_real=zreal,
                z_imag=zimag,
                thickness_cm=thickness_cm,
                area_cm2=area_cm2,
                temperature_K=temperature_K,
                fit_params=rb_fit_params
            )
            result['rb_result'] = rb_result
            
            # Rb 拟合失败不熔断，但标记为部分成功
            if not rb_result.get('success', False):
                result['error'] = f"Rb fitting failed: {rb_result.get('error', 'unknown')}"
                result['status'] = 'PARTIAL'
        
        except Exception as e:
            result['rb_result'] = {
                'success': False,
                'rb_ohm': None,
                'conductivity_s_per_cm': None,
                'method': 'error',
                'fit_quality': None,
                'error': str(e)
            }
            result['error'] = f"Rb fitting exception: {str(e)}"
            result['status'] = 'PARTIAL'
    
    # ===== 步骤 5: DRT 分析（可选，通过双重安检后执行） =====
    if run_drt:
        try:
            drt_result = analyze_drt(
                frequencies=freq,
                z_real=zreal,
                z_imag=zimag,
                min_points=10
            )
            result['drt_result'] = drt_result
            
            # DRT 失败不影响整体状态
            if not drt_result.get('success', False) and result['status'] != 'PARTIAL':
                result['status'] = 'PARTIAL'
        
        except Exception as e:
            result['drt_result'] = {
                'success': False,
                'tau': None,
                'G': None,
                'R_inf': None,
                'lambda_reg': None,
                'fit_quality': None,
                'peaks': [],
                'Z_fit': None,
                'error': str(e)
            }
            if result['status'] != 'PARTIAL':
                result['status'] = 'PARTIAL'
    
    # ===== 步骤 6: 相变检测分数（已废弃） =====
    # 注：相变检测已由 phase_detect.py 中的 Agent 统一处理（基于局部斜率）
    # 单点相变分数计算已废弃，不再使用
    if run_phase_score:
        # 兼容性：返回空结果，避免下游代码报错
        result['phase_score_result'] = {
            'phase_jump_score': 0.0,
            'method_change_score': 0.0,
            'is_phase_transition': False,
            'max_phase_change': 0.0,
            'method_type': 'deprecated',
            'error': 'Phase detection has been migrated to Agent (phase_detect.py)'
        }
    
    # ===== 判断整体成功 =====
    # 如果至少有 Rb 拟合成功，且未被 QA 熔断，就认为整体成功
    rb_success = result.get('rb_result', {}).get('success', False) if run_rb else True
    
    if result['status'] not in ['REJECTED_BY_QA', 'REJECTED_BY_INPUT']:
        result['success'] = rb_success
        if result['status'] != 'PARTIAL':
            result['status'] = 'OK'
    
    return result


# ============================================================
# 公共接口：多点 Arrhenius 分析
# ============================================================

def analyze_arrhenius_series(
    measurement_records,
    min_points=5,
    max_segments=4,
    temperature_key='temperature_K',
    conductivity_key='conductivity_s_per_cm',
    rb_key='rb_ohm',
    success_key='success'
):
    """
    从测量记录序列提取并分析 Arrhenius 关系（纯函数版）

    DEPRECATED / DUPLICATE (Tier1 note 2026-06-01):
        The canonical batch analyzer is
        ``modules.analysis.algorithms.arrhenius.analyze_arrhenius_series``,
        which is what the offline frozen pipeline
        (``code/stage0_processing/process_new_materials_stage0.py``) and the
        online/offline workflows actually call. This ``eis_pipeline`` copy has
        no live callers and is kept only for backward compatibility. Prefer the
        ``algorithms`` version for new code.

        ``max_segments`` is retained for signature compatibility but is NOT
        forwarded: the underlying ``analyze_arrhenius`` selects the number of
        segments via AICc model competition (up to 3).
    
    Args:
        measurement_records: 测量记录列表（每项为字典）
        min_points: 最小点数（默认 5；在线 Agent 上下文刷新可使用 3）
        max_segments: （已弃用，保留仅为兼容签名；分段数由 AICc 自动决定）
        temperature_key: 温度字段名（默认 'temperature_K'）
        conductivity_key: 电导率字段名（默认 'conductivity_s_per_cm'）
        rb_key: Rb 字段名（默认 'rb_ohm'）
        success_key: 成功标志字段名（默认 'success'）
    
    Returns:
        dict: Arrhenius 分析结果，包含以下字段
            - success: bool，是否成功
            - n_segments: int，分段数
            - segments: list[dict]，每段的拟合结果
            - has_transition: bool，是否存在相变
            - transition_temps_K: list[float]，转折温度
            - n_points_used: int，使用的点数
            - error: str or None，失败原因
    """
    # 提取和过滤序列
    try:
        temps_K, conductivities = extract_valid_arrhenius_series(
            records=measurement_records,
            temperature_key=temperature_key,
            conductivity_key=conductivity_key,
            rb_key=rb_key,
            success_key=success_key
        )
    except Exception as e:
        return {
            'success': False,
            'n_segments': 0,
            'segments': [],
            'has_transition': False,
            'transition_temps_K': [],
            'n_points_used': 0,
            'error': f'Series extraction failed: {str(e)}'
        }
    
    # 检查点数
    if len(temps_K) < min_points:
        return {
            'success': False,
            'n_segments': 0,
            'segments': [],
            'has_transition': False,
            'transition_temps_K': [],
            'n_points_used': len(temps_K),
            'error': f'Insufficient valid points ({len(temps_K)} < {min_points})'
        }
    
    # 执行 Arrhenius 分析（让 AICc 数学自动处理小样本）
    # Tier1 fix (2026-06-01): the canonical analyzer signature is
    #   analyze_arrhenius(x_data, y_data, min_segment_points, aic_improvement_threshold)
    # with x_data = 1000/T and y_data = ln(sigma). The previous call passed
    # ``temperatures=`` / ``conductivities=`` / ``max_segments=`` keyword args
    # that do NOT exist on that signature, so every call raised TypeError and was
    # silently swallowed by the except below (the function always returned
    # success=False). Build the correct arrays and pass the correct keywords.
    try:
        x_data = np.array([1000.0 / T for T in temps_K])
        y_data = np.log(np.array(conductivities, dtype=float))
        arrhenius_result = analyze_arrhenius(
            x_data,
            y_data,
            min_segment_points=min_points,
        )
    except Exception as e:
        return {
            'success': False,
            'n_segments': 0,
            'segments': [],
            'has_transition': False,
            'transition_temps_K': [],
            'n_points_used': len(temps_K),
            'error': f'Arrhenius analysis failed: {str(e)}'
        }
    
    # 添加使用点数
    if arrhenius_result.get('success', False):
        arrhenius_result['n_points_used'] = len(temps_K)
    
    return arrhenius_result


def extract_valid_arrhenius_series(
    records,
    temperature_key='temperature_K',
    conductivity_key='conductivity_s_per_cm',
    rb_key='rb_ohm',
    success_key='success'
):
    """
    从测量记录序列提取有效的 Arrhenius 数据点（纯函数版）
    
    过滤规则：
    1. 丢弃 success=False 的记录
    2. 必须同时具有温度、Rb、电导率
    3. 物理范围：T > 0，1e-10 < σ < 1 (S/cm)，Rb > 0.5 Ω
    4. 按温度从高到低排序
    5. 沿降温链要求 Rb 非减（抑制反常跳点）
    
    Args:
        records: 测量记录列表
        temperature_key: 温度字段名
        conductivity_key: 电导率字段名
        rb_key: Rb 字段名
        success_key: 成功标志字段名
    
    Returns:
        tuple: (temperatures_K, conductivities_S_per_cm)
    """
    if not records:
        return [], []
    
    # 候选点筛选
    candidates = []
    for r in records:
        # 检查 success 标志
        if success_key in r and r[success_key] is False:
            continue
        
        # 提取字段（支持多种别名）
        temp_K = r.get(temperature_key)
        if temp_K is None:
            temp_K = r.get('temperature_k') or r.get('temp_K') or r.get('temp_k')
        
        rb = r.get(rb_key)
        if rb is None:
            rb = r.get('rb') or r.get('Rb') or r.get('rb_value')
        
        conductivity = r.get(conductivity_key)
        if conductivity is None:
            conductivity = (
                r.get('conductivity_S_per_cm') or 
                r.get('conductivity') or
                r.get('sigma_s_per_cm') or
                r.get('sigma')
            )
        
        # 检查必需字段
        if temp_K is None or rb is None or conductivity is None:
            continue
        
        # 类型转换
        try:
            temp_K = float(temp_K)
            rb = float(rb)
            conductivity = float(conductivity)
        except (TypeError, ValueError):
            continue
        
        # 物理范围检查
        if not (temp_K > 0 and 1e-10 < conductivity < 1.0 and rb > 0.5):
            continue
        
        candidates.append({
            'temperature_K': temp_K,
            'conductivity': conductivity,
            'rb': rb
        })
    
    if not candidates:
        return [], []
    
    # 按温度从高到低排序
    sorted_candidates = sorted(candidates, key=lambda x: x['temperature_K'], reverse=True)
    
    # Rb 非减过滤（沿降温链）
    valid_temps = []
    valid_conductivities = []
    prev_rb = 0.0
    
    for c in sorted_candidates:
        rb = c['rb']
        # 如果 Rb 下降（反常），跳过该点
        if prev_rb > 0 and rb < prev_rb:
            continue
        
        valid_temps.append(c['temperature_K'])
        valid_conductivities.append(c['conductivity'])
        prev_rb = rb
    
    return valid_temps, valid_conductivities


# ============================================================
# 辅助函数：JSON 安全转换
# ============================================================

def make_json_safe(obj):
    """
    将嵌套结构转为 JSON 可序列化（纯函数版）
    
    处理 numpy 标量/数组、bool_ 等特殊类型
    
    Args:
        obj: 任意 Python 对象
    
    Returns:
        JSON 可序列化对象
    """
    if obj is None:
        return None
    
    if isinstance(obj, dict):
        return {str(k): make_json_safe(v) for k, v in obj.items()}
    
    if isinstance(obj, (list, tuple)):
        return [make_json_safe(x) for x in obj]
    
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    
    if isinstance(obj, (np.floating, np.float32, np.float64)):
        return float(obj)
    
    if isinstance(obj, (np.integer, np.int32, np.int64)):
        return int(obj)
    
    if isinstance(obj, np.bool_):
        return bool(obj)
    
    if isinstance(obj, complex):
        return {'real': obj.real, 'imag': obj.imag}
    
    return obj


# ============================================================
# 辅助函数：结果压缩（为了减少传输量）
# ============================================================

def compact_eis_result(full_result, strip_arrays=True):
    """
    压缩 EIS 分析结果（纯函数版）
    
    保留关键信息，移除大型数组和冗余字段
    
    Args:
        full_result: analyze_eis_point 返回的完整结果
        strip_arrays: 是否移除数组字段（默认 True）
    
    Returns:
        dict: 压缩后的结果，包含以下字段
            - success: bool，整体是否成功
            - temperature_C: float，温度 (°C)
            - temperature_K: float，温度 (K)
            - error: str or None，错误信息
            - rb: dict，压缩的 Rb 结果
            - quality: dict，压缩的质量结果
            - kk: dict，压缩的 KK 结果
            - drt: dict，压缩的 DRT 结果（可选）
            - phase_score: dict，压缩的相变分数（可选）
    """
    compact = {
        'success': full_result.get('success', False),
        'temperature_C': full_result.get('temperature_C'),
        'temperature_K': full_result.get('temperature_K'),
        'error': full_result.get('error')
    }
    
    # Rb 结果压缩
    rb_result = full_result.get('rb_result', {})
    if rb_result:
        compact['rb'] = {
            'success': rb_result.get('success', False),
            'rb_ohm': rb_result.get('rb_ohm'),
            'conductivity_s_per_cm': rb_result.get('conductivity_s_per_cm'),
            'method': rb_result.get('method'),
            'fit_quality': rb_result.get('fit_quality'),
            'error': rb_result.get('error')
        }
    
    # 质量结果压缩
    quality_result = full_result.get('quality_result', {})
    if quality_result:
        compact['quality'] = {
            'valid': quality_result.get('valid', False),
            'score': quality_result.get('quality_score', 0.0),
            'grade': quality_result.get('grade', 'F')
        }
    
    # KK 结果压缩
    kk_result = full_result.get('kk_result', {})
    if kk_result:
        compact['kk'] = {
            'passed': kk_result.get('passed', False),
            'score': kk_result.get('score', 0.0)
        }
    
    # DRT 结果压缩
    drt_result = full_result.get('drt_result', {})
    if drt_result:
        peaks = drt_result.get('peaks', [])
        compact['drt'] = {
            'success': drt_result.get('success', False),
            'n_peaks': len(peaks),
            'peaks': peaks[:5] if not strip_arrays else []  # 最多保留前5个峰
        }
    
    # 相变分数压缩
    phase_score = full_result.get('phase_score_result', {})
    if phase_score:
        compact['phase_score'] = {
            'is_phase_transition': phase_score.get('is_phase_transition', False),
            'phase_jump_score': phase_score.get('phase_jump_score', 0.0),
            'method_change_score': phase_score.get('method_change_score', 0.0)
        }
    
    return compact


def compact_arrhenius_result(full_result):
    """
    压缩 Arrhenius 分析结果（纯函数版）
    
    Args:
        full_result: analyze_arrhenius_series 返回的完整结果
    
    Returns:
        dict: 压缩后的结果
    """
    if not full_result or not full_result.get('success', False):
        return {
            'success': False,
            'n_segments': 0,
            'error': full_result.get('error') if full_result else 'No result'
        }
    
    segments = full_result.get('segments', [])
    segments_preview = []
    
    for seg in segments[:3]:  # 最多保留前3段
        segments_preview.append({
            'segment': seg.get('segment'),
            'ea_eV': seg.get('ea_eV'),
            'ea_kJ_per_mol': seg.get('ea_kJ_per_mol'),
            'temp_range_K': seg.get('temp_range_K'),
            'n_points': seg.get('n_points'),
            'r_squared': seg.get('r_squared'),
            'quality': seg.get('quality')
        })
    
    return {
        'success': True,
        'n_segments': full_result.get('n_segments', 0),
        'has_transition': full_result.get('has_transition', False),
        'transition_temps_K': full_result.get('transition_temps_K', []),
        'n_points_used': full_result.get('n_points_used', 0),
        'segments': segments_preview
    }
