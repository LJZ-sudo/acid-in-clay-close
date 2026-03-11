import os
import re
import pandas as pd
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
from scipy.signal import savgol_filter


def read_csv_files(folder_path, start_temp=300.0, delta_temp=3.0):
    """
    批量读取 EIS 文本文件, 文件名形如 "..._#i.txt" (i 从 1 开始)。
    温度计算公式: T = start_temp - (i - 1) * delta_temp。
    
    返回: 
      data_dict: { T: DataFrame(freq, Zreal, Zimag) }
    """
    data_dict = {}
    pattern = re.compile(r'#(\d+)\.txt$')
    for fname in os.listdir(folder_path):
        m = pattern.search(fname)
        if not m:
            continue
        idx = int(m.group(1))
        T = start_temp - (idx - 1) * delta_temp
        
        fullpath = os.path.join(folder_path, fname)
        try:
            # 先读取二进制定位"ZCURVE"行号
            with open(fullpath, 'rb') as f:
                lines = f.readlines()
            data_start = None
            for i, line in enumerate(lines):
                if b'ZCURVE' in line:
                    data_start = i + 3  # 跳过表头和列名两行
                    break
            if data_start is None:
                print(f"警告: 未在 {fname} 中找到 'ZCURVE' 标记, 跳过此文件")
                continue
            
            # 用 pandas 读取数据
            df = pd.read_csv(
                fullpath,
                skiprows=data_start,
                delimiter=r'\s+',
                names=['Pt', 'Time', 'Freq', 'Zreal', 'Zimag',
                       'Zsig', 'Zmod', 'Zphz', 'Idc', 'Vdc', 'IERange'],
                engine='python',
                encoding='latin1'
            )
            
            # 类型转换并清洗
            df['Freq']  = pd.to_numeric(df['Freq'],  errors='coerce')
            df['Zreal'] = pd.to_numeric(df['Zreal'], errors='coerce')
            df['Zimag'] = pd.to_numeric(df['Zimag'], errors='coerce')
            df = df.dropna(subset=['Freq','Zreal','Zimag'])
            
            data_dict[T] = df[['Freq','Zreal','Zimag']].copy()
            print(f"成功读取 {fname} -> T={T:.1f}K, 数据点={len(df)}")
        
        except Exception as e:
            print(f"错误: 读取文件 {fname} 时出错: {e}")
    
    if not data_dict:
        print("警告: 未读取到任何有效文件。请检查文件夹路径或文件命名规则。")
    return data_dict


def filter_data(freq, zreal, zimag, window=7, poly=3, thresh=3.0):
    """
    对阻抗数据进行 Savitzky-Golay 滤波平滑, 并剔除残差超过阈值的异常点。
    返回过滤后的 freq, zreal, zimag
    """
    if len(zreal) < window:
        print("警告: 数据点少于滤波窗口长度, 跳过滤波")
        return freq, zreal, zimag
    try:
        smooth_zreal = savgol_filter(zreal, window_length=window, polyorder=poly, mode='interp')
        smooth_zimag = savgol_filter(zimag, window_length=window, polyorder=poly, mode='interp')
    except Exception as e:
        print(f"错误: 滤波失败: {e}")
        return freq, zreal, zimag
    resid_real = zreal - smooth_zreal
    resid_imag = zimag - smooth_zimag
    mask = (np.abs(resid_real) < thresh * np.nanstd(resid_real)) & \
           (np.abs(resid_imag) < thresh * np.nanstd(resid_imag))
    removed = len(freq) - np.sum(mask)
    if removed > 0:
        print(f"移除 {removed} 个异常点 (残差筛选)")
    return freq[mask], zreal[mask], zimag[mask]


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


def calculate_rb(zreal, zimag, temp, params):
    """
    计算Rb值
    :param zreal: 实部阻抗
    :param zimag: 虚部阻抗
    :param temp: 温度
    :param params: 拟合参数
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


def calculate_conductivity(rb, thickness, area):
    """
    计算电导率
    :param rb: 体电阻 (Ω)
    :param thickness: 样品厚度 (m)
    :param area: 样品截面积 (m²)
    :return: 电导率 (S/m)
    """
    try:
        if rb <= 0:
            return 0.0
        
        # 电导率计算公式: σ = thickness / (Rb * area)
        conductivity = thickness / (rb * area)
        return conductivity
        
    except Exception as e:
        print(f"电导率计算失败: {e}")
        return 0.0


def get_fit_params():
    """
    获取拟合参数
    :return: 拟合参数字典
    """
    return {
        'window_length': 7,
        'polyorder': 3,
        'threshold': 3.0,
        'phase_jump_threshold': 0.1
    }


if __name__ == "__main__":
    # 设置中文和负号显示
    matplotlib.rcParams['font.sans-serif'] = ['SimHei']
    matplotlib.rcParams['axes.unicode_minus'] = False

    # 数据文件夹路径
    folder = 'D:\chi_data\S8-3-2-1 300-140K 1K-min'
    # 读取数据, 返回 {温度: DataFrame}
    data = read_csv_files(folder)

    # 输出目录
    out_dir = 'test/filter_data'
    os.makedirs(out_dir, exist_ok=True)

    # 逐温度进行滤波测试并绘图
    for T, df in sorted(data.items()):
        freq = df['Freq'].values
        zreal = df['Zreal'].values
        zimag = df['Zimag'].values

        # 滤波处理
        f_freq, f_zreal, f_zimag = filter_data(freq, zreal, zimag)

        # 绘制原始与滤波后数据对比图
        plt.figure(figsize=(8, 6))
        plt.plot(zreal, np.abs(zimag), 'bo-', label='原始数据')
        plt.plot(f_zreal, np.abs(f_zimag), 'ro-', label='滤波后数据')
        plt.xlabel("Z' (Ω)")
        plt.ylabel("|Z''| (Ω)")
        plt.title(f"滤波测试 T={int(T)}K")
        plt.legend()
        plt.grid(True)
        # 统一坐标单位间距
        ax = plt.gca()
        ax.set_aspect('equal', adjustable='box')
        plt.tight_layout()

        # 保存图像
        save_path = os.path.join(out_dir, f'filter_{int(T)}K.png')
        plt.savefig(save_path, dpi=300)
        plt.close()
        print(f"已保存: {save_path}") 