"""
Next Experiment Contract Schema
Agent 最终输出的通用契约，使用泛化的 Dict 配合严格的 Prompt 来约束大模型
"""
from pydantic import BaseModel, Field, field_validator
from typing import Dict, Any, List, Optional


class NextExperimentRecipe(BaseModel):
    """
    Agent 最终输出的通用契约
    
    不再硬编码具体的参数名，而是使用一个字典接收动态参数
    参数名必须严格匹配 Campaign JSON 中的参数名
    """
    
    reasoning: str = Field(
        ..., 
        description="对推荐这组参数的物理机制解释，包括为什么选择这些参数值"
    )
    
    expected_outcome: str = Field(
        ..., 
        description="预期这组参数能解决什么问题，或者能达到什么性能指标"
    )
    
    recommended_parameters: Dict[str, float] = Field(
        ..., 
        description=(
            "动态的参数字典，键必须严格匹配 Campaign JSON 中的参数名。"
            "值必须在配置文件定义的范围内。"
        )
    )
    
    confidence_score: float = Field(
        ..., 
        ge=0.0,
        le=1.0,
        description="置信度 (0.0-1.0)，表示对这组参数能达到预期效果的信心"
    )
    
    warnings: List[str] = Field(
        default_factory=list, 
        description=(
            "物理上的风险或妥协，例如：高温可能导致相变、"
            "过长球磨时间可能引入杂质等"
        )
    )
    
    alternative_suggestions: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description=(
            "可选的备选方案列表，每个方案包含 parameters 和 reasoning。"
            "用于探索-利用权衡 (exploration-exploitation tradeoff)"
        )
    )
    
    physical_constraints_checked: bool = Field(
        default=True,
        description="是否已检查物理约束（如相容性、稳定性等）"
    )
    
    @field_validator('reasoning', 'expected_outcome')
    @classmethod
    def validate_non_empty_string(cls, v: str) -> str:
        """确保推理和预期结果不为空"""
        if not v or not v.strip():
            raise ValueError("推理和预期结果不能为空")
        return v.strip()
    
    @field_validator('recommended_parameters')
    @classmethod
    def validate_parameters_not_empty(cls, v: Dict[str, float]) -> Dict[str, float]:
        """确保参数字典不为空"""
        if not v:
            raise ValueError("推荐参数不能为空")
        return v
    
    def validate_against_campaign(self, campaign_config) -> bool:
        """
        根据 Campaign 配置验证参数的有效性
        
        Args:
            campaign_config: CampaignConfig 对象
            
        Returns:
            True 如果所有参数都有效
            
        Raises:
            ValueError: 参数不符合配置要求
        """
        return campaign_config.validate_parameters(self.recommended_parameters)
    
    def to_experiment_dict(self) -> Dict[str, Any]:
        """
        转换为实验执行所需的字典格式
        
        Returns:
            包含所有必要信息的字典
        """
        return {
            "parameters": self.recommended_parameters,
            "reasoning": self.reasoning,
            "expected_outcome": self.expected_outcome,
            "confidence": self.confidence_score,
            "warnings": self.warnings,
            "physical_constraints_checked": self.physical_constraints_checked
        }
    
    class Config:
        json_schema_extra = {
            "example": {
                "reasoning": (
                    "基于前期实验数据，Al掺杂浓度在0.3附近显示出最佳的晶界电导率。"
                    "1000°C的烧结温度能够充分促进晶粒生长而不引起Li挥发。"
                    "12小时球磨可以获得均匀的粒径分布。"
                ),
                "expected_outcome": (
                    "预期室温电导率达到 10^-4 S/cm 量级，"
                    "相比基线提升约30%，主要通过优化晶界阻抗实现。"
                ),
                "recommended_parameters": {
                    "doping_concentration": 0.3,
                    "sintering_temp_C": 1000,
                    "ball_milling_time_h": 12.0
                },
                "confidence_score": 0.85,
                "warnings": [
                    "1000°C接近Li挥发温度，需要严格控制气氛",
                    "Al掺杂浓度过高可能形成第二相"
                ],
                "physical_constraints_checked": True
            }
        }
