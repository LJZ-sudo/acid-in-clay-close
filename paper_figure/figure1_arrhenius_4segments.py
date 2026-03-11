# -*- coding: utf-8 -*-
"""
Figure 1: 典型 S8 样品 4 段 Arrhenius 图 (AM 期刊风格)
展示主流的 4 段行为（对应 3 个变化点）
"""
from pathlib import Path
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd

# 路径设置
SAMPLE_ID = "S8-3-9-3"  # 4-segment sample with lower Ea values
RESULTS_DIR = Path(__file__).resolve().parent.parent / "output" / "phase1_results"
OUT_DIR = Path(__file__).resolve().parent

# AM 期刊风格（与 Figure 2/3 一致）
AM_RC = {
    'font.family': 'sans-serif',
    'font.sans-serif': ['Arial', 'Helvetica', 'DejaVu Sans'],
    'font.size': 10,
    'axes.labelsize': 12,
    'axes.titlesize': 13,
    'xtick.labelsize': 11,
    'ytick.labelsize': 10,
    'legend.fontsize': 10,
    'axes.linewidth': 1.2,
}

def main():
    # 读取数据
    json_path = RESULTS_DIR / f"{SAMPLE_ID}_analysis_result.json"
    
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 提取数据
    temperatures_K = np.array(data['temperatures'])
    conductivity_S_cm = np.array(data['conductivity_values'])
    segments = data['arrhenius']['segments']
    
    print(f"Sample: {SAMPLE_ID}")
    print(f"Data points: {len(temperatures_K)}")
    print(f"Temperature range: {temperatures_K.min():.1f} - {temperatures_K.max():.1f} K")
    print(f"Segments: {len(segments)}\n")
    
    # 单位转换
    inv_T = 1000.0 / temperatures_K
    T_C = temperatures_K - 273.15
    conductivity_mS_cm = conductivity_S_cm * 1000.0
    log_sigma = np.log10(conductivity_mS_cm)
    
    # 准备拟合线数据
    fit_data = []
    for idx, seg in enumerate(segments, 1):
        Ea_eV = seg['Ea_eV']
        ln_sigma0 = seg['ln_sigma0']
        T_low, T_high = seg['temp_range_K']
        r_squared = seg['r_squared']
        
        print(f"Segment {idx}: T=[{T_low:.1f}, {T_high:.1f}] K, Ea={Ea_eV:.3f} eV, R2={r_squared:.4f}")
        
        fit_data.append({
            'segment': idx,
            'Ea_eV': Ea_eV,
            'ln_sigma0': ln_sigma0,
            'T_low_K': T_low,
            'T_high_K': T_high,
            'r_squared': r_squared
        })
    
    # 绘图（与 S8-3-2-1 完全相同的风格）
    plt.rcParams.update(AM_RC)
    fig, ax1 = plt.subplots(figsize=(5.2, 4.0))  # 与 S8-3-2-1 相同
    
    # 配色（4 段需要 4 种颜色）
    colors_seg = ['#E91E63', '#4CAF50', '#FF9800', '#9C27B0']  # 粉红、绿色、橙色、紫色
    
    # 数据点 - 与 S8-3-2-1 完全相同的参数
    ax1.scatter(inv_T, log_sigma, color='#2c3e50', s=32, zorder=2,
                edgecolors='white', linewidths=0.5, label='Data', alpha=0.5)
    
    # 绘制拟合线 - 与 S8-3-2-1 完全相同的方法
    # 先生成整个数据范围的 x 轴
    x_plot = np.linspace(inv_T.min(), inv_T.max(), 200)
    breakpoints_x = []
    
    # 先收集所有标签位置，用于检测重叠
    label_positions = []
    y_range = log_sigma.max() - log_sigma.min()
    
    for idx, seg_info in enumerate(fit_data):
        Ea_eV = seg_info['Ea_eV']
        ln_sigma0 = seg_info['ln_sigma0']
        T_low = seg_info['T_low_K']
        T_high = seg_info['T_high_K']
        r_squared = seg_info['r_squared']
        
        # 从整体范围筛选该段的 x 轴 - 与 S8-3-2-1 一致
        inv_T_lo = 1000.0 / T_high
        inv_T_hi = 1000.0 / T_low
        x_seg = x_plot[(x_plot >= inv_T_lo) & (x_plot <= inv_T_hi)]
        if len(x_seg) < 2:
            x_seg = np.linspace(inv_T_lo, inv_T_hi, 50)
        
        # 使用 kB = 8.617e-5 eV/K
        kB_eV = 8.617e-5
        # ln_sigma0 是基于 S/cm 的 ln，需要转换为 mS/cm 的 log10
        # ln(σ_S/cm) -> log10(σ_mS/cm) = [ln(σ_S/cm) + ln(1000)] / ln(10)
        ln_sigma_fit = ln_sigma0 - (Ea_eV / (kB_eV * 1000.0)) * x_seg
        log_sigma_fit = (ln_sigma_fit + np.log(1000)) / np.log(10)
        
        # 绘制拟合线 - 与 S8-3-2-1 相同参数
        ax1.plot(x_seg, log_sigma_fit, color=colors_seg[idx], linewidth=2.5, zorder=3,
                label=f'Segment {idx+1} $R^2$={r_squared:.3f}')
        
        # 标注 Ea（放在每段中间）
        x_label = inv_T_lo + (inv_T_hi - inv_T_lo) * 0.5
        ln_sigma_label = ln_sigma0 - (Ea_eV / (kB_eV * 1000.0)) * x_label
        y_label = (ln_sigma_label + np.log(1000)) / np.log(10)
        
        # 为不同段设置不同的垂直偏移，避免重叠
        # Segment 1: -0.25, Segment 2: -0.35, Segment 3: -0.45, Segment 4: -0.55
        base_offsets = [-0.25, -0.35, -0.45, -0.55]
        y_offset = base_offsets[idx] * y_range if idx < len(base_offsets) else -0.3 * y_range
        y_text = y_label + y_offset
        
        # 确保标签不会超出下边界太多
        y_min_safe = log_sigma.min() - 0.1 * y_range
        if y_text < y_min_safe:
            y_text = y_min_safe + 0.05 * y_range
        
        label_positions.append((x_label, y_text, idx))
        
        # 记录变化点位置
        if idx < len(fit_data) - 1:
            breakpoints_x.append(inv_T_hi)
    
    # 检测并调整重叠的标签
    # 如果两个标签的 x 坐标太接近（< 0.3），调整它们的 y 位置
    for i in range(len(label_positions)):
        for j in range(i + 1, len(label_positions)):
            x1, y1, idx1 = label_positions[i]
            x2, y2, idx2 = label_positions[j]
            if abs(x1 - x2) < 0.3:  # x 坐标太接近
                # 调整 y 位置，让它们错开
                if abs(y1 - y2) < 0.3 * y_range:  # y 坐标也太接近
                    # 让 idx 小的标签在上方，大的在下方
                    if idx1 < idx2:
                        y1_new = y1 - 0.1 * y_range
                        y2_new = y2 + 0.1 * y_range
                    else:
                        y1_new = y1 + 0.1 * y_range
                        y2_new = y2 - 0.1 * y_range
                    label_positions[i] = (x1, y1_new, idx1)
                    label_positions[j] = (x2, y2_new, idx2)
    
    # 绘制所有 Ea 标签
    for x_label, y_text, idx in label_positions:
        seg_info = fit_data[idx]
        Ea_eV = seg_info['Ea_eV']
        text_str = f'$E_a$ = {Ea_eV:.2f} eV'
        bbox_props = dict(boxstyle='round,pad=0.35', facecolor='white', 
                         edgecolor=colors_seg[idx], linewidth=1.3, alpha=0.92)
        
        ax1.text(x_label, y_text, text_str, fontsize=7.5, ha='center', va='top',
                color=colors_seg[idx], fontweight='bold', bbox=bbox_props, zorder=5)
    
    # 绘制边界虚线 - 与 S8-3-2-1 相同
    for bp in breakpoints_x:
        ax1.axvline(x=bp, color='#808080', linestyle='--', linewidth=1.2, zorder=1, alpha=0.7)
    
    # 坐标轴 - 自动适应数据范围
    ax1.set_xlabel('1000/$T$ (K$^{-1}$)', fontsize=10, fontweight='normal')
    ax1.set_ylabel('log σ (mS·cm$^{-1}$)', fontsize=10, fontweight='normal')
    
    # 自动计算 X 轴范围，确保覆盖所有数据
    x_min = np.floor(inv_T.min() * 2) / 2  # 向下取整到 0.5
    x_max = np.ceil(inv_T.max() * 2) / 2   # 向上取整到 0.5
    ax1.set_xlim(x_min, x_max)
    
    # 为 Ea 标签预留更多底部空间
    y_range = log_sigma.max() - log_sigma.min()
    y_margin_top = 0.15 * y_range
    y_margin_bottom = 0.4 * y_range  # 底部留更多空间给 Ea 标签
    ax1.set_ylim(log_sigma.min() - y_margin_bottom, log_sigma.max() + y_margin_top + 0.5)
    
    x_ticks_bottom = np.arange(x_min, x_max + 0.01, 0.5)
    ax1.set_xticks(x_ticks_bottom)
    ax1.tick_params(axis='x', labelsize=9)
    ax1.grid(True, linestyle=':', alpha=0.4, linewidth=0.8, color='gray')
    ax1.legend(loc='lower left', frameon=True, framealpha=0.95, fontsize=7.5, edgecolor='gray')
    
    # 上横轴 - 与 S8-3-2-1 相同
    ax2 = ax1.twiny()
    ax2.set_xlim(ax1.get_xlim())
    T_K_ticks = 1000.0 / x_ticks_bottom
    T_C_ticks = T_K_ticks - 273.15
    ax2.set_xticks(x_ticks_bottom)
    ax2.set_xticklabels([f'{t:.0f}' for t in T_C_ticks], fontsize=9)
    ax2.set_xlabel('$T$ (°C)', fontsize=10, fontweight='normal')
    ax2.tick_params(axis='x', labelsize=9)
    
    plt.tight_layout()
    
    # 保存图像
    png_path = OUT_DIR / f"figure1_arrhenius_{SAMPLE_ID}_4segments.png"
    pdf_path = OUT_DIR / f"figure1_arrhenius_{SAMPLE_ID}_4segments.pdf"
    
    fig.savefig(png_path, dpi=300, bbox_inches='tight')
    fig.savefig(pdf_path, bbox_inches='tight')
    plt.close(fig)
    
    print(f"\nFigure saved:")
    print(f"  {png_path}")
    print(f"  {pdf_path}")
    
    # 保存 CSV 数据
    csv_data = []
    
    # Part 1: 测量数据
    for i in range(len(temperatures_K)):
        csv_data.append({
            '1000_T_K_inv': inv_T[i],
            'T_K': temperatures_K[i],
            'T_C': T_C[i],
            'sigma_S_cm': conductivity_S_cm[i],
            'log10_sigma_mS_cm': log_sigma[i]
        })
    
    df = pd.DataFrame(csv_data)
    
    # Part 2: 拟合参数
    seg_df = pd.DataFrame(fit_data)
    
    # Part 3: 变化点
    breakpoints_df = pd.DataFrame({
        'breakpoint_1000_T_K_inv': breakpoints_x
    })
    
    # 保存到 CSV
    csv_path = OUT_DIR / f"figure1_arrhenius_{SAMPLE_ID}_4segments_data.csv"
    
    with open(csv_path, 'w', encoding='utf-8') as f:
        f.write("# Part 1: Measurement Data\n")
        df.to_csv(f, index=False, float_format='%.6f')
        f.write("\n# Part 2: Arrhenius Fit Parameters\n")
        seg_df.to_csv(f, index=False, float_format='%.6f')
        f.write("\n# Part 3: Breakpoints\n")
        breakpoints_df.to_csv(f, index=False, float_format='%.6f')
    
    print(f"\nData saved to: {csv_path}")
    print(f"\nSummary:")
    print(f"  Sample: {SAMPLE_ID}")
    print(f"  Segments: 4")
    print(f"  Data points: {len(temperatures_K)}")
    print(f"  Breakpoints: {len(breakpoints_x)}")
    print(f"  Ea range: {fit_data[0]['Ea_eV']:.3f} - {fit_data[-1]['Ea_eV']:.3f} eV")

if __name__ == "__main__":
    main()
