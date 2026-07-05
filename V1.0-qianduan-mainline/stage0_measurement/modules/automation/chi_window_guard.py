# -*- coding: utf-8 -*-
"""
CHI 窗口守卫（B 方案 / L1 接入版）

目标：消灭"图像自动化点到 CHI 之外的窗口 / 焦点被别的窗口（浏览器、PDF）抢走"的根因，
且**完全不改任何模板匹配置信度阈值、不改现有点击坐标算法**。提供：
  1) activate()     —— 操作前强制把 CHI 主窗口恢复 + 置于前台 + 抢焦点，并用 win32 校验；
  2) grab_region()  —— 只截取 CHI 窗口矩形内画面 + 返回偏移（L2 用，本次 L1 不强制使用）；
  3) is_foreground / get_region / point_in_window —— 辅助判定。

设计原则（务必保持）：
  - 纯前置守卫，不驱动测量、不改业务流程；
  - 依赖（pywinauto / win32gui / Pillow / numpy）全部**惰性导入**，缺依赖时优雅降级
    （返回 (False, reason) / None），绝不在 import 阶段崩溃，绝不连累主路径；
  - 只"连接"已运行的 CHI，**绝不**启动新进程、绝不用 /runmacro。

真机验证：2026-06-14 在隔离原型 chi_macro_prototype/ 下验证——激活前区域截到的是盖在
CHI 上的 PDF（重现"点到别的窗口"），activate() 一次即把 CHI 抢到前台（win32 校验
foreground=True），之后区域截图为真正的 CHI 窗口，命中坐标全部落在 CHI 矩形内。
"""
from __future__ import annotations

import time
from typing import Optional, Tuple


