import cv2
import numpy as np
import pyautogui
from PIL import ImageGrab
import time
import re
import os
import sys

# 统一 standalone 路径初始化
try:
    from auto_control._path_setup import ensure_close_root
except ImportError:
    from _path_setup import ensure_close_root

CLOSE_ROOT = ensure_close_root()

try:
    from utils import cv2_imread_unicode
except ImportError:
    print("[警告] 无法导入utils，使用改进的cv2.imread替代")
    def cv2_imread_unicode(path, flags=cv2.IMREAD_COLOR):
        # 尝试使用OpenCV读取
        template = cv2.imread(path, flags)
        if template is None:
            # 尝试使用PIL作为备选方案
            try:
                from PIL import Image
                pil_image = Image.open(path)
                template = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
                print(f"[DEBUG] 使用PIL成功读取模板: {path}")
            except Exception as pil_error:
                print(f"[DEBUG] PIL读取也失败: {path}, 错误: {str(pil_error)}")
                return None
        return template

# ==================== CHI测量时间映射 ====================
def get_measurement_time(highf: str, lowf: str) -> int:
    """
    根据高频和低频参数返回CHI测量的等待时间（秒）
    
    时间映射表（基于实测数据）:
    - 高频 1000000, 低频 0.1  -> 200s
    - 高频 1000000, 低频 1    -> 150s
    - 高频 100000,  低频 0.1  -> 170s
    - 高频 100000,  低频 1    -> 120s
    - 高频 1000000, 低频 0.01 -> 820s
    - 高频 100000,  低频 0.01 -> 810s
    """
    try:
        high_freq = float(highf)
        low_freq = float(lowf)
    except (ValueError, TypeError):
        print(f"[警告] 频率参数格式错误: highf={highf}, lowf={lowf}，使用默认时间220秒")
        return 220
    
    time_mapping = {
        (1000000, 0.01): 820,
        (1000000, 0.1): 200,
        (1000000, 1): 150,
        (100000, 0.01): 810,
        (100000, 0.1): 170,
        (100000, 1): 120,
    }
    
    key = (high_freq, low_freq)
    if key in time_mapping:
        base_time = time_mapping[key]
        wait_time = int(base_time * 1.05)  # 添加5%安全余量
        print(f"[时间映射] 高频={high_freq}Hz, 低频={low_freq}Hz -> 等待时间{wait_time}秒")
        return wait_time
    
    # 估算
    if low_freq <= 0.01:
        base_time = 820 if high_freq >= 500000 else 810
    elif low_freq <= 0.1:
        base_time = 200 if high_freq >= 500000 else 170
    elif low_freq <= 1:
        base_time = 150 if high_freq >= 500000 else 120
    else:
        base_time = 100
    
    wait_time = int(base_time * 1.05)
    print(f"[时间映射] 估算等待时间: {wait_time}秒")
    return wait_time
# ========================================================

# 时间识别配置（已弃用，保留兼容性）
TIME_TEMPLATE_PATH = "time_remaining.png"

def _capture_remaining_time_strict(screenshot, template_dir=""):
    """改进的时间识别函数 - 基于模板匹配定位，OCR读取具体数值"""
    try:
        # 构建完整的模板路径
        if template_dir:
            time_template_path = os.path.join(template_dir, TIME_TEMPLATE_PATH)
        else:
            time_template_path = TIME_TEMPLATE_PATH
            
        time_template = cv2_imread_unicode(time_template_path, cv2.IMREAD_GRAYSCALE)
        if time_template is None:
            print(f"[错误] 时间模板未找到: {time_template_path}")
            return 0

        gray_screen = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
        res = cv2.matchTemplate(gray_screen, time_template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)

        if max_val < 0.45:  # 降低匹配阈值，提高检测灵敏度
            print(f"[警告] 时间区域匹配度低 (相似度: {max_val:.2f})")
            return 0

        # 基于模板匹配找到时间区域
        print(f"[信息] 时间区域匹配成功 (相似度: {max_val:.2f})")
        
        # 提取时间显示区域进行OCR识别
        h, w = time_template.shape[:2]
        # 扩大识别区域，确保包含完整的数字
        roi_x = max(0, max_loc[0] - 50)
        roi_y = max(0, max_loc[1] - 10)
        roi_w = min(w + 100, gray_screen.shape[1] - roi_x)
        roi_h = min(h + 20, gray_screen.shape[0] - roi_y)
        
        time_roi = gray_screen[roi_y:roi_y+roi_h, roi_x:roi_x+roi_w]
        
        # 使用OCR识别数字
        try:
            import pytesseract
            # 预处理图像以提高OCR准确性
            # 二值化处理
            _, binary = cv2.threshold(time_roi, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            # OCR识别
            text = pytesseract.image_to_string(binary, config='--psm 7 -c tessedit_char_whitelist=0123456789.s')
            
            # 提取数字
            import re
            numbers = re.findall(r'\d+\.?\d*', text)
            
            if numbers:
                # 取第一个数字作为剩余时间
                remaining_time = float(numbers[0])
                print(f"[信息] OCR识别到剩余时间: {remaining_time}秒")
                return remaining_time
            else:
                print(f"[警告] OCR未能识别到数字，使用默认时间")
                return 98.0
                
        except ImportError:
            print(f"[警告] pytesseract未安装，使用默认时间估算")
            return 98.0
        except Exception as ocr_error:
            print(f"[警告] OCR识别失败: {ocr_error}，使用默认时间")
            return 98.0

    except Exception as e:
        print(f"[异常] 时间识别失败: {str(e)}")
        return 0

def _click_dynamic_text_box(template_path, screenshot, fixed_side, click_side, confidence, delay, fixed_text=None):
    """改进版文本框点击：纯模板匹配"""
    try:
        # 仅使用模板匹配方法
        template = cv2_imread_unicode(template_path)
        if template is not None:
            res = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)

            if max_val >= confidence:
                h, w = template.shape[:2]
                if click_side == "right":
                    click_x = max_loc[0] + w - 15
                else:
                    click_x = max_loc[0] + 15

                click_y = max_loc[1] + h // 2
                pyautogui.click(click_x, click_y)
                time.sleep(delay)
                return True, "通过模板匹配点击成功"

        return False, "无法定位文本框"

    except Exception as e:
        return False, f"文本框点击错误: {str(e)}"

