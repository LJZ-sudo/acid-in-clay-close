"""
Morphology Expert - EIS 形貌特征专家
解析 EIS 图谱特征并与热力学断点对齐
"""

from typing import List, Dict, Any, Optional, Tuple
import pandas as pd
import numpy as np
from scipy import stats
from scipy.signal import find_peaks

try:
    from ..core.base_specialist import BaseSpecialist
    from ..core.schema import EvidenceUnit, ClaimLevel, EvidenceTheme
except ImportError:
    from core.base_specialist import BaseSpecialist
    from core.schema import EvidenceUnit, ClaimLevel, EvidenceTheme


class MorphologyExpert(BaseSpecialist):
    """
    EIS 形貌特征分析专家
    
    核心任务：
    1. 提取 EIS 圆弧特征温度 (T_arc)
    2. 提取 Arrhenius 折点温度 (T_break)
    3. 对齐分析：ΔT = |T_arc - T_break|
    """
    
    def __init__(
        self,
        name: str = "MorphologyExpert",
        alignment_threshold: float = 10.0,  # 温度对齐阈值（K）
        min_points_break: int = 5,  # 检测折点的最小点数
        break_detection_method: str = "derivative"  # 折点检测方法
    ):
        """
        初始化形貌专家
        
        Args:
            name: 专家名称
            alignment_threshold: 温度对齐阈值（K）
            min_points_break: 检测折点的最小点数
            break_detection_method: 折点检测方法（derivative 或 piecewise）
        """
        super().__init__(name)
        self.alignment_threshold = alignment_threshold
        self.min_points_break = min_points_break
        self.break_detection_method = break_detection_method
    
    def analyze(
        self,
        data: pd.DataFrame,
        profile: Optional[Dict[str, Any]] = None
    ) -> List[EvidenceUnit]:
        """
        分析 EIS 形貌特征与热力学断点的对齐
        
        Args:
            data: 输入数据，需包含 T, EIS 特征, Ea 等列
            profile: 数据画像（可选）
            
        Returns:
            List[EvidenceUnit]: 证据单元列表
        """
        evidences = []
        
        # 任务 1: 提取 EIS 圆弧特征温度
        T_arc_results = self._extract_arc_temperature(data)
        
        # 任务 2: 提取 Arrhenius 折点温度
        T_break_results = self._extract_break_temperature(data)
        
        # 任务 3: 对齐分析
        if T_arc_results and T_break_results:
            alignment_evidences = self._analyze_alignment(
                T_arc_results, T_break_results
            )
            evidences.extend(alignment_evidences)
        
        # 额外分析：EIS 形貌演化特征
        morphology_evidences = self._analyze_morphology_evolution(data)
        evidences.extend(morphology_evidences)
        
        return evidences
    
    def _extract_arc_temperature(
        self,
        data: pd.DataFrame
    ) -> Optional[Dict[str, Any]]:
        """
        提取 EIS 圆弧特征温度 (T_arc)
        
        扫描数据中关于 EIS 形状的描述：
        - 圆弧可见度
        - 特征频率
        - 半圆直径
        
        Args:
            data: 输入数据
            
        Returns:
            Dict: 圆弧特征温度信息
        """
        # 检查可能的 EIS 特征列
        eis_columns = [
            'arc_visible', 'semicircle_visible', 'arc_diameter',
            'characteristic_frequency', 'peak_frequency',
            'nyquist_arc', 'eis_shape', 'impedance_arc',
            'arc_diameter_ohm', 'semicircle_quality',
            'peak_neg_zimag_ohm', 'nyquist_peak_ratio',
            'R_high_freq_ohm', 'R_low_freq_ohm', 'R_ratio'
        ]
        
        available_eis_cols = [col for col in eis_columns if col in data.columns]
        
        if not available_eis_cols:
            # 如果没有显式的 EIS 列，尝试从其他特征推断
            return self._infer_arc_temperature_from_impedance(data)
        
        # 如果有 arc_visible 或类似的布尔列
        for col in ['arc_visible', 'semicircle_visible', 'nyquist_arc']:
            if col in data.columns:
                return self._extract_arc_from_boolean(data, col)
        
        # 如果有特征频率列
        for col in ['characteristic_frequency', 'peak_frequency', 'peak_neg_zimag_ohm']:
            if col in data.columns:
                return self._extract_arc_from_frequency(data, col)
        
        return None
    
    def _extract_arc_from_boolean(
        self,
        data: pd.DataFrame,
        col: str
    ) -> Optional[Dict[str, Any]]:
        """从布尔型圆弧可见度列提取特征温度"""
        df = data.dropna(subset=[col, 'T']).copy()
        
        if len(df) == 0:
            return None
        
        # 按温度排序
        df = df.sort_values('T')
        
        # 找到圆弧首次出现的温度
        arc_visible = df[col].astype(bool)
        
        if arc_visible.any():
            # 找到第一个 True 的位置
            first_arc_idx = arc_visible.idxmax() if arc_visible.any() else None
            
            if first_arc_idx is not None:
                T_arc = df.loc[first_arc_idx, 'T']
                
                # 统计圆弧可见的温度范围
                arc_temps = df[arc_visible]['T'].values
                
                return {
                    'T_arc': float(T_arc),
                    'T_arc_min': float(arc_temps.min()),
                    'T_arc_max': float(arc_temps.max()),
                    'n_arc_visible': int(arc_visible.sum()),
                    'detection_method': 'boolean_flag',
                    'column_used': col
                }
        
        return None
    
    def _extract_arc_from_frequency(
        self,
        data: pd.DataFrame,
        col: str
    ) -> Optional[Dict[str, Any]]:
        """从特征频率列提取圆弧温度"""
        df = data.dropna(subset=[col, 'T']).copy()
        
        if len(df) < 3:
            return None
        
        df = df.sort_values('T')
        
        # 特征频率的突变可能对应圆弧的出现
        freq = df[col].values
        T = df['T'].values
        
        # 计算频率的变化率
        d_freq = np.diff(freq)
        d_T = np.diff(T)
        
        # 避免除零
        mask = d_T != 0
        if not np.any(mask):
            return None
        
        freq_rate = np.abs(d_freq[mask] / d_T[mask])
        
        # 找到变化率最大的点
        if len(freq_rate) > 0:
            max_rate_idx = np.argmax(freq_rate)
            original_idx = np.where(mask)[0][max_rate_idx]
            
            T_arc = T[original_idx]
            
            return {
                'T_arc': float(T_arc),
                'characteristic_frequency': float(freq[original_idx]),
                'detection_method': 'frequency_jump',
                'column_used': col
            }
        
        return None
    
    def _infer_arc_temperature_from_impedance(
        self,
        data: pd.DataFrame
    ) -> Optional[Dict[str, Any]]:
        """
        从阻抗数据推断圆弧特征温度
        
        如果有 Rb (体电阻) 或 conductivity 数据，
        可以从其温度依赖性推断 EIS 形貌变化
        """
        # 检查是否有电导率或阻抗数据
        impedance_cols = [
            'Rb', 'rb_ohm', 'R_bulk', 'resistance',
            'R_high_freq_ohm', 'R_low_freq_ohm',
            'conductivity', 'sigma'
        ]
        available_cols = [col for col in impedance_cols if col in data.columns]
        
        if not available_cols or 'T' not in data.columns:
            return None
        
        col = available_cols[0]
        df = data.dropna(subset=[col, 'T']).copy()
        
        if len(df) < 5:
            return None
        
        df = self._aggregate_by_temperature(df, col)
        if len(df) < 5:
            return None

        T = df['T'].values
        values = df[col].values
        
        # 对于电导率，取对数
        if col in ['conductivity', 'sigma']:
            values = np.log(values)
        
        # 检测二阶导数的峰值（可能对应形貌变化）
        if len(T) >= 5:
            d2_values = np.gradient(np.gradient(values, T), T)
            
            # 找到二阶导数的峰值
            peaks, properties = find_peaks(np.abs(d2_values), prominence=np.std(d2_values))
            
            if len(peaks) > 0:
                # 取最显著的峰
                T_arc = T[peaks[0]]
                
                return {
                    'T_arc': float(T_arc),
                    'detection_method': 'impedance_curvature',
                    'column_used': col,
                    'inferred': True
                }
        
        return None
    
    def _extract_break_temperature(
        self,
        data: pd.DataFrame
    ) -> Optional[Dict[str, Any]]:
        """
        提取 Arrhenius 折点温度 (T_break)
        
        分析 ln(sigma) vs 1/T 或 Ea vs T 的折点
        
        Args:
            data: 输入数据
            
        Returns:
            Dict: 折点温度信息
        """
        # 方法 1: 从 Ea vs T 检测折点
        if 'Ea' in data.columns and 'T' in data.columns:
            result = self._detect_break_from_ea(data)
            if result:
                return result
        
        # 方法 2: 从 ln(sigma) vs 1/T 检测折点
        if 'sigma' in data.columns and 'T' in data.columns:
            result = self._detect_break_from_arrhenius(data)
            if result:
                return result
        
        # 方法 3: 从显式的折点标记
        if 'T_break' in data.columns or 'break_temperature' in data.columns:
            col = 'T_break' if 'T_break' in data.columns else 'break_temperature'
            T_break = data[col].dropna().values
            if len(T_break) > 0:
                return {
                    'T_break': float(np.mean(T_break)),
                    'T_break_std': float(np.std(T_break)) if len(T_break) > 1 else 0.0,
                    'detection_method': 'explicit_column',
                    'n_points': len(T_break)
                }
        
        return None
    
    def _detect_break_from_ea(
        self,
        data: pd.DataFrame
    ) -> Optional[Dict[str, Any]]:
        """从 Ea vs T 检测折点"""
        df = data.dropna(subset=['Ea', 'T']).copy()
        
        if len(df) < self.min_points_break:
            return None
        
        df = self._aggregate_by_temperature(df, 'Ea')
        if len(df) < self.min_points_break:
            return None

        T = df['T'].values
        Ea = df['Ea'].values
        
        if self.break_detection_method == "derivative":
            # 方法 1: 基于导数的折点检测
            if len(T) >= 5:
                # 计算 Ea 对 T 的导数
                dEa_dT = np.gradient(Ea, T)
                
                # 计算二阶导数
                d2Ea_dT2 = np.gradient(dEa_dT, T)
                
                # 找到二阶导数的峰值
                peaks, properties = find_peaks(
                    np.abs(d2Ea_dT2),
                    prominence=np.std(d2Ea_dT2)
                )
                
                if len(peaks) > 0:
                    # 取最显著的峰
                    break_idx = peaks[0]
                    T_break = T[break_idx]
                    
                    return {
                        'T_break': float(T_break),
                        'Ea_at_break': float(Ea[break_idx]),
                        'detection_method': 'derivative_peak',
                        'n_points': len(T)
                    }
        
        elif self.break_detection_method == "piecewise":
            # 方法 2: 分段线性拟合
            return self._detect_break_piecewise(T, Ea)
        
        return None
    
    def _detect_break_piecewise(
        self,
        T: np.ndarray,
        Ea: np.ndarray
    ) -> Optional[Dict[str, Any]]:
        """使用分段线性拟合检测折点"""
        if len(T) < self.min_points_break:
            return None
        
        best_break_idx = None
        best_improvement = 0
        
        # 尝试不同的折点位置
        for i in range(2, len(T) - 2):
            # 分段拟合
            T1, Ea1 = T[:i], Ea[:i]
            T2, Ea2 = T[i:], Ea[i:]
            
            if len(T1) < 2 or len(T2) < 2:
                continue
            
            # 拟合两段
            try:
                lr1 = stats.linregress(T1, Ea1)
                lr2 = stats.linregress(T2, Ea2)
                
                # 计算分段拟合的残差
                pred1 = lr1.slope * T1 + lr1.intercept
                pred2 = lr2.slope * T2 + lr2.intercept
                rss_piecewise = np.sum((Ea1 - pred1)**2) + np.sum((Ea2 - pred2)**2)
                
                # 计算整体线性拟合的残差
                lr_full = stats.linregress(T, Ea)
                pred_full = lr_full.slope * T + lr_full.intercept
                rss_full = np.sum((Ea - pred_full)**2)
                
                # 计算改进程度
                improvement = (rss_full - rss_piecewise) / rss_full
                
                if improvement > best_improvement:
                    best_improvement = improvement
                    best_break_idx = i
            
            except Exception:
                continue
        
        if best_break_idx is not None and best_improvement > 0.1:
            T_break = T[best_break_idx]
            
            return {
                'T_break': float(T_break),
                'Ea_at_break': float(Ea[best_break_idx]),
                'detection_method': 'piecewise_linear',
                'improvement': float(best_improvement),
                'n_points': len(T)
            }
        
        return None
    
    def _detect_break_from_arrhenius(
        self,
        data: pd.DataFrame
    ) -> Optional[Dict[str, Any]]:
        """从 Arrhenius 图 (ln(sigma) vs 1/T) 检测折点"""
        df = data.dropna(subset=['sigma', 'T']).copy()
        df = df[df['sigma'] > 0]
        df = df[df['T'] > 0]
        
        if len(df) < self.min_points_break:
            return None
        
        df = self._aggregate_by_temperature(df, 'sigma')
        if len(df) < self.min_points_break:
            return None

        T = df['T'].values
        ln_sigma = np.log(df['sigma'].values)
        inv_T = 1.0 / T
        
        # 使用分段线性拟合检测折点
        return self._detect_break_piecewise_arrhenius(T, inv_T, ln_sigma)
    
    def _detect_break_piecewise_arrhenius(
        self,
        T: np.ndarray,
        inv_T: np.ndarray,
        ln_sigma: np.ndarray
    ) -> Optional[Dict[str, Any]]:
        """在 Arrhenius 图上检测折点"""
        if len(T) < self.min_points_break:
            return None
        
        best_break_idx = None
        best_improvement = 0
        
        for i in range(2, len(T) - 2):
            inv_T1, ln_sigma1 = inv_T[:i], ln_sigma[:i]
            inv_T2, ln_sigma2 = inv_T[i:], ln_sigma[i:]
            
            if len(inv_T1) < 2 or len(inv_T2) < 2:
                continue
            
            try:
                lr1 = stats.linregress(inv_T1, ln_sigma1)
                lr2 = stats.linregress(inv_T2, ln_sigma2)
                
                pred1 = lr1.slope * inv_T1 + lr1.intercept
                pred2 = lr2.slope * inv_T2 + lr2.intercept
                rss_piecewise = np.sum((ln_sigma1 - pred1)**2) + np.sum((ln_sigma2 - pred2)**2)
                
                lr_full = stats.linregress(inv_T, ln_sigma)
                pred_full = lr_full.slope * inv_T + lr_full.intercept
                rss_full = np.sum((ln_sigma - pred_full)**2)
                
                improvement = (rss_full - rss_piecewise) / rss_full
                
                if improvement > best_improvement:
                    best_improvement = improvement
                    best_break_idx = i
            
            except Exception:
                continue
        
        if best_break_idx is not None and best_improvement > 0.1:
            T_break = T[best_break_idx]
            
            return {
                'T_break': float(T_break),
                'detection_method': 'arrhenius_piecewise',
                'improvement': float(best_improvement),
                'n_points': len(T)
            }
        
        return None

    def _aggregate_by_temperature(self, data: pd.DataFrame, value_col: str) -> pd.DataFrame:
        """
        按温度聚合，避免重复温度点导致 np.gradient 除零。

        S8 数据包含多个样品在同一温度下的记录，形貌层只需要温度趋势线索，
        因此这里使用同一温度下的均值作为启发式摘要。
        """
        if 'T' not in data.columns or value_col not in data.columns:
            return data

        aggregated = (
            data[['T', value_col]]
            .dropna()
            .groupby('T', as_index=False)[value_col]
            .mean()
            .sort_values('T')
        )
        return aggregated
    
    def _analyze_alignment(
        self,
        T_arc_results: Dict[str, Any],
        T_break_results: Dict[str, Any]
    ) -> List[EvidenceUnit]:
        """
        分析 T_arc 和 T_break 的对齐程度
        
        Args:
            T_arc_results: 圆弧特征温度结果
            T_break_results: 折点温度结果
            
        Returns:
            List[EvidenceUnit]: 证据列表
        """
        evidences = []
        
        T_arc = T_arc_results['T_arc']
        T_break = T_break_results['T_break']
        
        # 计算温度差异
        delta_T = abs(T_arc - T_break)
        
        # 判断是否高度对齐
        is_aligned = delta_T < self.alignment_threshold
        
        if is_aligned:
            # 生成高置信度证据
            statement = (
                f"EIS 中圆弧的涌现温度 (T_arc = {T_arc:.1f} K) 与 Arrhenius 折点温度 "
                f"(T_break = {T_break:.1f} K) 在温度上高度同步，偏差仅为 {delta_T:.1f} K (< {self.alignment_threshold} K)。"
                f"这提示电学活化能改变可能与微观结构重组或相变相关，"
                f"EIS 形貌特征与热激活折点存在值得后续验证的关联。"
            )
            
            # 置信度基于对齐程度
            confidence = min(0.95, 1.0 - delta_T / self.alignment_threshold * 0.2)
            
            evidences.append(EvidenceUnit(
                claim_level=ClaimLevel.interpretation,
                theme=EvidenceTheme.phase_transition,
                statement=statement,
                support_metrics={
                    'T_arc_K': float(T_arc),
                    'T_break_K': float(T_break),
                    'delta_T_K': float(delta_T),
                    'alignment_threshold_K': self.alignment_threshold,
                    'is_aligned': True,
                    'arc_detection_method': T_arc_results.get('detection_method'),
                    'break_detection_method': T_break_results.get('detection_method')
                },
                confidence=confidence,
                confidence_basis={
                    'rule_id': 'eis_arrhenius_alignment_delta_t',
                    'formula': 'min(0.95, 1.0 - delta_T / alignment_threshold * 0.2)',
                    'inputs': {'delta_T_K': float(delta_T), 'alignment_threshold_K': self.alignment_threshold},
                    'interpretation': 'EIS/Arrhenius 温度对齐线索；不是等效电路或相变证明'
                },
                tags=["phase_transition", "eis_arrhenius_alignment", "structural_reorganization"]
            ))
            
            # 如果对齐非常精确（< 5K），生成额外的强化证据
            if delta_T < 5.0:
                additional_statement = (
                    f"极高的温度对齐精度 (ΔT = {delta_T:.1f} K < 5 K) 表明 EIS 形貌变化"
                    f"与活化能跃迁可能受同一温区内的结构或动力学变化影响，"
                    f"提示 T ≈ {(T_arc + T_break)/2:.1f} K 附近存在需要独立验证的相变/重排线索。"
                )
                
                evidences.append(EvidenceUnit(
                    claim_level=ClaimLevel.interpretation,
                    theme=EvidenceTheme.phase_transition,
                    statement=additional_statement,
                    support_metrics={
                        'delta_T_K': float(delta_T),
                        'transition_temperature_K': float((T_arc + T_break) / 2)
                    },
                    confidence=0.90,
                    confidence_basis={
                        'rule_id': 'high_precision_eis_alignment',
                        'formula': 'fixed 0.90 when delta_T < 5 K',
                        'inputs': {'delta_T_K': float(delta_T)},
                        'interpretation': '高精度对齐线索；保持启发式解释边界'
                    },
                    tags=["phase_transition", "high_precision_alignment", "first_order_transition"]
                ))
        
        else:
            # 不对齐的情况，生成观测层级证据
            statement = (
                f"EIS 圆弧涌现温度 (T_arc = {T_arc:.1f} K) 与 Arrhenius 折点温度 "
                f"(T_break = {T_break:.1f} K) 存在 {delta_T:.1f} K 的偏差，"
                f"超过对齐阈值 ({self.alignment_threshold} K)。"
                f"这可能表明 EIS 形貌变化与活化能跃迁由不同的物理机制驱动，"
                f"或者存在多个相互竞争的弛豫过程。"
            )
            
            evidences.append(EvidenceUnit(
                claim_level=ClaimLevel.observation,
                theme=EvidenceTheme.phase_transition,
                statement=statement,
                support_metrics={
                    'T_arc_K': float(T_arc),
                    'T_break_K': float(T_break),
                    'delta_T_K': float(delta_T),
                    'is_aligned': False
                },
                confidence=0.75,
                confidence_basis={
                    'rule_id': 'eis_arrhenius_misalignment',
                    'formula': 'fixed 0.75 when delta_T exceeds alignment threshold',
                    'inputs': {'delta_T_K': float(delta_T), 'alignment_threshold_K': self.alignment_threshold},
                    'interpretation': 'EIS/Arrhenius 失配观测，提示多过程或测量窗口效应'
                },
                tags=["phase_transition", "misalignment", "multiple_processes"]
            ))
        
        return evidences
    
    def _analyze_morphology_evolution(
        self,
        data: pd.DataFrame
    ) -> List[EvidenceUnit]:
        """
        分析 EIS 形貌的演化特征
        
        Args:
            data: 输入数据
            
        Returns:
            List[EvidenceUnit]: 证据列表
        """
        evidences = []
        
        # 检查是否有足够的 EIS 相关数据
        eis_indicators = [
            'arc_visible', 'semicircle_visible', 'characteristic_frequency',
            'peak_frequency', 'arc_diameter', 'impedance_arc',
            'arc_diameter_ohm', 'semicircle_quality',
            'peak_neg_zimag_ohm', 'nyquist_peak_ratio'
        ]
        
        available = [col for col in eis_indicators if col in data.columns]
        
        if not available:
            return evidences
        
        # 分析 EIS 特征随温度的演化
        if 'T' in data.columns:
            for col in available:
                df = data.dropna(subset=[col, 'T']).copy()
                
                if len(df) >= 5:
                    df = df.sort_values('T')
                    T = df['T'].values
                    values = df[col].values
                    
                    # 如果是布尔型，统计出现频率
                    if df[col].dtype == bool:
                        appearance_rate = values.sum() / len(values)
                        
                        if appearance_rate > 0.5:
                            statement = (
                                f"EIS 形貌特征 ({col}) 在测量温度范围内频繁出现 "
                                f"(出现率 {appearance_rate*100:.1f}%)，"
                                f"表明体系在该温度区间内具有明显的界面或晶界弛豫过程。"
                            )
                            
                            evidences.append(EvidenceUnit(
                                claim_level=ClaimLevel.observation,
                                theme=EvidenceTheme.phase_transition,
                                statement=statement,
                                support_metrics={
                                    'feature': col,
                                    'appearance_rate': float(appearance_rate),
                                    'T_min': float(T.min()),
                                    'T_max': float(T.max())
                                },
                                confidence=0.80,
                                confidence_basis={
                                    'rule_id': 'eis_feature_appearance_rate',
                                    'formula': 'fixed 0.80 when boolean EIS feature appears in >50% rows',
                                    'inputs': {'feature': col, 'appearance_rate': float(appearance_rate)},
                                    'interpretation': 'EIS 形貌出现频率观测；不等同于等效电路判定'
                                },
                                tags=["eis_morphology", "interface_relaxation"]
                            ))
        
        return evidences
