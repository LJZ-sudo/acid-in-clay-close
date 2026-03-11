# -*- coding: utf-8 -*-
"""
闭环流程主入口脚本

功能：
1. 读取 experiment_data.json 中的 measurement_history
2. 对每个温度点：读取真实文件 → 解析 → filter_data → Rb拟合 → 更新记录
3. 全部温度点结束：自动做 Arrhenius 分析
4. 生成最终报告 report.json 和 report.md

使用方法：
    python auto_control/run_closed_loop.py --data-dir E:\chi_data --config experiment_data/experiment_data.json
"""

import os
import sys
import json
import argparse
from pathlib import Path
from typing import Optional

# 统一 standalone 路径初始化
try:
    from auto_control._path_setup import ensure_close_root
except ImportError:
    from _path_setup import ensure_close_root

CLOSE_ROOT = ensure_close_root()

# 导入模块
from auto_control.modules.acquisition import (
    find_chi_files, read_chi_data_file, extract_temperature_from_filename,
    load_measurement_history, match_files_to_records
)
from auto_control.modules.rb_fit import perform_rb_fitting, assess_fit_quality
from auto_control.modules.arrhenius import perform_arrhenius_analysis, generate_arrhenius_plot_data
from auto_control.modules.report import generate_report, print_report_summary, generate_markdown_report


def process_single_temperature_point(
    file_path: str,
    temperature_C: float,
    thickness: float,
    area: float,
    circle_dir: str
) -> dict:
    """
    处理单个温度点
    
    返回:
        完整的测量记录字典
    """
    print(f"\n[处理] T={temperature_C:.1f}°C, 文件: {file_path}")
    
    # 1. 读取数据
    frequencies, z_real, z_imag = read_chi_data_file(file_path)
    
    if frequencies is None:
        return {
            'temperature_C': temperature_C,
            'temperature_K': temperature_C + 273.15,
            'raw_data_path': file_path,
            'raw_data_exists': os.path.exists(file_path),
            'success': False,
            'failure_reason': '数据文件读取失败',
            'rb_ohm': None,
            'rb_method': '读取失败',
            'fit_quality': None,
            'conductivity_S_per_cm': None
        }
    
    print(f"  ✅ 读取 {len(frequencies)} 个数据点")
    
    # 2. Rb拟合
    fit_result = perform_rb_fitting(
        frequencies, z_real, z_imag,
        temperature_C, thickness, area, circle_dir
    )
    
    # 3. 质量评估
    quality = assess_fit_quality(fit_result)
    
    # 4. 构建记录
    record = {
        'temperature_C': temperature_C,
        'temperature_K': temperature_C + 273.15,
        'raw_data_path': file_path,
        'raw_data_exists': os.path.exists(file_path),
        'success': fit_result['success'],
        'failure_reason': fit_result.get('failure_reason'),
        'rb_ohm': fit_result['rb_ohm'],
        'rb_method': fit_result['rb_method'],
        'fit_quality': fit_result['fit_quality'],
        'conductivity_S_per_cm': fit_result['conductivity_S_per_cm'],
        'data_points_original': fit_result['data_points_original'],
        'data_points_filtered': fit_result['data_points_filtered'],
        'quality_grade': quality
    }
    
    if fit_result['success']:
        print(f"  ✅ 成功: Rb={fit_result['rb_ohm']:.2f}Ω, σ={fit_result['conductivity_S_per_cm']:.4e} S/cm, 质量={quality}")
    else:
        print(f"  ❌ 失败: {fit_result.get('failure_reason')}")
    
    return record


