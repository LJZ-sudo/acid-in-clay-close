# -*- coding: utf-8 -*-
"""
合并 S8-3-2-1 的 segment 1 和 2，重新拟合为三段
原来4段 → 合并后3段
"""
from pathlib import Path
import json
import numpy as np
from scipy import stats
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# 常量
CLOSE_ROOT = Path(__file__).resolve().parent.parent
PHASE1_DIR = CLOSE_ROOT / "output" / "phase1_results"
OUT_DIR = CLOSE_ROOT / "paper_figure"
kB_eV = 8.617333e-5  # eV/K

# AM 期刊风格
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


def sigma_S_cm_to_log10_mS_cm(sigma_S_cm: float) -> float:
    """σ (S/cm) -> log₁₀(σ / mS·cm⁻¹)."""
    if sigma_S_cm <= 0:
        return np.nan
    return np.log10(sigma_S_cm * 1000.0)


def ln_sigma_to_log10_mS_cm(ln_sigma: float) -> float:
    """ln(σ) with σ in S/cm -> log₁₀(σ / mS·cm⁻¹)."""
    return (ln_sigma + np.log(1000)) / np.log(10)


def fit_arrhenius(temperatures_K, conductivity_S_cm):
    """
    拟合 Arrhenius: ln(σ) = ln(σ0) - Ea/(kB*T)
    返回 Ea (eV), ln_sigma0, r_squared
    """
    # 过滤有效数据
    valid = (temperatures_K > 0) & (conductivity_S_cm > 0)
    T = temperatures_K[valid]
    sigma = conductivity_S_cm[valid]
    
    if len(T) < 3:
        return None, None, 0.0
    
    # X = 1/T, Y = ln(σ)
    X = 1.0 / T
    Y = np.log(sigma)
    
    # 线性拟合
    slope, intercept, r_value, p_value, std_err = stats.linregress(X, Y)
    
    # slope = -Ea/kB
    Ea_eV = -slope * kB_eV
    ln_sigma0 = intercept
    r_squared = r_value ** 2
    
    return Ea_eV, ln_sigma0, r_squared


