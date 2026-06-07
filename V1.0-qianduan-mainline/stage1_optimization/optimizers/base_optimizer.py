"""
Base Optimizer Abstract Class
定义优化器接口，确保未来可以轻松更换算法
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional


class BaseOptimizer(ABC):
    """
    优化器抽象基类
    
    所有优化算法（贝叶斯优化、遗传算法、粒子群优化等）必须继承此类
    并实现 suggest_next() 方法
    """
    
    @abstractmethod
    def suggest_next(self) -> Dict[str, Any]:
        """
        根据历史数据建议下一个实验参数
        
        Returns:
            参数字典，键为参数名，值为建议的参数值
            例如: {"doping_concentration": 0.3, "sintering_temp_C": 1000, ...}
            
        Notes:
            - 此方法是纯数学计算，不涉及物理机制解释
            - 对于冷启动场景，应该有合理的降级策略
            - 返回的参数必须在 ParameterSpace 定义的范围内
        """
        pass
    
    def validate_suggestion(self, suggestion: Dict[str, Any]) -> bool:
        """
        验证建议的参数是否在合法范围内（可选实现）
        
        Args:
            suggestion: 建议的参数字典
            
        Returns:
            True 如果参数合法
        """
        return True
    
    def get_acquisition_function_value(self, params: Dict[str, Any]) -> Optional[float]:
        """
        获取采集函数值（可选实现，用于调试和可视化）
        
        Args:
            params: 参数字典
            
        Returns:
            采集函数值，如果不支持则返回 None
        """
        return None
