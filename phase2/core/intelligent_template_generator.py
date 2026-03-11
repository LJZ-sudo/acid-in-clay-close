# -*- coding: utf-8 -*-
"""
Phase2批量报告生成器 - 智能模板版

特点：
1. 不使用LLM，完全基于模板和规则
2. 包含数据关联分析（智能）
3. 包含具体数值和对比
4. 输出详细但不做深度机理推断
"""
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List
import numpy as np


class IntelligentTemplateGenerator:
    """智能模板报告生成器"""
    
    def __init__(self):
        """初始化"""
        pass
    
    def generate_sample_report(self, integrated_data: Dict[str, Any]) -> str:
        """
        生成单个样品的智能模板报告
        
        Args:
            integrated_data: enhanced_data_integrator提供的完整数据
            
        Returns:
            Markdown格式报告
        """
        sample_id = integrated_data['sample_id']
        sample_type = integrated_data['sample_type']
        metadata = integrated_data.get('metadata', {})
        phase1 = integrated_data['phase1_data']
        
        # 开始构建报告
        report = f"""# {sample_id} 样品分析报告

**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**样品类型**: {sample_type}
**分析方法**: 数据驱动分析 + 机理推测（辅助）

---

"""
        
        # 1. 样品信息
        report += self._section_sample_info(sample_id, sample_type, metadata)
        
        # 2. 数据质量评估（提前，重要性提升）
        report += self._section_data_quality(phase1)
        
        # 3. Arrhenius分析
        report += self._section_arrhenius(phase1.get('arrhenius', {}), sample_type)
        
        # 4. 数据关联分析（核心）
        report += self._section_correlation_analysis(phase1, sample_type)
        
        # 5. DRT分析（可选，仅在数据存在时显示）
        # 兼容两种键名：drt_enhanced 和 drt
        drt_data = phase1.get('drt_enhanced') or phase1.get('drt', {})
        # 检查DRT数据是否存在且有实际内容
        # 1. 不是空字典
        # 2. 不是error字段
        # 3. 有实际数据（有summary字段，或者有total_peaks/n_temperatures等统计字段）
        # 4. 检查data_source_summary中的drt_enabled（如果存在）
        has_drt_data = (
            drt_data and 
            not drt_data.get('error') and
            len(drt_data) > 0 and
            (drt_data.get('summary') is not None or 
             drt_data.get('total_peaks', 0) > 0 or
             drt_data.get('n_temperatures', 0) > 0) and
            (not drt_data.get('data_source_summary') or 
             drt_data.get('data_source_summary', {}).get('drt_enabled', True))
        )
        if has_drt_data:
            report += self._section_drt(drt_data)
        # 如果DRT被禁用或数据为空，跳过此章节（不显示"无DRT数据"）
        
        # 6. Modulus分析（可选，仅在数据存在时显示）
        # 兼容两种键名：modulus_enhanced 和 modulus
        modulus_data = phase1.get('modulus_enhanced') or phase1.get('modulus', {})
        # 检查Modulus数据是否存在且有实际内容
        # 空字典{}应该被跳过
        has_modulus_data = (
            modulus_data and 
            len(modulus_data) > 0 and
            not modulus_data.get('error') and
            # 必须有实际数据：有summary字段，或者有统计信息
            (modulus_data.get('summary') is not None or 
             modulus_data.get('total_peaks', 0) > 0 or
             modulus_data.get('n_temperatures', 0) > 0) and
            # 检查data_source_summary中的modulus_enabled（如果存在且为False，则跳过）
            (not modulus_data.get('data_source_summary') or 
             modulus_data.get('data_source_summary', {}).get('modulus_enabled', True) != False)
        )
        if has_modulus_data:
            report += self._section_modulus(modulus_data)
        # 如果Modulus被禁用或数据为空，跳过此章节（不显示"无Modulus数据"）
        
        # 7. 特征提取（新增，为Phase 3准备）
        report += self._section_feature_extraction(integrated_data)
        
        # 8. 机理推测（降级为辅助，添加免责声明）
        report += "\n## 8. 机理推测（辅助参考）\n\n"
        report += "*⚠️ 注：以下推测基于数据模式识别，仅供参考，不作为主要结论。"
        report += "机理验证需要NMR、同位素效应等直接实验证据。*\n\n"
        report += self._section_simple_inference(phase1, sample_type, metadata)
        
        # 9. 数据总结
        report += self._section_summary(phase1, sample_type)
        
        return report
    
    def _section_sample_info(self, sample_id: str, sample_type: str, metadata: Dict) -> str:
        """1. 样品信息部分"""
        s = "## 1. 样品信息\n\n"
        s += f"- **样品ID**: {sample_id}\n"
        
        # 材料类型描述（支持所有材料类型）
        material_descriptions = {
            'S6': 'Sepiolite + Phytic acid',
            'S8': '含Sepiolite的Acid-in-Clay',
            'S12': 'Sepiolite + H2O',
            'S13': 'Bentonite + Phytic acid',
            'S14': 'Halloysite + H3PO4',
            'S15': 'Kaolin + Phytic acid',
            'S16': 'Bentonite + H3PO4',
            'S60': '纯磷酸液体',
            'S95': 'H2SO4 + Sepiolite',
            'S96': 'H2SO4 + Bentonite',
            'S97': 'H2SO4 + Halloysite'
        }
        material_desc = material_descriptions.get(sample_type, f'材料类型: {sample_type}')
        s += f"- **材料类型**: {sample_type} ({material_desc})\n"
        
        if metadata:
            # 使用新的字段名
            r = metadata.get('R')
            n = metadata.get('N')
            
            # 磷酸浓度（如果需要，可以从其他来源获取，这里暂时不显示）
            # s += f"- **磷酸浓度**: {h3po4:.1f} wt%\n"
            
            # R的定义: n(H3PO4)/n(H2O)
            if r is not None:
                s += f"- **R (n(H3PO4)/n(H2O))**: {r:.3f}\n"
            
            if sample_type == 'S8':
                if n is not None:
                    s += f"- **液固比(N)**: {n:.1f}\n"
                sepiolite = metadata.get('sepiolite_mg', 450)
                s += f"- **Sepiolite质量**: {sepiolite:.0f} mg\n"
        else:
            s += "- **元数据**: 未找到\n"
        
        s += "\n"
        return s
    
    def _section_arrhenius(self, arrhenius_data: Dict, sample_type: str) -> str:
        """3. Arrhenius分析部分"""
        s = "## 3. Arrhenius分析\n\n"
        
        segments = arrhenius_data.get('segments', [])
        
        if not segments:
            s += "**无高质量Arrhenius数据**\n\n"
            return s
        
        s += f"检测到**{len(segments)}个温度分段**，质子传导行为呈现分段特征：\n\n"
        
        # 分段详细信息
        for i, seg in enumerate(segments, 1):
            # 兼容两种格式：temp_range_K列表 或 T_min_K/T_max_K字段
            if 'temp_range_K' in seg:
                temp_range = seg['temp_range_K']
                t_min = temp_range[0] if isinstance(temp_range, (list, tuple)) else 0
                t_max = temp_range[1] if isinstance(temp_range, (list, tuple)) and len(temp_range) > 1 else 0
            else:
                t_min = seg.get('T_min_K', 0)
                t_max = seg.get('T_max_K', 0)
            
            ea = seg.get('Ea_eV', 0)
            # 兼容两种格式：r_squared 或 R_squared
            r2 = seg.get('r_squared') or seg.get('R_squared', 0)
            quality = seg.get('quality', 'unknown')
            
            s += f"### 分段{i}: {t_min:.1f} - {t_max:.1f} K\n\n"
            
            # 激活能及其误差分析
            s += f"- **激活能(Ea)**: {ea:.3f} eV\n"
            if seg.get('Ea_stderr') is not None:
                s += f"  - **标准误差**: {seg['Ea_stderr']:.4f} eV\n"
            if seg.get('Ea_ci_lower') is not None and seg.get('Ea_ci_upper') is not None:
                s += f"  - **95%置信区间**: [{seg['Ea_ci_lower']:.3f}, {seg['Ea_ci_upper']:.3f}] eV\n"
            if seg.get('Ea_relative_error') is not None:
                s += f"  - **相对误差**: {seg['Ea_relative_error']*100:.2f}%\n"
            
            # 前因子（sigma0）
            sigma0 = seg.get('sigma0_S_cm', 0)
            if sigma0 > 0:
                # 使用科学计数法格式化大数
                if sigma0 >= 1e10:
                    s += f"- **前因子(σ₀)**: {sigma0:.2e} S/cm\n"
                else:
                    s += f"- **前因子(σ₀)**: {sigma0:.2f} S/cm\n"
                if seg.get('sigma0_error') is not None:
                    s += f"  - **标准误差**: {seg['sigma0_error']:.2e} S/cm\n"
            
            # 拟合质量和统计显著性
            s += f"- **拟合质量(R²)**: {r2:.4f}\n"
            if seg.get('p_value') is not None:
                p_val = seg['p_value']
                if p_val < 0.001:
                    sig_mark = "✅ 高度显著"
                elif p_val < 0.01:
                    sig_mark = "✅ 显著"
                elif p_val < 0.05:
                    sig_mark = "⚠️ 边缘显著"
                else:
                    sig_mark = "❌ 不显著"
                s += f"- **统计显著性(p-value)**: {p_val:.3e} {sig_mark}\n"
            
            # 数据点数和质量
            s += f"- **数据点数**: {seg.get('n_points', 0)}\n"
            s += f"- **数据质量**: {quality}\n"
            
            # 智能评价
            s += self._eval_ea(ea, t_min, t_max)
            s += "\n"
        
        # 分段对比
        if len(segments) > 1:
            s += self._compare_segments(segments)
        
        return s
    
    def _eval_ea(self, ea: float, t_min: float, t_max: float) -> str:
        """评价激活能（智能规则）"""
        s = "\n**评价**: "
        
        # 温度区间
        if t_max < 220:
            temp_range = "极低温"
        elif t_max < 250:
            temp_range = "低温"
        elif t_max < 280:
            temp_range = "中温"
        else:
            temp_range = "高温"
        
        # Ea评价
        if ea < 0.15:
            ea_level = "极低"
            s += f"{temp_range}段Ea{ea_level}({ea:.3f} eV)，质子传导**非常活跃**。"
        elif ea < 0.30:
            ea_level = "较低"
            s += f"{temp_range}段Ea{ea_level}({ea:.3f} eV)，质子传导**活跃**。"
        elif ea < 0.50:
            ea_level = "中等"
            s += f"{temp_range}段Ea{ea_level}({ea:.3f} eV)，质子传导受一定阻碍。"
        elif ea < 0.70:
            ea_level = "较高"
            s += f"{temp_range}段Ea{ea_level}({ea:.3f} eV)，质子传导**明显受阻**。"
        else:
            ea_level = "极高"
            s += f"{temp_range}段Ea{ea_level}({ea:.3f} eV)，质子传导**严重受阻**，可能接近冻结态。"
        
        return s
    
    def _compare_segments(self, segments: List[Dict]) -> str:
        """对比不同分段（数据关联分析）"""
        s = "### 分段对比与传导行为演化\n\n"
        
        eas = [seg['Ea_eV'] for seg in segments]
        
        # Ea变化趋势
        ea_changes = [eas[i+1] - eas[i] for i in range(len(eas)-1)]
        
        s += "**Ea随温度变化**:\n\n"
        for i, change in enumerate(ea_changes, 1):
            if change < -0.1:
                s += f"- 分段{i}→{i+1}: Ea**显著降低**({change:.3f} eV)，传导大幅改善\n"
            elif change < -0.05:
                s += f"- 分段{i}→{i+1}: Ea降低({change:.3f} eV)，传导改善\n"
            elif change < 0.05:
                s += f"- 分段{i}→{i+1}: Ea基本稳定({change:+.3f} eV)\n"
            else:
                s += f"- 分段{i}→{i+1}: Ea升高({change:+.3f} eV)，传导恶化（异常）\n"
        
        # 最优温度段
        min_ea_idx = np.argmin(eas)
        # 兼容两种格式
        best_seg = segments[min_ea_idx]
        if 'temp_range_K' in best_seg:
            best_t_range = best_seg['temp_range_K']
            best_t_min = best_t_range[0] if isinstance(best_t_range, (list, tuple)) else 0
            best_t_max = best_t_range[1] if isinstance(best_t_range, (list, tuple)) and len(best_t_range) > 1 else 0
        else:
            best_t_min = best_seg.get('T_min_K', 0)
            best_t_max = best_seg.get('T_max_K', 0)
        s += f"\n**最优温度段**: 分段{min_ea_idx+1} ({best_t_min:.0f}-{best_t_max:.0f}K, Ea={eas[min_ea_idx]:.3f} eV)\n\n"
        
        return s
    
    def _section_data_quality(self, phase1: Dict) -> str:
        """2. 数据质量评估"""
        s = "## 2. 数据质量评估\n\n"
        
        arrhenius = phase1.get('arrhenius', {})
        segments = arrhenius.get('segments', [])
        
        if not segments:
            s += "**无法评估（缺少数据）**\n\n"
            return s
        
        # 统计质量分布
        quality_counts = {}
        for seg in segments:
            q = seg.get('quality', 'unknown')
            quality_counts[q] = quality_counts.get(q, 0) + 1
        
        s += "**Arrhenius拟合质量分布**:\n\n"
        for q, count in quality_counts.items():
            s += f"- {q}: {count}个分段\n"
        
        # R²统计 - 兼容两种格式：r_squared 或 R_squared
        r2_values = []
        for seg in segments:
            r2 = seg.get('r_squared') or seg.get('R_squared')
            if r2 is not None:
                r2_values.append(r2)
        
        if r2_values:
            r2_mean = np.mean(r2_values)
            r2_min = np.min(r2_values)
            
            s += f"\n**R²统计**: 平均{r2_mean:.4f}，最低{r2_min:.4f}\n"
            
            if r2_mean >= 0.99:
                s += "- **评价**: 拟合质量优秀 ✅\n"
            elif r2_mean >= 0.95:
                s += "- **评价**: 拟合质量良好 ✅\n"
            elif r2_mean >= 0.90:
                s += "- **评价**: 拟合质量可接受 ⚠️\n"
            else:
                s += "- **评价**: 拟合质量较差，需谨慎 ⚠️\n"
        else:
            s += "\n**R²统计**: 无法获取R²值\n"
        
        s += "\n"
        return s
    
    def _section_drt(self, drt_data: Dict) -> str:
        """5. DRT分析部分
        
        注意：此方法仅在DRT数据存在且有实际内容时被调用
        如果DRT被禁用，generate_sample_report会跳过此章节
        
        支持两种数据格式：
        1. 有summary字段的格式（旧格式）
        2. 直接包含统计信息的格式（新格式，从enhanced_data_integrator返回）
        """
        s = "## 5. DRT (弛豫时间分布) 分析\n\n"
        
        if not drt_data:
            s += "**无DRT数据**\n\n"
            return s
        
        # 兼容两种数据格式
        if 'summary' in drt_data:
            # 旧格式：有summary字段
            summary = drt_data['summary']
            total_peaks = summary.get('total_peaks', 0)
            detection_rate = summary.get('detection_rate', 0)
        else:
            # 新格式：直接包含统计信息
            total_peaks = drt_data.get('total_peaks', 0)
            detection_rate = drt_data.get('peak_detection_rate', 0) * 100  # 转换为百分比
        
        s += f"- **总峰数**: {total_peaks}\n"
        s += f"- **检出率**: {detection_rate:.1f}%\n"
        
        if detection_rate < 30:
            s += "- **评价**: 峰检出率较低，弛豫过程不明显或超出检测范围\n"
        elif detection_rate < 60:
            s += "- **评价**: 部分温度点检测到弛豫峰，说明存在明显弛豫过程\n"
        else:
            s += "- **评价**: 大部分温度点检测到弛豫峰，弛豫过程丰富\n"
        
        # 主要峰特征
        main_peaks = drt_data.get('main_peaks', {})
        # 兼容新格式：从detailed_by_temperature中提取主峰信息
        if not main_peaks and 'detailed_by_temperature' in drt_data:
            # 从新格式中提取主峰频率
            main_freq_median = drt_data.get('main_frequency_median_Hz', 0)
            if main_freq_median > 0:
                main_peaks = {'freq_main_Hz': main_freq_median}
        
        if main_peaks:
            s += "\n**主要弛豫特征**:\n\n"
            
            tau_主 = main_peaks.get('tau_main_s', None)
            freq_主 = main_peaks.get('freq_main_Hz', None)
            
            if tau_主:
                s += f"- 主弛豫时间: {tau_主:.2e} s\n"
            if freq_主:
                s += f"- 主弛豫频率: {freq_主:.2e} Hz\n"
                
                # 频率区间判断
                if freq_主 > 1e3:
                    s += "  - **解释**: 高频弛豫，可能对应快速质子跳跃过程\n"
                elif freq_主 > 1:
                    s += "  - **解释**: 中频弛豫，可能对应局部质子重排\n"
                else:
                    s += "  - **解释**: 低频弛豫，可能对应长程扩散或界面过程\n"
        
        s += "\n"
        return s
    
    def _section_modulus(self, modulus_data: Dict) -> str:
        """6. Modulus分析部分
        
        注意：此方法仅在Modulus数据存在且有实际内容时被调用
        如果Modulus被禁用，generate_sample_report会跳过此章节
        
        支持两种数据格式：
        1. 有summary字段的格式（旧格式）
        2. 直接包含统计信息的格式（新格式，从enhanced_data_integrator返回）
        """
        s = "## 6. 电模量(Modulus)分析\n\n"
        
        if not modulus_data:
            s += "**无Modulus数据**\n\n"
            return s
        
        # 兼容两种数据格式
        if 'summary' in modulus_data:
            # 旧格式：有summary字段
            summary = modulus_data['summary']
            total_peaks = summary.get('total_peaks', 0)
            detection_rate = summary.get('detection_rate', 0)
        else:
            # 新格式：直接包含统计信息
            total_peaks = modulus_data.get('total_peaks', 0)
            detection_rate = modulus_data.get('peak_detection_rate', 0) * 100  # 转换为百分比
        
        s += f"- **总峰数**: {total_peaks}\n"
        s += f"- **检出率**: {detection_rate:.1f}%\n"
        
        if detection_rate == 0:
            s += "- **评价**: 未检测到Modulus峰，可能是材料特性或测量限制\n"
        elif detection_rate < 30:
            s += "- **评价**: Modulus峰较少，主要弛豫过程可能在DRT中更清晰\n"
        else:
            s += "- **评价**: 检测到明显Modulus峰，电介质行为明显\n"
        
        s += "\n"
        return s
    
    def _section_correlation_analysis(self, phase1: Dict, sample_type: str) -> str:
        """4. 数据关联分析（智能核心）"""
        s = "## 4. 数据关联分析\n\n"
        s += "综合Arrhenius、DRT和Modulus数据，进行交叉分析：\n\n"
        
        arrhenius = phase1.get('arrhenius', {})
        drt = phase1.get('drt_enhanced', {})
        segments = arrhenius.get('segments', [])
        
        if not segments:
            s += "**无法进行关联分析（缺少Arrhenius数据）**\n\n"
            return s
        
        # 1. Ea vs DRT关联
        drt_rate = drt.get('summary', {}).get('detection_rate', 0)
        
        s += "### 6.1 Ea与弛豫行为的关联\n\n"
        
        if len(segments) >= 2:
            low_temp_ea = segments[0]['Ea_eV']
            high_temp_ea = segments[-1]['Ea_eV']
            ea_drop = low_temp_ea - high_temp_ea
            
            s += f"- 低温段Ea = {low_temp_ea:.3f} eV\n"
            s += f"- 高温段Ea = {high_temp_ea:.3f} eV\n"
            s += f"- Ea降幅 = {ea_drop:.3f} eV\n\n"
            
            if ea_drop > 0.3:
                s += "**关联结论**: Ea显著降低，说明质子传导路径在高温下发生改变。"
            elif ea_drop > 0.1:
                s += "**关联结论**: Ea适度降低，传导机制可能有渐进式转变。"
            else:
                s += "**关联结论**: Ea变化较小，传导机制相对稳定。"
            
            if drt_rate > 50:
                s += "DRT检测到丰富的弛豫过程，支持多机制共存。\n"
            else:
                s += "DRT峰较少，可能为单一主导机制。\n"
        
        # 2. 温度跨度分析
        s += "\n### 6.2 有效工作温度范围\n\n"
        
        # 兼容两种格式：temp_range_K列表 或 T_min_K/T_max_K字段
        seg0 = segments[0]
        seg_last = segments[-1]
        if 'temp_range_K' in seg0:
            t_min = seg0['temp_range_K'][0] if isinstance(seg0['temp_range_K'], (list, tuple)) else 0
        else:
            t_min = seg0.get('T_min_K', 0)
        if 'temp_range_K' in seg_last:
            t_max = seg_last['temp_range_K'][1] if isinstance(seg_last['temp_range_K'], (list, tuple)) and len(seg_last['temp_range_K']) > 1 else 0
        else:
            t_max = seg_last.get('T_max_K', 0)
        
        s += f"- **测试范围**: {t_min:.0f} - {t_max:.0f} K (跨度{t_max-t_min:.0f}K)\n"
        
        if t_min < 200:
            s += f"- **低温性能**: 在{t_min:.0f}K仍可测试，具备一定低温耐受性\n"
        
        if t_max >= 300:
            s += f"- **高温性能**: 覆盖室温以上，适用范围广\n"
        
        s += "\n"
        return s
    
    def _section_simple_inference(self, phase1: Dict, sample_type: str, metadata: Dict) -> str:
        """8. 简要推测（非深度机理）- 内容部分，标题在主函数中添加"""
        s = ""  # 标题已在generate_sample_report中添加
        
        segments = phase1.get('arrhenius', {}).get('segments', [])
        
        if not segments:
            s += "**无法推测（缺少数据）**\n\n"
            return s
        
        # 辅助函数：从segment提取温度范围
        def get_temp_range(seg):
            if 'temp_range_K' in seg:
                tr = seg['temp_range_K']
                if isinstance(tr, (list, tuple)) and len(tr) >= 2:
                    return tr[0], tr[1]
            return seg.get('T_min_K', 0), seg.get('T_max_K', 0)
        
        # 低温行为
        if len(segments) > 0:
            low_ea = segments[0].get('Ea_eV', 0)
            _, low_t = get_temp_range(segments[0])
            
            if low_ea > 0.6:
                s += f"- **低温段**(<{low_t:.0f}K): Ea高达{low_ea:.3f} eV，传导严重受阻，可能接近冻结态\n"
            elif low_ea > 0.4:
                s += f"- **低温段**(<{low_t:.0f}K): Ea为{low_ea:.3f} eV，传导受一定限制\n"
            else:
                s += f"- **低温段**(<{low_t:.0f}K): Ea为{low_ea:.3f} eV，低温性能良好\n"
        
        # 高温行为
        if len(segments) > 1:
            high_ea = segments[-1].get('Ea_eV', 0)
            high_t, _ = get_temp_range(segments[-1])
            
            if high_ea < 0.15:
                s += f"- **高温段**(>{high_t:.0f}K): Ea低至{high_ea:.3f} eV，传导非常活跃\n"
            elif high_ea < 0.30:
                s += f"- **高温段**(>{high_t:.0f}K): Ea为{high_ea:.3f} eV，传导活跃\n"
            else:
                s += f"- **高温段**(>{high_t:.0f}K): Ea为{high_ea:.3f} eV，仍需进一步优化\n"
        
        # 材料特定效应（支持所有材料类型）
        n = metadata.get('N') or metadata.get('N_liquid_solid', 0)
        
        if sample_type in ['S6', 'S8', 'S12', 'S14', 'S15', 'S16', 'S95', 'S96', 'S97']:
            # 含黏土的材料，可能有限域效应
            clay_types = {
                'S6': 'Sepiolite',
                'S8': 'Sepiolite',
                'S12': 'Sepiolite',
                'S14': 'Halloysite',
                'S15': 'Kaolin',
                'S16': 'Bentonite',
                'S95': 'Sepiolite',
                'S96': 'Bentonite',
                'S97': 'Halloysite'
            }
            clay_type = clay_types.get(sample_type, '黏土')
            s += f"\n- **{clay_type}纳米限域**: {sample_type}材料含{clay_type}，可能影响质子传导路径和机制\n"
            
            if n and n > 0:
                if n < 3:
                    s += f"  - 液固比N={n:.1f}（较低），限域效应可能较强\n"
                elif n < 6:
                    s += f"  - 液固比N={n:.1f}（中等），限域与自由扩散平衡\n"
                else:
                    s += f"  - 液固比N={n:.1f}（较高），限域效应可能较弱\n"
        elif sample_type == 'S60':
            # 纯液体，无限域效应
            s += f"\n- **Vehicle机制**: S60为纯液体电解质，质子传导主要通过Vehicle机制\n"
        
        s += "\n"
        return s
    
    def _section_summary(self, phase1: Dict, sample_type: str) -> str:
        """9. 数据总结"""
        s = "## 9. 数据总结\n\n"
        
        segments = phase1.get('arrhenius', {}).get('segments', [])
        drt_summary = phase1.get('drt_enhanced', {}).get('summary', {})
        
        # Arrhenius
        s += f"- **Arrhenius分段数**: {len(segments)}\n"
        if segments:
            eas = [seg['Ea_eV'] for seg in segments]
            s += f"- **Ea范围**: {min(eas):.3f} - {max(eas):.3f} eV\n"
            s += f"- **最优Ea**: {min(eas):.3f} eV\n"
        
        # DRT
        total_peaks = drt_summary.get('total_peaks', 0)
        s += f"- **DRT峰总数**: {total_peaks}\n"
        
        # 数据完整性
        s += "\n**数据完整性评价**:\n\n"
        
        has_arrhenius = len(segments) > 0
        has_drt = total_peaks > 0
        
        if has_arrhenius and has_drt:
            s += "✅ 数据完整，包含Arrhenius和DRT分析\n"
        elif has_arrhenius:
            s += "⚠️ 有Arrhenius数据，但缺少DRT数据\n"
        else:
            s += "❌ 数据不完整，建议重新测试\n"
        
        s += "\n---\n\n"
        s += "*本报告由智能模板生成，基于Phase1高质量数据*\n"
        
        return s
    
    def _section_feature_extraction(self, integrated_data: Dict) -> str:
        """7. 特征提取（为机器学习准备）"""
        s = "\n## 7. 特征提取\n\n"
        s += "为Phase 3机器学习建模提取的特征：\n\n"
        
        # 调用特征提取器
        from .feature_extractor import FeatureExtractor
        extractor = FeatureExtractor()
        features = extractor.extract_features(integrated_data)
        
        s += "### 基础特征\n\n"
        s += f"- **R (H3PO4/H2O)**: {features.get('R', 0):.3f}\n"
        s += f"- **N (液固比)**: {features.get('N', 0):.2f}\n"
        s += f"- **温度范围**: {features.get('T_min', 0):.0f} - {features.get('T_max', 0):.0f} K\n"
        s += f"- **平均温度**: {features.get('T_avg', 0):.1f} K\n\n"
        
        s += "### 派生特征\n\n"
        s += f"- **R²**: {features.get('R_squared', 0):.4f}\n"
        s += f"- **N²**: {features.get('N_squared', 0):.4f}\n"
        s += f"- **R×N**: {features.get('R_times_N', 0):.4f}\n"
        s += f"- **exp(-N/4)**: {features.get('exp_minus_N', 0):.4f} (限域效应衰减因子)\n\n"
        
        s += "### 温度区间\n\n"
        if features.get('is_low_temp'):
            s += "- ✅ 低温段 (<230K)\n"
        if features.get('is_mid_temp'):
            s += "- ✅ 中温段 (230-270K)\n"
        if features.get('is_high_temp'):
            s += "- ✅ 高温段 (≥270K)\n"
        
        s += "\n### 数据质量\n\n"
        s += f"- **质量评分**: {features.get('quality_score', 0):.1f}/100\n"
        s += f"- **质量等级**: {features.get('quality_level', 'unknown')}\n"
        s += f"- **建模适用性**: {'✅ 适用' if features.get('use_for_modeling', False) else '⚠️ 不推荐'}\n"
        s += f"- **Arrhenius分段数**: {features.get('n_segments', 0)}\n"
        s += f"- **平均拟合R²**: {features.get('avg_R_squared', 0):.4f}\n"
        
        # 新增：sigma0和误差特征
        if features.get('sigma0_mean', 0) > 0:
            s += f"- **前因子平均值(σ₀)**: {features.get('sigma0_mean', 0):.2e} S/cm\n"
        if features.get('Ea_stderr_mean', 0) > 0:
            s += f"- **Ea标准误差平均值**: {features.get('Ea_stderr_mean', 0):.4f} eV\n"
        if features.get('p_value_min', 1.0) < 1.0:
            p_min = features.get('p_value_min', 1.0)
            sig_status = "✅ 所有分段显著" if features.get('all_segments_significant', 0) == 1 else "⚠️ 部分分段不显著"
            s += f"- **最小p-value**: {p_min:.3e} ({sig_status})\n"
        
        s += "\n"
        
        return s