def _click_template(template_path, screenshot, confidence, delay):
    """原始简单模板点击函数"""
    try:
        template = cv2_imread_unicode(template_path)
        if template is None:
            return False, f"模板图片不存在: {template_path}"

        res = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)
        
        if max_val < confidence:
            return False, f"匹配失败 (相似度: {max_val:.4f} < {confidence})"

        h, w = template.shape[:2]
        click_x = max_loc[0] + w // 2
        click_y = max_loc[1] + h // 2
        
        # 直接点击，不使用moveTo
        pyautogui.click(click_x, click_y)
        time.sleep(delay)
        return True, f"点击成功 (匹配度: {max_val:.4f})"
    except Exception as e:
        return False, f"点击错误: {str(e)}"




def _locate_address_field(template_path, screenshot, confidence=0.85):
    """改进的地址字段定位 - 增加延迟和重试机制"""
    try:
        template = cv2_imread_unicode(template_path)
        if template is None:
            return False, f"地址字段模板不存在: {template_path}"

        # 确保screenshot不为None
        if screenshot is None:
            from PIL import ImageGrab
            screenshot = np.array(ImageGrab.grab())
            screenshot = cv2.cvtColor(screenshot, cv2.COLOR_RGB2BGR)

        res = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)

        if max_val >= confidence:
            h, w = template.shape[:2]
            click_x = max_loc[0] + w // 2
            click_y = max_loc[1] + h // 2
            
            # 直接点击，不使用moveTo
            pyautogui.click(click_x, click_y)
            time.sleep(1.0)  # 增加点击后等待时间
            
            # 再次点击确保激活
            pyautogui.click(click_x, click_y)
            time.sleep(0.5)
            
            return True, f"地址字段定位成功 (匹配度: {max_val:.4f})"
        else:
            return False, f"地址字段匹配度不足: {max_val:.4f} < {confidence}"

    except Exception as e:
        return False, f"地址字段定位错误: {str(e)}"

def _edit_text_box(template_path, screenshot, text, side, confidence, delay):
    """改进的文本框编辑 - 增加延迟、重试机制和回车确认"""
    try:
        template = cv2_imread_unicode(template_path)
        if template is None:
            return False, f"文本框模板不存在: {template_path}"

        res = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)

        if max_val >= confidence:
            h, w = template.shape[:2]
            if side == "right":
                click_x = max_loc[0] + w - 15
            else:
                click_x = max_loc[0] + 15
            click_y = max_loc[1] + h // 2
            
            # 对于保存路径输入，点击左侧位置
            if "saving_position" in template_path or "Directory" in template_path:
                click_x = max_loc[0] + 30  # 点击左侧位置
            
            # 直接点击，不使用moveTo
            pyautogui.click(click_x, click_y)
            time.sleep(delay + 0.5)  # 增加点击后等待时间
            
            # 确保文本框获得焦点
            pyautogui.click(click_x, click_y)  # 再次点击确保焦点
            time.sleep(0.5)
            
            # 清空并输入文本 - 增加延迟
            pyautogui.hotkey('ctrl', 'a')
            time.sleep(0.5)  # 增加延迟
            pyautogui.press('backspace')
            time.sleep(0.5)  # 增加延迟
            
            # 分段输入文本，避免输入过快
            for char in text:
                pyautogui.write(char)
                time.sleep(0.05)  # 每个字符间隔50ms
            
            time.sleep(0.5)  # 输入完成后短暂等待
            
            # 添加回车确认输入
            pyautogui.press('enter')
            time.sleep(0.5)  # 回车后等待
            
            time.sleep(1.0)  # 最终等待时间
            
            return True, f"文本框编辑成功: {text}"
        else:
            return False, f"文本框匹配度不足: {max_val:.4f} < {confidence}"

    except Exception as e:
        return False, f"文本框编辑错误: {str(e)}"

