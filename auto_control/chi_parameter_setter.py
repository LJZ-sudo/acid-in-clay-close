# -*- coding: utf-8 -*-
"""
CHI参数设置模块
用于在CHI软件中设置测量参数（初始电压、高频、低频）
"""

import cv2
import numpy as np
import pyautogui
from PIL import ImageGrab
import time
import os
import sys

# 设置控制台编码
import locale
import codecs

# 尝试设置UTF-8编码
try:
    if sys.platform.startswith('win'):
        # Windows系统
        os.system('chcp 65001 > nul')
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    else:
        # Linux/Mac系统
        locale.setlocale(locale.LC_ALL, 'zh_CN.UTF-8')
except:
    pass

# 设置标准输出编码
try:
    if hasattr(sys.stdout, 'detach'):
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.detach())
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.detach())
except:
    pass

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

def _clear_input_field(x, y):
    """清理输入框内容的多种方法"""
    try:
        # 点击输入框
        pyautogui.click(x, y)
        time.sleep(0.3)
        
        # 方法1: Ctrl+A全选然后删除
        try:
            pyautogui.hotkey('ctrl', 'a')
            time.sleep(0.2)
            pyautogui.press('delete')
            time.sleep(0.2)
            return True
        except:
            pass
        
        # 方法2: 双击选中然后删除
        try:
            pyautogui.doubleClick(x, y)
            time.sleep(0.2)
            pyautogui.press('delete')
            time.sleep(0.2)
            return True
        except:
            pass
        
        # 方法3: 手动删除 - 按Home键到开头，然后按Delete删除
        try:
            pyautogui.press('home')
            time.sleep(0.2)
            # 多次按Delete确保删除所有内容
            for _ in range(30):  # 最多删除30个字符
                pyautogui.press('delete')
                time.sleep(0.05)
            return True
        except:
            pass
        
        # 方法4: 使用Shift+End选中到末尾，然后删除
        try:
            pyautogui.press('home')
            time.sleep(0.2)
            pyautogui.hotkey('shift', 'end')
            time.sleep(0.2)
            pyautogui.press('delete')
            time.sleep(0.2)
            return True
        except:
            pass
        
        return False
    except Exception as e:
        print(f"[DEBUG] 清理输入框失败: {str(e)}")
        return False

def _click_template(template_path, screenshot, confidence, delay):
    """改进的模板点击函数，更好地处理中文路径"""
    try:
        print(f"[DEBUG] chi_parameter_setter: 尝试读取模板: {template_path}")
        
        # 方法1: 尝试使用OpenCV直接读取
        template = cv2.imread(template_path)
        if template is not None:
            print(f"[DEBUG] chi_parameter_setter: OpenCV成功读取模板")
        else:
            print(f"[DEBUG] chi_parameter_setter: OpenCV读取失败，尝试PIL")
            
            # 方法2: 尝试使用PIL作为备选方案
            try:
                from PIL import Image
                pil_image = Image.open(template_path)
                template = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
                print(f"[DEBUG] chi_parameter_setter: PIL成功读取模板: {template_path}")
            except Exception as pil_error:
                print(f"[DEBUG] chi_parameter_setter: PIL读取也失败: {pil_error}")
                
                # 方法3: 尝试使用绝对路径
                try:
                    abs_path = os.path.abspath(template_path)
                    print(f"[DEBUG] chi_parameter_setter: 尝试绝对路径: {abs_path}")
                    template = cv2.imread(abs_path)
                    if template is not None:
                        print(f"[DEBUG] chi_parameter_setter: 绝对路径读取成功")
                    else:
                        # 方法4: 尝试使用PIL读取绝对路径
                        pil_image = Image.open(abs_path)
                        template = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
                        print(f"[DEBUG] chi_parameter_setter: PIL绝对路径读取成功")
                except Exception as abs_error:
                    print(f"[DEBUG] chi_parameter_setter: 绝对路径读取失败: {abs_error}")
                    return False, f"所有方法都无法读取模板: {template_path}"

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

