import numpy as np
import matplotlib.pyplot as plt
import matplotlib
import os

# 全局设置matplotlib支持中文和负号
matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
matplotlib.rcParams['axes.unicode_minus'] = False

def plot_bode_diagram(freq, zreal, zimag, temp, save_path):
    """
    绘制Bode图，包含幅值和相位
    参数:
        freq: 频率数组
        zreal: 阻抗实部
        zimag: 阻抗虚部  
        temp: 温度
        save_path: 保存路径
    """
    try:
        # 计算阻抗幅值和相位
        Z_mag = np.sqrt(zreal**2 + zimag**2)
        Z_phase = np.arctan2(-np.abs(zimag), zreal) * 180 / np.pi  # 转换为度数，取虚部负值
        
        # 创建子图
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8, 6))
        
        # 绘制幅值图
        ax1.loglog(freq, Z_mag, 'b-', linewidth=2, marker='o', markersize=3)
        ax1.set_ylabel('|Z| (Ω)')
        ax1.set_title(f'Bode图 - T={temp:.0f}K')
        ax1.grid(True, which="both", ls="-", alpha=0.3)
        
        # 绘制相位图
        ax2.semilogx(freq, Z_phase, 'r-', linewidth=2, marker='s', markersize=3)
        ax2.set_xlabel('频率 (Hz)')
        ax2.set_ylabel('相位 (°)')
        ax2.grid(True, which="both", ls="-", alpha=0.3)
        
        plt.tight_layout()
        
        # 确保保存目录存在
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        
        # 保存图片
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"Bode图已保存: {save_path}")
        
    except Exception as e:
        print(f"绘制Bode图失败: {str(e)}")
        # 创建一个简单的错误提示图
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.text(0.5, 0.5, f'Bode图生成失败\n温度: {temp:.0f}K\n错误: {str(e)}', 
                ha='center', va='center', transform=ax.transAxes)
        ax.set_title(f'Bode图 - T={temp:.0f}K (错误)')
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.close()

def plot_nyquist_diagram(zreal, zimag, temp, save_path):
    """
    绘制Nyquist图（阻抗谱圆弧图）
    参数:
        zreal: 阻抗实部
        zimag: 阻抗虚部
        temp: 温度
        save_path: 保存路径
    """
    try:
        fig, ax = plt.subplots(figsize=(8, 6))
        
        # 绘制Nyquist图，虚部取负值
        ax.plot(zreal, -zimag, 'bo-', markersize=4, linewidth=1.5)
        
        ax.set_xlabel("Z' (Ω)")
        ax.set_ylabel("-Z'' (Ω)")
        ax.set_title(f'Nyquist图 - T={temp:.0f}K')
        ax.grid(True, alpha=0.3)
        ax.set_aspect('equal', adjustable='box')
        
        plt.tight_layout()
        
        # 确保保存目录存在
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        
        # 保存图片
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"Nyquist图已保存: {save_path}")
        
    except Exception as e:
        print(f"绘制Nyquist图失败: {str(e)}")
        # 创建一个简单的错误提示图
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.text(0.5, 0.5, f'Nyquist图生成失败\n温度: {temp:.0f}K\n错误: {str(e)}', 
                ha='center', va='center', transform=ax.transAxes)
        ax.set_title(f'Nyquist图 - T={temp:.0f}K (错误)')
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.close() 