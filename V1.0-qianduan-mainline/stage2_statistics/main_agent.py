"""
Stage 2 Main Agent
管理分析生命周期，汇总证据包
"""

import logging
import os
import json
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Any, Protocol, Tuple
import pandas as pd
import numpy as np

# 支持两种导入方式：作为包导入和直接运行
try:
    # 作为包导入时使用相对导入
    from .core.schema import EvidenceAtlas, EvidenceUnit
    from .core import sample_aggregator as _agg
    from .core import segment_fitter as _segfit
    from .core import sample_trend as _strend
    from .core import meyer_neldel_segment as _mnseg
    from .core import morphology_features as _morphf
    from .core import stage3_seed_builder as _seedb
    from .planner.data_profiler import DataProfiler
    from .planner.analysis_planner import AnalysisPlanner
    from .specialists.sanity_checker import SanityChecker
    from .specialists.trend_analyzer import TrendAnalyzer
    from .specialists.model_competitor import ModelCompetitor
    from .specialists.morphology_expert import MorphologyExpert
    from .specialists.evidence_synthesizer import EvidenceSynthesizer
    from .utils.viz_engine import VizEngine
except ImportError:
    # 直接运行时使用绝对导入
    from core.schema import EvidenceAtlas, EvidenceUnit
    from core import sample_aggregator as _agg
    from core import segment_fitter as _segfit
    from core import sample_trend as _strend
    from core import meyer_neldel_segment as _mnseg
    from core import morphology_features as _morphf
    from core import stage3_seed_builder as _seedb
    from planner.data_profiler import DataProfiler
    from planner.analysis_planner import AnalysisPlanner
    from specialists.sanity_checker import SanityChecker
    from specialists.trend_analyzer import TrendAnalyzer
    from specialists.model_competitor import ModelCompetitor
    from specialists.morphology_expert import MorphologyExpert
    from specialists.evidence_synthesizer import EvidenceSynthesizer
    from utils.viz_engine import VizEngine


# 定义专家模块协议（接口）
class SpecialistProtocol(Protocol):
    """专家模块必须实现的接口"""
    
    def analyze(self, data: pd.DataFrame, profile: Optional[Dict[str, Any]] = None) -> List[EvidenceUnit]:
        """
        分析数据并返回证据单元列表
        
        Args:
            data: 输入数据（DataFrame）
            profile: 数据画像（可选）
            
        Returns:
            List[EvidenceUnit]: 证据单元列表
        """
        ...


