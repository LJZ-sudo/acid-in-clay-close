"""
Trend Analyzer - 组分敏感性专家
分析 S8 材料组分（R 和 N）对活化能（Ea）的影响
"""

from typing import List, Dict, Any, Optional, Tuple
import pandas as pd
import numpy as np
from scipy import stats
from scipy.signal import find_peaks
from scipy.interpolate import interp1d

try:
    from ..core.base_specialist import BaseSpecialist
    from ..core.schema import EvidenceUnit, ClaimLevel, EvidenceTheme
except ImportError:
    from core.base_specialist import BaseSpecialist
    from core.schema import EvidenceUnit, ClaimLevel, EvidenceTheme


class TrendAnalyzer(BaseSpecialist):
    """
    组分敏感性分析专家
    分析活化能 Ea 随组分 R 和 N 的变化趋势，识别临界点和相变特征
    """
    
    def __init__(
        self,
        name: str = "TrendAnalyzer",
        jump_threshold: float = 0.15,  # Ea 跳变阈值（相对变化）
        min_samples: int = 3,  # 最小样本数
        r2_threshold: float = 0.85  # R² 阈值
    ):
        """
        初始化趋势分析器
        
        Args:
            name: 专家名称
            jump_threshold: Ea 跳变阈值（相对变化，默认 15%）
            min_samples: 最小样本数
            r2_threshold: R² 阈值
        """
        super().__init__(name)
        self.jump_threshold = jump_threshold
        self.min_samples = min_samples
        self.r2_threshold = r2_threshold
    
    def analyze(
        self,
        data: pd.DataFrame,
        profile: Optional[Dict[str, Any]] = None
    ) -> List[EvidenceUnit]:
        """
        分析组分对活化能的影响
        
        Args:
            data: 输入数据，需包含 R, N, Ea, T_mid, R2 等列
            profile: 数据画像（可选）
            
        Returns:
            List[EvidenceUnit]: 证据单元列表
        """
        evidences = []
        
        # 数据验证
        required_cols = ['R', 'Ea']
        missing_cols = [col for col in required_cols if col not in data.columns]
        if missing_cols:
            return evidences
        
        # 过滤高质量数据
        if 'R2' in data.columns:
            data = data[data['R2'] >= self.r2_threshold].copy()
        
        # 按温度区间分组分析
        if 'T_mid' in data.columns:
            # 定义温度区间
            temp_zones = self._define_temperature_zones(data)
            for zone_name, zone_data in temp_zones.items():
                if len(zone_data) >= self.min_samples:
                    evidences.extend(self._analyze_zone(zone_data, zone_name))
        else:
            # 没有温度信息，直接分析全部数据
            evidences.extend(self._analyze_zone(data, "all_T"))
        
        # 全局趋势分析（不分温度区间）
        evidences.extend(self._analyze_global_trends(data))
        
        return evidences
    
    def _define_temperature_zones(self, data: pd.DataFrame) -> Dict[str, pd.DataFrame]:
        """
        定义温度区间
        
        Args:
            data: 输入数据
            
        Returns:
            Dict[str, pd.DataFrame]: 温度区间字典
        """
        zones = {}
        
        if 'T_mid' not in data.columns:
            return {"all_T": data}
        
        # 定义温度区间（单位：K）
        data = data.copy()
        data['T_zone'] = pd.cut(
            data['T_mid'],
            bins=[0, 230, 270, 400],
            labels=['low_T', 'mid_T', 'high_T']
        )
        
        for zone_name in ['low_T', 'mid_T', 'high_T']:
            zone_data = data[data['T_zone'] == zone_name].copy()
            if len(zone_data) > 0:
                zones[zone_name] = zone_data
        
        return zones
    
    def _analyze_zone(
        self,
        data: pd.DataFrame,
        zone_name: str
    ) -> List[EvidenceUnit]:
        """
        分析单个温度区间的数据
        
        Args:
            data: 区间数据
            zone_name: 区间名称
            
        Returns:
            List[EvidenceUnit]: 证据列表
        """
        evidences = []
        
        # 分析 R 的影响
        if 'R' in data.columns and len(data['R'].unique()) >= self.min_samples:
            evidences.extend(self._analyze_composition_effect(
                data, 'R', zone_name
            ))
        
        # 分析 N 的影响
        if 'N' in data.columns and len(data['N'].unique()) >= self.min_samples:
            evidences.extend(self._analyze_composition_effect(
                data, 'N', zone_name
            ))
        
        return evidences
    
    def _analyze_composition_effect(
        self,
        data: pd.DataFrame,
        comp_var: str,
        zone_name: str
    ) -> List[EvidenceUnit]:
        """
        分析单个组分变量对 Ea 的影响
        
        Args:
            data: 输入数据
            comp_var: 组分变量名（'R' 或 'N'）
            zone_name: 温度区间名称
            
        Returns:
            List[EvidenceUnit]: 证据列表
        """
        evidences = []
        
        # 按组分排序并计算统计量
        df_sorted = data.sort_values(comp_var).copy()
        
        # 去除缺失值
        mask = ~(df_sorted[comp_var].isna() | df_sorted['Ea'].isna())
        df_sorted = df_sorted[mask]
        
        if len(df_sorted) < self.min_samples:
            return evidences
        
        comp_values = df_sorted[comp_var].values
        ea_values = df_sorted['Ea'].values
        
        # 1. 计算敏感度（一阶差分）
        sensitivity = self._calculate_sensitivity(comp_values, ea_values)
        
        # 2. 检测临界点（突变点）
        critical_points = self._detect_critical_points(
            comp_values, ea_values, comp_var
        )
        
        # 3. 非线性检验
        nonlinearity = self._test_nonlinearity(comp_values, ea_values)
        
        # 4. 生成证据
        
        # 证据 1: 敏感度分析
        if sensitivity['significant']:
            evidences.append(self._create_sensitivity_evidence(
                sensitivity, comp_var, zone_name
            ))
        
        # 证据 2: 临界点检测
        for cp in critical_points:
            evidences.append(self._create_critical_point_evidence(
                cp, comp_var, zone_name
            ))
        
        # 证据 3: 非线性特征
        if nonlinearity['is_nonlinear']:
            evidences.append(self._create_nonlinearity_evidence(
                nonlinearity, comp_var, zone_name
            ))
        
        return evidences
    
    def _calculate_sensitivity(
        self,
        comp_values: np.ndarray,
        ea_values: np.ndarray
    ) -> Dict[str, Any]:
        """
        计算敏感度 ∂Ea/∂R
        
        Args:
            comp_values: 组分值数组
            ea_values: Ea 值数组
            
        Returns:
            Dict: 敏感度统计信息
        """
        if len(comp_values) < 2:
            return {"significant": False}
        
        # 计算一阶差分
        d_comp = np.diff(comp_values)
        d_ea = np.diff(ea_values)
        
        # 避免除零
        mask = d_comp != 0
        if not np.any(mask):
            return {"significant": False}
        
        sensitivity = d_ea[mask] / d_comp[mask]
        
        # 统计量
        mean_sens = np.mean(sensitivity)
        std_sens = np.std(sensitivity)
        
        # 线性回归检验
        slope, intercept, r_value, p_value, std_err = stats.linregress(
            comp_values, ea_values
        )
        
        return {
            "significant": p_value < 0.05,
            "mean_sensitivity": float(mean_sens),
            "std_sensitivity": float(std_sens),
            "slope": float(slope),
            "r_squared": float(r_value**2),
            "p_value": float(p_value),
            "n_samples": len(comp_values)
        }
    
    def _detect_critical_points(
        self,
        comp_values: np.ndarray,
        ea_values: np.ndarray,
        comp_var: str
    ) -> List[Dict[str, Any]]:
        """
        检测临界点（Ea 突变点）
        
        Args:
            comp_values: 组分值数组
            ea_values: Ea 值数组
            comp_var: 组分变量名
            
        Returns:
            List[Dict]: 临界点列表
        """
        critical_points = []
        
        if len(comp_values) < 3:
            return critical_points
        
        # 方法 1: 基于一阶差分的突变检测
        d_comp = np.diff(comp_values)
        d_ea = np.diff(ea_values)
        
        # 避免除零
        mask = d_comp != 0
        if not np.any(mask):
            return critical_points
        
        # 计算相对变化率
        relative_change = np.abs(d_ea[mask] / ea_values[:-1][mask])
        
        # 找到超过阈值的点
        jump_indices = np.where(relative_change > self.jump_threshold)[0]
        
        for idx in jump_indices:
            # 找到原始索引
            original_idx = np.where(mask)[0][idx]
            
            if original_idx < len(comp_values) - 1:
                cp_value = comp_values[original_idx]
                ea_before = ea_values[original_idx]
                ea_after = ea_values[original_idx + 1]
                jump_magnitude = ea_after - ea_before
                relative_jump = jump_magnitude / ea_before
                
                critical_points.append({
                    "comp_value": float(cp_value),
                    "ea_before": float(ea_before),
                    "ea_after": float(ea_after),
                    "jump_magnitude": float(jump_magnitude),
                    "relative_jump": float(relative_jump),
                    "direction": "increase" if jump_magnitude > 0 else "decrease"
                })
        
        # 方法 2: 基于二阶导数的拐点检测（如果数据足够多）
        if len(comp_values) >= 5:
            try:
                # 使用插值平滑数据
                f = interp1d(comp_values, ea_values, kind='quadratic', fill_value='extrapolate')
                comp_fine = np.linspace(comp_values.min(), comp_values.max(), 100)
                ea_fine = f(comp_fine)
                
                # 计算二阶导数
                d2_ea = np.gradient(np.gradient(ea_fine, comp_fine), comp_fine)
                
                # 找到二阶导数的峰值
                peaks, properties = find_peaks(np.abs(d2_ea), prominence=np.std(d2_ea))
                
                for peak_idx in peaks:
                    cp_value = comp_fine[peak_idx]
                    # 确保不重复
                    if not any(abs(cp['comp_value'] - cp_value) < 0.05 for cp in critical_points):
                        # 找到最接近的原始数据点
                        closest_idx = np.argmin(np.abs(comp_values - cp_value))
                        if closest_idx < len(ea_values):
                            critical_points.append({
                                "comp_value": float(cp_value),
                                "ea_value": float(ea_values[closest_idx]),
                                "type": "inflection_point",
                                "curvature": float(d2_ea[peak_idx])
                            })
            except Exception:
                # 插值失败，跳过
                pass
        
        return critical_points
    
    def _test_nonlinearity(
        self,
        comp_values: np.ndarray,
        ea_values: np.ndarray
    ) -> Dict[str, Any]:
        """
        检验 Ea 随组分的非线性特征
        
        Args:
            comp_values: 组分值数组
            ea_values: Ea 值数组
            
        Returns:
            Dict: 非线性检验结果
        """
        if len(comp_values) < 4:
            return {"is_nonlinear": False}
        
        # 线性拟合
        linear_fit = np.polyfit(comp_values, ea_values, 1)
        linear_pred = np.polyval(linear_fit, comp_values)
        linear_residuals = ea_values - linear_pred
        linear_ss = np.sum(linear_residuals**2)
        
        # 二次拟合
        try:
            quad_fit = np.polyfit(comp_values, ea_values, 2)
            quad_pred = np.polyval(quad_fit, comp_values)
            quad_residuals = ea_values - quad_pred
            quad_ss = np.sum(quad_residuals**2)
            
            # F 检验
            n = len(comp_values)
            f_stat = ((linear_ss - quad_ss) / 1) / (quad_ss / (n - 3))
            p_value = 1 - stats.f.cdf(f_stat, 1, n - 3)
            
            return {
                "is_nonlinear": p_value < 0.05,
                "linear_r2": float(1 - linear_ss / np.sum((ea_values - np.mean(ea_values))**2)),
                "quadratic_r2": float(1 - quad_ss / np.sum((ea_values - np.mean(ea_values))**2)),
                "f_statistic": float(f_stat),
                "p_value": float(p_value),
                "quadratic_coeff": float(quad_fit[0])
            }
        except Exception:
            return {"is_nonlinear": False}
    
    def _create_sensitivity_evidence(
        self,
        sensitivity: Dict[str, Any],
        comp_var: str,
        zone_name: str
    ) -> EvidenceUnit:
        """创建敏感度证据"""
        direction = "增加" if sensitivity['slope'] > 0 else "减少"
        zone_desc = self._format_zone_name(zone_name)
        
        statement = (
            f"在{zone_desc}区间，活化能 Ea 随组分 {comp_var} 的变化呈现显著的{direction}趋势，"
            f"平均敏感度为 {sensitivity['mean_sensitivity']:.4f} eV/unit，"
            f"线性相关系数 R2 = {sensitivity['r_squared']:.3f}"
        )
        
        return EvidenceUnit(
            claim_level=ClaimLevel.observation,
            theme=EvidenceTheme.composition_sensitivity,
            statement=statement,
            support_metrics={
                "composition_variable": comp_var,
                "temperature_zone": zone_name,
                "mean_sensitivity": sensitivity['mean_sensitivity'],
                "slope": sensitivity['slope'],
                "r_squared": sensitivity['r_squared'],
                "p_value": sensitivity['p_value'],
                "n_samples": sensitivity['n_samples']
            },
            confidence=min(0.95, sensitivity['r_squared']),
            confidence_basis={
                "rule_id": "composition_sensitivity_r2_cap",
                "formula": "min(0.95, r_squared)",
                "inputs": {"r_squared": sensitivity['r_squared'], "p_value": sensitivity['p_value']},
                "interpretation": "基于线性趋势显著性和 R2 的启发式证据权重"
            },
            tags=["composition_sensitivity", f"{comp_var}_dependent", zone_name]
        )
    
    def _create_critical_point_evidence(
        self,
        cp: Dict[str, Any],
        comp_var: str,
        zone_name: str
    ) -> EvidenceUnit:
        """创建临界点证据"""
        zone_desc = self._format_zone_name(zone_name)
        
        if "jump_magnitude" in cp:
            # 突变点
            direction = "跃升" if cp['direction'] == "increase" else "突降"
            statement = (
                f"在{zone_desc}区间，活化能 Ea 在 {comp_var} = {cp['comp_value']:.2f} 附近"
                f"发生显著{direction}，从 {cp['ea_before']:.3f} eV {direction}至 {cp['ea_after']:.3f} eV，"
                f"相对变化达 {abs(cp['relative_jump'])*100:.1f}%。"
                f"这提示可能存在渗流类连通性转变，但仍需独立结构或重复实验验证。"
            )
            
            confidence = min(0.90, 0.7 + abs(cp['relative_jump']) * 0.5)
            tags = ["critical_breakpoint", "percolation_hint", f"{comp_var}_critical"]
        else:
            # 拐点
            statement = (
                f"在{zone_desc}区间，活化能 Ea 在 {comp_var} = {cp['comp_value']:.2f} 附近"
                f"出现拐点，Ea ≈ {cp['ea_value']:.3f} eV，"
                f"表明组分依赖关系发生转变。"
            )
            
            confidence = 0.75
            tags = ["inflection_point", f"{comp_var}_transition"]
        
        return EvidenceUnit(
            claim_level=ClaimLevel.interpretation,
            theme=EvidenceTheme.composition_sensitivity,
            statement=statement,
            support_metrics={
                "composition_variable": comp_var,
                "temperature_zone": zone_name,
                "critical_value": cp['comp_value'],
                "critical_value_unit": "composition",
                f"{comp_var}_critical": cp['comp_value'],
                **cp
            },
            confidence=confidence,
            confidence_basis={
                "rule_id": "critical_jump_or_inflection",
                "formula": "jump: min(0.90, 0.7 + abs(relative_jump) * 0.5); inflection: 0.75",
                "inputs": {
                    "relative_jump": cp.get('relative_jump'),
                    "critical_value": cp.get('comp_value'),
                    "composition_variable": comp_var
                },
                "interpretation": "组分阈值证据权重；渗流仅作为假说线索"
            },
            tags=tags
        )
    
    def _create_nonlinearity_evidence(
        self,
        nonlinearity: Dict[str, Any],
        comp_var: str,
        zone_name: str
    ) -> EvidenceUnit:
        """创建非线性特征证据"""
        zone_desc = self._format_zone_name(zone_name)
        
        curvature = "上凹" if nonlinearity['quadratic_coeff'] > 0 else "下凹"
        
        statement = (
            f"在{zone_desc}区间，活化能 Ea 随组分 {comp_var} 的变化呈现显著的非线性特征，"
            f"二次拟合优于线性拟合（R2 提升: {nonlinearity['linear_r2']:.3f} -> {nonlinearity['quadratic_r2']:.3f}），"
            f"曲线呈{curvature}形态，表明存在复杂的组分依赖机制。"
        )
        
        return EvidenceUnit(
            claim_level=ClaimLevel.interpretation,
            theme=EvidenceTheme.composition_sensitivity,
            statement=statement,
            support_metrics={
                "composition_variable": comp_var,
                "temperature_zone": zone_name,
                "linear_r2": nonlinearity['linear_r2'],
                "quadratic_r2": nonlinearity['quadratic_r2'],
                "f_statistic": nonlinearity['f_statistic'],
                "p_value": nonlinearity['p_value'],
                "quadratic_coeff": nonlinearity['quadratic_coeff']
            },
            confidence=min(0.85, nonlinearity['quadratic_r2']),
            confidence_basis={
                "rule_id": "quadratic_improvement_cap",
                "formula": "min(0.85, quadratic_r2)",
                "inputs": {
                    "linear_r2": nonlinearity['linear_r2'],
                    "quadratic_r2": nonlinearity['quadratic_r2'],
                    "p_value": nonlinearity['p_value']
                },
                "interpretation": "基于二次模型相对线性模型改进的启发式证据权重"
            },
            tags=["nonlinear_trend", f"{comp_var}_dependent", zone_name]
        )
    
    def _analyze_global_trends(self, data: pd.DataFrame) -> List[EvidenceUnit]:
        """
        分析全局趋势（不分温度区间）
        
        Args:
            data: 输入数据
            
        Returns:
            List[EvidenceUnit]: 证据列表
        """
        evidences = []
        
        # 检查是否有足够的 R 覆盖范围
        if 'R' in data.columns:
            r_range = data['R'].max() - data['R'].min()
            r_unique = len(data['R'].unique())
            
            if r_range > 0.3 and r_unique >= 5:
                # 分析 R 的全局覆盖特征
                statement = (
                    f"数据覆盖了组分 R 的宽范围（{data['R'].min():.2f} - {data['R'].max():.2f}），"
                    f"包含 {r_unique} 个不同的 R 值，为组分敏感性分析提供了充分的数据基础。"
                )
                
                evidences.append(EvidenceUnit(
                    claim_level=ClaimLevel.observation,
                    theme=EvidenceTheme.composition_sensitivity,
                    statement=statement,
                    support_metrics={
                        "R_min": float(data['R'].min()),
                        "R_max": float(data['R'].max()),
                        "R_range": float(r_range),
                        "R_unique_count": int(r_unique)
                    },
                    confidence=0.95,
                    confidence_basis={
                        "rule_id": "composition_coverage",
                        "formula": "fixed 0.95 for broad R coverage",
                        "inputs": {"R_range": float(r_range), "R_unique_count": int(r_unique)},
                        "interpretation": "数据覆盖度证据，表示后续组分分析具有足够横向范围"
                    },
                    tags=["data_coverage", "R_range"]
                ))
        
        return evidences
    
    def _format_zone_name(self, zone_name: str) -> str:
        """格式化温度区间名称"""
        zone_map = {
            "low_T": "低温（T < 230K）",
            "mid_T": "中温（230K ≤ T < 270K）",
            "high_T": "高温（T ≥ 270K）",
            "all_T": "全温度范围"
        }
        return zone_map.get(zone_name, zone_name)
