# -*- coding: utf-8 -*-
"""
绘图工具函数 - 整合utils.py的功能
"""
import cv2
import numpy as np
from PIL import Image
import base64
import io
import matplotlib.pyplot as plt
import matplotlib
from typing import Optional, Tuple, Union

class PlottingUtils:
    """绘图工具类"""
    
    def __init__(self):
        # 设置matplotlib中文显示
        matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
        matplotlib.rcParams['axes.unicode_minus'] = False
    
    @staticmethod
    def cv2_imread_unicode(filepath: str, flags: int = cv2.IMREAD_COLOR) -> Optional[np.ndarray]:
        """
        解决OpenCV无法读取中文路径的问题
        
        Args:
            filepath: 包含中文字符的文件路径
            flags: OpenCV读取标志，默认为cv2.IMREAD_COLOR
        
        Returns:
            图像数组，如果失败返回None
        """
        try:
            # 方法1：使用numpy fromfile + cv2.imdecode
            image_bytes = np.fromfile(filepath, dtype=np.uint8)
            
            # 根据flags确定解码方式
            if flags == cv2.IMREAD_GRAYSCALE:
                image = cv2.imdecode(image_bytes, cv2.IMREAD_GRAYSCALE)
            elif flags == cv2.IMREAD_COLOR:
                image = cv2.imdecode(image_bytes, cv2.IMREAD_COLOR)
            else:
                image = cv2.imdecode(image_bytes, flags)
                
            return image
            
        except Exception as e:
            print(f"[错误] 无法读取图像文件 {filepath}: {e}")
            try:
                # 方法2：使用PIL作为备选方案
                print(f"[调试] 使用PIL作为备选方案读取: {filepath}")
                pil_image = Image.open(filepath)
                
                # 转换为OpenCV格式
                if flags == cv2.IMREAD_GRAYSCALE:
                    if pil_image.mode != 'L':
                        pil_image = pil_image.convert('L')
                    cv_image = np.array(pil_image)
                else:
                    if pil_image.mode == 'RGBA':
                        pil_image = pil_image.convert('RGB')
                    elif pil_image.mode != 'RGB':
                        pil_image = pil_image.convert('RGB')
                        
                    cv_image = np.array(pil_image)
                    # PIL使用RGB，OpenCV使用BGR，需要转换
                    if len(cv_image.shape) == 3:
                        cv_image = cv2.cvtColor(cv_image, cv2.COLOR_RGB2BGR)
                
                print(f"[调试] 使用PIL成功加载: {filepath}")
                return cv_image
                
            except Exception as e2:
                print(f"[错误] PIL也无法读取图像文件 {filepath}: {e2}")
                return None
    
    @staticmethod
    def fig2base64(fig: plt.Figure, format: str = 'png', dpi: int = 100) -> Optional[str]:
        """
        将matplotlib图表转换为base64编码字符串
        
        Args:
            fig: matplotlib.figure.Figure对象
            format: 图像格式，默认为'png'
            dpi: 图像分辨率，默认为100
        
        Returns:
            base64编码的图像字符串
        """
        try:
            # 创建字节流缓冲区
            buffer = io.BytesIO()
            
            # 保存图表到缓冲区
            fig.savefig(buffer, format=format, dpi=dpi, bbox_inches='tight')
            
            # 移动到缓冲区开始位置
            buffer.seek(0)
            
            # 读取字节数据并转换为base64
            image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            
            # 关闭缓冲区
            buffer.close()
            
            return image_base64
            
        except Exception as e:
            print(f"[错误] 图表转换base64失败: {e}")
            return None
    
    @staticmethod
    def save_figure_with_unicode_path(fig: plt.Figure, filepath: str, **kwargs):
        """
        保存图片到包含中文字符的路径
        
        Args:
            fig: matplotlib图形对象
            filepath: 保存路径
            **kwargs: 其他保存参数
        """
        try:
            # 直接保存
            fig.savefig(filepath, **kwargs)
        except Exception as e:
            print(f"直接保存失败: {e}")
            try:
                # 使用临时文件方式
                import tempfile
                import shutil
                
                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
                    fig.savefig(temp_file.name, **kwargs)
                    shutil.move(temp_file.name, filepath)
                    
            except Exception as e2:
                print(f"临时文件保存也失败: {e2}")
    
    @staticmethod
    def create_subplot_layout(nrows: int, ncols: int, figsize: Tuple[int, int] = (12, 8)):
        """
        创建子图布局
        
        Args:
            nrows: 行数
            ncols: 列数
            figsize: 图片尺寸
            
        Returns:
            (fig, axes)
        """
        fig, axes = plt.subplots(nrows, ncols, figsize=figsize)
        
        # 确保axes始终是数组
        if nrows * ncols == 1:
            axes = [axes]
        elif nrows == 1 or ncols == 1:
            axes = axes.flatten()
        
        return fig, axes
    
    @staticmethod
    def set_axis_properties(ax: plt.Axes, xlabel: str = None, ylabel: str = None,
                           title: str = None, grid: bool = True, legend: bool = True):
        """
        设置坐标轴属性
        
        Args:
            ax: matplotlib轴对象
            xlabel: x轴标签
            ylabel: y轴标签
            title: 标题
            grid: 是否显示网格
            legend: 是否显示图例
        """
        if xlabel:
            ax.set_xlabel(xlabel)
        if ylabel:
            ax.set_ylabel(ylabel)
        if title:
            ax.set_title(title)
        if grid:
            ax.grid(True, alpha=0.3)
        if legend:
            ax.legend()
    
    @staticmethod
    def plot_nyquist(zreal: np.ndarray, zimag: np.ndarray, ax: plt.Axes = None,
                    title: str = "Nyquist图", **kwargs):
        """
        绘制Nyquist图
        
        Args:
            zreal: 阻抗实部
            zimag: 阻抗虚部
            ax: matplotlib轴对象
            title: 图标题
            **kwargs: 其他绘图参数
        """
        if ax is None:
            fig, ax = plt.subplots(figsize=(8, 8))
        
        ax.plot(zreal, np.abs(zimag), 'o-', **kwargs)
        ax.set_xlabel("Z' (Ω)")
        ax.set_ylabel("|Z''| (Ω)")
        ax.set_title(title)
        ax.set_aspect('equal', adjustable='box')
        ax.grid(True, alpha=0.3)
        
        return ax
    
    @staticmethod
    def plot_bode(freq: np.ndarray, zreal: np.ndarray, zimag: np.ndarray,
                 ax: Tuple[plt.Axes, plt.Axes] = None, title: str = "Bode图"):
        """
        绘制Bode图
        
        Args:
            freq: 频率
            zreal: 阻抗实部
            zimag: 阻抗虚部
            ax: matplotlib轴对象元组 (幅值轴, 相位轴)
            title: 图标题
        """
        if ax is None:
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))
            ax = (ax1, ax2)
        
        Z = zreal + 1j * zimag
        mag = np.abs(Z)
        phase = np.angle(Z, deg=True)
        
        # 幅频图
        ax[0].semilogx(freq, mag, 'b.-', linewidth=2, markersize=6)
        ax[0].set_xlabel('频率 (Hz)')
        ax[0].set_ylabel('幅值 |Z| (Ω)')
        ax[0].set_title(title)
        ax[0].grid(True, which='both', alpha=0.3)
        
        # 相频图
        ax[1].semilogx(freq, phase, 'r.-', linewidth=2, markersize=6)
        ax[1].set_xlabel('频率 (Hz)')
        ax[1].set_ylabel('相位 (°)')
        ax[1].grid(True, which='both', alpha=0.3)
        
        return ax
    
    @staticmethod
    def plot_arrhenius(temperatures: np.ndarray, conductivities: np.ndarray,
                      ax: plt.Axes = None, title: str = "阿伦尼乌斯图"):
        """
        绘制阿伦尼乌斯图
        
        Args:
            temperatures: 温度数组(K)
            conductivities: 电导率数组(S/cm)
            ax: matplotlib轴对象
            title: 图标题
        """
        if ax is None:
            fig, ax = plt.subplots(figsize=(8, 6))
        
        x = 1000 / temperatures  # 1000/T
        y = np.log(conductivities)  # ln(σ)
        
        ax.scatter(x, y, c='blue', s=50, alpha=0.7)
        ax.set_xlabel('1000/T (K⁻¹)')
        ax.set_ylabel('ln(σ) (S/cm)')
        ax.set_title(title)
        ax.grid(True, alpha=0.3)
        
        return ax
    
    @staticmethod
    def add_colorbar(fig: plt.Figure, mappable, ax: plt.Axes, label: str = ""):
        """
        添加颜色条
        
        Args:
            fig: matplotlib图形对象
            mappable: 可映射对象
            ax: 对应的轴对象
            label: 颜色条标签
        """
        cbar = fig.colorbar(mappable, ax=ax)
        if label:
            cbar.set_label(label)
        return cbar
    
    @staticmethod
    def save_plots_as_pdf(figures: list, filename: str):
        """
        将多个图形保存为一个PDF文件
        
        Args:
            figures: matplotlib图形对象列表
            filename: PDF文件名
        """
        from matplotlib.backends.backend_pdf import PdfPages
        
        with PdfPages(filename) as pdf:
            for fig in figures:
                pdf.savefig(fig, bbox_inches='tight')
        
        print(f"多图PDF已保存: {filename}")
    
    @staticmethod
    def apply_style(style: str = 'seaborn'):
        """
        应用matplotlib样式
        
        Args:
            style: 样式名称
        """
        try:
            plt.style.use(style)
        except OSError:
            print(f"样式 '{style}' 不可用，使用默认样式")
    
    @staticmethod
    def close_all_figures():
        """关闭所有matplotlib图形"""
        plt.close('all')
    
    @staticmethod
    def set_figure_dpi(dpi: int = 100):
        """
        设置图形DPI
        
        Args:
            dpi: 分辨率
        """
        matplotlib.rcParams['figure.dpi'] = dpi
        matplotlib.rcParams['savefig.dpi'] = dpi
