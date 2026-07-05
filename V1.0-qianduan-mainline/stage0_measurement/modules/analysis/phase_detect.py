#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
智能实验决策 Agent（基于 Rb 增长监测，OpenRouter / OpenAI SDK 兼容）

这是一个基于大模型的智能决策引擎，核心基于 Rb 的直接监测。

核心原理：
- 单相态下，Rb 应该平滑指数增长（Arrhenius 定律）
- 相变发生时，Rb 会出现突跳或增长异常加速
- 通过监测 Rb 的单步跳跃和累积增长率，实时检测相变

检测方法（按优先级）：
1. 主力方法 1：Rb 单步跳跃（检测突变型相变）
2. 主力方法 2：Rb 累积增长率（检测渐进型相变）
3. 辅助方法：残差突变（使用滑动基线，可选）

设计原则：
1. 纯函数化 - 所有函数只接受参数输入，返回计算结果
2. 冷启动保护 - < 5 点时跳过 LLM 调用
3. 特征预计算 - 替 LLM 算好数学，减少幻觉
4. 硬编码护栏 - LLM 决策后施加安全约束
5. 异常兜底 - API 失败时返回安全默认值

版本：6.0.0 (Rb 增长监测版)
"""

import os
import json
import hashlib
from pathlib import Path
import numpy as np
from typing import Dict, Any, Optional, List
from openai import OpenAI


# ============================================================
# 默认配置
# ============================================================

# 默认走 OpenRouter（与 Stage1 / Stage3 统一）。可用 env 覆盖：
#   PHASE_DETECT_BASE_URL / LLM_BASE_URL  -> 端点
#   PHASE_DETECT_MODEL                    -> 模型（本步独立固定为 gpt-5.2）
DEFAULT_BASE_URL = os.environ.get(
    "PHASE_DETECT_BASE_URL",
    os.environ.get("LLM_BASE_URL", "https://openrouter.ai/api/v1"),
)
DEFAULT_MODEL = os.environ.get("PHASE_DETECT_MODEL", "openai/gpt-5.2")
DEFAULT_TEMPERATURE = 0.3
DEFAULT_MAX_TOKENS = 1500

# API key must be supplied by argument, or LLM_API_KEY / POLOAPI_KEY env var.
POLOAPI_KEY_IN_CODE: Optional[str] = None


_PROMPT_PATH = Path(__file__).parent / "prompts" / "phase_detect_system.md"


def get_system_prompt() -> str:
    """Load the phase-detection system prompt from disk."""
    return _PROMPT_PATH.read_text(encoding="utf-8")


def get_system_prompt_sha256() -> str:
    """Return the prompt file sha256 for run manifests."""
    return hashlib.sha256(_PROMPT_PATH.read_bytes()).hexdigest()


# ============================================================
# System Prompt
# ============================================================
# The phase-detection system prompt is maintained ONLY in
#   prompts/phase_detect_system.md
# and is loaded at call time via get_system_prompt() (and hashed for run
# manifests via get_system_prompt_sha256()).
#
# Tier1 cleanup (2026-06-01): the previous in-code ``SYSTEM_PROMPT`` string
# constant was removed. It was never referenced anywhere (the live LLM call
# uses get_system_prompt()), and keeping a second copy created a prompt-drift
# risk between code and the canonical .md file. See
#   stage0_measurement/archive/20260601_tier1_cleanup/MANIFEST.md
# for the archived pre-removal snapshot.


# ============================================================
# 辅助函数：Rb 单步跳跃分析
# ============================================================

def _analyze_rb_jump(rb_values: List[float], window_size: int = 5, threshold: float = 1.5) -> Dict[str, Any]:
    """
    分析 Rb 的单步跳跃（主力检测方法 1）
    
    Args:
        rb_values: Rb 序列
        window_size: 监测窗口大小（最近 N 步）
        threshold: 突跳阈值（默认 1.5x）
    
    Returns:
        dict: {
            'recent_ratios': 最近 N 步的增长比列表,
            'max_ratio': 最大单步增长比,
            'max_ratio_index': 最大增长发生的位置,
            'avg_ratio': 平均单步增长比,
            'std_ratio': 标准差,
            'has_jump': 是否检测到突跳,
            'threshold': 阈值
        }
    """
    if len(rb_values) < 2:
        return {
            'recent_ratios': [],
            'max_ratio': 1.0,
            'max_ratio_index': -1,
            'avg_ratio': 1.0,
            'std_ratio': 0.0,
            'has_jump': False,
            'threshold': threshold
        }
    
    # 计算所有单步增长比
    all_ratios = []
    for i in range(len(rb_values) - 1):
        if rb_values[i] > 0:
            ratio = rb_values[i + 1] / rb_values[i]
            all_ratios.append(ratio)
        else:
            all_ratios.append(1.0)
    
    # 提取最近 N 步
    recent_ratios = all_ratios[-window_size:] if len(all_ratios) >= window_size else all_ratios
    
    # 统计
    max_ratio = max(recent_ratios) if recent_ratios else 1.0
    max_ratio_index = len(rb_values) - len(recent_ratios) + recent_ratios.index(max_ratio) if recent_ratios else -1
    avg_ratio = float(np.mean(recent_ratios)) if recent_ratios else 1.0
    std_ratio = float(np.std(recent_ratios)) if recent_ratios else 0.0
    has_jump = max_ratio > threshold
    
    return {
        'recent_ratios': [round(r, 4) for r in recent_ratios],
        'max_ratio': round(max_ratio, 4),
        'max_ratio_index': max_ratio_index,
        'avg_ratio': round(avg_ratio, 4),
        'std_ratio': round(std_ratio, 4),
        'has_jump': has_jump,
        'threshold': threshold
    }


# ============================================================
# 辅助函数：Rb 累积增长分析
# ============================================================

def _analyze_rb_cumulative_growth(
    rb_values: List[float], 
    recent_window: int = 5, 
    threshold: float = 1.5
) -> Dict[str, Any]:
    """
    分析 Rb 的累积增长率（主力检测方法 2）
    
    Args:
        rb_values: Rb 序列
        recent_window: 监测窗口大小
        threshold: 加速阈值（实际/预期）
    
    Returns:
        dict: {
            'baseline_avg_ratio': 基线平均增长比,
            'recent_window_size': 监测窗口大小,
            'cumulative_ratio': 累积增长比,
            'expected_ratio': 基于基线的预期增长,
            'growth_deviation': 实际/预期,
            'has_acceleration': 是否检测到增长加速,
            'threshold': 阈值
        }
    """
    if len(rb_values) < recent_window + 2:
        return {
            'baseline_avg_ratio': 1.0,
            'recent_window_size': recent_window,
            'cumulative_ratio': 1.0,
            'expected_ratio': 1.0,
            'growth_deviation': 1.0,
            'has_acceleration': False,
            'threshold': threshold
        }
    
    # 计算基线平均增长比（前 1/3 的数据，至少 3 个点）
    baseline_n = max(3, len(rb_values) // 3)
    baseline_data = rb_values[:baseline_n]
    
    # 几何平均增长比
    if baseline_data[0] > 0:
        baseline_avg_ratio = (baseline_data[-1] / baseline_data[0]) ** (1 / (baseline_n - 1))
    else:
        baseline_avg_ratio = 1.0
    
    # 计算最近 N 步的累积增长
    if len(rb_values) > recent_window and rb_values[-recent_window - 1] > 0:
        cumulative_ratio = rb_values[-1] / rb_values[-recent_window - 1]
    else:
        cumulative_ratio = 1.0
    
    # 基于基线的预期增长
    expected_ratio = baseline_avg_ratio ** recent_window
    
    # 实际 vs 预期
    if expected_ratio > 0:
        growth_deviation = cumulative_ratio / expected_ratio
    else:
        growth_deviation = 1.0
    
    has_acceleration = growth_deviation > threshold
    
    return {
        'baseline_avg_ratio': round(baseline_avg_ratio, 4),
        'recent_window_size': recent_window,
        'cumulative_ratio': round(cumulative_ratio, 4),
        'expected_ratio': round(expected_ratio, 4),
        'growth_deviation': round(growth_deviation, 4),
        'has_acceleration': has_acceleration,
        'threshold': threshold
    }


# ============================================================
# 辅助函数：残差分析（辅助方法，使用滑动基线）
# ============================================================

def _analyze_residual_deviation(
    temps_K: List[float],
    rb_values: List[float],
    sliding_window: int = 6,
    recent_n: int = 5,
    threshold_sigma: float = 2.5
) -> Dict[str, Any]:
    """
    残差分析（辅助检测方法，使用滑动基线）
    
    Args:
        temps_K: 温度序列（K）
        rb_values: Rb 序列
        sliding_window: 滑动基线窗口大小
        recent_n: 最近 N 个点的残差
        threshold_sigma: 残差阈值（sigma 倍数）
    
    Returns:
        dict: 残差分析结果
    """
    # 点数不足时，不启用残差分析
    if len(rb_values) < sliding_window + recent_n:
        return {
            'enabled': False,
            'reason': f'Insufficient points ({len(rb_values)} < {sliding_window + recent_n})'
        }
    
    try:
        # 计算 log10(Rb) 和 1000/T
        inv_T = [1000.0 / T for T in temps_K]
        log10_rb = [np.log10(rb) for rb in rb_values]
        
        # 使用滑动基线（倒数第 sliding_window 到倒数第 recent_n 之间的点）
        baseline_start = -(sliding_window + recent_n)
        baseline_end = -recent_n if recent_n > 0 else None
        
        baseline_inv_T = inv_T[baseline_start:baseline_end]
        baseline_log10_rb = log10_rb[baseline_start:baseline_end]
        
        # 线性拟合
        from scipy.stats import linregress
        slope, intercept, _, _, _ = linregress(baseline_inv_T, baseline_log10_rb)
        
        # 计算基线残差标准差
        baseline_residuals = [
            log10_rb[i] - (slope * inv_T[i] + intercept)
            for i in range(len(log10_rb) - sliding_window - recent_n, len(log10_rb) - recent_n)
        ]
        baseline_std = float(np.std(baseline_residuals))
        
        # 计算最近 N 个点的残差
        recent_residuals = [
            log10_rb[i] - (slope * inv_T[i] + intercept)
            for i in range(-recent_n, 0)
        ]
        
        max_residual = max(abs(r) for r in recent_residuals)
        threshold = threshold_sigma * baseline_std
        has_deviation = max_residual > threshold
        
        # 检查持续趋势（连续 3 点同向偏离）
        has_trend = False
        if len(recent_residuals) >= 3:
            last_3 = recent_residuals[-3:]
            if all(r > baseline_std for r in last_3) or all(r < -baseline_std for r in last_3):
                has_trend = True
        
        return {
            'enabled': True,
            'sliding_window_size': sliding_window,
            'baseline_slope': round(slope, 4),
            'recent_residuals': [round(r, 4) for r in recent_residuals],
            'max_residual': round(max_residual, 4),
            'baseline_std': round(baseline_std, 4),
            'threshold': round(threshold, 4),
            'has_deviation': has_deviation,
            'has_trend': has_trend
        }
    
    except Exception as e:
        return {
            'enabled': False,
            'reason': f'Calculation error: {str(e)}'
        }


# ============================================================
# 辅助函数：特征预计算
# ============================================================

def _prepare_agent_context(measurement_history: List[Any]) -> Dict[str, Any]:
    """
    准备 Agent 上下文（预计算特征）
    
    Args:
        measurement_history: 测量历史记录列表
    
    Returns:
        dict: Agent 上下文
    """
    # 1. 冷启动保护
    if len(measurement_history) < 5:
        return {
            'status': 'burn_in',
            'n_points': len(measurement_history),
            'message': '数据积累期，点数不足（< 5）'
        }
    
    # 2. 提取全量数据
    full_data = []
    temps_K = []
    rb_values = []
    
    for i, rec in enumerate(measurement_history):
        if not hasattr(rec, 'success') or not rec.success:
            continue
        
        if not hasattr(rec, 'rb_ohm') or not hasattr(rec, 'temperature_K'):
            continue
        
        if rec.rb_ohm is None or rec.temperature_K is None:
            continue
        
        if rec.rb_ohm <= 0 or rec.temperature_K <= 0:
            continue
        
        try:
            full_data.append({
                'index': i,
                'T_K': float(rec.temperature_K),
                'T_C': float(rec.temperature_K - 273.15),
                'Rb': float(rec.rb_ohm),
                'log10_Rb': float(np.log10(rec.rb_ohm)),
                'quality': float(rec.fit_quality) if hasattr(rec, 'fit_quality') and rec.fit_quality is not None else 1.0,
                'kk_warning': bool(rec.kk_warning) if hasattr(rec, 'kk_warning') else False
            })
            temps_K.append(float(rec.temperature_K))
            rb_values.append(float(rec.rb_ohm))
        except (ValueError, TypeError, AttributeError):
            continue
    
    if len(full_data) < 5:
        return {
            'status': 'insufficient_data',
            'n_points': len(full_data),
            'message': f'有效数据点不足（{len(full_data)} < 5）'
        }
    
    # 3. 主力检测 1：Rb 单步跳跃
    rb_jump_analysis = _analyze_rb_jump(rb_values, window_size=5, threshold=1.5)
    
    # 4. 主力检测 2：Rb 累积增长
    rb_cumulative_growth = _analyze_rb_cumulative_growth(rb_values, recent_window=5, threshold=1.5)
    
    # 5. 辅助检测：残差分析（滑动基线）
    # 注意：提高阈值到 3.0σ，避免被 Arrhenius 曲率误导
    residual_analysis = _analyze_residual_deviation(
        temps_K, rb_values, 
        sliding_window=6, 
        recent_n=5, 
        threshold_sigma=3.0
    )
    
    # 6. 统计质量警告
    recent_data = full_data[-5:]
    quality_warnings = sum(1 for p in recent_data if p.get('kk_warning'))
    
    # 7. 当前温度
    current_temperature_K = full_data[-1]['T_K']
    
    # 8. 生成检测摘要
    primary_signals = []
    if rb_jump_analysis['has_jump']:
        primary_signals.append('jump')
    if rb_cumulative_growth['has_acceleration']:
        primary_signals.append('acceleration')
    if not primary_signals:
        primary_signals.append('none')
    
    auxiliary_signals = []
    if residual_analysis.get('enabled') and residual_analysis.get('has_deviation'):
        auxiliary_signals.append('residual')
    if residual_analysis.get('enabled') and residual_analysis.get('has_trend'):
        auxiliary_signals.append('trend')
    if not auxiliary_signals:
        auxiliary_signals.append('none')
    
    # 置信度评估
    strong_signal_count = len([s for s in primary_signals if s != 'none'])
    medium_signal_count = 0
    
    # 中等信号计数（注意：残差信号的权重降低）
    if rb_jump_analysis['max_ratio'] > 1.3:
        medium_signal_count += 1
    if rb_cumulative_growth['growth_deviation'] > 1.3:
        medium_signal_count += 1
    if quality_warnings >= 3:
        medium_signal_count += 1
    
    # 残差信号只作为辅助（需要配合其他信号）
    residual_signal = 'residual' in auxiliary_signals or 'trend' in auxiliary_signals
    
    # 置信度等级（优化判断逻辑）
    if strong_signal_count >= 1:
        # 强信号：立即触发
        confidence = 'high'
        recommendation = 'FINE_GRAINED_SCAN'
    elif medium_signal_count >= 2:
        # 至少 2 个 Rb 相关的中等信号
        confidence = 'medium'
        recommendation = 'FINE_GRAINED_SCAN'
    elif medium_signal_count == 1 and residual_signal:
        # 1 个 Rb 信号 + 残差信号
        confidence = 'medium'
        recommendation = 'FINE_GRAINED_SCAN'
    elif medium_signal_count == 1:
        # 仅 1 个中等信号，不足以触发
        confidence = 'low'
        recommendation = 'CONTINUE'
    elif residual_signal and quality_warnings >= 2:
        # 残差 + 数据质量下降
        confidence = 'low'
        recommendation = 'CONTINUE'
    else:
        # 无明显信号
        confidence = 'low'
        recommendation = 'CONTINUE'
    
    detection_summary = {
        'primary_signals': primary_signals,
        'auxiliary_signals': auxiliary_signals,
        'confidence': confidence,
        'recommendation': recommendation
    }
    
    return {
        'status': 'ready',
        'n_points': len(full_data),
        'full_data': full_data,
        'rb_jump_analysis': rb_jump_analysis,
        'rb_cumulative_growth': rb_cumulative_growth,
        'residual_analysis': residual_analysis,
        'quality_warnings': quality_warnings,
        'current_temperature_K': current_temperature_K,
        'detection_summary': detection_summary
    }


# ============================================================
# 辅助函数：安全默认响应
# ============================================================

def _safe_default_response(
    reasoning: str = "系统默认响应",
    action: str = "CONTINUE",
    error: Optional[str] = None,
    current_temp_K: Optional[float] = None
) -> Dict[str, Any]:
    """
    返回安全的默认响应（API 失败或异常时）
    """
    next_temp = None
    if current_temp_K is not None:
        next_temp = float(current_temp_K) - 3.0
    
    return {
        'success': True,
        'reasoning': reasoning,
        'data_quality': 'GOOD',
        'action': action,
        'action_params': {
            'next_temp_target_K': next_temp,
            'step_size_K': 3.0 if action == 'CONTINUE' else 1.0
        },
        'confidence': 1.0 if action == 'CONTINUE' else 0.5,
        'warnings': [error] if error else [],
        'error': error,
        # 诚实标记:此路径为规则回退,LLM 未被(成功)调用。
        # 修复历史误报:hardware_adapter 曾以"有 api_key"兜底推断 llm_called=true。
        'llm_called': False,
    }


# ============================================================
# 辅助函数：硬编码安全护栏
# ============================================================

def _apply_safety_rails(decision: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    应用硬编码安全护栏（在 LLM 决策后）
    """
    action = decision.get('action', 'CONTINUE')
    
    if action == 'FINE_GRAINED_SCAN':
        current_T = context.get('current_temperature_K')
        next_T = decision.get('action_params', {}).get('next_temp_target_K')
        
        if current_T is not None and next_T is not None:
            temp_change = next_T - current_T
            
            # 硬性约束：最多回温 15K
            MAX_REHEAT = 15.0
            if temp_change > MAX_REHEAT:
                original_next = next_T
                next_T = current_T + MAX_REHEAT
                decision['action_params']['next_temp_target_K'] = next_T
                decision['warnings'] = decision.get('warnings', [])
                decision['warnings'].append(
                    f"回温幅度限制：{original_next:.1f}K → {next_T:.1f}K（最大 +{MAX_REHEAT}K）"
                )
            
            # 禁止降温（FINE_GRAINED_SCAN 应该回温）
            if temp_change < -10.0:
                next_T = current_T + 5.0
                decision['action_params']['next_temp_target_K'] = next_T
                decision['warnings'] = decision.get('warnings', [])
                decision['warnings'].append(
                    f"FINE_GRAINED_SCAN 应该回温，自动修正为 +5K"
                )
    
    return decision


