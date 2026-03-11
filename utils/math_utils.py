# -*- coding: utf-8 -*-
"""
数学计算工具函数
"""
import numpy as np
from typing import Tuple, Optional, Union
from scipy import stats
from sklearn.metrics import r2_score

class MathUtils:
    """数学计算工具类"""
    
    @staticmethod
    def calculate_correlation(x: np.ndarray, y: np.ndarray) -> float:
        """
        计算皮尔逊相关系数
        
        Args:
            x, y: 一维numpy数组
            
        Returns:
            相关系数，范围[-1, 1]
        """
        if len(x) != len(y) or len(x) < 2:
            return 0.0
        
        x_mean = np.mean(x)
        y_mean = np.mean(y)
        numerator = np.sum((x - x_mean) * (y - y_mean))
        denominator = np.sqrt(np.sum((x - x_mean)**2) * np.sum((y - y_mean)**2))
        
        return numerator / denominator if denominator != 0 else 0.0
    
    @staticmethod
    def linear_regression(x: np.ndarray, y: np.ndarray) -> Tuple[float, float, float]:
        """
        线性回归
        
        Args:
            x, y: 数据数组
            
        Returns:
            (斜率, 截距, R²)
        """
        slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)
        r_squared = r_value ** 2
        return slope, intercept, r_squared
    
    @staticmethod
    def polynomial_fit(x: np.ndarray, y: np.ndarray, degree: int = 2) -> Tuple[np.ndarray, float]:
        """
        多项式拟合
        
        Args:
            x, y: 数据数组
            degree: 多项式阶数
            
        Returns:
            (系数数组, R²)
        """
        coeffs = np.polyfit(x, y, degree)
        y_pred = np.polyval(coeffs, x)
        r_squared = r2_score(y, y_pred)
        return coeffs, r_squared
    
    @staticmethod
    def moving_average(data: np.ndarray, window: int) -> np.ndarray:
        """
        移动平均
        
        Args:
            data: 数据数组
            window: 窗口大小
            
        Returns:
            平滑后的数据
        """
        if window >= len(data):
            return np.full_like(data, np.mean(data))
        
        return np.convolve(data, np.ones(window)/window, mode='same')
    
    @staticmethod
    def outlier_detection_iqr(data: np.ndarray, factor: float = 1.5) -> np.ndarray:
        """
        IQR方法异常值检测
        
        Args:
            data: 数据数组
            factor: IQR倍数因子
            
        Returns:
            布尔掩码，True表示正常值
        """
        Q1 = np.percentile(data, 25)
        Q3 = np.percentile(data, 75)
        IQR = Q3 - Q1
        lower_bound = Q1 - factor * IQR
        upper_bound = Q3 + factor * IQR
        return (data >= lower_bound) & (data <= upper_bound)
    
    @staticmethod
    def outlier_detection_zscore(data: np.ndarray, threshold: float = 3.0) -> np.ndarray:
        """
        Z-score方法异常值检测
        
        Args:
            data: 数据数组
            threshold: Z-score阈值
            
        Returns:
            布尔掩码，True表示正常值
        """
        z_scores = np.abs(stats.zscore(data))
        return z_scores < threshold
    
    @staticmethod
    def normalize_data(data: np.ndarray, method: str = 'minmax') -> np.ndarray:
        """
        数据归一化
        
        Args:
            data: 数据数组
            method: 归一化方法 ('minmax', 'zscore')
            
        Returns:
            归一化后的数据
        """
        if method == 'minmax':
            data_min = np.min(data)
            data_max = np.max(data)
            if data_max == data_min:
                return np.zeros_like(data)
            return (data - data_min) / (data_max - data_min)
        
        elif method == 'zscore':
            return stats.zscore(data)
        
        else:
            raise ValueError(f"不支持的归一化方法: {method}")
    
    @staticmethod
    def confidence_interval(data: np.ndarray, confidence: float = 0.95) -> Tuple[float, float]:
        """
        计算置信区间
        
        Args:
            data: 数据数组
            confidence: 置信水平
            
        Returns:
            (下界, 上界)
        """
        mean = np.mean(data)
        sem = stats.sem(data)  # 标准误差
        h = sem * stats.t.ppf((1 + confidence) / 2., len(data)-1)
        return mean - h, mean + h
    
    @staticmethod
    def bootstrap_confidence_interval(data: np.ndarray, statistic_func: callable,
                                    n_bootstrap: int = 1000, confidence: float = 0.95) -> Tuple[float, float]:
        """
        Bootstrap置信区间
        
        Args:
            data: 数据数组
            statistic_func: 统计量函数
            n_bootstrap: Bootstrap次数
            confidence: 置信水平
            
        Returns:
            (下界, 上界)
        """
        bootstrap_stats = []
        n = len(data)
        
        for _ in range(n_bootstrap):
            bootstrap_sample = np.random.choice(data, size=n, replace=True)
            stat = statistic_func(bootstrap_sample)
            bootstrap_stats.append(stat)
        
        bootstrap_stats = np.array(bootstrap_stats)
        alpha = 1 - confidence
        lower = np.percentile(bootstrap_stats, 100 * alpha / 2)
        upper = np.percentile(bootstrap_stats, 100 * (1 - alpha / 2))
        
        return lower, upper
    
    @staticmethod
    def smooth_spline(x: np.ndarray, y: np.ndarray, smoothing_factor: float = None) -> np.ndarray:
        """
        样条平滑
        
        Args:
            x, y: 数据数组
            smoothing_factor: 平滑因子
            
        Returns:
            平滑后的y值
        """
        from scipy.interpolate import UnivariateSpline
        
        if smoothing_factor is None:
            smoothing_factor = len(x)
        
        spline = UnivariateSpline(x, y, s=smoothing_factor)
        return spline(x)
    
    @staticmethod
    def find_peaks(data: np.ndarray, height: Optional[float] = None,
                  distance: Optional[int] = None) -> np.ndarray:
        """
        寻找峰值
        
        Args:
            data: 数据数组
            height: 最小峰高
            distance: 峰间最小距离
            
        Returns:
            峰值位置索引
        """
        from scipy.signal import find_peaks as scipy_find_peaks
        
        peaks, _ = scipy_find_peaks(data, height=height, distance=distance)
        return peaks
    
    @staticmethod
    def calculate_auc(x: np.ndarray, y: np.ndarray) -> float:
        """
        计算曲线下面积（梯形法则）
        
        Args:
            x, y: 数据数组
            
        Returns:
            曲线下面积
        """
        return np.trapz(y, x)
    
    @staticmethod
    def derivative(x: np.ndarray, y: np.ndarray, method: str = 'gradient') -> np.ndarray:
        """
        数值微分
        
        Args:
            x, y: 数据数组
            method: 微分方法 ('gradient', 'diff')
            
        Returns:
            导数数组
        """
        if method == 'gradient':
            return np.gradient(y, x)
        elif method == 'diff':
            return np.diff(y) / np.diff(x)
        else:
            raise ValueError(f"不支持的微分方法: {method}")
    
    @staticmethod
    def integral(x: np.ndarray, y: np.ndarray, method: str = 'trapz') -> float:
        """
        数值积分
        
        Args:
            x, y: 数据数组
            method: 积分方法 ('trapz', 'simpson')
            
        Returns:
            积分值
        """
        if method == 'trapz':
            return np.trapz(y, x)
        elif method == 'simpson':
            from scipy.integrate import simpson
            return simpson(y, x)
        else:
            raise ValueError(f"不支持的积分方法: {method}")
    
    @staticmethod
    def rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
        """计算均方根误差"""
        return np.sqrt(np.mean((y_true - y_pred) ** 2))
    
    @staticmethod
    def mae(y_true: np.ndarray, y_pred: np.ndarray) -> float:
        """计算平均绝对误差"""
        return np.mean(np.abs(y_true - y_pred))
    
    @staticmethod
    def mape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
        """计算平均绝对百分比误差"""
        return np.mean(np.abs((y_true - y_pred) / y_true)) * 100
