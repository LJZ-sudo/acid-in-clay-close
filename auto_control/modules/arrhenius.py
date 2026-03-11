# -*- coding: utf-8 -*-
"""
Arrhenius分析模块：从成功点计算电导率，进行Arrhenius拟合
升级版：支持自动分段拟合，识别相变和多机理传输
"""

import os
import sys
import numpy as np
from typing import List, Dict, Tuple, Optional
from scipy import stats

# 常数
R_GAS = 8.314  # J/(mol·K)


def _simple_arrhenius_fit(temps_K: np.ndarray, conductivities: np.ndarray) -> List[Dict]:
    """
    简单的单一线性Arrhenius拟合（内联函数，用于回退）
    """
    if len(temps_K) < 3:
        return []
    
    inv_T = 1.0 / temps_K
    ln_sigma = np.log(conductivities)
    
    slope, intercept, r_value, p_value, std_err = stats.linregress(inv_T, ln_sigma)
    Ea_kJ = -slope * R_GAS / 1000.0
    sigma0 = np.exp(intercept)
    
    return [{
        'segment': 1,
        'Ea': Ea_kJ,
        'sigma0': sigma0,
        'T_range': (float(np.min(temps_K)), float(np.max(temps_K))),
        'points': len(temps_K),
        'r_squared': r_value ** 2
    }]


