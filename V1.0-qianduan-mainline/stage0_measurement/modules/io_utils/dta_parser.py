# -*- coding: utf-8 -*-
"""
Gamry DTA 文件解析器（纯函数版）

用于从 Gamry 仪器的 .DTA 文件中提取：
- 时间戳（DATE/TIME LABEL）
- 实验参数（从文件名）
- 温度计算（基于时间和降温/升温速率）
- 实验阶段判断（cooling/heating/warming_up）

核心原则：
1. 纯函数 - 只接受路径参数，返回结果字典
2. 标准错误字典 - 失败时返回规范格式
3. 无副作用 - 只读取文件，不写入、不修改
4. 无 print - 错误信息放在返回字典中

版本：3.0.0 (重构版)
"""

import os
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from pathlib import Path


# ============================================================
# 公共接口：DTA 文件温度计算
# ============================================================

def calculate_temperature_from_dta(
    filepath,
    reference_time=None,
    default_start_temp_K=300.0,
    default_rate_K_per_min=1.0
):
    """
    从 DTA 文件计算温度（纯函数版主入口）
    
    Args:
        filepath: DTA 文件路径
        reference_time: 参考起始时间（datetime 对象），None 时自动查找
        default_start_temp_K: 默认起始温度（默认 300 K）
        default_rate_K_per_min: 默认温变速率（默认 1 K/min）
    
    Returns:
        dict: 包含以下字段
            - success: bool，是否成功
            - temperature_K: float，计算的温度 (K)
            - temperature_C: float，计算的温度 (°C)
            - is_valid: bool，数据是否有效
            - phase: str，实验阶段（'cooling'/'heating'/'warming_up'/'unknown'）
            - confidence: float (0-1)，温度计算的置信度
            - file_sequence: int，文件序号
            - timestamp: datetime or None，文件时间戳
            - error: str or None，失败原因
    """
    # 检查文件是否存在
    if not os.path.exists(filepath):
        return {
            'success': False,
            'temperature_K': None,
            'temperature_C': None,
            'is_valid': False,
            'phase': 'unknown',
            'confidence': 0.0,
            'file_sequence': 0,
            'timestamp': None,
            'error': f'File not found: {filepath}'
        }
    
    filename = os.path.basename(filepath)
    
    # 提取文件序号
    file_seq = _extract_file_sequence(filename)
    
    # 特殊处理：Up 文件夹（温度在文件名中）
    up_temp_result = _extract_temperature_from_up_filename(filename)
    if up_temp_result['success']:
        temp_K = up_temp_result['temperature_K']
        return {
            'success': True,
            'temperature_K': temp_K,
            'temperature_C': temp_K - 273.15,
            'is_valid': True,
            'phase': 'heating',
            'confidence': 1.0,
            'file_sequence': file_seq,
            'timestamp': None,
            'error': None
        }
    
    # 提取实验参数
    params = _extract_experiment_params_from_filename(filename)
    start_temp_K = params.get('start_temp_K', default_start_temp_K)
    target_end_temp_K = params.get('target_end_temp_K', 140.0)
    temp_rate_K_per_min = params.get('temp_rate_K_per_min', default_rate_K_per_min)
    is_heating = params.get('is_heating', False)
    
    # 读取文件时间戳
    timestamp = _extract_timestamp_from_dta(filepath)
    if timestamp is None:
        return {
            'success': False,
            'temperature_K': None,
            'temperature_C': None,
            'is_valid': False,
            'phase': 'unknown',
            'confidence': 0.0,
            'file_sequence': file_seq,
            'timestamp': None,
            'error': 'Failed to extract timestamp from DTA file'
        }
    
    # 获取参考起始时间
    if reference_time is None:
        folder_path = os.path.dirname(filepath)
        reference_time = _find_reference_start_time(folder_path, filepath)
    
    if reference_time is None:
        # 使用简化计算
        temp_result = _calculate_temperature_simple(filepath, start_temp_K, target_end_temp_K, is_heating)
        return temp_result
    
    # 基于时间计算温度
    elapsed_minutes = (timestamp - reference_time).total_seconds() / 60.0
    
    if is_heating:
        calculated_temp_K = start_temp_K + temp_rate_K_per_min * elapsed_minutes
    else:
        calculated_temp_K = start_temp_K - temp_rate_K_per_min * elapsed_minutes
    
    # 判断实验阶段和数据有效性
    phase, is_valid, confidence, final_temp_K = _determine_experiment_phase(
        calculated_temp_K=calculated_temp_K,
        target_end_temp_K=target_end_temp_K,
        is_heating=is_heating,
        elapsed_minutes=elapsed_minutes,
        start_temp_K=start_temp_K,
        temp_rate_K_per_min=temp_rate_K_per_min
    )
    
    return {
        'success': True,
        'temperature_K': final_temp_K,
        'temperature_C': final_temp_K - 273.15,
        'is_valid': is_valid,
        'phase': phase,
        'confidence': confidence,
        'file_sequence': file_seq,
        'timestamp': timestamp,
        'error': None
    }


