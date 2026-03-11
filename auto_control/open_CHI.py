import cv2
import numpy as np
import pyautogui
from PIL import ImageGrab
import time
import os


def click_template(template_name, template_dir="", confidence=0.8, delay=0.5):
    """
    原始简单模板点击函数 - 已修复中文路径问题
    :param template_name: 模板文件名（如"open_CHI.png"）
    :param template_dir: 模板目录路径
    :param confidence: 匹配阈值(0-1)
    :param delay: 点击后延迟(秒)
    :return: (是否成功, 错误信息)
    """
    try:
        # 1. 构建模板文件路径
        if template_dir:
            template_path = os.path.join(template_dir, template_name)
        else:
            template_path = template_name
        
        print(f"[DEBUG] 尝试读取模板文件: {os.path.basename(template_path)}")
        print(f"[DEBUG] 完整路径: {template_path}")
        
        # 检查文件是否存在
        if not os.path.exists(template_path):
            return False, f"模板文件不存在: {template_path}"
        
        # 优先使用PIL读取模板(避免OpenCV的中文路径问题)
        template = None
        try:
            from PIL import Image
            # 直接使用PIL读取，避免中文路径编码问题
            pil_image = Image.open(template_path)
            template = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
            print(f"[DEBUG] ✅ 使用PIL成功读取模板: {os.path.basename(template_path)}")
        except Exception as pil_error:
            print(f"[DEBUG] PIL读取失败，尝试OpenCV: {str(pil_error)}")
            # 备选方案：使用OpenCV读取
            try:
                # 使用cv2.imdecode避免中文路径问题
                with open(template_path, 'rb') as f:
                    img_data = f.read()
                img_array = np.frombuffer(img_data, np.uint8)
                template = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
                if template is not None:
                    print(f"[DEBUG] ✅ 使用OpenCV decode成功读取模板")
                else:
                    raise Exception("OpenCV decode失败")
            except Exception as cv_error:
                return False, f"模板文件读取失败: {os.path.basename(template_path)}\nPIL错误: {str(pil_error)}\nOpenCV错误: {str(cv_error)}"
        
        if template is None:
            return False, f"无法读取模板文件: {os.path.basename(template_path)}"

        # 2. 屏幕匹配
        screenshot = np.array(ImageGrab.grab())
        screenshot = cv2.cvtColor(screenshot, cv2.COLOR_RGB2BGR)
        res = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)

        if max_val < confidence:
            return False, f"匹配失败(相似度: {max_val:.2f})"

        # 3. 计算并点击中心位置
        h, w = template.shape[:2]
        center_x = max_loc[0] + w // 2
        center_y = max_loc[1] + h // 2
        pyautogui.click(center_x, center_y)
        time.sleep(delay)

        return True, "点击成功"

    except Exception as e:
        return False, f"运行时错误: {str(e)}"


def open_chi_instrument(template_dir="", confidence=0.8, delay=0.5):
    """
    专用函数：打开CHI仪器界面
    :param template_dir: 模板目录路径
    :param confidence: 匹配阈值
    :param delay: 点击后延迟
    :return: (是否成功, 错误信息)
    """
    print(f"[DEBUG] CHI仪器连接测试开始...")
    print(f"[DEBUG] 模板目录: {template_dir}")
    print(f"[DEBUG] 匹配阈值: {confidence}")
    
    result = click_template("open_CHI.png", template_dir, confidence, delay)
    
    if result[0]:
        print(f"[DEBUG] ✅ CHI界面检测成功")
    else:
        print(f"[DEBUG] ❌ CHI界面检测失败: {result[1]}")
    
    return result
"""
from open_CHI import open_chi_instrument

# 示例1：基本调用
success, message = open_chi_instrument(
    template_dir="",  # 模板存放目录
    confidence=0.85,                         # 提高匹配阈值
    delay=1.0                                # 延长操作间隔
)
"""