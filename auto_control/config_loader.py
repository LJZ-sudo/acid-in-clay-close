#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置文件加载器
从JSON配置文件读取参数并调用jilu_sheding.py
"""

import json
import os
import sys
from typing import Dict, Any, List

# 添加当前目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from jilu_sheding import RefrigeratorController


class ConfigLoader:
    """配置文件加载器"""
    
    def __init__(self, config_file: str):
        """
        初始化配置加载器
        :param config_file: 配置文件路径
        """
        self.config_file = config_file
        self.config = self.load_config()
    
    def load_config(self) -> Dict[str, Any]:
        """
        加载配置文件
        :return: 配置字典
        """
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            print(f"成功加载配置文件: {self.config_file}")
            return config
        except FileNotFoundError:
            print(f"配置文件不存在: {self.config_file}")
            return {}
        except json.JSONDecodeError as e:
            print(f"配置文件格式错误: {e}")
            return {}
        except Exception as e:
            print(f"加载配置文件时出错: {e}")
            return {}
    
    def create_controller(self) -> RefrigeratorController:
        """
        根据配置文件创建控制器实例
        :return: RefrigeratorController实例
        """
        if not self.config:
            print("配置为空，使用默认参数创建控制器")
            return RefrigeratorController(
                port='COM3',
                T_start=25.0,
                T_end=10.0
            )
        
        # 获取基本参数
        basic_params = self.config.get('basic_params', {})
        chi_params = self.config.get('chi_params', {})
        
        # 合并参数
        all_params = {**basic_params, **chi_params}
        
        print("从配置文件创建控制器:")
        print(f"基本参数: {basic_params}")
        print(f"CHI参数: {chi_params}")
        
        # 创建控制器实例
        controller = RefrigeratorController(**all_params)
        
        return controller
    
    def run_measurement_sequence(self) -> List[RefrigeratorController]:
        """
        运行测量序列
        :return: 控制器实例列表
        """
        if not self.config:
            print("配置为空，无法运行测量序列")
            return []
        
        sequences = self.config.get('measurement_sequences', [])
        if not sequences:
            print("没有找到测量序列配置")
            return []
        
        controllers = []
        
        # 获取基本参数
        basic_params = self.config.get('basic_params', {})
        
        print(f"开始运行 {len(sequences)} 个测量序列...")
        
        for i, sequence in enumerate(sequences, 1):
            print(f"\n--- 序列 {i}: {sequence.get('name', f'sequence_{i}')} ---")
            
            # 合并基本参数和序列参数
            all_params = {**basic_params, **sequence}
            
            try:
                # 创建控制器
                controller = RefrigeratorController(**all_params)
                controllers.append(controller)
                
                # 显示参数
                print(f"材料: {sequence.get('material', 'N/A')}")
                print(f"温度: {sequence.get('temperature', 'N/A')}K")
                print(f"频率范围: {sequence.get('low_freq', 'N/A')} - {sequence.get('high_freq', 'N/A')} Hz")
                print(f"初始电压: {sequence.get('init_voltage', 'N/A')}V")
                print(f"保存路径: {sequence.get('save_path', 'N/A')}")
                print(f"文件名: {controller.get_filename()}")
                
                # 这里可以调用实际的测量方法
                # controller.run_chi_measurement()
                
                print("参数设置完成，准备测量")
                
            except Exception as e:
                print(f"创建控制器失败: {e}")
                continue
        
        return controllers
    
    def validate_config(self) -> bool:
        """
        验证配置文件
        :return: 验证是否通过
        """
        if not self.config:
            print("配置为空")
            return False
        
        required_sections = ['basic_params', 'chi_params']
        for section in required_sections:
            if section not in self.config:
                print(f"缺少必需的配置节: {section}")
                return False
        
        # 验证基本参数
        basic_params = self.config['basic_params']
        required_basic = ['port', 'T_start', 'T_end']
        for param in required_basic:
            if param not in basic_params:
                print(f"缺少必需的基本参数: {param}")
                return False
        
        # 验证CHI参数
        chi_params = self.config['chi_params']
        required_chi = ['material', 'temperature', 'high_freq', 'low_freq', 'init_voltage']
        for param in required_chi:
            if param not in chi_params:
                print(f"缺少必需的CHI参数: {param}")
                return False
        
        print("配置文件验证通过")
        return True


def main():
    """主函数"""
    print("配置文件加载器示例")
    print("=" * 50)
    
    # 配置文件路径
    config_file = "config_example.json"
    
    # 检查配置文件是否存在
    if not os.path.exists(config_file):
        print(f"配置文件不存在: {config_file}")
        print("请确保config_example.json文件在当前目录中")
        return
    
    # 创建配置加载器
    loader = ConfigLoader(config_file)
    
    # 验证配置
    if not loader.validate_config():
        print("配置文件验证失败")
        return
    
    # 示例1：创建单个控制器
    print("\n=== 示例1：创建单个控制器 ===")
    controller = loader.create_controller()
    print(f"控制器创建成功，文件名: {controller.get_filename()}")
    
    # 示例2：运行测量序列
    print("\n=== 示例2：运行测量序列 ===")
    controllers = loader.run_measurement_sequence()
    print(f"成功创建 {len(controllers)} 个控制器实例")
    
    # 示例3：动态修改参数
    print("\n=== 示例3：动态修改参数 ===")
    if controllers:
        controller = controllers[0]
        print("原始参数:")
        print(controller.get_chi_params())
        
        # 动态修改参数
        controller.set_chi_params(
            material='Zn',
            temperature='400',
            high_freq='200000',
            low_freq='0.001',
            init_voltage='2.0'
        )
        
        print("修改后参数:")
        print(controller.get_chi_params())
        print(f"新文件名: {controller.get_filename()}")


if __name__ == "__main__":
    main() 