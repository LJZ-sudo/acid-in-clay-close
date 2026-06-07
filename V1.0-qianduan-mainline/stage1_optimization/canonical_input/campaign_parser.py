"""
Campaign Configuration Parser
动态读取实验战役配置，实现材料泛化
"""
import json
from pathlib import Path
from typing import Dict, Any, List


class CampaignConfig:
    """动态读取实验战役配置，实现材料泛化"""
    
    def __init__(self, config_path: str):
        """
        加载实验战役配置文件
        
        Args:
            config_path: JSON 配置文件路径
            
        Raises:
            FileNotFoundError: 配置文件不存在
            json.JSONDecodeError: JSON 格式错误
            ValueError: 配置文件缺少必需字段
        """
        config_file = Path(config_path)
        if not config_file.exists():
            raise FileNotFoundError(f"配置文件不存在: {config_path}")
            
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = json.load(f)
        
        self._validate_config()
        
        self.campaign_name = self.config.get("campaign_name", "Unnamed_Campaign")
        self.parameters = self.config.get("parameters", {})
        self.objective = self.config.get("objective", {})
        self.domain_knowledge = self.config.get("domain_knowledge", "")
        self.objective_formula = self.objective.get("formula", "")
    
    def _validate_config(self) -> None:
        """验证配置文件的完整性"""
        required_fields = ["campaign_name", "objective", "parameters"]
        for field in required_fields:
            if field not in self.config:
                raise ValueError(f"配置文件缺少必需字段: {field}")
        
        if "target" not in self.config["objective"]:
            raise ValueError("objective 必须包含 'target' 字段")
        
        if "goal" not in self.config["objective"]:
            raise ValueError("objective 必须包含 'goal' 字段 (maximize/minimize)")
        
        if self.config["objective"]["goal"] not in ["maximize", "minimize"]:
            raise ValueError("goal 必须是 'maximize' 或 'minimize'")
        
        if not self.config["parameters"]:
            raise ValueError("parameters 不能为空")
        
        for param_name, param_config in self.config["parameters"].items():
            if "type" not in param_config:
                raise ValueError(f"参数 {param_name} 缺少 'type' 字段")
            
            param_type = param_config["type"]
            if param_type == "continuous":
                if "low" not in param_config or "high" not in param_config:
                    raise ValueError(f"连续参数 {param_name} 必须包含 'low' 和 'high'")
            elif param_type == "discrete":
                if "options" not in param_config:
                    raise ValueError(f"离散参数 {param_name} 必须包含 'options'")
            elif param_type == "integer":
                if "low" not in param_config or "high" not in param_config:
                    raise ValueError(f"整数参数 {param_name} 必须包含 'low' 和 'high'")
            else:
                raise ValueError(f"不支持的参数类型: {param_type}")
    
    def get_parameter_names(self) -> List[str]:
        """
        获取所有参数名称列表
        
        Returns:
            参数名称列表
        """
        return list(self.parameters.keys())
    
    def get_objective_target(self) -> str:
        """获取优化目标的指标名称"""
        return self.objective["target"]
    
    def get_objective_goal(self) -> str:
        """获取优化目标 (maximize/minimize)"""
        return self.objective["goal"]
    
    def get_domain_knowledge(self) -> str:
        """
        获取领域知识描述
        
        Returns:
            领域知识字符串，如果配置中没有则返回空字符串
        """
        return self.domain_knowledge
    
    def get_objective_formula(self) -> str:
        """
        获取目标计算公式
        
        Returns:
            公式字符串（如 "math.log10(conductivity_room_temp_S_cm) - 5.0 * ea_high_temp_eV"）
            如果配置中没有则返回空字符串
        """
        return self.objective_formula
    
    def get_prompt_description(self) -> str:
        """
        动态生成给大模型的变量描述
        
        Returns:
            格式化的参数描述字符串，用于 LLM Prompt
        """
        desc = f"## 实验战役: {self.campaign_name}\n\n"
        desc += f"### 优化目标\n"
        desc += f"- 指标: {self.objective['target']}\n"
        desc += f"- 目标: {self.objective['goal']}\n\n"
        desc += "### 可调节参数\n"
        desc += "你可以调节以下参数：\n\n"
        
        for k, v in self.parameters.items():
            if v["type"] == "continuous":
                desc += f"- **{k}**: 连续变量，范围 [{v['low']}, {v['high']}] ({v.get('desc', '')})\n"
            elif v["type"] == "discrete":
                desc += f"- **{k}**: 离散变量，可选值 {v['options']} ({v.get('desc', '')})\n"
            elif v["type"] == "integer":
                desc += f"- **{k}**: 整数变量，范围 [{v['low']}, {v['high']}] ({v.get('desc', '')})\n"
        
        return desc
    
    def validate_parameters(self, params: Dict[str, Any]) -> bool:
        """
        验证给定的参数字典是否符合配置要求
        
        Args:
            params: 待验证的参数字典
            
        Returns:
            True 如果参数有效
            
        Raises:
            ValueError: 参数不符合配置要求
        """
        for param_name in self.get_parameter_names():
            if param_name not in params:
                raise ValueError(f"缺少必需参数: {param_name}")
        
        for param_name, value in params.items():
            if param_name not in self.parameters:
                raise ValueError(f"未知参数: {param_name}")
            
            param_config = self.parameters[param_name]
            param_type = param_config["type"]
            
            if param_type == "continuous":
                if not isinstance(value, (int, float)):
                    raise ValueError(f"参数 {param_name} 必须是数值类型")
                if not (param_config["low"] <= value <= param_config["high"]):
                    raise ValueError(
                        f"参数 {param_name} 超出范围 "
                        f"[{param_config['low']}, {param_config['high']}]"
                    )
            elif param_type == "discrete":
                if value not in param_config["options"]:
                    raise ValueError(
                        f"参数 {param_name} 必须是以下值之一: {param_config['options']}"
                    )
            elif param_type == "integer":
                if not isinstance(value, int):
                    raise ValueError(f"参数 {param_name} 必须是整数类型")
                if not (param_config["low"] <= value <= param_config["high"]):
                    raise ValueError(
                        f"参数 {param_name} 超出范围 "
                        f"[{param_config['low']}, {param_config['high']}]"
                    )
        
        return True
