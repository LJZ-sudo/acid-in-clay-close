# -*- coding: utf-8 -*-
"""
批量生成机理分析报告

为所有样品调用LLM生成机理分析报告

使用方法:
    cd close
    python phase2/run_batch_reports.py --material S8 --max 10
    python phase2/run_batch_reports.py --all --max 60
"""

import sys
import json
import requests
import time
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

# 设置项目根目录
PHASE2_ROOT = Path(__file__).resolve().parent
CLOSE_ROOT = PHASE2_ROOT.parent

# 第一轮 standalone 化：优先只使用 close 自身模块
sys.path.insert(0, str(CLOSE_ROOT))

# 解决Windows编码问题
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except:
        pass

# 导入模块
from phase2.core.sample_mechanism_generator import SampleMechanismGenerator

# API 配置（仅使用 close/config）
from config.api_config import OPENROUTER_CONFIG


def get_material_from_sample_id(sample_id: str) -> str:
    """从样品ID提取材料类型"""
    parts = sample_id.split('-')
    if parts:
        return parts[0]
    return sample_id


def is_material_allowed(material: str) -> bool:
    """检查材料是否在白名单中"""
    WHITELIST = ['S8', 'S60', 'S6', 'S12', 'S13', 'S14', 'S15', 'S16', 'S95', 'S96', 'S97']
    return material in WHITELIST


def call_llm(prompt: str, model: str = 'anthropic/claude-sonnet-4', max_tokens: int = 8000) -> Optional[str]:
    """调用LLM生成机理报告"""
    
    api_key = OPENROUTER_CONFIG['api_key']
    url = OPENROUTER_CONFIG['base_url']
    
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
        'HTTP-Referer': 'https://github.com/eis-data-analysis',
        'X-Title': 'EIS Mechanism Analysis Batch'
    }
    
    data = {
        'model': model,
        'messages': [
            {
                'role': 'system',
                'content': '你是电化学/固态离子导体专家，专门研究质子导体材料的传导机理。请用中文回答，给出详细的机理分析。'
            },
            {
                'role': 'user',
                'content': prompt
            }
        ],
        'temperature': 0.5,
        'max_tokens': max_tokens,
    }
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=180)
        
        if response.status_code == 200:
            result = response.json()
            choices = result.get('choices', [])
            if choices:
                content = choices[0].get('message', {}).get('content', '')
                error = choices[0].get('error', {})
                if error:
                    print(f"    API错误: {error.get('message', 'Unknown')[:50]}")
                    return None
                return content
        else:
            print(f"    HTTP错误: {response.status_code}")
            return None
            
    except requests.exceptions.Timeout:
        print("    超时")
        return None
    except Exception as e:
        print(f"    异常: {str(e)[:50]}")
        return None


def batch_generate_reports(
    processed_dir: Path,
    output_dir: Path,
    material_filter: Optional[str] = None,
    max_samples: int = 10,
    model: str = 'anthropic/claude-sonnet-4',
    delay_seconds: float = 2.0
):
    """
    批量生成机理报告
    
    Args:
        processed_dir: 处理结果目录
        output_dir: 输出目录
        material_filter: 只处理指定材料（如 "S8"）
        max_samples: 最大处理样品数
        model: 使用的模型
        delay_seconds: 请求间隔（秒）
    """
    print("\n" + "=" * 70)
    print("批量生成机理分析报告")
    print("=" * 70)
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"模型: {model}")
    print(f"最大样品数: {max_samples}")
    if material_filter:
        print(f"材料过滤: {material_filter}")
    
    # 收集JSON文件
    all_files = list(processed_dir.glob("*_analysis_result.json"))
    
    # 过滤
    json_files = []
    for f in all_files:
        sample_id = f.stem.replace("_analysis_result", "")
        material = get_material_from_sample_id(sample_id)
        
        if not is_material_allowed(material):
            continue
        
        if material_filter and material != material_filter:
            continue
        
        json_files.append(f)
    
    print(f"\n发现 {len(all_files)} 个文件，过滤后 {len(json_files)} 个")
    
    # 限制数量
    json_files = sorted(json_files)[:max_samples]
    print(f"本次处理: {len(json_files)} 个样品")
    
    # 创建输出目录
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 初始化生成器
    generator = SampleMechanismGenerator()
    
    # 统计
    results = {
        'total': len(json_files),
        'success': 0,
        'failed': 0,
        'skipped': 0,
        'samples': []
    }
    
    print("\n" + "-" * 70)
    
    for i, json_file in enumerate(json_files, 1):
        sample_id = json_file.stem.replace("_analysis_result", "")
        print(f"\n[{i}/{len(json_files)}] {sample_id}")
        
        # 检查是否已存在报告
        report_file = output_dir / f"{sample_id}_mechanism_report.md"
        if report_file.exists():
            print(f"  [SKIP] 报告已存在")
            results['skipped'] += 1
            continue
        
        # 1. 生成提示词
        print("  生成提示词...")
        try:
            result = generator.generate_from_file(json_file)
            if result['error']:
                print(f"  提示词错误: {result['error']}")
                results['failed'] += 1
                continue
            
            prompt = result['prompt']
            print(f"  提示词长度: {len(prompt)} 字符")
        except Exception as e:
            print(f"  异常: {e}")
            results['failed'] += 1
            continue
        
        # 2. 调用LLM
        print(f"  调用 {model}...")
        llm_response = call_llm(prompt, model=model, max_tokens=8000)
        
        if llm_response and len(llm_response) > 100:
            # 保存报告
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write(f"# {sample_id} 机理分析报告\n\n")
                f.write(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"**模型**: {model}\n\n")
                f.write("---\n\n")
                f.write(llm_response)
            
            print(f"  [OK] 成功! 报告长度: {len(llm_response)} 字符")
            results['success'] += 1
            results['samples'].append({
                'sample_id': sample_id,
                'success': True,
                'report_length': len(llm_response)
            })
        else:
            print(f"  [FAIL] 失败")
            results['failed'] += 1
            results['samples'].append({
                'sample_id': sample_id,
                'success': False
            })
        
        # 延迟，避免API限流
        if i < len(json_files):
            time.sleep(delay_seconds)
    
    # 保存统计结果
    stats_file = output_dir / "batch_stats.json"
    with open(stats_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    # 打印总结
    print("\n" + "=" * 70)
    print("批量处理完成!")
    print("=" * 70)
    print(f"总计: {results['total']}")
    print(f"成功: {results['success']}")
    print(f"跳过: {results['skipped']}")
    print(f"失败: {results['failed']}")
    print(f"输出目录: {output_dir}")
    
    return results


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='批量生成机理分析报告')
    parser.add_argument('--material', type=str, default=None, help='材料类型 (默认处理所有白名单材料)')
    parser.add_argument('--max', type=int, default=60, help='最大样品数 (默认60)')
    parser.add_argument('--model', type=str, default='anthropic/claude-sonnet-4', help='模型')
    parser.add_argument('--delay', type=float, default=2.0, help='请求间隔秒数')
    parser.add_argument('--all', action='store_true', help='处理所有白名单材料')
    
    args = parser.parse_args()
    
    # 使用close中的目录
    processed_dir = CLOSE_ROOT / "output" / "phase1_results"
    output_dir = CLOSE_ROOT / "output" / "phase2_reports"
    
    # 如果指定--all，则material_filter为None
    material_filter = None if args.all else args.material
    
    batch_generate_reports(
        processed_dir=processed_dir,
        output_dir=output_dir,
        material_filter=material_filter,
        max_samples=args.max,
        model=args.model,
        delay_seconds=args.delay
    )
