import cv2
import numpy as np
import pyautogui
from PIL import ImageGrab
import time


def modify_parameters(param_values, template_dir="", confidence=0.8, delay=0.3):
    """
    通过图片模板批量修改参数值（可被其他模块调用）

    参数:
        param_values (dict): {
            "Init_E": 1.23,         # 参数名: 目标值
            "High_frequency": 5000,
            "Low_Frequency": 100
        }
        template_dir (str): 模板图片目录路径（默认为当前目录）
        confidence (float): 模板匹配阈值(0-1)
        delay (float): 操作间隔时间(秒)

    返回:
        dict: {
            "Init_E": (True, "修改成功"),
            "High_frequency": (False, "错误原因"),
            ...
        }
    """
    results = {}

    # 新增：首先点击Parameters.png（仅添加这部分）
    try:
        params_template = cv2.imread(f"{template_dir}Parameters.png")
        if params_template is not None:
            screenshot = np.array(ImageGrab.grab())
            screenshot = cv2.cvtColor(screenshot, cv2.COLOR_RGB2BGR)
            res = cv2.matchTemplate(screenshot, params_template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)
            if max_val >= confidence:
                h, w = params_template.shape[:2]
                pyautogui.click(max_loc[0] + w // 2, max_loc[1] + h // 2)
                time.sleep(delay)
    except Exception:
        pass  # 静默处理，不干扰原有流程

    # 以下是原有完整逻辑（完全不变）
    for param_name, target_value in param_values.items():
        try:
            # 1. 构建模板路径
            template_path = f"{template_dir}{param_name}.png"

            # 2. 读取模板
            template = cv2.imread(template_path)
            if template is None:
                results[param_name] = (False, f"模板不存在: {template_path}")
                continue

            # 3. 屏幕匹配
            screenshot = np.array(ImageGrab.grab())
            screenshot = cv2.cvtColor(screenshot, cv2.COLOR_RGB2BGR)
            res = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)

            if max_val < confidence:
                results[param_name] = (False, f"匹配失败(相似度: {max_val:.2f})")
                continue

            # 4. 计算点击位置
            h, w = template.shape[:2]
            click_pos = (
                max_loc[0] + int(w * 0.7),  # 水平偏移
                max_loc[1] + h // 2  # 垂直居中
            )

            # 5. 执行修改
            pyautogui.doubleClick(click_pos)
            time.sleep(delay)
            pyautogui.hotkey('ctrl', 'a')
            time.sleep(delay)
            for _ in range(3):
                pyautogui.press('backspace')
                time.sleep(0.1)
            pyautogui.write(str(target_value))

            results[param_name] = (True, f"修改为: {target_value}")

        except Exception as e:
            results[param_name] = (False, f"运行时错误: {str(e)}")

    pyautogui.press('enter')
    return results
"""
    调用时候main部分这么写
from parameter_modifier import modify_parameters

# 1. 定义要修改的参数
my_parameters = {
    "Init_E": 1.23,
    "High_frequency": 5000,
    "Low_Frequency": 100
}

# 2. 调用函数（可指定模板目录）
results = modify_parameters(
    param_values=my_parameters,
    template_dir="F:/templates/",  # 可选参数
    confidence=0.75,              # 可选参数
    delay=0.2                     # 可选参数
)
"""