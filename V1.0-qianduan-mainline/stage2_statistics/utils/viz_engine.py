"""
Visualization Engine - 学术级绘图引擎
生成符合学术论文标准的图表
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib as mpl
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, List, Union

# 设置 matplotlib 全局参数（学术论文标准）
mpl.rcParams['font.size'] = 12
mpl.rcParams['axes.labelsize'] = 12
mpl.rcParams['axes.titlesize'] = 13
mpl.rcParams['xtick.labelsize'] = 11
mpl.rcParams['ytick.labelsize'] = 11
mpl.rcParams['legend.fontsize'] = 10
mpl.rcParams['figure.titlesize'] = 14
mpl.rcParams['figure.dpi'] = 100  # 屏幕显示
mpl.rcParams['savefig.dpi'] = 300  # 保存时高分辨率
mpl.rcParams['savefig.bbox'] = 'tight'
mpl.rcParams['axes.grid'] = True
mpl.rcParams['grid.alpha'] = 0.3
mpl.rcParams['lines.linewidth'] = 2.0
mpl.rcParams['lines.markersize'] = 6

# 学术配色方案（参考旧代码）
ACADEMIC_COLORS = {
    'primary': '#2196F3',      # 蓝色（高温区）
    'secondary': '#FF9800',    # 橙色（中温区）
    'tertiary': '#E91E63',     # 粉红色（低温区）
    'accent1': '#4ECDC4',      # 青色
    'accent2': '#FF6B6B',      # 红色
    'neutral': 'steelblue',    # 钢蓝色
    'fit_line': '#D32F2F',     # 深红色（拟合线）
    'gray': 'gray'
}


class VizEngine:
    """
    学术级可视化引擎
    
    生成符合学术论文标准的图表，包括：
    - Arrhenius/VTF 模型对比
    - Ea 趋势图（带置信区间）
    - EIS-Arrhenius 温度对齐图
    """
    
    def __init__(
        self,
        style: str = 'default',
        dpi: int = 300,
        font_size: int = 12
    ):
        """
        初始化可视化引擎
        
        Args:
            style: 绘图风格 ('default', 'seaborn', 'ggplot')
            dpi: 保存图像的分辨率
            font_size: 基础字体大小
        """
        self.style = style
        self.dpi = dpi
        self.font_size = font_size
        
        # 应用风格
        if style != 'default':
            plt.style.use(style)
    
    def plot_arrhenius_vtf_comparison(
        self,
        T: np.ndarray,
        sigma: np.ndarray,
        arr_params: Dict[str, float],
        vtf_params: Dict[str, float],
        output_path: Union[str, Path],
        title: Optional[str] = None,
        show_residuals: bool = False
    ) -> None:
        """
        绘制 Arrhenius 和 VTF 模型对比图
        
        Args:
            T: 温度数组 (K)
            sigma: 电导率数组 (S/cm)
            arr_params: Arrhenius 参数字典 {'sigma0': float, 'Ea': float, 'R2': float}
            vtf_params: VTF 参数字典 {'A': float, 'B': float, 'T0': float, 'R2': float}
            output_path: 输出文件路径
            title: 图表标题（可选）
            show_residuals: 是否显示残差图
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 创建图形
        if show_residuals:
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8, 10), 
                                           gridspec_kw={'height_ratios': [3, 1]})
        else:
            fig, ax1 = plt.subplots(figsize=(8, 6))
        
        # 计算 1000/T
        inv_T = 1000.0 / T
        
        # Arrhenius 模型拟合曲线
        sigma0_arr = arr_params['sigma0']
        Ea_arr = arr_params['Ea']
        k_B = 8.617333e-5  # eV/K
        
        T_fit = np.linspace(T.min(), T.max(), 200)
        inv_T_fit = 1000.0 / T_fit
        sigma_arr_fit = sigma0_arr * np.exp(-Ea_arr / (k_B * T_fit))
        
        # VTF 模型拟合曲线
        A_vtf = vtf_params['A']
        B_vtf = vtf_params['B']
        T0_vtf = vtf_params['T0']
        
        sigma_vtf_fit = A_vtf * np.exp(-B_vtf / (T_fit - T0_vtf))
        
        # 绘制实验数据点
        ax1.scatter(inv_T, np.log10(sigma), 
                   s=50, alpha=0.7, c=ACADEMIC_COLORS['neutral'],
                   edgecolors='black', linewidth=0.5,
                   label='Experimental data', zorder=3)
        
        # 绘制 Arrhenius 拟合线
        ax1.plot(inv_T_fit, np.log10(sigma_arr_fit),
                color=ACADEMIC_COLORS['primary'], linewidth=2.5,
                label=f'Arrhenius ($R^2$ = {arr_params["R2"]:.4f})',
                zorder=2)
        
        # 绘制 VTF 拟合线
        ax1.plot(inv_T_fit, np.log10(sigma_vtf_fit),
                color=ACADEMIC_COLORS['fit_line'], linewidth=2.5, linestyle='--',
                label=f'VTF ($R^2$ = {vtf_params["R2"]:.4f}, $T_0$ = {T0_vtf:.1f} K)',
                zorder=2)
        
        # 设置标签（LaTeX 格式）
        ax1.set_xlabel(r'$1000/T$ (K$^{-1}$)', fontsize=self.font_size)
        ax1.set_ylabel(r'$\log_{10}(\sigma)$ (S/cm)', fontsize=self.font_size)
        
        if title:
            ax1.set_title(title, fontsize=self.font_size + 1, fontweight='bold')
        else:
            ax1.set_title('Arrhenius vs VTF Model Comparison',
                         fontsize=self.font_size + 1, fontweight='bold')
        
        ax1.legend(loc='best', frameon=True, shadow=True)
        ax1.grid(True, alpha=0.3, linestyle='--')
        
        # 绘制残差图（如果需要）
        if show_residuals:
            # 计算残差
            sigma_arr_interp = sigma0_arr * np.exp(-Ea_arr / (k_B * T))
            sigma_vtf_interp = A_vtf * np.exp(-B_vtf / (T - T0_vtf))
            
            residuals_arr = np.log10(sigma) - np.log10(sigma_arr_interp)
            residuals_vtf = np.log10(sigma) - np.log10(sigma_vtf_interp)
            
            ax2.scatter(inv_T, residuals_arr, 
                       c=ACADEMIC_COLORS['primary'], alpha=0.6, s=30,
                       label='Arrhenius residuals')
            ax2.scatter(inv_T, residuals_vtf,
                       c=ACADEMIC_COLORS['fit_line'], alpha=0.6, s=30,
                       label='VTF residuals')
            ax2.axhline(0, color='black', linestyle='--', linewidth=1, alpha=0.5)
            
            ax2.set_xlabel(r'$1000/T$ (K$^{-1}$)', fontsize=self.font_size)
            ax2.set_ylabel('Residuals', fontsize=self.font_size)
            ax2.legend(loc='best', fontsize=10)
            ax2.grid(True, alpha=0.3, linestyle='--')
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=self.dpi, bbox_inches='tight')
        plt.close()
    
    def plot_ea_trend_with_ci(
        self,
        R_values: np.ndarray,
        Ea_values: np.ndarray,
        ci_low: np.ndarray,
        ci_high: np.ndarray,
        output_path: Union[str, Path],
        title: Optional[str] = None,
        xlabel: str = 'R (H$_3$PO$_4$/H$_2$O mol ratio)',
        ylabel: str = r'$E_{\mathrm{a}}$ (eV)',
        critical_points: Optional[List[float]] = None
    ) -> None:
        """
        绘制 Ea 随组分变化的趋势图（带置信区间）
        
        Args:
            R_values: R 值数组
            Ea_values: Ea 值数组
            ci_low: 置信区间下界
            ci_high: 置信区间上界
            output_path: 输出文件路径
            title: 图表标题
            xlabel: x 轴标签
            ylabel: y 轴标签
            critical_points: 临界点列表（用于标注）
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 创建图形
        fig, ax = plt.subplots(figsize=(10, 6))
        
        # 绘制置信区间（阴影）
        ax.fill_between(R_values, ci_low, ci_high,
                       alpha=0.3, color=ACADEMIC_COLORS['primary'],
                       label='95% Confidence Interval')
        
        # 绘制 Ea 趋势线
        ax.plot(R_values, Ea_values,
               color=ACADEMIC_COLORS['primary'], linewidth=2.5,
               marker='o', markersize=8, markerfacecolor='white',
               markeredgecolor=ACADEMIC_COLORS['primary'], markeredgewidth=2,
               label=r'$E_{\mathrm{a}}$ trend', zorder=3)
        
        # 标注临界点（如果提供）
        if critical_points:
            for cp in critical_points:
                # 找到最接近临界点的索引
                idx = np.argmin(np.abs(R_values - cp))
                ax.axvline(cp, color=ACADEMIC_COLORS['fit_line'],
                          linestyle='--', linewidth=2, alpha=0.7)
                ax.annotate(f'Critical point\nR = {cp:.3f}',
                           xy=(cp, Ea_values[idx]),
                           xytext=(10, 20), textcoords='offset points',
                           fontsize=10, color=ACADEMIC_COLORS['fit_line'],
                           bbox=dict(boxstyle='round,pad=0.5',
                                   facecolor='white', edgecolor=ACADEMIC_COLORS['fit_line'],
                                   alpha=0.8),
                           arrowprops=dict(arrowstyle='->', 
                                         color=ACADEMIC_COLORS['fit_line'],
                                         lw=1.5))
        
        # 设置标签
        ax.set_xlabel(xlabel, fontsize=self.font_size)
        ax.set_ylabel(ylabel, fontsize=self.font_size)
        
        if title:
            ax.set_title(title, fontsize=self.font_size + 1, fontweight='bold')
        else:
            ax.set_title(r'Activation Energy vs Composition (with 95% CI)',
                        fontsize=self.font_size + 1, fontweight='bold')
        
        ax.legend(loc='best', frameon=True, shadow=True)
        ax.grid(True, alpha=0.3, linestyle='--')
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=self.dpi, bbox_inches='tight')
        plt.close()
    
    def plot_eis_alignment(
        self,
        T_axis: np.ndarray,
        features: Dict[str, np.ndarray],
        t_arc: float,
        t_break: float,
        output_path: Union[str, Path],
        title: Optional[str] = None,
        alignment_threshold: float = 10.0
    ) -> None:
        """
        可视化 EIS 特征演化与 Arrhenius 折点的温度对齐
        
        Args:
            T_axis: 温度轴数组 (K)
            features: EIS 特征字典，例如 {'arc_intensity': array, 'char_freq': array}
            t_arc: EIS 圆弧出现温度 (K)
            t_break: Arrhenius 折点温度 (K)
            output_path: 输出文件路径
            title: 图表标题
            alignment_threshold: 对齐阈值 (K)
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 计算温度差
        delta_T = abs(t_arc - t_break)
        is_aligned = delta_T < alignment_threshold
        
        # 创建双 y 轴图形
        fig, ax1 = plt.subplots(figsize=(10, 6))
        ax2 = ax1.twinx()
        
        # 绘制 EIS 特征（左 y 轴）
        colors_features = [ACADEMIC_COLORS['accent1'], ACADEMIC_COLORS['accent2']]
        for i, (feature_name, feature_values) in enumerate(features.items()):
            color = colors_features[i % len(colors_features)]
            ax1.plot(T_axis, feature_values,
                    color=color, linewidth=2.5, marker='s',
                    markersize=6, label=f'EIS: {feature_name}',
                    alpha=0.8)
        
        # 标注 T_arc（EIS 圆弧出现温度）
        ax1.axvline(t_arc, color=ACADEMIC_COLORS['accent1'],
                   linestyle='--', linewidth=2.5, alpha=0.8,
                   label=f'$T_{{\\mathrm{{arc}}}}$ = {t_arc:.1f} K')
        
        # 标注 T_break（Arrhenius 折点温度）
        ax2.axvline(t_break, color=ACADEMIC_COLORS['fit_line'],
                   linestyle='--', linewidth=2.5, alpha=0.8,
                   label=f'$T_{{\\mathrm{{break}}}}$ = {t_break:.1f} K')
        
        # 如果高度对齐，添加阴影区域
        if is_aligned:
            ax1.axvspan(min(t_arc, t_break) - 5, max(t_arc, t_break) + 5,
                       alpha=0.2, color='green',
                       label=f'Aligned region (ΔT = {delta_T:.1f} K)')
        
        # 设置标签
        ax1.set_xlabel('Temperature (K)', fontsize=self.font_size)
        ax1.set_ylabel('EIS Features (a.u.)', fontsize=self.font_size, 
                      color=ACADEMIC_COLORS['accent1'])
        ax2.set_ylabel(r'$E_{\mathrm{a}}$ or Arrhenius metric (eV)', 
                      fontsize=self.font_size,
                      color=ACADEMIC_COLORS['fit_line'])
        
        # 设置刻度颜色
        ax1.tick_params(axis='y', labelcolor=ACADEMIC_COLORS['accent1'])
        ax2.tick_params(axis='y', labelcolor=ACADEMIC_COLORS['fit_line'])
        
        if title:
            ax1.set_title(title, fontsize=self.font_size + 1, fontweight='bold')
        else:
            status = "Highly Aligned" if is_aligned else "Misaligned"
            ax1.set_title(f'EIS-Arrhenius Temperature Alignment ({status})',
                         fontsize=self.font_size + 1, fontweight='bold')
        
        # 合并图例
        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2,
                  loc='best', frameon=True, shadow=True)
        
        ax1.grid(True, alpha=0.3, linestyle='--')
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=self.dpi, bbox_inches='tight')
        plt.close()
    
    def plot_meyer_neldel(
        self,
        Ea_values: np.ndarray,
        ln_sigma0_values: np.ndarray,
        fit_params: Dict[str, float],
        output_path: Union[str, Path],
        title: Optional[str] = None,
        show_equation: bool = True
    ) -> None:
        """
        绘制 Meyer-Neldel 补偿效应图
        
        Args:
            Ea_values: 活化能数组 (eV)
            ln_sigma0_values: ln(sigma0) 数组
            fit_params: 拟合参数字典 {'slope': float, 'intercept': float, 'R2': float, 'E_MN': float}
            output_path: 输出文件路径
            title: 图表标题
            show_equation: 是否显示拟合方程
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        fig, ax = plt.subplots(figsize=(8, 6))
        
        # 绘制数据点
        ax.scatter(Ea_values, ln_sigma0_values,
                  s=50, alpha=0.6, c=ACADEMIC_COLORS['neutral'],
                  edgecolors='black', linewidth=0.5,
                  label='Experimental data', zorder=3)
        
        # 绘制拟合线
        slope = fit_params['slope']
        intercept = fit_params['intercept']
        E_MN = fit_params['E_MN']
        R2 = fit_params['R2']
        
        x_fit = np.linspace(Ea_values.min(), Ea_values.max(), 100)
        y_fit = slope * x_fit + intercept
        
        ax.plot(x_fit, y_fit,
               color=ACADEMIC_COLORS['fit_line'], linewidth=2.5,
               label=f'Linear fit ($R^2$ = {R2:.4f})', zorder=2)
        
        # 显示方程
        if show_equation:
            equation_text = (
                f'$\\ln(\\sigma_0) = {slope:.3f} \\cdot E_a + {intercept:.3f}$\n'
                f'$E_{{\\mathrm{{MN}}}} = {E_MN:.2f}$ eV'
            )
            ax.text(0.05, 0.95, equation_text,
                   transform=ax.transAxes,
                   fontsize=11, verticalalignment='top',
                   bbox=dict(boxstyle='round', facecolor='white',
                           edgecolor=ACADEMIC_COLORS['fit_line'], alpha=0.8))
        
        # 设置标签
        ax.set_xlabel(r'$E_{\mathrm{a}}$ (eV)', fontsize=self.font_size)
        ax.set_ylabel(r'$\ln(\sigma_0)$ (S/cm)', fontsize=self.font_size)
        
        if title:
            ax.set_title(title, fontsize=self.font_size + 1, fontweight='bold')
        else:
            ax.set_title('Meyer-Neldel Compensation Effect',
                        fontsize=self.font_size + 1, fontweight='bold')
        
        ax.legend(loc='best', frameon=True, shadow=True)
        ax.grid(True, alpha=0.3, linestyle='--')
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=self.dpi, bbox_inches='tight')
        plt.close()
    
    def plot_composition_heatmap(
        self,
        R_values: np.ndarray,
        N_values: np.ndarray,
        Ea_matrix: np.ndarray,
        output_path: Union[str, Path],
        title: Optional[str] = None,
        cmap: str = 'viridis'
    ) -> None:
        """
        绘制组分-活化能热力图
        
        Args:
            R_values: R 值数组
            N_values: N 值数组
            Ea_matrix: Ea 矩阵 (shape: len(N_values) x len(R_values))
            output_path: 输出文件路径
            title: 图表标题
            cmap: 颜色映射
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        fig, ax = plt.subplots(figsize=(10, 8))
        
        # 绘制热力图
        im = ax.imshow(Ea_matrix, aspect='auto', origin='lower',
                      cmap=cmap, interpolation='bilinear')
        
        # 设置刻度
        ax.set_xticks(np.arange(len(R_values)))
        ax.set_yticks(np.arange(len(N_values)))
        ax.set_xticklabels([f'{r:.3f}' for r in R_values], rotation=45)
        ax.set_yticklabels([f'{n:.2f}' for n in N_values])
        
        # 设置标签
        ax.set_xlabel('R (H$_3$PO$_4$/H$_2$O mol ratio)', fontsize=self.font_size)
        ax.set_ylabel('N (liquid/solid mass ratio)', fontsize=self.font_size)
        
        if title:
            ax.set_title(title, fontsize=self.font_size + 1, fontweight='bold')
        else:
            ax.set_title(r'$E_{\mathrm{a}}$ Composition Map',
                        fontsize=self.font_size + 1, fontweight='bold')
        
        # 添加颜色条
        cbar = plt.colorbar(im, ax=ax)
        cbar.set_label(r'$E_{\mathrm{a}}$ (eV)', fontsize=self.font_size)
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=self.dpi, bbox_inches='tight')
        plt.close()
    
    @staticmethod
    def save_figure_with_metadata(
        fig: plt.Figure,
        output_path: Union[str, Path],
        metadata: Optional[Dict[str, Any]] = None,
        dpi: int = 300
    ) -> None:
        """
        保存图形并附加元数据
        
        Args:
            fig: matplotlib Figure 对象
            output_path: 输出文件路径
            metadata: 元数据字典
            dpi: 分辨率
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        if metadata:
            fig.savefig(output_path, dpi=dpi, bbox_inches='tight',
                       metadata=metadata)
        else:
            fig.savefig(output_path, dpi=dpi, bbox_inches='tight')
        
        plt.close(fig)
