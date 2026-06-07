"""
Stage 2 Evidence Schema Definition
根据 SDL.md 定义的数据协议，使用 Pydantic 构建类型安全的证据结构
"""

import json
from datetime import datetime
from enum import Enum
from typing import List, Dict, Any, Optional

from pydantic import BaseModel, Field, field_validator


class ClaimLevel(str, Enum):
    """
    声明层级：定义证据的抽象程度
    - observation: 直接观测事实（如 R² > 0.95）
    - interpretation: 物理解释（如"VTF 模型优于 Arrhenius"）
    - question: 待解决的机理问题（如"为何 Ea 在 R=0.3 处突变？"）
    """
    observation = "observation"
    interpretation = "interpretation"
    question = "question"


class EvidenceTheme(str, Enum):
    """
    证据主题：将发现归类到三大研究方向
    - transport_dynamics: 离子传输动力学（Ea, σ, 扩散系数）
    - composition_sensitivity: 组分敏感性（R/N 依赖关系）
    - phase_transition: 相变与结构演化（EIS 形貌、玻璃化转变）
    """
    transport_dynamics = "transport_dynamics"
    composition_sensitivity = "composition_sensitivity"
    phase_transition = "phase_transition"


class EvidenceUnit(BaseModel):
    """
    证据单元：Specialist 模块输出的最小证据包
    
    Attributes:
        claim_level: 声明层级（观测/解释/问题）
        theme: 证据主题（动力学/组分/相变）
        statement: 自然语言描述的发现
        support_metrics: 支撑数据（如 R², AIC, 样本量等）
        confidence: 置信度 [0.0-1.0]，作为规则化证据权重使用
        confidence_basis: 置信度来源说明，用于审计启发式规则
        tags: 标签列表，用于快速筛选关键发现
    """
    claim_level: ClaimLevel = Field(..., description="声明层级")
    theme: EvidenceTheme = Field(..., description="证据主题")
    statement: str = Field(..., min_length=10, description="自然语言描述的发现")
    support_metrics: Dict[str, Any] = Field(
        default_factory=dict,
        description="支撑数据（如 R², AIC, 样本量等）"
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="规则化证据权重 [0.0-1.0]，不等同于严格统计置信概率"
    )
    confidence_basis: Dict[str, Any] = Field(
        default_factory=dict,
        description="置信度来源说明（rule_id、formula、inputs、interpretation）"
    )
    tags: List[str] = Field(
        default_factory=list,
        description="标签列表（如 critical_breakpoint, vtf_preferred）"
    )

    @field_validator('confidence')
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        """确保置信度在合理范围内"""
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"confidence must be between 0.0 and 1.0, got {v}")
        return v

    def to_jsonl(self) -> str:
        """
        将 EvidenceUnit 转换为 JSONL 格式的单行字符串
        用于批量导出和流式处理
        
        Returns:
            str: JSON 格式的单行字符串（不含换行符）
        """
        return self.model_dump_json(exclude_none=True)

    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典格式，方便后续处理
        
        Returns:
            Dict[str, Any]: 包含所有字段的字典
        """
        return self.model_dump(exclude_none=True)


class EvidenceAtlas(BaseModel):
    """
    证据地图：Stage 2 的最终输出容器
    汇总所有 Specialist 模块的发现，面向 Stage 3 的机理推理
    
    Attributes:
        metadata: 元数据（生成时间、数据源、分析参数等）
        sample_ids: 参与分析的样本列表（如 ["S8_R0.1_N0.5", ...]）
        evidence_units: 证据单元列表
    """
    metadata: Dict[str, Any] = Field(
        default_factory=lambda: {
            "generated_at": datetime.now().isoformat(),
            "stage": "stage2_statistics",
            "version": "1.0"
        },
        description="元数据（生成时间、数据源、分析参数等）"
    )
    sample_ids: List[str] = Field(
        default_factory=list,
        description="参与分析的样本列表"
    )
    evidence_units: List[EvidenceUnit] = Field(
        default_factory=list,
        description="证据单元列表"
    )

    def add_evidence(self, evidence: EvidenceUnit) -> None:
        """
        添加单个证据单元
        
        Args:
            evidence: 要添加的证据单元
        """
        self.evidence_units.append(evidence)

    def add_evidences(self, evidences: List[EvidenceUnit]) -> None:
        """
        批量添加证据单元
        
        Args:
            evidences: 证据单元列表
        """
        self.evidence_units.extend(evidences)

    def filter_by_theme(self, theme: EvidenceTheme) -> List[EvidenceUnit]:
        """
        按主题筛选证据
        
        Args:
            theme: 证据主题
            
        Returns:
            List[EvidenceUnit]: 符合主题的证据列表
        """
        return [e for e in self.evidence_units if e.theme == theme]

    def filter_by_claim_level(self, level: ClaimLevel) -> List[EvidenceUnit]:
        """
        按声明层级筛选证据
        
        Args:
            level: 声明层级
            
        Returns:
            List[EvidenceUnit]: 符合层级的证据列表
        """
        return [e for e in self.evidence_units if e.claim_level == level]

    def filter_by_tag(self, tag: str) -> List[EvidenceUnit]:
        """
        按标签筛选证据
        
        Args:
            tag: 标签名称
            
        Returns:
            List[EvidenceUnit]: 包含该标签的证据列表
        """
        return [e for e in self.evidence_units if tag in e.tags]

    def get_high_confidence_evidences(self, threshold: float = 0.8) -> List[EvidenceUnit]:
        """
        获取高置信度证据
        
        Args:
            threshold: 置信度阈值（默认 0.8）
            
        Returns:
            List[EvidenceUnit]: 置信度高于阈值的证据列表
        """
        return [e for e in self.evidence_units if e.confidence >= threshold]

    def to_json(self, filepath: str, indent: int = 2) -> None:
        """
        导出为 JSON 文件
        
        Args:
            filepath: 输出文件路径
            indent: 缩进空格数（默认 2）
        """
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(self.model_dump_json(indent=indent, exclude_none=True))

    def to_jsonl(self, filepath: str) -> None:
        """
        导出为 JSONL 文件（每个 EvidenceUnit 一行）
        
        Args:
            filepath: 输出文件路径
        """
        with open(filepath, 'w', encoding='utf-8') as f:
            for evidence in self.evidence_units:
                f.write(evidence.to_jsonl() + '\n')

    def summary(self) -> Dict[str, Any]:
        """
        生成证据地图摘要统计
        
        Returns:
            Dict[str, Any]: 包含各类统计信息的字典
        """
        return {
            "total_evidences": len(self.evidence_units),
            "total_samples": len(self.sample_ids),
            "by_theme": {
                theme.value: len(self.filter_by_theme(theme))
                for theme in EvidenceTheme
            },
            "by_claim_level": {
                level.value: len(self.filter_by_claim_level(level))
                for level in ClaimLevel
            },
            "avg_confidence": (
                sum(e.confidence for e in self.evidence_units) / len(self.evidence_units)
                if self.evidence_units else 0.0
            ),
            "high_confidence_count": len(self.get_high_confidence_evidences()),
            "metadata": self.metadata
        }

    @classmethod
    def from_json(cls, filepath: str) -> "EvidenceAtlas":
        """
        从 JSON 文件加载证据地图
        
        Args:
            filepath: JSON 文件路径
            
        Returns:
            EvidenceAtlas: 加载的证据地图实例
        """
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return cls.model_validate(data)
