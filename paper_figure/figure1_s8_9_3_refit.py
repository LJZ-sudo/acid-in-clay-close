# -*- coding: utf-8 -*-
"""
S8-3-9-3 Figure 1 - 重新拟合所有segment，确保拟合线正确
"""
from pathlib import Path
import json
import numpy as np
from scipy.stats import linregress
import matplotlib.pyplot as plt

SAMPLE_ID = "S8-3-9-3"
RESULTS_DIR = Path(__file__).resolve().parent.parent / "output" / "phase1_results"
OUT_DIR = Path(__file__).resolve().parent

json_path = RESULTS_DIR / f"{SAMPLE_ID}_analysis_result.json"
with open(json_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

temperatures_K = np.array(data['temperatures'])
conductivity_S_cm = np.array(data['conductivity_values'])
segments_json = data["arrhenius"]["segments"]

print(f"Sample: {SAMPLE_ID}")
print(f"Data points: {len(temperatures_K)}")
print(f"Segments: {len(segments_json)}\n")

# 常数
kB_eV = 8.617333e-5

def sigma_S_cm_to_log10_mS_cm(sigma_S_cm):
    return np.log10(sigma_S_cm * 1000)

def ln_sigma_to_log10_mS_cm(ln_sigma):
    return ln_sigma / np.log(10) + np.log10(1000)

# 重新拟合每个segment，使用JSON中的温度范围
refit_segments = []
for i, seg_json in enumerate(segments_json, 1):
    T_lo, T_hi = seg_json["temp_range_K"]
    
    # 提取该段数据
    mask = (temperatures_K >= T_lo) & (temperatures_K <= T_hi)
    T_seg = temperatures_K[mask]
    sigma_seg = conductivity_S_cm[mask]
    
    # 重新拟合
    inv_T_seg = 1000.0 / T_seg
    ln_sigma_seg = np.log(sigma_seg)
    
    slope, intercept, r_value, p_value, std_err = linregress(inv_T_seg, ln_sigma_seg)
    
    Ea_eV = -slope * kB_eV * 1000.0
    ln_sigma0 = intercept
    r_squared = r_value ** 2
    
    refit_segments.append({
        "segment": i,
        "Ea_eV": Ea_eV,
        "ln_sigma0": ln_sigma0,
        "temp_range_K": [T_lo, T_hi],
        "r_squared": r_squared
    })
    
    print(f"Seg {i}: {T_lo:.2f}-{T_hi:.2f} K, Ea={Ea_eV:.3f} eV, R2={r_squared:.3f}")

# 计算边界点
breakpoints_inv_T = []
for i in range(len(refit_segments) - 1):
    T_bound = refit_segments[i + 1]["temp_range_K"][1]
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

# AM期刊风格
AM_RC = {
    'font.family': 'sans-serif',
    'font.sans-serif': ['Arial', 'Helvetica', 'DejaVu Sans'],
    'font.size': 10,
    'axes.labelsize': 10,
    'axes.titlesize': 11,
    'xtick.labelsize': 9,
    'ytick.labelsize': 9,
    'legend.fontsize': 7.5,
    'figure.dpi': 300,
    'savefig.dpi': 300,
    'axes.linewidth': 1.0,
    'xtick.major.width': 1.0,
    'ytick.major.width': 1.0,
}

# 绘图
plt.rcParams.update(AM_RC)
fig, ax1 = plt.subplots(figsize=(5.2, 4.0))

# 数据点
ax1.scatter(inv_T, log_sigma, color='#2c3e50', s=32, zorder=2, 
            edgecolors='white', linewidths=0.5, label='Data', alpha=0.5)

# 配色
colors_seg = ['#E91E63', '#4CAF50', '#FF9800', '#9C27B0']

# 绘制拟合线 - 使用重新拟合的参数
x_plot = np.linspace(inv_T.min(), inv_T.max(), 200)

for idx, seg in enumerate(refit_segments):
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
    
    # Ea标注 - 每段使用不同的y_offset避免重叠
    x_label = inv_T_lo + (inv_T_hi - inv_T_lo) * 0.5
    y_label = ln_sigma_to_log10_mS_cm(ln_sigma0 - (Ea / (kB_eV * 1000.0)) * x_label)
    
    # 不同segment使用不同的偏移量
    y_offsets = [-0.25, -0.45, -0.60, -0.30]  # Seg3(橙色)向下调整，避免与Seg2(绿色)重叠
    y_offset = y_offsets[idx] * (log_sigma.max() - log_sigma.min())
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

x_min = np.floor(inv_T.min() * 2) / 2
x_max = np.ceil(inv_T.max() * 2) / 2 + 0.5
ax1.set_xlim(x_min, x_max)

y_margin = 0.15 * (log_sigma.max() - log_sigma.min())
ax1.set_ylim(log_sigma.min() - y_margin, log_sigma.max() + y_margin + 0.5)

x_ticks_bottom = np.arange(x_min, x_max + 0.01, 0.5)
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

# 保存
fig.savefig(OUT_DIR / f"figure1_arrhenius_{SAMPLE_ID}_4segments.png", dpi=300, bbox_inches='tight')
fig.savefig(OUT_DIR / f"figure1_arrhenius_{SAMPLE_ID}_4segments.pdf", bbox_inches='tight')
plt.close(fig)

print(f"\nFigure saved:")
print(f"  {OUT_DIR / f'figure1_arrhenius_{SAMPLE_ID}_4segments.png'}")
print(f"  {OUT_DIR / f'figure1_arrhenius_{SAMPLE_ID}_4segments.pdf'}")
print(f"\nX-axis range: {x_min} - {x_max}")
print(f"All {len(temperatures_K)} data points displayed")
print("\n使用重新拟合的参数，确保拟合线完全匹配数据点！")
