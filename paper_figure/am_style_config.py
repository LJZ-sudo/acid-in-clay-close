# -*- coding: utf-8 -*-
"""
Advanced Materials (AM) 期刊绘图风格配置
统一的颜色方案和字体设置

配色参考:
- 主色调：采用高对比度、印刷友好的配色
- S8 (Sepiolite/凹凸棒石): 粉红色系 #E91E63
- S60 (Montmorillonite/蒙脱石): 蓝色系 #2196F3
"""

import sys
import io

# 修复 Windows 控制台编码问题
if sys.platform == 'win32':
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass

import matplotlib.pyplot as plt
import matplotlib as mpl

# =============================================================================
# AM 期刊标准颜色方案
# =============================================================================

# 材料颜色 (Material Colors)
COLORS = {
    # 主材料颜色
    'S8': '#E91E63',        # 粉红色 (Pink) - Sepiolite
    'S60': '#2196F3',       # 蓝色 (Blue) - Montmorillonite
    
    # Segment 颜色 (与 Figure 1 保持一致)
    'segment1': '#E91E63',  # 粉红 (高温段)
    'segment2': '#4CAF50',  # 绿色 (次高温)
    'segment3': '#FF9800',  # 橙色 (次低温)
    'segment4': '#9C27B0',  # 紫色 (低温段)
    
    # 温区颜色
    'high_temp': '#E53935',    # 红色 (高温 >270K)
    'mid_temp': '#43A047',     # 绿色 (中温 230-270K)
    'low_temp': '#1E88E5',     # 蓝色 (低温 <230K)
    
    # 辅助颜色
    'fit_line': '#D32F2F',     # 拟合线 (深红)
    'ci_fill': '#BBDEFB',      # 置信区间填充 (浅蓝)
    'ci_fill_pink': '#F8BBD0', # 置信区间填充 (浅粉)
    'grid': '#9E9E9E',         # 网格线 (灰色)
    'reference': '#757575',    # 参考线 (深灰)
    'data_point': '#2C3E50',   # 数据点 (深灰蓝)
    
    # 梯度色 (用于SHAP等)
    'gradient_pos': '#D32F2F',  # 正向影响 (红)
    'gradient_neg': '#1976D2',  # 负向影响 (蓝)
    
    # 对比色
    'observed': '#2C3E50',      # 观测值 (深灰)
    'predicted': '#E91E63',     # 预测值 (粉红)
    
    # Meyer-Neldel 分析颜色
    'mn_s8': '#E91E63',
    'mn_s60': '#2196F3',
    'mn_s8_high': '#F48FB1',   # S8 高温 (浅粉)
    'mn_s8_low': '#AD1457',    # S8 低温 (深粉)
}

# =============================================================================
# AM 期刊字体和尺寸标准
# =============================================================================

# RC 参数配置
AM_RCPARAMS = {
    # 字体
    'font.family': 'sans-serif',
    'font.sans-serif': ['Arial', 'Helvetica', 'DejaVu Sans'],
    'font.size': 10,
    
    # 坐标轴
    'axes.labelsize': 11,
    'axes.titlesize': 12,
    'axes.titleweight': 'bold',
    'axes.linewidth': 1.2,
    'axes.labelweight': 'normal',
    
    # 刻度
    'xtick.labelsize': 10,
    'ytick.labelsize': 10,
    'xtick.direction': 'in',
    'ytick.direction': 'in',
    'xtick.major.width': 1.0,
    'ytick.major.width': 1.0,
    'xtick.major.size': 4,
    'ytick.major.size': 4,
    
    # 图例
    'legend.fontsize': 9,
    'legend.frameon': True,
    'legend.framealpha': 0.9,
    'legend.edgecolor': '#CCCCCC',
    
    # 线条
    'lines.linewidth': 2.0,
    'lines.markersize': 6,
    
    # 网格
    'grid.alpha': 0.35,
    'grid.linewidth': 0.8,
    
    # 保存
    'savefig.dpi': 300,
    'savefig.bbox': 'tight',
    'savefig.pad_inches': 0.1,
    
    # 其他
    'figure.facecolor': 'white',
    'axes.facecolor': 'white',
}

