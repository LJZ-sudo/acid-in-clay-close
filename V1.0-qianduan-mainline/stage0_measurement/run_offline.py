#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
离线批处理启动程序

职责：
1. 解析命令行参数
2. 组装依赖（EIS / Arrhenius 分析器）
3. 启动 OfflineBatchWorkflow

用法：
    python run_offline.py --data_dir E:\\chi_data --material LLZO
    python run_offline.py --data_dir ./data --output_dir ./results --disable_reporting
    
版本：2.0.0 (重构版)
"""

import argparse
import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from controllers import (
    OfflineBatchWorkflow,
    OfflineConfig,
    create_default_eis_analyzer,
    create_default_arrhenius_analyzer,
)
from modules.io_utils.run_manifest import write_run_manifest
import config


def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="离线批处理程序",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    # 必需参数
    parser.add_argument(
        "--data_dir",
        type=str,
        required=True,
        help="数据目录（CHI 文件）"
    )
    
    # 基本参数
    parser.add_argument(
        "--material",
        type=str,
        default="Sample",
        help="材料名称"
    )
    parser.add_argument(
        "--output_dir",
        type=str,
        default="./offline_results",
        help="输出目录"
    )
    
    # 样品参数
    parser.add_argument(
        "--thickness",
        type=float,
        default=config.DEFAULT_THICKNESS_CM,
        help="样品厚度 (cm)"
    )
    parser.add_argument(
        "--area",
        type=float,
        default=config.DEFAULT_AREA_CM2,
        help="样品面积 (cm²)"
    )
    
    # 文件匹配
    parser.add_argument(
        "--chi_pattern",
        type=str,
        default=config.DEFAULT_CHI_FILE_PATTERN,
        help="CHI 文件匹配模式"
    )
    parser.add_argument(
        "--dta_dir",
        type=str,
        default=None,
        help="DTA 文件目录（可选）"
    )
    parser.add_argument(
        "--dta_pattern",
        type=str,
        default=config.DEFAULT_DTA_FILE_PATTERN,
        help="DTA 文件匹配模式"
    )
    
    # 错误处理
    parser.add_argument(
        "--strict_mode",
        action="store_true",
        help="严格模式（遇到错误停止）"
    )
    
    # 功能开关
    parser.add_argument(
        "--disable_arrhenius",
        action="store_true",
        help="禁用 Arrhenius 分析"
    )
    parser.add_argument(
        "--disable_reporting",
        action="store_true",
        help="禁用图表输出 (PNG)"
    )
    
    # AI 报告（预留）
    parser.add_argument(
        "--enable_ai_report",
        action="store_true",
        help="启用 AI 机理分析报告（实验性）"
    )
    parser.add_argument(
        "--ai_api_key",
        type=str,
        default=None,
        help="OpenAI API Key（用于 AI 报告）"
    )
    
    return parser.parse_args()


def create_offline_config(args):
    """创建离线配置"""
    return OfflineConfig(
        data_dir=args.data_dir,
        dta_dir=args.dta_dir,
        output_dir=args.output_dir,
        chi_file_pattern=args.chi_pattern,
        dta_file_pattern=args.dta_pattern,
        skip_failed_files=not args.strict_mode,
        continue_on_error=not args.strict_mode,
        enable_arrhenius=not args.disable_arrhenius,
        enable_reporting=not args.disable_reporting,
        material_name=args.material,
        thickness_cm=args.thickness,
        area_cm2=args.area,
    )


def main():
    """主函数"""
    print("=" * 60)
    print("🚀 离线批处理程序")
    print("=" * 60)
    
    # 1. 解析参数
    args = parse_arguments()
    
    print(f"\n📋 批处理配置:")
    print(f"   材料: {args.material}")
    print(f"   数据目录: {args.data_dir}")
    print(f"   输出目录: {args.output_dir}")
    print(f"   文件模式: {args.chi_pattern}")
    
    if args.strict_mode:
        print(f"   模式: 严格模式（遇到错误停止）")
    else:
        print(f"   模式: 宽松模式（跳过失败文件）")
    
    print(f"   Arrhenius 分析: {'启用' if not args.disable_arrhenius else '禁用'}")
    print(f"   图表输出 (PNG): {'启用' if not args.disable_reporting else '禁用'}")
    
    if args.enable_ai_report:
        print(f"   AI 报告: {'启用' if args.ai_api_key else '需要 API Key'}")
    
    # 2. 创建配置
    offline_config = create_offline_config(args)
    
    # 3. 创建分析器
    print(f"\n🔧 初始化组件...")
    
    # 3.1 EIS 分析器
    print(f"   - EIS 分析器...")
    eis_analyzer = create_default_eis_analyzer()
    if eis_analyzer:
        print(f"     ✅ EIS 分析器创建成功")
    else:
        print(f"     ⚠️ EIS 分析器不可用（将跳过 EIS 分析）")
    
    # 3.2 Arrhenius 分析器
    arrhenius_analyzer = None
    if not args.disable_arrhenius:
        print(f"   - Arrhenius 分析器...")
        arrhenius_analyzer = create_default_arrhenius_analyzer()
        if arrhenius_analyzer:
            print(f"     ✅ Arrhenius 分析器创建成功")
        else:
            print(f"     ⚠️ Arrhenius 分析器不可用")
    
    # 4. 创建工作流
    print(f"\n🎯 创建离线批处理工作流...")
    workflow = OfflineBatchWorkflow(
        config=offline_config,
        eis_analyzer=eis_analyzer,
        arrhenius_analyzer=arrhenius_analyzer,
    )
    print(f"   ✅ 工作流创建成功")
    
    # 5. 运行批处理
    print(f"\n" + "=" * 60)
    print(f"▶️ 开始批处理")
    print(f"=" * 60)
    
    try:
        result = workflow.run_batch_processing()
        write_run_manifest(Path(offline_config.output_dir) / "offline_run_manifest.json", {
            "mode": "offline",
            "material": args.material,
            "data_dir": args.data_dir,
            "output_dir": args.output_dir,
            "chi_pattern": args.chi_pattern,
            "dta_dir": args.dta_dir,
            "dta_pattern": args.dta_pattern,
            "strict_mode": args.strict_mode,
            "arrhenius_enabled": not args.disable_arrhenius,
            "reporting_enabled": not args.disable_reporting,
            "total_files": result.total_files,
            "successful_files": result.successful_files,
            "failed_files": result.failed_files,
            "duration_seconds": result.duration_seconds,
            "report_paths": result.report_paths,
            "arrhenius_success": (
                result.arrhenius_result.get("success")
                if result.arrhenius_result
                else None
            ),
        })
        
        # 6. 输出结果
        print(f"\n" + "=" * 60)
        print(f"✅ 批处理完成")
        print(f"=" * 60)
        print(f"   总文件数: {result.total_files}")
        print(f"   处理成功: {result.successful_files}")
        print(f"   处理失败: {result.failed_files}")
        print(f"   耗时: {result.duration_seconds:.2f} 秒")
        
        # Arrhenius 结果
        if result.arrhenius_result:
            print(f"\n📊 Arrhenius 分析:")
            if result.arrhenius_result.get('success'):
                print(f"   分段数: {result.arrhenius_result.get('n_segments', 0)}")
                transitions = result.arrhenius_result.get('transition_temps_K', [])
                if transitions:
                    print(f"   相变温度: {[f'{t:.2f}K' for t in transitions]}")
            else:
                print(f"   ⚠️ 分析失败: {result.arrhenius_result.get('error')}")
        
        # 图表路径（仅 PNG）
        if result.report_paths:
            print(f"\n📈 输出图表:")
            for path in result.report_paths:
                if path.lower().endswith('.png'):
                    print(f"   - {path}")
        
        # 日志
        print(f"\n📋 详细日志:")
        print(f"   查看 {offline_config.output_dir}/processing_log.txt")
        
        if result.successful_files > 0:
            print(f"\n🎉 批处理成功完成！")
            return 0
        else:
            print(f"\n⚠️ 没有成功处理的文件")
            return 1
    
    except KeyboardInterrupt:
        print(f"\n\n⚠️ 用户中断批处理")
        return 130
    
    except Exception as e:
        print(f"\n\n❌ 批处理异常: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
