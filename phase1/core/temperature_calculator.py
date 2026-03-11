# -*- coding: utf-8 -*-
"""
温度计算器 - 基于时间戳的精确温度计算
简化版：从V1.0-qianduan迁移
"""
import os
import re
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path


class TemperatureCalculator:
    """温度计算器"""
    
    def calculate_temperature_with_phases(self, file_path: str) -> Dict[str, Any]:
        """
        计算DTA文件对应的温度
        
        Args:
            file_path: DTA文件路径
            
        Returns:
            {
                'temperature': float,      # 计算的温度
                'is_valid': bool,         # 数据是否有效
                'phase': str,             # 实验阶段
                'confidence': float,      # 温度计算的置信度
            }
        """
        try:
            filename = os.path.basename(file_path)
            
            # 特殊处理：Up文件夹（温度在文件名中）
            up_temp_match = re.search(r'up-(\d+)', filename.lower())
            if up_temp_match:
                temperature = float(up_temp_match.group(1))
                return {
                    'temperature': temperature,
                    'is_valid': True,
                    'phase': 'heating',
                    'confidence': 1.0,
                }
            
            # 提取文件序号 (#1, #2, ...)
            seq_match = re.search(r'#(\d+)', filename)
            file_seq = int(seq_match.group(1)) if seq_match else 1
            
            # 提取温度范围 (300-140K)
            temp_range_match = re.search(r'(\d+)-(\d+)K', filename)
            start_temp = float(temp_range_match.group(1)) if temp_range_match else 300.0
            target_end_temp = float(temp_range_match.group(2)) if temp_range_match else 140.0
            
            # 提取降温速率 (1K-min, 0.3K-min)
            rate_match = re.search(r'(\d+(?:\.\d+)?)K-min', filename)
            temp_rate = float(rate_match.group(1)) if rate_match else 1.0
            
            # 判断升温还是降温
            is_heating = start_temp < target_end_temp
            
            # 尝试基于时间戳计算温度
            calculated_temp = self._calculate_from_timestamp(
                file_path, start_temp, temp_rate, is_heating
            )
            
            if calculated_temp is None:
                # 回退：基于文件序号简单估算
                calculated_temp = self._calculate_simple(
                    file_seq, start_temp, target_end_temp
                )
            
            # 判断数据有效性
            if is_heating:
                is_valid = calculated_temp <= target_end_temp
                phase = "heating" if is_valid else "heating_over"
            else:
                is_valid = calculated_temp >= target_end_temp
                phase = "cooling" if is_valid else "warming_up"
            
            return {
                'temperature': calculated_temp,
                'is_valid': is_valid,
                'phase': phase,
                'confidence': 0.95 if is_valid else 0.5,
            }
            
        except Exception as e:
            # 最简单的回退
            return self._fallback(file_path)
    
    def _calculate_from_timestamp(
        self, 
        file_path: str, 
        start_temp: float,
        temp_rate: float,
        is_heating: bool
    ) -> Optional[float]:
        """基于文件内时间戳计算温度"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # 提取当前文件时间戳
            date_match = re.search(r'DATE\s+LABEL\s+(\d{1,2}/\d{1,2}/\d{4})', content)
            time_match = re.search(r'TIME\s+LABEL\s+(\d{1,2}:\d{2}:\d{2})', content)
            
            if not (date_match and time_match):
                return None
            
            current_datetime = datetime.strptime(
                f"{date_match.group(1)} {time_match.group(1)}", 
                "%m/%d/%Y %H:%M:%S"
            )
            
            # 获取起始时间（从#1文件）
            start_datetime = self._get_start_datetime(file_path)
            if start_datetime is None:
                return None
            
            # 计算经过时间
            elapsed_minutes = (current_datetime - start_datetime).total_seconds() / 60.0
            
            # 计算温度
            if is_heating:
                return start_temp + temp_rate * elapsed_minutes
            else:
                return start_temp - temp_rate * elapsed_minutes
            
        except Exception:
            return None
    
    def _get_start_datetime(self, file_path: str) -> Optional[datetime]:
        """获取实验起始时间（从#1文件）"""
        try:
            folder_path = os.path.dirname(file_path)
            filename = os.path.basename(file_path)
            
            # 构造#1文件名
            first_filename = re.sub(r'#\d+', '#1', filename)
            first_file_path = os.path.join(folder_path, first_filename)
            
            if not os.path.exists(first_file_path):
                return None
            
            with open(first_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            date_match = re.search(r'DATE\s+LABEL\s+(\d{1,2}/\d{1,2}/\d{4})', content)
            time_match = re.search(r'TIME\s+LABEL\s+(\d{1,2}:\d{2}:\d{2})', content)
            
            if date_match and time_match:
                return datetime.strptime(
                    f"{date_match.group(1)} {time_match.group(1)}", 
                    "%m/%d/%Y %H:%M:%S"
                )
            
            return None
            
        except Exception:
            return None
    
    def _calculate_simple(
        self, 
        file_seq: int, 
        start_temp: float,
        end_temp: float
    ) -> float:
        """基于文件序号简单估算温度"""
        # 假设总共60个文件
        total_files = 60
        temp_per_file = (start_temp - end_temp) / (total_files - 1)
        calculated_temp = start_temp - (file_seq - 1) * temp_per_file
        return max(end_temp, calculated_temp)
    
    def _fallback(self, file_path: str) -> Dict[str, Any]:
        """回退方案"""
        filename = os.path.basename(file_path)
        
        seq_match = re.search(r'#(\d+)', filename)
        file_seq = int(seq_match.group(1)) if seq_match else 1
        
        # 简单估算：300K开始，每个文件降约2.7K
        temperature = max(140, 300 - (file_seq - 1) * 2.7)
        
        return {
            'temperature': temperature,
            'is_valid': file_seq <= 50,
            'phase': "unknown",
            'confidence': 0.5,
        }
