# -*- coding: utf-8 -*-
"""
报告生成模块：输出完整的实验报告
"""

import os
import json
import time
import numpy as np
from typing import List, Dict, Optional
from datetime import datetime


class NumpyEncoder(json.JSONEncoder):
    """自定义JSON编码器，处理numpy类型"""
    def default(self, obj):
        if isinstance(obj, (np.integer, np.int_, np.intc, np.intp, np.int8,
                           np.int16, np.int32, np.int64, np.uint8,
                           np.uint16, np.uint32, np.uint64)):
            return int(obj)
        elif isinstance(obj, (np.floating, np.float_, np.float16, np.float32, np.float64)):
            return float(obj)
        elif isinstance(obj, (np.bool_, np.bool8)):
            return bool(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        return super(NumpyEncoder, self).default(obj)


def generate_report(
    successful_records: List[Dict],
    failed_records: List[Dict],
    arrhenius_result: Dict,
    config: Dict,
    output_path: str = None
) -> Dict:
    """
    生成完整的实验报告
    
    参数:
        successful_records: 成功的测量记录列表
        failed_records: 失败的测量记录列表
        arrhenius_result: Arrhenius分析结果
        config: 输入配置（温度范围、样品参数等）
        output_path: 输出文件路径（默认：experiment_data/report.json）
        
    返回:
        报告字典
    """
    if output_path is None:
        output_path = os.path.join('experiment_data', 'report.json')
    
    # 创建输出目录
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # 构建报告
    report = {
        'metadata': {
            'report_version': '1.0',
            'generated_at': datetime.now().isoformat(),
            'timestamp': time.time()
        },
        
        'configuration': config,
        
        'summary': {
            'total_measurements': len(successful_records) + len(failed_records),
            'successful_measurements': len(successful_records),
            'failed_measurements': len(failed_records),
            'success_rate': len(successful_records) / (len(successful_records) + len(failed_records)) if (len(successful_records) + len(failed_records)) > 0 else 0.0
        },
        
        'successful_points': _format_successful_records(successful_records),
        
        'failed_points': _format_failed_records(failed_records),
        
        'arrhenius_analysis': arrhenius_result,
        
        'raw_data_mapping': _create_raw_data_mapping(successful_records, failed_records)
    }
    
    # 保存到文件（使用自定义编码器处理numpy类型）
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False, cls=NumpyEncoder)
    
    print(f"✅ 报告已保存: {output_path}")
    
    return report


def _format_successful_records(records: List[Dict]) -> List[Dict]:
    """格式化成功记录"""
    formatted = []
    
    for record in records:
        formatted.append({
            'temperature_C': record.get('temperature_C'),
            'temperature_K': record.get('temperature_K'),
            'rb_ohm': record.get('rb_ohm'),
            'rb_method': record.get('rb_method'),
            'fit_quality': record.get('fit_quality'),
            'conductivity_S_per_cm': record.get('conductivity_S_per_cm'),
            'raw_data_path': record.get('raw_data_path'),
            'raw_data_exists': record.get('raw_data_exists', False),
            'data_points_original': record.get('data_points_original'),
            'data_points_filtered': record.get('data_points_filtered'),
            'timestamp_str': record.get('timestamp_str')
        })
    
    return formatted


def _format_failed_records(records: List[Dict]) -> List[Dict]:
    """格式化失败记录"""
    formatted = []
    
    for record in records:
        formatted.append({
            'temperature_C': record.get('temperature_C'),
            'temperature_K': record.get('temperature_K'),
            'failure_reason': record.get('failure_reason'),
            'rb_method': record.get('rb_method'),
            'raw_data_path': record.get('raw_data_path'),
            'raw_data_exists': record.get('raw_data_exists', False),
            'debug_artifacts': record.get('debug_artifacts', []),
            'timestamp_str': record.get('timestamp_str')
        })
    
    return formatted


def _create_raw_data_mapping(successful_records: List[Dict], failed_records: List[Dict]) -> Dict:
    """创建原始数据路径映射"""
    mapping = {}
    
    all_records = successful_records + failed_records
    
    for record in all_records:
        temp_c = record.get('temperature_C')
        raw_path = record.get('raw_data_path')
        
        if temp_c is not None and raw_path:
            mapping[f"T_{temp_c:.1f}C"] = {
                'path': raw_path,
                'exists': record.get('raw_data_exists', False),
                'success': record.get('success', False)
            }
    
    return mapping


