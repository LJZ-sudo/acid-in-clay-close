# -*- coding: utf-8 -*-
"""
Phase 2: 智能模板报告生成 + AI深度机理分析

功能模块:
- core/: 核心分析模块
  - intelligent_template_generator.py: 智能模板报告生成
  - material_deep_analyzer.py: AI深度机理分析
  - feature_extractor.py: 特征提取
  - knowledge_based_classifier.py: 知识库分类器
  - mechanism_inference.py: 机理推断
- knowledge/: 知识库
  - proton_conduction_mechanisms.yaml: 质子传导机理知识
  - composition_performance_S8_S60.yaml: 组分-性能关系
"""

from .core.intelligent_template_generator import IntelligentTemplateGenerator
from .core.material_deep_analyzer import MaterialDeepAnalyzer

__all__ = [
    'IntelligentTemplateGenerator',
    'MaterialDeepAnalyzer'
]