def generate_batch_reports_with_template(
    phase1_result_dir: Path,
    output_dir: Path,
    metadata_file: Path = None
) -> Dict:
    """
    批量生成模板报告
    
    Args:
        phase1_result_dir: Phase1结果目录
        output_dir: 输出目录
        metadata_file: 元数据文件（S8-S60.xlsx）
        
    Returns:
        生成统计
    """
    from phase2.core.enhanced_data_integrator import EnhancedDataIntegrator
    
    # 初始化
    integrator = EnhancedDataIntegrator(
        result_dir=phase1_result_dir,
        metadata_file=metadata_file
    )
    generator = IntelligentTemplateGenerator()
    
    # 获取所有样品
    sample_dirs = [d for d in phase1_result_dir.iterdir() if d.is_dir() and d.name.startswith('phase1_')]
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    stats = {
        'total': len(sample_dirs),
        'success': 0,
        'failed': 0,
        'reports': []
    }
    
    for i, sample_dir in enumerate(sample_dirs, 1):
        sample_dir_name = sample_dir.name
        
        try:
            print(f"[{i}/{len(sample_dirs)}] 生成报告: {sample_dir_name}")
            
            # 整合数据
            data = integrator.integrate_sample(sample_dir_name)
            
            if 'error' in data:
                print(f"  [ERROR] {data['error']}")
                stats['failed'] += 1
                continue
            
            # 生成报告
            report = generator.generate_sample_report(data)
            
            # 保存
            sample_id = data['sample_id']
            output_file = output_dir / f"{sample_id}_template_report.md"
            
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(report)
            
            print(f"  [OK] 已保存: {output_file.name}")
            
            stats['success'] += 1
            stats['reports'].append({
                'sample_id': sample_id,
                'file': str(output_file.name)
            })
            
        except Exception as e:
            print(f"  [ERROR] {str(e)}")
            stats['failed'] += 1
    
    # 保存统计
    stats_file = output_dir / "batch_template_reports_summary.json"
    with open(stats_file, 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)
    
    print(f"\n=== 完成 ===")
    print(f"成功: {stats['success']}/{stats['total']}")
    print(f"失败: {stats['failed']}/{stats['total']}")
    print(f"输出目录: {output_dir}")
    
    return stats

