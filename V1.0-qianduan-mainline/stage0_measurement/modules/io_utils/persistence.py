# -*- coding: utf-8 -*-
"""
持久化工具：纯粹的文件读写（纯函数版）

专注于文件系统操作：
- JSON 读写（原子操作、UTF-8、错误处理）
- 文本文件读写
- 目录管理

核心原则：
1. 纯函数 - 只接受路径和数据，返回结果字典
2. 标准错误字典 - 失败时返回规范格式
3. 无业务逻辑 - 不拼装业务数据，只负责文件 I/O
4. 无 print - 错误信息放在返回字典中

版本：3.0.0 (重构版)
"""

import json
import os
from typing import Any, Dict, List, Optional


# ============================================================
# 公共接口：JSON 读写
# ============================================================

def save_json(data, filepath, indent=2, ensure_ascii=False, create_dirs=True):
    """
    将数据保存为 JSON 文件（纯函数版）
    
    Args:
        data: 可序列化的数据（dict, list, etc.）
        filepath: 目标文件路径
        indent: 缩进（默认 2 空格）
        ensure_ascii: 是否强制 ASCII（默认 False，支持中文）
        create_dirs: 是否自动创建父目录（默认 True）
    
    Returns:
        dict: 包含以下字段
            - success: bool，是否成功
            - filepath: str，写入的文件路径（绝对路径）
            - bytes_written: int，写入的字节数
            - error: str or None，失败原因
    """
    try:
        abs_path = os.path.abspath(filepath)
        
        # 创建父目录
        if create_dirs:
            parent_dir = os.path.dirname(abs_path)
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)
        
        # 写入 JSON
        with open(abs_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=indent, ensure_ascii=ensure_ascii, default=str)
        
        # 获取文件大小
        file_size = os.path.getsize(abs_path)
        
        return {
            'success': True,
            'filepath': abs_path,
            'bytes_written': file_size,
            'error': None
        }
    
    except Exception as e:
        return {
            'success': False,
            'filepath': os.path.abspath(filepath) if filepath else None,
            'bytes_written': 0,
            'error': f'Failed to save JSON: {str(e)}'
        }


def load_json(filepath, default_value=None):
    """
    从 JSON 文件加载数据（纯函数版）
    
    Args:
        filepath: JSON 文件路径
        default_value: 文件不存在时的默认值（默认 None）
    
    Returns:
        dict: 包含以下字段
            - success: bool，是否成功
            - data: Any，加载的数据
            - filepath: str，读取的文件路径（绝对路径）
            - error: str or None，失败原因
    """
    # 文件不存在时返回默认值
    if not os.path.exists(filepath):
        if default_value is not None:
            return {
                'success': True,
                'data': default_value,
                'filepath': os.path.abspath(filepath),
                'error': None
            }
        else:
            return {
                'success': False,
                'data': None,
                'filepath': os.path.abspath(filepath),
                'error': f'File not found: {filepath}'
            }
    
    try:
        abs_path = os.path.abspath(filepath)
        with open(abs_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return {
            'success': True,
            'data': data,
            'filepath': abs_path,
            'error': None
        }
    
    except Exception as e:
        return {
            'success': False,
            'data': default_value,
            'filepath': os.path.abspath(filepath),
            'error': f'Failed to load JSON: {str(e)}'
        }


# ============================================================
# 公共接口：文本文件读写
# ============================================================

def save_text(content, filepath, encoding='utf-8', create_dirs=True):
    """
    保存文本文件（纯函数版）
    
    Args:
        content: 文本内容（字符串）
        filepath: 目标文件路径
        encoding: 编码（默认 UTF-8）
        create_dirs: 是否自动创建父目录（默认 True）
    
    Returns:
        dict: 包含以下字段
            - success: bool
            - filepath: str，绝对路径
            - bytes_written: int
            - error: str or None
    """
    try:
        abs_path = os.path.abspath(filepath)
        
        # 创建父目录
        if create_dirs:
            parent_dir = os.path.dirname(abs_path)
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)
        
        # 写入文件
        with open(abs_path, 'w', encoding=encoding) as f:
            f.write(content)
        
        file_size = os.path.getsize(abs_path)
        
        return {
            'success': True,
            'filepath': abs_path,
            'bytes_written': file_size,
            'error': None
        }
    
    except Exception as e:
        return {
            'success': False,
            'filepath': os.path.abspath(filepath) if filepath else None,
            'bytes_written': 0,
            'error': f'Failed to save text: {str(e)}'
        }


