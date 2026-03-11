import os
import sys
import traceback
from pathlib import Path
from typing import Optional, Tuple, Dict

import numpy as np

# 统一 standalone 路径初始化
CLOSE_ROOT = Path(__file__).resolve().parents[2]
if str(CLOSE_ROOT) not in sys.path:
    sys.path.insert(0, str(CLOSE_ROOT))

# ============================================================
# 🔥 强制导入真实模块，不使用任何模拟代码
# ============================================================
print(f"[data_analysis] project root: {CLOSE_ROOT}")

# 直接导入，如果失败就让程序知道
from specific_conductance.data_processing import filter_data
from specific_conductance.rb_fitting import calculate_rb, detect_phase_jump
from specific_conductance.conductivity import calculate_conductivity, get_fit_params

# 导入新增的分析模块
from auto_control.modules.kk_validation import kk_check
from auto_control.modules.drt_analysis import drt_analyze
from auto_control.modules.data_quality import assess_data_quality

# 获取拟合参数（包含linear_threshold等必需参数）
_FIT_PARAMS = get_fit_params()

print("[data_analysis] imported specific_conductance successfully")
print("[data_analysis] imported KK/DRT/data_quality successfully")


def try_parse_three_floats(line: str) -> Optional[Tuple[float, float, float]]:
    """
    尝试从一行文本中解析出3个浮点数
    支持分隔符：逗号、制表符、空白
    """
    line = line.strip()
    if not line:
        return None

    for delimiter in [",", "\t", None]:
        try:
            parts = line.split(delimiter) if delimiter else line.split()
            if len(parts) < 3:
                continue
            freq = float(parts[0].strip())
            z_real = float(parts[1].strip())
            z_imag = float(parts[2].strip())
            return freq, z_real, z_imag
        except (ValueError, IndexError):
            continue

    return None


def read_chi_eis_file(filepath: str, strict_mode: bool) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """读取CHI保存的数据文件"""
    if not os.path.exists(filepath):
        msg = f"❌ 文件不存在: {filepath}"
        print(msg)
        if strict_mode:
            raise FileNotFoundError(msg)
        return None, None, None

    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    data_start_line = None
    for i, line in enumerate(lines):
        result = try_parse_three_floats(line)
        if result is not None:
            data_start_line = i
            print(f"[找到数据起始行] 第 {i + 1} 行: {line.strip()[:80]}")
            break

    if data_start_line is None:
        msg = f"❌ 未找到有效数据行（无法解析出3个浮点数）: {filepath}"
        print(msg)
        if strict_mode:
            raise ValueError(msg)
        return None, None, None

    data_rows = []
    for i in range(data_start_line, len(lines)):
        result = try_parse_three_floats(lines[i])
        if result is not None:
            data_rows.append(result)

    if len(data_rows) == 0:
        msg = f"❌ 解析到0个有效数据点: {filepath}"
        print(msg)
        if strict_mode:
            raise ValueError(msg)
        return None, None, None

    data = np.array(data_rows)
    frequencies = data[:, 0]
    z_real = data[:, 1]
    z_imag = data[:, 2]

    if len(frequencies) < 10:
        msg = f"❌ 有效数据点不足10个 ({len(frequencies)}个): {filepath}"
        print(msg)
        if strict_mode:
            raise ValueError(msg)
        return None, None, None

    print(f"✅ 成功读取 {len(frequencies)} 个数据点")
    return frequencies, z_real, z_imag


def _evaluate_quality(r_value: Optional[float], r_squared: Optional[float]) -> str:
    if r_value is not None:
        if r_value >= 0.99:
            return "good"
        if r_value >= 0.95:
            return "acceptable"
        return "poor"
    if r_squared is not None:
        if r_squared >= 0.98:
            return "good"
        if r_squared >= 0.95:
            return "acceptable"
    return "poor"


