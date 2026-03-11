import os
import re
import pandas as pd
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
from scipy.signal import savgol_filter
import sys, os
# sys.path.insert(0, os.path.abspath('..'))  # Add parent directory for code_set
# from code_set.utils import fig2base64  # 注释掉不存在的导入


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
        try:
            temp_k = start_temp - (idx - 1) * delta_temp
            if np.isnan(temp_k) or not np.isfinite(temp_k):
                temp_k = None
                error_msg = '温度计算无效'
            else:
                temp_k = start_temp - (idx - 1) * delta_temp
        except:
            temp_k = None
            error_msg = '文件名解析失败'
        
        fullpath = os.path.join(folder_path, fname)
        try:
            # 先读取二进制定位“ZCURVE”行号
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
            
            # 改进温度解析
            from re import search
            m_temp = search(r'(\d+)(?:-\d+)?K', fname)
            if m_temp:
                temp_k = float(m_temp.group(1))
            else:
                m_idx = pattern.search(fname)
                if m_idx:
                    idx = int(m_idx.group(1))
                    temp_k = start_temp - (idx - 1) * delta_temp
                else:
                    temp_k = None
            if temp_k is not None and not np.isnan(temp_k) and np.isfinite(temp_k):
                data_dict[temp_k] = df[['Freq','Zreal','Zimag']].copy()
                print(f"成功读取 {fname} -> T={temp_k:.1f}K")
            else:
                print(f"警告: 无法解析 {fname} 的温度，跳过")
                continue
        
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


def generate_bode_plot(freq, zreal, zimag, temp_k):
    """生成 Bode 图并返回 base64 编码"""
    import base64
    from io import BytesIO
    
    # 计算模量和相位
    zmod = np.sqrt(zreal**2 + zimag**2)  # 模量
    zphz = np.arctan2(zimag, zreal) * 180 / np.pi  # 相位 (度)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8, 6), sharex=True)

    # 模量图
    ax1.semilogx(freq, 20 * np.log10(zmod), 'bo-', label='模量')
    ax1.set_ylabel('|Z| (dB)')
    ax1.grid(True)
    ax1.legend()

    # 相位图
    ax2.semilogx(freq, zphz, 'ro-', label='相位')
    ax2.set_xlabel('频率 (Hz)')
    ax2.set_ylabel('相位 (度)')
    ax2.grid(True)
    ax2.legend()

    plt.suptitle(f'Bode 图 T={temp_k:.1f}K')
    plt.tight_layout()

    # 转换为base64
    buffer = BytesIO()
    fig.savefig(buffer, format='png', dpi=300, bbox_inches='tight')
    buffer.seek(0)
    image_base64 = base64.b64encode(buffer.read()).decode()
    plt.close(fig)
    
    return image_base64


if __name__ == "__main__":
    # 设置中文和负号显示
    matplotlib.rcParams['font.sans-serif'] = ['SimHei']
    matplotlib.rcParams['axes.unicode_minus'] = False

    # 数据文件夹路径
    folder = 'data/S8-3-2-1 300-140K 1K-min'
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