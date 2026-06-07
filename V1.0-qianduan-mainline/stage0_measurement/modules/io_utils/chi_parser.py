# -*- coding: utf-8 -*-
"""
CHI 电化学工作站数据文件解析器（纯函数版）

支持两种格式：
1. 仪器原始导出（多行表头 + 5 列数据行）：Freq/Hz, Z'/ohm, Z"/ohm, Z/ohm, Phase/deg
2. Stage 0 在线测量写出的三列文本：Frequency, Zreal, Zimag

核心原则：
1. 纯函数 - 只接受路径参数，返回数据字典
2. 标准错误字典 - 失败时返回 {"success": False, "error": "..."}
3. 无副作用 - 只读取文件，不写入、不修改
4. 无 print - 错误信息放在返回字典中

版本：3.0.0 (重构版)
"""

import os
import re
import numpy as np
from typing import Dict, List, Tuple, Optional


# ============================================================
# 公共接口：CHI 文件解析
# ============================================================

def parse_chi_file(filepath, min_points=5):
    """
    解析 CHI 数据文件（纯函数版主入口）
    
    自动识别格式：
    - 5 列逗号分隔（原始 CHI 导出）
    - 3 列空白/制表符分隔（加工格式）
    
    Args:
        filepath: 文件路径
        min_points: 最小有效点数（默认 5）
    
    Returns:
        dict: 包含以下字段
            - success: bool，是否成功
            - frequencies: np.ndarray，频率 (Hz)
            - z_real: np.ndarray，阻抗实部 (Ω)
            - z_imag: np.ndarray，阻抗虚部 (Ω)
            - n_points: int，数据点数
            - format_type: str，检测到的格式类型
            - error: str or None，失败原因
    """
    # 检查文件是否存在
    if not os.path.exists(filepath):
        return {
            'success': False,
            'frequencies': None,
            'z_real': None,
            'z_imag': None,
            'n_points': 0,
            'format_type': None,
            'error': f'File not found: {filepath}'
        }
    
    # 读取文件内容
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
    except Exception as e:
        return {
            'success': False,
            'frequencies': None,
            'z_real': None,
            'z_imag': None,
            'n_points': 0,
            'format_type': None,
            'error': f'Failed to read file: {str(e)}'
        }
    
    if not lines:
        return {
            'success': False,
            'frequencies': None,
            'z_real': None,
            'z_imag': None,
            'n_points': 0,
            'format_type': None,
            'error': 'File is empty'
        }
    
    # 解析数据行
    data_rows = []
    format_type = None
    
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        
        parsed = _try_parse_data_line(stripped)
        if parsed is not None:
            freq, zr, zi = parsed[0], parsed[1], parsed[2]
            data_rows.append((freq, zr, zi))
            
            # 检测格式类型
            if format_type is None:
                if ',' in stripped:
                    format_type = 'chi_5col_csv'
                else:
                    format_type = 'chi_3col_tsv'
    
    # 验证数据点数
    if len(data_rows) < min_points:
        return {
            'success': False,
            'frequencies': None,
            'z_real': None,
            'z_imag': None,
            'n_points': len(data_rows),
            'format_type': format_type,
            'error': f'Insufficient data points ({len(data_rows)} < {min_points})'
        }
    
    # 转换为 numpy 数组
    try:
        data = np.array(data_rows, dtype=float)
        frequencies = data[:, 0]
        z_real = data[:, 1]
        z_imag = data[:, 2]
    except Exception as e:
        return {
            'success': False,
            'frequencies': None,
            'z_real': None,
            'z_imag': None,
            'n_points': len(data_rows),
            'format_type': format_type,
            'error': f'Failed to convert to numpy arrays: {str(e)}'
        }
    
    return {
        'success': True,
        'frequencies': frequencies,
        'z_real': z_real,
        'z_imag': z_imag,
        'n_points': len(frequencies),
        'format_type': format_type,
        'error': None
    }


def parse_chi_file_with_metadata(filepath):
    """
    解析 CHI 文件并提取表头元数据（纯函数版）
    
    Args:
        filepath: 文件路径
    
    Returns:
        dict: 包含数据和元数据的完整字典
            - success: bool
            - frequencies, z_real, z_imag: 数据数组
            - n_points: 数据点数
            - format_type: 格式类型
            - metadata: 元数据字典（仪器型号、参数等）
            - error: 失败原因
    """
    # 先解析数据
    data_result = parse_chi_file(filepath)
    
    # 读取元数据
    metadata = {}
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            metadata = _parse_chi_header(lines)
        except Exception:
            metadata = {}
    
    # 合并结果
    result = {**data_result}
    result['metadata'] = metadata
    
    return result