def run_closed_loop(
    data_dir: str,
    config_file: Optional[str] = None,
    thickness: float = 0.01,
    area: float = 1.0,
    min_arrhenius_points: int = 5,
    output_dir: str = 'experiment_data',
    bundle_report: bool = False,
    ai_eval: bool = False,
    export_pdf: bool = False,
    mechanism: bool = False,
    mechanism_out: str = 'experiment_data',
    mechanism_write_report: bool = False,
):
    """
    运行完整的闭环流程
    
    参数:
        data_dir: CHI数据目录（如 E:\chi_data）
        config_file: 实验配置文件（如 experiment_data/experiment_data.json）
        thickness: 样品厚度（cm）
        area: 样品面积（cm²）
        min_arrhenius_points: Arrhenius分析最少数据点要求
        output_dir: 输出目录
    """
    print("="*70)
    print("🔬 闭环流程启动")
    print("="*70)
    print(f"数据目录: {data_dir}")
    print(f"配置文件: {config_file}")
    print(f"样品参数: 厚度={thickness}cm, 面积={area}cm²")
    print(f"Arrhenius最少点数: {min_arrhenius_points}")
    print("="*70)
    
    # 创建输出目录
    os.makedirs(output_dir, exist_ok=True)
    circle_dir = os.path.join(output_dir, 'circle_fits')
    os.makedirs(circle_dir, exist_ok=True)
    
    # ==================== 阶段1：数据获取 ====================
    print("\n[阶段1] 数据获取")
    
    # 查找CHI文件
    chi_files = find_chi_files(data_dir, "*.txt")
    
    if not chi_files:
        print("❌ 未找到CHI数据文件，退出")
        return None
    
    # 加载现有的measurement_history（如果有）
    measurement_history = []
    if config_file and os.path.exists(config_file):
        print(f"[加载] 从 {config_file} 加载现有记录")
        measurement_history = load_measurement_history(config_file)
        print(f"  已加载 {len(measurement_history)} 条记录")
    
    # 匹配文件到记录
    if measurement_history:
        file_mapping = match_files_to_records(chi_files, measurement_history)
        print(f"  匹配成功 {len(file_mapping)} 个文件")
    else:
        # 如果没有现有记录，直接从文件名提取温度
        file_mapping = {}
        for i, file_path in enumerate(chi_files):
            temp_c = extract_temperature_from_filename(os.path.basename(file_path))
            if temp_c is not None:
                file_mapping[i] = file_path
                # 创建占位记录
                measurement_history.append({
                    'temperature_C': temp_c,
                    'temperature_K': temp_c + 273.15,
                    'raw_data_path': file_path
                })
    
    print(f"  总共 {len(file_mapping)} 个温度点待处理")
    
    # ==================== 阶段2：逐点处理 ====================
    print("\n[阶段2] 逐点Rb拟合")
    
    all_records = []
    
    for idx, file_path in file_mapping.items():
        # 获取温度
        if idx < len(measurement_history):
            temp_c = measurement_history[idx].get('temperature_C')
        else:
            temp_c = extract_temperature_from_filename(os.path.basename(file_path))
        
        if temp_c is None:
            print(f"⚠️ 无法确定温度，跳过文件: {file_path}")
            continue
        
        # 处理单个温度点
        record = process_single_temperature_point(
            file_path, temp_c, thickness, area, circle_dir
        )
        
        all_records.append(record)
    
    # 分离成功和失败记录
    successful_records = [r for r in all_records if r.get('success')]
    failed_records = [r for r in all_records if not r.get('success')]
    
    print(f"\n[汇总] 成功: {len(successful_records)}, 失败: {len(failed_records)}")
    
    # ==================== 阶段3：Arrhenius分析 ====================
    print("\n[阶段3] Arrhenius分析")
    
    arrhenius_result = perform_arrhenius_analysis(
        successful_records,
        min_points=min_arrhenius_points
    )
    
    if arrhenius_result['success']:
        print(f"  ✅ 成功分析 {len(arrhenius_result['segments'])} 个分段")
        for seg in arrhenius_result['segments']:
            print(f"    分段{seg['segment']}: Ea={seg['Ea_kJ_per_mol']:.2f} kJ/mol, "
                  f"T={seg['T_range_C'][0]:.1f}~{seg['T_range_C'][1]:.1f}°C ({seg['data_points']}点)")
    else:
        print(f"  ❌ {arrhenius_result['message']}")
    
    # ==================== 阶段4：生成报告 ====================
    print("\n[阶段4] 生成报告")
    
    config = {
        'data_directory': data_dir,
        'thickness_cm': thickness,
        'area_cm2': area,
        'min_arrhenius_points': min_arrhenius_points,
        'total_files_found': len(chi_files),
        'total_files_processed': len(all_records)
    }
    
    report_json_path = os.path.join(output_dir, 'report.json')
    report_md_path = os.path.join(output_dir, 'report.md')
    
    report = generate_report(
        successful_records,
        failed_records,
        arrhenius_result,
        config,
        output_path=report_json_path
    )
    
    generate_markdown_report(report, output_path=report_md_path)
    
    if bundle_report:
        try:
            from auto_control.modules.report_bundle import bundle_report as do_bundle_report
        except ImportError:
            from modules.report_bundle import bundle_report as do_bundle_report
        
        print("\n[附加] 生成报告打包产物")
        bundle_outputs = do_bundle_report(
            report_json_path,
            output_dir,
            enable_ai_eval=ai_eval,
            enable_pdf=export_pdf,
        )
        if bundle_outputs:
            print("  ✅ 打包完成")
            for k, v in bundle_outputs.items():
                if v:
                    print(f"  - {k}: {v}")
        else:
            print("  ⚠️ 打包过程未生成输出")
        
        # 🔥 机理分析报告已整合到 bundle_report 中，无需单独生成

    if mechanism:
        try:
            from auto_control.modules.mechanism_report import write_mechanism_artifacts
        except ImportError:
            from modules.mechanism_report import write_mechanism_artifacts
        print("\n[附加] 生成机理分析输入")
        mech_outputs = write_mechanism_artifacts(
            report_json_path,
            mechanism_out,
            write_prompt=True,
            write_evidence=True,
            write_stub_report=mechanism_write_report,
        )
        if mech_outputs:
            print("  ✅ 机理输入生成完成")
            for k, v in mech_outputs.items():
                if v:
                    print(f"  - {k}: {v}")
        else:
            print("  ⚠️ 机理输入未生成")
    
    # 打印摘要
    print_report_summary(report)
    
    print("="*70)
    print("✅ 闭环流程完成")
    print("="*70)
    print(f"📄 JSON报告: {report_json_path}")
    print(f"📄 Markdown报告: {report_md_path}")
    print("="*70)
    
    return report