def print_report_summary(report: Dict):
    """打印报告摘要"""
    print("\n" + "="*70)
    print("📊 实验报告摘要")
    print("="*70)
    
    summary = report['summary']
    print(f"总测量点: {summary['total_measurements']}")
    print(f"成功: {summary['successful_measurements']} ({summary['success_rate']*100:.1f}%)")
    print(f"失败: {summary['failed_measurements']} ({(1-summary['success_rate'])*100:.1f}%)")
    
    # Arrhenius分析
    arrhenius = report['arrhenius_analysis']
    print(f"\nArrhenius分析:")
    if arrhenius['success']:
        print(f"  ✅ 成功分析 {len(arrhenius['segments'])} 个分段")
        for seg in arrhenius['segments']:
            print(f"  分段{seg['segment']}: Ea = {seg['Ea_kJ_per_mol']:.2f} kJ/mol, "
                  f"T = {seg['T_range_C'][0]:.1f}~{seg['T_range_C'][1]:.1f}°C ({seg['data_points']}点)")
    else:
        print(f"  ❌ {arrhenius['message']}")
    
    # 失败点详情
    if report['failed_points']:
        print(f"\n失败点详情:")
        for fp in report['failed_points']:
            print(f"  ❌ T={fp['temperature_C']:.1f}°C: {fp['failure_reason']}")
            print(f"     文件: {fp['raw_data_path']}")
    
    print("="*70 + "\n")


def generate_markdown_report(report: Dict, output_path: str = None) -> str:
    """
    生成Markdown格式的报告
    """
    if output_path is None:
        output_path = os.path.join('experiment_data', 'report.md')
    
    def fmt(val, fmt_str, default="N/A"):
        """安全格式化工具"""
        if val is None: return default
        try:
            return format(val, fmt_str)
        except (ValueError, TypeError):
            return str(val)

    lines = []
    
    # 标题
    lines.append("# 实验报告")
    lines.append(f"\n生成时间: {report['metadata']['generated_at']}")
    lines.append(f"\n---\n")
    
    # 摘要
    lines.append("## 摘要\n")
    summary = report['summary']
    lines.append(f"- **总测量点**: {summary['total_measurements']}")
    lines.append(f"- **成功**: {summary['successful_measurements']} ({summary['success_rate']*100:.1f}%)")
    lines.append(f"- **失败**: {summary['failed_measurements']} ({(1-summary['success_rate'])*100:.1f}%)")
    
    # 配置
    lines.append("\n## 实验配置\n")
    config = report['configuration']
    for key, value in config.items():
        lines.append(f"- **{key}**: {value}")
    
    # Arrhenius分析
    lines.append("\n## Arrhenius分析\n")
    arrhenius = report['arrhenius_analysis']
    if arrhenius['success']:
        lines.append(f"✅ 成功分析 {len(arrhenius['segments'])} 个分段\n")
        lines.append("| 分段 | Ea (kJ/mol) | σ₀ (S/cm) | 温度范围 (°C) | 数据点 |")
        lines.append("|------|-------------|-----------|---------------|--------|")
        for seg in arrhenius['segments']:
            lines.append(f"| {seg['segment']} | {fmt(seg['Ea_kJ_per_mol'], '.2f')} | {fmt(seg['sigma0_S_per_cm'], '.2e')} | "
                        f"{seg['T_range_C'][0]:.1f}~{seg['T_range_C'][1]:.1f} | {seg['data_points']} |")
    else:
        lines.append(f"❌ {arrhenius['message']}")
    
    # 成功点列表
    lines.append("\n## 成功测量点\n")
    if report['successful_points']:
        lines.append("| 温度 (°C) | Rb (Ω) | 拟合方法 | 拟合质量 (r) | 电导率 (S/cm) |")
        lines.append("|-----------|--------|----------|--------------|---------------|")
        for sp in report['successful_points']:
            lines.append(f"| {fmt(sp['temperature_C'], '.1f')} | {fmt(sp['rb_ohm'], '.2f')} | {sp['rb_method']} | "
                        f"{fmt(sp['fit_quality'], '.4f')} | {fmt(sp['conductivity_S_per_cm'], '.4e')} |")
    else:
        lines.append("无成功点")
    
    # 失败点列表
    lines.append("\n## 失败测量点\n")
    if report['failed_points']:
        lines.append("| 温度 (°C) | 失败原因 | 原始数据文件 |")
        lines.append("|-----------|----------|--------------|")
        for fp in report['failed_points']:
            lines.append(f"| {fmt(fp['temperature_C'], '.1f')} | {fp['failure_reason']} | `{fp['raw_data_path']}` |")
    else:
        lines.append("无失败点")
    
    # 原始数据映射
    lines.append("\n## 原始数据文件映射\n")
    lines.append("| 温度点 | 文件路径 | 存在 | 成功 |")
    lines.append("|--------|----------|------|------|")
    for temp_key, mapping in report['raw_data_mapping'].items():
        exists_icon = "✅" if mapping['exists'] else "❌"
        success_icon = "✅" if mapping['success'] else "❌"
        lines.append(f"| {temp_key} | `{mapping['path']}` | {exists_icon} | {success_icon} |")
    
    markdown_text = "\n".join(lines)
    
    # 保存到文件
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(markdown_text)
    
    print(f"✅ Markdown报告已保存: {output_path}")
    
    return markdown_text

