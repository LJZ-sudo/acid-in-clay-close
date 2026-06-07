"""
Model Competitor - 物理传输模型竞争专家
判定最佳物理传输模型：Arrhenius vs VTF，以及 Meyer-Neldel 补偿效应分析
"""

from typing import List, Dict, Any, Optional, Tuple
import pandas as pd
import numpy as np
from scipy import stats
from scipy.optimize import curve_fit
import warnings

try:
    from ..core.base_specialist import BaseSpecialist
    from ..core.schema import EvidenceUnit, ClaimLevel, EvidenceTheme
    from ..utils.statistics_lib import calculate_aic, calculate_aicc
except ImportError:
    from core.base_specialist import BaseSpecialist
    from core.schema import EvidenceUnit, ClaimLevel, EvidenceTheme
    from utils.statistics_lib import calculate_aic, calculate_aicc


class ModelCompetitor(BaseSpecialist):
    """
    物理传输模型竞争分析专家
    
    核心任务：
    1. Meyer-Neldel 补偿效应分析
    2. Arrhenius vs VTF 模型竞争
    """
    
    def __init__(
        self,
        name: str = "ModelCompetitor",
        mn_r2_threshold: float = 0.9,  # Meyer-Neldel R² 阈值
        min_points_mn: int = 5,  # MN 分析最小点数
        min_points_vtf: int = 8,  # VTF 拟合最小点数
        aic_threshold: float = 4.0,  # AIC 差异阈值（认为显著优于）
        t0_valid_range: Tuple[float, float] = (-100, 50)  # T0 合理范围（相对于 T_min）
    ):
        """
        初始化模型竞争器
        
        Args:
            name: 专家名称
            mn_r2_threshold: Meyer-Neldel R² 阈值
            min_points_mn: MN 分析最小点数
            min_points_vtf: VTF 拟合最小点数
            aic_threshold: AIC 差异阈值
            t0_valid_range: T0 合理范围（相对于 T_min 的偏移）
        """
        super().__init__(name)
        self.mn_r2_threshold = mn_r2_threshold
        self.min_points_mn = min_points_mn
        self.min_points_vtf = min_points_vtf
        self.aic_threshold = aic_threshold
        self.t0_valid_range = t0_valid_range
    
    def analyze(
        self,
        data: pd.DataFrame,
        profile: Optional[Dict[str, Any]] = None
    ) -> List[EvidenceUnit]:
        """
        分析物理传输模型
        
        Args:
            data: 输入数据，需包含 Ea, ln_sigma0, T, sigma 等列
            profile: 数据画像（可选）
            
        Returns:
            List[EvidenceUnit]: 证据单元列表
        """
        evidences = []
        
        # 任务 A: Meyer-Neldel 补偿效应分析
        mn_evidences = self._analyze_meyer_neldel(data)
        evidences.extend(mn_evidences)
        
        # 任务 B: Arrhenius vs VTF 模型竞争
        vtf_evidences = self._analyze_arrhenius_vs_vtf(data)
        evidences.extend(vtf_evidences)
        
        return evidences
    
    def _analyze_meyer_neldel(self, data: pd.DataFrame) -> List[EvidenceUnit]:
        """
        任务 A: Meyer-Neldel 补偿效应分析
        
        ln(sigma0) = a + Ea/E_MN
        线性回归 ln_sigma0 ~ Ea，斜率 = 1/E_MN
        
        Args:
            data: 输入数据
            
        Returns:
            List[EvidenceUnit]: 证据列表
        """
        evidences = []
        
        # 检查必需列
        required_cols = ['Ea', 'ln_sigma0']
        if not all(col in data.columns for col in required_cols):
            # 尝试从其他列计算
            if 'Ea_eV' in data.columns:
                data = data.copy()
                data['Ea'] = data['Ea_eV']
            else:
                return evidences
        
        # 数据清洗
        df = data.dropna(subset=['Ea', 'ln_sigma0']).copy()
        
        # 转换 Ea 单位（如果需要）
        if 'Ea_eV' in df.columns:
            df['Ea'] = df['Ea_eV']
        
        df = df[df['Ea'] > 0]
        
        if len(df) < self.min_points_mn:
            return evidences
        
        # 线性回归：ln_sigma0 = a + b * Ea
        x = df['Ea'].values
        y = df['ln_sigma0'].values
        
        try:
            lr = stats.linregress(x, y)
            slope = lr.slope
            intercept = lr.intercept
            r2 = lr.rvalue ** 2
            p_value = lr.pvalue
            stderr_slope = lr.stderr

            # Tier2 (issue 8, 2026-06-01): ALWAYS emit a low-confidence diagnostic
            # evidence carrying the raw MN regression fields (slope/intercept/r2/
            # E_MN/n_points), regardless of slope sign or R² threshold. Previously
            # these fields were only produced when slope>0 AND r2>=threshold, so the
            # V1 Meyer-Neldel plot had nothing to draw below threshold. This is a V1
            # specialist diagnostic (NOT the canonical V2 stage3_seed), so it does
            # not alter frozen seed results; it just makes the figure renderable.
            E_MN_diag = (1.0 / slope) if slope > 0 else None
            evidences.append(EvidenceUnit(
                claim_level=ClaimLevel.observation,
                theme=EvidenceTheme.transport_dynamics,
                statement=(
                    f"Meyer-Neldel 诊断回归：ln(sigma0) ~ Ea，slope={slope:.4g}, "
                    f"intercept={intercept:.4g}, R2={r2:.3f}, n={len(df)}"
                    + ("" if slope > 0 else "（slope<=0，未呈现正向补偿，E_MN 不适用）")
                ),
                support_metrics={
                    "slope": float(slope),
                    "intercept": float(intercept),
                    "r_squared": float(r2),
                    "p_value": float(p_value),
                    "n_points": int(len(df)),
                    "slope_positive": bool(slope > 0),
                    "E_MN_eV": float(E_MN_diag) if E_MN_diag is not None else None,
                },
                confidence=min(0.5, float(r2)),
                confidence_basis={
                    "rule_id": "meyer_neldel_diagnostic",
                    "formula": "min(0.5, r_squared)",
                    "inputs": {"r_squared": float(r2), "slope_positive": bool(slope > 0)},
                    "interpretation": "始终产出的 MN 回归诊断（供作图/审计，不作为强证据）",
                },
                tags=["meyer_neldel", "meyer_neldel_diagnostic", "transport_dynamics"],
            ))

            # 计算 E_MN
            if slope > 0:
                E_MN = 1.0 / slope
                E_MN_se = stderr_slope / (slope ** 2) if stderr_slope else None
                
                # 判断是否满足阈值
                if r2 >= self.mn_r2_threshold:
                    # 生成证据
                    statement = (
                        f"Meyer-Neldel 补偿效应分析显示，ln(sigma0) 与 Ea 呈现显著的线性关系 "
                        f"(R2 = {r2:.3f}, p < {p_value:.4f})，提取出补偿能量 E_MN = {E_MN:.3f} eV。"
                        f"这表明体系中存在普适的能量补偿机制，不同传输通道的激活能与指前因子之间存在内在关联。"
                    )
                    
                    confidence = min(0.95, r2)
                    
                    evidences.append(EvidenceUnit(
                        claim_level=ClaimLevel.observation,
                        theme=EvidenceTheme.transport_dynamics,
                        statement=statement,
                        support_metrics={
                            "E_MN_eV": float(E_MN),
                            "E_MN_se": float(E_MN_se) if E_MN_se else None,
                            "slope": float(slope),
                            "intercept": float(intercept),
                            "r_squared": float(r2),
                            "p_value": float(p_value),
                            "n_points": len(df)
                        },
                        confidence=confidence,
                        confidence_basis={
                            "rule_id": "meyer_neldel_r2_cap",
                            "formula": "min(0.95, r_squared)",
                            "inputs": {"r_squared": float(r2), "p_value": float(p_value)},
                            "interpretation": "基于 Meyer-Neldel 线性关系强度的启发式证据权重"
                        },
                        tags=["meyer_neldel", "compensation_effect", "transport_dynamics"]
                    ))
                    
                    # 如果 R² 非常高，生成解释层级证据
                    if r2 >= 0.95:
                        interpretation = (
                            f"极高的 Meyer-Neldel 相关性 (R2 = {r2:.3f}) 暗示体系中的离子传输通道"
                            f"可能共享相同的物理起源，例如共同的势垒分布或相似的局域环境结构。"
                        )
                        
                        evidences.append(EvidenceUnit(
                            claim_level=ClaimLevel.interpretation,
                            theme=EvidenceTheme.transport_dynamics,
                            statement=interpretation,
                            support_metrics={
                                "E_MN_eV": float(E_MN),
                                "r_squared": float(r2)
                            },
                            confidence=0.85,
                            confidence_basis={
                                "rule_id": "meyer_neldel_mechanism_insight",
                                "formula": "fixed 0.85 when r_squared >= 0.95",
                                "inputs": {"r_squared": float(r2)},
                                "interpretation": "极高 MN 相关性触发的解释层证据"
                            },
                            tags=["meyer_neldel", "mechanism_insight"]
                        ))
            
        except Exception as e:
            # 拟合失败，跳过
            pass
        
        return evidences
    
    def _analyze_arrhenius_vs_vtf(self, data: pd.DataFrame) -> List[EvidenceUnit]:
        """
        任务 B: Arrhenius vs VTF 模型竞争
        
        Arrhenius: sigma = sigma0 * exp(-Ea / (k*T))
        VTF: sigma = sigma0 * exp(-B / (T - T0))
        
        Args:
            data: 输入数据
            
        Returns:
            List[EvidenceUnit]: 证据列表
        """
        evidences = []
        
        # 检查必需列
        required_cols = ['T', 'sigma']
        if not all(col in data.columns for col in required_cols):
            # 尝试其他列名
            if 'T_K' in data.columns:
                data = data.copy()
                data['T'] = data['T_K']
            elif 'T_mid' in data.columns:
                data = data.copy()
                data['T'] = data['T_mid']
            
            if 'conductivity' in data.columns:
                data = data.copy()
                data['sigma'] = data['conductivity']
            
            if not all(col in data.columns for col in required_cols):
                return evidences
        
        # 数据清洗
        df = data.dropna(subset=['T', 'sigma']).copy()
        df = df[df['sigma'] > 0]
        df = df[df['T'] > 0]
        
        if len(df) < self.min_points_vtf:
            return evidences
        
        # 按温度排序
        df = df.sort_values('T')
        
        # 检查温度范围（需要宽温区数据）
        T_range = df['T'].max() - df['T'].min()
        if T_range < 50:  # 温度范围至少 50K
            return evidences
        
        T = df['T'].values
        sigma = df['sigma'].values
        ln_sigma = np.log(sigma)
        
        # 拟合 Arrhenius 模型
        arrhenius_result = self._fit_arrhenius(T, sigma)
        
        # 拟合 VTF 模型
        vtf_result = self._fit_vtf(T, sigma)
        
        # 模型比较
        if arrhenius_result and vtf_result:
            evidences.extend(self._compare_models(
                arrhenius_result, vtf_result, T, sigma
            ))
        
        return evidences
    
    def _fit_arrhenius(
        self,
        T: np.ndarray,
        sigma: np.ndarray
    ) -> Optional[Dict[str, Any]]:
        """
        拟合 Arrhenius 模型
        
        sigma = sigma0 * exp(-Ea / (k*T))
        ln(sigma) = ln(sigma0) - Ea / (k*T)
        
        Args:
            T: 温度数组（K）
            sigma: 电导率数组
            
        Returns:
            Dict: 拟合结果
        """
        try:
            ln_sigma = np.log(sigma)
            inv_T = 1.0 / T
            
            # 线性回归
            lr = stats.linregress(inv_T, ln_sigma)
            
            # 提取参数
            slope = lr.slope
            intercept = lr.intercept
            r2 = lr.rvalue ** 2
            
            # 计算 Ea（单位：eV）
            k_eV = 8.617333e-5  # Boltzmann constant in eV/K
            Ea_eV = -slope * k_eV
            ln_sigma0 = intercept
            
            # 计算残差和 AIC
            sigma_pred = np.exp(intercept + slope * inv_T)
            residuals = sigma - sigma_pred
            rss = np.sum(residuals**2)
            n = len(T)
            k_params = 2  # sigma0, Ea
            
            aic = calculate_aic(n=n, rss=float(rss), k=k_params)
            aicc = calculate_aicc(n=n, rss=float(rss), k=k_params)
            
            return {
                "model": "Arrhenius",
                "Ea_eV": float(Ea_eV),
                "ln_sigma0": float(ln_sigma0),
                "r_squared": float(r2),
                "rss": float(rss),
                "aic": float(aic) if aic is not None else None,
                "aicc": float(aicc) if aicc is not None else None,
                "n_points": n,
                "n_params": k_params,
                "params": {"Ea_eV": float(Ea_eV), "ln_sigma0": float(ln_sigma0)}
            }
            
        except Exception:
            return None
    
    def _fit_vtf(
        self,
        T: np.ndarray,
        sigma: np.ndarray
    ) -> Optional[Dict[str, Any]]:
        """
        拟合 VTF 模型
        
        sigma = sigma0 * exp(-B / (T - T0))
        ln(sigma) = ln(sigma0) - B / (T - T0)
        
        Args:
            T: 温度数组（K）
            sigma: 电导率数组
            
        Returns:
            Dict: 拟合结果
        """
        try:
            ln_sigma = np.log(sigma)
            
            # VTF 模型函数
            def vtf_model(T, ln_sigma0, B, T0):
                return ln_sigma0 - B / (T - T0)
            
            # 初始猜测
            T_min = T.min()
            T_max = T.max()
            
            # T0 应该低于最低温度
            T0_init = T_min - 50
            B_init = 1000
            ln_sigma0_init = np.max(ln_sigma)
            
            # 设置边界
            bounds = (
                [ln_sigma0_init - 10, 100, T_min - 200],  # 下界
                [ln_sigma0_init + 10, 5000, T_min]  # 上界
            )
            
            # 非线性拟合
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                popt, pcov = curve_fit(
                    vtf_model,
                    T,
                    ln_sigma,
                    p0=[ln_sigma0_init, B_init, T0_init],
                    bounds=bounds,
                    maxfev=10000
                )
            
            ln_sigma0, B, T0 = popt
            
            # 计算 R²
            ln_sigma_pred = vtf_model(T, ln_sigma0, B, T0)
            ss_res = np.sum((ln_sigma - ln_sigma_pred)**2)
            ss_tot = np.sum((ln_sigma - np.mean(ln_sigma))**2)
            r2 = 1 - ss_res / ss_tot
            
            # 计算残差和 AIC
            sigma_pred = np.exp(ln_sigma_pred)
            residuals = sigma - sigma_pred
            rss = np.sum(residuals**2)
            n = len(T)
            k_params = 3  # sigma0, B, T0
            
            aic = calculate_aic(n=n, rss=float(rss), k=k_params)
            aicc = calculate_aicc(n=n, rss=float(rss), k=k_params)
            
            # 检查 T0 的合理性
            T0_offset = T0 - T_min
            is_valid = self.t0_valid_range[0] <= T0_offset <= self.t0_valid_range[1]
            
            return {
                "model": "VTF",
                "ln_sigma0": float(ln_sigma0),
                "B": float(B),
                "T0": float(T0),
                "T0_offset": float(T0_offset),
                "r_squared": float(r2),
                "rss": float(rss),
                "aic": float(aic) if aic is not None else None,
                "aicc": float(aicc) if aicc is not None else None,
                "n_points": n,
                "n_params": k_params,
                "T0_valid": is_valid,
                "params": {"ln_sigma0": float(ln_sigma0), "B": float(B), "T0": float(T0)}
            }
            
        except Exception:
            return None
    
    def _compare_models(
        self,
        arrhenius: Dict[str, Any],
        vtf: Dict[str, Any],
        T: np.ndarray,
        sigma: np.ndarray
    ) -> List[EvidenceUnit]:
        """
        比较 Arrhenius 和 VTF 模型
        
        Args:
            arrhenius: Arrhenius 拟合结果
            vtf: VTF 拟合结果
            T: 温度数组
            sigma: 电导率数组
            
        Returns:
            List[EvidenceUnit]: 证据列表
        """
        evidences = []
        
        arr_ic = arrhenius.get('aicc') if arrhenius.get('aicc') is not None else arrhenius.get('aic')
        vtf_ic = vtf.get('aicc') if vtf.get('aicc') is not None else vtf.get('aic')
        criterion = 'aicc' if arrhenius.get('aicc') is not None and vtf.get('aicc') is not None else 'aic'
        if arr_ic is None or vtf_ic is None:
            return evidences
        delta_aic = arr_ic - vtf_ic
        
        # 温度范围
        T_min = T.min()
        T_max = T.max()
        T_range = T_max - T_min
        
        # 生成模型比较证据（observation 层级）
        if delta_aic > 0:
            better_model = "VTF"
            worse_model = "Arrhenius"
        else:
            better_model = "Arrhenius"
            worse_model = "VTF"
        
        comparison_statement = (
            f"在宽温区数据 (T = {T_min:.1f} - {T_max:.1f} K, 跨度 {T_range:.1f} K) 上，"
            f"{better_model} 模型的拟合质量优于 {worse_model} 模型 "
            f"(Δ{criterion.upper()} = {abs(delta_aic):.2f})。"
        )
        
        evidences.append(EvidenceUnit(
            claim_level=ClaimLevel.observation,
            theme=EvidenceTheme.transport_dynamics,
            statement=comparison_statement,
            support_metrics={
                "arrhenius_aic": arrhenius['aic'],
                "vtf_aic": vtf['aic'],
                "arrhenius_aicc": arrhenius.get('aicc'),
                "vtf_aicc": vtf.get('aicc'),
                f"delta_{criterion}": float(delta_aic),
                "selection_criterion": criterion,
                "arrhenius_r2": arrhenius['r_squared'],
                "vtf_r2": vtf['r_squared'],
                "T_min": float(T_min),
                "T_max": float(T_max),
                "T_range": float(T_range),
                "n_points": arrhenius['n_points']
            },
            confidence=0.90,
            confidence_basis={
                "rule_id": "model_comparison_observation",
                "formula": "fixed 0.90 for successful Arrhenius/VTF information-criterion comparison",
                "inputs": {"criterion": criterion, f"delta_{criterion}": float(delta_aic)},
                "interpretation": "模型比较观测证据；信息准则差值不等同于物理机制证明"
            },
            tags=["model_comparison", "arrhenius_vs_vtf"]
        ))
        
        # VTF 判定：如果 VTF 显著更优且 T0 合理
        if delta_aic > self.aic_threshold and vtf['T0_valid']:
            # 生成 interpretation 层级证据
            T0 = vtf['T0']
            B = vtf['B']
            
            statement = (
                f"宽温区电导率更符合 VTF 动力学特征 (Δ{criterion.upper()} = {delta_aic:.2f} > {self.aic_threshold})，"
                f"提取出理想玻璃化温度 T0 = {T0:.1f} K (相对最低温度偏移 {vtf['T0_offset']:.1f} K)，"
                f"VTF 参数 B = {B:.1f} K。"
                f"这强烈暗示体系存在类似聚合物的链段运动或液态动态异质性，"
                f"离子传输受到合作重排过程（cooperative rearrangement）的控制。"
            )
            
            # 置信度基于 AIC 差异和 T0 合理性
            confidence = min(0.90, 0.7 + delta_aic / 20.0)
            
            evidences.append(EvidenceUnit(
                claim_level=ClaimLevel.interpretation,
                theme=EvidenceTheme.transport_dynamics,
                statement=statement,
                support_metrics={
                    "T0_K": float(T0),
                    "B_K": float(B),
                    "T0_offset": vtf['T0_offset'],
                    f"delta_{criterion}": float(delta_aic),
                    "selection_criterion": criterion,
                    "vtf_r2": vtf['r_squared'],
                    "arrhenius_r2": arrhenius['r_squared']
                },
                confidence=confidence,
                confidence_basis={
                    "rule_id": "vtf_preferred_delta_ic",
                    "formula": "min(0.90, 0.7 + delta_ic / 20.0)",
                    "inputs": {"criterion": criterion, f"delta_{criterion}": float(delta_aic), "T0_valid": bool(vtf['T0_valid'])},
                    "interpretation": "VTF 偏好证据；用于生成假说，不作为机制证明"
                },
                tags=["vtf_preferred", "glass_transition", "cooperative_dynamics"]
            ))
            
            # 如果 T0 非常接近合理范围的中心，生成额外的解释
            if -80 <= vtf['T0_offset'] <= -20:
                additional_statement = (
                    f"提取的 T0 值 ({T0:.1f} K) 位于最低测量温度以下 {abs(vtf['T0_offset']):.1f} K，"
                    f"这是典型的玻璃态电解质特征，表明体系在更低温度下可能发生动力学冻结。"
                )
                
                evidences.append(EvidenceUnit(
                    claim_level=ClaimLevel.interpretation,
                    theme=EvidenceTheme.phase_transition,
                    statement=additional_statement,
                    support_metrics={
                        "T0_K": float(T0),
                        "T_min_K": float(T_min),
                        "T0_offset": vtf['T0_offset']
                    },
                    confidence=0.80,
                    confidence_basis={
                        "rule_id": "vtf_t0_offset_window",
                        "formula": "fixed 0.80 when -80 <= T0_offset <= -20",
                        "inputs": {"T0_offset": float(vtf['T0_offset'])},
                        "interpretation": "T0 位置触发的动态冻结线索"
                    },
                    tags=["glass_transition", "dynamic_freezing"]
                ))
        
        # 如果 Arrhenius 更优，也生成相应证据
        elif delta_aic < -self.aic_threshold:
            statement = (
                f"Arrhenius 模型显著优于 VTF 模型 (Δ{criterion.upper()} = {abs(delta_aic):.2f} > {self.aic_threshold})，"
                f"表明在测量温度范围内，离子传输遵循简单的热激活机制，"
                f"不存在明显的合作重排或玻璃化转变特征。"
            )
            
            evidences.append(EvidenceUnit(
                claim_level=ClaimLevel.interpretation,
                theme=EvidenceTheme.transport_dynamics,
                statement=statement,
                support_metrics={
                    f"delta_{criterion}": float(delta_aic),
                    "selection_criterion": criterion,
                    "arrhenius_r2": arrhenius['r_squared'],
                    "arrhenius_Ea_eV": arrhenius['Ea_eV']
                },
                confidence=0.85,
                confidence_basis={
                    "rule_id": "arrhenius_preferred_delta_ic",
                    "formula": "fixed 0.85 when Arrhenius beats VTF by threshold",
                    "inputs": {"criterion": criterion, f"delta_{criterion}": float(delta_aic)},
                    "interpretation": "Arrhenius 偏好证据；用于约束机理语言"
                },
                tags=["arrhenius_preferred", "simple_activation"]
            ))
        
        return evidences