class Stage2Agent:
    """
    Stage 2 证据分析主控程序
    负责协调各个专家模块，汇总证据，生成最终的证据地图
    """
    
    def __init__(
        self,
        output_dir: str = "./exports",
        viz_dir: str = "./exports/visualizations",
        log_level: int = logging.INFO,
        auto_register: bool = True
    ):
        """
        初始化 Stage2Agent
        
        Args:
            output_dir: 输出目录路径
            viz_dir: 可视化输出目录路径
            log_level: 日志级别
            auto_register: 是否自动注册所有模块
        """
        # 路径配置
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.viz_dir = Path(viz_dir)
        self.viz_dir.mkdir(parents=True, exist_ok=True)
        
        # 配置日志
        self._setup_logging(log_level)
        
        # 专家模块字典（可插拔设计）
        self.specialists: Dict[str, SpecialistProtocol] = {}
        
        # 数据清洗器
        self.sanity_checker = None
        
        # 数据画像器
        self.data_profiler = None
        
        # 分析计划器
        self.analysis_planner = None
        
        # 证据合成器
        self.evidence_synthesizer = None
        
        # 可视化引擎
        self.viz_engine = None

        # 清洗审计表（由 SanityChecker 生成）
        self.excluded_samples = pd.DataFrame()
        
        # 自动注册所有模块
        if auto_register:
            self._auto_register_modules()
        
        self.logger.info("Stage2Agent 初始化完成")
    
    def _setup_logging(self, log_level: int) -> None:
        """配置日志系统（避免重复配置）"""
        self.logger = logging.getLogger(__name__)
        
        # 只在没有 handler 时配置
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setLevel(log_level)
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(log_level)
            self.logger.propagate = False  # 防止传播到根 logger
    
    def _auto_register_modules(self) -> None:
        """自动注册所有模块"""
        try:
            # 注册数据清洗器（第一个注册）
            self.sanity_checker = SanityChecker()
            self.logger.info("自动注册: SanityChecker")
            
            # 注册数据画像器
            self.data_profiler = DataProfiler()
            self.logger.info("自动注册: DataProfiler")
            
            # 注册分析计划器
            self.analysis_planner = AnalysisPlanner()
            self.logger.info("自动注册: AnalysisPlanner")
            
            # 注册专家模块
            self.specialists['trend_analyzer'] = TrendAnalyzer()
            self.logger.info("自动注册: TrendAnalyzer")
            
            self.specialists['model_competitor'] = ModelCompetitor()
            self.logger.info("自动注册: ModelCompetitor")
            
            self.specialists['morphology_expert'] = MorphologyExpert()
            self.logger.info("自动注册: MorphologyExpert")
            
            # 注册证据合成器
            self.evidence_synthesizer = EvidenceSynthesizer()
            self.logger.info("自动注册: EvidenceSynthesizer")
            
            # 注册可视化引擎
            self.viz_engine = VizEngine(dpi=300, font_size=12)
            self.logger.info("自动注册: VizEngine")
            
        except Exception as e:
            self.logger.error(f"自动注册模块失败: {e}", exc_info=True)
            raise
    
    def register_specialist(self, name: str, specialist: SpecialistProtocol) -> None:
        """
        注册专家模块（依赖注入）
        
        Args:
            name: 专家模块名称
            specialist: 专家模块实例
        """
        self.specialists[name] = specialist
        self.logger.info(f"注册专家模块: {name}")
    
    def register_data_profiler(self, profiler: Any) -> None:
        """
        注册数据画像器
        
        Args:
            profiler: 数据画像器实例
        """
        self.data_profiler = profiler
        self.logger.info("注册数据画像器")
    
    def register_analysis_planner(self, planner: Any) -> None:
        """
        注册分析计划器
        
        Args:
            planner: 分析计划器实例
        """
        self.analysis_planner = planner
        self.logger.info("注册分析计划器")
    
    def register_evidence_synthesizer(self, synthesizer: Any) -> None:
        """
        注册证据合成器
        
        Args:
            synthesizer: 证据合成器实例
        """
        self.evidence_synthesizer = synthesizer
        self.logger.info("注册证据合成器")
    
    def register_viz_engine(self, viz_engine: Any) -> None:
        """
        注册可视化引擎
        
        Args:
            viz_engine: 可视化引擎实例
        """
        self.viz_engine = viz_engine
        self.logger.info("注册可视化引擎")
    
    def load_data(self, input_csv_path: str) -> pd.DataFrame:
        """
        加载输入数据
        
        Args:
            input_csv_path: CSV 文件路径
            
        Returns:
            pd.DataFrame: 加载的数据
        """
        self.logger.info(f"加载数据: {input_csv_path}")
        
        if not os.path.exists(input_csv_path):
            raise FileNotFoundError(f"输入文件不存在: {input_csv_path}")
        
        data = pd.read_csv(input_csv_path)
        self.logger.info(f"数据加载完成，共 {len(data)} 行")
        
        return data
    
    def profile_data(self, data: pd.DataFrame) -> Dict[str, Any]:
        """
        生成数据画像
        
        Args:
            data: 输入数据
            
        Returns:
            Dict[str, Any]: 数据画像
        """
        self.logger.info("生成数据画像...")
        
        if self.data_profiler is not None:
            profile = self.data_profiler.profile(data)
            self.logger.info(f"数据画像生成完成: {profile}")
            return profile
        else:
            # 占位：返回基本统计信息
            self.logger.warning("数据画像器未注册，使用默认画像")
            profile = {
                "sample_count": len(data),
                "columns": list(data.columns),
                "has_R": "R" in data.columns,
                "has_N": "N" in data.columns,
                "has_Ea": "Ea" in data.columns
            }
            return profile
    
    def create_analysis_plan(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        """
        创建分析执行计划
        
        Args:
            profile: 数据画像
            
        Returns:
            Dict[str, Any]: 执行计划
        """
        self.logger.info("创建分析执行计划...")
        
        if self.analysis_planner is not None:
            plan = self.analysis_planner.create_plan(profile)
            self.logger.info(f"分析计划创建完成")
            self.logger.info(f"计划摘要: {plan['plan_summary']}")
            return plan
        else:
            # 默认计划：启动所有专家
            self.logger.warning("分析计划器未注册，使用默认计划（启动所有专家）")
            return {
                'specialists': {name: True for name in self.specialists.keys()},
                'plan_summary': '默认计划：启动所有专家模块'
            }
    
    def filter_data_with_sanity_check(
        self,
        data: pd.DataFrame,
        profile: Dict[str, Any]
    ) -> Tuple[pd.DataFrame, List[EvidenceUnit]]:
        """
        使用 SanityChecker 过滤数据
        
        Args:
            data: 输入数据
            profile: 数据画像
            
        Returns:
            Tuple[pd.DataFrame, List[EvidenceUnit]]: 过滤后的数据和清洗证据
        """
        self.logger.info("数据清洗（SanityChecker）...")
        
        sanity_evidences = []
        
        if self.sanity_checker is not None:
            # 使用 SanityChecker 进行清洗
            original_count = len(data)
            
            # 生成清洗证据（基于原始数据）
            sanity_evidences = self.sanity_checker.analyze(data, profile)
            
            # 执行数据过滤
            filtered_data = self.sanity_checker.filter_data(data)
            self.excluded_samples = self.sanity_checker.build_exclusion_report(data)
            
            filtered_count = original_count - len(filtered_data)
            self.logger.info(f"SanityChecker: 移除 {filtered_count} 行低质量数据")
            self.logger.info(f"清洗后数据: {len(filtered_data)} 行")
            
            # 记录清洗证据
            for ev in sanity_evidences:
                self.logger.info(f"  证据: {ev.statement[:80]}...")
            
            return filtered_data, sanity_evidences
        else:
            # 回退到基本过滤逻辑
            self.logger.warning("SanityChecker 未注册，使用基本过滤逻辑")
            
            filtered_data = data.copy()
            
            # 基本过滤：移除 R2 < 0.8 的数据
            if 'R2' in filtered_data.columns:
                original_count = len(filtered_data)
                filtered_data = filtered_data[filtered_data['R2'] >= 0.8].copy()
                filtered_count = original_count - len(filtered_data)
                self.logger.info(f"基于 R2 过滤: 移除 {filtered_count} 行低质量数据")
            
            # 移除 NaN 值
            original_count = len(filtered_data)
            filtered_data = filtered_data.dropna(subset=['Ea'] if 'Ea' in filtered_data.columns else [])
            filtered_count = original_count - len(filtered_data)
            if filtered_count > 0:
                self.logger.info(f"移除 {filtered_count} 行包含 NaN 的数据")
            
            self.logger.info(f"清洗后数据: {len(filtered_data)} 行")
            
            return filtered_data, sanity_evidences
    
    def run_specialists(
        self,
        data: pd.DataFrame,
        profile: Dict[str, Any],
        execution_plan: Dict[str, Any]
    ) -> Dict[str, List[EvidenceUnit]]:
        """
        根据执行计划运行专家模块
        
        Args:
            data: 输入数据
            profile: 数据画像
            execution_plan: 执行计划
            
        Returns:
            Dict[str, List[EvidenceUnit]]: 专家名称 -> 证据列表的映射
        """
        specialist_results = {}
        enabled_specialists = execution_plan.get('specialists', {})
        
        self.logger.info(f"开始运行专家模块...")
        
        for name, specialist in self.specialists.items():
            # 检查是否启用
            if not enabled_specialists.get(name, True):
                self.logger.info(f"跳过专家模块（已禁用）: {name}")
                specialist_results[name] = []
                continue
            
            try:
                self.logger.info(f"运行专家模块: {name}")
                evidences = specialist.analyze(data, profile)
                specialist_results[name] = evidences
                self.logger.info(f"{name} 完成，生成 {len(evidences)} 条证据")
            except Exception as e:
                self.logger.error(f"{name} 运行失败: {e}", exc_info=True)
                specialist_results[name] = []
        
        # 统计总证据数
        total_evidences = sum(len(evs) for evs in specialist_results.values())
        self.logger.info(f"所有专家模块完成，共生成 {total_evidences} 条证据")
        
        return specialist_results
    
    def synthesize_evidence(
        self,
        evidences: List[EvidenceUnit],
        profile: Dict[str, Any]
    ) -> List[EvidenceUnit]:
        """
        证据合成（跨维度证据合成，生成 Question 层级声明）
        
        Args:
            evidences: 原始证据列表
            profile: 数据画像
            
        Returns:
            List[EvidenceUnit]: 合成后的证据列表
        """
        self.logger.info("开始证据合成...")
        
        if self.evidence_synthesizer is not None:
            try:
                synthesized = self.evidence_synthesizer.synthesize(evidences, profile)
                self.logger.info(f"证据合成完成，最终 {len(synthesized)} 条证据")
                
                # 统计新增的 Question 级别证据
                original_count = len(evidences)
                new_questions = len(synthesized) - original_count
                if new_questions > 0:
                    self.logger.info(f"合成生成 {new_questions} 条 Question 级别证据")
                
                return synthesized
            except Exception as e:
                self.logger.error(f"证据合成失败: {e}", exc_info=True)
                return evidences
        else:
            # 占位：直接返回原始证据
            self.logger.warning("证据合成器未注册，跳过合成步骤")
            return evidences
    
    def generate_visualizations(
        self,
        data: pd.DataFrame,
        specialist_results: Dict[str, List[EvidenceUnit]],
        profile: Dict[str, Any]
    ) -> Dict[str, str]:
        """
        生成所有关键可视化图表
        
        Args:
            data: 输入数据
            specialist_results: 专家模块结果
            profile: 数据画像
            
        Returns:
            Dict[str, str]: 图表名称 -> 文件路径的映射
        """
        self.logger.info("生成可视化图表...")
        
        if self.viz_engine is None:
            self.logger.warning("可视化引擎未注册，跳过可视化步骤")
            return {}
        
        viz_paths = {}
        
        try:
            # 1. Ea vs R 趋势图（如果有 TrendAnalyzer 结果）
            if 'trend_analyzer' in specialist_results and len(specialist_results['trend_analyzer']) > 0:
                self._generate_ea_trend_plots(data, specialist_results['trend_analyzer'], viz_paths)
            
            # 2. Arrhenius vs VTF 对比图（如果有 ModelCompetitor 结果）
            if 'model_competitor' in specialist_results and len(specialist_results['model_competitor']) > 0:
                self._generate_model_comparison_plots(data, specialist_results['model_competitor'], viz_paths)
            
            # 3. EIS 对齐图（如果有 MorphologyExpert 结果）
            if 'morphology_expert' in specialist_results and len(specialist_results['morphology_expert']) > 0:
                self._generate_eis_alignment_plots(data, specialist_results['morphology_expert'], viz_paths)
            
            self.logger.info(f"可视化完成，生成 {len(viz_paths)} 个图表")
            
        except Exception as e:
            self.logger.error(f"可视化生成失败: {e}", exc_info=True)
        
        return viz_paths
    
    def _generate_ea_trend_plots(
        self,
        data: pd.DataFrame,
        evidences: List[EvidenceUnit],
        viz_paths: Dict[str, str]
    ) -> None:
        """生成 Ea 趋势图"""
        try:
            # 数据验证
            if data is None or data.empty:
                self.logger.warning("数据为空，跳过 Ea 趋势图生成")
                return
            
            if 'R' not in data.columns or 'Ea' not in data.columns:
                self.logger.warning("缺少必需列（R 或 Ea），跳过 Ea 趋势图生成")
                return
            
            # 检查是否有临界点证据
            critical_points = []
            for ev in evidences:
                if 'critical_breakpoint' not in ev.tags:
                    continue
                metrics = ev.support_metrics
                if metrics.get('composition_variable') == 'R' and 'critical_value' in metrics:
                    critical_points.append(metrics['critical_value'])
                elif 'R_critical' in metrics:
                    critical_points.append(metrics['R_critical'])
            
            # 按 R 排序并计算均值
            grouped = data.groupby('R')['Ea'].agg(['mean', 'std', 'count']).reset_index()
            
            if len(grouped) < 2:
                self.logger.warning(f"R 值数量不足（{len(grouped)}），跳过 Ea 趋势图生成")
                return
            
            grouped = grouped.sort_values('R')
            
            # 简单的置信区间估计（均值 ± 1.96 * std / sqrt(n)）
            grouped['ci_low'] = grouped['mean'] - 1.96 * grouped['std'] / np.sqrt(grouped['count'])
            grouped['ci_high'] = grouped['mean'] + 1.96 * grouped['std'] / np.sqrt(grouped['count'])
            
            # 处理 NaN（单点数据没有 std）
            grouped['ci_low'] = grouped['ci_low'].fillna(grouped['mean'])
            grouped['ci_high'] = grouped['ci_high'].fillna(grouped['mean'])
            
            output_path = self.viz_dir / "ea_vs_R_trend.png"
            self.viz_engine.plot_ea_trend_with_ci(
                R_values=grouped['R'].values,
                Ea_values=grouped['mean'].values,
                ci_low=grouped['ci_low'].values,
                ci_high=grouped['ci_high'].values,
                output_path=output_path,
                title="Activation Energy vs Composition (S8)",
                critical_points=critical_points if critical_points else None
            )
            viz_paths['ea_vs_R_trend'] = str(output_path)
            self.logger.info(f"✓ 生成图表: {output_path.name}")
            
        except KeyError as e:
            self.logger.error(f"生成 Ea 趋势图失败（缺少列）: {e}")
        except ValueError as e:
            self.logger.error(f"生成 Ea 趋势图失败（数值错误）: {e}")
        except Exception as e:
            self.logger.error(f"生成 Ea 趋势图失败（未知错误）: {e}", exc_info=True)
    
    def _generate_model_comparison_plots(
        self,
        data: pd.DataFrame,
        evidences: List[EvidenceUnit],
        viz_paths: Dict[str, str]
    ) -> None:
        """生成模型对比图"""
        try:
            if data is None or data.empty:
                self.logger.warning("数据为空，跳过模型对比图生成")
                return
            
            # 查找 VTF 或 Arrhenius 证据
            for ev in evidences:
                if 'vtf_preferred' in ev.tags or 'arrhenius_preferred' in ev.tags:
                    # 提取模型参数（如果有）
                    if 'T' in data.columns and 'sigma' in data.columns:
                        # 简化：只生成 Meyer-Neldel 图
                        if 'Ea' in data.columns and 'sigma0' in data.columns:
                            self._generate_meyer_neldel_plot(data, evidences, viz_paths)
                    else:
                        self.logger.warning("缺少必需列（T 或 sigma），跳过模型对比图生成")
                    break
        except Exception as e:
            self.logger.error(f"生成模型对比图失败: {e}", exc_info=True)
    
    def _generate_meyer_neldel_plot(
        self,
        data: pd.DataFrame,
        evidences: List[EvidenceUnit],
        viz_paths: Dict[str, str]
    ) -> None:
        """生成 Meyer-Neldel 图"""
        try:
            if data is None or data.empty:
                self.logger.warning("数据为空，跳过 Meyer-Neldel 图生成")
                return
            
            # 查找 Meyer-Neldel 证据
            for ev in evidences:
                if 'meyer_neldel' in ev.tags:
                    # 提取参数
                    fit_params = self._normalize_meyer_neldel_metrics(ev.support_metrics)
                    required_keys = ['slope', 'intercept', 'R2', 'E_MN']
                    if all(k in fit_params for k in required_keys):
                        if 'Ea' not in data.columns or 'ln_sigma0' not in data.columns:
                            self.logger.warning("缺少必需列（Ea 或 ln_sigma0），跳过 Meyer-Neldel 图生成")
                            break
                        
                        output_path = self.viz_dir / "meyer_neldel.png"
                        self.viz_engine.plot_meyer_neldel(
                            Ea_values=data['Ea'].values,
                            ln_sigma0_values=data['ln_sigma0'].values,
                            fit_params=fit_params,
                            output_path=output_path,
                            title="Meyer-Neldel Compensation Effect (S8)"
                        )
                        viz_paths['meyer_neldel'] = str(output_path)
                        self.logger.info(f"✓ 生成图表: {output_path.name}")
                    else:
                        missing = [k for k in required_keys if k not in fit_params]
                        self.logger.warning(f"Meyer-Neldel 证据缺少参数: {missing}")
                    break
        except Exception as e:
            self.logger.error(f"生成 Meyer-Neldel 图失败: {e}", exc_info=True)

    def _normalize_meyer_neldel_metrics(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """将当前 evidence 字段转成 VizEngine 需要的 Meyer-Neldel 参数。"""
        normalized = dict(metrics)
        if 'E_MN' not in normalized and 'E_MN_eV' in normalized:
            normalized['E_MN'] = normalized['E_MN_eV']
        if 'R2' not in normalized and 'r_squared' in normalized:
            normalized['R2'] = normalized['r_squared']
        return normalized
    
    def _generate_eis_alignment_plots(
        self,
        data: pd.DataFrame,
        evidences: List[EvidenceUnit],
        viz_paths: Dict[str, str]
    ) -> None:
        """生成 EIS 对齐图"""
        try:
            if data is None or data.empty:
                self.logger.warning("数据为空，跳过 EIS 对齐图生成")
                return
            
            # 查找对齐证据
            for ev in evidences:
                if 'eis_arrhenius_alignment' in ev.tags:
                    # 提取温度信息
                    metrics = ev.support_metrics
                    t_arc = metrics.get('T_arc_K', metrics.get('T_arc'))
                    t_break = metrics.get('T_break_K', metrics.get('T_break'))
                    if t_arc is None or t_break is None:
                        missing = [
                            name for name, value in [('T_arc_K/T_arc', t_arc), ('T_break_K/T_break', t_break)]
                            if value is None
                        ]
                        self.logger.warning(f"EIS 对齐证据缺少参数: {missing}")
                        break

                    # Tier2 (issue 7, 2026-06-01): actually render the alignment plot.
                    # The morphology feature axes ARE present in the S8 export
                    # (arc_diameter_ohm / characteristic_frequency / nyquist_peak_ratio /
                    # median_zimag_ohm), so build a temperature axis + up to two feature
                    # series and call the existing viz_engine.plot_eis_alignment.
                    T_axis, features = self._build_eis_alignment_series(data)
                    if T_axis is None or not features:
                        self.logger.info(
                            f"EIS 对齐证据已识别（T_arc={t_arc}, T_break={t_break}），"
                            "但缺少可用的温度轴/形貌特征列，跳过作图"
                        )
                        break

                    output_path = self.viz_dir / "eis_alignment.png"
                    self.viz_engine.plot_eis_alignment(
                        T_axis=T_axis,
                        features=features,
                        t_arc=float(t_arc),
                        t_break=float(t_break),
                        output_path=output_path,
                        title="EIS-Arrhenius Temperature Alignment (S8)",
                        alignment_threshold=float(metrics.get("alignment_threshold_K", 10.0) or 10.0),
                    )
                    viz_paths['eis_alignment'] = str(output_path)
                    self.logger.info(f"✓ 生成图表: {output_path.name}")
                    break
        except Exception as e:
            self.logger.error(f"生成 EIS 对齐图失败: {e}", exc_info=True)

    def _build_eis_alignment_series(self, data: pd.DataFrame):
        """从 S8 数据构造 EIS 对齐图的温度轴 + 形貌特征序列（Tier2 issue 7）。

        返回 (T_axis ndarray, {feature_name: ndarray})；无可用数据时返回 (None, {})。
        """
        import numpy as _np

        temp_col = next((c for c in ("T_K", "T", "T_mid", "temperature_K") if c in data.columns), None)
        if temp_col is None:
            return None, {}

        candidate_cols = [
            c for c in (
                "arc_diameter_ohm",
                "characteristic_frequency",
                "nyquist_peak_ratio",
                "median_zimag_ohm",
            ) if c in data.columns
        ]
        if not candidate_cols:
            return None, {}

        df = data[[temp_col] + candidate_cols].copy()
        df = df.apply(pd.to_numeric, errors="coerce").dropna(subset=[temp_col])
        df = df.sort_values(temp_col)
        if df.empty:
            return None, {}

        features: Dict[str, _np.ndarray] = {}
        for c in candidate_cols:
            series = df[c]
            # Keep a feature only if it has at least 2 distinct non-null values.
            if series.notna().sum() >= 2 and series.dropna().nunique() >= 2:
                features[c] = series.to_numpy(dtype=float)
                if len(features) >= 2:  # two axes are enough for the twin-axis plot
                    break
        if not features:
            return None, {}
        return df[temp_col].to_numpy(dtype=float), features
    
    def build_atlas(
        self,
        evidences: List[EvidenceUnit],
        sample_ids: List[str],
        metadata: Optional[Dict[str, Any]] = None
    ) -> EvidenceAtlas:
        """
        构建证据地图
        
        Args:
            evidences: 证据单元列表
            sample_ids: 样本 ID 列表
            metadata: 额外的元数据
            
        Returns:
            EvidenceAtlas: 证据地图
        """
        self.logger.info("构建证据地图...")
        
        # 创建证据地图
        atlas = EvidenceAtlas(sample_ids=sample_ids)
        
        # 添加证据
        atlas.add_evidences(evidences)
        
        # 更新元数据
        if metadata:
            atlas.metadata.update(metadata)
        
        self.logger.info(f"证据地图构建完成，包含 {len(evidences)} 条证据")
        
        return atlas
    
    def export_atlas(self, atlas: EvidenceAtlas, filename: str = "s8_evidence_atlas.json") -> str:
        """
        导出证据地图
        
        Args:
            atlas: 证据地图
            filename: 输出文件名
            
        Returns:
            str: 输出文件路径
        """
        output_path = self.output_dir / filename
        
        self.logger.info(f"导出证据地图到: {output_path}")
        
        # 转换 numpy 类型为 Python 原生类型
        self._convert_numpy_types(atlas)
        
        atlas.to_json(str(output_path), indent=2)
        
        self.logger.info("证据地图导出完成")
        
        return str(output_path)
    
    def _convert_numpy_types(self, atlas: EvidenceAtlas) -> None:
        """
        递归转换 numpy 类型为 Python 原生类型
        
        Args:
            atlas: 证据地图
        """
        # 转换证据单元中的 numpy 类型
        for evidence in atlas.evidence_units:
            # 转换 support_metrics 中的 numpy 类型
            if evidence.support_metrics:
                evidence.support_metrics = self._convert_dict_numpy_types(
                    evidence.support_metrics
                )
        
        # 转换 metadata 中的 numpy 类型
        if atlas.metadata:
            atlas.metadata = self._convert_dict_numpy_types(atlas.metadata)
    
    def _convert_dict_numpy_types(self, d: Dict[str, Any]) -> Dict[str, Any]:
        """
        递归转换字典中的 numpy 类型
        
        Args:
            d: 输入字典
            
        Returns:
            Dict[str, Any]: 转换后的字典
        """
        result = {}
        for key, value in d.items():
            if isinstance(value, np.bool_):
                result[key] = bool(value)
            elif isinstance(value, (np.integer, np.int64, np.int32)):
                result[key] = int(value)
            elif isinstance(value, (np.floating, np.float64, np.float32)):
                result[key] = float(value)
            elif isinstance(value, np.ndarray):
                result[key] = value.tolist()
            elif isinstance(value, dict):
                result[key] = self._convert_dict_numpy_types(value)
            elif isinstance(value, list):
                result[key] = [
                    self._convert_value_numpy_type(item) for item in value
                ]
            else:
                result[key] = value
        return result
    
    def _convert_value_numpy_type(self, value: Any) -> Any:
        """转换单个值的 numpy 类型（增强版）"""
        # None 和基本类型直接返回
        if value is None or isinstance(value, (bool, int, float, str)):
            return value
        
        # NumPy 布尔类型
        if isinstance(value, np.bool_):
            return bool(value)
        
        # NumPy 整数类型（包括所有变体）
        if isinstance(value, (np.integer, np.int8, np.int16, np.int32, np.int64,
                              np.uint8, np.uint16, np.uint32, np.uint64)):
            return int(value)
        
        # NumPy 浮点类型（包括所有变体）
        if isinstance(value, (np.floating, np.float16, np.float32, np.float64)):
            # 处理 NaN 和 Inf
            if np.isnan(value):
                return None  # 将 NaN 转换为 None
            if np.isinf(value):
                return float('inf') if value > 0 else float('-inf')
            return float(value)
        
        # NumPy 复数类型
        if isinstance(value, (np.complexfloating, np.complex64, np.complex128)):
            return {'real': float(value.real), 'imag': float(value.imag)}
        
        # NumPy 数组
        if isinstance(value, np.ndarray):
            return value.tolist()
        
        # NumPy 标量（通用处理）
        if isinstance(value, np.generic):
            return value.item()
        
        # 列表和元组（递归处理）
        if isinstance(value, (list, tuple)):
            converted = [self._convert_value_numpy_type(v) for v in value]
            return converted if isinstance(value, list) else tuple(converted)
        
        # 字典（递归处理）
        if isinstance(value, dict):
            return self._convert_dict_numpy_types(value)
        
        return value
    
    def run_pipeline(
        self,
        input_csv_path: str,
        sample_ids: Optional[List[str]] = None,
        enable_visualization: bool = True
    ) -> EvidenceAtlas:
        """
        运行完整的分析流程
        
        Args:
            input_csv_path: 输入 CSV 文件路径
            sample_ids: 样本 ID 列表（可选，如果不提供则从数据中提取）
            enable_visualization: 是否生成可视化图表
            
        Returns:
            EvidenceAtlas: 最终的证据地图
        """
        self.logger.info("=" * 60)
        self.logger.info("Stage 2 Evidence Agent - 分析流程开始")
        self.logger.info("=" * 60)
        
        try:
            # ========== Step 1: 加载数据 ==========
            self.logger.info("\n[Step 1/9] 加载数据")
            data = self.load_data(input_csv_path)
            
            # ========== Step 2: 生成数据画像 ==========
            self.logger.info("\n[Step 2/9] 生成数据画像")
            profile = self.profile_data(data)
            
            # 打印画像摘要
            if self.data_profiler:
                self.data_profiler.print_summary(profile)
            
            # ========== Step 3: 创建分析计划 ==========
            self.logger.info("\n[Step 3/9] 创建分析执行计划")
            execution_plan = self.create_analysis_plan(profile)
            
            # 打印计划摘要
            if self.analysis_planner:
                self.analysis_planner.print_plan(execution_plan)
            
            # ========== Step 4: 数据清洗（SanityChecker）==========
            self.logger.info("\n[Step 4/9] 数据清洗")
            cleaned_data, sanity_evidences = self.filter_data_with_sanity_check(data, profile)
            
            # ========== Step 5: 运行专家模块 ==========
            self.logger.info("\n[Step 5/9] 运行专家模块")
            specialist_results = self.run_specialists(cleaned_data, profile, execution_plan)
            
            # 收集所有证据（包括 SanityChecker 的证据）
            all_evidences = []
            
            # 添加 SanityChecker 证据
            all_evidences.extend(sanity_evidences)
            
            # 添加其他专家证据
            for name, evidences in specialist_results.items():
                all_evidences.extend(evidences)
            
            self.logger.info(f"专家模块总计生成 {len(all_evidences)} 条证据（含 SanityChecker {len(sanity_evidences)} 条）")
            
            # ========== Step 6: 证据合成 ==========
            self.logger.info("\n[Step 6/9] 证据合成")
            synthesized_evidences = self.synthesize_evidence(all_evidences, profile)
            
            # ========== Step 7: 生成可视化图表 ==========
            viz_paths = {}
            if enable_visualization:
                self.logger.info("\n[Step 7/9] 生成可视化图表")
                viz_paths = self.generate_visualizations(
                    cleaned_data,
                    specialist_results,
                    profile
                )
            else:
                self.logger.info("\n[Step 7/9] 跳过可视化（已禁用）")
            
            # ========== Step 8: 构建证据地图 ==========
            self.logger.info("\n[Step 8/9] 构建证据地图")
            if sample_ids is None:
                # 从数据中提取样本 ID
                if "sample_id" in cleaned_data.columns:
                    sample_ids = cleaned_data["sample_id"].unique().tolist()
                else:
                    # 使用 R 和 N 组合作为样本 ID
                    if "R" in cleaned_data.columns and "N" in cleaned_data.columns:
                        sample_ids = [
                            f"S8_R{r:.3f}_N{n:.1f}"
                            for r, n in zip(cleaned_data["R"], cleaned_data["N"])
                        ]
                        sample_ids = list(set(sample_ids))  # 去重
                    else:
                        sample_ids = [f"sample_{i}" for i in range(len(cleaned_data))]
            
            atlas = self.build_atlas(
                evidences=synthesized_evidences,
                sample_ids=sample_ids,
                metadata={
                    "input_file": input_csv_path,
                    "data_profile": profile,
                    "execution_plan": execution_plan,
                    "specialist_count": len(self.specialists),
                    "original_data_rows": len(data),
                    "cleaned_data_rows": len(cleaned_data),
                    "visualization_paths": viz_paths
                }
            )
            
            # ========== Step 9: 导出结果 ==========
            self.logger.info("\n[Step 9/9] 导出结果")
            output_path = self.export_atlas(atlas)
            
            # 导出执行计划、画像、清洗审计和运行摘要
            self._export_metadata(profile, execution_plan, viz_paths)
            self._export_excluded_samples()
            self._export_run_summary(atlas, profile, execution_plan, viz_paths)

            # P-Stage2-A..H: 输出 V2 sample/segment/trend/MN/morphology + stage3_seed.json
            #
            # CANONICAL INTERFACE (Tier1 note 2026-06-01): the V2 pipeline below,
            # which emits `exports/stage3_seed.json`, is the ONE canonical
            # Stage2 -> Stage3 contract that Stage3 actually consumes (validated by
            # tests/test_stage2_current_seed_contract.py and audit_mainline.py).
            # The legacy "V1" specialist evidence atlas exported just above
            # (TrendAnalyzer / ModelCompetitor / MorphologyExpert -> s8_evidence_atlas)
            # is DIAGNOSTIC ONLY and is NOT read by Stage3. The two tracks run
            # independently and are not reconciled today; a real V1/V2
            # reconciliation (or removing the V1 seed path) is Tier 2 work.
            v2_summary = self._export_stage3_seed_pipeline(
                raw_data=data,
                cleaned_data=cleaned_data,
                profile=profile,
                input_csv_path=input_csv_path,
            )
            self.logger.info(
                "  V2 stage3_seed: %d samples, %d segments, %d evidences",
                v2_summary.get("n_samples", 0),
                v2_summary.get("n_segments", 0),
                v2_summary.get("n_evidences", 0),
            )
            
            # ========== 打印最终摘要 ==========
            self.logger.info("\n" + "=" * 60)
            self.logger.info("分析完成！最终摘要:")
            self.logger.info("=" * 60)
            
            summary = atlas.summary()
            for key, value in summary.items():
                if key != "metadata":
                    self.logger.info(f"  {key}: {value}")
            
            self.logger.info(f"\n输出文件:")
            self.logger.info(f"  证据地图: {output_path}")
            
            if viz_paths:
                self.logger.info(f"  可视化图表: {len(viz_paths)} 个")
                for name, path in viz_paths.items():
                    self.logger.info(f"    - {name}: {Path(path).name}")
            
            self.logger.info("=" * 60)
            
            return atlas
            
        except Exception as e:
            self.logger.error(f"\n分析流程失败: {e}", exc_info=True)
            raise
    
    def _export_metadata(
        self,
        profile: Dict[str, Any],
        execution_plan: Dict[str, Any],
        viz_paths: Dict[str, str]
    ) -> None:
        """
        导出元数据（画像、计划、可视化路径）
        
        Args:
            profile: 数据画像
            execution_plan: 执行计划
            viz_paths: 可视化路径
        """
        
        # 自定义 JSON 编码器，处理 numpy 类型
        class NumpyEncoder(json.JSONEncoder):
            def default(self, obj):
                if isinstance(obj, np.integer):
                    return int(obj)
                elif isinstance(obj, np.floating):
                    return float(obj)
                elif isinstance(obj, np.ndarray):
                    return obj.tolist()
                elif isinstance(obj, (np.bool_, bool)):
                    return bool(obj)
                return super().default(obj)
        
        try:
            # 导出数据画像
            profile_path = self.output_dir / "data_profile.json"
            with open(profile_path, 'w', encoding='utf-8') as f:
                json.dump(profile, f, indent=2, ensure_ascii=False, cls=NumpyEncoder)
            self.logger.info(f"  数据画像: {profile_path}")
            
            # 导出执行计划
            plan_path = self.output_dir / "execution_plan.json"
            with open(plan_path, 'w', encoding='utf-8') as f:
                json.dump(execution_plan, f, indent=2, ensure_ascii=False, cls=NumpyEncoder)
            self.logger.info(f"  执行计划: {plan_path}")
            
            # 导出可视化清单；即使本次没有图，也写出空 manifest 供 Stage3 strict real 读取。
            viz_manifest_path = self.output_dir / "visualization_manifest.json"
            with open(viz_manifest_path, 'w', encoding='utf-8') as f:
                json.dump(viz_paths or {}, f, indent=2, ensure_ascii=False, cls=NumpyEncoder)
            self.logger.info(f"  可视化清单: {viz_manifest_path}")
            
        except Exception as e:
            self.logger.error(f"导出元数据失败: {e}", exc_info=True)

    def _export_excluded_samples(self) -> None:
        """导出逐行排除原因表。"""
        if self.excluded_samples is None or self.excluded_samples.empty:
            self.logger.info("  排除样品表: 无排除记录")
            return

        csv_path = self.output_dir / "excluded_samples.csv"
        json_path = self.output_dir / "excluded_samples.json"
        self.excluded_samples.to_csv(csv_path, index=False, encoding='utf-8-sig')
        self.excluded_samples.to_json(json_path, orient='records', force_ascii=False, indent=2)
        self.logger.info(f"  排除样品表: {csv_path}")
        self.logger.info(f"  排除样品 JSON: {json_path}")

    # ------------------------------------------------------------------
    # P-Stage2-H: V2 pipeline (sample/segment/trend/MN/morphology + stage3_seed)
    # ------------------------------------------------------------------

    def _export_stage3_seed_pipeline(
        self,
        raw_data: pd.DataFrame,
        cleaned_data: pd.DataFrame,
        profile: Dict[str, Any],
        input_csv_path: str,
    ) -> Dict[str, Any]:
        """
        Build sample-level / segment-level / trend / MN / morphology artifacts and
        emit stage3_seed.json. Uses cleaned_data for sample summary (same scope as
        legacy specialists) but raw_data for row_level QC visibility.
        """
        from datetime import datetime as _dt

        run_id = _dt.utcnow().strftime("stage2-%Y%m%dT%H%M%SZ")

        # Row-level + sample-level
        raw_points_all = _agg.build_raw_points(raw_data)
        row_qc = _agg.build_row_level_qc(raw_points_all)

        cleaned_points = _agg.build_raw_points(cleaned_data)
        summaries = _agg.build_sample_summaries(cleaned_data, points=cleaned_points)

        # Segment-level fits + per-sample model competition
        segments, model_rows, model_summary = _segfit.fit_per_sample(cleaned_points, summaries)

        # Sample-level trends
        trends = _strend.analyze_sample_trends(summaries)

        # Segment-level Meyer-Neldel
        mn_result = _mnseg.analyze_meyer_neldel_from_segments(segments)

        # Morphology
        morph_features_df = _morphf.build_morphology_features(cleaned_points, cleaned_data)
        morph_summary = _morphf.summarize_morphology(summaries, morph_features_df)

        input_path = Path(input_csv_path)
        input_files = {"input_csv": str(input_path)}
        input_hashes = {}
        if input_path.exists():
            input_hashes["input_csv"] = hashlib.sha256(input_path.read_bytes()).hexdigest()

        # Build seed
        seed = _seedb.build_stage3_seed(
            run_id=run_id,
            summaries=summaries,
            segments=segments,
            trends=trends,
            model_summary=model_summary,
            mn_result=mn_result,
            morphology_summary=morph_summary,
            data_profile=profile,
            input_files=input_files,
            input_hashes=input_hashes,
        )

        # ---------- write everything ----------
        out = self.output_dir

        # canonical raw points
        pd.DataFrame([p.model_dump() for p in raw_points_all]).to_csv(
            out / "canonical_raw_points.csv", index=False, encoding="utf-8-sig"
        )

        pd.DataFrame([q.model_dump() for q in row_qc]).to_csv(
            out / "row_level_qc.csv", index=False, encoding="utf-8-sig"
        )

        # sample manifest = small projection of summaries
        manifest_df = pd.DataFrame(
            [
                {
                    "sample_id": s.sample_id,
                    "R": s.R,
                    "N": s.N,
                    "n_temperature_points": s.n_temperature_points,
                    "T_min_K": s.temperature_min_K,
                    "T_max_K": s.temperature_max_K,
                    "quality_flags": ";".join(s.quality_flags),
                }
                for s in summaries
            ]
        )
        manifest_df.to_csv(out / "sample_manifest.csv", index=False, encoding="utf-8-sig")

        _agg.sample_summaries_to_dataframe(summaries).to_csv(
            out / "sample_level_summary.csv", index=False, encoding="utf-8-sig"
        )

        seg_df = _segfit.segments_to_dataframe(segments)
        if not seg_df.empty:
            seg_df.to_csv(
                out / "segment_level_arrhenius.csv", index=False, encoding="utf-8-sig"
            )

        model_df = _segfit.model_rows_to_dataframe(model_rows)
        if not model_df.empty:
            model_df.to_csv(
                out / "model_comparison_by_sample.csv", index=False, encoding="utf-8-sig"
            )

        if morph_features_df is not None and not morph_features_df.empty:
            morph_features_df.to_csv(
                out / "eis_morphology_features.csv", index=False, encoding="utf-8-sig"
            )

        # JSON outputs
        with open(out / "trend_results.json", "w", encoding="utf-8") as f:
            json.dump(
                [t.model_dump() for t in trends], f, indent=2, ensure_ascii=False
            )
        with open(out / "meyer_neldel_analysis.json", "w", encoding="utf-8") as f:
            json.dump(mn_result, f, indent=2, ensure_ascii=False)
        with open(out / "evidence_units.json", "w", encoding="utf-8") as f:
            json.dump(
                [e.model_dump() for e in seed.evidence_units], f, indent=2, ensure_ascii=False
            )
        try:
            with open(out / "stage3_seed.json", "w", encoding="utf-8") as f:
                f.write(seed.model_dump_json(indent=2))
        except Exception as e:
            self.logger.warning(
                f"  V2: model_dump_json failed ({type(e).__name__}: {e}); "
                f"falling back to numpy-stripped json.dump"
            )
            seed_dict = self._convert_dict_numpy_types(seed.model_dump())
            with open(out / "stage3_seed.json", "w", encoding="utf-8") as f:
                json.dump(seed_dict, f, indent=2, ensure_ascii=False, default=str)

        # critical_transition_analysis = projection from trend_results
        crit = {
            "trends_with_transitions": [
                {
                    "trend_id": t.trend_id,
                    "target_metric": t.target_metric,
                    "predictor": t.predictor,
                    "candidate_transition_points": t.candidate_transition_points,
                    "strength": t.strength,
                }
                for t in trends
                if t.candidate_transition_points
            ]
        }
        with open(out / "critical_transition_analysis.json", "w", encoding="utf-8") as f:
            json.dump(crit, f, indent=2, ensure_ascii=False)

        self.logger.info(f"  V2: wrote sample_level_summary.csv ({len(summaries)} samples)")
        self.logger.info(f"  V2: wrote segment_level_arrhenius.csv ({len(segments)} segments)")
        self.logger.info(f"  V2: wrote model_comparison_by_sample.csv ({len(model_rows)} rows)")
        self.logger.info(f"  V2: wrote evidence_units.json ({len(seed.evidence_units)} units)")
        self.logger.info(f"  V2: wrote stage3_seed.json (seed_id={seed.seed_id})")

        return {
            "n_samples": len(summaries),
            "n_segments": len(segments),
            "n_trends": len(trends),
            "n_evidences": len(seed.evidence_units),
            "stage3_seed_id": seed.seed_id,
        }

    def _export_run_summary(
        self,
        atlas: EvidenceAtlas,
        profile: Dict[str, Any],
        execution_plan: Dict[str, Any],
        viz_paths: Dict[str, str]
    ) -> None:
        """导出机器可读和 Markdown 版运行摘要，作为当前事实源。"""
        summary = atlas.summary()
        excluded_count = 0 if self.excluded_samples is None else len(self.excluded_samples)
        run_summary = {
            'input_file': atlas.metadata.get('input_file'),
            'generated_at': atlas.metadata.get('generated_at'),
            'original_data_rows': atlas.metadata.get('original_data_rows'),
            'cleaned_data_rows': atlas.metadata.get('cleaned_data_rows'),
            'excluded_records': excluded_count,
            'evidence_summary': {
                'total_evidences': summary.get('total_evidences'),
                'by_theme': summary.get('by_theme'),
                'by_claim_level': summary.get('by_claim_level'),
                'avg_confidence': summary.get('avg_confidence'),
                'high_confidence_count': summary.get('high_confidence_count')
            },
            'data_profile': profile,
            'execution_plan': execution_plan,
            'visualization_paths': viz_paths
        }

        json_path = self.output_dir / "run_summary.json"
        md_path = self.output_dir / "run_summary.md"

        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(self._convert_dict_numpy_types(run_summary), f, indent=2, ensure_ascii=False)

        md_lines = [
            "# Stage2 Run Summary",
            "",
            f"- Input file: `{run_summary['input_file']}`",
            f"- Generated at: `{run_summary['generated_at']}`",
            f"- Original rows: {run_summary['original_data_rows']}",
            f"- Cleaned rows: {run_summary['cleaned_data_rows']}",
            f"- Excluded records: {excluded_count}",
            f"- Total evidences: {summary.get('total_evidences')}",
            f"- Average confidence: {summary.get('avg_confidence'):.4f}",
            "",
            "## Evidence By Theme",
            ""
        ]
        for theme, count in summary.get('by_theme', {}).items():
            md_lines.append(f"- `{theme}`: {count}")
        md_lines.extend(["", "## Evidence By Claim Level", ""])
        for level, count in summary.get('by_claim_level', {}).items():
            md_lines.append(f"- `{level}`: {count}")
        md_lines.extend(["", "## Visualizations", ""])
        if viz_paths:
            for name, path in viz_paths.items():
                md_lines.append(f"- `{name}`: `{path}`")
        else:
            md_lines.append("- None")

        with open(md_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(md_lines) + "\n")

        self.logger.info(f"  运行摘要: {json_path}")
        self.logger.info(f"  运行摘要 Markdown: {md_path}")


def _demo_main_legacy():
    """示例：如何使用 Stage2Agent"""
    
    import sys
    
    # 创建 agent（自动注册所有模块）
    agent = Stage2Agent(
        output_dir="./exports",
        viz_dir="./exports/visualizations",
        log_level=logging.INFO,
        auto_register=True
    )
    
    print("\n" + "=" * 60)
    print("Stage 2 Evidence Agent")
    print("=" * 60)
    print("\n已自动注册以下模块:")
    print("  [Data Cleaning]")
    print("    - SanityChecker: 数据清洗器")
    print("  [Planner]")
    print("    - DataProfiler: 数据画像器")
    print("    - AnalysisPlanner: 智能计划器")
    print("  [Specialists]")
    print("    - TrendAnalyzer: 组分趋势分析")
    print("    - ModelCompetitor: 物理模型竞争")
    print("    - MorphologyExpert: EIS 形貌分析")
    print("  [Synthesizer]")
    print("    - EvidenceSynthesizer: 证据合成器")
    print("  [Visualization]")
    print("    - VizEngine: 学术级绘图引擎")
    
    print("\n使用方法:")
    print("  1. 准备输入 CSV 文件（包含 R, N, T, Ea, sigma 等列）")
    print("  2. 调用 agent.run_pipeline('path/to/input.csv')")
    print("  3. 查看输出目录 ./exports/ 中的结果")
    
    # 如果提供了命令行参数，运行分析
    if len(sys.argv) > 1:
        input_csv = sys.argv[1]
        print(f"\n开始分析: {input_csv}")
        
        try:
            atlas = agent.run_pipeline(input_csv, enable_visualization=True)
            print("\n分析成功完成！")
        except Exception as e:
            print(f"\n分析失败: {e}")
            sys.exit(1)
    else:
        print("\n提示: 可以通过命令行参数指定输入文件")
        print("  python main_agent.py path/to/input.csv")
    
    print("\n" + "=" * 60)


def main():
    """Command line entry point for the Stage2 evidence pipeline."""
    import argparse

    default_output = Path(__file__).resolve().parent / "exports"
    parser = argparse.ArgumentParser(description="Stage2 Evidence Agent")
    parser.add_argument("input_csv", nargs="?", help="Input CSV containing S8 row-level data")
    parser.add_argument(
        "--output-dir",
        default=str(default_output),
        help="Directory for Stage2 exports (default: stage2_statistics/exports)",
    )
    parser.add_argument(
        "--no-visualization",
        action="store_true",
        help="Skip visualization generation but still write visualization_manifest.json",
    )
    args = parser.parse_args()

    if not args.input_csv:
        parser.print_help()
        return

    agent = Stage2Agent(
        output_dir=args.output_dir,
        viz_dir=str(Path(args.output_dir) / "visualizations"),
        log_level=logging.INFO,
        auto_register=True,
    )
    agent.run_pipeline(args.input_csv, enable_visualization=not args.no_visualization)


if __name__ == "__main__":
    main()