class AdvancedArrheniusAnalyzer:
    """
    高级Arrhenius分段分析器
    功能：自动拐点检测、多段拟合、统计检验
    """
    
    def __init__(self, 
                 window_size=5,
                 threshold=0.5,
                 min_segment_points=5,
                 max_segments=4,
                 alpha=0.05):
        """
        参数:
            window_size: 滑动窗口大小
            threshold: 拐点检测阈值（相对标准差的倍数）
            min_segment_points: 每段最少数据点
            max_segments: 最多分段数
            alpha: 显著性水平 (F-test)
        """
        self.window_size = window_size
        self.threshold = threshold
        self.min_segment_points = min_segment_points
        self.max_segments = max_segments
        self.alpha = alpha
    
    def detect_breakpoints_sliding_window(self, inv_T, ln_sigma):
        """
        使用滑动窗口检测Arrhenius图中的拐点
        
        返回:
            breakpoints: 拐点索引列表
        """
        n = len(inv_T)
        if n < self.window_size * 2:
            return []
        
        slopes = []
        
        # 计算每个窗口的斜率
        for i in range(n - self.window_size + 1):
            x_window = inv_T[i:i+self.window_size]
            y_window = ln_sigma[i:i+self.window_size]
            try:
                slope, _ = np.polyfit(x_window, y_window, 1)
                slopes.append(slope)
            except:
                slopes.append(0)
        
        slopes = np.array(slopes)
        
        # 计算斜率的一阶差分
        if len(slopes) < 2:
            return []
        
        slope_diff = np.abs(np.diff(slopes))
        
        # 识别显著变化点
        if np.std(slope_diff) == 0:
            return []
        
        threshold_value = self.threshold * np.std(slope_diff)
        breakpoint_candidates = np.where(slope_diff > threshold_value)[0]
        
        # 合并接近的拐点（避免过度分段）
        breakpoints = []
        if len(breakpoint_candidates) > 0:
            current_group = [breakpoint_candidates[0]]
            for bp in breakpoint_candidates[1:]:
                if bp - current_group[-1] < self.window_size:
                    current_group.append(bp)
                else:
                    # 取当前组的中位数作为拐点
                    breakpoints.append(int(np.median(current_group)) + self.window_size // 2)
                    current_group = [bp]
            # 处理最后一组
            breakpoints.append(int(np.median(current_group)) + self.window_size // 2)
        
        return breakpoints
    
    def fit_segments(self, inv_T, ln_sigma, temps_K, breakpoints):
        """
        对指定的分段进行线性拟合
        
        返回:
            segments: 分段拟合结果列表
        """
        segments = []
        
        # 定义分段边界
        boundaries = [0] + breakpoints + [len(inv_T)]
        
        for i in range(len(boundaries) - 1):
            start = boundaries[i]
            end = boundaries[i + 1]
            
            # 提取当前分段数据
            x_seg = inv_T[start:end]
            y_seg = ln_sigma[start:end]
            temps_seg = temps_K[start:end]
            
            if len(x_seg) < 2:
                continue
            
            # 线性拟合
            try:
                slope, intercept, r_value, p_value, std_err = stats.linregress(x_seg, y_seg)
            except:
                continue
            
            # 计算活化能 (kJ/mol)
            # ln(σ) = ln(σ0) - Ea/(R*T)
            # slope = -Ea/R → Ea = -slope * R
            # 注意：slope的单位是 (ln S/cm) / (K⁻¹)
            Ea_kJ = -slope * R_GAS / 1000.0  # 转换为kJ/mol
            
            # 计算指前因子
            sigma0 = np.exp(intercept)
            
            # 计算温度范围
            T_start_K = float(np.min(temps_seg))
            T_end_K = float(np.max(temps_seg))
            
            # 计算残差平方和
            y_pred = slope * x_seg + intercept
            rss = np.sum((y_seg - y_pred) ** 2)
            
            segments.append({
                'segment': i + 1,
                'Ea_kJ_per_mol': Ea_kJ,
                'Ea_error_kJ_per_mol': std_err * R_GAS / 1000.0 if std_err else 0,
                'sigma0_S_per_cm': sigma0,
                'R_squared': r_value ** 2 if r_value is not None else 0,
                'p_value': p_value if p_value is not None else 1,
                'T_range_K': (T_start_K, T_end_K),
                'T_range_C': (T_start_K - 273.15, T_end_K - 273.15),
                'data_points': len(x_seg),
                'RSS': rss,
                'slope': slope,
                'intercept': intercept
            })
        
        return segments
    
    def f_test_segmentation(self, inv_T, ln_sigma, segments_simple, segments_complex):
        """
        使用F-test检验分段是否显著改善拟合
        
        返回:
            f_statistic: F统计量
            p_value: p值
            is_significant: 是否显著改善 (p < alpha)
        """
        n = len(inv_T)
        
        # 简单模型
        k1 = len(segments_simple)
        RSS1 = sum(seg['RSS'] for seg in segments_simple)
        
        # 复杂模型
        k2 = len(segments_complex)
        RSS2 = sum(seg['RSS'] for seg in segments_complex)
        
        # F统计量
        if RSS2 == 0 or k2 == k1 or RSS1 <= RSS2:
            return float('inf'), 0.0, True
        
        try:
            f_statistic = ((RSS1 - RSS2) / (k2 - k1)) / (RSS2 / (n - 2 * k2))
            
            # p值（使用F分布）
            from scipy.stats import f as f_dist
            p_value = 1 - f_dist.cdf(f_statistic, k2 - k1, n - 2 * k2)
            
            is_significant = p_value < self.alpha
            
            return f_statistic, p_value, is_significant
        except:
            return 0, 1.0, False
    
    def calculate_aic_bic(self, inv_T, ln_sigma, segments):
        """
        计算AIC和BIC准则
        
        AIC = 2k + n·ln(RSS/n)
        BIC = k·ln(n) + n·ln(RSS/n)
        """
        n = len(inv_T)
        k = 2 * len(segments)  # 每段有2个参数（斜率和截距）
        RSS = sum(seg['RSS'] for seg in segments)
        
        if RSS == 0 or n <= k:
            return float('inf'), float('inf')
        
        try:
            AIC = 2 * k + n * np.log(RSS / n)
            BIC = k * np.log(n) + n * np.log(RSS / n)
            return AIC, BIC
        except:
            return float('inf'), float('inf')
    
    def validate_breakpoints(self, inv_T, breakpoints):
        """验证拐点是否合理（每段至少有min_segment_points个点）"""
        boundaries = [0] + breakpoints + [len(inv_T)]
        for i in range(len(boundaries) - 1):
            if boundaries[i+1] - boundaries[i] < self.min_segment_points:
                return False
        return True
    
    def analyze(self, temps_K, conductivities):
        """
        执行完整的Arrhenius分段分析
        
        返回:
            result: {
                'optimal_segments': [...],
                'num_segments': int,
                'breakpoints': [...],
                'all_models': [...],
                'f_tests': [...],
                'model_selection': {...}
            }
        """
        try:
            # 1. 数据预处理
            temps_K = np.array(temps_K)
            conductivities = np.array(conductivities)
            
            inv_T = 1.0 / temps_K  # 转换为 1/T (K⁻¹)
            ln_sigma = np.log(conductivities)
            
            # 按 1/T 升序排列（温度从高到低）
            sorted_idx = np.argsort(inv_T)
            inv_T = inv_T[sorted_idx]
            ln_sigma = ln_sigma[sorted_idx]
            temps_K = temps_K[sorted_idx]
            
            # 2. 拐点检测
            breakpoints = self.detect_breakpoints_sliding_window(inv_T, ln_sigma)
            
            # 3. 生成候选分段方案
            candidate_models = []
            
            # 模型0: 不分段（基准模型）
            segments_0 = self.fit_segments(inv_T, ln_sigma, temps_K, [])
            if segments_0:
                AIC_0, BIC_0 = self.calculate_aic_bic(inv_T, ln_sigma, segments_0)
                candidate_models.append({
                    'num_segments': 1,
                    'breakpoints': [],
                    'segments': segments_0,
                    'AIC': AIC_0,
                    'BIC': BIC_0
                })
            
            # 模型1+: 基于检测到的拐点
            for i in range(min(len(breakpoints), self.max_segments - 1)):
                bp_subset = breakpoints[:i+1]
                # 确保每段有足够的点
                if self.validate_breakpoints(inv_T, bp_subset):
                    segments = self.fit_segments(inv_T, ln_sigma, temps_K, bp_subset)
                    if segments:
                        AIC, BIC = self.calculate_aic_bic(inv_T, ln_sigma, segments)
                        candidate_models.append({
                            'num_segments': len(segments),
                            'breakpoints': bp_subset,
                            'segments': segments,
                            'AIC': AIC,
                            'BIC': BIC
                        })
            
            if not candidate_models:
                return None
            
            # 4. F-test检验（逐级比较）
            f_tests = []
            for i in range(1, len(candidate_models)):
                f_stat, p_val, is_sig = self.f_test_segmentation(
                    inv_T, ln_sigma,
                    candidate_models[i-1]['segments'],
                    candidate_models[i]['segments']
                )
                f_tests.append({
                    'comparison': f"{i} vs {i+1} segments",
                    'f_statistic': f_stat,
                    'p_value': p_val,
                    'is_significant': is_sig
                })
            
            # 5. 模型选择（优先选择F-test显著且AIC最小的模型）
            best_model_idx = 0
            min_AIC = candidate_models[0]['AIC']
            
            for i, model in enumerate(candidate_models):
                # 检查F-test是否支持更复杂的模型
                if i > 0:
                    # 如果增加分段不显著，且AIC没有明显改善，停止
                    if not f_tests[i-1]['is_significant'] and model['AIC'] >= min_AIC * 0.95:
                        break
                
                if model['AIC'] < min_AIC:
                    min_AIC = model['AIC']
                    best_model_idx = i
            
            optimal_model = candidate_models[best_model_idx]
            
            # ✅ 新增：构建 aic_scores 对象（用于前端 AIC 对比表格）
            aic_scores = {}
            for model in candidate_models:
                num_seg = model['num_segments']
                aic_scores[num_seg] = model['AIC']
            
            return {
                'success': True,
                'optimal_segments': optimal_model['segments'],
                'num_segments': optimal_model['num_segments'],
                'breakpoints': optimal_model['breakpoints'],
                'all_models': candidate_models,
                'f_tests': f_tests,
                'model_selection': {
                    'criterion': 'AIC + F-test',
                    'selected_model': best_model_idx + 1,
                    'AIC': optimal_model['AIC'],
                    'BIC': optimal_model['BIC'],
                    'aic_scores': aic_scores,  # ✅ 新增：所有模型的 AIC 值
                    'best_num_segments': optimal_model['num_segments']  # ✅ 新增：最优分段数
                }
            }
            
        except Exception as e:
            print(f"[WARNING] 高级Arrhenius分析失败: {e}")
            import traceback
            traceback.print_exc()
            return None


# 使用内置分析器
ANALYZER_AVAILABLE = True


def perform_arrhenius_analysis(
    successful_records: List[Dict],
    min_points: int = 5,
    enable_segmentation: bool = True  # 新参数：是否启用分段拟合
) -> Dict:
    """
    执行Arrhenius分析（升级版：支持自动分段）
    
    参数:
        successful_records: 成功的测量记录列表（每个记录必须包含temperature_K, rb_ohm, conductivity_S_per_cm）
        min_points: 最少数据点要求
        enable_segmentation: 是否启用分段拟合（默认True），如果False则使用简单单一拟合
        
    返回:
        分析结果字典（格式完全向后兼容）：
        - success: bool
        - message: str
        - data_points: int
        - segments: List[Dict]
        - arrhenius_data: List[Dict]
        - model_selection: Dict (仅在enable_segmentation=True时)
        - f_tests: List (仅在enable_segmentation=True时)
    """
    # 检查数据点数量
    if len(successful_records) < min_points:
        return {
            'success': False,
            'message': f'数据点不足：需要至少{min_points}个成功点，实际{len(successful_records)}个',
            'data_points': len(successful_records),
            'segments': [],
            'arrhenius_data': []
        }
    
    try:
        # 提取温度和电导率
        temps_K = []
        conductivities = []
        
        for record in successful_records:
            temp_K = record.get('temperature_K')
            conductivity = record.get('conductivity_S_per_cm')
            
            if temp_K and conductivity and conductivity > 0:
                temps_K.append(temp_K)
                conductivities.append(conductivity)
        
        if len(temps_K) < min_points:
            return {
                'success': False,
                'message': f'有效电导率数据点不足：需要至少{min_points}个，实际{len(temps_K)}个',
                'data_points': len(temps_K),
                'segments': [],
                'arrhenius_data': []
            }
        
        # 准备Arrhenius数据（用于绘图）
        arrhenius_data = []
        for temp_K, conductivity in zip(temps_K, conductivities):
            arrhenius_data.append({
                'temperature_K': temp_K,
                'temperature_C': temp_K - 273.15,
                'conductivity_S_per_cm': conductivity,
                'inv_T': 1.0 / temp_K,
                'ln_sigma': float(np.log(conductivity))
            })
        
        # ========== 数据预处理：去重（处理精测区间的重复点）==========
        from collections import defaultdict
        temp_groups = defaultdict(list)
        for temp_K, cond in zip(temps_K, conductivities):
            # 四舍五入到0.5K，合并相近温度点
            temp_key = round(temp_K * 2) / 2
            temp_groups[temp_key].append((temp_K, cond))
        
        # 对重复点取几何平均（电导率跨度大，几何平均更合理）
        if len(temp_groups) < len(temps_K):
            print(f"[INFO] 检测到重复温度点，合并 {len(temps_K)} → {len(temp_groups)} 点")
            temps_K_dedup = []
            conductivities_dedup = []
            for temp_key in sorted(temp_groups.keys()):
                records = temp_groups[temp_key]
                avg_temp = sum(r[0] for r in records) / len(records)
                # 几何平均 = exp(算术平均(ln值))
                geo_mean_cond = np.exp(sum(np.log(r[1]) for r in records) / len(records))
                temps_K_dedup.append(avg_temp)
                conductivities_dedup.append(geo_mean_cond)
            temps_K = temps_K_dedup
            conductivities = conductivities_dedup
            
            # 重建arrhenius_data
            arrhenius_data = []
            for temp_K_val, cond_val in zip(temps_K, conductivities):
                arrhenius_data.append({
                    'temperature_K': temp_K_val,
                    'temperature_C': temp_K_val - 273.15,
                    'conductivity_S_per_cm': cond_val,
                    'inv_T': 1.0 / temp_K_val,
                    'ln_sigma': float(np.log(cond_val))
                })
        
        # 根据参数选择分析方法
        if enable_segmentation and len(temps_K) >= 10:
            print("[INFO] 使用高级分段Arrhenius分析...")
            
            # 使用高级分段分析器（参数经过实际数据验证优化）
            analyzer = AdvancedArrheniusAnalyzer(
                window_size=5,          # 5点窗口，适合3°C步长数据
                threshold=1.0,          # 1.0σ阈值，减少噪声误触发（原0.5过敏感）
                min_segment_points=5,   # 每段至少5点，保证统计显著性
                max_segments=3          # 最多3段，符合物理预期
            )
            result = analyzer.analyze(temps_K, conductivities)
            
            if result and result.get('success'):
                # ========== 分段质量检验（已禁用，完全信任AIC/BIC统计选择）==========
                # ⚠️ 2026-01-26 修改：注释掉R²回退逻辑，完全信任F-test + AIC/BIC的统计学结果
                # 
                # 原逻辑问题：
                # 1. R²<0.90不代表分段错误，只是单段拟合质量
                # 2. 回退到单一拟合往往导致更低的R²（如0.26）
                # 3. 与AIC/BIC的统计学模型选择矛盾
                #
                # 参考: ALGORITHM_COMPARISON_ANALYSIS.md 第3.5.1节
                
                # min_r_squared = 0.90  # 最低R²要求
                # all_segments_valid = True
                # for seg in result['optimal_segments']:
                #     if seg.get('R_squared', 0) < min_r_squared:
                #         print(f"[WARNING] 分段{seg['segment']}的R²={seg['R_squared']:.4f} < {min_r_squared}，质量不达标")
                #         all_segments_valid = False
                #         break
                # 
                # # 如果分段质量不达标且分段数>1，回退到简单模型
                # if not all_segments_valid and result['num_segments'] > 1:
                #     print("[INFO] 分段质量检验未通过，回退到单一拟合...")
                #     enable_segmentation = False
                # else:
                
                # 直接使用AIC/BIC选择的最优模型，不再进行R²回退检验
                print(f"[INFO] 采用AIC/BIC选择的{result['num_segments']}段模型（AIC={result['model_selection']['AIC']:.2f}, BIC={result['model_selection']['BIC']:.2f}）")
                
                # 转换为兼容格式
                formatted_segments = []
                for seg in result['optimal_segments']:
                    formatted_segments.append({
                        'segment': seg['segment'],
                        'Ea_kJ_per_mol': seg['Ea_kJ_per_mol'],
                        'Ea_error_kJ_per_mol': seg.get('Ea_error_kJ_per_mol', 0),
                        'sigma0_S_per_cm': seg['sigma0_S_per_cm'],
                        'T_range_K': seg['T_range_K'],
                        'T_range_C': seg['T_range_C'],
                        'data_points': seg['data_points'],
                        'R_squared': seg['R_squared'],
                        'p_value': seg.get('p_value', 0)
                    })
                
                # 返回完整结果（修复：移到循环外）
                return {
                    'success': True,
                    'message': f'[SUCCESS] 成功识别 {result["num_segments"]} 个分段 (AIC={result["model_selection"]["AIC"]:.2f})',
                    'data_points': len(temps_K),
                    'segments': formatted_segments,
                    'arrhenius_data': arrhenius_data,
                    'model_selection': result['model_selection'],
                    'f_tests': result.get('f_tests', []),
                    'num_segments': result['num_segments']
                }
            else:
                print("[WARNING] 高级分析失败，回退到简单模型")
                enable_segmentation = False
        
        # 回退到简单模型（向后兼容）
        if not enable_segmentation or len(temps_K) < 10:
            print("[INFO] 使用简单单一线性拟合...")
            
            # 使用内联函数替代SimpleArrheniusAnalyzer类
            segments = _simple_arrhenius_fit(np.array(temps_K), np.array(conductivities))
            
            if not segments:
                return {
                    'success': False,
                    'message': '分析失败：无法识别有效数据段',
                    'data_points': len(temps_K),
                    'segments': [],
                    'arrhenius_data': []
                }
            
            # 格式化分段结果（向后兼容）
            formatted_segments = []
            for seg in segments:
                formatted_segments.append({
                    'segment': seg['segment'],
                    'Ea_kJ_per_mol': seg['Ea'],
                    'sigma0_S_per_cm': seg['sigma0'],
                    'T_range_K': seg['T_range'],
                    'T_range_C': (seg['T_range'][0] - 273.15, seg['T_range'][1] - 273.15),
                    'data_points': seg['points'],
                    'R_squared': seg.get('r_squared', 0)
                })
            
            return {
                'success': True,
                'message': f'使用单一线性拟合 (R²={segments[0].get("r_squared", 0):.4f})',
                'data_points': len(temps_K),
                'segments': formatted_segments,
                'arrhenius_data': arrhenius_data,
                'num_segments': 1,
                # ✅ 新增：为简单模型添加 model_selection 和 f_tests，保持与高级分析一致
                'model_selection': {
                    'criterion': 'simple_linear',
                    'selected_model': 1,
                    'AIC': None,  # 简单模型不计算 AIC
                    'BIC': None,
                    'aic_scores': {1: None},  # 只有一个模型
                    'best_num_segments': 1
                },
                'f_tests': []  # 只有一个分段，无需 F-test
            }
        
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        
        return {
            'success': False,
            'message': f'分析异常: {str(e)}',
            'error_detail': error_detail,
            'data_points': len(successful_records),
            'segments': [],
            'arrhenius_data': []
        }


def generate_arrhenius_plot_data(
    arrhenius_data: List[Dict],
    segments: List[Dict]
) -> Dict:
    """
    生成Arrhenius图的绘图数据
    
    参数:
        arrhenius_data: Arrhenius原始数据
        segments: 拟合分段结果
        
    返回:
        绘图数据字典
    """
    R = 8.314  # J/(mol·K)
    
    plot_data = {
        'scatter': {
            'x': [d['inv_T'] for d in arrhenius_data],
            'y': [d['ln_sigma'] for d in arrhenius_data],
            'labels': [f"{d['temperature_C']:.1f}°C" for d in arrhenius_data]
        },
        'fit_lines': []
    }
    
    for seg in segments:
        T1, T2 = seg['T_range_K']
        x_fit = np.linspace(1/T2, 1/T1, 50)
        Ea = seg.get('Ea_kJ_per_mol', seg.get('Ea', 0))  # 兼容旧格式
        sigma0 = seg.get('sigma0_S_per_cm', seg.get('sigma0', 1))
        y_fit = np.log(sigma0) - Ea * 1000 / R * x_fit
        
        plot_data['fit_lines'].append({
            'segment': seg['segment'],
            'x': x_fit.tolist(),
            'y': y_fit.tolist(),
            'label': f"分段{seg['segment']} Ea={Ea:.2f} kJ/mol"
        })
    
    return plot_data
