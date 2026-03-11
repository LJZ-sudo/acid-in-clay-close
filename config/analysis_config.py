# -*- coding: utf-8 -*-
"""
EIS数据分析配置参数
"""

class AnalysisConfig:
    """分析参数配置类"""
    
    # 数据加载参数
    DEFAULT_START_TEMP = 300.0  # 默认起始温度(K)
    DEFAULT_DELTA_TEMP = 3.0    # 默认温度间隔(K)
    
    # 滤波参数
    SAVGOL_WINDOW = 7           # Savitzky-Golay滤波窗口
    SAVGOL_POLY = 3             # 多项式阶数
    OUTLIER_THRESHOLD = 3.0     # 异常点检测阈值(σ)
    
    # 拟合参数
    LINEAR_R2_THRESHOLD = 0.998         # 线性拟合R²阈值
    LINEAR_PROGRESSIVE_THRESHOLD = 0.995 # 渐进式线性拟合阈值
    MIN_INLIER_RATIO = 0.05             # 最小内点比例
    MAX_REMOVE_RATIO = 0.2              # 最大移除点比例
    
    # 圆拟合参数
    CIRCLE_LINEAR_THRESHOLD = 0.999     # 圆拟合线性检测阈值
    HUBER_TAU = 10                      # Huber权重参数
    CIRCLE_MAX_ITER = 50                # 圆拟合最大迭代次数
    CIRCLE_TOL = 1e-6                   # 圆拟合收敛容忍度
    
    # 阿伦尼乌斯分析参数
    MIN_SEGMENT_POINTS = 3              # 最小分段点数
    ARRHENIUS_R = 8.314                 # 气体常数
    
    # 可视化参数
    FIGURE_DPI = 300                    # 图片分辨率
    FIGURE_SIZE = (10, 8)               # 默认图片尺寸
    
    @classmethod
    def get_fit_params(cls):
        """获取拟合参数字典"""
        return {
            'linear_r2_threshold': cls.LINEAR_R2_THRESHOLD,
            'linear_progressive_threshold': cls.LINEAR_PROGRESSIVE_THRESHOLD,
            'circle_linear_threshold': cls.CIRCLE_LINEAR_THRESHOLD,
            'max_remove_ratio': cls.MAX_REMOVE_RATIO,
            'huber_tau': cls.HUBER_TAU,
            'circle_max_iter': cls.CIRCLE_MAX_ITER,
            'circle_tol': cls.CIRCLE_TOL
        }
        
    @classmethod
    def get_arrhenius_params(cls):
        """获取阿伦尼乌斯分析参数字典"""
        return {
            'min_segment_points': cls.MIN_SEGMENT_POINTS,
            'gas_constant': cls.ARRHENIUS_R
        }
