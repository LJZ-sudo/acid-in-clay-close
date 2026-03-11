# -*- coding: utf-8 -*-
"""
Figure 1: 典型 S8 样品 Arrhenius 图 (Advanced Materials 风格)
- 下横轴: 1000/T (K⁻¹)
- 上横轴: T (°C)
- 纵轴: log₁₀(σ / mS·cm⁻¹)
- 分段拟合线 + 数据点，变化点垂直虚线，每段标注 Ea
"""
from pathlib import Path
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# 常量
CLOSE_ROOT = Path(__file__).resolve().parent.parent
PHASE1_DIR = CLOSE_ROOT / "output" / "phase1_results"
OUT_DIR = CLOSE_ROOT / "paper_figure"
kB_eV = 8.617333e-5  # eV/K

# AM 期刊风格：Helvetica/Arial，单栏约 8.5 cm，双栏 17.5 cm；字体不小于 5–7 pt（印刷时）
# 使用 300 dpi，线宽 1–1.5 pt，RGB
AM_RC = {
    'font.family': 'sans-serif',
    'font.sans-serif': ['Arial', 'Helvetica', 'DejaVu Sans'],
    'font.size': 9,
    'axes.labelsize': 10,
    'axes.titlesize': 10,
    'xtick.labelsize': 9,
    'ytick.labelsize': 9,
    'legend.fontsize': 8,
    'axes.linewidth': 1.0,
    'lines.linewidth': 1.5,
    'lines.markersize': 5,
}


def load_phase1_result(sample_id: str) -> dict:
    path = PHASE1_DIR / f"{sample_id}_analysis_result.json"
    if not path.exists():
        raise FileNotFoundError(f"Phase1 result not found: {path}")
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def sigma_S_cm_to_log10_mS_cm(sigma_S_cm: float) -> float:
    """σ (S/cm) -> log₁₀(σ / mS·cm⁻¹). 即 log10(σ_S_cm * 1000)."""
    if sigma_S_cm <= 0:
        return np.nan
    return np.log10(sigma_S_cm * 1000.0)


def ln_sigma_to_log10_mS_cm(ln_sigma: float) -> float:
    """ln(σ) with σ in S/cm -> log₁₀(σ / mS·cm⁻¹)."""
    return (ln_sigma + np.log(1000)) / np.log(10)