def _edit_parameter_field(template_path, screenshot, value, template_dir, confidence=0.6, delay=0.5):
    """编辑参数字段"""
    try:
        print(f"[DEBUG] chi_parameter_setter: 尝试读取参数模板: {template_path}")
        
        # 方法1: 尝试使用OpenCV直接读取
        template = cv2.imread(template_path)
        if template is None:
            print(f"[DEBUG] chi_parameter_setter: OpenCV读取失败，尝试PIL")
            
            # 方法2: 尝试使用PIL作为备选方案
            try:
                from PIL import Image
                pil_image = Image.open(template_path)
                template = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
                print(f"[DEBUG] chi_parameter_setter: PIL成功读取参数模板")
            except Exception as pil_error:
                print(f"[DEBUG] chi_parameter_setter: PIL读取也失败: {pil_error}")
                
                # 方法3: 尝试使用绝对路径
                try:
                    abs_path = os.path.abspath(template_path)
                    print(f"[DEBUG] chi_parameter_setter: 尝试绝对路径: {abs_path}")
                    template = cv2.imread(abs_path)
                    if template is None:
                        # 方法4: 尝试使用PIL读取绝对路径
                        pil_image = Image.open(abs_path)
                        template = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
                        print(f"[DEBUG] chi_parameter_setter: PIL绝对路径读取成功")
                except Exception as abs_error:
                    print(f"[DEBUG] chi_parameter_setter: 绝对路径读取失败: {abs_error}")
                    return False, f"所有方法都无法读取参数模板: {template_path}"
        
        if template is None:
            return False, f"参数模板不存在: {template_path}"

        res = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)

        if max_val >= confidence:
            h, w = template.shape[:2]
            # 点击模板右侧的输入框
            click_x = max_loc[0] + w + 10  # 模板右侧10像素
            click_y = max_loc[1] + h // 2
            
            # 使用专门的清理函数
            if _clear_input_field(click_x, click_y):
                print(f"[DEBUG] 成功清理输入框")
            else:
                print(f"[DEBUG] 清理输入框失败，尝试备用方法")
                # 备用方法：直接输入，覆盖现有内容
                pyautogui.click(click_x, click_y)
                time.sleep(0.3)
                pyautogui.hotkey('ctrl', 'a')
                time.sleep(0.2)
            
            # 输入新值
            pyautogui.write(str(value))
            time.sleep(0.5)
            
            # 按Tab键确认输入并移动到下一个字段
            pyautogui.press('tab')
            time.sleep(0.3)
            
            return True, f"参数设置成功: {value} (匹配度: {max_val:.4f})"
        else:
            return False, f"参数字段匹配度不足: {max_val:.4f} < {confidence}"

    except Exception as e:
        return False, f"参数设置错误: {str(e)}"

