"""
Evidence Synthesizer - 证据合成器
合成三层 Claim 包 (Observation/Interpretation/Question)
"""

from typing import List, Dict, Any, Optional, Set
from collections import defaultdict

try:
    from ..core.schema import EvidenceUnit, ClaimLevel, EvidenceTheme
except ImportError:
    from core.schema import EvidenceUnit, ClaimLevel, EvidenceTheme


class EvidenceSynthesizer:
    """
    证据合成器
    
    不继承 BaseSpecialist，因为输入是 EvidenceUnit 列表而非 DataFrame
    
    核心任务：
    1. 扫描证据列表中的 tags 和 theme
    2. 识别证据模式并生成高级 Question
    3. 合成跨专家的综合性发现
    """
    
    def __init__(
        self,
        name: str = "EvidenceSynthesizer",
        enable_cross_synthesis: bool = True
    ):
        """
        初始化证据合成器
        
        Args:
            name: 合成器名称
            enable_cross_synthesis: 是否启用跨专家证据合成
        """
        self.name = name
        self.enable_cross_synthesis = enable_cross_synthesis
    
    def synthesize(
        self,
        evidence_list: List[EvidenceUnit],
        profile: Optional[Dict[str, Any]] = None
    ) -> List[EvidenceUnit]:
        """
        合成证据并生成高级 Question
        
        Args:
            evidence_list: 输入的证据单元列表
            profile: 数据画像（可选）
            
        Returns:
            List[EvidenceUnit]: 包含原始证据和新生成 Question 的完整列表
        """
        # 复制原始列表，避免修改输入
        synthesized = evidence_list.copy()
        
        if not self.enable_cross_synthesis:
            return synthesized
        
        # 分析证据模式
        patterns = self._analyze_evidence_patterns(evidence_list)
        
        # 触发器 1: VTF + 组分敏感突变
        vtf_composition_questions = self._trigger_vtf_composition_transition(
            evidence_list, patterns
        )
        synthesized.extend(vtf_composition_questions)
        
        # 触发器 2: Meyer-Neldel 补偿效应
        mn_questions = self._trigger_meyer_neldel_universality(
            evidence_list, patterns
        )
        synthesized.extend(mn_questions)
        
        # 触发器 3: EIS-Arrhenius 对齐 + 相变
        phase_transition_questions = self._trigger_phase_transition_mechanism(
            evidence_list, patterns
        )
        synthesized.extend(phase_transition_questions)
        
        # 触发器 4: 多重证据收敛
        convergence_questions = self._trigger_evidence_convergence(
            evidence_list, patterns
        )
        synthesized.extend(convergence_questions)

        # 触发器 5: 基于数据画像的冷端传输问题
        profile_questions = self._trigger_profile_based_questions(
            profile, patterns
        )
        synthesized.extend(profile_questions)
        
        return synthesized
    
    def _analyze_evidence_patterns(
        self,
        evidence_list: List[EvidenceUnit]
    ) -> Dict[str, Any]:
        """
        分析证据模式
        
        Args:
            evidence_list: 证据列表
            
        Returns:
            Dict: 证据模式统计
        """
        patterns = {
            'all_tags': set(),
            'themes': defaultdict(int),
            'claim_levels': defaultdict(int),
            'tag_counts': defaultdict(int),
            'theme_tag_map': defaultdict(set),
            'evidences_by_tag': defaultdict(list),
            'evidences_by_theme': defaultdict(list)
        }
        
        for evidence in evidence_list:
            # 收集所有标签
            for tag in evidence.tags:
                patterns['all_tags'].add(tag)
                patterns['tag_counts'][tag] += 1
                patterns['evidences_by_tag'][tag].append(evidence)
                patterns['theme_tag_map'][evidence.theme].add(tag)
            
            # 统计主题和层级
            patterns['themes'][evidence.theme] += 1
            patterns['claim_levels'][evidence.claim_level] += 1
            patterns['evidences_by_theme'][evidence.theme].append(evidence)
        
        return patterns
    
    def _trigger_vtf_composition_transition(
        self,
        evidence_list: List[EvidenceUnit],
        patterns: Dict[str, Any]
    ) -> List[EvidenceUnit]:
        """
        触发器 1: VTF 优胜 + 组分敏感突变
        
        如果同时存在 VTF 优势和组分突变证据，生成 Question
        
        Args:
            evidence_list: 证据列表
            patterns: 证据模式
            
        Returns:
            List[EvidenceUnit]: 生成的 Question 证据
        """
        questions = []
        
        # 检查是否存在 VTF 优势标签（放宽条件）
        vtf_tags = ['vtf_preferred', 'glass_transition', 'cooperative_dynamics', 'vtf', 'non_arrhenius']
        has_vtf = any(tag in patterns['all_tags'] for tag in vtf_tags)
        
        # 检查是否存在组分敏感突变标签（放宽条件）
        composition_tags = [
            'critical_breakpoint', 'percolation_hint', 'R_critical', 'N_critical',
            'composition_sensitivity', 'nonlinear_trend', 'composition_dependent', 'trend_analysis'
        ]
        has_composition_transition = any(tag in patterns['all_tags'] for tag in composition_tags)
        
        if has_vtf and has_composition_transition:
            # 提取关键信息
            vtf_evidences = []
            for tag in vtf_tags:
                vtf_evidences.extend(patterns['evidences_by_tag'].get(tag, []))
            
            composition_evidences = []
            for tag in composition_tags:
                composition_evidences.extend(patterns['evidences_by_tag'].get(tag, []))
            
            # 提取临界 R 值
            critical_R_values = []
            for e in composition_evidences:
                if 'critical_value' in e.support_metrics:
                    critical_R_values.append(e.support_metrics['critical_value'])
                elif 'critical_R' in e.support_metrics:
                    critical_R_values.append(e.support_metrics['critical_R'])
            
            # 提取 T0 值
            T0_values = []
            for e in vtf_evidences:
                if 'T0_K' in e.support_metrics:
                    T0_values.append(e.support_metrics['T0_K'])
            
            # 生成 Question
            if critical_R_values:
                R_critical = critical_R_values[0]
                
                statement = (
                    f"S8 体系在 R = {R_critical:.2f} 处发生的动态转变，"
                    f"是否是由氢键网络的局部受限引发的类似玻璃化转变过程？"
                )
                
                if T0_values:
                    T0 = T0_values[0]
                    statement += (
                        f" VTF 分析提取的理想玻璃化温度 T0 = {T0:.1f} K "
                        f"是否与该组分点的微观结构重组相关联？"
                    )
                
                questions.append(EvidenceUnit(
                    claim_level=ClaimLevel.question,
                    theme=EvidenceTheme.phase_transition,
                    statement=statement,
                    support_metrics={
                        'critical_R': float(critical_R_values[0]) if critical_R_values else None,
                        'T0_K': float(T0_values[0]) if T0_values else None,
                        'synthesis_trigger': 'vtf_composition_transition',
                        'n_vtf_evidences': len(vtf_evidences),
                        'n_composition_evidences': len(composition_evidences)
                    },
                    confidence=0.70,
                    confidence_basis={
                        'rule_id': 'synthesis_vtf_composition_transition',
                        'formula': 'fixed 0.70 when VTF-like tags and composition-transition tags co-occur',
                        'inputs': {
                            'n_vtf_evidences': len(vtf_evidences),
                            'n_composition_evidences': len(composition_evidences)
                        },
                        'interpretation': '跨证据合成问题，不是实验结论'
                    },
                    tags=['mechanistic_question', 'vtf_composition_coupling', 'hydrogen_bond_network']
                ))
            else:
                # 没有具体 R 值，生成更通用的问题
                statement = (
                    "S8 体系中观察到的 VTF 动力学特征与组分敏感的活化能跃迁，"
                    "是否共同指向氢键网络受限引发的玻璃化转变过程？"
                    "这种动态转变的微观起源是什么？"
                )
                
                questions.append(EvidenceUnit(
                    claim_level=ClaimLevel.question,
                    theme=EvidenceTheme.phase_transition,
                    statement=statement,
                    support_metrics={
                        'synthesis_trigger': 'vtf_composition_transition',
                        'n_vtf_evidences': len(vtf_evidences),
                        'n_composition_evidences': len(composition_evidences)
                    },
                    confidence=0.65,
                    confidence_basis={
                        'rule_id': 'synthesis_vtf_composition_transition_generic',
                        'formula': 'fixed 0.65 when VTF-like and composition-sensitive evidence co-occur without a specific critical value',
                        'inputs': {
                            'n_vtf_evidences': len(vtf_evidences),
                            'n_composition_evidences': len(composition_evidences)
                        },
                        'interpretation': '跨证据合成问题，不是实验结论'
                    },
                    tags=['mechanistic_question', 'vtf_composition_coupling']
                ))
        
        return questions
    
    def _trigger_meyer_neldel_universality(
        self,
        evidence_list: List[EvidenceUnit],
        patterns: Dict[str, Any]
    ) -> List[EvidenceUnit]:
        """
        触发器 2: Meyer-Neldel 补偿效应
        
        如果存在强烈的 MN 标签，生成关于普适性的 Question
        
        Args:
            evidence_list: 证据列表
            patterns: 证据模式
            
        Returns:
            List[EvidenceUnit]: 生成的 Question 证据
        """
        questions = []
        
        # 检查 Meyer-Neldel 标签
        mn_tags = ['meyer_neldel', 'compensation_effect']
        has_mn = any(tag in patterns['all_tags'] for tag in mn_tags)
        
        if has_mn:
            # 提取 MN 证据
            mn_evidences = []
            for tag in mn_tags:
                mn_evidences.extend(patterns['evidences_by_tag'].get(tag, []))
            
            # 提取 E_MN 值和 R² 值
            E_MN_values = []
            r2_values = []
            n_points_total = 0
            
            for e in mn_evidences:
                if 'E_MN_eV' in e.support_metrics:
                    E_MN_values.append(e.support_metrics['E_MN_eV'])
                if 'r_squared' in e.support_metrics:
                    r2_values.append(e.support_metrics['r_squared'])
                if 'n_points' in e.support_metrics:
                    n_points_total += e.support_metrics['n_points']
            
            # 判断是否为强烈的 MN 效应（放宽条件：R² > 0.8）
            strong_mn = any(r2 > 0.8 for r2 in r2_values) if r2_values else False
            
            if strong_mn:
                E_MN_avg = sum(E_MN_values) / len(E_MN_values) if E_MN_values else None
                r2_max = max(r2_values) if r2_values else None
                
                statement = (
                    f"多重离散的 Ea 数据点能塌缩到同一条 Meyer-Neldel 补偿线上 "
                    f"(R2 = {r2_max:.3f}, E_MN = {E_MN_avg:.3f} eV)，"
                    f"是否意味着所有 S8 样本共享同一种基础跳跃势垒机制？"
                    f"这种普适的补偿关系背后的物理起源是什么——"
                    f"是多声子辅助跃迁、还是势垒分布的统计效应？"
                )
                
                questions.append(EvidenceUnit(
                    claim_level=ClaimLevel.question,
                    theme=EvidenceTheme.transport_dynamics,
                    statement=statement,
                    support_metrics={
                        'E_MN_eV': float(E_MN_avg) if E_MN_avg else None,
                        'r_squared_max': float(r2_max) if r2_max else None,
                        'n_points_total': n_points_total,
                        'synthesis_trigger': 'meyer_neldel_universality',
                        'n_mn_evidences': len(mn_evidences)
                    },
                    confidence=0.75,
                    confidence_basis={
                        'rule_id': 'synthesis_meyer_neldel_universality',
                        'formula': 'fixed 0.75 when Meyer-Neldel r_squared > 0.8',
                        'inputs': {
                            'r_squared_max': float(r2_max) if r2_max else None,
                            'n_mn_evidences': len(mn_evidences)
                        },
                        'interpretation': 'MN 普适性问题，用于 Stage3 假说生成'
                    },
                    tags=['mechanistic_question', 'meyer_neldel', 'universal_mechanism']
                ))
        
        return questions
    
    def _trigger_phase_transition_mechanism(
        self,
        evidence_list: List[EvidenceUnit],
        patterns: Dict[str, Any]
    ) -> List[EvidenceUnit]:
        """
        触发器 3: EIS-Arrhenius 对齐 + 相变
        
        如果存在高度对齐的证据，生成关于相变机制的 Question
        
        Args:
            evidence_list: 证据列表
            patterns: 证据模式
            
        Returns:
            List[EvidenceUnit]: 生成的 Question 证据
        """
        questions = []
        
        # 检查 EIS-Arrhenius 对齐标签
        alignment_tags = [
            'eis_arrhenius_alignment', 'structural_reorganization',
            'high_precision_alignment', 'first_order_transition'
        ]
        has_alignment = any(tag in patterns['all_tags'] for tag in alignment_tags)
        
        # 检查相变标签
        phase_tags = ['phase_transition', 'glass_transition', 'dynamic_freezing']
        has_phase_transition = any(tag in patterns['all_tags'] for tag in phase_tags)
        
        if has_alignment and has_phase_transition:
            # 提取对齐证据
            alignment_evidences = []
            for tag in alignment_tags:
                alignment_evidences.extend(patterns['evidences_by_tag'].get(tag, []))
            
            # 提取温度信息
            transition_temps = []
            delta_T_values = []
            
            for e in alignment_evidences:
                if 'transition_temperature_K' in e.support_metrics:
                    transition_temps.append(e.support_metrics['transition_temperature_K'])
                elif 'T_arc_K' in e.support_metrics and 'T_break_K' in e.support_metrics:
                    T_avg = (e.support_metrics['T_arc_K'] + e.support_metrics['T_break_K']) / 2
                    transition_temps.append(T_avg)
                
                if 'delta_T_K' in e.support_metrics:
                    delta_T_values.append(e.support_metrics['delta_T_K'])
            
            # 判断是否为高精度对齐
            high_precision = any(dt < 5.0 for dt in delta_T_values) if delta_T_values else False
            
            if high_precision and transition_temps:
                T_transition = transition_temps[0]
                
                statement = (
                    f"EIS 形貌特征与 Arrhenius 折点在 T ≈ {T_transition:.1f} K 处的高精度对齐，"
                    f"强烈暗示该温度点发生了结构相变。"
                    f"这是一级相变（伴随潜热和体积变化）还是二级相变（连续的对称性破缺）？"
                    f"相变的序参量是什么——是离子配位数、氢键网络连通性，还是自由体积分数？"
                )
                
                questions.append(EvidenceUnit(
                    claim_level=ClaimLevel.question,
                    theme=EvidenceTheme.phase_transition,
                    statement=statement,
                    support_metrics={
                        'transition_temperature_K': float(T_transition),
                        'delta_T_min': float(min(delta_T_values)) if delta_T_values else None,
                        'synthesis_trigger': 'phase_transition_mechanism',
                        'n_alignment_evidences': len(alignment_evidences)
                    },
                    confidence=0.80,
                    confidence_basis={
                        'rule_id': 'synthesis_phase_alignment',
                        'formula': 'fixed 0.80 when EIS/Arrhenius alignment tags and phase tags co-occur',
                        'inputs': {
                            'transition_temperature_K': float(T_transition),
                            'delta_T_min': float(min(delta_T_values)) if delta_T_values else None
                        },
                        'interpretation': 'EIS-Arrhenius 对齐触发的机理问题，不是相变证明'
                    },
                    tags=['mechanistic_question', 'phase_transition', 'order_parameter']
                ))
        
        return questions
    
    def _trigger_evidence_convergence(
        self,
        evidence_list: List[EvidenceUnit],
        patterns: Dict[str, Any]
    ) -> List[EvidenceUnit]:
        """
        触发器 4: 多重证据收敛
        
        如果多个不同主题的证据指向同一物理图景，生成综合性 Question
        
        Args:
            evidence_list: 证据列表
            patterns: 证据模式
            
        Returns:
            List[EvidenceUnit]: 生成的 Question 证据
        """
        questions = []
        
        # 检查是否有多个主题都有高置信度证据
        high_confidence_by_theme = defaultdict(int)
        
        for evidence in evidence_list:
            if evidence.confidence >= 0.85:
                high_confidence_by_theme[evidence.theme] += 1
        
        # 如果至少有 2 个主题都有高置信度证据
        if len(high_confidence_by_theme) >= 2:
            themes_involved = list(high_confidence_by_theme.keys())
            
            # 检查是否涉及所有三个主题
            if len(themes_involved) == 3:
                statement = (
                    "传输动力学、组分敏感性和相变特征三个维度的证据相互印证，"
                    "共同指向 S8 体系中存在复杂的多尺度耦合机制。"
                    "如何构建一个统一的理论框架来描述这些现象之间的内在联系？"
                    "是否可以用单一的序参量（如自由体积或氢键网络连通性）来统一解释？"
                )
                
                questions.append(EvidenceUnit(
                    claim_level=ClaimLevel.question,
                    theme=EvidenceTheme.transport_dynamics,  # 使用主要主题
                    statement=statement,
                    support_metrics={
                        'themes_involved': [t.value for t in themes_involved],
                        'high_confidence_counts': {
                            t.value: int(count) for t, count in high_confidence_by_theme.items()
                        },
                        'synthesis_trigger': 'evidence_convergence',
                        'total_evidences': len(evidence_list)
                    },
                    confidence=0.70,
                    confidence_basis={
                        'rule_id': 'synthesis_multitheme_convergence',
                        'formula': 'fixed 0.70 when all three evidence themes contain high-confidence evidence',
                        'inputs': {
                            'themes_involved': [t.value for t in themes_involved],
                            'total_evidences': len(evidence_list)
                        },
                        'interpretation': '多主题证据收敛问题，用于 Stage3 构建统一解释框架'
                    },
                    tags=['mechanistic_question', 'multiscale_coupling', 'unified_framework']
                ))
        
        return questions

    def _trigger_profile_based_questions(
        self,
        profile: Optional[Dict[str, Any]],
        patterns: Dict[str, Any]
    ) -> List[EvidenceUnit]:
        """根据数据画像补充 S8 冷端传输相关机理问题。"""
        questions = []
        if not profile:
            return questions

        temp_cov = profile.get('temperature_coverage', {})
        features = profile.get('feature_completeness', {})
        scale = profile.get('data_scale', {})

        has_low = temp_cov.get('has_low_T', False)
        has_high = temp_cov.get('has_high_T', False)
        has_eis = features.get('has_eis_features', False)
        has_composition = features.get('has_composition', False)

        if has_low and has_high and has_composition:
            statement = (
                "S8 数据覆盖从冷端到室温的宽温区，且同时包含 R/N 组分维度。"
                "低温区活化能抬升是否主要来自酸-水相冻结、限域水氢键网络断裂，"
                "还是来自黏土界面连通性下降？"
            )
            questions.append(EvidenceUnit(
                claim_level=ClaimLevel.question,
                theme=EvidenceTheme.transport_dynamics,
                statement=statement,
                support_metrics={
                    'synthesis_trigger': 'profile_cold_window_transport',
                    'T_min': temp_cov.get('T_min'),
                    'T_max': temp_cov.get('T_max'),
                    'T_range': temp_cov.get('T_range'),
                    'R_unique_count': scale.get('R_unique_count'),
                    'N_unique_count': scale.get('N_unique_count')
                },
                confidence=0.68,
                confidence_basis={
                    'rule_id': 'profile_cold_window_transport',
                    'formula': 'fixed 0.68 when wide cold-to-room temperature coverage and composition axes exist',
                    'inputs': {
                        'has_low_T': has_low,
                        'has_high_T': has_high,
                        'has_composition': has_composition
                    },
                    'interpretation': '由数据画像触发的低温传输问题'
                },
                tags=['mechanistic_question', 'cold_window_transport', 'hydrogen_bond_network']
            ))

        if has_eis and 'critical_breakpoint' in patterns.get('all_tags', set()):
            statement = (
                "S8 数据同时包含 EIS 形貌特征和组分临界点线索。"
                "EIS 形貌变化是否与 R/N 阈值附近的传输通道重排同步，"
                "还是仅反映界面极化或测量窗口效应？"
            )
            questions.append(EvidenceUnit(
                claim_level=ClaimLevel.question,
                theme=EvidenceTheme.phase_transition,
                statement=statement,
                support_metrics={
                    'synthesis_trigger': 'profile_eis_composition_threshold',
                    'n_eis_features': features.get('n_eis_features'),
                    'critical_breakpoint_count': patterns.get('tag_counts', {}).get('critical_breakpoint', 0)
                },
                confidence=0.66,
                confidence_basis={
                    'rule_id': 'profile_eis_composition_threshold',
                    'formula': 'fixed 0.66 when EIS features and critical_breakpoint tags co-occur',
                    'inputs': {
                        'has_eis_features': has_eis,
                        'critical_breakpoint_count': patterns.get('tag_counts', {}).get('critical_breakpoint', 0)
                    },
                    'interpretation': 'EIS/组分阈值耦合问题，保持启发式边界'
                },
                tags=['mechanistic_question', 'eis_composition_coupling', 'phase_transition']
            ))

        if has_eis and has_low and has_high:
            statement = (
                "S8 数据包含宽温区 EIS 形貌特征。T_arc 与 T_break 的关系是否能够区分"
                "体相传输受阻、界面极化增强和氢键网络重排这三类解释？"
            )
            questions.append(EvidenceUnit(
                claim_level=ClaimLevel.question,
                theme=EvidenceTheme.phase_transition,
                statement=statement,
                support_metrics={
                    'synthesis_trigger': 'profile_eis_breakpoint_disambiguation',
                    'n_eis_features': features.get('n_eis_features'),
                    'T_min': temp_cov.get('T_min'),
                    'T_max': temp_cov.get('T_max')
                },
                confidence=0.65,
                confidence_basis={
                    'rule_id': 'profile_eis_breakpoint_disambiguation',
                    'formula': 'fixed 0.65 when EIS features and wide temperature coverage exist',
                    'inputs': {
                        'has_eis_features': has_eis,
                        'has_low_T': has_low,
                        'has_high_T': has_high
                    },
                    'interpretation': 'EIS 形貌与热激活折点关系的开放问题'
                },
                tags=['mechanistic_question', 'eis_arrhenius_disambiguation', 'phase_transition']
            ))

        if 'model_comparison' in patterns.get('all_tags', set()) or 'arrhenius_vs_vtf' in patterns.get('all_tags', set()):
            statement = (
                "Arrhenius 与 VTF 的信息准则比较给出了动力学模型偏好。该偏好在不同 R/N 子区间"
                "是否稳定，还是由少数组分区域或低温数据点主导？"
            )
            questions.append(EvidenceUnit(
                claim_level=ClaimLevel.question,
                theme=EvidenceTheme.transport_dynamics,
                statement=statement,
                support_metrics={
                    'synthesis_trigger': 'profile_model_preference_stability',
                    'has_model_comparison': True
                },
                confidence=0.64,
                confidence_basis={
                    'rule_id': 'profile_model_preference_stability',
                    'formula': 'fixed 0.64 when model_comparison evidence exists',
                    'inputs': {
                        'model_comparison_count': patterns.get('tag_counts', {}).get('model_comparison', 0),
                        'arrhenius_vs_vtf_count': patterns.get('tag_counts', {}).get('arrhenius_vs_vtf', 0)
                    },
                    'interpretation': '模型偏好稳定性问题，用于后续分区/敏感性分析'
                },
                tags=['mechanistic_question', 'model_preference_stability', 'arrhenius_vs_vtf']
            ))

        return questions
    
    def __repr__(self) -> str:
        return f"EvidenceSynthesizer(name='{self.name}', cross_synthesis={self.enable_cross_synthesis})"
