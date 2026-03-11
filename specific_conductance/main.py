from data_processing import read_csv_files, filter_data
from rb_fitting import calculate_rb, visualize_fitting, detect_phase_jump
from conductivity import calculate_conductivity, get_fit_params, visualize_conductivity
import os

def analyze_eis_data(folder, fit_dir, temp_sup, temp_step, thickness, area, fit_params):
    """
    分析EIS数据并检测相变点
    参数:
        folder: 数据文件夹
        fit_dir: 拟合结果保存路径
        temp_sup: 温度上限
        temp_step: 温度步长
        thickness: 薄膜厚度
        area: 电极面积
        fit_params: 拟合参数
    返回:
        phase_transition_range: 相变温度区间元组 (T_high, T_low) 或 None
        conductivity_results: 电导率结果列表
        temp_inf: 温度下限
        warnings: 警告信息列表
    """
    data = read_csv_files(folder, temp_sup, temp_step)
    os.makedirs(fit_dir, exist_ok=True)
    conductivity_results = []
    warnings = []
    flag = True
    phase_transition_range = None
    for temp, df in sorted(data.items(), reverse=True):
        freq = df['Freq'].values
        zreal = df['Zreal'].values
        zimag = df['Zimag'].values
        # 数据清洗
        freq, zreal, zimag = filter_data(freq, zreal, zimag)
        if len(freq) < 5:
            warnings.append(f"温度 {temp:.0f}K: 数据点太少, 跳过")
            continue
        # 检查相位突变
        if detect_phase_jump(zreal, zimag, threshold=15): #  相位阈值此处更改
            print(f"检测到相位突变, 温度 {temp:.0f}K 及以下的数据可能无法用于电导率计算, 程序终止！")
            temp+=3
            break
        rb_result = calculate_rb(zreal, zimag, temp, fit_params)
        if flag and rb_result['method'] == '圆弧拟合':
            flag = False
            phase_transition_range = (temp+temp_step, temp)
        rb = rb_result.get('rb', None)
        sigma = calculate_conductivity(rb, thickness, area)
        # 可视化每个温度点的拟合过程
        visualize_fitting(zreal, zimag, rb_result, fit_dir)
        if sigma is not None:
            conductivity_results.append((temp, sigma))
            print(f"温度 {temp:.0f}K: 电导率 = {sigma:.4e} S/cm")
        else:
            warnings.append(f"温度 {temp:.0f}K: 电导率计算失败")
    temp_inf = temp
    # 电导率-温度关系图保存到test目录
    visualize_conductivity(conductivity_results, 'test')
    return phase_transition_range, conductivity_results, temp_inf, warnings


if __name__ == "__main__":
    phase_transition_range, conductivity_results, temp_inf, warnings = analyze_eis_data(folder = 'data\S8-3-2-1 300-140K 1K-min', fit_dir = 'test/fit', temp_sup = 300, temp_step = 3, thickness = 0.1, area = 1.0, fit_params = get_fit_params())
    print(f"发生相变区间为({phase_transition_range[0]:.4f}, {phase_transition_range[1]:.4f})K")
    for i in range(len(conductivity_results)):
        print(f"温度 {conductivity_results[i][0]:.0f}K: 电导率 = {conductivity_results[i][1]:.4e} S/cm")
    print(f"测温下限为{temp_inf:.4f}K")
    print(warnings)