def parse_dta_directory(
    folder_path,
    file_pattern=r'\.DTA$',
    min_files=1
):
    """
    批量解析目录中的所有 DTA 文件（纯函数版）
    
    Args:
        folder_path: 文件夹路径
        file_pattern: 文件名正则模式（默认 .DTA 结尾）
        min_files: 最少文件数（默认 1）
    
    Returns:
        dict: 包含以下字段
            - success: bool，是否成功
            - files: list[dict]，每个文件的温度计算结果
            - n_files: int，文件总数
            - n_valid: int，有效文件数
            - error: str or None，失败原因
    """
    if not os.path.exists(folder_path):
        return {
            'success': False,
            'files': [],
            'n_files': 0,
            'n_valid': 0,
            'error': f'Folder not found: {folder_path}'
        }
    
    # 递归查找所有 DTA 文件
    try:
        base_path = Path(folder_path)
        dta_files = []
        
        for file_path in base_path.rglob('*.DTA'):
            filename = file_path.name
            if re.search(file_pattern, filename, re.IGNORECASE):
                dta_files.append(str(file_path))
    except Exception as e:
        return {
            'success': False,
            'files': [],
            'n_files': 0,
            'n_valid': 0,
            'error': f'Failed to scan directory: {str(e)}'
        }
    
    if len(dta_files) < min_files:
        return {
            'success': False,
            'files': [],
            'n_files': len(dta_files),
            'n_valid': 0,
            'error': f'Insufficient DTA files ({len(dta_files)} < {min_files})'
        }
    
    # 解析每个文件
    results = []
    n_valid = 0
    
    for filepath in sorted(dta_files):
        temp_result = calculate_temperature_from_dta(filepath)
        temp_result['filepath'] = filepath
        results.append(temp_result)
        
        if temp_result.get('is_valid', False):
            n_valid += 1
    
    return {
        'success': True,
        'files': results,
        'n_files': len(results),
        'n_valid': n_valid,
        'error': None
    }


# ============================================================
# 内部函数：时间戳提取
# ============================================================

def _extract_timestamp_from_dta(filepath):
    """
    从 DTA 文件提取时间戳（内部函数）
    
    Args:
        filepath: DTA 文件路径
    
    Returns:
        datetime or None: 时间戳对象
    """
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        date_match = re.search(r'DATE\s+LABEL\s+(\d{1,2}/\d{1,2}/\d{4})', content)
        time_match = re.search(r'TIME\s+LABEL\s+(\d{1,2}:\d{2}:\d{2})', content)
        
        if date_match and time_match:
            timestamp = datetime.strptime(
                f"{date_match.group(1)} {time_match.group(1)}",
                "%m/%d/%Y %H:%M:%S"
            )
            return timestamp
    except Exception:
        pass
    
    return None


def _find_reference_start_time(folder_path, current_filepath):
    """
    查找参考起始时间（内部函数）
    
    优先级：
    1. #1 文件的时间戳
    2. 序列文件（.GSequence/.seq）的创建时间
    
    Args:
        folder_path: 文件夹路径
        current_filepath: 当前文件路径
    
    Returns:
        datetime or None: 起始时间
    """
    # 方法 1: 从 #1 文件读取时间戳
    try:
        filename = os.path.basename(current_filepath)
        first_filename = re.sub(r'#\d+', '#1', filename)
        first_file_path = os.path.join(folder_path, first_filename)
        
        if os.path.exists(first_file_path):
            first_timestamp = _extract_timestamp_from_dta(first_file_path)
            if first_timestamp:
                return first_timestamp
    except Exception:
        pass
    
    # 方法 2: 从序列文件获取创建时间
    try:
        for filename in os.listdir(folder_path):
            if filename.endswith('.GSequence') or filename.endswith('.seq'):
                file_path = os.path.join(folder_path, filename)
                modification_time = os.path.getmtime(file_path)
                return datetime.fromtimestamp(modification_time)
    except Exception:
        pass
    
    return None


# ============================================================
# 内部函数：实验参数提取
# ============================================================

def _extract_file_sequence(filename):
    """提取文件序号（内部函数）"""
    m = re.search(r'#(\d+)', filename)
    if m:
        return int(m.group(1))
    
    m = re.search(r'-(\d+)\.DTA', filename)
    if m:
        return int(m.group(1))
    
    return 1


def _extract_temperature_from_up_filename(filename):
    """从 Up 文件夹文件名提取温度（内部函数）"""
    m = re.search(r'up-(\d+)', filename.lower())
    if m:
        temp_K = float(m.group(1))
        return {
            'success': True,
            'temperature_K': temp_K
        }
    return {'success': False}