def run_chi_measurement(
        material: str,
        T: str,
        highf: str,
        lowf: str,
        initV: str,
        your_position: str,
        your_type_text: str,
        template_dir: str = "",
        confidence: float = 0.5,  # 适中的匹配阈值
        text_confidence: int = 70,
        delay: float = 0.5
) -> dict:
    """完整的CHI测量流程：开始测量 → 等待完成 → 保存结果"""
    results = {}
    
    print(f"\n=== 开始完整CHI测量流程 ===")
    print(f"[配置] 材料: {material}, 温度: {T}K")
    print(f"[配置] 频率范围: {lowf}-{highf}Hz, 初始电位: {initV}V")
    print(f"[配置] 保存路径: {your_position}")
    print(f"[配置] 模板目录: {template_dir}")

    def get_screenshot():
        return np.array(ImageGrab.grab())

    # 验证保存路径
    try:
        os.makedirs(your_position, exist_ok=True)
        print(f"[验证] 保存目录已创建/验证: {your_position}")
    except Exception as e:
        print(f"[错误] 无法创建保存目录: {e}")
        return {"error": f"保存目录创建失败: {e}"}

    # 第一步：点击开始测量按钮
    print(f"\n[步骤1] 点击开始测量按钮...")
    start_measure_path = os.path.join(template_dir, "start_to_measure.png")
    success, msg = _click_template(start_measure_path, get_screenshot(), confidence, delay)
    results["start_measure"] = (success, msg)
    print(f"[结果] 开始测量: {'✅ 成功' if success else '❌ 失败'} - {msg}")
    if not success:
        return results

    # 第二步：初始等待8秒
    print(f"\n[步骤2] 初始等待8秒...")
    time.sleep(8)
    results["initial_wait"] = (True, "初始等待完成")

    # 第三步：根据频率参数计算等待时间
    print(f"\n[步骤3] 等待测量完成...")
    
    # 使用时间映射函数计算等待时间
    wait_seconds = get_measurement_time(highf, lowf)
    print(f"[信息] CHI测量频率范围: {lowf}Hz - {highf}Hz")
    print(f"[信息] 计算等待时间: {wait_seconds}秒")
    print(f"[信息] 等待CHI测量完成...")
    
    time.sleep(wait_seconds)
    results["wait_time"] = (True, f"等待完成 ({wait_seconds}s)")

    # 第四步：点击另存为
    print(f"\n[步骤4] 点击另存为...")
    save_as_path = os.path.join(template_dir, "save_as.png")
    success, msg = _click_template(save_as_path, get_screenshot(), confidence, delay)
    results["save_as"] = (success, msg)
    print(f"[结果] 另存为: {'✅ 成功' if success else '❌ 失败'} - {msg}")
    if not success:
        return results

    # 第五步：点击保存类型
    print(f"\n[步骤5] 点击保存类型...")
    type_saving_path = os.path.join(template_dir, "type_saving.png")
    
    # 使用成功的匹配阈值，确保能找到保存类型按钮
    type_success = False
    type_msg = ""
    type_confidence_levels = [0.5, 0.4, 0.3, 0.2, 0.1]  # 成功的匹配阈值
    
    for i, conf in enumerate(type_confidence_levels, 1):
        print(f"[尝试] 保存类型第{i}次尝试，匹配阈值: {conf}")
        type_success, type_msg = _click_template(type_saving_path, get_screenshot(), conf, delay)
        if type_success:
            print(f"[成功] 保存类型点击成功，使用阈值: {conf}")
            break
        else:
            print(f"[失败] 保存类型第{i}次尝试失败: {type_msg}")
            time.sleep(0.8)  # 增加等待时间后重试
    
    results["type_saving"] = (type_success, type_msg)
    print(f"[结果] 保存类型: {'✅ 成功' if type_success else '❌ 失败'} - {type_msg}")
    
    # 如果保存类型点击成功，添加确认
    if type_success:
        print(f"[确认] 保存类型点击成功，等待下拉菜单展开...")
        time.sleep(0.8)  # 等待下拉菜单展开
        print(f"[确认] 保存类型下拉菜单已展开")
    else:
        print(f"[警告] 保存类型点击失败，但继续尝试后续步骤...")
        # 不直接返回，继续尝试后续步骤

    # 第六步：点击指定类型
    print(f"\n[步骤6] 选择文件类型...")
    white_path = os.path.join(template_dir, "your_type_white.png")
    blue_path = os.path.join(template_dir, "your_type_blue.png")
    
    # 使用成功的匹配阈值，确保能找到文件类型选项
    file_type_success = False
    file_type_msg = ""
    file_type_confidence_levels = [0.5, 0.4, 0.3, 0.2, 0.1]  # 成功的匹配阈值
    
    for i, conf in enumerate(file_type_confidence_levels, 1):
        print(f"[尝试] 文件类型第{i}次尝试，匹配阈值: {conf}")
        # 先尝试白色类型
        file_type_success, file_type_msg = _click_template(white_path, get_screenshot(), conf, delay)
        if not file_type_success:
            print(f"[尝试] 白色类型失败，尝试蓝色类型...")
            file_type_success, file_type_msg = _click_template(blue_path, get_screenshot(), conf, delay)
        
        if file_type_success:
            print(f"[成功] 文件类型选择成功，使用阈值: {conf}")
            break
        else:
            print(f"[失败] 文件类型第{i}次尝试失败: {file_type_msg}")
            time.sleep(0.8)  # 增加等待时间后重试
    
    results["your_type"] = (file_type_success, file_type_msg)
    print(f"[结果] 文件类型: {'✅ 成功' if file_type_success else '❌ 失败'} - {file_type_msg}")
    
    # 如果文件类型选择成功，等待下拉菜单展开
    if file_type_success:
        print(f"[确认] 文件类型选择成功，等待下拉菜单展开...")
        time.sleep(0.8)  # 等待下拉菜单完全展开
        print(f"[确认] 文件类型选择完成，下拉菜单已展开")
    else:
        print(f"[警告] 文件类型选择失败，但继续尝试后续步骤...")
        # 不直接返回，继续尝试后续步骤

    # 第七步：编辑文件名
    print(f"\n[步骤7] 编辑文件名...")
    # 使用更简单的文件名格式，避免特殊字符
    filename = f"{material}_T{T}_f{lowf}_{highf}_V{initV}"
    name_of_dc_path = os.path.join(template_dir, "name_of_dc.png")
    
    # 使用成功的匹配阈值，确保能找到文件名输入框
    name_success = False
    name_msg = ""
    name_confidence_levels = [0.7, 0.6, 0.5, 0.4]  # 成功的匹配阈值
    
    for i, conf in enumerate(name_confidence_levels, 1):
        print(f"[尝试] 文件名编辑第{i}次尝试，匹配阈值: {conf}")
        name_success, name_msg = _edit_text_box(name_of_dc_path, get_screenshot(), filename, "right", conf, delay)
        if name_success:
            print(f"[成功] 文件名编辑成功，使用阈值: {conf}")
            break
        else:
            print(f"[失败] 文件名编辑第{i}次尝试失败: {name_msg}")
            time.sleep(1.0)  # 增加等待时间后重试
    
    results["name_edit"] = (name_success, name_msg)
    print(f"[结果] 文件名编辑: {'✅ 成功' if name_success else '❌ 失败'} - {name_msg}")
    if not name_success:
        print(f"[警告] 文件名编辑失败，但继续尝试后续步骤...")
        # 不直接返回，继续尝试后续步骤

    # 第八步：点击目录图标
    print(f"\n[步骤8] 点击目录图标...")
    directory_icon_path = os.path.join(template_dir, "Directory.png")
    
    # 使用成功的匹配阈值，确保能找到目录图标
    success = False
    msg = ""
    confidence_levels = [0.5, 0.4, 0.3, 0.2, 0.1]  # 成功的匹配阈值
    
    for i, conf in enumerate(confidence_levels, 1):
        print(f"[尝试] 第{i}次尝试，匹配阈值: {conf}")
        success, msg = _locate_address_field(directory_icon_path, get_screenshot(), conf)
        if success:
            print(f"[成功] 目录点击成功，使用阈值: {conf}")
            break
        else:
            print(f"[失败] 第{i}次尝试失败: {msg}")
            time.sleep(0.8)  # 增加等待时间后重试
    
    results["directory_click"] = (success, msg)
    print(f"[结果] 目录点击: {'✅ 成功' if success else '❌ 失败'} - {msg}")
    if not success:
        print(f"[警告] 目录点击失败，但继续尝试后续步骤...")
        # 不直接返回，继续尝试后续步骤

    # 第九步：输入保存路径
    print(f"\n[步骤9] 输入保存路径...")
    try:
        print(f"[输入] 路径: {your_position}")
        
        # 使用saving_position.png模板定位保存路径输入框
        saving_position_path = os.path.join(template_dir, "saving_position.png")
        
        # 使用成功的匹配阈值，确保能找到路径输入框
        path_success = False
        path_msg = ""
        path_confidence_levels = [0.5, 0.4, 0.3, 0.2, 0.1]  # 成功的匹配阈值
        
        for i, conf in enumerate(path_confidence_levels, 1):
            print(f"[尝试] 保存路径输入框第{i}次尝试，匹配阈值: {conf}")
            path_success, path_msg = _edit_text_box(saving_position_path, get_screenshot(), your_position, "right", conf, delay)
            if path_success:
                print(f"[成功] 保存路径输入成功，使用阈值: {conf}")
                break
            else:
                print(f"[失败] 保存路径输入第{i}次尝试失败: {path_msg}")
                time.sleep(0.8)  # 增加等待时间后重试
        
        if not path_success:
            print(f"[警告] 保存路径输入失败，尝试备用方法...")
            # 备用方法：使用Tab键导航
            try:
                # 多次按Tab键确保焦点在路径输入框
                for i in range(3):
                    pyautogui.press('tab')
                    time.sleep(0.3)
                
                # 清空并输入路径 - 增加延迟
                pyautogui.hotkey('ctrl', 'a')
                time.sleep(0.8)  # 增加延迟
                pyautogui.press('backspace')
                time.sleep(0.8)  # 增加延迟
                
                # 分段输入路径，避免输入过快
                path_parts = your_position.split('\\')
                for i, part in enumerate(path_parts):
                    pyautogui.write(part)
                    time.sleep(0.1)  # 每个路径段间隔100ms
                    if i < len(path_parts) - 1:
                        pyautogui.write('\\')
                        time.sleep(0.05)
                
                time.sleep(0.5)  # 输入完成后短暂等待
                
                # 添加回车确认输入
                pyautogui.press('enter')
                time.sleep(0.5)  # 回车后等待
                
                time.sleep(1.5)  # 最终等待时间
                
                path_success = True
                path_msg = "通过Tab键导航输入路径成功"
                print(f"[成功] 备用方法输入路径成功")
            except Exception as e:
                path_success = False
                path_msg = f"备用方法也失败: {str(e)}"
                print(f"[失败] 备用方法输入路径失败: {str(e)}")
        
        results["path_input"] = (path_success, path_msg)
        print(f"[结果] 路径输入: {'✅ 成功' if path_success else '❌ 失败'} - {path_msg}")
        if not path_success:
            print(f"[警告] 路径输入失败，但继续尝试后续步骤...")
            # 不直接返回，继续尝试保存按钮
    except Exception as e:
        results["path_input"] = (False, f"路径输入失败: {str(e)}")
        print(f"[结果] 路径输入: ❌ 失败 - {str(e)}")
        # 不直接返回，继续尝试保存按钮

    # 第十步：点击保存按钮
    print(f"\n[步骤10] 点击保存按钮...")
    
    # 选择保存方法：1=模板匹配，2=固定位置，3=键盘快捷键
    # 注意：save_as.png是"另存为"按钮，不是"保存"按钮
    # 所以模板匹配可能找不到真正的保存按钮，建议使用键盘快捷键
    save_method = 3  # 默认使用键盘快捷键方法（最可靠）
    
    if save_method == 1:
        # 方法1：模板匹配（视觉识别）
        print(f"[方法1] 使用模板匹配（视觉识别）...")
        # 使用正确的保存按钮模板
        save_button_path = os.path.join(template_dir, "save_as.png")  # 修复：使用正确的保存按钮模板
        
        # 使用成功的匹配阈值，确保光标能停在保存图标上
        save_success = False
        save_msg = ""
        save_confidence_levels = [0.7, 0.5, 0.45, 0.3, 0.2]  # 成功的匹配阈值
        
        for i, conf in enumerate(save_confidence_levels, 1):
            print(f"[尝试] 保存按钮第{i}次尝试，匹配阈值: {conf}")
            save_success, save_msg = _click_template(save_button_path, get_screenshot(), conf, delay)
            if save_success:
                print(f"[成功] 保存按钮点击成功，使用阈值: {conf}")
                break
            else:
                print(f"[失败] 保存按钮第{i}次尝试失败: {save_msg}")
                time.sleep(0.8)  # 增加等待时间后重试
    
    elif save_method == 2:
        # 方法2：固定位置点击（推荐）
        print(f"[方法2] 使用固定位置点击...")
        try:
            # 获取屏幕尺寸
            screen_width, screen_height = pyautogui.size()
            print(f"[信息] 屏幕尺寸: {screen_width}x{screen_height}")
            
            # 保存按钮的固定位置（根据你的屏幕调整）
            # 这些位置需要根据你的CHI软件界面调整
            save_positions = [
                (screen_width - 150, screen_height - 100),  # 右下角
                (screen_width - 100, screen_height - 80),   # 右下角偏上
                (screen_width - 200, screen_height - 120),  # 右下角偏左
                (screen_width // 2, screen_height - 100),   # 底部中央
            ]
            
            save_success = False
            save_msg = ""
            
            for i, (x, y) in enumerate(save_positions, 1):
                print(f"[固定位置] 尝试位置{i}: ({x}, {y})")
                pyautogui.click(x, y)
                time.sleep(1.0)
                
                # 检查是否保存成功
                expected_filename = f"{filename}.txt"
                expected_filepath = os.path.join(your_position, expected_filename)
                
                if os.path.exists(expected_filepath):
                    print(f"[固定位置成功] 位置{i}点击成功，文件已保存！")
                    save_success = True
                    save_msg = f"通过固定位置{i}保存成功"
                    break
                else:
                    print(f"[固定位置失败] 位置{i}点击失败，文件未保存")
                    time.sleep(0.5)
            
            if not save_success:
                save_msg = "所有固定位置都失败"
                
        except Exception as e:
            save_success = False
            save_msg = f"固定位置方法异常: {e}"
    
    elif save_method == 3:
        # 步骤10：识别并点击保存按钮（与run_analysis.py保持一致）
        print(f"\n[步骤10] 识别并点击保存按钮...")
        print(f"[DEBUG] 🆕 这是新版本的保存按钮识别代码！")
        print(f"[DEBUG] 🆕 如果你看到这个消息，说明新代码正在运行")
        print(f"[DEBUG] 🆕 如果你看到旧版本的输出，说明代码没有更新")
        
        try:
            print(f"[信息] 开始识别保存按钮...")
            save_button_path = os.path.join(template_dir, "bao_cun.png")
            
            # 检查模板文件是否存在
            print(f"[调试] 保存按钮模板路径: {save_button_path}")
            if not os.path.exists(save_button_path):
                print(f"[错误] 保存按钮模板文件不存在: {save_button_path}")
                save_msg = f"模板文件不存在: {save_button_path}"
                save_success = False
            else:
                print(f"[调试] 保存按钮模板文件存在，开始识别...")
                
                # 使用多种匹配阈值进行保存按钮识别，降低阈值提高识别成功率
                save_success = False
                save_msg = ""
                save_confidence_levels = [0.6, 0.5, 0.4, 0.3, 0.25, 0.2, 0.15, 0.1]  # 进一步降低阈值
                
                for i, conf in enumerate(save_confidence_levels, 1):
                    print(f"[尝试] 保存按钮识别第{i}次尝试，匹配阈值: {conf}")
                    
                    # 获取当前截图
                    current_screenshot = get_screenshot()
                    print(f"[调试] 截图尺寸: {current_screenshot.shape}")
                    
                    # 尝试识别保存按钮
                    try:
                        # 使用改进的模板读取函数，支持中文路径
                        template = cv2_imread_unicode(save_button_path)
                        if template is None:
                            save_msg = f"无法读取保存按钮模板: {save_button_path}"
                            print(f"[失败] {save_msg}")
                            continue
                        
                        print(f"[调试] 模板尺寸: {template.shape}")
                        
                        # 进行模板匹配
                        result = cv2.matchTemplate(current_screenshot, template, cv2.TM_CCOEFF_NORMED)
                        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
                        
                        # 输出详细的匹配度信息
                        print(f"[调试] 最大匹配度: {max_val:.3f}, 阈值: {conf}, 位置: {max_loc}")
                        print(f"[调试] 匹配度详情: 最小值={min_val:.3f}, 最大值={max_val:.3f}")
                        
                        # 如果匹配度很低，输出更多调试信息
                        if max_val < 0.3:
                            print(f"[调试] 匹配度过低，可能原因:")
                            print(f"[调试] - 保存按钮不在当前截图中")
                            print(f"[调试] - 模板图片与实际按钮不匹配")
                            print(f"[调试] - 截图时机不对，保存对话框未完全显示")
                            print(f"[调试] - 屏幕分辨率或缩放设置问题")
                        
                        if max_val >= conf:
                            # 找到匹配的保存按钮，计算点击位置
                            h, w = template.shape[:2]
                            click_x = max_loc[0] + w // 2
                            click_y = max_loc[1] + h // 2
                            
                            print(f"[成功] 保存按钮识别成功，匹配度: {max_val:.3f}, 位置: ({click_x}, {click_y})")
                            
                            # 点击识别出的保存按钮
                            try:
                                print(f"[调试] 准备点击位置: ({click_x}, {click_y})")
                                pyautogui.click(click_x, click_y)
                                time.sleep(delay)
                                save_success = True
                                save_msg = f"成功点击识别出的保存按钮，匹配度: {max_val:.3f}"
                                print(f"[成功] 保存按钮点击成功")
                                break
                            except Exception as click_error:
                                save_msg = f"点击保存按钮失败: {str(click_error)}"
                                print(f"[失败] 点击失败: {save_msg}")
                                continue
                        else:
                            save_msg = f"匹配度不足: {max_val:.3f} < {conf}"
                            print(f"[失败] {save_msg}")
                            
                    except Exception as e:
                        save_msg = f"保存按钮识别异常: {str(e)}"
                        print(f"[异常] {save_msg}")
                        continue
                    
                    # 如果当前阈值失败，等待后尝试下一个阈值
                    if not save_success:
                        print(f"[调试] 第{i}次尝试失败，等待0.5秒后尝试下一个阈值...")
                        time.sleep(0.5)
                
                # 输出保存按钮识别的总结信息
                if save_success:
                    print(f"[总结] 保存按钮识别成功！")
                    print(f"[总结] 最终匹配度: {save_msg}")
                else:
                    print(f"[总结] 保存按钮识别失败！")
                    print(f"[总结] 尝试了 {len(save_confidence_levels)} 个不同的匹配阈值")
                    print(f"[总结] 从 {save_confidence_levels[0]} 到 {save_confidence_levels[-1]}")
                    print(f"[总结] 失败原因: {save_msg}")
                
                # 如果保存按钮识别和点击失败，尝试备用方案
                if not save_success:
                    print(f"[尝试] 保存按钮识别失败，尝试备用方案...")
                    
                    # 备用方案1：尝试按Enter键
                    try:
                        print(f"[备用] 尝试按Enter键保存...")
                        pyautogui.press('enter')
                        time.sleep(2.0)  # 等待更长时间让保存完成
                        
                        # 验证文件是否真的保存成功
                        expected_filename = f"{filename}.txt"
                        expected_filepath = os.path.join(your_position, expected_filename)
                        
                        if os.path.exists(expected_filepath):
                            save_success = True
                            save_msg = "通过Enter键成功保存"
                            print(f"[结果] 通过Enter键保存: ✅ 成功")
                        else:
                            print(f"[备用] Enter键保存失败，文件未找到: {expected_filepath}")
                            save_success = False
                            save_msg = "Enter键保存失败，文件未找到"
                            
                    except Exception as e:
                        print(f"[备用] Enter键保存失败: {e}")
                        save_success = False
                        save_msg = f"Enter键保存异常: {str(e)}"
                        
                        # 备用方案2：尝试按Ctrl+S
                        try:
                            print(f"[备用] 尝试按Ctrl+S保存...")
                            pyautogui.hotkey('ctrl', 's')
                            time.sleep(2.0)  # 等待更长时间
                            
                            # 验证文件是否真的保存成功
                            if os.path.exists(expected_filepath):
                                save_success = True
                                save_msg = "通过Ctrl+S成功保存"
                                print(f"[结果] 通过Ctrl+S保存: ✅ 成功")
                            else:
                                print(f"[备用] Ctrl+S保存失败，文件未找到: {expected_filepath}")
                                save_success = False
                                save_msg = "Ctrl+S保存失败，文件未找到"
                                
                        except Exception as e2:
                            print(f"[备用] Ctrl+S保存也失败: {e2}")
                            save_success = False
                            save_msg = f"所有保存方法都失败: 识别失败 + Enter失败 + Ctrl+S失败"
                
        except Exception as e:
            save_success = False
            save_msg = f"保存按钮识别异常: {str(e)}"
            print(f"[异常] {save_msg}")
    
    results["save_button"] = (save_success, save_msg)
    print(f"[结果] 保存按钮: {'✅ 成功' if save_success else '❌ 失败'} - {save_msg}")
    
    # 如果保存按钮也失败，强制使用备用方法
    if not save_success:
        print(f"[强制] 保存按钮点击失败，强制使用备用方法...")
        
        # 方法1：强制点击保存按钮的常见位置
        try:
            print(f"[强制尝试] 方法1: 强制点击保存按钮位置...")
            # 保存按钮通常在对话框右下角，尝试多个位置
            screen_width, screen_height = pyautogui.size()
            
            # 尝试多个可能的保存按钮位置
            save_positions = [
                (screen_width - 150, screen_height - 100),  # 右下角
                (screen_width - 100, screen_height - 80),   # 右下角偏上
                (screen_width - 200, screen_height - 120),  # 右下角偏左
                (screen_width // 2, screen_height - 100),   # 底部中央
            ]
            
            for i, (x, y) in enumerate(save_positions, 1):
                print(f"[强制尝试] 位置{i}: ({x}, {y})")
                pyautogui.click(x, y)
                time.sleep(1.0)
                
                # 检查是否保存成功（通过检查文件是否存在）
                expected_filename = f"{filename}.txt"
                expected_filepath = os.path.join(your_position, expected_filename)
                
                if os.path.exists(expected_filepath):
                    print(f"[强制成功] 位置{i}点击成功，文件已保存！")
                    results["save_button"] = (True, f"通过位置{i}点击保存成功")
                    break
                else:
                    print(f"[强制失败] 位置{i}点击失败，文件未保存")
                    time.sleep(0.5)
            else:
                print(f"[强制失败] 所有位置都失败，尝试键盘方法...")
                
                # 方法2：强制使用键盘保存
                try:
                    print(f"[强制尝试] 方法2: 强制使用Ctrl+S...")
                    pyautogui.hotkey('ctrl', 's')
                    time.sleep(2.0)  # 等待更长时间
                    
                    # 再次检查文件
                    if os.path.exists(expected_filepath):
                        print(f"[强制成功] Ctrl+S保存成功！")
                        results["save_button"] = (True, "通过Ctrl+S强制保存成功")
                    else:
                        print(f"[强制失败] Ctrl+S也失败，尝试Enter键...")
                        
                        # 方法3：强制使用Enter键
                        pyautogui.press('enter')
                        time.sleep(2.0)
                        
                        if os.path.exists(expected_filepath):
                            print(f"[强制成功] Enter键保存成功！")
                            results["save_button"] = (True, "通过Enter键强制保存成功")
                        else:
                            print(f"[强制失败] 所有方法都失败")
                            results["save_button"] = (False, "所有强制保存方法都失败")
                            
                except Exception as e:
                    print(f"[强制失败] 键盘方法异常: {e}")
                    results["save_button"] = (False, f"键盘方法异常: {e}")
                    
        except Exception as e:
            print(f"[强制失败] 位置点击方法异常: {e}")
            results["save_button"] = (False, f"位置点击方法异常: {e}")
    
    # 第十一步：等待保存完成并验证
    print(f"\n[步骤11] 等待保存完成并验证...")
    try:
        # 等待保存对话框关闭
        time.sleep(3.0)
        print(f"[等待] 已等待3秒让保存对话框关闭")
        
        # 验证文件是否真的保存了
        expected_filename = f"{filename}.txt"
        expected_filepath = os.path.join(your_position, expected_filename)
        
        if os.path.exists(expected_filepath):
            file_size = os.path.getsize(expected_filepath)
            print(f"✅ 文件保存验证成功: {expected_filename}")
            print(f"✅ 文件大小: {file_size} 字节")
            results["file_verification"] = (True, f"文件已保存: {expected_filename} ({file_size} bytes)")
        else:
            print(f"❌ 文件保存验证失败: {expected_filepath} 不存在")
            results["file_verification"] = (False, f"文件未找到: {expected_filepath}")
            
    except Exception as e:
        print(f"❌ 文件验证失败: {e}")
        results["file_verification"] = (False, f"验证异常: {e}")
    
    print(f"\n=== 完整CHI测量流程完成 ===")
    return results

if __name__ == "__main__":
    # 获取当前脚本所在目录作为模板目录
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 测试配置
    params = {
        "material": "Sample",
        "T": "298",
        "highf": "10000",
        "lowf": "1",
        "initV": "0",
        "your_position": os.path.join(os.path.dirname(os.path.dirname(current_dir)), "test"),
        "your_type_text": "Text Files",
        "template_dir": current_dir,
        "text_confidence": 70,
        "delay": 0.1
    }

    print(f"[信息] 使用模板目录: {current_dir}")
    print("[信息] 确保CHI软件正在运行并准备开始测量")

    # 自动创建目录
    os.makedirs(params["your_position"], exist_ok=True)

    # 执行并打印结果
    result = run_chi_measurement(**params)
    
    print("\n" + "="*50)
    print("CHI自动化测量完成!")
    print("="*50)
    for step, (success, msg) in result.items():
        status = "✅ 成功" if success else "❌ 失败"
        print(f"{step.ljust(15)}: {status} - {msg}")
    
    # 统计结果
    success_count = sum(1 for success, _ in result.values() if success)
    total_count = len(result)
    success_rate = (success_count / total_count) * 100
    
    print(f"\n📊 成功率: {success_count}/{total_count} ({success_rate:.1f}%)")
    
    if success_rate == 100:
        print("🎉 完美执行！所有步骤都成功了！")
    elif success_rate >= 80:
        print("😊 执行良好！大部分步骤成功")
    else:
        print("⚠️ 需要检查失败的步骤")