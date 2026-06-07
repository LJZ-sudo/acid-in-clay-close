# -*- coding: utf-8 -*-
"""
I/O 工具包：纯函数化的数据读取与持久化

子模块：
- chi_parser: CHI 电化学工作站数据文件解析
- dta_parser: Gamry DTA 文件解析与温度计算
- persistence: JSON/文本文件读写工具

核心原则：
1. 纯函数 - 只接受参数，返回结果字典
2. 标准错误字典 - 失败时返回 {"success": False, "error": "..."}
3. 无副作用 - 只读写文件，不修改全局状态
4. 无业务逻辑 - 只负责 I/O，不拼装业务数据

版本：3.0.0 (重构版)
"""

from .chi_parser import (
    parse_chi_file,
    parse_chi_file_with_metadata,
    extract_temperature_from_filename,
)

from .dta_parser import (
    calculate_temperature_from_dta,
    parse_dta_directory,
    scan_dta_files_in_directory,
)

from .persistence import (
    save_json,
    load_json,
    save_text,
    load_text,
    ensure_directory,
    list_files,
    check_file_exists,
    make_json_safe,
    save_multiple_json,
    load_multiple_json,
    save_eis_data_tsv,
)

__all__ = [
    # CHI 解析
    'parse_chi_file',
    'parse_chi_file_with_metadata',
    'extract_temperature_from_filename',
    
    # DTA 解析
    'calculate_temperature_from_dta',
    'parse_dta_directory',
    'scan_dta_files_in_directory',
    
    # 持久化
    'save_json',
    'load_json',
    'save_text',
    'load_text',
    'ensure_directory',
    'list_files',
    'check_file_exists',
    'make_json_safe',
    'save_multiple_json',
    'load_multiple_json',
    'save_eis_data_tsv',
]
