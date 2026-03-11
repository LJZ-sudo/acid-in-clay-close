# -*- coding: utf-8 -*-
"""
文件处理工具函数
"""
import os
import json
import pickle
import re
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd
import numpy as np

class FileUtils:
    """文件处理工具类"""
    
    @staticmethod
    def ensure_directory(path: str):
        """确保目录存在"""
        os.makedirs(path, exist_ok=True)
    
    @staticmethod
    def save_json(data: Dict, filepath: str, encoding: str = 'utf-8'):
        """保存JSON文件"""
        FileUtils.ensure_directory(os.path.dirname(filepath))
        with open(filepath, 'w', encoding=encoding) as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    @staticmethod
    def load_json(filepath: str, encoding: str = 'utf-8') -> Dict:
        """加载JSON文件"""
        with open(filepath, 'r', encoding=encoding) as f:
            return json.load(f)
    
    @staticmethod
    def save_pickle(data: Any, filepath: str):
        """保存pickle文件"""
        FileUtils.ensure_directory(os.path.dirname(filepath))
        with open(filepath, 'wb') as f:
            pickle.dump(data, f)
    
    @staticmethod
    def load_pickle(filepath: str) -> Any:
        """加载pickle文件"""
        with open(filepath, 'rb') as f:
            return pickle.load(f)
    
    @staticmethod
    def save_csv(data: pd.DataFrame, filepath: str, **kwargs):
        """保存CSV文件"""
        FileUtils.ensure_directory(os.path.dirname(filepath))
        data.to_csv(filepath, **kwargs)
    
    @staticmethod
    def load_csv(filepath: str, **kwargs) -> pd.DataFrame:
        """加载CSV文件"""
        return pd.read_csv(filepath, **kwargs)
    
    @staticmethod
    def get_file_size(filepath: str) -> int:
        """获取文件大小（字节）"""
        return os.path.getsize(filepath)
    
    @staticmethod
    def list_files(directory: str, extension: Optional[str] = None) -> List[str]:
        """列出目录下的文件"""
        files = []
        for filename in os.listdir(directory):
            filepath = os.path.join(directory, filename)
            if os.path.isfile(filepath):
                if extension is None or filename.endswith(extension):
                    files.append(filepath)
        return files
    
    @staticmethod
    def copy_file(src: str, dst: str):
        """复制文件"""
        import shutil
        FileUtils.ensure_directory(os.path.dirname(dst))
        shutil.copy2(src, dst)
    
    @staticmethod
    def move_file(src: str, dst: str):
        """移动文件"""
        import shutil
        FileUtils.ensure_directory(os.path.dirname(dst))
        shutil.move(src, dst)
    
    @staticmethod
    def delete_file(filepath: str):
        """删除文件"""
        if os.path.exists(filepath):
            os.remove(filepath)
    
    @staticmethod
    def backup_file(filepath: str, backup_dir: str = None) -> str:
        """备份文件"""
        if backup_dir is None:
            backup_dir = os.path.dirname(filepath)
        
        filename = os.path.basename(filepath)
        name, ext = os.path.splitext(filename)
        
        # 生成备份文件名
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"{name}_backup_{timestamp}{ext}"
        backup_path = os.path.join(backup_dir, backup_filename)
        
        FileUtils.copy_file(filepath, backup_path)
        return backup_path

