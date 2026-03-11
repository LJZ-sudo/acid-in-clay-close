# -*- coding: utf-8 -*-
"""
Step 1: 解析原始EIS文件
=======================

输入: data/raw_eis/{material}/{sample_id}/.../*.seq
输出: output/phase1_results/{sample_id}_raw_data.json

功能:
1. 扫描所有原始EIS文件（.seq, .GSequence等）
2. 解析频率、阻抗数据
3. 提取温度信息（从文件名或目录名）
4. 输出结构化JSON

TODO: 从现有项目迁移EIS解析逻辑
"""

import sys
from pathlib import Path

# 统一 standalone 路径初始化
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import get_material_params


def find_eis_files(data_dir: Path = None):
    """
    查找所有EIS原始数据文件
    
    Returns:
        List[dict]: [{sample_id, material, file_path, temp_info}, ...]
    """
    if data_dir is None:
        data_dir = PROJECT_ROOT / "data" / "raw_eis"
    
    eis_files = []
    
    # 遍历材料文件夹
    for material_dir in data_dir.iterdir():
        if not material_dir.is_dir():
            continue
        
        material = material_dir.name
        
        # 遍历样品文件夹
        for sample_dir in material_dir.iterdir():
            if not sample_dir.is_dir():
                continue
            
            sample_id = sample_dir.name
            
            # 查找.seq和.GSequence文件
            seq_files = list(sample_dir.rglob("*.seq"))
            gseq_files = list(sample_dir.rglob("*.GSequence"))
            
            for f in seq_files + gseq_files:
                # 尝试从路径提取温度信息
                temp_info = extract_temp_from_path(f)
                
                eis_files.append({
                    'sample_id': sample_id,
                    'material': material,
                    'file_path': str(f),
                    'temp_info': temp_info,
                })
    
    return eis_files


def extract_temp_from_path(file_path: Path) -> dict:
    """
    从文件路径提取温度范围信息
    
    例如: "300-140K 1K-min" → {T_start: 300, T_end: 140, rate: 1}
    """
    path_str = str(file_path)
    
    # TODO: 解析温度信息
    # 常见格式: "300-140K", "300-200K 0.3K-min"
    
    return {
        'T_start_K': None,
        'T_end_K': None,
        'rate_K_per_min': None,
    }


def parse_seq_file(file_path: Path) -> dict:
    """
    解析.seq文件
    
    Returns:
        {
            frequencies: List[float],
            Z_real: List[float],
            Z_imag: List[float],
            temperatures: List[float],
            ...
        }
    
    TODO: 从现有项目迁移解析逻辑
    """
    # 占位符 - 需要迁移实际的解析代码
    return {
        'frequencies': [],
        'Z_real': [],
        'Z_imag': [],
        'temperatures': [],
        'raw_data': None,
    }


def main():
    """主函数"""
    print("=" * 70)
    print("Step 1: 解析原始EIS文件")
    print("=" * 70)
    
    # 查找所有EIS文件
    eis_files = find_eis_files()
    
    print(f"\n找到 {len(eis_files)} 个EIS文件")
    
    # 按材料统计
    materials = {}
    for f in eis_files:
        mat = f['material']
        if mat not in materials:
            materials[mat] = 0
        materials[mat] += 1
    
    print("\n按材料统计:")
    for mat, count in sorted(materials.items()):
        print(f"  {mat}: {count} 个文件")
    
    # TODO: 解析每个文件并保存结果
    print("\n注意: 实际解析逻辑需要从现有项目迁移")


if __name__ == '__main__':
    main()
