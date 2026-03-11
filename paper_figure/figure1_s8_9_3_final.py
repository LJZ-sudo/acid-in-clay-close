# -*- coding: utf-8 -*-
"""
Figure 1: S8-3-9-3 (4 segments)
完全复制 S8-3-2-1 的绘图逻辑，只改数据源
"""
from pathlib import Path
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# 样品信息
SAMPLE_ID = "S8-3-9-3"
RESULTS_DIR = Path(__file__).resolve().parent.parent / "output" / "phase1_results"
OUT_DIR = Path(__file__).resolve().parent

# AM 期刊风格（与 S8-3-2-1 完全相同）
AM_RC = {
    'font.family': 'sans-serif',
    'font.sans-serif': ['Arial', 'Helvetica', 'DejaVu Sans'],
    'font.size': 10,
    'axes.labelsize': 10,
    'axes.titlesize': 11,
    'xtick.labelsize': 9,
    'ytick.labelsize': 9,
    'legend.fontsize': 7.5,
    'axes.linewidth': 1.0,
}

kB_eV = 8.617e-5

def sigma_S_cm_to_log10_mS_cm(sigma_S_cm):
    return np.log10(sigma_S_cm * 1000.0)

def ln_sigma_to_log10_mS_cm(ln_sigma):
    return ln_sigma / np.log(10)

# 读取数据
json_path = RESULTS_DIR / f"{SAMPLE_ID}_analysis_result.json"
with open(json_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

temperatures_K = np.array(data['temperatures'])
conductivity_S_cm = np.array(data['conductivity_values'])
segments = data["arrhenius"]["segments"]

print(f"Sample: {SAMPLE_ID}")
print(f"Data points: {len(temperatures_K)}")
print(f"Segments: {len(segments)}\n")

# 提取分段信息
new_segments = []
for i, seg in enumerate(segments):
    new_segments.append({
        "segment": i + 1,
        "Ea_eV": seg["Ea_eV"],
        "ln_sigma0": seg["ln_sigma0"],
        "temp_range_K": seg["temp_range_K"],
        "r_squared": seg["r_squared"]
    })
    tr = seg["temp_range_K"]
    print(f"Seg {i+1}: {tr[0]:.2f}-{tr[1]:.2f} K, Ea={seg['Ea_eV']:.3f} eV, R2={seg['r_squared']:.3f}")

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

# 绘图（与 S8-3-2-1 完全相同）
plt.rcParams.update(AM_RC)
fig, ax1 = plt.subplots(figsize=(5.2, 4.0))

# 数据点
ax1.scatter(inv_T, log_sigma, color='#2c3e50', s=32, zorder=2, 
            edgecolors='white', linewidths=0.5, label='Data', alpha=0.5)

# 配色（4 段需要 4 种颜色）
colors_seg = ['#E91E63', '#4CAF50', '#FF9800', '#9C27B0']

# 绘制拟合线（与 S8-3-2-1 完全相同的方式）
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
    
    # Ea 标注
    x_label = inv_T_lo + (inv_T_hi - inv_T_lo) * 0.5
    y_label = ln_sigma_to_log10_mS_cm(ln_sigma0 - (Ea / (kB_eV * 1000.0)) * x_label)
    
    # 向下偏移
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

# 坐标轴（自动范围，确保显示所有数据）
ax1.set_xlabel('1000/$T$ (K$^{-1}$)', fontsize=10, fontweight='normal')
ax1.set_ylabel('log σ (mS·cm$^{-1}$)', fontsize=10, fontweight='normal')

# 自动计算 X 轴范围，右边增加余量
x_min = np.floor(inv_T.min() * 2) / 2  # 向下取整到 0.5
x_max = np.ceil(inv_T.max() * 2) / 2 + 0.5  # 向上取整到 0.5，再加0.5余量
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
print(f"\nX-axis range: {x_min:.1f} - {x_max:.1f}")
print(f"All {len(temperatures_K)} data points displayed")
