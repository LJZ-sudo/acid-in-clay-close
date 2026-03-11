import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit
from scipy.constants import e, k


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


def calculate_activation_energy(temperatures, conductivities):
    """
    计算活化能
    :param temperatures: 温度数组 (K)
    :param conductivities: 电导率数组 (S/m)
    :return: 活化能 (eV)
    """
    try:
        # 转换为K温度
        T_k = temperatures + 273.15
        
        # 计算ln(σT)
        ln_sigma_T = np.log(conductivities * T_k)
        
        # 计算1/T
        inv_T = 1.0 / T_k
        
        # 线性拟合
        coeffs = np.polyfit(inv_T, ln_sigma_T, 1)
        slope = coeffs[0]
        
        # 活化能 Ea = -slope * k / e
        activation_energy = -slope * k / e
        
        return activation_energy
        
    except Exception as e:
        print(f"活化能计算失败: {e}")
        return 0.0


def fit_arrhenius_plot(temperatures, conductivities):
    """
    拟合Arrhenius图
    :param temperatures: 温度数组 (°C)
    :param conductivities: 电导率数组 (S/m)
    :return: 拟合结果
    """
    try:
        # 转换为K温度
        T_k = temperatures + 273.15
        
        # 计算ln(σT)
        ln_sigma_T = np.log(conductivities * T_k)
        
        # 计算1/T
        inv_T = 1.0 / T_k
        
        # 线性拟合
        coeffs = np.polyfit(inv_T, ln_sigma_T, 1)
        slope = coeffs[0]
        intercept = coeffs[1]
        
        # 计算活化能
        activation_energy = -slope * k / e
        
        # 计算拟合误差
        fitted_ln_sigma_T = slope * inv_T + intercept
        error = np.sqrt(np.mean((ln_sigma_T - fitted_ln_sigma_T)**2))
        
        return {
            'activation_energy': activation_energy,
            'slope': slope,
            'intercept': intercept,
            'error': error,
            'r_squared': 1 - np.sum((ln_sigma_T - fitted_ln_sigma_T)**2) / np.sum((ln_sigma_T - np.mean(ln_sigma_T))**2)
        }
        
    except Exception as e:
        print(f"Arrhenius拟合失败: {e}")
        return {
            'activation_energy': 0.0,
            'slope': 0.0,
            'intercept': 0.0,
            'error': float('inf'),
            'r_squared': 0.0
        }


def analyze_conductivity_temperature_dependence(temperatures, conductivities):
    """
    分析电导率温度依赖性
    :param temperatures: 温度数组 (°C)
    :param conductivities: 电导率数组 (S/m)
    :return: 分析结果
    """
    try:
        # 计算电导率变化率
        conductivity_changes = np.diff(conductivities)
        temperature_changes = np.diff(temperatures)
        
        # 计算温度系数
        temp_coefficients = conductivity_changes / temperature_changes
        
        # 找到最大变化率
        max_change_idx = np.argmax(np.abs(conductivity_changes))
        max_change_temp = temperatures[max_change_idx]
        max_change_rate = temp_coefficients[max_change_idx]
        
        # 计算平均温度系数
        avg_temp_coefficient = np.mean(temp_coefficients)
        
        return {
            'max_change_temperature': max_change_temp,
            'max_change_rate': max_change_rate,
            'average_temp_coefficient': avg_temp_coefficient,
            'temperature_range': f"{np.min(temperatures):.1f}°C - {np.max(temperatures):.1f}°C",
            'conductivity_range': f"{np.min(conductivities):.2e} - {np.max(conductivities):.2e} S/m"
        }
        
    except Exception as e:
        print(f"电导率温度依赖性分析失败: {e}")
        return {
            'max_change_temperature': 0.0,
            'max_change_rate': 0.0,
            'average_temp_coefficient': 0.0,
            'temperature_range': "N/A",
            'conductivity_range': "N/A"
        }


def plot_conductivity_vs_temperature(temperatures, conductivities, save_path=None):
    """
    绘制电导率随温度变化图
    :param temperatures: 温度数组 (°C)
    :param conductivities: 电导率数组 (S/m)
    :param save_path: 保存路径
    """
    try:
        plt.figure(figsize=(10, 6))
        
        # 主图：电导率随温度变化
        plt.subplot(2, 1, 1)
        plt.semilogy(temperatures, conductivities, 'ro-', markersize=8, linewidth=2)
        plt.xlabel('温度 (°C)')
        plt.ylabel('电导率 (S/m)')
        plt.title('电导率随温度变化')
        plt.grid(True)
        
        # 子图：Arrhenius图
        plt.subplot(2, 1, 2)
        T_k = temperatures + 273.15
        ln_sigma_T = np.log(conductivities * T_k)
        inv_T = 1.0 / T_k
        
        plt.plot(inv_T, ln_sigma_T, 'bo-', markersize=6, linewidth=2)
        plt.xlabel('1/T (K⁻¹)')
        plt.ylabel('ln(σT)')
        plt.title('Arrhenius图')
        plt.grid(True)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"电导率图已保存: {save_path}")
        
        plt.show()
        
    except Exception as e:
        print(f"绘图失败: {e}")


def get_fit_params():
    """
    获取拟合参数
    :return: 拟合参数字典
    """
    return {
        'thickness_default': 0.001,  # 默认样品厚度 (m)
        'area_default': 1e-4,        # 默认样品截面积 (m²)
        'activation_energy_unit': 'eV',
        'conductivity_unit': 'S/m',
        'temperature_unit': '°C'
    }


def calculate_conductivity_from_rb_data(rb_data, thickness, area):
    """
    从Rb数据计算电导率
    :param rb_data: Rb数据字典列表
    :param thickness: 样品厚度 (m)
    :param area: 样品截面积 (m²)
    :return: 电导率数据
    """
    conductivity_data = []
    
    for data_point in rb_data:
        try:
            rb = data_point.get('rb', 0)
            temp = data_point.get('temperature', 0)
            
            conductivity = calculate_conductivity(rb, thickness, area)
            
            conductivity_data.append({
                'temperature': temp,
                'conductivity': conductivity,
                'rb': rb,
                'method': data_point.get('method', '未知')
            })
            
        except Exception as e:
            print(f"计算电导率失败: {e}")
            continue
    
    return conductivity_data


if __name__ == "__main__":
    # 测试函数
    print("电导率计算模块测试")
    
    # 生成测试数据
    temps = np.array([20, 10, 0, -10, -20, -30])
    conductivities = np.array([1e-3, 5e-4, 2e-4, 1e-4, 5e-5, 2e-5])
    
    # 测试电导率计算
    rb = 100.0
    thickness = 0.001
    area = 1e-4
    conductivity = calculate_conductivity(rb, thickness, area)
    print(f"电导率计算结果: {conductivity:.2e} S/m")
    
    # 测试活化能计算
    activation_energy = calculate_activation_energy(temps, conductivities)
    print(f"活化能计算结果: {activation_energy:.3f} eV")
    
    # 测试Arrhenius拟合
    arrhenius_result = fit_arrhenius_plot(temps, conductivities)
    print(f"Arrhenius拟合结果: {arrhenius_result}")
    
    # 测试温度依赖性分析
    temp_dep_result = analyze_conductivity_temperature_dependence(temps, conductivities)
    print(f"温度依赖性分析结果: {temp_dep_result}")
    
    # 测试绘图
    plot_conductivity_vs_temperature(temps, conductivities) 