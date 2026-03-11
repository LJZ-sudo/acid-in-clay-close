import cv2
import numpy as np
import pyautogui
from PIL import ImageGrab
import time
import os


def click_template(template_path, confidence=0.8, delay=0.5):
    """改进的模板点击函数，更好地处理中文路径"""
    try:
        print(f"[DEBUG] technique_select: 尝试读取模板: {template_path}")
        
        # 方法1: 尝试使用OpenCV直接读取
        template = cv2.imread(template_path)
        if template is not None:
            print(f"[DEBUG] technique_select: OpenCV成功读取模板")
        else:
            print(f"[DEBUG] technique_select: OpenCV读取失败，尝试PIL")
            
            # 方法2: 尝试使用PIL作为备选方案
            try:
                from PIL import Image
                pil_image = Image.open(template_path)
                template = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
                print(f"[DEBUG] technique_select: PIL成功读取模板: {template_path}")
            except Exception as pil_error:
                print(f"[DEBUG] technique_select: PIL读取也失败: {pil_error}")
                
                # 方法3: 尝试使用绝对路径
                try:
                    abs_path = os.path.abspath(template_path)
                    print(f"[DEBUG] technique_select: 尝试绝对路径: {abs_path}")
                    template = cv2.imread(abs_path)
                    if template is not None:
                        print(f"[DEBUG] technique_select: 绝对路径读取成功")
                    else:
                        # 方法4: 尝试使用PIL读取绝对路径
                        pil_image = Image.open(abs_path)
                        template = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
                        print(f"[DEBUG] technique_select: PIL绝对路径读取成功")
                except Exception as abs_error:
                    print(f"[DEBUG] technique_select: 绝对路径读取失败: {abs_error}")
                    return False, f"所有方法都无法读取模板: {template_path}"

        # 获取屏幕截图
        screenshot = np.array(ImageGrab.grab())
        screenshot = cv2.cvtColor(screenshot, cv2.COLOR_RGB2BGR)
        
        # 使用单一匹配方法
        res = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)
        
        if max_val < confidence:
            return False, f"匹配度不足: {max_val:.4f} < {confidence}"
        
        # 点击目标位置
        h, w = template.shape[:2]
        click_x = max_loc[0] + w // 2
        click_y = max_loc[1] + h // 2
        
        pyautogui.click(click_x, click_y)
        time.sleep(delay)
        return True, f"成功点击: {template_path} (匹配度: {max_val:.4f})"

    except Exception as e:
        return False, f"点击错误: {str(e)}"


def setup_impedance_technique(template_dir="", confidence=0.2, delay=0.1):  # 提高默认阈值
    """
    改进版阻抗测试配置：
    1. 点击 Technique.png
    2. 点击 IMP_AC_Impedance_white.png 或 IMP_AC_Impedance_blue.png
    3. 点击 Technique_OK.png
    """
    results = {}
    
    print(f"\n=== 开始IMP_AC_Impedance模式设置 ===")
    print(f"[DEBUG] 模板目录: {template_dir}")
    
    # 检查模板文件是否存在
    # 注意：Technique.png现在在D盘根目录，其他文件仍在原目录
    technique_file = "Technique.png"
    technique_path = os.path.join(template_dir, technique_file)
    technique_exists = os.path.exists(technique_path)
    print(f"[DEBUG] {technique_file}: {'✅ 存在' if technique_exists else '❌ 不存在'} ({technique_path})")
    
    if not technique_exists:
        return {"error": f"缺少必要模板文件: {technique_file}"}
    
    # 其他文件仍在原目录，需要从原路径检查
    other_files = ["IMP_AC_Impedance_white.png", "IMP_AC_Impedance_blue.png", "Technique_OK.png"]
    original_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 获取项目根目录
    auto_control_dir = os.path.join(original_dir, 'auto_control')
    
    print(f"[DEBUG] 其他模板文件目录: {auto_control_dir}")
    for file in other_files:
        file_path = os.path.join(auto_control_dir, file)
        exists = os.path.exists(file_path)
        print(f"[DEBUG] {file}: {'✅ 存在' if exists else '❌ 不存在'} ({file_path})")
        if not exists:
            return {"error": f"缺少必要模板文件: {file}"}

    # 第一步：点击Technique
    print(f"\n[步骤1] 点击Technique按钮...")
    tech_success, tech_msg = click_template(os.path.join(template_dir, "Technique.png"), confidence, delay)
    results["Technique"] = (tech_success, tech_msg)
    print(f"[结果] Technique: {'✅ 成功' if tech_success else '❌ 失败'} - {tech_msg}")
    
    if not tech_success:
        print(f"[错误] 无法找到Technique按钮，停止流程")
        return results

    # 等待界面响应
    time.sleep(1)
    print(f"[等待] 界面响应完成")

    # 第二步：尝试点击白或蓝变体
    print(f"\n[步骤2] 选择IMP_AC_Impedance模式...")
    variants = ["IMP_AC_Impedance_white.png", "IMP_AC_Impedance_blue.png"]
    imp_success = False
    imp_msg = ""

    for i, variant in enumerate(variants, 1):
        print(f"[尝试] 变体 {i}: {variant}")
        # 从auto_control目录读取其他模板文件
        success, msg = click_template(os.path.join(auto_control_dir, variant), confidence, delay)
        print(f"[结果] {variant}: {'✅ 成功' if success else '❌ 失败'} - {msg}")
        
        if success:
            imp_success = True
            imp_msg = msg
            print(f"[成功] 找到并点击了 {variant}")
            break
        elif msg and "匹配度不足" in msg:
            print(f"[信息] {variant} 匹配度不足，尝试下一个变体")
        else:
            print(f"[错误] {variant} 识别失败: {msg}")

    results["IMP_AC_Impedance"] = (imp_success, imp_msg or "未找到任何IMP_AC_Impedance变体")
    
    if not imp_success:
        print(f"[错误] 无法找到IMP_AC_Impedance模式，停止流程")
        return results

    # 等待界面响应
    time.sleep(1)
    print(f"[等待] 模式选择完成")

    # 第三步：点击确认（从原目录）
    print(f"\n[步骤3] 点击确认按钮...")
    ok_success, ok_msg = click_template(os.path.join(auto_control_dir, "Technique_OK.png"), confidence, delay)
    results["Technique_OK"] = (ok_success, ok_msg)
    print(f"[结果] Technique_OK: {'✅ 成功' if ok_success else '❌ 失败'} - {ok_msg}")
    
    if ok_success:
        # 额外按Enter键确保确认
        time.sleep(0.5)
        pyautogui.press('enter')
        print(f"[额外] 按Enter键确认")
    
    print(f"\n=== IMP_AC_Impedance模式设置完成 ===")
    return results


def test_technique_recognition():
    """测试函数：验证模板识别功能"""
    print("=== 测试模板识别功能 ===")
    
    from path_config import TEMPLATE_DIR
    
    # 测试参数
    test_config = {
        "template_dir": TEMPLATE_DIR,
        "confidence": 0.1,
        "delay": 0.1
    }
    
    print(f"测试配置: {test_config}")
    
    # 执行测试
    result = setup_impedance_technique(**test_config)
    
    print(f"\n=== 测试结果 ===")
    for key, (success, msg) in result.items():
        status = "✅ 成功" if success else "❌ 失败"
        print(f"{key}: {status} - {msg}")
    
    return result


if __name__ == "__main__":
    test_technique_recognition()