class ChiWindowGuard:
    """连接到正在运行的 CHI 主窗口，提供激活 + 窗口区域截图。"""

    def __init__(self, title_re: str = ".*CHI660E.*", connect_timeout: float = 5.0):
        self.title_re = title_re
        self.connect_timeout = connect_timeout
        self._app = None
        self._win = None  # pywinauto WindowSpecification（连接成功后缓存）

    # ------------------------------------------------------------------
    # 连接
    # ------------------------------------------------------------------
    def connect(self) -> Tuple[bool, str]:
        """连接到已运行的 CHI（不启动新进程）。返回 (ok, reason)。"""
        try:
            from pywinauto.application import Application
        except Exception as exc:  # noqa: BLE001
            return False, f"pywinauto unavailable: {exc}"
        try:
            self._app = Application(backend="win32").connect(
                title_re=self.title_re, timeout=self.connect_timeout
            )
            self._win = self._app.top_window()
            return True, "connected"
        except Exception as exc:  # noqa: BLE001
            self._app = None
            self._win = None
            return False, f"connect failed: {exc}"

    def _win_is_valid(self) -> bool:
        """缓存的窗口句柄是否仍指向一个存在的窗口。

        无法校验（缺 win32gui）时信任缓存，保持旧行为、避免反复重连。
        """
        if self._win is None:
            return False
        try:
            import win32gui
        except Exception:  # noqa: BLE001
            return True
        try:
            h = int(self._win.handle)
            return bool(win32gui.IsWindow(h))
        except Exception:  # noqa: BLE001
            return False

    def _ensure_win(self) -> bool:
        # 句柄仍有效则直接用；失效（CHI 关闭/重启导致 stale）则丢弃并自动重连一次，
        # 保证长 campaign 中途重开 CHI 后守卫不会"哑火"。
        if self._win_is_valid():
            return True
        self._win = None
        self._app = None
        ok, _ = self.connect()
        return ok

    # ------------------------------------------------------------------
    # 句柄 / 前台判定
    # ------------------------------------------------------------------
    def hwnd(self) -> Optional[int]:
        if not self._ensure_win():
            return None
        try:
            return int(self._win.handle)
        except Exception:  # noqa: BLE001
            return None

    def is_foreground(self) -> bool:
        """CHI 主窗口（或其拥有的弹窗）是否就是当前前台窗口。"""
        try:
            import win32gui
        except Exception:  # noqa: BLE001
            return False
        h = self.hwnd()
        if h is None:
            return False
        try:
            fg = win32gui.GetForegroundWindow()
            if fg == h:
                return True
            # CHI 弹出的模态子窗口（另存为/宏对话框）也算"在 CHI 之内"：
            # 其根 owner 应为 CHI 主窗口。GA_ROOTOWNER = 3。
            try:
                GA_ROOTOWNER = 3
                root = win32gui.GetAncestor(fg, GA_ROOTOWNER)
            except Exception:  # noqa: BLE001
                root = None
            return root == h
        except Exception:  # noqa: BLE001
            return False

    # ------------------------------------------------------------------
    # 激活（B 方案核心动作之一）
    # ------------------------------------------------------------------
    def activate(self, retries: int = 4, settle_s: float = 0.4) -> Tuple[bool, str]:
        """仅在 CHI 不在前台时才把它抢回前台；已在前台则零动作。

        与图像自动化的"无冲突"保证（重要）：
          - 若 CHI 主窗口或其拥有的模态弹窗（如"另存为"对话框）已是前台，直接返回，
            **不调用 restore/set_focus/SetForegroundWindow**——绝不打扰正在交互的对话框；
          - 只在窗口**最小化**时才 restore()，绝不把用户最大化的 CHI 还原变小；
          - 全程不移动鼠标、不截图、不碰模板与坐标，因此不与 matchTemplate 点击冲突。
        """
        if not self._ensure_win():
            return False, "no CHI window (connect failed)"
        # 健康路径：已在前台（含 CHI 拥有的模态对话框）→ 零动作，避免任何干扰。
        if self.is_foreground():
            return True, "already foreground (no-op)"
        last = ""
        for attempt in range(1, retries + 1):
            # 仅当最小化时才恢复，避免把最大化窗口还原变小（不改用户窗口布局）。
            try:
                import win32gui
                h = self.hwnd()
                if h is not None and win32gui.IsIconic(h):
                    self._win.restore()
            except Exception as exc:  # noqa: BLE001
                last = f"restore: {exc}"
            try:
                self._win.set_focus()
            except Exception as exc:  # noqa: BLE001
                last = f"set_focus: {exc}"
            # win32 兜底：SetForegroundWindow（set_focus 偶尔不抢前台）。
            # 注意：若主窗口拥有活动模态弹窗，Windows 会把弹窗带到前台，符合预期。
            try:
                import win32gui
                h = self.hwnd()
                if h is not None:
                    win32gui.SetForegroundWindow(h)
            except Exception as exc:  # noqa: BLE001
                last = f"SetForegroundWindow: {exc}"
            time.sleep(settle_s)
            if self.is_foreground():
                return True, f"foreground after {attempt} attempt(s)"
        return False, f"could not bring CHI to foreground ({last})"

    # ------------------------------------------------------------------
    # 窗口矩形 / 区域截图（B 方案核心动作之二，L2 用）
    # ------------------------------------------------------------------
    def get_region(self) -> Optional[Tuple[int, int, int, int]]:
        """返回 CHI 主窗口屏幕矩形 (left, top, right, bottom)。失败返回 None。"""
        if not self._ensure_win():
            return None
        try:
            r = self._win.rectangle()
            return (int(r.left), int(r.top), int(r.right), int(r.bottom))
        except Exception:  # noqa: BLE001
            return None

    def grab_region(self):
        """只截取 CHI 窗口矩形内的画面。

        返回 (np_rgb_image, (offset_left, offset_top))；失败返回 (None, None)。
        命中坐标换算：abs_x = offset_left + match_x，abs_y = offset_top + match_y。
        """
        region = self.get_region()
        if region is None:
            return None, None
        left, top, right, bottom = region
        if right <= left or bottom <= top:
            return None, None
        try:
            import numpy as np
            from PIL import ImageGrab
            img = ImageGrab.grab(bbox=(left, top, right, bottom))
            arr = np.array(img)  # RGB，与 chi_executor 的 ImageGrab.grab() 一致
            return arr, (left, top)
        except Exception:  # noqa: BLE001
            return None, None

    def point_in_window(self, x: int, y: int) -> bool:
        """判断屏幕绝对坐标是否落在 CHI 窗口矩形内（用于点击前的安全断言）。"""
        region = self.get_region()
        if region is None:
            return False
        left, top, right, bottom = region
        return left <= x <= right and top <= y <= bottom