def load_text(filepath, encoding='utf-8', default_value=None):
    """
    加载文本文件（纯函数版）
    
    Args:
        filepath: 文件路径
        encoding: 编码（默认 UTF-8）
        default_value: 文件不存在时的默认值（默认 None）
    
    Returns:
        dict: 包含以下字段
            - success: bool
            - content: str or None，文件内容
            - filepath: str，绝对路径
            - error: str or None
    """
    if not os.path.exists(filepath):
        if default_value is not None:
            return {
                'success': True,
                'content': default_value,
                'filepath': os.path.abspath(filepath),
                'error': None
            }
        else:
            return {
                'success': False,
                'content': None,
                'filepath': os.path.abspath(filepath),
                'error': f'File not found: {filepath}'
            }
    
    try:
        abs_path = os.path.abspath(filepath)
        with open(abs_path, 'r', encoding=encoding) as f:
            content = f.read()
        
        return {
            'success': True,
            'content': content,
            'filepath': abs_path,
            'error': None
        }
    
    except Exception as e:
        return {
            'success': False,
            'content': default_value,
            'filepath': os.path.abspath(filepath),
            'error': f'Failed to load text: {str(e)}'
        }


# ============================================================
# 公共接口：目录管理
# ============================================================

def ensure_directory(dirpath):
    """
    确保目录存在（纯函数版）
    
    Args:
        dirpath: 目录路径
    
    Returns:
        dict: 包含以下字段
            - success: bool
            - dirpath: str，绝对路径
            - created: bool，是否新创建
            - error: str or None
    """
    try:
        abs_path = os.path.abspath(dirpath)
        existed = os.path.exists(abs_path)
        
        os.makedirs(abs_path, exist_ok=True)
        
        return {
            'success': True,
            'dirpath': abs_path,
            'created': not existed,
            'error': None
        }
    
    except Exception as e:
        return {
            'success': False,
            'dirpath': os.path.abspath(dirpath) if dirpath else None,
            'created': False,
            'error': f'Failed to create directory: {str(e)}'
        }


def list_files(dirpath, extension=None, recursive=False):
    """
    列出目录中的文件（纯函数版）
    
    Args:
        dirpath: 目录路径
        extension: 文件扩展名过滤（如 '.json'，None 表示所有文件）
        recursive: 是否递归扫描子目录（默认 False）
    
    Returns:
        dict: 包含以下字段
            - success: bool
            - files: list[str]，文件路径列表（绝对路径）
            - n_files: int，文件数
            - dirpath: str，扫描的目录（绝对路径）
            - error: str or None
    """
    if not os.path.exists(dirpath):
        return {
            'success': False,
            'files': [],
            'n_files': 0,
            'dirpath': os.path.abspath(dirpath),
            'error': f'Directory not found: {dirpath}'
        }
    
    try:
        abs_path = os.path.abspath(dirpath)
        files = []
        
        if recursive:
            # 递归扫描
            for root, _, filenames in os.walk(abs_path):
                for filename in filenames:
                    if extension is None or filename.endswith(extension):
                        files.append(os.path.join(root, filename))
        else:
            # 仅扫描当前目录
            for filename in os.listdir(abs_path):
                filepath = os.path.join(abs_path, filename)
                if os.path.isfile(filepath):
                    if extension is None or filename.endswith(extension):
                        files.append(filepath)
        
        files.sort()
        
        return {
            'success': True,
            'files': files,
            'n_files': len(files),
            'dirpath': abs_path,
            'error': None
        }
    
    except Exception as e:
        return {
            'success': False,
            'files': [],
            'n_files': 0,
            'dirpath': os.path.abspath(dirpath),
            'error': f'Failed to list files: {str(e)}'
        }


def check_file_exists(filepath):
    """
    检查文件是否存在（纯函数版）
    
    Args:
        filepath: 文件路径
    
    Returns:
        dict: 包含以下字段
            - exists: bool
            - filepath: str，绝对路径
            - is_file: bool，是否为文件
            - is_dir: bool，是否为目录
            - size: int or None，文件大小（字节）
    """
    abs_path = os.path.abspath(filepath)
    exists = os.path.exists(abs_path)
    
    if exists:
        is_file = os.path.isfile(abs_path)
        is_dir = os.path.isdir(abs_path)
        size = os.path.getsize(abs_path) if is_file else None
    else:
        is_file = False
        is_dir = False
        size = None
    
    return {
        'exists': exists,
        'filepath': abs_path,
        'is_file': is_file,
        'is_dir': is_dir,
        'size': size
    }


# ============================================================
# 辅助函数：JSON 安全转换
# ============================================================

def make_json_safe(obj):
    """
    将对象转换为 JSON 安全的格式（纯函数版）
    
    处理：
    - numpy 数组 → list
    - numpy 标量 → Python 标量
    - datetime → ISO 字符串
    - 递归处理 dict, list
    
    Args:
        obj: 任意对象
    
    Returns:
        JSON 安全的对象
    """
    # numpy 数组
    if hasattr(obj, 'tolist'):
        return obj.tolist()
    
    # numpy 标量
    if hasattr(obj, 'item'):
        return obj.item()
    
    # datetime 对象
    if hasattr(obj, 'isoformat'):
        return obj.isoformat()
    
    # 字典
    if isinstance(obj, dict):
        return {k: make_json_safe(v) for k, v in obj.items()}
    
    # 列表/元组
    if isinstance(obj, (list, tuple)):
        return [make_json_safe(item) for item in obj]
    
    # 基础类型
    if isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    
    # 其他类型：转为字符串
    return str(obj)