def extract_temperature_from_filename(filename):
    """
    从文件名提取温度（纯函数版）
    
    支持的文件名模式：
      - Material_T-99_f0.1_...  → -99.0°C
      - Material_T25_f...        → 25.0°C
      - eis_-5.6C_20260114_....  → -5.6°C
    
    Args:
        filename: 文件名（可以是完整路径）
    
    Returns:
        dict: 包含以下字段
            - success: bool，是否成功提取
            - temperature_C: float or None，温度 (°C)
            - pattern: str or None，匹配的模式
            - error: str or None，失败原因
    """
    basename = os.path.basename(filename)
    
    # 模式一：_T整数_（常见 CHI 命名）
    m = re.search(r"_T(-?\d+)_", basename)
    if m:
        return {
            'success': True,
            'temperature_C': float(m.group(1)),
            'pattern': '_T{temp}_',
            'error': None
        }
    
    # 模式二：eis_浮点数C_（Stage 0 保存的 eis 文件名）
    m = re.search(r"eis_(-?\d+\.?\d*)C_", basename)
    if m:
        return {
            'success': True,
            'temperature_C': float(m.group(1)),
            'pattern': 'eis_{temp}C_',
            'error': None
        }
    
    # 模式三：泛化 T/t + 数字
    m = re.search(r"[Tt](-?\d+\.?\d*)", basename)
    if m:
        return {
            'success': True,
            'temperature_C': float(m.group(1)),
            'pattern': 'T{temp}',
            'error': None
        }
    
    return {
        'success': False,
        'temperature_C': None,
        'pattern': None,
        'error': 'No temperature pattern matched in filename'
    }


# ============================================================
# 内部函数：数据行解析
# ============================================================

def _try_parse_data_line(line):
    """
    尝试将一行文本解析为 (频率, Z', Z'')（内部函数）
    
    Args:
        line: 文本行
    
    Returns:
        tuple or None: (freq, zreal, zimag) 或 None
    """
    # 跳过明显的表头、注释行
    skip_prefixes = [
        '#', '//', 'Date', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
        'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
        'A.C.', 'File:', 'Data', 'Instrument', 'Header', 'Note',
        'Init', 'High', 'Low', 'Imp', 'Amplitude', 'Quiet', 'Cycles',
        'Freq/Hz', 'Frequency', 'Z\'', 'Z"'
    ]
    
    if any(line.startswith(prefix) for prefix in skip_prefixes):
        return None
    
    # 含逗号则按逗号切分，否则按空白切分
    if ',' in line:
        parts = [p.strip() for p in line.split(',')]
    else:
        parts = line.split()
    
    if len(parts) < 3:
        return None
    
    try:
        values = [float(p) for p in parts]
        if len(values) >= 11:
            # CHI DTA 格式（11列）：Pt, Time, Freq, Zreal, Zimag, Zsig, Zmod, Zphz, Idc, Vdc, IERange
            # 取第 2, 3, 4 列（索引从 0 开始）
            return (values[2], values[3], values[4])
        elif len(values) >= 5:
            # 原始 5 列：Freq, Z', Z", Z, Phase
            return (values[0], values[1], values[2])
        elif len(values) >= 3:
            # 3 列：Freq, Z', Z"
            return (values[0], values[1], values[2])
    except (ValueError, IndexError):
        return None
    
    return None


def _parse_chi_header(lines):
    """
    从文件前若干行提取元数据（内部函数）
    
    Args:
        lines: 文件行列表
    
    Returns:
        dict: 元数据字典
    """
    metadata = {}
    
    # 键值对模式
    kv_patterns = [
        (r'Instrument Model:\s*(.+)', 'instrument'),
        (r'Init E \(V\)\s*=\s*(.+)', 'init_e_v'),
        (r'High Frequency \(Hz\)\s*=\s*(.+)', 'high_freq_hz'),
        (r'Low Frequency \(Hz\)\s*=\s*(.+)', 'low_freq_hz'),
        (r'Amplitude \(V\)\s*=\s*(.+)', 'amplitude_v'),
        (r'Quiet Time \(sec\)\s*=\s*(.+)', 'quiet_time_s'),
    ]
    
    for line in lines[:20]:  # 只检查前 20 行
        stripped = line.strip()
        if not stripped:
            continue
        
        for pattern, key in kv_patterns:
            m = re.match(pattern, stripped)
            if m:
                metadata[key] = m.group(1).strip()
                break
        
        # 检测日期行
        if 'instrument' not in metadata and re.match(r'^[A-Z][a-z]{2}\.\s+\d+', stripped):
            metadata['date'] = stripped
    
    return metadata
