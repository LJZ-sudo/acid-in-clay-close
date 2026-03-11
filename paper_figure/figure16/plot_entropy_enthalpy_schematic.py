# -*- coding: utf-8 -*-
"""
Figure 16: 熵-焓补偿示意图（Meyer-Neldel 物理含义）

展示 Meyer-Neldel 补偿规律的物理本质：
- 熵-焓补偿关系示意
- 自由能等势线
- Iso-kinetic temperature 概念
- S8 vs S60 对比

这是一个概念示意图，不是数据图
"""

import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch
from matplotlib.lines import Line2D

# 显式路径配置，便于 standalone 使用
SCRIPT_DIR = Path(__file__).resolve().parent
PAPER_FIG_DIR = SCRIPT_DIR.parent
if str(PAPER_FIG_DIR) not in sys.path:
    sys.path.insert(0, str(PAPER_FIG_DIR))
from am_style_config import (
    setup_am_style, COLORS, save_figure, add_panel_label
)

# 物理常数
k_B = 8.617333262e-5  # eV/K

# 路径配置
OUT_DIR = SCRIPT_DIR


def plot_figure16():
    """绘制 Figure 16: 熵-焓补偿示意图"""
    
    print("=" * 60)
    print("Figure 16: Entropy-Enthalpy Compensation Schematic")
    print("=" * 60)
    
    setup_am_style()
    
    # 创建图形 (1x2 布局)
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.5))
    
    # ==================== Panel (a): 熵-焓补偿示意 ====================
    ax1 = axes[0]
    
    # 设定参数
    # Meyer-Neldel: ΔS = ΔH / T_MN
    # 其中 Ea ≈ ΔH (活化焓), ln(σ0) ∝ ΔS (活化熵)
    
    # T_MN 参考值 (从数据估算)
    T_MN_s8 = 230  # K
    T_MN_s60 = 240  # K
    
    # 生成示意数据
    Ea_range = np.linspace(0.1, 1.0, 50)  # eV
    
    # ln(σ0) = ln(σ00) + Ea/E_MN, 其中 E_MN = k_B * T_MN
    E_MN_s8 = k_B * T_MN_s8
    E_MN_s60 = k_B * T_MN_s60
    
    ln_sigma0_s8 = -5 + Ea_range / E_MN_s8
    ln_sigma0_s60 = -4 + Ea_range / E_MN_s60
    
    # 绘制补偿线
    ax1.plot(Ea_range, ln_sigma0_s8, '-', color=COLORS['S8'], linewidth=2.5,
             label=f'S8 (Confined)\n$T_{{MN}}$ ≈ {T_MN_s8} K')
    ax1.plot(Ea_range, ln_sigma0_s60, '-', color=COLORS['S60'], linewidth=2.5,
             label=f'S60 (Bulk)\n$T_{{MN}}$ ≈ {T_MN_s60} K')
    
    # 添加散点示意
    np.random.seed(42)
    n_points = 15
    Ea_s8_pts = np.random.uniform(0.15, 0.9, n_points)
    Ea_s60_pts = np.random.uniform(0.15, 0.7, n_points)
    
    ln_sigma0_s8_pts = -5 + Ea_s8_pts / E_MN_s8 + np.random.normal(0, 1.5, n_points)
    ln_sigma0_s60_pts = -4 + Ea_s60_pts / E_MN_s60 + np.random.normal(0, 1.2, n_points)
    
    ax1.scatter(Ea_s8_pts, ln_sigma0_s8_pts, c=COLORS['S8'], alpha=0.5, s=40,
               edgecolors='white', linewidths=0.5)
    ax1.scatter(Ea_s60_pts, ln_sigma0_s60_pts, c=COLORS['S60'], alpha=0.5, s=40,
               edgecolors='white', linewidths=0.5)
    
    ax1.set_xlabel('$E_a$ (Activation Energy, eV)', fontsize=11)
    ax1.set_ylabel('ln($\\sigma_0$) (Pre-exponential Factor)', fontsize=11)
    ax1.set_title('Meyer-Neldel Compensation Effect', fontsize=12, fontweight='bold')
    ax1.legend(loc='lower right', fontsize=9)
    ax1.grid(True, alpha=0.35)
    
    # 物理解释注释
    explanation1 = (
        'Meyer-Neldel Rule:\n'
        'ln(σ₀) = ln(σ₀₀) + $E_a$/$E_{MN}$\n'
        '\n'
        'Physical meaning:\n'
        'Higher barrier → Higher attempt rate\n'
        '(Entropy-Enthalpy compensation)'
    )
    ax1.text(0.02, 0.98, explanation1, transform=ax1.transAxes,
             fontsize=9, verticalalignment='top',
             bbox=dict(boxstyle='round,pad=0.5', facecolor='#ECEFF1',
                      edgecolor='#607D8B', alpha=0.95))
    
    add_panel_label(ax1, 'a')
    
    # ==================== Panel (b): 自由能图示 ====================
    ax2 = axes[1]
    
    # 反应坐标示意
    x = np.linspace(0, 10, 200)
    
    # 自由能曲线 (反应物 → 过渡态 → 产物)
    def free_energy_curve(x, Ea, offset=0):
        """双势阱模型"""
        # 高斯形状的过渡态
        barrier = Ea * np.exp(-0.5 * ((x - 5) / 1.5)**2)
        # 初态和终态
        initial = 0.5 * (1 - np.tanh((x - 2) / 0.5))
        final = 0.5 * (1 + np.tanh((x - 8) / 0.5))
        return barrier + 0.1 * initial - 0.1 * final + offset
    
    # 不同温度下的自由能曲线
    temps = [200, 250, 300]
    temp_colors = [COLORS['low_temp'], COLORS['mid_temp'], COLORS['high_temp']]
    
    for T, color in zip(temps, temp_colors):
        # G = H - TS, 温度越高，熵贡献越大
        # 由于 MN 补偿，高 Ea 对应高 σ0 (高熵)
        Ea_eff = 0.5 * (1 - 0.002 * (T - 250))  # 温度效应
        G = free_energy_curve(x, Ea_eff)
        ax2.plot(x, G + (T - 250) * 0.003, '-', color=color, linewidth=2,
                 label=f'T = {T} K', alpha=0.8)
    
    # 等温动力学线 (iso-kinetic)
    # 在 T_MN 处，所有反应速率相同
    ax2.axhline(0.4, color=COLORS['reference'], linestyle='--', linewidth=1.5,
               label=f'Iso-kinetic line\n($T$ = $T_{{MN}}$)', alpha=0.7)
    
    # 标注
    ax2.annotate('Transition\nState', xy=(5, 0.55), fontsize=9, ha='center',
                 color='#455A64')
    ax2.annotate('', xy=(5, 0.5), xytext=(5, 0.2),
                arrowprops=dict(arrowstyle='->', color='#455A64', lw=1.5))
    ax2.text(5, 0.15, '$E_a$', fontsize=10, ha='center', color='#455A64')
    
    ax2.annotate('Reactant', xy=(1.5, 0.1), fontsize=9, ha='center', color='#607D8B')
    ax2.annotate('Product', xy=(8.5, 0.05), fontsize=9, ha='center', color='#607D8B')
    
    ax2.set_xlabel('Reaction Coordinate', fontsize=11)
    ax2.set_ylabel('Free Energy $G$ = $H$ - $TS$', fontsize=11)
    ax2.set_title('Temperature-Dependent Free Energy Landscape', fontsize=12, fontweight='bold')
    ax2.legend(loc='upper right', fontsize=9)
    ax2.set_xlim(0, 10)
    ax2.set_ylim(-0.1, 0.8)
    ax2.set_xticks([])  # 隐藏x轴刻度（概念图）
    ax2.grid(True, alpha=0.35, axis='y')
    
    # 补偿效应物理解释
    explanation2 = (
        'At $T$ = $T_{MN}$:\n'
        'ΔG = $E_a$ - $T_{MN}$Δ$S^‡$ ≈ const\n'
        '\n'
        '→ All reactions have\n'
        '   same rate at $T_{MN}$'
    )
    ax2.text(0.02, 0.55, explanation2, transform=ax2.transAxes,
             fontsize=9, verticalalignment='top',
             bbox=dict(boxstyle='round,pad=0.5', facecolor='#FFF9C4',
                      edgecolor='#FBC02D', alpha=0.95))
    
    add_panel_label(ax2, 'b')
    
    plt.tight_layout()
    
    # 保存
    save_figure(fig, str(OUT_DIR / 'figure16_entropy_enthalpy_schematic'))
    plt.close(fig)
    
    # 创建说明文档
    readme_content = """# Figure 16: Entropy-Enthalpy Compensation Schematic

## 概述

本图展示 Meyer-Neldel 补偿规律的物理本质，属于概念示意图。

## Panel (a): Meyer-Neldel 补偿效应

**核心公式**：
```
ln(σ₀) = ln(σ₀₀) + Ea / E_MN
```

其中：
- σ₀: 预指数因子 (pre-exponential factor)
- Ea: 活化能 (activation energy)
- E_MN = k_B × T_MN: Meyer-Neldel 能量
- T_MN: Meyer-Neldel 温度 (iso-kinetic temperature)

**物理意义**：
- 高活化能 → 高预指数因子
- 这是熵-焓补偿的体现：更高的能量壁垒伴随更多的构型熵

## Panel (b): 自由能景观

展示不同温度下的自由能曲线：
- G = H - TS
- 温度越高，熵贡献 (-TS) 越大
- 在 T = T_MN 处，所有反应的自由能壁垒趋于相等

## 科学意义

1. **统一动力学**：不同温区、不同机制的传导过程遵循统一的补偿规律

2. **材料对比**：
   - S8 (限域): T_MN ≈ 230 K
   - S60 (本体): T_MN ≈ 240 K
   - 限域效应可能改变补偿温度

3. **传导机制**：
   - T < T_MN: Ea 主导，低温区
   - T > T_MN: σ₀ 主导，高温区

## 参考文献

1. Meyer, W.; Neldel, H. Z. Tech. Phys. 1937, 18, 588.
2. Yelon, A.; Movaghar, B. Phys. Rev. Lett. 1990, 65, 618.

---
生成时间: 2026-02-03
"""
    
    with open(OUT_DIR / 'README.md', 'w', encoding='utf-8') as f:
        f.write(readme_content)
    
    print(f'\nFiles saved:')
    print(f'  {OUT_DIR / "figure16_entropy_enthalpy_schematic.png"}')
    print(f'  {OUT_DIR / "figure16_entropy_enthalpy_schematic.pdf"}')
    print(f'  {OUT_DIR / "README.md"}')
    
    print(f'\n[Figure 16 完成]')


if __name__ == '__main__':
    plot_figure16()