def _extract_experiment_params_from_filename(filename):
    """
    从文件名提取实验参数（内部函数）
    
    Args:
        filename: 文件名
    
    Returns:
        dict: 实验参数
    """
    params = {
        'start_temp_K': 300.0,
        'target_end_temp_K': 140.0,
        'temp_rate_K_per_min': 1.0,
        'is_heating': False
    }
    
    # 提取温度范围（如 300-140K）
    m = re.search(r'(\d+)-(\d+)K', filename)
    if m:
        temp1 = float(m.group(1))
        temp2 = float(m.group(2))
        params['start_temp_K'] = temp1
        params['target_end_temp_K'] = temp2
        params['is_heating'] = temp1 < temp2
    
    # 提取温变速率（如 1.0K-min）
    m = re.search(r'(\d+(?:\.\d+)?)K-min', filename)
    if m:
        params['temp_rate_K_per_min'] = float(m.group(1))
    
    return params


# ============================================================
# 内部函数：温度计算
# ============================================================

def _determine_experiment_phase(
    calculated_temp_K,
    target_end_temp_K,
    is_heating,
    elapsed_minutes,
    start_temp_K,
    temp_rate_K_per_min
):
    """
    判断实验阶段和数据有效性（内部函数）
    
    Args:
        calculated_temp_K: 计算的温度 (K)
        target_end_temp_K: 目标终止温度 (K)
        is_heating: 是否升温实验
        elapsed_minutes: 已经过时间（分钟）
        start_temp_K: 起始温度 (K)
        temp_rate_K_per_min: 温变速率 (K/min)
    
    Returns:
        tuple: (phase, is_valid, confidence, final_temp_K)
    """
    if is_heating:
        # 升温实验
        if calculated_temp_K <= target_end_temp_K:
            return 'heating', True, 0.95, calculated_temp_K
        else:
            return 'heating_over', True, 0.7, min(calculated_temp_K, target_end_temp_K)
    else:
        # 降温实验
        if calculated_temp_K >= target_end_temp_K:
            return 'cooling', True, 0.95, calculated_temp_K
        
        elif calculated_temp_K < target_end_temp_K:
            # 计算预期降温时间
            total_temp_drop = start_temp_K - target_end_temp_K
            expected_cooling_time = total_temp_drop / temp_rate_K_per_min
            
            if elapsed_minutes <= expected_cooling_time * 1.1:
                # 仍在正常降温范围内
                return 'cooling_end', True, 0.7, target_end_temp_K
            else:
                # 降温系统已关闭，样品开始回温
                return 'warming_up', False, 0.3, calculated_temp_K


def _calculate_temperature_simple(filepath, start_temp_K, target_end_temp_K, is_heating):
    """
    简化的温度计算（内部函数）
    
    当无法从时间戳精确计算时使用
    
    Args:
        filepath: 文件路径
        start_temp_K: 起始温度 (K)
        target_end_temp_K: 目标终止温度 (K)
        is_heating: 是否升温
    
    Returns:
        dict: 温度计算结果
    """
    filename = os.path.basename(filepath)
    file_seq = _extract_file_sequence(filename)
    
    # 假设总共 60 个文件，线性插值
    total_files = 60
    temp_per_file = abs(target_end_temp_K - start_temp_K) / (total_files - 1)
    
    if is_heating:
        calculated_temp_K = start_temp_K + (file_seq - 1) * temp_per_file
        calculated_temp_K = min(calculated_temp_K, target_end_temp_K)
    else:
        calculated_temp_K = start_temp_K - (file_seq - 1) * temp_per_file
        calculated_temp_K = max(calculated_temp_K, target_end_temp_K)
    
    is_valid = True
    confidence = 0.5
    phase = 'heating' if is_heating else 'cooling'
    
    return {
        'success': True,
        'temperature_K': calculated_temp_K,
        'temperature_C': calculated_temp_K - 273.15,
        'is_valid': is_valid,
        'phase': phase,
        'confidence': confidence,
        'file_sequence': file_seq,
        'timestamp': None,
        'error': None
    }


# ============================================================
# 辅助函数：批量解析
# ============================================================

def scan_dta_files_in_directory(folder_path, recursive=True):
    """
    扫描目录中的所有 DTA 文件（纯函数版）
    
    Args:
        folder_path: 文件夹路径
        recursive: 是否递归扫描子文件夹（默认 True）
    
    Returns:
        dict: 包含以下字段
            - success: bool
            - files: list[str]，文件路径列表（排序后）
            - n_files: int，文件数
            - error: str or None
    """
    if not os.path.exists(folder_path):
        return {
            'success': False,
            'files': [],
            'n_files': 0,
            'error': f'Folder not found: {folder_path}'
        }
    
    try:
        base_path = Path(folder_path)
        dta_files = []
        
        if recursive:
            file_iterator = base_path.rglob('*.DTA')
        else:
            file_iterator = base_path.glob('*.DTA')
        
        for file_path in file_iterator:
            dta_files.append(str(file_path))
        
        # 按文件序号排序
        def get_sort_key(filepath):
            filename = os.path.basename(filepath)
            seq = _extract_file_sequence(filename)
            return seq
        
        dta_files.sort(key=get_sort_key)
        
        return {
            'success': True,
            'files': dta_files,
            'n_files': len(dta_files),
            'error': None
        }
    
    except Exception as e:
        return {
            'success': False,
            'files': [],
            'n_files': 0,
            'error': f'Failed to scan directory: {str(e)}'
        }
