# -*- coding: utf-8 -*-
"""
路径配置文件 - 解决中文路径编码问题
"""

import os

# 使用英文路径避免编码问题
# 获取当前工作目录的父目录（项目根目录）
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))

# 新的英文模板路径（避免中文编码问题）
TEMPLATE_DIR = os.path.join(current_dir)  # 直接使用当前目录

# 新的保存路径（使用D盘根目录避免中文路径问题）
SAVE_DIR = "D:\\chi_data"

# 原始代码目录路径（用于导入模块）
ORIGINAL_AUTO_CONTROL_PATH = current_dir

def get_template_path(filename):
    """
    获取模板文件的完整路径
    :param filename: 模板文件名
    :return: 完整的模板文件路径
    """
    return os.path.join(TEMPLATE_DIR, filename)

def check_template_exists(filename):
    """
    检查模板文件是否存在
    :param filename: 模板文件名
    :return: 文件是否存在
    """
    template_path = get_template_path(filename)
    exists = os.path.exists(template_path)
    print(f"[DEBUG] 检查模板文件: {filename}")
    print(f"[DEBUG] 完整路径: {template_path}")
    print(f"[DEBUG] 文件存在: {exists}")
    return exists

def list_available_templates():
    """
    列出所有可用的模板文件
    :return: 模板文件列表
    """
    if os.path.exists(TEMPLATE_DIR):
        files = [f for f in os.listdir(TEMPLATE_DIR) if f.endswith('.png')]
        print(f"[INFO] 可用模板文件: {files}")
        return files
    else:
        print(f"[ERROR] 模板目录不存在: {TEMPLATE_DIR}")
        return [] 