# 图像尺寸标准 (英寸)
FIGURE_SIZES = {
    'single': (5, 4),           # 单面板
    'double_horizontal': (10, 4),  # 双面板横向
    'double_vertical': (5, 8),     # 双面板纵向
    'triple': (12, 4),          # 三面板
    'quad': (10, 8),            # 四面板 (2x2)
    'wide': (8, 4),             # 宽幅单图
    'tall': (5, 6),             # 高图
}

# =============================================================================
# 辅助函数
# =============================================================================

def setup_am_style():
    """设置 AM 期刊样式"""
    plt.rcParams.update(AM_RCPARAMS)


def get_color(key):
    """获取颜色，支持默认值"""
    return COLORS.get(key, '#333333')


def create_figure(size_key='single', **kwargs):
    """创建符合 AM 标准的图形"""
    setup_am_style()
    figsize = FIGURE_SIZES.get(size_key, FIGURE_SIZES['single'])
    fig, ax = plt.subplots(figsize=figsize, **kwargs)
    return fig, ax


def create_figure_subplots(nrows, ncols, size_key='double_horizontal', **kwargs):
    """创建多子图的图形"""
    setup_am_style()
    figsize = FIGURE_SIZES.get(size_key, (5 * ncols, 4 * nrows))
    fig, axes = plt.subplots(nrows, ncols, figsize=figsize, **kwargs)
    return fig, axes


def add_panel_label(ax, label, x=-0.15, y=1.05, fontsize=14, fontweight='bold'):
    """添加面板标签 (a), (b), (c) 等"""
    ax.text(x, y, f'({label})', transform=ax.transAxes,
            fontsize=fontsize, fontweight=fontweight, va='bottom')


def save_figure(fig, path_without_ext, dpi=300):
    """保存图形为 PNG 和 PDF 格式"""
    fig.savefig(f'{path_without_ext}.png', dpi=dpi, bbox_inches='tight')
    fig.savefig(f'{path_without_ext}.pdf', bbox_inches='tight')
    print(f'Saved: {path_without_ext}.png')
    print(f'Saved: {path_without_ext}.pdf')


# =============================================================================
# 统计注释格式化
# =============================================================================

def format_pvalue(p):
    """格式化 p 值"""
    if p < 0.001:
        return 'p < 0.001'
    elif p < 0.01:
        return f'p = {p:.3f}'
    elif p < 0.05:
        return f'p = {p:.3f}'
    else:
        return f'p = {p:.2f}'


def format_r2(r2):
    """格式化 R² 值"""
    return f'R² = {r2:.3f}'


def format_ci(ci_low, ci_high, precision=3):
    """格式化置信区间"""
    return f'95% CI [{ci_low:.{precision}f}, {ci_high:.{precision}f}]'


# =============================================================================
# 颜色映射
# =============================================================================

def get_temperature_cmap():
    """获取温度相关的颜色映射"""
    from matplotlib.colors import LinearSegmentedColormap
    colors = [COLORS['low_temp'], COLORS['mid_temp'], COLORS['high_temp']]
    return LinearSegmentedColormap.from_list('temp_cmap', colors)


def get_diverging_cmap():
    """获取发散型颜色映射 (用于 SHAP 等)"""
    from matplotlib.colors import LinearSegmentedColormap
    colors = [COLORS['gradient_neg'], '#FFFFFF', COLORS['gradient_pos']]
    return LinearSegmentedColormap.from_list('diverging_cmap', colors)


if __name__ == '__main__':
    # 测试颜色显示
    import numpy as np
    
    setup_am_style()
    fig, ax = plt.subplots(figsize=(8, 6))
    
    # 显示所有颜色
    y = 0
    for name, color in COLORS.items():
        ax.barh(y, 1, color=color, edgecolor='black', linewidth=0.5)
        ax.text(1.1, y, f'{name}: {color}', va='center', fontsize=9)
        y += 1
    
    ax.set_xlim(0, 2.5)
    ax.set_ylim(-0.5, y - 0.5)
    ax.set_yticks([])
    ax.set_title('AM Style Color Palette', fontweight='bold')
    ax.set_xlabel('Color')
    
    plt.tight_layout()
    plt.savefig('am_color_palette_test.png', dpi=150)
    print('Color palette saved to am_color_palette_test.png')
