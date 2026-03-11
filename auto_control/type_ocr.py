import cv2
import numpy as np
import pyautogui
from PIL import ImageGrab
import time
import os

# 图片资源（同一目录下）
NAME_BOX_ICON = "name_of_dc.png"  # 文件名输入框标识
DIRECTORY_ICON = "Directory.png"  # 地址栏文件夹图标


def get_screenshot():
    """获取当前屏幕截图（BGR格式）"""
    return cv2.cvtColor(np.array(ImageGrab.grab()), cv2.COLOR_RGB2BGR)


def click_icon(icon_path, confidence=0.8, click_offset=0):
    """
    精准点击图标
    :param icon_path: 图标路径
    :param confidence: 匹配阈值(0-1)
    :param click_offset: 点击位置相对图标中心的偏移
    :return: (是否成功, 坐标或错误信息)
    """
    try:
        if not os.path.exists(icon_path):
            return False, f"图标文件缺失: {icon_path}"

        screenshot = get_screenshot()
        template = cv2.imread(icon_path)
        res = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)

        if max_val < confidence:
            return False, f"匹配失败 (相似度: {max_val:.2f})"

        # 计算点击位置（中心点+偏移）
        h, w = template.shape[:2]
        click_x = max_loc[0] + w // 2 + click_offset
        click_y = max_loc[1] + h // 2

        pyautogui.click(click_x, click_y)
        return True, (click_x, click_y)
    except Exception as e:
        return False, f"点击错误: {str(e)}"


def input_text(text, delay=0.3):
    """在焦点处输入文本"""
    try:
        pyautogui.hotkey('ctrl', 'a')
        time.sleep(delay / 2)
        pyautogui.press('backspace')
        time.sleep(delay / 2)
        pyautogui.write(text)
        time.sleep(delay)
        return True
    except Exception as e:
        print(f"输入错误: {e}")
        return False


def run_save_workflow(filename, save_path):
    """完整的保存流程（严格保持原有顺序）"""
    print("=== 文件保存流程开始 ===")
    results = {}

    # 步骤1：定位文件名输入框（点击图标右侧区域）
    print("1. 定位文件名输入框...")
    success, pos = click_icon(NAME_BOX_ICON, click_offset=15)  # 向右偏移15像素
    results["name_box"] = (success, pos if success else "定位失败")
    if not success:
        return results

    print(f"   ✅ 已定位 (点击坐标: {pos[0]}, {pos[1]})")
    time.sleep(0.5)

    # 步骤2：编辑文件名
    print(f"2. 正在修改文件名 -> {filename}")
    results["name_edit"] = input_text(filename)

    # 步骤3：定位地址栏（精准点击图标中心）
    print("3. 定位地址栏...")
    success, pos = click_icon(DIRECTORY_ICON)  # 无偏移，点击中心
    results["address_box"] = (success, pos if success else "定位失败")
    if not success:
        return results

    print(f"   ✅ 已定位 (点击坐标: {pos[0]}, {pos[1]})")
    time.sleep(0.8)  # 等待地址栏展开

    # 步骤4：编辑保存路径
    print(f"4. 正在修改路径 -> {save_path}")
    results["path_edit"] = input_text(save_path)

    # 步骤5：回车确认
    print("5. 保存文件...")
    pyautogui.press('enter')
    time.sleep(1)
    results["save"] = True
    
    print("=== 文件保存流程完成 ===")
    return results


if __name__ == "__main__":
    # 配置参数
    FILENAME = "Cu_T298_highf10000_lowf1_initV0.txt"  # 格式与原有逻辑一致
    SAVE_PATH = r"C:\Users\HP\Desktop\data"  # 原有路径格式

    # 检查资源文件
    missing = [f for f in [NAME_BOX_ICON, DIRECTORY_ICON] if not os.path.exists(f)]
    if missing:
        print("❌ 缺少必要文件:")
        print("\n".join(f" - {f}" for f in missing))
    else:
        results = run_save_workflow(FILENAME, SAVE_PATH)
        print("\n=== 执行结果 ===")
        for step, result in results.items():
            status = "✓" if result[0] else "✗"
            print(f"{step.ljust(12)}: {status} {result[1]}")