def main():
    sample_id = "S8-3-37-1-1"  # 典型 S8 样品，三段 Arrhenius，35 数据点，R=0.30, N=4.89
    data = load_phase1_result(sample_id)

    temperatures_K = np.array(data["temperatures"], dtype=float)
    conductivity_S_cm = np.array(data["conductivity_values"], dtype=float)
    # 去掉明显异常点（负值、零值、以及低温区明显偏离的孤立点）
    valid = (temperatures_K > 0) & (conductivity_S_cm > 0)
    temperatures_K = temperatures_K[valid]
    conductivity_S_cm = conductivity_S_cm[valid]
    # 剔除低温端孤立异常点（如 186 K 处单点跳变）
    if len(temperatures_K) > 1 and temperatures_K[-1] < 195:
        if conductivity_S_cm[-1] > 1e-4 and conductivity_S_cm[-2] < 1e-6:
            temperatures_K = temperatures_K[:-1]
            conductivity_S_cm = conductivity_S_cm[:-1]

    inv_T = 1000.0 / temperatures_K  # K⁻¹
    T_C = temperatures_K - 273.15
    log_sigma = np.array([sigma_S_cm_to_log10_mS_cm(s) for s in conductivity_S_cm])

    segments = data["arrhenius"]["segments"]
    if not segments:
        raise ValueError("No arrhenius segments in JSON")

    # 按 1000/T 升序（即 T 从高到低）排序，与常见 Arrhenius 图一致
    order = np.argsort(inv_T)
    inv_T = inv_T[order]
    T_C = T_C[order]
    log_sigma = log_sigma[order]
    temperatures_K = temperatures_K[order]
    conductivity_S_cm = conductivity_S_cm[order]

    # 分段边界（变化点）：相邻段之间取边界 1000/T
    breakpoints_inv_T = []
    for i in range(len(segments) - 1):
        # 当前段温区 [T_low, T_high]，下一段 [T_low2, T_high2]；边界取下一段的高温端
        tr = segments[i + 1].get("temp_range_K") or segments[i + 1].get("T_range")
        if tr:
            T_bound = max(tr)  # 下一段最高 T
            breakpoints_inv_T.append(1000.0 / T_bound)

    # 绘图
    plt.rcParams.update(AM_RC)
    fig, ax1 = plt.subplots(figsize=(5.2, 4.0))  # 单栏约 8.5 cm -> 5.2 inch 左右

    # 数据点 - 使用深色实心点
    ax1.scatter(inv_T, log_sigma, color='#2c3e50', s=36, zorder=3, edgecolors='white', linewidths=0.6, label='Data', alpha=0.85)

    # 分段拟合线颜色 - 参考图鲜艳配色（红、绿、橙）
    # 类似参考图中的 SP-0.3-4 (红/粉), HP-0.3-2 (绿), BP-0.2-1 (橙)
    colors_seg = ['#E91E63', '#4CAF50', '#FF9800'][:len(segments)]  # 粉红、绿色、橙色

    # 分段拟合线 + Ea 标注
    x_plot = np.linspace(inv_T.min(), inv_T.max(), 200)
    
    for idx, seg in enumerate(segments):
        Ea = seg["Ea_eV"]
        ln_sigma0 = seg["ln_sigma0"]
        r_squared = seg.get("r_squared", 0)
        tr = seg.get("temp_range_K") or seg.get("T_range") or [inv_T.min(), inv_T.max()]
        T_lo, T_hi = min(tr), max(tr)
        inv_T_lo, inv_T_hi = 1000.0 / T_hi, 1000.0 / T_lo  # 高 T -> 小 1000/T
        x_seg = x_plot[(x_plot >= inv_T_lo) & (x_plot <= inv_T_hi)]
        if len(x_seg) < 2:
            x_seg = np.linspace(inv_T_lo, inv_T_hi, 50)
        # ln(σ) = ln_sigma0 - Ea/(kB*T) => ln(σ) = ln_sigma0 - (Ea/(kB*1000)) * (1000/T)
        ln_sigma_fit = ln_sigma0 - (Ea / (kB_eV * 1000.0)) * x_seg
        log_sigma_fit = ln_sigma_to_log10_mS_cm(ln_sigma_fit)
        # 图例标签包含 R² 值
        ax1.plot(x_seg, log_sigma_fit, color=colors_seg[idx], linewidth=2.2, zorder=2, 
                label=f'Segment {idx+1} $R^2$={r_squared:.3f}')
        
        # Ea 标注：放在每段中间位置
        x_label = inv_T_lo + (inv_T_hi - inv_T_lo) * 0.5  # 中间位置
        y_label = ln_sigma_to_log10_mS_cm(ln_sigma0 - (Ea / (kB_eV * 1000.0)) * x_label)
        
        # 标注文本：只显示 Ea
        text_str = f'$E_a$ = {Ea:.2f} eV'
        bbox_props = dict(boxstyle='round,pad=0.35', facecolor='white', edgecolor=colors_seg[idx], 
                         linewidth=1.3, alpha=0.92)
        ax1.text(x_label, y_label, text_str, fontsize=7.5, ha='center', va='bottom',
                 color=colors_seg[idx], fontweight='bold', bbox=bbox_props, zorder=5)

    # 变化点垂直虚线 - 灰色虚线（参考图风格）
    for bp in breakpoints_inv_T:
        ax1.axvline(x=bp, color='#808080', linestyle='--', linewidth=1.2, zorder=1, alpha=0.7)

    # 坐标轴设置 - 参考图风格
    ax1.set_xlabel('1000/$T$ (K$^{-1}$)', fontsize=10, fontweight='normal')
    ax1.set_ylabel('log σ (mS·cm$^{-1}$)', fontsize=10, fontweight='normal')  # 简化标签
    
    # 设置横坐标范围：3 到 5.5，每 0.5 一个单位
    ax1.set_xlim(3.0, 5.5)
    y_margin = 0.15 * (log_sigma.max() - log_sigma.min())
    ax1.set_ylim(log_sigma.min() - y_margin, log_sigma.max() + y_margin + 0.5)  # 上方多留空间给Ea标注
    
    # 设置下横轴刻度：3.0, 3.5, 4.0, 4.5, 5.0, 5.5
    x_ticks_bottom = np.arange(3.0, 5.51, 0.5)
    ax1.set_xticks(x_ticks_bottom)
    ax1.tick_params(axis='x', labelsize=9)
    
    # 网格线 - 参考图风格（浅灰色虚线）
    ax1.grid(True, linestyle=':', alpha=0.4, linewidth=0.8, color='gray')
    
    # 图例 - 左下角，包含 Data 和各段的 R² 值
    ax1.legend(loc='lower left', frameon=True, framealpha=0.95, fontsize=7.5, edgecolor='gray')

    # 上横轴: T (°C) - 参考图风格
    ax2 = ax1.twiny()
    ax2.set_xlim(ax1.get_xlim())
    # 设置合理的刻度（与下横轴对应）
    T_K_ticks = 1000.0 / x_ticks_bottom
    T_C_ticks = T_K_ticks - 273.15
    ax2.set_xticks(x_ticks_bottom)
    ax2.set_xticklabels([f'{t:.0f}' for t in T_C_ticks], fontsize=9)
    ax2.set_xlabel('$T$ (°C)', fontsize=10, fontweight='normal')
    ax2.tick_params(axis='x', labelsize=9)

    plt.tight_layout()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # 保存图像 (300 dpi 满足 AM 要求)
    fig.savefig(OUT_DIR / f"figure1_arrhenius_{sample_id}.png", dpi=300, bbox_inches='tight')
    fig.savefig(OUT_DIR / f"figure1_arrhenius_{sample_id}.pdf", bbox_inches='tight')
    plt.close(fig)

    # 导出 CSV：供 Origin 等使用
    import csv
    csv_path = OUT_DIR / f"figure1_arrhenius_{sample_id}_data.csv"
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['1000_T_K_inv', 'T_K', 'T_C', 'sigma_S_cm', 'log10_sigma_mS_cm'])
        for i in range(len(inv_T)):
            w.writerow([round(inv_T[i], 6), round(temperatures_K[i], 4), round(T_C[i], 2),
                        conductivity_S_cm[i], round(log_sigma[i], 6)])
        w.writerow([])
        w.writerow(['segment', 'Ea_eV', 'ln_sigma0', 'T_range_K_low', 'T_range_K_high', 'r_squared'])
        for seg in segments:
            tr = seg.get("temp_range_K") or seg.get("T_range") or [None, None]
            w.writerow([seg.get('segment', ''), seg['Ea_eV'], seg['ln_sigma0'], tr[0], tr[1], seg.get('r_squared', '')])
        w.writerow([])
        w.writerow(['breakpoints_1000_T_K_inv'])
        for bp in breakpoints_inv_T:
            w.writerow([round(bp, 6)])

    print(f"Figure 1 saved: {OUT_DIR / f'figure1_arrhenius_{sample_id}.png'}, PDF, and {csv_path.name}")


if __name__ == "__main__":
    main()
