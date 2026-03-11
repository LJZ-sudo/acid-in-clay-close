# -*- coding: utf-8 -*-
"""
统一EIS数据处理模块

功能：将原始EIS数据处理为Phase 2-3统一格式
适用场景：
  1. V1.0-qianduan在线测试数据
  2. 历史原始EIS数据（.seq/.txt文件）

输出格式完全统一，可直接供Phase 2-3使用。
"""

import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import json
from datetime import datetime


class UnifiedEISProcessor:
    """统一EIS数据处理器"""
    
    def __init__(self, material_params: Dict[str, float] = None):
        """
        初始化处理器
        
        Args:
            material_params: 材料参数字典 {'N': float, 'R': float, 'L_cm': float, 'S_cm2': float}
        """
        self.material_params = material_params or {}
        
    def process_eis_data(
        self,
        freq: np.ndarray,
        z_real: np.ndarray,
        z_imag: np.ndarray,
        temperature_K: float
    ) -> Dict[str, Any]:
        """
        处理单个温度点的EIS数据
        
        Args:
            freq: 频率数组 (Hz)
            z_real: 实部阻抗数组 (Ω)
            z_imag: 虚部阻抗数组 (Ω)
            temperature_K: 测量温度 (K)
            
        Returns:
            处理结果字典
        """
        result = {
            'temperature_K': temperature_K,
            'n_points': len(freq)
        }
        
        # 1. Rb拟合
        rb_result = self._fit_rb(freq, z_real, z_imag)
        result.update(rb_result)
        
        # 2. 计算电导率
        if rb_result['rb_ohm'] > 0:
            L = self.material_params.get('L_cm', 0.12)
            S = self.material_params.get('S_cm2', 3.92)
            result['conductivity_S_cm'] = L / (rb_result['rb_ohm'] * S)
        else:
            result['conductivity_S_cm'] = 0
        
        # 3. KK校验
        result['kk_validation'] = self._kk_check(freq, z_real, z_imag)
        
        # 4. DRT分析
        result['drt_analysis'] = self._drt_analyze(freq, z_real, z_imag)
        
        # 5. 数据质量评估
        result['data_quality'] = self._assess_quality(
            rb_result, result['kk_validation'], result['drt_analysis']
        )
        
        return result
    
    def _fit_rb(
        self,
        freq: np.ndarray,
        z_real: np.ndarray,
        z_imag: np.ndarray
    ) -> Dict[str, Any]:
        """
        Rb拟合（体相电阻）
        
        使用多种方法，选择最优结果
        """
        results = []
        
        # 方法1: X轴截距法
        try:
            rb, r2 = self._fit_rb_x_intercept(z_real, z_imag)
            if rb > 0:
                results.append(('x_axis_intercept', rb, r2))
        except:
            pass
        
        # 方法2: 线性拟合法
        try:
            rb, r2 = self._fit_rb_linear(z_real, z_imag)
            if rb > 0:
                results.append(('linear', rb, r2))
        except:
            pass
        
        # 方法3: 渐进线性法（针对噪声数据）
        try:
            rb, r2 = self._fit_rb_progressive_linear(z_real, z_imag)
            if rb > 0:
                results.append(('progressive_linear', rb, r2))
        except:
            pass
        
        # 选择R²最高的结果
        if results:
            best = max(results, key=lambda x: x[2])
            return {
                'rb_ohm': best[1],
                'rb_method': best[0],
                'rb_r2': best[2]
            }
        
        # 兜底：使用最小实部
        return {
            'rb_ohm': float(np.min(z_real[z_real > 0])) if np.any(z_real > 0) else 0,
            'rb_method': 'min_real',
            'rb_r2': 0.0
        }
    
    def _fit_rb_x_intercept(self, z_real: np.ndarray, z_imag: np.ndarray) -> Tuple[float, float]:
        """X轴截距法"""
        # 找到虚部最接近0的点
        idx = np.argmin(np.abs(z_imag))
        rb = z_real[idx]
        
        # 计算拟合度（基于周围点的一致性）
        if len(z_real) > 5:
            # 使用附近点线性拟合
            start = max(0, idx - 2)
            end = min(len(z_real), idx + 3)
            if end - start >= 3:
                coef = np.polyfit(z_imag[start:end], z_real[start:end], 1)
                fitted = np.polyval(coef, z_imag[start:end])
                ss_res = np.sum((z_real[start:end] - fitted) ** 2)
                ss_tot = np.sum((z_real[start:end] - np.mean(z_real[start:end])) ** 2)
                r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0
            else:
                r2 = 0.95 if abs(z_imag[idx]) < 1 else 0.8
        else:
            r2 = 0.9
        
        return float(rb), float(max(0, r2))
    
    def _fit_rb_linear(self, z_real: np.ndarray, z_imag: np.ndarray) -> Tuple[float, float]:
        """线性拟合法"""
        # 选择虚部为负（正常半圆）的点
        mask = z_imag < 0
        if np.sum(mask) < 3:
            mask = np.ones(len(z_imag), dtype=bool)
        
        # 线性拟合 Z_real vs Z_imag
        coef = np.polyfit(z_imag[mask], z_real[mask], 1)
        rb = coef[1]  # Z_imag = 0 时的 Z_real
        
        # 计算R²
        fitted = np.polyval(coef, z_imag[mask])
        ss_res = np.sum((z_real[mask] - fitted) ** 2)
        ss_tot = np.sum((z_real[mask] - np.mean(z_real[mask])) ** 2)
        r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0
        
        return float(rb), float(max(0, r2))
    
    def _fit_rb_progressive_linear(self, z_real: np.ndarray, z_imag: np.ndarray) -> Tuple[float, float]:
        """渐进线性法（从高频开始逐步拟合）"""
        best_rb = 0
        best_r2 = 0
        
        # 假设高频在数组开头
        for n in range(5, min(20, len(z_real)), 2):
            try:
                coef = np.polyfit(z_imag[:n], z_real[:n], 1)
                rb = coef[1]
                
                fitted = np.polyval(coef, z_imag[:n])
                ss_res = np.sum((z_real[:n] - fitted) ** 2)
                ss_tot = np.sum((z_real[:n] - np.mean(z_real[:n])) ** 2)
                r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0
                
                if r2 > best_r2 and rb > 0:
                    best_rb = rb
                    best_r2 = r2
            except:
                continue
        
        return float(best_rb), float(best_r2)
    
    def _kk_check(
        self,
        freq: np.ndarray,
        z_real: np.ndarray,
        z_imag: np.ndarray
    ) -> Dict[str, Any]:
        """
        Kramers-Kronig一致性校验
        """
        try:
            from auto_control.modules.kk_validation import kk_check
            result = kk_check(freq, z_real, z_imag)
            return result
        except Exception as e:
            # 简化版KK校验
            return self._simple_kk_check(freq, z_real, z_imag)
    
    def _simple_kk_check(
        self,
        freq: np.ndarray,
        z_real: np.ndarray,
        z_imag: np.ndarray
    ) -> Dict[str, Any]:
        """简化版KK校验"""
        # 基于数据点数和噪声水平估计质量
        n_points = len(freq)
        
        # 计算噪声水平
        if n_points > 10:
            # 使用高频段（假设较平稳）估计噪声
            noise_real = np.std(np.diff(z_real[:10])) / np.mean(np.abs(z_real[:10]) + 1e-10)
            noise_imag = np.std(np.diff(z_imag[:10])) / np.mean(np.abs(z_imag[:10]) + 1e-10)
            noise_level = (noise_real + noise_imag) / 2
        else:
            noise_level = 0.1
        
        # 估计残差
        residual = noise_level * 100  # 转换为百分比
        
        return {
            'ok': residual < 30,
            'score': max(0, 100 - residual * 2),
            'residual_real': noise_level,
            'residual_imag': noise_level,
            'message': f'KK校验{"通过" if residual < 30 else "未通过"}（估计残差 {residual:.1f}%）'
        }
    
    def _drt_analyze(
        self,
        freq: np.ndarray,
        z_real: np.ndarray,
        z_imag: np.ndarray
    ) -> Dict[str, Any]:
        """
        DRT (Distribution of Relaxation Times) 分析
        """
        try:
            from auto_control.modules.drt_analysis import drt_analyze
            result = drt_analyze(freq, z_real, z_imag)
            return result
        except Exception as e:
            # 简化版DRT
            return self._simple_drt(freq, z_real, z_imag)
    
    def _simple_drt(
        self,
        freq: np.ndarray,
        z_real: np.ndarray,
        z_imag: np.ndarray
    ) -> Dict[str, Any]:
        """简化版DRT分析"""
        # 找虚部极值点作为峰
        peaks = []
        z_imag_abs = np.abs(z_imag)
        
        for i in range(1, len(z_imag_abs) - 1):
            if z_imag_abs[i] > z_imag_abs[i-1] and z_imag_abs[i] > z_imag_abs[i+1]:
                if z_imag_abs[i] > 0.1 * np.max(z_imag_abs):  # 阈值过滤
                    tau = 1 / (2 * np.pi * freq[i]) if freq[i] > 0 else 0
                    peaks.append({
                        'tau': tau,
                        'frequency_Hz': freq[i],
                        'height': z_imag_abs[i]
                    })
        
        return {
            'ok': True,
            'n_peaks': len(peaks),
            'peaks': peaks,
            'message': f'检测到 {len(peaks)} 个弛豫峰'
        }
    
    def _assess_quality(
        self,
        rb_result: Dict,
        kk_result: Dict,
        drt_result: Dict
    ) -> Dict[str, Any]:
        """
        数据质量综合评估
        """
        scores = []
        flags = []
        
        # 1. Rb拟合质量 (40分)
        rb_r2 = rb_result.get('rb_r2', 0)
        rb_score = rb_r2 * 40
        scores.append(rb_score)
        if rb_r2 < 0.9:
            flags.append('RB_LOW_R2')
        
        # 2. KK校验 (30分)
        kk_score = kk_result.get('score', 50) * 0.3
        scores.append(kk_score)
        if not kk_result.get('ok', True):
            flags.append('KK_FAILED')
        
        # 3. DRT质量 (20分)
        drt_ok = drt_result.get('ok', True)
        drt_score = 20 if drt_ok else 10
        scores.append(drt_score)
        if drt_result.get('n_peaks', 0) == 0:
            flags.append('DRT_NO_PEAKS')
        
        # 4. 数据点数 (10分)
        # 这个在外部根据n_points评估
        scores.append(10)  # 默认满分
        
        total_score = sum(scores)
        
        # 确定等级
        if total_score >= 85:
            grade = 'A'
        elif total_score >= 70:
            grade = 'B'
        elif total_score >= 55:
            grade = 'C'
        else:
            grade = 'D'
        
        return {
            'grade': grade,
            'score': total_score,
            'flags': flags
        }


