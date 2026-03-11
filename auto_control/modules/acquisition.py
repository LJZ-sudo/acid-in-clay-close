# -*- coding: utf-8 -*-
"""
数据获取模块：找文件 + 读文件（CHI输出解析）
"""

import os
import glob
import numpy as np
from typing import Tuple, Optional, List, Dict


def find_chi_files(data_dir: str, pattern: str = "*.txt") -> List[str]:
    """
    在指定目录查找CHI数据文件
    
    参数:
        data_dir: 数据目录路径
        pattern: 文件匹配模式
        
    返回:
        文件路径列表（按修改时间排序）
    """
    if not os.path.exists(data_dir):
        print(f"❌ 数据目录不存在: {data_dir}")
        return []
    
    search_pattern = os.path.join(data_dir, pattern)
    files = glob.glob(search_pattern)
    
    # 按修改时间排序
    files.sort(key=lambda x: os.path.getmtime(x))
    
    print(f"[查找] 在 {data_dir} 找到 {len(files)} 个文件")
    return files


def extract_temperature_from_filename(filename: str) -> Optional[float]:
    """
    从文件名提取温度
    
    支持格式：
    - PSE-2_T-99_f0.1_1000000_V0.txt  → -99.0
    - Sample_T25C_...txt              → 25.0
    
    参数:
        filename: 文件名
        
    返回:
        温度（摄氏度）或None
    """
    import re
    
    # 尝试匹配 T-99 或 T25C 格式
    patterns = [
        r'[Tt](-?\d+)[Cc]?',  # T-99 或 T25C
        r'[Tt]emp(-?\d+)',     # Temp-99
    ]
    
    for pattern in patterns:
        match = re.search(pattern, filename)
        if match:
            try:
                return float(match.group(1))
            except:
                pass
    
    return None


def _try_parse_three_floats(line: str):
    """
    尝试从一行文本中解析出3个浮点数
    支持分隔符：逗号、制表符、空白
    """
    line = line.strip()
    if not line:
        return None
    
    # 尝试不同的分隔符
    for delimiter in [',', '\t', None]:  # None表示空白分隔
        try:
            if delimiter:
                parts = line.split(delimiter)
            else:
                parts = line.split()
            
            if len(parts) < 3:
                continue
            
            freq = float(parts[0].strip())
            z_real = float(parts[1].strip())
            z_imag = float(parts[2].strip())
            return (freq, z_real, z_imag)
        except (ValueError, IndexError):
            continue
    
    return None


def read_chi_data_file(filepath: str) -> Tuple[Optional[np.ndarray], Optional[np.ndarray], Optional[np.ndarray]]:
    """
    读取CHI660E数据文件（支持动态表头定位）
    
    参数:
        filepath: 数据文件路径
        
    返回:
        (frequencies, z_real, z_imag) 或 (None, None, None)
    """
    try:
        if not os.path.exists(filepath):
            print(f"❌ 文件不存在: {filepath}")
            return None, None, None
        
        # 读取所有行
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        
        # 扫描每一行，找到第一行能解析出3个浮点数的行
        data_start_line = None
        for i, line in enumerate(lines):
            result = _try_parse_three_floats(line)
            if result is not None:
                data_start_line = i
                print(f"[找到数据起始行] 第 {i+1} 行: {line.strip()[:80]}")
                break
        
        if data_start_line is None:
            print(f"❌ 未找到有效数据行（无法解析出3个浮点数）: {filepath}")
            return None, None, None
        
        # 手动逐行解析数据（从data_start_line开始）
        data_rows = []
        for i in range(data_start_line, len(lines)):
            result = _try_parse_three_floats(lines[i])
            if result is not None:
                data_rows.append(result)
        
        if len(data_rows) == 0:
            print(f"❌ 解析到0个有效数据点: {filepath}")
            return None, None, None
        
        # 转换为numpy数组
        data = np.array(data_rows)
        frequencies = data[:, 0]
        z_real = data[:, 1]
        z_imag = data[:, 2]
        
        if len(frequencies) < 10:
            print(f"❌ 有效数据点不足10个 ({len(frequencies)}个): {filepath}")
            return None, None, None
        
        print(f"✅ 成功读取 {len(frequencies)} 个数据点")
        return frequencies, z_real, z_imag
        
    except Exception as e:
        print(f"❌ 读取文件失败 {filepath}: {e}")
        return None, None, None


def load_measurement_history(experiment_data_file: str) -> List[Dict]:
    """
    从experiment_data.json加载measurement_history
    
    参数:
        experiment_data_file: experiment_data.json文件路径
        
    返回:
        measurement_history列表
    """
    import json
    
    if not os.path.exists(experiment_data_file):
        print(f"❌ 实验数据文件不存在: {experiment_data_file}")
        return []
    
    try:
        with open(experiment_data_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if 'measurement_history' not in data:
            print(f"❌ 文件中缺少 measurement_history 字段")
            return []
        
        return data['measurement_history']
        
    except Exception as e:
        print(f"❌ 加载实验数据失败: {e}")
        return []


def match_files_to_records(chi_files: List[str], records: List[Dict]) -> Dict[int, str]:
    """
    将CHI文件匹配到measurement_history记录
    
    参数:
        chi_files: CHI文件路径列表
        records: measurement_history记录列表
        
    返回:
        {record_index: file_path} 映射
    """
    mapping = {}
    
    for i, record in enumerate(records):
        raw_path = record.get('raw_data_path')
        
        if raw_path and os.path.exists(raw_path):
            mapping[i] = raw_path
        else:
            # 尝试根据温度匹配
            temp_c = record.get('temperature_C')
            if temp_c is not None:
                for file_path in chi_files:
                    file_temp = extract_temperature_from_filename(os.path.basename(file_path))
                    if file_temp is not None and abs(file_temp - temp_c) < 0.5:
                        mapping[i] = file_path
                        break
    
    return mapping

