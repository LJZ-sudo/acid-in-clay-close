import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit
from scipy.signal import savgol_filter


def detect_phase_jump(zreal, zimag, threshold=0.1):
    """
    检测相变点
    :param zreal: 实部阻抗
    :param zimag: 虚部阻抗
    :param threshold: 检测阈值
    :return: 是否检测到相变点
    """
    try:
        # 计算阻抗模量
        z_mod = np.sqrt(zreal**2 + zimag**2)
        
        # 计算阻抗模量的变化率
        z_mod_diff = np.diff(z_mod)
        
        # 检测突变点
        jump_points = np.where(np.abs(z_mod_diff) > threshold * np.std(z_mod_diff))[0]
        
        if len(jump_points) > 0:
            print(f"检测到 {len(jump_points)} 个可能的相变点")
            return True
        
        return False
        
    except Exception as e:
        print(f"相变点检测失败: {e}")
        return False


def calculate_rb(zreal, zimag, temp, params, circle_dir=None):
    """
    计算Rb值
    :param zreal: 实部阻抗
    :param zimag: 虚部阻抗
    :param temp: 温度
    :param params: 拟合参数
    :param circle_dir: 图片保存目录 (可选)
    :return: Rb计算结果
    """
    try:
        # 简化的Rb计算（实际应用中需要更复杂的拟合算法）
        # 这里使用高频极限作为Rb的近似
        high_freq_idx = len(zreal) // 4  # 取最后1/4的数据点
        rb_estimate = np.mean(zreal[-high_freq_idx:])
        
        return {
            'rb': rb_estimate,
            'method': '高频极限近似',
            'fit_params': {
                'temperature': temp,
                'data_points': len(zreal)
            }
        }
        
    except Exception as e:
        print(f"Rb计算失败: {e}")
        return {
            'rb': 100.0,
            'method': '默认值',
            'fit_params': {}
        }


def fit_nyquist_plot(zreal, zimag, temp):
    """
    拟合Nyquist图
    :param zreal: 实部阻抗
    :param zimag: 虚部阻抗
    :param temp: 温度
    :return: 拟合结果
    """
    try:
        # 简化的Nyquist拟合
        # 实际应用中需要更复杂的等效电路拟合
        
        # 计算半圆拟合参数
        center_x = (np.max(zreal) + np.min(zreal)) / 2
        center_y = np.min(zimag)
        radius = (np.max(zreal) - np.min(zreal)) / 2
        
        # 计算拟合误差
        fitted_zreal = center_x + radius * np.cos(np.linspace(0, np.pi, len(zreal)))
        fitted_zimag = center_y + radius * np.sin(np.linspace(0, np.pi, len(zreal)))
        
        error = np.sqrt(np.mean((zreal - fitted_zreal)**2 + (zimag - fitted_zimag)**2))
        
        return {
            'center_x': center_x,
            'center_y': center_y,
            'radius': radius,
            'error': error,
            'temperature': temp
        }
        
    except Exception as e:
        print(f"Nyquist拟合失败: {e}")
        return {
            'center_x': 0,
            'center_y': 0,
            'radius': 0,
            'error': float('inf'),
            'temperature': temp
        }


def analyze_impedance_spectrum(freq, zreal, zimag, temp):
    """
    分析阻抗谱
    :param freq: 频率
    :param zreal: 实部阻抗
    :param zimag: 虚部阻抗
    :param temp: 温度
    :return: 分析结果
    """
    try:
        # 计算阻抗模量
        z_mod = np.sqrt(zreal**2 + zimag**2)
        
        # 计算相位角
        phase = np.arctan2(zimag, zreal)
        
        # 找到最大阻抗点
        max_idx = np.argmax(z_mod)
        max_freq = freq[max_idx]
        max_z_mod = z_mod[max_idx]
        
        # 计算特征频率
        char_freq = freq[np.argmin(np.abs(phase + np.pi/4))]
        
        return {
            'max_frequency': max_freq,
            'max_impedance': max_z_mod,
            'characteristic_frequency': char_freq,
            'temperature': temp,
            'data_points': len(freq)
        }
        
    except Exception as e:
        print(f"阻抗谱分析失败: {e}")
        return {
            'max_frequency': 0,
            'max_impedance': 0,
            'characteristic_frequency': 0,
            'temperature': temp,
            'data_points': 0
        }


if __name__ == "__main__":
    # 测试函数
    print("Rb拟合模块测试")
    
    # 生成测试数据
    freq = np.logspace(0, 4, 50)
    zreal = 100 + 50 * np.cos(np.linspace(0, np.pi, 50))
    zimag = -50 * np.sin(np.linspace(0, np.pi, 50))
    
    # 测试相变点检测
    phase_jump = detect_phase_jump(zreal, zimag)
    print(f"相变点检测结果: {phase_jump}")
    
    # 测试Rb计算
    rb_result = calculate_rb(zreal, zimag, 298.15, {})
    print(f"Rb计算结果: {rb_result}")
    
    # 测试Nyquist拟合
    nyquist_result = fit_nyquist_plot(zreal, zimag, 298.15)
    print(f"Nyquist拟合结果: {nyquist_result}")
    
    # 测试阻抗谱分析
    spectrum_result = analyze_impedance_spectrum(freq, zreal, zimag, 298.15)
    print(f"阻抗谱分析结果: {spectrum_result}") 