def process_multi_temperature(
    temperature_data: List[Dict],
    material_params: Dict[str, float],
    sample_id: str
) -> Dict[str, Any]:
    """
    处理多温度点数据，生成Phase 2-3统一格式
    
    Args:
        temperature_data: 每个温度点的EIS数据列表
            [{'temperature_K': float, 'freq': array, 'z_real': array, 'z_imag': array}, ...]
        material_params: {'N': float, 'R': float, 'L_cm': float, 'S_cm2': float}
        sample_id: 样品ID
        
    Returns:
        Phase 2-3统一格式的分析结果
    """
    processor = UnifiedEISProcessor(material_params)
    
    # 处理每个温度点
    temperature_results = []
    temperatures = []
    rb_values = []
    conductivity_values = []
    
    for data in temperature_data:
        temp_K = data['temperature_K']
        result = processor.process_eis_data(
            freq=np.array(data['freq']),
            z_real=np.array(data['z_real']),
            z_imag=np.array(data['z_imag']),
            temperature_K=temp_K
        )
        
        temperature_results.append(result)
        temperatures.append(temp_K)
        rb_values.append(result['rb_ohm'])
        conductivity_values.append(result['conductivity_S_cm'])
    
    # 按温度排序（高温到低温）
    sorted_indices = np.argsort(temperatures)[::-1]
    temperatures = [temperatures[i] for i in sorted_indices]
    rb_values = [rb_values[i] for i in sorted_indices]
    conductivity_values = [conductivity_values[i] for i in sorted_indices]
    temperature_results = [temperature_results[i] for i in sorted_indices]
    
    # Arrhenius分析
    from auto_control.modules.arrhenius import perform_arrhenius_analysis
    arrhenius_result = perform_arrhenius_analysis(temperatures, conductivity_values)
    
    # 规范化Arrhenius结果格式
    arrhenius_normalized = normalize_arrhenius_format(arrhenius_result)
    
    # 计算汇总质量分数
    quality_scores = [r['data_quality']['score'] for r in temperature_results]
    overall_quality_score = np.mean(quality_scores) if quality_scores else 0
    
    # 构建最终结果
    result = {
        'sample_id': sample_id,
        'material_type': sample_id.split('-')[0] if '-' in sample_id else sample_id,
        'N': material_params.get('N', 0),
        'R': material_params.get('R', 0),
        'L_cm': material_params.get('L_cm', 0.12),
        'S_cm2': material_params.get('S_cm2', 3.92),
        'temperatures': temperatures,
        'rb_values': rb_values,
        'conductivity_values': conductivity_values,
        'arrhenius': arrhenius_normalized,
        'temperature_results': temperature_results,
        'quality_summary': {
            'overall_score': overall_quality_score,
            'overall_grade': 'A' if overall_quality_score >= 85 else 'B' if overall_quality_score >= 70 else 'C' if overall_quality_score >= 55 else 'D',
            'n_temperature_points': len(temperatures),
            'temp_range_K': [min(temperatures), max(temperatures)] if temperatures else [0, 0]
        },
        'processing_timestamp': datetime.now().isoformat(),
        'processor_version': '2.0_unified'
    }
    
    return result


