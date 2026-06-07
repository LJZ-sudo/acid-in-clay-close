"""
Analysis Planner - 智能分析计划器
根据 S8 数据分布动态调整分析强度
"""

from typing import Dict, Any, List


class AnalysisPlanner:
    """
    智能分析计划器
    
    根据数据画像决定启动哪些专家模块
    """
    
    def __init__(
        self,
        name: str = "AnalysisPlanner",
        wide_temp_threshold: float = 50.0,  # 宽温区阈值（K）
        min_quality_ratio: float = 0.5  # 最低质量数据占比
    ):
        """
        初始化分析计划器
        
        Args:
            name: 计划器名称
            wide_temp_threshold: 宽温区判定阈值（K）
            min_quality_ratio: 启动 model_competitor 所需的最低质量数据占比
        """
        self.name = name
        self.wide_temp_threshold = wide_temp_threshold
        self.min_quality_ratio = min_quality_ratio
    
    def create_plan(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        """
        创建分析执行计划
        
        Args:
            profile: DataProfiler 输出的数据画像
            
        Returns:
            Dict: 执行计划，包含各专家模块的启动状态和计划摘要
        """
        plan = {
            'specialists': {},
            'plan_summary': '',
            'reasons': {},
            'expected_evidences': {}
        }
        
        # 决策逻辑
        
        # 1. sanity_checker: 永远启动（数据清洗是必需的）
        plan['specialists']['sanity_checker'] = True
        plan['reasons']['sanity_checker'] = "数据清洗是所有分析的基础，必须执行"
        plan['expected_evidences']['sanity_checker'] = ['data_quality', 'outlier_detection']
        
        # 2. trend_analyzer: 永远启动（组分敏感性是核心分析）
        plan['specialists']['trend_analyzer'] = True
        plan['reasons']['trend_analyzer'] = "组分敏感性分析是 S8 材料的核心研究目标，必须执行"
        plan['expected_evidences']['trend_analyzer'] = [
            'composition_sensitivity',
            'critical_breakpoint',
            'nonlinear_trend'
        ]
        
        # 3. model_competitor: 条件启动
        plan['specialists']['model_competitor'] = self._should_enable_model_competitor(profile)
        plan['reasons']['model_competitor'] = self._get_model_competitor_reason(profile)
        plan['expected_evidences']['model_competitor'] = [
            'meyer_neldel',
            'vtf_preferred',
            'arrhenius_preferred'
        ]
        
        # 4. morphology_expert: 条件启动
        plan['specialists']['morphology_expert'] = self._should_enable_morphology_expert(profile)
        plan['reasons']['morphology_expert'] = self._get_morphology_expert_reason(profile)
        plan['expected_evidences']['morphology_expert'] = [
            'eis_arrhenius_alignment',
            'phase_transition',
            'structural_reorganization'
        ]
        
        # 5. evidence_synthesizer: 永远启动（证据合成是最后一步）
        plan['specialists']['evidence_synthesizer'] = True
        plan['reasons']['evidence_synthesizer'] = "证据合成是生成高级 Question 的必需步骤，必须执行"
        plan['expected_evidences']['evidence_synthesizer'] = [
            'mechanistic_question',
            'cross_specialist_synthesis'
        ]
        
        # 生成计划摘要
        plan['plan_summary'] = self._generate_plan_summary(plan, profile)
        
        # 统计信息
        plan['total_specialists'] = len(plan['specialists'])
        plan['enabled_specialists'] = sum(1 for enabled in plan['specialists'].values() if enabled)
        plan['disabled_specialists'] = plan['total_specialists'] - plan['enabled_specialists']
        
        return plan
    
    def _should_enable_model_competitor(self, profile: Dict[str, Any]) -> bool:
        """
        判断是否启动 model_competitor
        
        条件：
        1. 温度跨度 > 50K（宽温区）
        2. 高质量数据占比充足
        
        Args:
            profile: 数据画像
            
        Returns:
            bool: 是否启动
        """
        # 检查温度覆盖度
        temp_cov = profile.get('temperature_coverage', {})
        is_wide_temp = temp_cov.get('is_wide_temperature_range', False)
        T_range = temp_cov.get('T_range', 0)
        
        # 检查数据质量
        quality = profile.get('quality_assessment', {})
        quality_ratio = quality.get('high_quality_ratio', 0)
        
        # 检查特征完整度
        features = profile.get('feature_completeness', {})
        has_conductivity = features.get('has_conductivity', False)
        has_activation_energy = features.get('has_activation_energy', False)
        
        # 决策逻辑
        if not is_wide_temp:
            return False
        
        if not has_conductivity or not has_activation_energy:
            return False
        
        if quality_ratio < self.min_quality_ratio:
            return False
        
        return True
    
    def _get_model_competitor_reason(self, profile: Dict[str, Any]) -> str:
        """获取 model_competitor 的启动原因"""
        temp_cov = profile.get('temperature_coverage', {})
        quality = profile.get('quality_assessment', {})
        features = profile.get('feature_completeness', {})
        
        is_wide_temp = temp_cov.get('is_wide_temperature_range', False)
        T_range = temp_cov.get('T_range', 0)
        quality_ratio = quality.get('high_quality_ratio', 0)
        has_conductivity = features.get('has_conductivity', False)
        has_activation_energy = features.get('has_activation_energy', False)
        
        if not is_wide_temp:
            return f"温度范围较窄（{T_range:.1f} K < {self.wide_temp_threshold} K），不适合 VTF 模型拟合"
        
        if not has_conductivity:
            return "缺少电导率数据，无法进行 Arrhenius/VTF 模型竞争"
        
        if not has_activation_energy:
            return "缺少活化能数据，无法进行 Meyer-Neldel 分析"
        
        if quality_ratio < self.min_quality_ratio:
            return f"高质量数据占比不足（{quality_ratio*100:.1f}% < {self.min_quality_ratio*100:.0f}%）"
        
        return (
            f"数据满足宽温区条件（{T_range:.1f} K > {self.wide_temp_threshold} K），"
            f"且高质量数据充足（{quality_ratio*100:.1f}%），适合进行模型竞争分析"
        )
    
    def _should_enable_morphology_expert(self, profile: Dict[str, Any]) -> bool:
        """
        判断是否启动 morphology_expert
        
        条件：
        1. 存在 EIS 形貌特征
        
        Args:
            profile: 数据画像
            
        Returns:
            bool: 是否启动
        """
        features = profile.get('feature_completeness', {})
        has_eis_features = features.get('has_eis_features', False)
        
        return has_eis_features
    
    def _get_morphology_expert_reason(self, profile: Dict[str, Any]) -> str:
        """获取 morphology_expert 的启动原因"""
        features = profile.get('feature_completeness', {})
        has_eis_features = features.get('has_eis_features', False)
        n_eis_features = features.get('n_eis_features', 0)
        
        if not has_eis_features:
            return "缺少 EIS 形貌特征数据，无法进行 EIS-Arrhenius 对齐分析"
        
        return f"检测到 {n_eis_features} 个 EIS 形貌特征，可以进行 EIS-Arrhenius 对齐分析"
    
    def _generate_plan_summary(
        self,
        plan: Dict[str, Any],
        profile: Dict[str, Any]
    ) -> str:
        """
        生成计划摘要（自然语言描述）
        
        Args:
            plan: 执行计划
            profile: 数据画像
            
        Returns:
            str: 计划摘要
        """
        specialists = plan['specialists']
        enabled_count = sum(1 for enabled in specialists.values() if enabled)
        total_count = len(specialists)
        
        # 提取关键信息
        temp_cov = profile.get('temperature_coverage', {})
        features = profile.get('feature_completeness', {})
        quality = profile.get('quality_assessment', {})
        scale = profile.get('data_scale', {})
        
        is_wide_temp = temp_cov.get('is_wide_temperature_range', False)
        has_eis = features.get('has_eis_features', False)
        quality_grade = quality.get('quality_grade', 'unknown')
        total_rows = scale.get('total_rows', 0)
        
        # 构建摘要
        summary_parts = []
        
        # 数据规模
        summary_parts.append(f"数据包含 {total_rows} 个样本")
        
        # 温度覆盖
        if is_wide_temp:
            T_range = temp_cov.get('T_range', 0)
            summary_parts.append(f"宽温区数据（跨度 {T_range:.1f} K）")
        else:
            summary_parts.append("窄温区数据")
        
        # EIS 特征
        if has_eis:
            n_eis = features.get('n_eis_features', 0)
            summary_parts.append(f"包含 {n_eis} 个 EIS 形貌特征")
        else:
            summary_parts.append("无 EIS 特征")
        
        # 数据质量
        summary_parts.append(f"数据质量为 {quality_grade}")
        
        # 启动状态
        if enabled_count == total_count:
            summary_parts.append(f"将全量启动所有 {total_count} 个分析专家")
        else:
            summary_parts.append(
                f"将启动 {enabled_count}/{total_count} 个分析专家"
            )
        
        # 列出禁用的专家
        disabled = [name for name, enabled in specialists.items() if not enabled]
        if disabled:
            summary_parts.append(f"（禁用: {', '.join(disabled)}）")
        
        summary = "，".join(summary_parts) + "。"
        
        return summary
    
    def print_plan(self, plan: Dict[str, Any]) -> None:
        """
        打印执行计划
        
        Args:
            plan: 执行计划
        """
        print("\n" + "=" * 60)
        print("分析执行计划")
        print("=" * 60)
        
        print(f"\n[计划摘要]")
        print(f"  {plan['plan_summary']}")
        
        print(f"\n[专家模块启动状态]")
        for specialist, enabled in plan['specialists'].items():
            status = "[启动]" if enabled else "[禁用]"
            print(f"  {status} {specialist}")
            print(f"       原因: {plan['reasons'][specialist]}")
        
        print(f"\n[统计信息]")
        print(f"  总专家数: {plan['total_specialists']}")
        print(f"  启动数: {plan['enabled_specialists']}")
        print(f"  禁用数: {plan['disabled_specialists']}")
        
        print("\n" + "=" * 60)
    
    def __repr__(self) -> str:
        return f"AnalysisPlanner(name='{self.name}')"