# ============================================================
# 辅助函数：构建决策用户消息（注入 R²-Memory + C³ 收敛证书）
# ============================================================

def _json_default(o: Any):
    """json.dumps 兜底:numpy 布尔/整型/浮点/数组 → 原生类型。

    residual_analysis 等信号自 n_points≥11 起会携带 numpy 标量(np.bool_ 等),
    直接 dumps 会抛 'Object of type bool_ is not JSON serializable' →
    LLM 调用被跳过、静默回落规则决策(fe4b 真机长跑步 10+ 实际踩中)。
    """
    try:
        import numpy as np
        if isinstance(o, np.bool_):
            return bool(o)
        if isinstance(o, np.integer):
            return int(o)
        if isinstance(o, np.floating):
            return float(o)
        if isinstance(o, np.ndarray):
            return o.tolist()
    except ImportError:
        pass
    return str(o)


def build_decision_user_message(
    context: Dict[str, Any],
    memory_projection: Optional[Dict[str, Any]] = None,
    convergence: Optional[Dict[str, Any]] = None,
) -> str:
    """构建发给 LLM 的用户消息。

    除 Rb 信号外,**注入两块经治理的 agent 上下文**(这正是"把 agent 大脑接进
    闭环"的关键:LLM 不再只看裸 Rb,而是带着治理过的记忆 + 收敛证据做判断):

      - ``memory_projection``: R²-Memory 角色投影(本域记忆 + 外域只读参照)。
        外域参照 ``usable_as_training_label=False`` —— LLM 可参考,但绝不可当本域标签。
      - ``convergence``: C³-Harness 收敛证书快照(计量不确定度 / 复现地板 / 推荐动作)。
        用于让 LLM 在"是否还要继续/补测"上对齐治理层,而非只看 Rb 曲线形状。
    """
    user_message_data = {
        'status': context['status'],
        'n_points': context['n_points'],
        'rb_jump_analysis': context['rb_jump_analysis'],
        'rb_cumulative_growth': context['rb_cumulative_growth'],
        'residual_analysis': context['residual_analysis'],
        'quality_warnings': context['quality_warnings'],
        'current_temperature_K': context['current_temperature_K'],
        'detection_summary': context['detection_summary'],
    }

    parts: List[str] = ["请分析以下实验数据并给出决策：", ""]
    parts.append("## Rb 相变信号")
    parts.append(json.dumps(user_message_data, indent=2, ensure_ascii=False,
                            default=_json_default))

    if memory_projection:
        parts.append("")
        parts.append(
            "## 治理记忆（R²-Memory，经写门/用途门/来源域守卫的角色投影）\n"
            "- in_domain_recent 为本域可作决策上下文的测量记忆。\n"
            "- cross_domain_refs 为外域迁移参照：仅作只读启发，"
            "usable_as_training_label=False 表示治理层禁止其成为本域标签，"
            "你也不得据其直接对本域下结论。"
        )
        parts.append(json.dumps(memory_projection, indent=2, ensure_ascii=False,
                                default=_json_default))

    if convergence:
        parts.append("")
        parts.append(
            "## 收敛证据（C³-Harness shadow 证书快照）\n"
            "- recommended_action / delta_vs_legacy 为治理层对“停止 vs 继续”的裁决。\n"
            "- 若复现地板未满（reproducibility have<required）或计量不确定度偏高，"
            "即便 Rb 看似平滑，也不应过早判定收敛；据此校准你的 confidence。"
        )
        parts.append(json.dumps(convergence, indent=2, ensure_ascii=False,
                                default=_json_default))

    parts.append("")
    parts.append("请严格按照 JSON 格式输出决策结果。")
    return "\n".join(parts)