def main():
    parser = argparse.ArgumentParser(description='闭环流程：自动处理EIS数据并生成报告')
    parser.add_argument('--data-dir', type=str, default=r'E:\chi_data',
                        help='CHI数据目录路径')
    parser.add_argument('--config', type=str, default=None,
                        help='实验配置文件路径（可选，用于加载现有measurement_history）')
    parser.add_argument('--thickness', type=float, default=0.01,
                        help='样品厚度（cm），默认0.01')
    parser.add_argument('--area', type=float, default=1.0,
                        help='样品面积（cm²），默认1.0')
    parser.add_argument('--min-points', type=int, default=5,
                        help='Arrhenius分析最少数据点，默认5')
    parser.add_argument('--output-dir', type=str, default='experiment_data',
                        help='输出目录，默认experiment_data')
    parser.add_argument('--bundle-report', action='store_true', default=False,
                        help='生成完整报告打包 (conductivity_plot.png, analysis_report.md, mechanism_report.md 等)')
    parser.add_argument('--ai-eval', action='store_true', default=False,
                        help='启用AI评述（需 DEEPSEEK_API_KEY/OPENAI_API_KEY）')
    parser.add_argument('--export-pdf', action='store_true', default=False,
                        help='如果检测到LaTeX则导出PDF')
    parser.add_argument('--mechanism', action='store_true', default=False,
                        help='生成机理分析输入 (prompt/evidence/可选模板报告)')
    parser.add_argument('--mechanism-out', type=str, default='experiment_data',
                        help='机理分析产物输出目录')
    parser.add_argument('--mechanism-write-report', action='store_true', default=False,
                        help='生成机理分析模板报告 mechanism_report.md')
    
    args = parser.parse_args()
    
    # 运行闭环流程
    report = run_closed_loop(
        data_dir=args.data_dir,
        config_file=args.config,
        thickness=args.thickness,
        area=args.area,
        min_arrhenius_points=args.min_points,
        output_dir=args.output_dir,
        bundle_report=args.bundle_report,
        ai_eval=args.ai_eval,
        export_pdf=args.export_pdf,
        mechanism=args.mechanism,
        mechanism_out=args.mechanism_out,
        mechanism_write_report=args.mechanism_write_report,
    )
    
    if report is None:
        sys.exit(1)
    
    sys.exit(0)


if __name__ == '__main__':
    main()

