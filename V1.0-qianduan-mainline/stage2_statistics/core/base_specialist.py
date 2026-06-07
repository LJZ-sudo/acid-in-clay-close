"""
Base Specialist - 专家模块抽象基类
定义所有 Specialist 模块的标准接口
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import pandas as pd

from .schema import EvidenceUnit


class BaseSpecialist(ABC):
    """
    专家模块抽象基类
    所有 Specialist 必须继承此类并实现 analyze 方法
    """
    
    def __init__(self, name: str = None):
        """
        初始化专家模块
        
        Args:
            name: 专家模块名称（可选）
        """
        self.name = name or self.__class__.__name__
    
    @abstractmethod
    def analyze(
        self,
        data: pd.DataFrame,
        profile: Optional[Dict[str, Any]] = None
    ) -> List[EvidenceUnit]:
        """
        分析数据并返回证据单元列表
        
        Args:
            data: 输入数据（DataFrame）
            profile: 数据画像（可选）
            
        Returns:
            List[EvidenceUnit]: 证据单元列表
        """
        pass
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name='{self.name}')"
