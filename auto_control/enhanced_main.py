    def _perform_measurement(self):
        """执行测量 - 智能自适应版"""
        if self.measurement_lock:
            print("测量进行中，跳过")
            return 0

        self.measurement_lock = True
        try:
            # 确保有当前温度数据
            if self.current_temp is None:
                self.current_temp = self.read_temperature()
                if self.current_temp is None:
                    print("无法获取当前温度，跳过测量")
                    return 0
            
            print(f"开始测量，当前温度: {self.current_temp:.1f}°C")
            
            # 更新CHI参数中的温度
            self.chi_params["T"] = str(int(self.current_temp + 273.15))
            
            # 执行CHI测量
            print("开始CHI测量...")
            result = self.perform_chi_measurement()
            
            # 处理测量结果
            if result:
                print("CHI测量成功")
                # 记录温度历史
                if self.current_temp is not None:
                    self.temperature_history.append({
                        'temperature': self.current_temp,
                        'timestamp': datetime.now().isoformat()
                    })
                    print(f"测量完成，温度: {self.current_temp:.1f}°C")
                return 1  # 测量成功
            else:
                print("CHI测量失败")
                return 0  # 测量失败
            
        except Exception as e:
            print(f"测量失败: {e}")
            import traceback
            traceback.print_exc()
            return 0  # 测量失败
        finally:
            self.measurement_lock = False

    def perform_chi_measurement(self) -> bool:
        """
        执行CHI测量流程
        :return: 是否成功
        """
        print("\n>>> 开始CHI测量流程 <<<")

        # 1. 打开CHI仪器
        print("正在打开CHI仪器...")
        success = self.open_chi_instrument()
        if not success:
            print("CHI仪器打开失败")
            return False

        # 2. 执行测量
        print("执行CHI测量...")
        result = self.run_chi_measurement()

        # 3. 关闭CHI仪器
        print("正在关闭CHI仪器...")
        success = self.open_chi_instrument()  # 再次调用open_chi_instrument关闭
        if not success:
            print("CHI仪器关闭失败")

        # 根据测量结果返回成功状态
        if all(success for step, (success, msg) in result.items()):
            print("CHI测量完全成功")
            return True
        else:
            print("CHI测量部分失败")
            return False

    def open_chi_instrument(self) -> bool:
        """打开CHI仪器界面"""
        try:
            # 1. 读取模板
            template_path = os.path.join(self.chi_params["template_dir"], "open_CHI.png")
            template = cv2.imread(template_path)
            if template is None:
                print(f"模板文件不存在: {template_path}")
                return False

            # 2. 屏幕匹配
            screenshot = np.array(ImageGrab.grab())
            screenshot = cv2.cvtColor(screenshot, cv2.COLOR_RGB2BGR)
            res = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)

            if max_val < self.chi_params["text_confidence"] / 100:
                print(f"匹配失败(相似度: {max_val:.2f})")
                return False

            # 3. 计算并点击中心位置
            h, w = template.shape[:2]
            center_x = max_loc[0] + w // 2
            center_y = max_loc[1] + h // 2
            pyautogui.click(center_x, center_y)
            time.sleep(self.chi_params["delay"])

            return True
        except Exception as e:
            print(f"打开CHI仪器错误: {str(e)}")
            return False

    def run_chi_measurement(self) -> dict:
        """执行CHI测量流程"""
        results = {}
        screenshot = None

        def get_screenshot():
            nonlocal screenshot
            screenshot = np.array(ImageGrab.grab())
            return cv2.cvtColor(screenshot, cv2.COLOR_RGB2BGR)

        # 1. 点击开始测量
        start_measure_path = os.path.join(self.chi_params["template_dir"], "start_to_measure.png")
        success, msg = self.click_template(start_measure_path, get_screenshot())
        results["start_measure"] = (success, msg)
        if not success:
            return results

        # 2. 初始等待8秒
        time.sleep(8)

        # 3. 捕获剩余时间
        remain_time = self.capture_remaining_time(get_screenshot())
        if remain_time > 0:
            total_wait = remain_time + 5
            time.sleep(total_wait)
            results["wait_time"] = (True, f"等待完成 (检测到{remain_time:.1f}s + 5s缓冲)")
        else:
            results["wait_time"] = (False, "未检测到剩余时间")
            return results

        # 4. 点击另存为
        save_as_path = os.path.join(self.chi_params["template_dir"], "save_as.png")
        success, msg = self.click_template(save_as_path, get_screenshot())
        results["save_as"] = (success, msg)
        if not success:
            return results

        # 5. 点击保存类型框
        type_saving_path = os.path.join(self.chi_params["template_dir"], "type_saving.png")
        success, msg = self.click_dynamic_text_box(
            template_path=type_saving_path,
            screenshot=get_screenshot(),
            fixed_side="left",
            click_side="right",
            fixed_text="保存类型"
        )
        results["type_saving"] = (success, msg)
        if not success:
            return results

        # 6. 点击指定类型
        white_path = os.path.join(self.chi_params["template_dir"], "your_type_white.png")
        blue_path = os.path.join(self.chi_params["template_dir"], "your_type_blue.png")
        success, msg = self.click_template(white_path, get_screenshot())
        if not success:
            success, msg = self.click_template(blue_path, get_screenshot())
        results["your_type"] = (success, msg)
        if not success:
            return results

        # 7. 编辑文件名
        filename = f"{self.chi_params['material']}_T{self.chi_params['T']}_highf{self.chi_params['highf']}_lowf{self.chi_params['lowf']}_initV{self.chi_params['initV']}"
        name_of_dc_path = os.path.join(self.chi_params["template_dir"], "name_of_dc.png")
        success, msg = self.edit_text_box(name_of_dc_path, get_screenshot(), filename, "right")
        results["name_edit"] = (success, msg)
        if not success:
            return results

        # 8. 编辑保存位置
        directory_icon_path = os.path.join(self.chi_params["template_dir"], "Directory.png")
        success, msg = self.locate_address_field(directory_icon_path, get_screenshot())
        if success:
            try:
                time.sleep(0.5)
                pyautogui.write(self.chi_params["your_position"])
                time.sleep(self.chi_params["delay"])
                msg = f"地址已修改为: {self.chi_params['your_position']}"
            except Exception as e:
                success = False
                msg = f"地址输入失败: {str(e)}"
        results["position_edit"] = (success, msg)
        if not success:
            return results

        # 9. 点击保存按钮
        save_button_path = os.path.join(self.chi_params["template_dir"], "bao_cun.png")
        success, msg = self.click_template(save_button_path, get_screenshot())
        results["save_button"] = (success, msg)

        return results