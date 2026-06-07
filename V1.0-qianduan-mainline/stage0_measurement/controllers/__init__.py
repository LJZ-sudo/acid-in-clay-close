# -*- coding: utf-8 -*-
"""
Controllers 层：业务编排

子模块：
- state_manager: 实验状态管理器
- online_workflow: 在线实验工作流
- offline_workflow: 离线批处理工作流

职责：
1. 协调 hardware、automation、analysis、reporting 模块
2. 管理实验流程和状态
3. 不包含具体的算法或硬件操作逻辑

版本：2.0.0 (重构版)
"""

from .state_manager import (
    # 数据类
    HardwareState,
    MeasurementRecord,
    PhaseTransitionRecord,
    PhaseTransitionCandidate,
    ExperimentProgress,
    PhaseDetectionQueue,
    ExperimentState,
    
    # 控制器
    StateController,
    
    # 工具函数
    create_measurement_record,
    validate_state_integrity,
)

from .online_workflow import (
    # 配置类
    CoolingConfig,
    ChiConfig,
    ExperimentConfig,
    
    # 工作流
    OnlineExperimentWorkflow,
)

from .offline_workflow import (
    # 配置类
    OfflineConfig,
    
    # 结果类
    ProcessingResult,
    BatchResult,
    
    # 工作流
    OfflineBatchWorkflow,
    
    # 辅助函数
    create_default_eis_analyzer,
    create_default_arrhenius_analyzer,
)

__all__ = [
    # 数据类
    'HardwareState',
    'MeasurementRecord',
    'PhaseTransitionRecord',
    'PhaseTransitionCandidate',
    'ExperimentProgress',
    'PhaseDetectionQueue',
    'ExperimentState',
    
    # 控制器
    'StateController',
    
    # 工具函数
    'create_measurement_record',
    'validate_state_integrity',
    
    # 在线工作流
    'CoolingConfig',
    'ChiConfig',
    'ExperimentConfig',
    'OnlineExperimentWorkflow',
    
    # 离线工作流
    'OfflineConfig',
    'ProcessingResult',
    'BatchResult',
    'OfflineBatchWorkflow',
    'create_default_eis_analyzer',
    'create_default_arrhenius_analyzer',
]