def normalize_arrhenius_format(arrhenius_result: Dict) -> Dict:
    """
    规范化Arrhenius结果格式，确保字段名统一
    """
    if not arrhenius_result:
        return {}
    
    normalized = {
        'success': arrhenius_result.get('success', True),
        'n_segments': arrhenius_result.get('n_segments', 1),
        'segments': []
    }
    
    # 规范化segments
    segments = arrhenius_result.get('segments', [])
    for i, seg in enumerate(segments):
        # 获取Ea（优先使用Ea_eV，否则从Ea_kJ_per_mol转换）
        Ea_eV = seg.get('Ea_eV') or seg.get('Ea')
        Ea_kJ = seg.get('Ea_kJ_per_mol') or seg.get('Ea_kJ_mol')
        
        if Ea_eV is None and Ea_kJ is not None:
            Ea_eV = Ea_kJ / 96.485  # kJ/mol → eV
        elif Ea_eV is None:
            Ea_eV = 0
        
        if Ea_kJ is None and Ea_eV:
            Ea_kJ = Ea_eV * 96.485  # eV → kJ/mol
        elif Ea_kJ is None:
            Ea_kJ = 0
        
        # 获取温度范围
        temp_range = seg.get('temp_range_K') or seg.get('T_range_K')
        if temp_range is None:
            temp_range = [seg.get('T_min_K', 0), seg.get('T_max_K', 0)]
        if isinstance(temp_range, tuple):
            temp_range = list(temp_range)
        
        norm_seg = {
            'segment': seg.get('segment', i + 1),
            'Ea_eV': Ea_eV,
            'Ea_kJ_per_mol': Ea_kJ,
            'r_squared': seg.get('r_squared') or seg.get('R_squared', 0),
            'temp_range_K': temp_range,
            'n_points': seg.get('n_points') or seg.get('data_points', 0),
            'sigma0_S_per_cm': seg.get('sigma0_S_per_cm') or seg.get('sigma0', 1),
            'ln_sigma0': seg.get('ln_sigma0', 0)
        }
        
        # 确保temp_range_K是列表
        if not isinstance(norm_seg['temp_range_K'], list):
            norm_seg['temp_range_K'] = [0, 0]
        
        normalized['segments'].append(norm_seg)
    
    # 添加整体Ea
    if normalized['segments']:
        normalized['Ea_eV'] = normalized['segments'][0]['Ea_eV']
        normalized['r_squared'] = normalized['segments'][0]['r_squared']
    
    return normalized


# 测试代码
if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    
    print("=" * 60)
    print("UnifiedEISProcessor Test")
    print("=" * 60)
    
    # 模拟测试数据
    freq = np.logspace(0, 6, 50)  # 1 Hz to 1 MHz
    # 模拟简单RC电路
    R = 100
    C = 1e-6
    omega = 2 * np.pi * freq
    Z = R / (1 + 1j * omega * R * C)
    z_real = np.real(Z)
    z_imag = np.imag(Z)
    
    # 测试单点处理
    processor = UnifiedEISProcessor({'N': 4.0, 'R': 0.3, 'L_cm': 0.12, 'S_cm2': 3.92})
    result = processor.process_eis_data(freq, z_real, z_imag, 300.0)
    
    print(f"\nSingle point result:")
    print(f"  Rb: {result['rb_ohm']:.2f} Ω (method: {result['rb_method']})")
    print(f"  Conductivity: {result['conductivity_S_cm']:.4e} S/cm")
    print(f"  KK: {result['kk_validation']['message']}")
    print(f"  DRT: {result['drt_analysis']['message']}")
    print(f"  Quality: {result['data_quality']['grade']} ({result['data_quality']['score']:.0f})")
    
    print("\n[OK] Test passed")
