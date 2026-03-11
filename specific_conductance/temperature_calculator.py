# -*- coding: utf-8 -*-
"""
温度计算器 - 基于时间戳的精确温度计算和数据有效性判断
"""
import os
import re
import numpy as np
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any
import warnings

class TemperatureCalculator:
    """温度计算器"""
    
    def __init__(self):
        self.data_encodings = ['utf-8', 'latin1', 'gbk', 'cp1252']
    
    def calculate_temperature_with_phases(self, file_path: str) -> Dict[str, Any]:
        """
        考虑降温/升温阶段的温度计算
        
        Args:
            file_path: DTA文件路径
            
        Returns:
            {
                'temperature': float,      # 计算的温度
                'is_valid': bool,         # 数据是否有效
                'phase': str,             # 实验阶段
                'confidence': float,      # 温度计算的置信度
                'raw_calculated_temp': float,  # 原始计算温度
                'file_sequence': int      # 文件序号
            }
        """
        try:
            # 0. 【特殊处理】检查是否是Up文件夹（温度在文件名中）
            filename = os.path.basename(file_path)
            up_temp_match = re.search(r'up-(\d+)', filename.lower())
            if up_temp_match:
                # 从文件名直接提取温度
                temperature = float(up_temp_match.group(1))
                seq_match = re.search(r'-(\d+)\.DTA', filename)
                file_seq = int(seq_match.group(1)) if seq_match else 1
                
                return {
                    'temperature': temperature,
                    'is_valid': True,
                    'phase': 'heating',  # Up文件夹通常是升温
                    'confidence': 1.0,  # 从文件名直接读取，高置信度
                    'raw_calculated_temp': temperature,
                    'file_sequence': file_seq
                }
            
            # 1. 基础信息提取
            seq_match = re.search(r'#(\d+)', filename)
            file_seq = int(seq_match.group(1)) if seq_match else 1
            
            # 2. 从文件名提取实验参数
            temp_range_match = re.search(r'(\d+)-(\d+)K', filename)
            start_temp = float(temp_range_match.group(1)) if temp_range_match else 300.0  # 300K
            target_end_temp = float(temp_range_match.group(2)) if temp_range_match else 140.0  # 140K
            
            rate_match = re.search(r'(\d+(?:\.\d+)?)K-min', filename)
            temp_rate = float(rate_match.group(1)) if rate_match else 1.0  # 1K/min
            
            # 【关键修改】判断是升温还是降温实验
            is_heating = start_temp < target_end_temp
            
            # 3. 基于时间戳计算温度
            calculated_temp = self._calculate_temperature_from_timestamp(file_path, is_heating=is_heating)
            
            # 4. 判断实验阶段和数据有效性
            if is_heating:
                # 升温实验
                if calculated_temp <= target_end_temp:
                    # 正常升温阶段
                    phase = "heating"
                    is_valid = True
                    confidence = 0.95
                    final_temp = calculated_temp
                else:
                    # 超过目标温度
                    phase = "heating_over"
                    is_valid = True
                    confidence = 0.7
                    final_temp = min(calculated_temp, target_end_temp)
            else:
                # 降温实验（原有逻辑）
                if calculated_temp >= target_end_temp:
                    # 正常降温阶段
                    phase = "cooling"
                    is_valid = True
                    confidence = 0.95
                    final_temp = calculated_temp
                    
                elif calculated_temp < target_end_temp:
                    # 可能进入恢复阶段
                    # 估算正常降温应该需要的时间
                    total_temp_drop = start_temp - target_end_temp  # 160K
                    expected_cooling_time = total_temp_drop / temp_rate  # 160分钟
                    
                    # 基于文件时间戳估算实际经过时间
                    actual_elapsed_time = self._estimate_elapsed_time(file_path)
                    
                    if actual_elapsed_time <= expected_cooling_time * 1.1:  # 允许10%误差
                        # 仍在正常降温范围内，但温度计算可能有误差
                        phase = "cooling_end"
                        is_valid = True
                        confidence = 0.7
                        final_temp = target_end_temp  # 使用目标温度
                        
                    else:
                        # 降温系统已关闭，样品开始回温
                        phase = "warming_up"
                        is_valid = False  # 标记为无效数据
                        confidence = 0.3
                        final_temp = calculated_temp  # 保留计算值但标记无效
            
            return {
                'temperature': final_temp,
                'is_valid': is_valid,
                'phase': phase,
                'confidence': confidence,
                'raw_calculated_temp': calculated_temp,
                'file_sequence': file_seq
            }
            
        except Exception as e:
            # 回退方案
            return self._calculate_temperature_fallback(file_path)
    
    def _calculate_temperature_from_timestamp(self, file_path: str, is_heating: bool = False) -> float:
        """基于文件时间戳计算精确温度"""
        try:
            # 读取当前文件时间戳
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            date_match = re.search(r'DATE\s+LABEL\s+(\d{1,2}/\d{1,2}/\d{4})', content)
            time_match = re.search(r'TIME\s+LABEL\s+(\d{1,2}:\d{2}:\d{2})', content)
            
            if not (date_match and time_match):
                raise ValueError("无法提取时间信息")
            
            # 解析当前文件时间戳
            current_datetime = datetime.strptime(
                f"{date_match.group(1)} {time_match.group(1)}", 
                "%m/%d/%Y %H:%M:%S"
            )
            
            # 从文件名提取实验参数
            filename = os.path.basename(file_path)
            temp_range_match = re.search(r'(\d+)-(\d+)K', filename)
            start_temp = float(temp_range_match.group(1)) if temp_range_match else 300.0
            
            rate_match = re.search(r'(\d+(?:\.\d+)?)K-min', filename)
            temp_rate = float(rate_match.group(1)) if rate_match else 1.0
            
            # 找到起始时间（优先使用序列文件创建时间）
            start_datetime = self._get_start_datetime(file_path)
            
            if start_datetime:
                # 计算经过时间和温度
                elapsed_minutes = (current_datetime - start_datetime).total_seconds() / 60.0
                
                # 【关键修改】根据实验类型使用不同的公式
                if is_heating:
                    calculated_temp = start_temp + temp_rate * elapsed_minutes  # 升温：加法
                else:
                    calculated_temp = start_temp - temp_rate * elapsed_minutes  # 降温：减法
                
                return calculated_temp
            else:
                # 如果无法获取起始时间，使用简化计算
                raise ValueError("无法获取起始时间")
                
        except Exception:
            # 回退到简化计算
            return self._calculate_temperature_simple(file_path)
    
    def _get_sequence_file_creation_time(self, folder_path: str) -> Optional[datetime]:
        """
        获取序列文件（.GSequence或.seq）的创建时间作为实验真正起始时间
        
        这是最准确的t₀标记，因为：
        - .GSequence文件是Gamry仪器在启动实验序列时创建的
        - 文件创建时间 = 仪器开始工作时间 = 样品开始降温时间
        
        Args:
            folder_path: 包含数据文件的文件夹路径
        
        Returns:
            序列文件的创建时间，如果未找到则返回None
        """
        try:
            # 查找序列文件（优先级：.GSequence > .seq）
            sequence_files = []
            
            for filename in os.listdir(folder_path):
                if filename.endswith('.GSequence') or filename.endswith('.seq'):
                    file_path = os.path.join(folder_path, filename)
                    # 使用修改时间（保留原始时间戳，即使文件被复制）
                    # 修改时间 = 文件内容最后修改的时间 = 实验进行的时间
                    modification_time = os.path.getmtime(file_path)
                    
                    sequence_files.append((filename, modification_time, file_path))
            
            if not sequence_files:
                return None
            
            # 选择最早的序列文件（通常只有一个）
            sequence_files.sort(key=lambda x: x[1])
            earliest_file = sequence_files[0]
            
            # 转换为datetime对象
            start_datetime = datetime.fromtimestamp(earliest_file[1])
            
            print(f"[温度计算] 找到序列文件: {earliest_file[0]}, "
                  f"起始时间: {start_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
            
            return start_datetime
            
        except Exception as e:
            print(f"[温度计算] 无法获取序列文件创建时间: {e}")
            return None
    
    def _get_start_datetime(self, file_path: str) -> Optional[datetime]:
        """
        获取实验起始时间
        
        优先级：
        1. #1文件内部的DATE/TIME标签（最可靠，来自实验数据）
        2. 序列文件的文件系统时间（备用）
        
        Args:
            file_path: 当前DTA文件路径
        
        Returns:
            实验起始时间
        """
        try:
            folder_path = os.path.dirname(file_path)
            
            # 方法1: 从#1文件内部读取时间戳（最可靠）
            filename = os.path.basename(file_path)
            first_filename = re.sub(r'#\d+', '#1', filename)
            first_file_path = os.path.join(folder_path, first_filename)
            
            if os.path.exists(first_file_path):
                with open(first_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    first_content = f.read()
                
                first_date_match = re.search(r'DATE\s+LABEL\s+(\d{1,2}/\d{1,2}/\d{4})', first_content)
                first_time_match = re.search(r'TIME\s+LABEL\s+(\d{1,2}:\d{2}:\d{2})', first_content)
                
                if first_date_match and first_time_match:
                    start_datetime = datetime.strptime(
                        f"{first_date_match.group(1)} {first_time_match.group(1)}", 
                        "%m/%d/%Y %H:%M:%S"
                    )
                    print(f"[温度计算] 从#1文件读取起始时间: {start_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
                    return start_datetime
            
            # 方法2: 尝试从序列文件获取时间（备用）
            print("[温度计算] 警告：未找到#1文件，尝试使用序列文件时间")
            sequence_start_time = self._get_sequence_file_creation_time(folder_path)
            if sequence_start_time:
                return sequence_start_time
            
            return None
            
        except Exception as e:
            print(f"[温度计算] 获取起始时间失败: {e}")
            return None
    
    def _estimate_elapsed_time(self, file_path: str) -> float:
        """估算从实验开始经过的时间(分钟)"""
        try:
            # 读取当前文件时间戳
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            date_match = re.search(r'DATE\s+LABEL\s+(\d{1,2}/\d{1,2}/\d{4})', content)
            time_match = re.search(r'TIME\s+LABEL\s+(\d{1,2}:\d{2}:\d{2})', content)
            
            if date_match and time_match:
                current_datetime = datetime.strptime(
                    f"{date_match.group(1)} {time_match.group(1)}", 
                    "%m/%d/%Y %H:%M:%S"
                )
                
                start_datetime = self._get_start_datetime(file_path)
                if start_datetime:
                    elapsed_minutes = (current_datetime - start_datetime).total_seconds() / 60.0
                    return elapsed_minutes
            
            return 0.0
            
        except Exception:
            return 0.0
    
    def _calculate_temperature_simple(self, file_path: str) -> float:
        """简化的温度计算方法"""
        try:
            filename = os.path.basename(file_path)
            
            # 提取文件序号
            seq_match = re.search(r'#(\d+)', filename)
            file_seq = int(seq_match.group(1)) if seq_match else 1
            
            # 提取温度范围
            temp_range_match = re.search(r'(\d+)-(\d+)K', filename)
            if temp_range_match:
                start_temp = float(temp_range_match.group(1))
                end_temp = float(temp_range_match.group(2))
                
                # 假设总共60个文件，线性插值
                total_files = 60
                temp_per_file = (start_temp - end_temp) / (total_files - 1)
                calculated_temp = start_temp - (file_seq - 1) * temp_per_file
                
                return max(end_temp, calculated_temp)
            else:
                # 最简单的回退方法
                return max(140, 300 - (file_seq - 1) * 2.7)
                
        except Exception:
            return 300.0  # 默认起始温度
    
    def _calculate_temperature_fallback(self, file_path: str) -> Dict[str, Any]:
        """回退的温度计算方法"""
        filename = os.path.basename(file_path)
        
        # 提取文件序号
        seq_match = re.search(r'#(\d+)', filename)
        file_seq = int(seq_match.group(1)) if seq_match else 1
        
        # 简单估算
        calculated_temp = max(140, 300 - (file_seq - 1) * 2.7)
        
        return {
            'temperature': calculated_temp,
            'is_valid': file_seq <= 50,  # 简单判断：前50个文件有效
            'phase': "unknown",
            'confidence': 0.5,
            'raw_calculated_temp': calculated_temp,
            'file_sequence': file_seq
        }
    
    def generate_temperature_sequence(self, folder_path: str) -> Dict[str, Dict[str, Any]]:
        """
        为整个文件夹生成温度序列
        
        Args:
            folder_path: 包含DTA文件的文件夹路径
            
        Returns:
            {文件名: 温度计算结果}
        """
        # 1. 获取所有DTA文件（递归扫描子文件夹）
        from pathlib import Path
        dta_files = []
        base_path = Path(folder_path)
        
        # 递归查找所有DTA文件
        for file_path in base_path.rglob("*.DTA"):
            filename = file_path.name
            
            # 【特殊处理】Up文件夹：温度在文件名中（如up-150.DTA）
            up_temp_match = re.search(r'up-(\d+)', filename.lower())
            if up_temp_match:
                # 使用温度作为序号，确保按温度排序
                temp_value = int(up_temp_match.group(1))
                dta_files.append((temp_value, filename, str(file_path)))
            elif '#' in filename:
                # 标准格式：文件名包含序号（如#1, #2）
                seq_match = re.search(r'#(\d+)', filename)
                if seq_match:
                    seq_num = int(seq_match.group(1))
                    dta_files.append((seq_num, filename, str(file_path)))
        
        # 2. 按序号排序
        dta_files.sort(key=lambda x: x[0])
        
        # 3. 计算每个文件的温度和有效性
        temperature_results = {}
        
        for seq_num, filename, file_path in dta_files:
            temp_result = self.calculate_temperature_with_phases(file_path)
            temperature_results[filename] = temp_result
        
        return temperature_results
    
    def filter_valid_files(self, temperature_results: Dict[str, Dict[str, Any]]) -> List[Tuple[str, Dict[str, Any]]]:
        """
        过滤出有效的文件
        
        Args:
            temperature_results: 温度计算结果
            
        Returns:
            [(文件名, 温度结果)] - 只包含有效文件
        """
        valid_files = []
        
        for filename, temp_result in temperature_results.items():
            if temp_result['is_valid'] and temp_result['temperature'] >= 140.0:
                valid_files.append((filename, temp_result))
        
        # 按文件序号排序
        valid_files.sort(key=lambda x: x[1]['file_sequence'])
        
        return valid_files