def _analyze_eis_data(
    frequencies: np.ndarray,
    z_real: np.ndarray,
    z_imag: np.ndarray,
    temperature_c: float,
    thickness_cm: float,
    area_cm2: float,
    strict_mode: bool,
    circle_dir: Optional[str] = None,
    filepath: Optional[str] = None,
) -> Dict:
    try:
        freq_arr = np.asarray(frequencies, dtype=float)
        z_real_arr = np.asarray(z_real, dtype=float)
        z_imag_arr = np.asarray(z_imag, dtype=float)

        if freq_arr.size == 0 or z_real_arr.size == 0 or z_imag_arr.size == 0:
            raise ValueError("输入数据为空")
        if freq_arr.size != z_real_arr.size or freq_arr.size != z_imag_arr.size:
            raise ValueError("频率与阻抗数据长度不一致")
        if freq_arr.size < 10:
            raise ValueError(f"有效数据点不足10个 ({freq_arr.size}个)")

        freq_filtered, zreal_filtered, zimag_filtered = filter_data(freq_arr, z_real_arr, z_imag_arr)
        print(f"[滤波] 原始点数={len(freq_arr)}, 滤波后={len(freq_filtered)}")

        phase_jump_detected = detect_phase_jump(zreal_filtered, zimag_filtered, threshold=20)

        if circle_dir:
            os.makedirs(circle_dir, exist_ok=True)

        rb_result = calculate_rb(
            zreal_filtered,
            zimag_filtered,
            temperature_c + 273.15,
            _FIT_PARAMS,
            circle_dir=circle_dir,
            freq=freq_filtered,  # 传递频率数组用于X轴交点检测
        )

        rb_value = rb_result.get("rb")
        conductivity = None
        if rb_value is not None and rb_value > 0:
            # ✅ 修复：calculate_conductivity 期望厘米和平方厘米，不需要转换！
            # thickness_cm 已经是厘米，area_cm2 已经是平方厘米
            conductivity = calculate_conductivity(rb_value, thickness_cm, area_cm2)

        r_value = rb_result.get("r")
        r_squared = None
        fit_params = rb_result.get("fit_params") or {}
        
        # ✅ 修复1：从fit_params获取（如果有）
        if r_squared is None and isinstance(fit_params, dict):
            r_squared = fit_params.get("r_squared")
            if r_value is None:
                r_value = fit_params.get("r")
        
        # ✅ 修复2：如果有r值但没有r_squared，则计算 R² = r²
        if r_value is not None and r_squared is None:
            r_squared = float(r_value) ** 2
            print(f"[data_analysis] 计算R²: r={r_value:.4f}, R²={r_squared:.4f}")

        quality = _evaluate_quality(r_value, r_squared)

        # ========== 新增：高级分析模块 ==========
        # KK一致性校验
        kk_result = None
        try:
            kk_result = kk_check(freq_filtered, zreal_filtered, zimag_filtered)
            print(f"[KK校验] {kk_result.get('message', 'N/A')}")
        except Exception as e:
            print(f"[KK校验] 失败: {e}")
            kk_result = {'ok': False, 'score': 0.0, 'message': str(e)}
        
        # DRT分析
        drt_result = None
        try:
            drt_result = drt_analyze(freq_filtered, zreal_filtered, zimag_filtered)
            n_peaks = len(drt_result.get('peaks', []))
            print(f"[DRT分析] 识别到 {n_peaks} 个弛豫峰")
        except Exception as e:
            print(f"[DRT分析] 失败: {e}")
            drt_result = {'peaks': [], 'error': str(e)}
        
        # 数据质量评估
        quality_assessment = None
        try:
            quality_assessment = assess_data_quality(
                freq_filtered, zreal_filtered, zimag_filtered, 
                temperature=temperature_c + 273.15
            )
            print(f"[数据质量] {quality_assessment.get('message', 'N/A')}")
        except Exception as e:
            print(f"[数据质量] 失败: {e}")
            quality_assessment = {'grade': 'F', 'quality_score': 0.0, 'message': str(e)}
        
        return {
            "temperature_c": temperature_c,
            "filepath": filepath,
            "n_points": len(freq_arr),
            "rb_ohm": rb_value,
            "sigma_s_per_cm": conductivity,
            "quality": quality,
            "freq_hz": freq_arr,
            "z_real_ohm": z_real_arr,
            "z_imag_ohm": z_imag_arr,
            "details": {
                "fit_method": rb_result.get("method", "未知"),
                "fit_params": fit_params,
                "phase_jump_detected": phase_jump_detected,
                "r": r_value,
                "r_squared": r_squared,
                "circle_dir": circle_dir,
                "freq_filtered": freq_filtered,
                "zreal_filtered": zreal_filtered,
                "zimag_filtered": zimag_filtered,
                "rb_result": rb_result,
            },
            # 新增的高级分析结果
            "kk_validation": kk_result,
            "drt_analysis": drt_result,
            "data_quality": quality_assessment,
        }
    except Exception as e:
        print(f"❌ 数据分析失败: {e}")
        traceback.print_exc()
        if strict_mode:
            raise
        return {
            "temperature_c": temperature_c,
            "filepath": filepath,
            "n_points": 0,
            "rb_ohm": None,
            "sigma_s_per_cm": None,
            "quality": "poor",
            "freq_hz": np.array([]),
            "z_real_ohm": np.array([]),
            "z_imag_ohm": np.array([]),
            "details": {
                "fit_method": "处理失败",
                "fit_params": None,
                "phase_jump_detected": False,
                "r": None,
                "r_squared": None,
                "circle_dir": circle_dir,
                "freq_filtered": np.array([]),
                "zreal_filtered": np.array([]),
                "zimag_filtered": np.array([]),
                "rb_result": {"error": str(e)},
            },
        }


def analyze_one_point(
    filepath: str,
    temperature_c: float,
    thickness_cm: float,
    area_cm2: float,
    strict_mode: bool,
) -> Dict:
    freq, z_real, z_imag = read_chi_eis_file(filepath, strict_mode)
    circle_dir = os.path.join(os.path.dirname(filepath) or ".", "circle_fits")
    return _analyze_eis_data(
        freq,
        z_real,
        z_imag,
        temperature_c,
        thickness_cm,
        area_cm2,
        strict_mode,
        circle_dir=circle_dir,
        filepath=filepath,
    )


def analyze_arrays(
    frequencies: np.ndarray,
    z_real: np.ndarray,
    z_imag: np.ndarray,
    temperature_c: float,
    thickness_cm: float,
    area_cm2: float,
    strict_mode: bool,
    circle_dir: Optional[str] = None,
    filepath: Optional[str] = None,
) -> Dict:
    return _analyze_eis_data(
        frequencies,
        z_real,
        z_imag,
        temperature_c,
        thickness_cm,
        area_cm2,
        strict_mode,
        circle_dir=circle_dir,
        filepath=filepath,
    )
