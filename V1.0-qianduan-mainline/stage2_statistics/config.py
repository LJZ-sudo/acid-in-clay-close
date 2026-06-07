"""
Configuration Constants for Stage 2 Evidence Agent
所有魔法数字和硬编码常量的集中管理
"""

from typing import Tuple


# ============================================================
# 数据清洗阈值 (SanityChecker)
# ============================================================
class SanityCheckConfig:
    """数据清洗配置"""
    R2_THRESHOLD: float = 0.8  # R² 阈值
    EA_RANGE: Tuple[float, float] = (0.1, 2.0)  # Ea 合理范围 (eV)
    SIGMA_RANGE: Tuple[float, float] = (1e-10, 1e2)  # sigma 合理范围 (S/cm)
    IQR_MULTIPLIER: float = 1.5  # IQR 异常值检测倍数


# ============================================================
# 数据画像阈值 (DataProfiler)
# ============================================================
class DataProfileConfig:
    """数据画像配置"""
    WIDE_TEMP_THRESHOLD: float = 50.0  # 宽温区阈值 (K)
    HIGH_QUALITY_R2_THRESHOLD: float = 0.9  # 高质量数据 R² 阈值
    LOW_TEMP_THRESHOLD: float = 230.0  # 低温区上限 (K)
    HIGH_TEMP_THRESHOLD: float = 270.0  # 高温区下限 (K)
    MIN_DATA_POINTS: int = 10  # 最小数据点数


# ============================================================
# 分析计划阈值 (AnalysisPlanner)
# ============================================================
class AnalysisPlanConfig:
    """分析计划配置"""
    MODEL_COMPETITOR_TEMP_RANGE: float = 50.0  # ModelCompetitor 所需最小温度范围 (K)
    MODEL_COMPETITOR_MIN_QUALITY_RATIO: float = 0.5  # 高质量数据占比阈值


# ============================================================
# 趋势分析阈值 (TrendAnalyzer)
# ============================================================
class TrendAnalysisConfig:
    """趋势分析配置"""
    CRITICAL_JUMP_THRESHOLD: float = 0.1  # 临界跳变阈值 (eV)
    SENSITIVITY_THRESHOLD: float = 0.05  # 敏感度阈值 (eV per unit R)
    MIN_POINTS_FOR_TREND: int = 5  # 趋势分析最小点数
    CONFIDENCE_HIGH: float = 0.85  # 高置信度阈值
    CONFIDENCE_MEDIUM: float = 0.65  # 中等置信度阈值


# ============================================================
# 模型竞争阈值 (ModelCompetitor)
# ============================================================
class ModelCompetitionConfig:
    """模型竞争配置"""
    MN_R2_THRESHOLD: float = 0.9  # Meyer-Neldel R² 阈值
    VTF_AIC_IMPROVEMENT_THRESHOLD: float = 10.0  # VTF AIC 改进阈值
    T0_VALID_RANGE_OFFSET: float = 100.0  # T0 合理范围偏移 (K)
    MIN_POINTS_FOR_VTF: int = 8  # VTF 拟合最小点数
    ARRHENIUS_MIN_POINTS: int = 5  # Arrhenius 拟合最小点数


# ============================================================
# 形貌分析阈值 (MorphologyExpert)
# ============================================================
class MorphologyConfig:
    """形貌分析配置"""
    ALIGNMENT_THRESHOLD: float = 10.0  # 温度对齐阈值 (K)
    T_ARC_CONFIDENCE_HIGH: float = 0.9  # T_arc 高置信度阈值
    T_BREAK_CONFIDENCE_HIGH: float = 0.85  # T_break 高置信度阈值


# ============================================================
# 证据合成阈值 (EvidenceSynthesizer)
# ============================================================
class SynthesisConfig:
    """证据合成配置"""
    STRONG_MN_R2_THRESHOLD: float = 0.8  # 强 Meyer-Neldel R² 阈值（已放宽）
    QUESTION_BASE_CONFIDENCE: float = 0.65  # Question 基础置信度
    MIN_EVIDENCES_FOR_SYNTHESIS: int = 2  # 合成所需最小证据数


# ============================================================
# 可视化配置 (VizEngine)
# ============================================================
class VisualizationConfig:
    """可视化配置"""
    DPI: int = 300  # 图像分辨率
    FONT_SIZE: int = 12  # 字体大小
    FIGURE_WIDTH: float = 10.0  # 图像宽度 (inches)
    FIGURE_HEIGHT: float = 6.0  # 图像高度 (inches)
    LINE_WIDTH: float = 2.0  # 线宽
    MARKER_SIZE: float = 6.0  # 标记大小


# ============================================================
# 统计分析配置 (statistics_lib)
# ============================================================
class StatisticsConfig:
    """统计分析配置"""
    BOOTSTRAP_ITERATIONS: int = 2000  # Bootstrap 迭代次数
    CONFIDENCE_LEVEL: float = 0.95  # 置信水平
    IQR_MULTIPLIER: float = 1.5  # IQR 异常值检测倍数
    Z_SCORE_THRESHOLD: float = 3.0  # Z-score 异常值阈值


# ============================================================
# 文件路径配置
# ============================================================
class PathConfig:
    """文件路径配置"""
    DEFAULT_DATA_DIR: str = "data"
    DEFAULT_OUTPUT_DIR: str = "exports"
    DEFAULT_VIZ_DIR: str = "exports/visualizations"
    DEFAULT_ATLAS_FILENAME: str = "s8_evidence_atlas.json"
    DEFAULT_PROFILE_FILENAME: str = "data_profile.json"
    DEFAULT_PLAN_FILENAME: str = "execution_plan.json"


# ============================================================
# 全局配置类（方便访问）
# ============================================================
class Config:
    """全局配置"""
    sanity_check = SanityCheckConfig
    data_profile = DataProfileConfig
    analysis_plan = AnalysisPlanConfig
    trend_analysis = TrendAnalysisConfig
    model_competition = ModelCompetitionConfig
    morphology = MorphologyConfig
    synthesis = SynthesisConfig
    visualization = VisualizationConfig
    statistics = StatisticsConfig
    paths = PathConfig


# 导出
__all__ = [
    'Config',
    'SanityCheckConfig',
    'DataProfileConfig',
    'AnalysisPlanConfig',
    'TrendAnalysisConfig',
    'ModelCompetitionConfig',
    'MorphologyConfig',
    'SynthesisConfig',
    'VisualizationConfig',
    'StatisticsConfig',
    'PathConfig',
]