# ============================================================
# 主函数：智能决策 Agent
# ============================================================

def analyze_experiment_state(
    agent_context: Dict[str, Any],
    api_key: Optional[str] = None,
    base_url: str = DEFAULT_BASE_URL,
    model: str = DEFAULT_MODEL,
    temperature: float = DEFAULT_TEMPERATURE,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    use_hardcoded_triggers: bool = True,
) -> Dict[str, Any]:
    """
    基于 Rb 增长监测的智能实验决策
    
    核心原理：
    - 主力方法 1：Rb 单步跳跃（> 1.5x → 相变）
    - 主力方法 2：Rb 累积增长（实际/预期 > 1.5x → 相变）
    - 辅助方法：残差突变（使用滑动基线，可选）
    
    Args:
        agent_context: {'measurement_history': [...]}
        api_key: PoloAPI Key
        base_url: API Base URL
        model: 模型名称
        temperature: 温度参数
        max_tokens: 最大 token 数
    
    Returns:
        dict: 决策结果
    
    版本：6.0.0
    """
    # ===== 步骤 1: 兼容性处理 =====
    measurement_history = None
    
    if 'measurement_history' in agent_context:
        measurement_history = agent_context.get('measurement_history', [])
    elif 'history_trend' in agent_context:
        return _safe_default_response(
            reasoning="旧格式 agent_context 需要适配",
            error="请使用新格式 agent_context 或提供 measurement_history",
            action='CONTINUE'
        )
    else:
        return _safe_default_response(
            reasoning="agent_context 格式错误",
            error="Missing measurement_history",
            action='CONTINUE'
        )
    
    if not measurement_history:
        return _safe_default_response(
            reasoning="无测量历史数据",
            error="measurement_history is empty"
        )
    
    # ===== 步骤 2: 预计算特征 =====
    context = _prepare_agent_context(measurement_history)
    
    # ===== 步骤 3: 冷启动保护 =====
    if context['status'] == 'burn_in':
        return _safe_default_response(
            reasoning=f"数据积累期（{context['n_points']}/5 点），继续粗扫",
            action='CONTINUE',
            current_temp_K=measurement_history[-1].temperature_K if measurement_history else None
        )
    
    if context['status'] == 'insufficient_data':
        return _safe_default_response(
            reasoning=f"有效数据点不足（{context['n_points']}/5 点）",
            action='CONTINUE',
            current_temp_K=measurement_history[-1].temperature_K if measurement_history else None
        )
    
    # ===== 步骤 4: 硬编码预判（强信号直接触发，不调用 LLM）=====
    summary = context['detection_summary']

    # 用户要求：规则 1（Rb 突跳）/ 规则 2（累积增长加速）容易误触，
    # 在 web 在线闭环里关掉它们，把 Rb_jump + cumulative_growth + residual
    # 三路信号一起交给 LLM 综合判断。use_hardcoded_triggers=False 时跳过。
    if use_hardcoded_triggers and context['rb_jump_analysis']['has_jump']:
        max_ratio = context['rb_jump_analysis']['max_ratio']
        max_idx = context['rb_jump_analysis']['max_ratio_index']
        
        return {
            'success': True,
            'reasoning': f"Rb 单步跳跃 {max_ratio:.2f}x（索引 {max_idx}），疑似相变",
            'data_quality': 'GOOD',
            'action': 'FINE_GRAINED_SCAN',
            'action_params': {
                'next_temp_target_K': context['current_temperature_K'] + 5.0,
                'step_size_K': 1.0
            },
            'confidence': 0.9,
            'warnings': ['Rb 突跳检测，建议密集扫描'],
            'error': None
        }
    
    if use_hardcoded_triggers and context['rb_cumulative_growth']['has_acceleration']:
        deviation = context['rb_cumulative_growth']['growth_deviation']
        
        return {
            'success': True,
            'reasoning': f"累积增长加速 {deviation:.2f}x 预期值，疑似渐进相变",
            'data_quality': 'GOOD' if context['quality_warnings'] < 2 else 'POOR',
            'action': 'FINE_GRAINED_SCAN',
            'action_params': {
                'next_temp_target_K': context['current_temperature_K'] + 5.0,
                'step_size_K': 1.0
            },
            'confidence': 0.85,
            'warnings': ['累积增长异常，建议密集扫描'],
            'error': None
        }
    
    # ===== 步骤 5: API Key 获取 =====
    if api_key is None:
        # 统一到 OpenRouter：优先 LLM_API_KEY（与 Stage1/Stage3 同一把 OpenRouter key），
        # 回退 POLOAPI_KEY 以兼容旧环境。
        api_key = os.environ.get('LLM_API_KEY') or os.environ.get('POLOAPI_KEY')
    
    if not api_key:
        # 无 API key 时，使用硬编码逻辑
        if use_hardcoded_triggers and summary['recommendation'] == 'FINE_GRAINED_SCAN':
            return {
                'success': True,
                'reasoning': f"检测到中等信号（{summary['confidence']} 置信度），建议细扫",
                'data_quality': 'GOOD',
                'action': 'FINE_GRAINED_SCAN',
                'action_params': {
                    'next_temp_target_K': context['current_temperature_K'] + 5.0,
                    'step_size_K': 1.0
                },
                'confidence': 0.7,
                'warnings': [],
                'error': None
            }
        else:
            return _safe_default_response(
                reasoning="无明显相变信号，继续粗扫",
                action='CONTINUE',
                current_temp_K=context.get('current_temperature_K')
            )
    
    # ===== 步骤 6: 构建用户消息（注入治理记忆 + 收敛证书）=====
    try:
        # 精简数据（只发送摘要，不发送完整 full_data）+ R²-Memory / C³ 上下文。
        user_message = build_decision_user_message(
            context,
            memory_projection=agent_context.get('memory_projection'),
            convergence=agent_context.get('convergence'),
        )
    
    except Exception as e:
        return _safe_default_response(
            reasoning="数据序列化失败",
            error=f"Failed to serialize data: {str(e)}",
            action='CONTINUE',
            current_temp_K=context.get('current_temperature_K')
        )
    
    # ===== 步骤 7: 调用 LLM =====
    try:
        client = OpenAI(api_key=api_key, base_url=base_url)
        
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": get_system_prompt()},
                {"role": "user", "content": user_message}
            ],
            temperature=temperature,
            max_tokens=max_tokens
        )
        
        raw_response = response.choices[0].message.content.strip()
        
        # 去除可能的 Markdown 代码块标记
        if raw_response.startswith('```'):
            lines = raw_response.split('\n')
            if lines[0].startswith('```'):
                lines = lines[1:]
            if lines and lines[-1].startswith('```'):
                lines = lines[:-1]
            raw_response = '\n'.join(lines).strip()
        
        # 解析 JSON
        decision = json.loads(raw_response)
        decision['success'] = True
        decision['error'] = None
        decision['llm_called'] = True  # 只有真实走到这里(LLM 返回并解析成功)才为 True
        
    except json.JSONDecodeError as e:
        return _safe_default_response(
            reasoning="LLM 返回格式错误",
            error=f"JSON decode error: {str(e)}",
            action='CONTINUE',
            current_temp_K=context.get('current_temperature_K')
        )
    
    except Exception as e:
        return _safe_default_response(
            reasoning="API 调用失败",
            error=f"API error: {str(e)}",
            action='CONTINUE',
            current_temp_K=context.get('current_temperature_K')
        )
    
    # ===== 步骤 8: 应用硬编码安全护栏 =====
    decision = _apply_safety_rails(decision, context)
    
    return decision