# ============================================================
# 辅助函数：批量操作
# ============================================================

def save_multiple_json(data_dict, base_dir, create_dirs=True):
    """
    批量保存多个 JSON 文件（纯函数版）
    
    Args:
        data_dict: dict[str, Any]，{文件名: 数据}
        base_dir: 基础目录路径
        create_dirs: 是否自动创建目录（默认 True）
    
    Returns:
        dict: 包含以下字段
            - success: bool，是否全部成功
            - results: list[dict]，每个文件的保存结果
            - n_success: int，成功数
            - n_failed: int，失败数
            - error: str or None
    """
    if create_dirs:
        dir_result = ensure_directory(base_dir)
        if not dir_result['success']:
            return {
                'success': False,
                'results': [],
                'n_success': 0,
                'n_failed': 0,
                'error': dir_result['error']
            }
    
    results = []
    n_success = 0
    n_failed = 0
    
    for filename, data in data_dict.items():
        filepath = os.path.join(base_dir, filename)
        result = save_json(data, filepath, create_dirs=False)
        result['filename'] = filename
        results.append(result)
        
        if result['success']:
            n_success += 1
        else:
            n_failed += 1
    
    return {
        'success': n_failed == 0,
        'results': results,
        'n_success': n_success,
        'n_failed': n_failed,
        'error': None
    }


def load_multiple_json(filenames, base_dir):
    """
    批量加载多个 JSON 文件（纯函数版）
    
    Args:
        filenames: list[str]，文件名列表
        base_dir: 基础目录路径
    
    Returns:
        dict: 包含以下字段
            - success: bool，是否全部成功
            - data: dict[str, Any]，{文件名: 数据}
            - n_success: int
            - n_failed: int
            - error: str or None
    """
    data_dict = {}
    n_success = 0
    n_failed = 0
    
    for filename in filenames:
        filepath = os.path.join(base_dir, filename)
        result = load_json(filepath)
        
        if result['success']:
            data_dict[filename] = result['data']
            n_success += 1
        else:
            n_failed += 1
    
    return {
        'success': n_failed == 0,
        'data': data_dict,
        'n_success': n_success,
        'n_failed': n_failed,
        'error': None if n_failed == 0 else f'{n_failed} files failed to load'
    }


# ============================================================
# 辅助函数：EIS 数据文件写入
# ============================================================

def save_eis_data_tsv(
    frequencies,
    z_real,
    z_imag,
    filepath,
    header="Frequency\tZreal\tZimag",
    create_dirs=True
):
    """
    保存 EIS 数据为三列 TSV 文件（纯函数版）
    
    Args:
        frequencies: 频率数组
        z_real: 阻抗实部数组
        z_imag: 阻抗虚部数组
        filepath: 目标文件路径
        header: 表头（默认 "Frequency\tZreal\tZimag"）
        create_dirs: 是否自动创建父目录（默认 True）
    
    Returns:
        dict: 包含以下字段
            - success: bool
            - filepath: str，绝对路径
            - n_points: int，数据点数
            - bytes_written: int
            - error: str or None
    """
    try:
        # 验证数据长度
        if not (len(frequencies) == len(z_real) == len(z_imag)):
            return {
                'success': False,
                'filepath': os.path.abspath(filepath) if filepath else None,
                'n_points': 0,
                'bytes_written': 0,
                'error': 'Data arrays have different lengths'
            }
        
        abs_path = os.path.abspath(filepath)
        
        # 创建父目录
        if create_dirs:
            parent_dir = os.path.dirname(abs_path)
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)
        
        # 构建内容
        lines = [header]
        for f, zr, zi in zip(frequencies, z_real, z_imag):
            lines.append(f"{f}\t{zr}\t{zi}")
        
        content = '\n'.join(lines) + '\n'
        
        # 写入文件
        with open(abs_path, 'w', encoding='utf-8') as file:
            file.write(content)
        
        file_size = os.path.getsize(abs_path)
        
        return {
            'success': True,
            'filepath': abs_path,
            'n_points': len(frequencies),
            'bytes_written': file_size,
            'error': None
        }
    
    except Exception as e:
        return {
            'success': False,
            'filepath': os.path.abspath(filepath) if filepath else None,
            'n_points': 0,
            'bytes_written': 0,
            'error': f'Failed to save EIS data: {str(e)}'
        }
