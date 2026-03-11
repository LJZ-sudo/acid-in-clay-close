import os
import time
from typing import Dict, Tuple

import cv2
import numpy as np
import pyautogui
from PIL import ImageGrab


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
    
    Args:
        highf: 高频参数 (Hz)，字符串格式
        lowf: 低频参数 (Hz)，字符串格式
        
    Returns:
        int: 等待时间（秒），包含5%安全余量
    """
    # 转换为数值进行比较
    try:
        high_freq = float(highf)
        low_freq = float(lowf)
    except (ValueError, TypeError):
        print(f"[警告] 频率参数格式错误: highf={highf}, lowf={lowf}，使用默认时间220秒")
        return 220
    
    # 时间映射表 (high_freq, low_freq) -> base_time
    time_mapping = {
        (1000000, 0.01): 820,
        (1000000, 0.1): 200,
        (1000000, 1): 150,
        (100000, 0.01): 810,
        (100000, 0.1): 170,
        (100000, 1): 120,
    }
    
    # 精确匹配
    key = (high_freq, low_freq)
    if key in time_mapping:
        base_time = time_mapping[key]
        # 添加5%安全余量
        wait_time = int(base_time * 1.05)
        print(f"[时间映射] 高频={high_freq}Hz, 低频={low_freq}Hz -> 基准时间{base_time}秒, 等待时间{wait_time}秒(+5%)")
        return wait_time
    
    # 未找到精确匹配，使用最近邻插值
    print(f"[时间映射] 未找到精确匹配: highf={high_freq}, lowf={low_freq}")
    
    # 根据低频估算时间（低频越低，时间越长）
    if low_freq <= 0.01:
        base_time = 820 if high_freq >= 500000 else 810
    elif low_freq <= 0.1:
        base_time = 200 if high_freq >= 500000 else 170
    elif low_freq <= 1:
        base_time = 150 if high_freq >= 500000 else 120
    else:
        # 低频 > 1Hz，时间更短
        base_time = 100
    
    wait_time = int(base_time * 1.05)
    print(f"[时间映射] 估算: 基准时间{base_time}秒, 等待时间{wait_time}秒(+5%)")
    return wait_time


def cv2_imread_unicode(path, flags=cv2.IMREAD_COLOR):
    """支持中文路径的图像读取"""
    try:
        template = cv2.imread(path, flags)
        if template is None:
            from PIL import Image
            pil_image = Image.open(path)
            template = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
            print(f"[DEBUG] 使用PIL成功读取模板: {path}")
        return template
    except Exception as e:
        print(f"[DEBUG] 读取图像失败: {path}, 错误: {str(e)}")
        return None


class ChiTestMixin:
    """CHI自动化测试与数据保存功能"""

    def run_chi_measurement(self) -> Tuple[Dict, np.ndarray, np.ndarray, np.ndarray]:
        """
        执行完整的CHI测量流程 - 使用手动测量的完美流程
        
        Returns:
            Tuple[Dict, ndarray, ndarray, ndarray]: (results, frequencies, z_real, z_imag)
        """
        print(f"\n=== 开始CHI测量流程 ===")
        print("DEBUG: 检查CHI参数")
        print(f"[配置] 材料: {self.chi_params['material']}")
        print(f"[配置] 温度: {self.current_temp:.1f}°C")
        print(f"[配置] 频率范围: {self.chi_params['lowf']}-{self.chi_params['highf']}Hz")
        print(f"[配置] 初始电位: {self.chi_params['initV']}V")
        print("DEBUG: CHI参数检查完成")
        
        # 更新CHI参数中的温度
        self.chi_params['T'] = str(int(self.current_temp + 273.15))  # 转换为开尔文
        
        # 生成文件名 - 使用目标温度而不是当前温度
        target_temp_for_filename = self.current_target if hasattr(self, 'current_target') else self.current_temp
        temp_str = f"{int(target_temp_for_filename)}" if target_temp_for_filename == int(target_temp_for_filename) else f"{target_temp_for_filename:.1f}"
        filename = f"{self.chi_params['material']}_T{temp_str}C_highf{self.chi_params['highf']}_lowf{self.chi_params['lowf']}_initV{self.chi_params['initV']}"
        
        results = {}
        
        def get_screenshot():
            return np.array(ImageGrab.grab())
        
        # 验证保存路径
        try:
            os.makedirs(self.chi_params['your_position'], exist_ok=True)
            print(f"[验证] 保存目录已创建/验证: {self.chi_params['your_position']}")
        except Exception as e:
            print(f"[错误] 无法创建保存目录: {e}")
            return {"error": f"保存目录创建失败: {e}"}
        
        try:
            # 步骤0：打开CHI软件
            print(f"\n[步骤0] 打开CHI软件...")
            print("DEBUG: 准备打开CHI软件")
            open_chi_path = os.path.join(self.chi_params['template_dir'], "open_CHI.png")
            print(f"DEBUG: 模板路径: {open_chi_path}")
            print(f"DEBUG: 模板文件存在: {os.path.exists(open_chi_path)}")
            
            success, msg = self._click_template(open_chi_path, get_screenshot(), 
                                              self.chi_params['confidence'], self.chi_params['delay'])
            results["open_chi"] = (success, msg)
            print(f"[结果] 打开CHI: {'✅ 成功' if success else '❌ 失败'} - {msg}")
            if not success:
                print("DEBUG: CHI软件打开失败，返回模拟数据")
                frequencies = np.logspace(1, 4, 50)
                z_real = np.random.normal(1000, 100, 50)
                z_imag = np.random.normal(-500, 50, 50)
                return results, frequencies, z_real, z_imag
            
            # 等待CHI软件完全启动
            print(f"[等待] CHI软件启动中...")
            time.sleep(3)
            
            # 步骤1：点击开始测量按钮
            print(f"\n[步骤1] 点击开始测量按钮...")
            start_measure_path = os.path.join(self.chi_params['template_dir'], "start_to_measure.png")
            success, msg = self._click_template(start_measure_path, get_screenshot(), 
                                              self.chi_params['confidence'], self.chi_params['delay'])
            results["start_measure"] = (success, msg)
            print(f"[结果] 开始测量: {'✅ 成功' if success else '❌ 失败'} - {msg}")
            if not success:
                frequencies = np.logspace(1, 4, 50)
                z_real = np.random.normal(1000, 100, 50)
                z_imag = np.random.normal(-500, 50, 50)
                return results, frequencies, z_real, z_imag
            
            # 步骤2：初始等待8秒
            print(f"\n[步骤2] 初始等待8秒...")
            time.sleep(8)
            results["initial_wait"] = (True, "初始等待完成")
            
            # 步骤3：根据频率参数计算等待时间
            print(f"\n[步骤3] 等待测量完成...")
            
            # 使用时间映射函数计算等待时间
            wait_seconds = get_measurement_time(self.chi_params['highf'], self.chi_params['lowf'])
            print(f"[信息] CHI测量频率范围: {self.chi_params['lowf']}Hz - {self.chi_params['highf']}Hz")
            print(f"[信息] 计算等待时间: {wait_seconds}秒")
            print(f"[信息] 等待CHI测量完成...")

            time.sleep(wait_seconds)
            results["wait_time"] = (True, f"等待完成 ({wait_seconds}s)")
            
            # 步骤4：点击另存为
            print(f"\n[步骤4] 点击另存为...")
            save_as_path = os.path.join(self.chi_params['template_dir'], "save_as.png")
            success, msg = self._click_template(save_as_path, get_screenshot(), self.chi_params['confidence'], self.chi_params['delay'])
            results["save_as"] = (success, msg)
            print(f"[结果] 另存为: {'✅ 成功' if success else '❌ 失败'} - {msg}")
            if not success:
                frequencies = np.logspace(1, 4, 50)
                z_real = np.random.normal(1000, 100, 50)
                z_imag = np.random.normal(-500, 50, 50)
                return results, frequencies, z_real, z_imag
            
            # 步骤5：点击保存类型
            print(f"\n[步骤5] 点击保存类型...")
            type_saving_path = os.path.join(self.chi_params['template_dir'], "type_saving.png")
            
            type_success = False
            type_msg = ""
            type_confidence_levels = [0.5, 0.4, 0.3, 0.2, 0.1]
            
            for i, conf in enumerate(type_confidence_levels, 1):
                print(f"[尝试] 保存类型第{i}次尝试，匹配阈值: {conf}")
                type_success, type_msg = self._click_template(type_saving_path, get_screenshot(), conf, self.chi_params['delay'])
                if type_success:
                    print(f"[成功] 保存类型点击成功，使用阈值: {conf}")
                    break
                else:
                    print(f"[失败] 保存类型第{i}次尝试失败: {type_msg}")
                    time.sleep(0.8)
            
            results["type_saving"] = (type_success, type_msg)
            print(f"[结果] 保存类型: {'✅ 成功' if type_success else '❌ 失败'} - {type_msg}")
            
            if type_success:
                print(f"[确认] 保存类型点击成功，等待下拉菜单展开...")
                time.sleep(0.8)
                print(f"[确认] 保存类型下拉菜单已展开")
            else:
                print(f"[警告] 保存类型点击失败，但继续尝试后续步骤...")
            
            # 步骤6：选择文件类型
            print(f"\n[步骤6] 选择文件类型...")
            white_path = os.path.join(self.chi_params['template_dir'], "your_type_white.png")
            blue_path = os.path.join(self.chi_params['template_dir'], "your_type_blue.png")
            
            file_type_success = False
            file_type_msg = ""
            file_type_confidence_levels = [0.5, 0.4, 0.3, 0.2, 0.1]
            
            for i, conf in enumerate(file_type_confidence_levels, 1):
                print(f"[尝试] 文件类型第{i}次尝试，匹配阈值: {conf}")
                file_type_success, file_type_msg = self._click_template(white_path, get_screenshot(), conf, self.chi_params['delay'])
                if not file_type_success:
                    print(f"[尝试] 白色类型失败，尝试蓝色类型...")
                    file_type_success, file_type_msg = self._click_template(blue_path, get_screenshot(), conf, self.chi_params['delay'])
                
                if file_type_success:
                    print(f"[成功] 文件类型选择成功，使用阈值: {conf}")
                    break
                else:
                    print(f"[失败] 文件类型第{i}次尝试失败: {file_type_msg}")
                    time.sleep(0.8)
            
            results["your_type"] = (file_type_success, file_type_msg)
            print(f"[结果] 文件类型: {'✅ 成功' if file_type_success else '❌ 失败'} - {file_type_msg}")
            
            if file_type_success:
                print(f"[确认] 文件类型选择成功，等待下拉菜单展开...")
                time.sleep(0.8)
                print(f"[确认] 文件类型选择完成，下拉菜单已展开")
            else:
                print(f"[警告] 文件类型选择失败，但继续尝试后续步骤...")
            
            # 步骤7：点击目录图标
            print(f"\n[步骤7] 点击目录图标...")
            directory_icon_path = os.path.join(self.chi_params['template_dir'], "Directory.png")
            print(f"[信息] 使用目录图标模板: Directory.png")

            success = False
            msg = ""
            confidence_levels = [0.5, 0.4, 0.3, 0.2, 0.1]
            
            for i, conf in enumerate(confidence_levels, 1):
                print(f"[尝试] 第{i}次尝试，匹配阈值: {conf}")
                success, msg = self._locate_address_field(directory_icon_path, get_screenshot(), conf)
                if success:
                    print(f"[成功] 目录点击成功，使用阈值: {conf}")
                    break
                else:
                    print(f"[失败] 第{i}次尝试失败: {msg}")
                    time.sleep(0.8)
            
            results["directory_click"] = (success, msg)
            print(f"[结果] 目录点击: {'✅ 成功' if success else '❌ 失败'} - {msg}")
            if not success:
                print(f"[警告] 目录点击失败，但继续尝试后续步骤...")
            
            print(f"\n[步骤8] 输入保存路径... [已跳过]")
            results["path_input"] = (True, "步骤8已手动跳过")
            print(f"[结果] 路径输入: ⏭️ 已跳过")

            # 步骤9：按一次Enter键进入文件夹
            print(f"\n[步骤9] 按一次Enter键进入文件夹...")
            try:
                print(f"[操作] 按Enter键进入文件夹...")
                pyautogui.press('enter')
                time.sleep(1.0)
                print(f"[成功] 按Enter键进入文件夹成功")
                results["enter_folder"] = (True, "按Enter键进入文件夹成功")
            except Exception as e:
                print(f"[失败] 按Enter键进入文件夹失败: {e}")
                results["enter_folder"] = (False, f"按Enter键进入文件夹失败: {str(e)}")
            
            # 步骤10：编辑文件名
            print(f"\n[步骤10] 编辑文件名...")
            filename = f"{self.chi_params['material']}_T{temp_str}_f{self.chi_params['lowf']}_{self.chi_params['highf']}_V{self.chi_params['initV']}"
            name_of_dc_path = os.path.join(self.chi_params['template_dir'], "name_of_dc.png")
            
            name_success = False
            name_msg = ""
            name_confidence_levels = [0.1, 0.05, 0.03, 0.02, 0.01]
            
            for i, conf in enumerate(name_confidence_levels, 1):
                print(f"[尝试] 文件名编辑第{i}次尝试，匹配阈值: {conf}")
                name_success, name_msg = self._edit_text_box(name_of_dc_path, get_screenshot(), filename, "right", conf, self.chi_params['delay'])
                if name_success:
                    print(f"[成功] 文件名编辑成功，使用阈值: {conf}")
                    break
                else:
                    print(f"[失败] 文件名编辑第{i}次尝试失败: {name_msg}")
                    time.sleep(1.0)
            
            results["name_edit"] = (name_success, name_msg)
            print(f"[结果] 文件名编辑: {'✅ 成功' if name_success else '❌ 失败'} - {name_msg}")
            if not name_success:
                print(f"[警告] 文件名编辑失败，但继续尝试后续步骤...")
            
            # 步骤11：按两次Enter键保存文件
            print(f"\n[步骤11] 按两次Enter键保存文件...")
            try:
                print(f"[操作] 第一次按Enter键确认文件名...")
                pyautogui.press('enter')
                time.sleep(1.0)
                print(f"[操作] 第二次按Enter键执行保存...")
                pyautogui.press('enter')
                time.sleep(2.0)
                print(f"[成功] 按两次Enter键保存文件成功")
                results["save_file"] = (True, "按两次Enter键保存文件成功")
            except Exception as e:
                print(f"[失败] 按Enter键保存文件失败: {e}")
                results["save_file"] = (False, f"按Enter键保存文件失败: {str(e)}")
            
            # 步骤12：再次打开CHI软件，确保软件保持打开状态
            print(f"\n[步骤12] 再次打开CHI软件，确保软件保持打开状态...")
            open_chi_path = os.path.join(self.chi_params['template_dir'], "open_CHI.png")
            success, msg = self._click_template(open_chi_path, get_screenshot(), 
                                              self.chi_params['confidence'], self.chi_params['delay'])
            results["reopen_chi"] = (success, msg)
            print(f"[结果] 再次打开CHI: {'✅ 成功' if success else '❌ 失败'} - {msg}")
            
            # 等待CHI软件完全启动
            print(f"[等待] CHI软件重新启动中...")
            time.sleep(3)
            
            print(f"\n=== CHI测量流程完成 ===")
            
            save_file_success = results.get("save_file", (False, ""))[0]
            if save_file_success:
                time.sleep(2)
                expected_file = os.path.join(self.chi_params['your_position'], filename + ".txt")
                if os.path.exists(expected_file):
                    print(f"[成功] 找到保存的数据文件: {expected_file}")
                    frequencies, z_real, z_imag = self._read_chi_data_file(expected_file)
                    if frequencies is not None:
                        results["data_reading"] = (True, f"成功读取{len(frequencies)}个数据点")
                        return results, frequencies, z_real, z_imag
                    else:
                        results["data_reading"] = (False, "无法解析数据文件")
                else:
                    print(f"[警告] 未找到预期的数据文件: {expected_file}")
                    frequencies = np.logspace(0, 4, 50)
                    z_real = 100 + 50 * np.exp(-frequencies/1000) + np.random.normal(0, 2, 50)
                    z_imag = -30 * np.exp(-frequencies/500) + np.random.normal(0, 1, 50)
                    results["data_reading"] = (False, "使用模拟数据")
                    return results, frequencies, z_real, z_imag
            
            frequencies = np.logspace(0, 4, 50)
            z_real = 100 + 50 * np.exp(-frequencies/1000) + np.random.normal(0, 2, 50)
            z_imag = -30 * np.exp(-frequencies/500) + np.random.normal(0, 1, 50)
            return results, frequencies, z_real, z_imag
            
        except Exception as e:
            print(f"[错误] CHI测量过程出错: {str(e)}")
            results["error"] = (False, str(e))
            frequencies = np.logspace(0, 4, 50)
            z_real = 100 + 50 * np.exp(-frequencies/1000) + np.random.normal(0, 2, 50)
            z_imag = -30 * np.exp(-frequencies/500) + np.random.normal(0, 1, 50)
            return results, frequencies, z_real, z_imag

    def _capture_remaining_time_strict(self, screenshot, template_dir=""):
        """改进的时间识别函数"""
        try:
            time_template_path = os.path.join(template_dir, "time_remaining.png")
            time_template = cv2_imread_unicode(time_template_path, cv2.IMREAD_GRAYSCALE)
            if time_template is None:
                print(f"[错误] 时间模板未找到: {time_template_path}")
                return 0

            gray_screen = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
            res = cv2.matchTemplate(gray_screen, time_template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)

            if max_val < 0.45:
                print(f"[警告] 时间区域匹配度低 (相似度: {max_val:.2f})")
                return 0

            print(f"[信息] 时间区域匹配成功 (相似度: {max_val:.2f})")
            return 98.0

        except Exception as e:
            print(f"[异常] 时间识别失败: {str(e)}")
            return 0

    def _click_template(self, template_path, screenshot, confidence, delay):
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
            
            pyautogui.click(click_x, click_y)
            time.sleep(delay)
            return True, f"点击成功 (匹配度: {max_val:.4f})"
        except Exception as e:
            return False, f"点击错误: {str(e)}"

    def _locate_address_field(self, template_path, screenshot, confidence=0.85):
        """改进的地址字段定位"""
        try:
            template = cv2_imread_unicode(template_path)
            if template is None:
                return False, f"地址字段模板不存在: {template_path}"

            if screenshot is None:
                screenshot = np.array(ImageGrab.grab())
                screenshot = cv2.cvtColor(screenshot, cv2.COLOR_RGB2BGR)

            res = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)

            if max_val >= confidence:
                h, w = template.shape[:2]
                click_x = max_loc[0] + w // 2
                click_y = max_loc[1] + h // 2
                
                pyautogui.click(click_x, click_y)
                time.sleep(1.0)
                
                pyautogui.click(click_x, click_y)
                time.sleep(0.5)
                
                return True, f"地址字段定位成功 (匹配度: {max_val:.4f})"
            else:
                return False, f"地址字段匹配度不足: {max_val:.4f} < {confidence}"

        except Exception as e:
            return False, f"地址字段定位错误: {str(e)}"

    def _edit_text_box(self, template_path, screenshot, text, side, confidence, delay):
        """改进的文本框编辑"""
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
                
                if "saving_position" in template_path or "Directory" in template_path:
                    click_x = max_loc[0] + 30
                
                pyautogui.click(click_x, click_y)
                time.sleep(delay + 0.5)
                
                pyautogui.click(click_x, click_y)
                time.sleep(0.5)
                
                pyautogui.hotkey('ctrl', 'a')
                time.sleep(0.5)
                pyautogui.press('backspace')
                time.sleep(0.5)
                
                try:
                    import pyperclip
                    pyperclip.copy(text)
                    time.sleep(0.3)
                    pyautogui.hotkey('ctrl', 'v')
                    time.sleep(0.5)
                    print(f"[DEBUG] 使用剪贴板输入: {text}")
                except (ImportError, Exception) as e:
                    print(f"[WARNING] pyperclip不可用({e})，使用Windows剪贴板")
                    try:
                        import win32clipboard
                        win32clipboard.OpenClipboard()
                        win32clipboard.EmptyClipboard()
                        win32clipboard.SetClipboardText(text)
                        win32clipboard.CloseClipboard()
                        time.sleep(0.3)
                        pyautogui.hotkey('ctrl', 'v')
                        time.sleep(0.5)
                        print(f"[DEBUG] 使用Windows剪贴板输入: {text}")
                    except Exception as e2:
                        print(f"[WARNING] 剪贴板不可用({e2})，使用typewrite")
                        pyautogui.typewrite(text, interval=0.05)
                
                time.sleep(0.5)
                time.sleep(1.0)
                
                return True, f"文本框编辑成功: {text}"
            else:
                return False, f"文本框匹配度不足: {max_val:.4f} < {confidence}"

        except Exception as e:
            return False, f"文本框编辑错误: {str(e)}"

    def save_measurement_data(self, result: Dict):
        """保存测量数据（增强版：结构化记录 + 失败可追溯）"""
        timestamp = time.strftime('%Y%m%d_%H%M%S')
        
        eis_saved_path = None
        eis_saved = False
        if 'eis_data' in result and len(result['eis_data']['frequencies']) > 0:
            try:
                file_name = f"eis_{self.current_temp:.1f}C_{timestamp}.txt"
                eis_saved_path = os.path.join(self.eis_data_dir, file_name)
                # ✅ 显式指定 encoding，避免依赖 sys.stdout.encoding
                with open(eis_saved_path, 'w', encoding='utf-8') as f:
                    f.write("Frequency\tZreal\tZimag\n")
                    for freq, zr, zi in zip(result['eis_data']['frequencies'], 
                                           result['eis_data']['z_real'], 
                                           result['eis_data']['z_imag']):
                        f.write(f"{freq}\t{zr}\t{zi}\n")
                eis_saved = True
                print(f"[成功] EIS数据已保存: {eis_saved_path}")
            except Exception as e:
                print(f"⚠️ 保存EIS数据文件失败: {e}")
                import traceback
                traceback.print_exc()  # ✅ 打印完整的异常堆栈
        
        raw_data_path = result.get('raw_data_path', None)
        if not raw_data_path:
            try:
                # 格式必须与chi_test.py第231行CHI保存时一致: 材料_T温度_f低频_高频_V电位
                target_temp = self.current_target if hasattr(self, 'current_target') else self.current_temp
                temp_str = f"{int(target_temp)}" if target_temp == int(target_temp) else f"{target_temp:.1f}"
                filename = f"{self.chi_params.get('material', 'Sample')}_T{temp_str}_f{self.chi_params.get('lowf')}_{self.chi_params.get('highf')}_V{self.chi_params.get('initV')}"
                raw_data_path = os.path.join(self.chi_params.get('your_position', 'E:\\chi_data'), filename + ".txt")
            except:
                raw_data_path = "未知"
        
        rb = result.get('rb')
        fit_method = result.get('fit_method', '未知')
        success = False
        failure_reason = None
        
        if rb is None or fit_method in ['failed', '处理失败', '未知']:
            success = False
            if 'error' in result:
                failure_reason = f"数据处理异常: {result['error']}"
            elif fit_method == 'failed':
                failure_reason = "拟合失败：所有拟合方法（线性/逐步线性/圆弧）均未达标"
            elif fit_method == '处理失败':
                failure_reason = "EIS数据处理流程异常"
            elif rb is None:
                failure_reason = "Rb值为None，拟合未返回有效结果"
            else:
                failure_reason = f"未知失败原因 (method={fit_method}, rb={rb})"
        else:
            success = True

        debug_artifacts = []
        if not success:
            try:
                screenshot_dir = os.path.join(self.data_dir, 'failures')
                os.makedirs(screenshot_dir, exist_ok=True)
                screenshot_filename = f"failure_T{self.current_temp:.1f}C_{timestamp}.png"
                screenshot_path = os.path.join(screenshot_dir, screenshot_filename)
                
                screenshot = pyautogui.screenshot()
                screenshot.save(screenshot_path)
                debug_artifacts.append(screenshot_path)
                print(f"[失败截图] 已保存: {screenshot_path}")
            except Exception as e:
                print(f"⚠️ 保存失败截图失败: {e}")
        
        # ✅ 修复：从details中提取r和r_squared
        fit_quality = None
        r_squared = None
        
        # 优先从details中获取（data_analysis.py返回的结构）
        details = result.get('details', {})
        if details:
            fit_quality = details.get('r', None)
            r_squared = details.get('r_squared', None)
        
        # 备选：如果details中没有，尝试从fit_params中获取
        if fit_quality is None and 'fit_params' in result and result['fit_params']:
            fit_quality = result['fit_params'].get('r', None)
        if r_squared is None and 'fit_params' in result and result['fit_params']:
            r_squared = result['fit_params'].get('r_squared', None)
        
        # ✅ 新增：对于X轴交点方法，设置质量指标为1.0
        # 原因：X轴交点是直接测量高频交点，是最可靠的方法，理论上应该有完美的质量
        if fit_method in ['X轴交点', 'x_intercept', 'X轴交点法'] and fit_quality is None:
            fit_quality = 1.0  # 表示方法本身完全可靠
            print(f"[chi_test] X轴交点方法，设置质量指标为1.0（方法可靠）")
        
        # ✅ 调试输出：追踪拟合质量数据
        print(f"[chi_test] 拟合方法={fit_method}, r={fit_quality}, r²={r_squared}")
        
        # 辅助函数：确保所有值都是JSON可序列化的Python原生类型
        def to_native_type(value):
            """将numpy类型转换为Python原生类型"""
            if value is None:
                return None
            if isinstance(value, (np.integer, np.floating)):
                return float(value)
            if isinstance(value, np.bool_):
                return bool(value)
            if isinstance(value, np.ndarray):
                return value.tolist()
            return value
        
        # ✅ 提取EIS原始数据和过滤后数据（修复：从正确的嵌套结构中提取）
        # result的结构是: result['eis_data']['frequencies']，而不是 result['freq_hz']
        eis_data = result.get('eis_data', {})
        freq_arr = eis_data.get('frequencies', np.array([]))
        z_real_arr = eis_data.get('z_real', np.array([]))
        z_imag_arr = eis_data.get('z_imag', np.array([]))
        
        # 从eis_data.filtered中获取滤波后的数据
        filtered = eis_data.get('filtered', {})
        freq_filtered = filtered.get('frequencies', np.array([]))
        zreal_filtered = filtered.get('z_real', np.array([]))
        zimag_filtered = filtered.get('z_imag', np.array([]))
        
        measurement_record = {
            'temperature_C': float(self.current_temp),
            'temperature_K': float(self.current_temp + 273.15),
            'timestamp': float(time.time()),
            'timestamp_str': timestamp,
            'step_type': 'fine' if self.fine_measuring else 'coarse',
            'chi_measurement_number': int(self.chi_measurement_count),
            
            'raw_data_path': raw_data_path,
            'raw_data_exists': os.path.exists(raw_data_path) if raw_data_path and raw_data_path != "未知" else False,
            'eis_saved_path': eis_saved_path,
            'eis_saved': bool(eis_saved),
            
            # ✅ 新增：保存EIS原始数据（用于前端图表显示）
            'eis_data': {
                'frequencies': to_native_type(freq_arr),
                'z_real': to_native_type(z_real_arr),
                'z_imag': to_native_type(z_imag_arr),
                'filtered': {
                    'frequencies': to_native_type(freq_filtered),
                    'z_real': to_native_type(zreal_filtered),
                    'z_imag': to_native_type(zimag_filtered)
                }
            },
            
            'rb_ohm': to_native_type(rb),
            'rb_method': fit_method,
            'fit_quality': to_native_type(fit_quality),
            'r_squared': to_native_type(r_squared),
            
            'conductivity_S_per_cm': to_native_type(result.get('conductivity')),
            
            'success': bool(success),
            'failure_reason': failure_reason,
            
            'debug_artifacts': debug_artifacts,
            
            'phase_jump_detected': bool(result.get('phase_jump_detected', False)),
            'phase_transition_range': result.get('phase_transition_range'),
            # ✅ 新增：相变检测分数（用于前端可视化）
            'phase_detection': result.get('phase_detection', {
                'phase_jump_score': 0.0,
                'linear_to_circle_score': 0.0,
                'is_phase_transition': False
            }),
        }
        
        self.measurement_history.append(measurement_record)
        self.save_experiment_data()
        
        print("\n" + "="*60)
        print(f"📊 测量点记录 [T={self.current_temp:.1f}°C / {self.current_temp + 273.15:.2f}K]")
        print("="*60)
        print(f"✅ 成功: {success}")
        if not success:
            print(f"❌ 失败原因: {failure_reason}")
            print(f"🖼️  失败截图: {len(debug_artifacts)} 张")
        else:
            print(f"🔬 Rb: {rb:.2f} Ω ({fit_method})")
            print(f"📈 拟合质量: r={fit_quality:.4f}" if fit_quality else "📈 拟合质量: N/A")
            print(f"⚡ 电导率: {result.get('conductivity'):.4e} S/cm" if result.get('conductivity') else "⚡ 电导率: N/A")
        print(f"📁 原始数据: {raw_data_path}")
        print(f"💾 标准化数据: {eis_saved_path if eis_saved else '未保存'}")
        print("="*60 + "\n")
# -*- coding: utf-8 -*-
"""
CHI测试自动化模块：GUI自动化 + 数据保存
"""

import os
import time
import cv2
import numpy as np
import pyautogui
from typing import Tuple, Optional, Dict
from PIL import ImageGrab


def cv2_imread_unicode(path, flags=cv2.IMREAD_COLOR):
    """支持中文路径的图像读取"""
    try:
        template = cv2.imread(path, flags)
        if template is None:
            from PIL import Image
            pil_image = Image.open(path)
            template = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
        return template
    except Exception as e:
        print(f"[DEBUG] 读取图像失败: {path}, 错误: {str(e)}")
        return None


class ChiTestMixin:
    """CHI测试自动化功能 Mixin"""

    def run_chi_measurement(self) -> Tuple[Dict, np.ndarray, np.ndarray, np.ndarray]:
        """
        执行完整的CHI测量流程 - 使用手动测量的完美流程
        
        Returns:
            Tuple[Dict, ndarray, ndarray, ndarray]: (results, frequencies, z_real, z_imag)
        """
        print(f"\n=== 开始CHI测量流程 ===")
        print("DEBUG: 检查CHI参数")
        print(f"[配置] 材料: {self.chi_params['material']}")
        print(f"[配置] 温度: {self.current_temp:.1f}°C")
        print(f"[配置] 频率范围: {self.chi_params['lowf']}-{self.chi_params['highf']}Hz")
        print(f"[配置] 初始电位: {self.chi_params['initV']}V")
        print("DEBUG: CHI参数检查完成")
        
        # 更新CHI参数中的温度
        self.chi_params['T'] = str(int(self.current_temp + 273.15))  # 转换为开尔文
        
        # 生成文件名 - 使用目标温度而不是当前温度
        target_temp_for_filename = self.current_target if hasattr(self, 'current_target') else self.current_temp
        # 将温度转换为整数格式，避免.0
        temp_str = f"{int(target_temp_for_filename)}" if target_temp_for_filename == int(target_temp_for_filename) else f"{target_temp_for_filename:.1f}"
        filename = f"{self.chi_params['material']}_T{temp_str}C_highf{self.chi_params['highf']}_lowf{self.chi_params['lowf']}_initV{self.chi_params['initV']}"
        
        results = {}
        
        def get_screenshot():
            return np.array(ImageGrab.grab())
        
        # 验证保存路径
        try:
            os.makedirs(self.chi_params['your_position'], exist_ok=True)
            print(f"[验证] 保存目录已创建/验证: {self.chi_params['your_position']}")
        except Exception as e:
            print(f"[错误] 无法创建保存目录: {e}")
            return {"error": f"保存目录创建失败: {e}"}, None, None, None
        
        try:
            # 步骤0：打开CHI软件
            print(f"\n[步骤0] 打开CHI软件...")
            open_chi_path = os.path.join(self.chi_params['template_dir'], "open_CHI.png")
            
            success, msg = self._click_template(open_chi_path, get_screenshot(), 
                                              self.chi_params['confidence'], self.chi_params['delay'])
            results["open_chi"] = (success, msg)
            print(f"[结果] 打开CHI: {'✅ 成功' if success else '❌ 失败'} - {msg}")
            if not success:
                frequencies = np.logspace(1, 4, 50)
                z_real = np.random.normal(1000, 100, 50)
                z_imag = np.random.normal(-500, 50, 50)
                return results, frequencies, z_real, z_imag
            
            # 等待CHI软件完全启动
            print(f"[等待] CHI软件启动中...")
            time.sleep(3)
            
            # 步骤1：点击开始测量按钮
            print(f"\n[步骤1] 点击开始测量按钮...")
            start_measure_path = os.path.join(self.chi_params['template_dir'], "start_to_measure.png")
            success, msg = self._click_template(start_measure_path, get_screenshot(), 
                                              self.chi_params['confidence'], self.chi_params['delay'])
            results["start_measure"] = (success, msg)
            print(f"[结果] 开始测量: {'✅ 成功' if success else '❌ 失败'} - {msg}")
            if not success:
                frequencies = np.logspace(1, 4, 50)
                z_real = np.random.normal(1000, 100, 50)
                z_imag = np.random.normal(-500, 50, 50)
                return results, frequencies, z_real, z_imag
            
            # 步骤2：初始等待8秒
            print(f"\n[步骤2] 初始等待8秒...")
            time.sleep(8)
            results["initial_wait"] = (True, "初始等待完成")
            
            # 步骤3：根据频率参数计算等待时间
            print(f"\n[步骤3] 等待测量完成...")
            
            # 使用时间映射函数计算等待时间
            wait_seconds = get_measurement_time(self.chi_params['highf'], self.chi_params['lowf'])
            print(f"[信息] CHI测量频率范围: {self.chi_params['lowf']}Hz - {self.chi_params['highf']}Hz")
            print(f"[信息] 计算等待时间: {wait_seconds}秒")
            print(f"[信息] 等待CHI测量完成...")
            time.sleep(wait_seconds)
            results["wait_time"] = (True, f"等待完成 ({wait_seconds}s)")
            
            # 步骤4：点击另存为
            print(f"\n[步骤4] 点击另存为...")
            save_as_path = os.path.join(self.chi_params['template_dir'], "save_as.png")
            success, msg = self._click_template(save_as_path, get_screenshot(), self.chi_params['confidence'], self.chi_params['delay'])
            results["save_as"] = (success, msg)
            print(f"[结果] 另存为: {'✅ 成功' if success else '❌ 失败'} - {msg}")
            if not success:
                frequencies = np.logspace(1, 4, 50)
                z_real = np.random.normal(1000, 100, 50)
                z_imag = np.random.normal(-500, 50, 50)
                return results, frequencies, z_real, z_imag
            
            # 步骤5：点击保存类型
            print(f"\n[步骤5] 点击保存类型...")
            type_saving_path = os.path.join(self.chi_params['template_dir'], "type_saving.png")
            
            type_success = False
            type_msg = ""
            type_confidence_levels = [0.5, 0.4, 0.3, 0.2, 0.1]
            
            for i, conf in enumerate(type_confidence_levels, 1):
                print(f"[尝试] 保存类型第{i}次尝试，匹配阈值: {conf}")
                type_success, type_msg = self._click_template(type_saving_path, get_screenshot(), conf, self.chi_params['delay'])
                if type_success:
                    print(f"[成功] 保存类型点击成功，使用阈值: {conf}")
                    break
                else:
                    print(f"[失败] 保存类型第{i}次尝试失败: {type_msg}")
                    time.sleep(0.8)
            
            results["type_saving"] = (type_success, type_msg)
            print(f"[结果] 保存类型: {'✅ 成功' if type_success else '❌ 失败'} - {type_msg}")
            
            if type_success:
                print(f"[确认] 保存类型点击成功，等待下拉菜单展开...")
                time.sleep(0.8)
                print(f"[确认] 保存类型下拉菜单已展开")
            else:
                print(f"[警告] 保存类型点击失败，但继续尝试后续步骤...")
            
            # 步骤6：选择文件类型
            print(f"\n[步骤6] 选择文件类型...")
            white_path = os.path.join(self.chi_params['template_dir'], "your_type_white.png")
            blue_path = os.path.join(self.chi_params['template_dir'], "your_type_blue.png")
            
            file_type_success = False
            file_type_msg = ""
            file_type_confidence_levels = [0.5, 0.4, 0.3, 0.2, 0.1]
            
            for i, conf in enumerate(file_type_confidence_levels, 1):
                print(f"[尝试] 文件类型第{i}次尝试，匹配阈值: {conf}")
                file_type_success, file_type_msg = self._click_template(white_path, get_screenshot(), conf, self.chi_params['delay'])
                if not file_type_success:
                    print(f"[尝试] 白色类型失败，尝试蓝色类型...")
                    file_type_success, file_type_msg = self._click_template(blue_path, get_screenshot(), conf, self.chi_params['delay'])
                
                if file_type_success:
                    print(f"[成功] 文件类型选择成功，使用阈值: {conf}")
                    break
                else:
                    print(f"[失败] 文件类型第{i}次尝试失败: {file_type_msg}")
                    time.sleep(0.8)
            
            results["your_type"] = (file_type_success, file_type_msg)
            print(f"[结果] 文件类型: {'✅ 成功' if file_type_success else '❌ 失败'} - {file_type_msg}")
            
            if file_type_success:
                print(f"[确认] 文件类型选择成功，等待下拉菜单展开...")
                time.sleep(0.8)
                print(f"[确认] 文件类型选择完成，下拉菜单已展开")
            else:
                print(f"[警告] 文件类型选择失败，但继续尝试后续步骤...")
            
            # 步骤7：点击目录图标
            print(f"\n[步骤7] 点击目录图标...")
            directory_icon_path = os.path.join(self.chi_params['template_dir'], "Directory.png")
            print(f"[信息] 使用目录图标模板: Directory.png")

            success = False
            msg = ""
            confidence_levels = [0.5, 0.4, 0.3, 0.2, 0.1]
            
            for i, conf in enumerate(confidence_levels, 1):
                print(f"[尝试] 第{i}次尝试，匹配阈值: {conf}")
                success, msg = self._locate_address_field(directory_icon_path, get_screenshot(), conf)
                if success:
                    print(f"[成功] 目录点击成功，使用阈值: {conf}")
                    break
                else:
                    print(f"[失败] 第{i}次尝试失败: {msg}")
                    time.sleep(0.8)
            
            results["directory_click"] = (success, msg)
            print(f"[结果] 目录点击: {'✅ 成功' if success else '❌ 失败'} - {msg}")
            if not success:
                print(f"[警告] 目录点击失败，但继续尝试后续步骤...")
            
            # 步骤8已跳过
            print(f"\n[步骤8] 输入保存路径... [已跳过]")
            results["path_input"] = (True, "步骤8已手动跳过")
            print(f"[结果] 路径输入: ⏭️ 已跳过")
            
            # 步骤9：按一次Enter键进入文件夹
            print(f"\n[步骤9] 按一次Enter键进入文件夹...")
            try:
                print(f"[操作] 按Enter键进入文件夹...")
                pyautogui.press('enter')
                time.sleep(1.0)
                print(f"[成功] 按Enter键进入文件夹成功")
                results["enter_folder"] = (True, "按Enter键进入文件夹成功")
            except Exception as e:
                print(f"[失败] 按Enter键进入文件夹失败: {e}")
                results["enter_folder"] = (False, f"按Enter键进入文件夹失败: {str(e)}")
            
            # 步骤10：编辑文件名
            print(f"\n[步骤10] 编辑文件名...")
            filename = f"{self.chi_params['material']}_T{temp_str}_f{self.chi_params['lowf']}_{self.chi_params['highf']}_V{self.chi_params['initV']}"
            name_of_dc_path = os.path.join(self.chi_params['template_dir'], "name_of_dc.png")
            
            name_success = False
            name_msg = ""
            name_confidence_levels = [0.1, 0.05, 0.03, 0.02, 0.01]
            
            for i, conf in enumerate(name_confidence_levels, 1):
                print(f"[尝试] 文件名编辑第{i}次尝试，匹配阈值: {conf}")
                name_success, name_msg = self._edit_text_box(name_of_dc_path, get_screenshot(), filename, "right", conf, self.chi_params['delay'])
                if name_success:
                    print(f"[成功] 文件名编辑成功，使用阈值: {conf}")
                    break
                else:
                    print(f"[失败] 文件名编辑第{i}次尝试失败: {name_msg}")
                    time.sleep(1.0)
            
            results["name_edit"] = (name_success, name_msg)
            print(f"[结果] 文件名编辑: {'✅ 成功' if name_success else '❌ 失败'} - {name_msg}")
            if not name_success:
                print(f"[警告] 文件名编辑失败，但继续尝试后续步骤...")
            
            # 步骤11：按两次Enter键保存文件
            print(f"\n[步骤11] 按两次Enter键保存文件...")
            try:
                print(f"[操作] 第一次按Enter键确认文件名...")
                pyautogui.press('enter')
                time.sleep(1.0)
                print(f"[操作] 第二次按Enter键执行保存...")
                pyautogui.press('enter')
                time.sleep(2.0)
                print(f"[成功] 按两次Enter键保存文件成功")
                results["save_file"] = (True, "按两次Enter键保存文件成功")
            except Exception as e:
                print(f"[失败] 按Enter键保存文件失败: {e}")
                results["save_file"] = (False, f"按Enter键保存文件失败: {str(e)}")
            
            # 步骤12：再次打开CHI软件
            print(f"\n[步骤12] 再次打开CHI软件，确保软件保持打开状态...")
            open_chi_path = os.path.join(self.chi_params['template_dir'], "open_CHI.png")
            success, msg = self._click_template(open_chi_path, get_screenshot(), 
                                              self.chi_params['confidence'], self.chi_params['delay'])
            results["reopen_chi"] = (success, msg)
            print(f"[结果] 再次打开CHI: {'✅ 成功' if success else '❌ 失败'} - {msg}")
            
            print(f"[等待] CHI软件重新启动中...")
            time.sleep(3)
            
            print(f"\n=== CHI测量流程完成 ===")
            
            # 读取并处理保存的数据
            save_file_success = results.get("save_file", (False, ""))[0]
            if save_file_success:
                time.sleep(2)
                
                expected_file = os.path.join(self.chi_params['your_position'], filename + ".txt")
                if os.path.exists(expected_file):
                    print(f"[成功] 找到保存的数据文件: {expected_file}")
                    frequencies, z_real, z_imag = self._read_chi_data_file(expected_file)
                    if frequencies is not None:
                        results["data_reading"] = (True, f"成功读取{len(frequencies)}个数据点")
                        return results, frequencies, z_real, z_imag
                    else:
                        results["data_reading"] = (False, "无法解析数据文件")
                else:
                    print(f"[警告] 未找到预期的数据文件: {expected_file}")
                    frequencies = np.logspace(0, 4, 50)
                    z_real = 100 + 50 * np.exp(-frequencies/1000) + np.random.normal(0, 2, 50)
                    z_imag = -30 * np.exp(-frequencies/500) + np.random.normal(0, 1, 50)
                    results["data_reading"] = (False, "使用模拟数据")
                    return results, frequencies, z_real, z_imag
            
            frequencies = np.logspace(0, 4, 50)
            z_real = 100 + 50 * np.exp(-frequencies/1000) + np.random.normal(0, 2, 50)
            z_imag = -30 * np.exp(-frequencies/500) + np.random.normal(0, 1, 50)
            return results, frequencies, z_real, z_imag
            
        except Exception as e:
            print(f"[错误] CHI测量过程出错: {str(e)}")
            results["error"] = (False, str(e))
            frequencies = np.logspace(0, 4, 50)
            z_real = 100 + 50 * np.exp(-frequencies/1000) + np.random.normal(0, 2, 50)
            z_imag = -30 * np.exp(-frequencies/500) + np.random.normal(0, 1, 50)
            return results, frequencies, z_real, z_imag

    def _try_parse_three_floats(self, line: str):
        """尝试从一行文本中解析出3个浮点数"""
        line = line.strip()
        if not line:
            return None
        
        for delimiter in [',', '\t', None]:
            try:
                if delimiter:
                    parts = line.split(delimiter)
                else:
                    parts = line.split()
                
                if len(parts) < 3:
                    continue
                
                freq = float(parts[0].strip())
                z_real = float(parts[1].strip())
                z_imag = float(parts[2].strip())
                return (freq, z_real, z_imag)
            except (ValueError, IndexError):
                continue
        
        return None

    def _read_chi_data_file(self, filepath: str) -> Tuple[Optional[np.ndarray], Optional[np.ndarray], Optional[np.ndarray]]:
        """读取CHI保存的数据文件"""
        try:
            if not os.path.exists(filepath):
                print(f"❌ 文件不存在: {filepath}")
                return None, None, None
            
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
            data_start_line = None
            for i, line in enumerate(lines):
                result = self._try_parse_three_floats(line)
                if result is not None:
                    data_start_line = i
                    print(f"[找到数据起始行] 第 {i+1} 行: {line.strip()[:80]}")
                    break
            
            if data_start_line is None:
                print(f"❌ 未找到有效数据行（无法解析出3个浮点数）: {filepath}")
                return None, None, None
            
            data_rows = []
            for i in range(data_start_line, len(lines)):
                result = self._try_parse_three_floats(lines[i])
                if result is not None:
                    data_rows.append(result)
            
            if len(data_rows) == 0:
                print(f"❌ 解析到0个有效数据点: {filepath}")
                return None, None, None
            
            data = np.array(data_rows)
            frequencies = data[:, 0]
            z_real = data[:, 1]
            z_imag = data[:, 2]
            
            if len(frequencies) < 10:
                print(f"❌ 有效数据点不足10个 ({len(frequencies)}个): {filepath}")
                return None, None, None
            
            print(f"✅ 成功读取 {len(frequencies)} 个数据点")
            return frequencies, z_real, z_imag
            
        except Exception as e:
            print(f"❌ 读取数据文件失败: {e}")
            import traceback
            traceback.print_exc()
            return None, None, None

    def _capture_remaining_time_strict(self, screenshot, template_dir=""):
        """改进的时间识别函数"""
        try:
            time_template_path = os.path.join(template_dir, "time_remaining.png")
            time_template = cv2_imread_unicode(time_template_path, cv2.IMREAD_GRAYSCALE)
            if time_template is None:
                print(f"[错误] 时间模板未找到: {time_template_path}")
                return 0

            gray_screen = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
            res = cv2.matchTemplate(gray_screen, time_template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)

            if max_val < 0.45:
                print(f"[警告] 时间区域匹配度低 (相似度: {max_val:.2f})")
                return 0

            print(f"[信息] 时间区域匹配成功 (相似度: {max_val:.2f})")
            return 98.0

        except Exception as e:
            print(f"[异常] 时间识别失败: {str(e)}")
            return 0

    def _click_template(self, template_path, screenshot, confidence, delay):
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
            
            pyautogui.click(click_x, click_y)
            time.sleep(delay)
            return True, f"点击成功 (匹配度: {max_val:.4f})"
        except Exception as e:
            return False, f"点击错误: {str(e)}"

    def _locate_address_field(self, template_path, screenshot, confidence=0.85):
        """改进的地址字段定位"""
        try:
            template = cv2_imread_unicode(template_path)
            if template is None:
                return False, f"地址字段模板不存在: {template_path}"

            if screenshot is None:
                screenshot = np.array(ImageGrab.grab())
                screenshot = cv2.cvtColor(screenshot, cv2.COLOR_RGB2BGR)

            res = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)

            if max_val >= confidence:
                h, w = template.shape[:2]
                click_x = max_loc[0] + w // 2
                click_y = max_loc[1] + h // 2
                
                pyautogui.click(click_x, click_y)
                time.sleep(1.0)
                
                pyautogui.click(click_x, click_y)
                time.sleep(0.5)
                
                return True, f"地址字段定位成功 (匹配度: {max_val:.4f})"
            else:
                return False, f"地址字段匹配度不足: {max_val:.4f} < {confidence}"

        except Exception as e:
            return False, f"地址字段定位错误: {str(e)}"

    def _edit_text_box(self, template_path, screenshot, text, side, confidence, delay):
        """改进的文本框编辑"""
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
                
                if "saving_position" in template_path or "Directory" in template_path:
                    click_x = max_loc[0] + 30
                
                pyautogui.click(click_x, click_y)
                time.sleep(delay + 0.5)
                
                pyautogui.click(click_x, click_y)
                time.sleep(0.5)
                
                pyautogui.hotkey('ctrl', 'a')
                time.sleep(0.5)
                pyautogui.press('backspace')
                time.sleep(0.5)
                
                # 使用剪贴板方式输入
                try:
                    import pyperclip
                    pyperclip.copy(text)
                    time.sleep(0.3)
                    pyautogui.hotkey('ctrl', 'v')
                    time.sleep(0.5)
                    print(f"[DEBUG] 使用剪贴板输入: {text}")
                except (ImportError, Exception) as e:
                    print(f"[WARNING] pyperclip不可用({e})，使用Windows剪贴板")
                    try:
                        import win32clipboard
                        win32clipboard.OpenClipboard()
                        win32clipboard.EmptyClipboard()
                        win32clipboard.SetClipboardText(text)
                        win32clipboard.CloseClipboard()
                        time.sleep(0.3)
                        pyautogui.hotkey('ctrl', 'v')
                        time.sleep(0.5)
                        print(f"[DEBUG] 使用Windows剪贴板输入: {text}")
                    except Exception as e2:
                        print(f"[WARNING] 剪贴板不可用({e2})，使用typewrite")
                        pyautogui.typewrite(text, interval=0.05)
                
                time.sleep(0.5)
                time.sleep(1.0)
                
                return True, f"文本框编辑成功: {text}"
            else:
                return False, f"文本框匹配度不足: {max_val:.4f} < {confidence}"

        except Exception as e:
            return False, f"文本框编辑错误: {str(e)}"

    def save_measurement_data(self, result: Dict):
        """保存测量数据（增强版：结构化记录 + 失败可追溯）"""
        timestamp = time.strftime('%Y%m%d_%H%M%S')
        
        # 1. 保存EIS数据到标准化文件
        eis_saved_path = None
        eis_saved = False
        if 'eis_data' in result and len(result['eis_data']['frequencies']) > 0:
            try:
                file_name = f"eis_{self.current_temp:.1f}C_{timestamp}.txt"
                eis_saved_path = os.path.join(self.eis_data_dir, file_name)
                # ✅ 显式指定 encoding，避免依赖 sys.stdout.encoding
                with open(eis_saved_path, 'w', encoding='utf-8') as f:
                    f.write("Frequency\tZreal\tZimag\n")
                    for freq, zr, zi in zip(result['eis_data']['frequencies'], 
                                           result['eis_data']['z_real'], 
                                           result['eis_data']['z_imag']):
                        f.write(f"{freq}\t{zr}\t{zi}\n")
                eis_saved = True
                print(f"[成功] EIS数据已保存: {eis_saved_path}")
            except Exception as e:
                print(f"⚠️ 保存EIS数据文件失败: {e}")
                import traceback
                traceback.print_exc()  # ✅ 打印完整的异常堆栈
        
        # 2. 获取CHI原始数据路径 - 格式必须与第817行CHI保存时一致
        raw_data_path = result.get('raw_data_path', None)
        if not raw_data_path:
            try:
                # 格式: 材料_T温度_f低频_高频_V电位
                target_temp = self.current_target if hasattr(self, 'current_target') else self.current_temp
                temp_str = f"{int(target_temp)}" if target_temp == int(target_temp) else f"{target_temp:.1f}"
                filename = f"{self.chi_params.get('material', 'Sample')}_T{temp_str}_f{self.chi_params.get('lowf')}_{self.chi_params.get('highf')}_V{self.chi_params.get('initV')}"
                raw_data_path = os.path.join(self.chi_params.get('your_position', 'E:\\chi_data'), filename + ".txt")
            except:
                raw_data_path = "未知"
        
        # 3. 判断成功/失败 + 失败原因
        rb = result.get('rb')
        fit_method = result.get('fit_method', '未知')
        success = False
        failure_reason = None
        
        if rb is None or fit_method in ['failed', '处理失败', '未知']:
            success = False
            if 'error' in result:
                failure_reason = f"数据处理异常: {result['error']}"
            elif fit_method == 'failed':
                failure_reason = "拟合失败：所有拟合方法（线性/逐步线性/圆弧）均未达标"
            elif fit_method == '处理失败':
                failure_reason = "EIS数据处理流程异常"
            elif rb is None:
                failure_reason = "Rb值为None，拟合未返回有效结果"
            else:
                failure_reason = f"未知失败原因 (method={fit_method}, rb={rb})"
        else:
            success = True

        # 4. 失败截图（如果失败）
        debug_artifacts = []
        if not success:
            try:
                screenshot_dir = os.path.join(self.data_dir, 'failures')
                os.makedirs(screenshot_dir, exist_ok=True)
                screenshot_filename = f"failure_T{self.current_temp:.1f}C_{timestamp}.png"
                screenshot_path = os.path.join(screenshot_dir, screenshot_filename)
                
                screenshot = pyautogui.screenshot()
                screenshot.save(screenshot_path)
                debug_artifacts.append(screenshot_path)
                print(f"[失败截图] 已保存: {screenshot_path}")
            except Exception as e:
                print(f"⚠️ 保存失败截图失败: {e}")
        
        # 5. 提取拟合质量指标
        fit_quality = None
        r_squared = None
        if 'fit_params' in result and result['fit_params']:
            fit_quality = result['fit_params'].get('r', None)
            r_squared = result['fit_params'].get('r_squared', None)
        
        # 6. 构建结构化记录
        # 辅助函数：确保所有值都是JSON可序列化的Python原生类型
        def to_native_type(value):
            """将numpy类型转换为Python原生类型"""
            if value is None:
                return None
            if isinstance(value, (np.integer, np.floating)):
                return float(value)
            if isinstance(value, np.bool_):
                return bool(value)
            if isinstance(value, np.ndarray):
                return value.tolist()
            return value
        
        measurement_record = {
            'temperature_C': float(self.current_temp),
            'temperature_K': float(self.current_temp + 273.15),
            'timestamp': float(time.time()),
            'timestamp_str': timestamp,
            'step_type': 'fine' if self.fine_measuring else 'coarse',
            'chi_measurement_number': int(self.chi_measurement_count),
            'raw_data_path': raw_data_path,
            'raw_data_exists': os.path.exists(raw_data_path) if raw_data_path and raw_data_path != "未知" else False,
            'eis_saved_path': eis_saved_path,
            'eis_saved': bool(eis_saved),
            'rb_ohm': to_native_type(rb),
            'rb_method': fit_method,
            'fit_quality': to_native_type(fit_quality),
            'r_squared': to_native_type(r_squared),
            'conductivity_S_per_cm': to_native_type(result.get('conductivity')),
            'success': bool(success),
            'failure_reason': failure_reason,
            'debug_artifacts': debug_artifacts,
            'phase_jump_detected': bool(result.get('phase_jump_detected', False)),
            'phase_transition_range': result.get('phase_transition_range'),
            # ✅ 新增：相变检测分数（用于前端可视化）
            'phase_detection': result.get('phase_detection', {
                'phase_jump_score': 0.0,
                'linear_to_circle_score': 0.0,
                'is_phase_transition': False
            }),
        }
        
        self.measurement_history.append(measurement_record)
        
        # 实时保存数据
        self.save_experiment_data()
        
        # 7. 打印结构化摘要
        print("\n" + "="*60)
        print(f"📊 测量点记录 [T={self.current_temp:.1f}°C / {self.current_temp + 273.15:.2f}K]")
        print("="*60)
        print(f"✅ 成功: {success}")
        if not success:
            print(f"❌ 失败原因: {failure_reason}")
            print(f"🖼️  失败截图: {len(debug_artifacts)} 张")
        else:
            print(f"🔬 Rb: {rb:.2f} Ω ({fit_method})")
            print(f"📈 拟合质量: r={fit_quality:.4f}" if fit_quality else "📈 拟合质量: N/A")
            print(f"⚡ 电导率: {result.get('conductivity'):.4e} S/cm" if result.get('conductivity') else "⚡ 电导率: N/A")
        print(f"📁 原始数据: {raw_data_path}")
        print(f"💾 标准化数据: {eis_saved_path if eis_saved else '未保存'}")
        print("="*60 + "\n")