def main():
    # 读取原始数据
    sample_id = "S8-3-2-1"
    data_file = PHASE1_DIR / f"{sample_id}_analysis_result.json"
    
    with open(data_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    temperatures_K = np.array(data["temperatures"], dtype=float)
    conductivity_S_cm = np.array(data["conductivity_values"], dtype=float)
    
    # 删除最后一个异常点（186.55 K 附近，inv_T ≈ 5.36）
    # 这个点明显偏离趋势
    if len(temperatures_K) > 0 and temperatures_K[-1] < 187:
        temperatures_K = temperatures_K[:-1]
        conductivity_S_cm = conductivity_S_cm[:-1]
        print(f"Removed last outlier point (T < 187 K)")
    
    # 原始分段信息
    orig_segments = data["arrhenius"]["segments"]
    print("Original segments:")
    for i, s in enumerate(orig_segments):
        tr = s["temp_range_K"]
        print(f"  Seg {i+1}: {tr[0]:.2f}-{tr[1]:.2f} K, Ea={s['Ea_eV']:.3f} eV, R2={s['r_squared']:.3f}")
    
    # 定义新的三段温度范围
    # 新段1：合并原段1和段2 (260.85-300.00 K)
    # 新段2：原段3 (230.35-258.07 K)
    # 新段3：原段4 (192.15-227.15 K)
    
    new_segment_ranges = [
        (260.85, 300.00),   # 合并段1和段2
        (230.35, 258.07),   # 原段3
        (192.15, 227.15),   # 原段4
    ]
    
    # 重新拟合每段
    new_segments = []
    print("\nNew merged segments:")
    
    for i, (T_low, T_high) in enumerate(new_segment_ranges):
        # 筛选该温度范围的数据点
        mask = (temperatures_K >= T_low) & (temperatures_K <= T_high)
        T_seg = temperatures_K[mask]
        sigma_seg = conductivity_S_cm[mask]
        
        # 拟合
        Ea, ln_sigma0, r2 = fit_arrhenius(T_seg, sigma_seg)
        
        new_segments.append({
            "segment": i + 1,
            "Ea_eV": Ea,
            "ln_sigma0": ln_sigma0,
            "temp_range_K": [T_low, T_high],
            "r_squared": r2,
            "n_points": len(T_seg)
        })
        
        print(f"  Seg {i+1}: {T_low:.2f}-{T_high:.2f} K, Ea={Ea:.4f} eV, R2={r2:.4f}, n={len(T_seg)}")
    
    # 计算边界点
    breakpoints_inv_T = []
    for i in range(len(new_segments) - 1):
        T_bound = new_segments[i + 1]["temp_range_K"][1]  # 下一段的高温端
        breakpoints_inv_T.append(1000.0 / T_bound)
    
    # 准备绘图数据
    inv_T = 1000.0 / temperatures_K
    T_C = temperatures_K - 273.15
    log_sigma = np.array([sigma_S_cm_to_log10_mS_cm(s) for s in conductivity_S_cm])
    
    # 排序
    order = np.argsort(inv_T)
    inv_T = inv_T[order]
    T_C = T_C[order]
    log_sigma = log_sigma[order]
    temperatures_K = temperatures_K[order]
    conductivity_S_cm = conductivity_S_cm[order]
    
    # 绘图
    plt.rcParams.update(AM_RC)
    fig, ax1 = plt.subplots(figsize=(5.2, 4.0))
    
    # 数据点 - 增加透明度，让拟合线颜色清晰可见
    ax1.scatter(inv_T, log_sigma, color='#2c3e50', s=32, zorder=2, 
                edgecolors='white', linewidths=0.5, label='Data', alpha=0.5)
    
    # 配色
    colors_seg = ['#E91E63', '#4CAF50', '#FF9800']
    
    # 绘制拟合线
    x_plot = np.linspace(inv_T.min(), inv_T.max(), 200)
    
    for idx, seg in enumerate(new_segments):
        Ea = seg["Ea_eV"]
        ln_sigma0 = seg["ln_sigma0"]
        r_squared = seg["r_squared"]
        T_lo, T_hi = seg["temp_range_K"]
        inv_T_lo, inv_T_hi = 1000.0 / T_hi, 1000.0 / T_lo
        
        x_seg = x_plot[(x_plot >= inv_T_lo) & (x_plot <= inv_T_hi)]
        if len(x_seg) < 2:
            x_seg = np.linspace(inv_T_lo, inv_T_hi, 50)
        
        ln_sigma_fit = ln_sigma0 - (Ea / (kB_eV * 1000.0)) * x_seg
        log_sigma_fit = ln_sigma_to_log10_mS_cm(ln_sigma_fit)
        
        ax1.plot(x_seg, log_sigma_fit, color=colors_seg[idx], linewidth=2.5, zorder=3, 
                label=f'Segment {idx+1} $R^2$={r_squared:.3f}')
        
        # Ea 标注 - 放在拟合线下方，避免挡住线
        x_label = inv_T_lo + (inv_T_hi - inv_T_lo) * 0.5
        y_label = ln_sigma_to_log10_mS_cm(ln_sigma0 - (Ea / (kB_eV * 1000.0)) * x_label)
        
        # 向下偏移，放在线的下方
        y_offset = -0.35 * (log_sigma.max() - log_sigma.min())
        y_text = y_label + y_offset
        
        text_str = f'$E_a$ = {Ea:.2f} eV'
        bbox_props = dict(boxstyle='round,pad=0.35', facecolor='white', 
                         edgecolor=colors_seg[idx], linewidth=1.3, alpha=0.92)
        ax1.text(x_label, y_text, text_str, fontsize=7.5, ha='center', va='top',
                color=colors_seg[idx], fontweight='bold', bbox=bbox_props, zorder=5)
    
    # 边界虚线
    for bp in breakpoints_inv_T:
        ax1.axvline(x=bp, color='#808080', linestyle='--', linewidth=1.2, zorder=1, alpha=0.7)
    
    # 坐标轴
    ax1.set_xlabel('1000/$T$ (K$^{-1}$)', fontsize=10, fontweight='normal')
    ax1.set_ylabel('log σ (mS·cm$^{-1}$)', fontsize=10, fontweight='normal')
    ax1.set_xlim(3.0, 5.5)
    y_margin = 0.15 * (log_sigma.max() - log_sigma.min())
    ax1.set_ylim(log_sigma.min() - y_margin, log_sigma.max() + y_margin + 0.5)
    
    x_ticks_bottom = np.arange(3.0, 5.51, 0.5)
    ax1.set_xticks(x_ticks_bottom)
    ax1.tick_params(axis='x', labelsize=9)
    ax1.grid(True, linestyle=':', alpha=0.4, linewidth=0.8, color='gray')
    ax1.legend(loc='lower left', frameon=True, framealpha=0.95, fontsize=7.5, edgecolor='gray')
    
    # 上横轴
    ax2 = ax1.twiny()
    ax2.set_xlim(ax1.get_xlim())
    T_K_ticks = 1000.0 / x_ticks_bottom
    T_C_ticks = T_K_ticks - 273.15
    ax2.set_xticks(x_ticks_bottom)
    ax2.set_xticklabels([f'{t:.0f}' for t in T_C_ticks], fontsize=9)
    ax2.set_xlabel('$T$ (°C)', fontsize=10, fontweight='normal')
    ax2.tick_params(axis='x', labelsize=9)
    
    plt.tight_layout()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # 保存图像
    fig.savefig(OUT_DIR / f"figure1_arrhenius_{sample_id}_3segments.png", dpi=300, bbox_inches='tight')
    fig.savefig(OUT_DIR / f"figure1_arrhenius_{sample_id}_3segments.pdf", bbox_inches='tight')
    plt.close(fig)
    
    # 导出 CSV
    import csv
    csv_path = OUT_DIR / f"figure1_arrhenius_{sample_id}_3segments_data.csv"
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['1000_T_K_inv', 'T_K', 'T_C', 'sigma_S_cm', 'log10_sigma_mS_cm'])
        for i in range(len(inv_T)):
            w.writerow([round(inv_T[i], 6), round(temperatures_K[i], 4), round(T_C[i], 2),
                       conductivity_S_cm[i], round(log_sigma[i], 6)])
        w.writerow([])
        w.writerow(['segment', 'Ea_eV', 'ln_sigma0', 'T_range_K_low', 'T_range_K_high', 'r_squared', 'n_points'])
        for seg in new_segments:
            tr = seg["temp_range_K"]
            w.writerow([seg["segment"], seg["Ea_eV"], seg["ln_sigma0"], 
                       tr[0], tr[1], seg["r_squared"], seg["n_points"]])
        w.writerow([])
        w.writerow(['breakpoints_1000_T_K_inv'])
        for bp in breakpoints_inv_T:
            w.writerow([round(bp, 6)])
    
    print(f"\nFigure saved: {OUT_DIR / f'figure1_arrhenius_{sample_id}_3segments.png'}")
    print(f"CSV saved: {csv_path}")
    print("\nMerge complete! Segment 1 and 2 combined into new Segment 1.")


if __name__ == "__main__":
    main()
