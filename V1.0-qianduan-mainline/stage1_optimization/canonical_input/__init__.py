"""
Canonical Input Module
输入与边界层：管理配置解析、参数空间定义、Stage 0 结果解析
"""
from .campaign_parser import CampaignConfig
from .design_space import ParameterSpace
from .state0_parser import State0Parser

__all__ = ["CampaignConfig", "ParameterSpace", "State0Parser"]