def load_eis_data(file_path: str) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    从DTA文件加载EIS数据
    
    Args:
        file_path: DTA文件路径
        
    Returns:
        Tuple[频率, 阻抗实部, 阻抗虚部]
    """
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        # 查找ZCURVE表格数据
        zcurve_start = content.find('ZCURVE')
        if zcurve_start == -1:
            raise ValueError("未找到ZCURVE数据表")
        
        # 提取数据行
        lines = content[zcurve_start:].split('\n')
        
        # 跳过表头，找到数据开始位置
        data_start = 0
        for i, line in enumerate(lines):
            if 'Pt' in line and 'Freq' in line:
                data_start = i + 1
                break
        
        # 解析数据
        freq_list = []
        zreal_list = []
        zimag_list = []
        
        for line in lines[data_start:]:
            line = line.strip()
            if not line or line.startswith('EOD'):
                break
            
            try:
                # 分割数据列
                parts = line.split('\t')
                if len(parts) >= 6:  # 至少需要Pt, Time, Freq, Zreal, Zimag, Zmod
                    freq = float(parts[2])    # Freq
                    zreal = float(parts[3])   # Zreal
                    zimag = float(parts[4])   # Zimag
                    
                    freq_list.append(freq)
                    zreal_list.append(zreal)
                    zimag_list.append(zimag)
                    
            except (ValueError, IndexError):
                continue
        
        if not freq_list:
            raise ValueError("未找到有效的EIS数据")
        
        # 转换为numpy数组
        freq = np.array(freq_list)
        zreal = np.array(zreal_list)
        zimag = np.array(zimag_list)
        
        # 按频率排序
        sort_idx = np.argsort(freq)
        freq = freq[sort_idx]
        zreal = zreal[sort_idx]
        zimag = zimag[sort_idx]
        
        return freq, zreal, zimag
        
    except Exception as e:
        raise RuntimeError(f"加载EIS数据失败: {str(e)}")

def extract_temperature_from_dta(file_path: str) -> float:
    """
    从DTA文件提取实际测量温度（保留向后兼容性）
    
    Args:
        file_path: DTA文件路径
        
    Returns:
        测量温度 (K)
    """
    # 使用新的温度计算器
    try:
        from phase1.core.temperature_calculator import TemperatureCalculator
        temp_calc = TemperatureCalculator()
        result = temp_calc.calculate_temperature_with_phases(file_path)
        return result['temperature']
    except ImportError:
        # 回退到原有逻辑
        pass
    
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        # 查找DATE和TIME字段
        date_match = re.search(r'DATE\s+(\d{1,2}/\d{1,2}/\d{4})', content)
        time_match = re.search(r'TIME\s+(\d{1,2}:\d{2}:\d{2})', content)
        
        if date_match and time_match:
            # 从文件名提取参数
            filename = os.path.basename(file_path)
            
            # 提取起始温度
            temp_match = re.search(r'(\d+)-\d+K', filename)
            start_temp = int(temp_match.group(1)) if temp_match else 300
            
            # 提取文件序号
            seq_match = re.search(r'#(\d+)', filename)
            file_seq = int(seq_match.group(1)) if seq_match else 1
            
            # 提取冷却速率
            rate_match = re.search(r'(\d+)K-min', filename)
            cooling_rate = float(rate_match.group(1)) if rate_match else 1.0
            
            # 简化计算：假设每个序号间隔约3分钟
            estimated_time_elapsed = (file_seq - 1) * 3  # 分钟
            actual_temp = start_temp - cooling_rate * estimated_time_elapsed
            
            # 确保温度在合理范围内
            actual_temp = max(140, min(300, actual_temp))
            
            return actual_temp
        
        else:
            # 如果无法从文件中提取时间，使用文件名估算
            filename = os.path.basename(file_path)
            temp_match = re.search(r'(\d+)-\d+K', filename)
            seq_match = re.search(r'#(\d+)', filename)
            rate_match = re.search(r'(\d+)K-min', filename)
            
            start_temp = int(temp_match.group(1)) if temp_match else 300
            file_seq = int(seq_match.group(1)) if seq_match else 1
            cooling_rate = float(rate_match.group(1)) if rate_match else 1.0
            
            estimated_temp = start_temp - cooling_rate * (file_seq - 1) * 3
            return max(140, min(300, estimated_temp))
    
    except Exception:
        # 如果所有方法都失败，返回默认值
        filename = os.path.basename(file_path)
        seq_match = re.search(r'#(\d+)', filename)
        file_seq = int(seq_match.group(1)) if seq_match else 1
        
        # 简单线性估算
        return max(140, min(300, 300 - (file_seq - 1) * 3))
