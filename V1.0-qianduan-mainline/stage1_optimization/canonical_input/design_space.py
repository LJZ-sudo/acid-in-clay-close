"""
Dynamic Parameter Space Generator
动态生成贝叶斯优化的搜索空间
"""
from typing import List, Any
from .campaign_parser import CampaignConfig


class ParameterSpace:
    """动态搜索空间生成器"""
    
    def __init__(self, campaign_config: CampaignConfig):
        """
        初始化参数空间
        
        Args:
            campaign_config: 实验战役配置对象
        """
        self.campaign_config = campaign_config
    
    def get_skopt_space(self) -> List[Any]:
        """
        根据传入的 JSON 动态生成 scikit-optimize 的 Space
        
        Returns:
            scikit-optimize Space 对象列表
            
        Raises:
            ImportError: scikit-optimize 未安装
        """
        try:
            from skopt.space import Real, Categorical, Integer
        except ImportError:
            raise ImportError(
                "请安装 scikit-optimize: pip install scikit-optimize"
            )
        
        space = []
        for param_name, config in self.campaign_config.parameters.items():
            if config["type"] == "continuous":
                space.append(
                    Real(
                        config["low"], 
                        config["high"], 
                        name=param_name
                    )
                )
            elif config["type"] == "discrete":
                space.append(
                    Categorical(
                        config["options"], 
                        name=param_name
                    )
                )
            elif config["type"] == "integer":
                space.append(
                    Integer(
                        config["low"], 
                        config["high"], 
                        name=param_name
                    )
                )
            else:
                raise ValueError(
                    f"不支持的参数类型: {config['type']} (参数: {param_name})"
                )
        
        return space
    
    def get_bounds(self) -> List[tuple]:
        """
        获取所有参数的边界（用于其他优化器）
        
        Returns:
            边界列表，每个元素为 (low, high) 元组
        """
        bounds = []
        for param_name, config in self.campaign_config.parameters.items():
            if config["type"] in ["continuous", "integer"]:
                bounds.append((config["low"], config["high"]))
            elif config["type"] == "discrete":
                bounds.append((0, len(config["options"]) - 1))
        
        return bounds
    
    def get_parameter_info(self) -> dict:
        """
        获取参数空间的详细信息
        
        Returns:
            包含参数类型、范围等信息的字典
        """
        info = {
            "campaign_name": self.campaign_config.campaign_name,
            "num_parameters": len(self.campaign_config.parameters),
            "parameters": {}
        }
        
        for param_name, config in self.campaign_config.parameters.items():
            param_info = {
                "type": config["type"],
                "description": config.get("desc", "")
            }
            
            if config["type"] in ["continuous", "integer"]:
                param_info["range"] = [config["low"], config["high"]]
            elif config["type"] == "discrete":
                param_info["options"] = config["options"]
            
            info["parameters"][param_name] = param_info
        
        return info
    
    def decode_discrete_indices(self, params: dict) -> dict:
        """
        将离散参数的索引转换为实际值（如果优化器返回的是索引）
        
        Args:
            params: 参数字典，可能包含索引
            
        Returns:
            解码后的参数字典
        """
        decoded = params.copy()
        
        for param_name, value in params.items():
            if param_name in self.campaign_config.parameters:
                config = self.campaign_config.parameters[param_name]
                if config["type"] == "discrete" and isinstance(value, int):
                    options = config["options"]
                    if 0 <= value < len(options):
                        decoded[param_name] = options[value]
        
        return decoded
