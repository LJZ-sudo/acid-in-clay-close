# -*- coding: utf-8 -*-
"""
CHI 仪器桌面自动化执行器（纯函数版）

纯粹的"自动打字员"，执行 CHI GUI 自动化操作

核心原则：
1. 纯执行 - 只负责 UI 自动化，不生成模拟数据
2. 标准错误字典 - 失败时如实返回错误，绝不伪造数据
3. 参数化配置 - 所有硬编码提取为配置字典
4. 无业务逻辑 - 不保存历史，不触发回调

关键安全约束：
- 禁止生成随机模拟数据！
- UI 操作失败时必须如实返回 {"success": False, "error": "..."}
- 不污染真实数据流

版本：3.0.0 (重构版)
"""

import os
import time
from typing import Dict, Tuple, Optional

import cv2
import numpy as np
import pyautogui
from PIL import ImageGrab


# ============================================================
# 公共接口：CHI 测量执行器
# ============================================================

class ChiExecutor:
    """
    CHI 仪器桌面自动化执行器
    
    纯粹的 UI 自动化工具，不包含业务逻辑
    """
    
    def __init__(self, config=None):
        """
        初始化执行器
        
        Args:
            config: 配置字典（可选），包含以下字段：
                - template_dir: 模板图片目录
                - confidence: 默认匹配置信度（0-1）
                - delay: 默认操作延迟（秒）
                - wait_times: 等待时间配置
                - click_offsets: 点击偏移配置
        """
        self.config = config or self._get_default_config()

    def close(self):
        """Release GUI automation state.

        The executor does not own a persistent CHI process handle, so close is
        intentionally idempotent. It exists so online workflows can abort or
        finalize without depending on optional implementation details.
        """
        return None
    
    def execute_measurement(
        self,
        chi_params,
        output_dir,
        current_temperature_C=None
    ):
        """
        执行完整的 CHI 测量流程（纯函数版主入口）
        
        Args:
            chi_params: CHI 参数字典
                - material: 材料名称
                - highf: 高频 (Hz)
                - lowf: 低频 (Hz)
                - initV: 初始电位 (V)
                - your_position: 保存目录
                - template_dir: 模板目录
            output_dir: 输出目录（保存 EIS 数据）
            current_temperature_C: 当前温度 (°C)，用于文件命名
        
        Returns:
            dict: 包含以下字段
                - success: bool，整体是否成功
                - frequencies: np.ndarray or None，频率数据
                - z_real: np.ndarray or None，阻抗实部
                - z_imag: np.ndarray or None，阻抗虚部
                - output_file: str or None，保存的文件路径
                - steps: dict，每个步骤的结果
                - error: str or None，失败原因
        """
        # 验证输入
        required_keys = ['material', 'highf', 'lowf', 'initV', 'your_position', 'template_dir']
        for key in required_keys:
            if key not in chi_params:
                return {
                    'success': False,
                    'frequencies': None,
                    'z_real': None,
                    'z_imag': None,
                    'output_file': None,
                    'steps': {},
                    'error': f'Missing required CHI parameter: {key}'
                }
        
        # 验证保存目录
        try:
            os.makedirs(chi_params['your_position'], exist_ok=True)
        except Exception as e:
            return {
                'success': False,
                'frequencies': None,
                'z_real': None,
                'z_imag': None,
                'output_file': None,
                'steps': {},
                'error': f'Failed to create save directory: {str(e)}'
            }
        
        # 生成文件名（带时间戳后缀防止冲突）
        temp_str = f"{current_temperature_C:.1f}" if current_temperature_C is not None else "unknown"
        
        # 基础文件名
        base_filename = f"{chi_params['material']}_T{temp_str}_f{chi_params['lowf']}_{chi_params['highf']}_V{chi_params['initV']}"
        
        # 检查文件是否已存在，如果存在则添加序号后缀
        output_path = chi_params['your_position']
        filename = base_filename
        counter = 1
        
        while os.path.exists(os.path.join(output_path, f"{filename}.txt")):
            filename = f"{base_filename}_#{counter}"
            counter += 1
        
        # 如果添加了序号，在日志中说明
        if counter > 1:
            print(f"   [CHI] 检测到重复文件名，添加序号: {filename}.txt")
        
        # 执行 UI 自动化流程
        steps_result = {}
        
        # 获取屏幕截图函数
        def get_screenshot():
            return np.array(ImageGrab.grab())
        
        # 步骤 1: 打开 CHI 软件
        step_result = self._step_open_chi(chi_params['template_dir'], get_screenshot)
        steps_result['open_chi'] = step_result
        if not step_result['success']:
            return {
                'success': False,
                'frequencies': None,
                'z_real': None,
                'z_imag': None,
                'output_file': None,
                'steps': steps_result,
                'error': f"Step 1 failed: {step_result['error']}"
            }
        
        # 步骤 2: 点击开始测量
        step_result = self._step_start_measurement(chi_params['template_dir'], get_screenshot)
        steps_result['start_measurement'] = step_result
        if not step_result['success']:
            return {
                'success': False,
                'frequencies': None,
                'z_real': None,
                'z_imag': None,
                'output_file': None,
                'steps': steps_result,
                'error': f"Step 2 failed: {step_result['error']}"
            }
        
        # 步骤 3: 等待测量完成
        step_result = self._step_wait_measurement(chi_params['highf'], chi_params['lowf'])
        steps_result['wait_measurement'] = step_result
        if not step_result['success']:
            return {
                'success': False,
                'frequencies': None,
                'z_real': None,
                'z_imag': None,
                'output_file': None,
                'steps': steps_result,
                'error': f"Step 3 failed: {step_result['error']}"
            }
        
        # 步骤 4: 保存数据
        step_result = self._step_save_data(chi_params, filename, get_screenshot)
        steps_result['save_data'] = step_result
        if not step_result['success']:
            return {
                'success': False,
                'frequencies': None,
                'z_real': None,
                'z_imag': None,
                'output_file': None,
                'steps': steps_result,
                'error': f"Step 4 failed: {step_result['error']}"
            }
        
        # 步骤 5: 读取保存的数据文件
        expected_file = os.path.join(chi_params['your_position'], filename + ".txt")
        step_result = self._step_read_data_file(expected_file)
        steps_result['read_data'] = step_result
        
        if not step_result['success']:
            return {
                'success': False,
                'frequencies': None,
                'z_real': None,
                'z_imag': None,
                'output_file': expected_file,
                'steps': steps_result,
                'error': f"Step 5 failed: {step_result['error']}"
            }
        
        # 成功返回
        return {
            'success': True,
            'frequencies': step_result['frequencies'],
            'z_real': step_result['z_real'],
            'z_imag': step_result['z_imag'],
            'output_file': expected_file,
            'steps': steps_result,
            'error': None
        }
    
    # ========================================================
    # 内部函数：UI 自动化步骤
    # ========================================================
    
    def _step_open_chi(self, template_dir, get_screenshot):
        """步骤：打开 CHI 软件"""
        template_path = os.path.join(template_dir, "open_CHI.png")
        
        if not os.path.exists(template_path):
            return {
                'success': False,
                'error': f'Template not found: {template_path}'
            }
        
        screenshot = get_screenshot()
        success, msg = self._click_template(template_path, screenshot)
        
        if not success:
            return {
                'success': False,
                'error': f'Failed to open CHI software: {msg}'
            }
        
        # 等待软件启动
        time.sleep(self.config['wait_times']['chi_startup'])
        
        return {
            'success': True,
            'message': msg,
            'error': None
        }
    
    def _step_start_measurement(self, template_dir, get_screenshot):
        """步骤：点击开始测量"""
        template_path = os.path.join(template_dir, "start_to_measure.png")
        
        if not os.path.exists(template_path):
            return {
                'success': False,
                'error': f'Template not found: {template_path}'
            }
        
        screenshot = get_screenshot()
        success, msg = self._click_template(template_path, screenshot)
        
        if not success:
            return {
                'success': False,
                'error': f'Failed to start measurement: {msg}'
            }
        
        return {
            'success': True,
            'message': msg,
            'error': None
        }
    
    def _step_wait_measurement(self, highf, lowf):
        """步骤：等待测量完成"""
        # 计算等待时间
        wait_seconds = self._calculate_measurement_time(highf, lowf)
        
        # 初始等待
        time.sleep(self.config['wait_times']['initial'])
        
        # 测量等待
        time.sleep(wait_seconds)
        
        return {
            'success': True,
            'wait_seconds': wait_seconds,
            'error': None
        }
    
    def _step_save_data(self, chi_params, filename, get_screenshot):
        """步骤：保存数据"""
        template_dir = chi_params['template_dir']
        
        # 4.1: 点击另存为
        result = self._substep_save_as(template_dir, get_screenshot)
        if not result['success']:
            return result
        
        # 4.2: 选择保存类型
        result = self._substep_select_save_type(template_dir, get_screenshot)
        if not result['success']:
            return result
        
        # 4.3: 选择文件类型
        result = self._substep_select_file_type(template_dir, get_screenshot)
        if not result['success']:
            return result
        
        # 4.4: 点击目录图标
        result = self._substep_click_directory(template_dir, get_screenshot)
        if not result['success']:
            return result
        
        # 4.5: 进入文件夹
        result = self._substep_enter_folder()
        if not result['success']:
            return result
        
        # 4.6: 编辑文件名
        result = self._substep_edit_filename(template_dir, filename, get_screenshot)
        if not result['success']:
            return result
        
        # 4.7: 保存文件
        result = self._substep_save_file()
        if not result['success']:
            return result
        
        # 4.8: 重新打开 CHI
        result = self._substep_reopen_chi(template_dir, get_screenshot)
        # 重新打开失败不算致命错误，继续
        
        return {
            'success': True,
            'error': None
        }
    
    def _step_read_data_file(self, filepath):
        """步骤：读取保存的数据文件"""
        # 等待文件生成
        time.sleep(self.config['wait_times']['file_generation'])
        
        if not os.path.exists(filepath):
            return {
                'success': False,
                'frequencies': None,
                'z_real': None,
                'z_imag': None,
                'error': f'Data file not found: {filepath}'
            }
        
        # 读取文件
        try:
            frequencies, z_real, z_imag = self._parse_chi_data_file(filepath)
            
            if frequencies is None:
                return {
                    'success': False,
                    'frequencies': None,
                    'z_real': None,
                    'z_imag': None,
                    'error': f'Failed to parse data file: {filepath}'
                }
            
            if len(frequencies) < 10:
                return {
                    'success': False,
                    'frequencies': frequencies,
                    'z_real': z_real,
                    'z_imag': z_imag,
                    'error': f'Insufficient data points: {len(frequencies)} < 10'
                }
            
            return {
                'success': True,
                'frequencies': frequencies,
                'z_real': z_real,
                'z_imag': z_imag,
                'n_points': len(frequencies),
                'error': None
            }
        
        except Exception as e:
            return {
                'success': False,
                'frequencies': None,
                'z_real': None,
                'z_imag': None,
                'error': f'Exception reading data file: {str(e)}'
            }
    
    # ========================================================
    # 内部函数：子步骤
    # ========================================================
    
    def _substep_save_as(self, template_dir, get_screenshot):
        """子步骤：点击另存为"""
        template_path = os.path.join(template_dir, "save_as.png")
        screenshot = get_screenshot()
        success, msg = self._click_template(template_path, screenshot)
        
        if not success:
            return {'success': False, 'error': f'Failed to click save_as: {msg}'}
        
        return {'success': True, 'error': None}
    
    def _substep_select_save_type(self, template_dir, get_screenshot):
        """子步骤：选择保存类型"""
        template_path = os.path.join(template_dir, "type_saving.png")
        
        # 多次尝试不同置信度
        confidence_levels = self.config['retry_confidences']
        
        for conf in confidence_levels:
            screenshot = get_screenshot()
            success, msg = self._click_template(template_path, screenshot, confidence=conf)
            
            if success:
                time.sleep(self.config['wait_times']['dropdown'])
                return {'success': True, 'error': None}
            
            time.sleep(self.config['wait_times']['retry'])
        
        return {
            'success': False,
            'error': 'Failed to select save type after all retries'
        }
    
    def _substep_select_file_type(self, template_dir, get_screenshot):
        """子步骤：选择文件类型"""
        white_path = os.path.join(template_dir, "your_type_white.png")
        blue_path = os.path.join(template_dir, "your_type_blue.png")
        
        confidence_levels = self.config['retry_confidences']
        
        for conf in confidence_levels:
            screenshot = get_screenshot()
            
            # 尝试白色模板
            success, msg = self._click_template(white_path, screenshot, confidence=conf)
            if success:
                time.sleep(self.config['wait_times']['dropdown'])
                return {'success': True, 'error': None}
            
            # 尝试蓝色模板
            success, msg = self._click_template(blue_path, screenshot, confidence=conf)
            if success:
                time.sleep(self.config['wait_times']['dropdown'])
                return {'success': True, 'error': None}
            
            time.sleep(self.config['wait_times']['retry'])
        
        return {
            'success': False,
            'error': 'Failed to select file type after all retries'
        }
    
    def _substep_click_directory(self, template_dir, get_screenshot):
        """子步骤：点击目录图标"""
        template_path = os.path.join(template_dir, "Directory.png")
        
        confidence_levels = self.config['retry_confidences']
        
        for conf in confidence_levels:
            screenshot = get_screenshot()
            success, msg = self._locate_and_click_address_field(template_path, screenshot, confidence=conf)
            
            if success:
                return {'success': True, 'error': None}
            
            time.sleep(self.config['wait_times']['retry'])
        
        return {
            'success': False,
            'error': 'Failed to click directory icon after all retries'
        }
    
    def _substep_enter_folder(self):
        """子步骤：按 Enter 键进入文件夹"""
        try:
            pyautogui.press('enter')
            time.sleep(self.config['wait_times']['enter'])
            return {'success': True, 'error': None}
        except Exception as e:
            return {'success': False, 'error': f'Failed to press Enter: {str(e)}'}
    
    def _substep_edit_filename(self, template_dir, filename, get_screenshot):
        """子步骤：编辑文件名"""
        template_path = os.path.join(template_dir, "name_of_dc.png")
        
        # 文件名编辑使用更低的置信度
        confidence_levels = self.config['filename_confidences']
        
        for conf in confidence_levels:
            screenshot = get_screenshot()
            success, msg = self._edit_text_box_clipboard(
                template_path, screenshot, filename, side='right', confidence=conf
            )
            
            if success:
                return {'success': True, 'error': None}
            
            time.sleep(self.config['wait_times']['retry'])
        
        return {
            'success': False,
            'error': 'Failed to edit filename after all retries'
        }
    
    def _substep_save_file(self):
        """子步骤：按两次 Enter 保存文件"""
        try:
            # 第一次 Enter：确认文件名
            pyautogui.press('enter')
            time.sleep(self.config['wait_times']['enter'])
            
            # 第二次 Enter：执行保存
            pyautogui.press('enter')
            time.sleep(self.config['wait_times']['save'])
            
            return {'success': True, 'error': None}
        except Exception as e:
            return {'success': False, 'error': f'Failed to save file: {str(e)}'}
    
    def _substep_reopen_chi(self, template_dir, get_screenshot):
        """子步骤：重新打开 CHI（非致命）"""
        template_path = os.path.join(template_dir, "open_CHI.png")
        screenshot = get_screenshot()
        success, msg = self._click_template(template_path, screenshot)
        
        if success:
            time.sleep(self.config['wait_times']['chi_startup'])
        
        return {
            'success': success,
            'error': None if success else msg
        }
    
    # ========================================================
    # 内部函数：底层操作
    # ========================================================
    
    def _click_template(self, template_path, screenshot, confidence=None):
        """模板匹配点击"""
        if confidence is None:
            confidence = self.config['confidence']
        
        try:
            template = self._load_template(template_path)
            if template is None:
                return False, f'Template not found: {template_path}'
            
            res = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)
            
            if max_val < confidence:
                return False, f'Match confidence too low: {max_val:.4f} < {confidence}'
            
            # 计算点击位置（模板中心）
            h, w = template.shape[:2]
            click_x = max_loc[0] + w // 2
            click_y = max_loc[1] + h // 2
            
            pyautogui.click(click_x, click_y)
            time.sleep(self.config['delay'])
            
            return True, f'Clicked successfully (confidence: {max_val:.4f})'
        
        except Exception as e:
            return False, f'Click error: {str(e)}'
    
    def _locate_and_click_address_field(self, template_path, screenshot, confidence=None):
        """定位并双击地址字段"""
        if confidence is None:
            confidence = self.config['confidence']
        
        try:
            template = self._load_template(template_path)
            if template is None:
                return False, f'Template not found: {template_path}'
            
            res = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)
            
            if max_val < confidence:
                return False, f'Match confidence too low: {max_val:.4f} < {confidence}'
            
            # 计算点击位置
            h, w = template.shape[:2]
            click_x = max_loc[0] + w // 2
            click_y = max_loc[1] + h // 2
            
            # 双击
            pyautogui.click(click_x, click_y)
            time.sleep(1.0)
            pyautogui.click(click_x, click_y)
            time.sleep(0.5)
            
            return True, f'Double clicked successfully (confidence: {max_val:.4f})'
        
        except Exception as e:
            return False, f'Address field click error: {str(e)}'
    
    def _edit_text_box_clipboard(self, template_path, screenshot, text, side='right', confidence=None):
        """使用剪贴板编辑文本框"""
        if confidence is None:
            confidence = self.config['confidence']
        
        try:
            template = self._load_template(template_path)
            if template is None:
                return False, f'Template not found: {template_path}'
            
            res = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)
            
            if max_val < confidence:
                return False, f'Match confidence too low: {max_val:.4f} < {confidence}'
            
            # 计算点击位置（带偏移）
            h, w = template.shape[:2]
            if side == 'right':
                click_x = max_loc[0] + w + self.config['click_offsets']['textbox_right']
            else:
                click_x = max_loc[0] + self.config['click_offsets']['textbox_left']
            
            click_y = max_loc[1] + h // 2
            
            # 特殊处理：目录相关模板
            if 'Directory' in template_path or 'saving_position' in template_path:
                click_x = max_loc[0] + self.config['click_offsets']['directory']
            
            # 双击激活
            pyautogui.click(click_x, click_y)
            time.sleep(self.config['delay'] + 0.5)
            pyautogui.click(click_x, click_y)
            time.sleep(0.5)
            
            # 清空内容
            pyautogui.hotkey('ctrl', 'a')
            time.sleep(0.5)
            pyautogui.press('backspace')
            time.sleep(0.5)
            
            # 使用剪贴板粘贴
            try:
                import pyperclip
                pyperclip.copy(text)
                time.sleep(0.3)
                pyautogui.hotkey('ctrl', 'v')
                time.sleep(0.5)
            except (ImportError, Exception):
                # 回退：使用 Windows 剪贴板
                try:
                    import win32clipboard
                    win32clipboard.OpenClipboard()
                    win32clipboard.EmptyClipboard()
                    win32clipboard.SetClipboardText(text)
                    win32clipboard.CloseClipboard()
                    time.sleep(0.3)
                    pyautogui.hotkey('ctrl', 'v')
                    time.sleep(0.5)
                except Exception:
                    # 最后回退：逐字输入
                    pyautogui.typewrite(text, interval=0.05)
            
            time.sleep(1.0)
            
            return True, f'Text box edited: {text}'
        
        except Exception as e:
            return False, f'Text box edit error: {str(e)}'
    
    # ========================================================
    # 内部函数：工具函数
    # ========================================================
    
    def _load_template(self, path):
        """加载模板图片（支持 Unicode 路径）"""
        try:
            template = cv2.imread(path)
            if template is None:
                # 回退到 PIL
                from PIL import Image
                pil_image = Image.open(path)
                template = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
            return template
        except Exception:
            return None
    
    def _calculate_measurement_time(self, highf, lowf):
        """计算测量等待时间"""
        try:
            high_freq = float(highf)
            low_freq = float(lowf)
        except (ValueError, TypeError):
            return self.config['wait_times']['measurement_default']
        
        time_mapping = self.config['measurement_time_mapping']
        
        # 查找精确匹配
        key = (high_freq, low_freq)
        if key in time_mapping:
            return int(time_mapping[key] * 1.05)  # 添加 5% 余量
        
        # 估算
        if low_freq <= 0.01:
            base_time = 820 if high_freq >= 500000 else 810
        elif low_freq <= 0.1:
            base_time = 200 if high_freq >= 500000 else 170
        elif low_freq <= 1:
            base_time = 150 if high_freq >= 500000 else 120
        else:
            base_time = 100
        
        return int(base_time * 1.05)
    
    def _parse_chi_data_file(self, filepath):
        """解析 CHI 数据文件"""
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
            # 查找数据起始行
            data_rows = []
            for line in lines:
                parsed = self._try_parse_three_floats(line)
                if parsed is not None:
                    data_rows.append(parsed)
            
            if len(data_rows) == 0:
                return None, None, None
            
            # 转换为 numpy 数组
            data = np.array(data_rows)
            frequencies = data[:, 0]
            z_real = data[:, 1]
            z_imag = data[:, 2]
            
            return frequencies, z_real, z_imag
        
        except Exception:
            return None, None, None
    
    def _try_parse_three_floats(self, line):
        """尝试从一行解析三个浮点数"""
        line = line.strip()
        if not line:
            return None
        
        # 跳过表头和注释
        skip_prefixes = [
            '#', '//', 'Frequency', 'Date', 'Init', 'High', 'Low',
            'Amplitude', 'Quiet', 'Cycles', 'Instrument'
        ]
        if any(line.startswith(prefix) for prefix in skip_prefixes):
            return None
        
        # 尝试不同分隔符
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
    
    def _get_default_config(self):
        """获取默认配置"""
        return {
            'confidence': 0.5,
            'delay': 1.0,
            'wait_times': {
                'chi_startup': 3.0,      # CHI 软件启动等待
                'initial': 8.0,          # 初始等待
                'measurement_default': 220,  # 默认测量时间
                'dropdown': 0.8,         # 下拉菜单展开等待
                'retry': 0.8,            # 重试间隔
                'enter': 1.0,            # Enter 键后等待
                'save': 2.0,             # 保存后等待
                'file_generation': 2.0,  # 文件生成等待
            },
            'click_offsets': {
                'textbox_right': -15,    # 文本框右侧偏移
                'textbox_left': 15,      # 文本框左侧偏移
                'directory': 30,         # 目录图标偏移
            },
            'retry_confidences': [0.5, 0.4, 0.3, 0.2, 0.1],  # 重试置信度序列
            'filename_confidences': [0.1, 0.05, 0.03, 0.02, 0.01],  # 文件名编辑置信度
            'measurement_time_mapping': {
                (1000000, 0.01): 820,
                (1000000, 0.1): 200,
                (1000000, 1): 150,
                (100000, 0.01): 810,
                (100000, 0.1): 170,
                (100000, 1): 120,
            }
        }


# ============================================================
# 辅助函数：独立工具函数
# ============================================================

def calculate_chi_measurement_time(high_freq, low_freq, config=None):
    """
    计算 CHI 测量等待时间（独立函数）
    
    Args:
        high_freq: 高频 (Hz)
        low_freq: 低频 (Hz)
        config: 配置字典（可选）
    
    Returns:
        int: 等待时间（秒）
    """
    executor = ChiExecutor(config)
    return executor._calculate_measurement_time(high_freq, low_freq)