def setup_chi_parameters(initial_voltage, high_frequency, low_frequency, template_dir=None):
    """
    在CHI软件中设置测量参数
    
    Args:
        initial_voltage (str): 初始电压值
        high_frequency (str): 高频值
        low_frequency (str): 低频值
        template_dir (str): 模板文件目录路径
    
    Returns:
        dict: 设置结果
    """
    if template_dir is None:
        template_dir = os.path.dirname(os.path.abspath(__file__))
    
    results = {}
    
    def get_screenshot():
        return np.array(ImageGrab.grab())
    
    print(f"\n=== 开始设置CHI测量参数 ===")
    print(f"[配置] 初始电压: {initial_voltage}V")
    print(f"[配置] 高频: {high_frequency}Hz")
    print(f"[配置] 低频: {low_frequency}Hz")
    print(f"[配置] 模板目录: {template_dir}")
    
    try:
        # 步骤1: 打开CHI软件
        print(f"\n[步骤1] 打开CHI软件...")
        open_chi_path = os.path.join(template_dir, "open_CHI.png")
        success, msg = _click_template(open_chi_path, get_screenshot(), 0.6, 1.0)
        results["open_chi"] = (success, msg)
        print(f"[结果] 打开CHI: {'成功' if success else '失败'} - {msg}")
        if not success:
            return results
        
        # 等待CHI软件启动
        print(f"[等待] CHI软件启动中...")
        time.sleep(3)
        
        # 步骤2: 设置IMP_AC_Impedance测量模式 (交换后的新步骤2)
        print(f"\n[步骤2] 设置IMP_AC_Impedance测量模式...")
        try:
            # 导入并执行IMP_AC_Impedance设置
            try:
                from technique_select import setup_impedance_technique
            except ImportError:
                # 如果相对导入失败，尝试绝对导入
                from auto_control.technique_select import setup_impedance_technique
            
            # 调试：打印路径信息
            print(f"[DEBUG] 模板目录: {template_dir}")
            print(f"[DEBUG] 检查路径是否存在: {os.path.exists(template_dir)}")
            print(f"[DEBUG] 检查Technique.png是否存在: {os.path.exists(os.path.join(template_dir, 'Technique.png'))}")
            
            # 使用D盘根目录下的Technique.png避免中文路径问题
            d_drive_template_dir = "D:\\"
            d_technique_path = os.path.join(d_drive_template_dir, "Technique.png")
            print(f"[DEBUG] 使用D盘路径: {d_technique_path}")
            print(f"[DEBUG] D盘Technique.png是否存在: {os.path.exists(d_technique_path)}")
            
            technique_results = setup_impedance_technique(
                template_dir=d_drive_template_dir,  # 使用D盘根目录
                confidence=0.2,  # 提高阈值，根据测试结果调整
                delay=0.1
            )
            
            # 检查IMP_AC_Impedance设置是否成功
            critical_steps = ["Technique", "IMP_AC_Impedance", "Technique_OK"]
            technique_success = all(technique_results.get(step, (False, ""))[0] for step in critical_steps)
            
            if technique_success:
                results["setup_impedance_technique"] = (True, "IMP_AC_Impedance测量模式设置成功")
                print(f"[结果] IMP_AC_Impedance设置: 成功")
            else:
                results["setup_impedance_technique"] = (False, f"IMP_AC_Impedance设置失败: {technique_results}")
                print(f"[结果] IMP_AC_Impedance设置: 失败 - {technique_results}")
                
        except ImportError:
            # 如果导入失败，记录警告但继续执行
            results["setup_impedance_technique"] = (False, "无法导入technique_select模块")
            print(f"[警告] 无法导入technique_select模块，跳过测量模式设置")
        except Exception as tech_error:
            results["setup_impedance_technique"] = (False, f"测量模式设置异常: {str(tech_error)}")
            print(f"[错误] 测量模式设置异常: {str(tech_error)}")
        
        # 等待测量模式设置完成
        time.sleep(2)
        
        # 步骤3: 点击Parameters按钮 (交换后的新步骤3)
        print(f"\n[步骤3] 点击Parameters按钮...")
        parameters_path = os.path.join(template_dir, "Parameters.png")
        success, msg = _click_template(parameters_path, get_screenshot(), 0.6, 1.0)
        results["click_parameters"] = (success, msg)
        print(f"[结果] 点击Parameters: {'成功' if success else '失败'} - {msg}")
        if not success:
            return results
        
        # 等待参数界面加载
        time.sleep(2)
        
        # 步骤4: 设置初始电压
        print(f"\n[步骤4] 设置初始电压: {initial_voltage}V...")
        init_e_path = os.path.join(template_dir, "Init_E.png")
        success, msg = _edit_parameter_field(init_e_path, get_screenshot(), initial_voltage, template_dir, 0.6, 0.5)
        results["set_initial_voltage"] = (success, msg)
        print(f"[结果] 设置初始电压: {'成功' if success else '失败'} - {msg}")
        
        # 步骤5: 设置高频
        print(f"\n[步骤5] 设置高频: {high_frequency}Hz...")
        high_freq_path = os.path.join(template_dir, "High_frequency.png")
        success, msg = _edit_parameter_field(high_freq_path, get_screenshot(), high_frequency, template_dir, 0.6, 0.5)
        results["set_high_frequency"] = (success, msg)
        print(f"[结果] 设置高频: {'成功' if success else '失败'} - {msg}")
        
        # 步骤6: 设置低频
        print(f"\n[步骤6] 设置低频: {low_frequency}Hz...")
        low_freq_path = os.path.join(template_dir, "Low_Frequency.png")
        success, msg = _edit_parameter_field(low_freq_path, get_screenshot(), low_frequency, template_dir, 0.6, 0.5)
        results["set_low_frequency"] = (success, msg)
        print(f"[结果] 设置低频: {'成功' if success else '失败'} - {msg}")
        
        # 步骤7: 按回车确认设置
        print(f"\n[步骤7] 按回车确认设置...")
        time.sleep(1)
        pyautogui.press('enter')
        time.sleep(1)
        results["confirm_settings"] = (True, "回车确认完成")
        print(f"[结果] 确认设置: 成功")
        
        # 步骤8: 再次打开CHI软件
        print(f"\n[步骤8] 再次打开CHI软件...")
        success, msg = _click_template(open_chi_path, get_screenshot(), 0.6, 1.0)
        results["reopen_chi"] = (success, msg)
        print(f"[结果] 再次打开CHI: {'成功' if success else '失败'} - {msg}")
        
        # 等待软件重新加载
        time.sleep(2)
        
        print(f"\n=== CHI参数设置完成 ===")
        
        # 计算成功率
        success_count = sum(1 for success, _ in results.values() if success)
        total_count = len(results)
        success_rate = (success_count / total_count) * 100 if total_count > 0 else 0
        
        print(f"[统计] 总步骤: {total_count}, 成功: {success_count}, 成功率: {success_rate:.1f}%")
        
        return results
        
    except Exception as e:
        print(f"[错误] CHI参数设置过程出错: {str(e)}")
        results["error"] = (False, str(e))
        return results

if __name__ == "__main__":
    # 测试函数
    print("测试CHI参数设置功能...")
    result = setup_chi_parameters("0", "10000", "1")
    
    print("\n==== 执行结果 ====")
    for step, (success, msg) in result.items():
        status = "成功" if success else "失败"
        print(f"{step.ljust(20)}: {status} - {msg}")
