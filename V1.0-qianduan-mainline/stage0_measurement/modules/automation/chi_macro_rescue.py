# -*- coding: utf-8 -*-
"""
CHI 宏命令"救援存盘"执行器(Macro Command tsave rescue)—— 已真机验证

定位:这是 ``chi_executor.py``(图像自动化主路径)的**故障兜底**,不是替代品。
默认不参与正常流程,**只在主路径失败时**被显式调用。

为什么需要它
------------
真机实测(CHI660E):
  * 主路径 ``ChiExecutor`` 用 **GUI Run** 触发测量 —— 能达到设定的 1e6 Hz
    (单频 Imp SF 模式,实测 84 点、top≈8.252e5 Hz)。
  * 但主路径的"另存为"是**多步图像模板匹配**,在某些瞬态 UI 下会点不中而失败,
    于是整条(约 10 分钟的)谱被丢弃 —— 这正是历史上 ``淀粉-1`` 丢点的根因。
  * 失败发生在"保存"这一步时,**谱图其实已经测完并在 CHI 内存里**。

本模块就是利用这一点:用 CHI 自带的 **Macro Command 对话框**跑一条
``folder / fileoverride / tsave``(**只存盘、不重新测量**)把内存里那条谱直接落盘。

为什么不直接用宏 ``run`` 重测
-----------------------------
真机实测:宏命令 ``run`` 在本 CHI 构建里会**无视单频(SF)/1e6 设置,强制套用
FT 阻抗的 1e5 上限**(每次都弹 "max freq for FT impedance is 100000 Hz" 并钳到 1e5)。
而 GUI Run 不会。所以宏只用来"存内存里已测好的数据"(tsave),绝不用宏来"测量"(run),
这样既鲁棒又**完整保留 GUI Run 已经测到的 1e6**。

为什么不用命令行 ``/runmacro``
------------------------------
真机实测:``chi660e.exe /runmacro:"...mcr"`` 在本机必崩(C++ Runtime abort),
故走 GUI 的 Macro Command 对话框(普通已运行实例),实测稳定。

依赖:pywinauto / pyautogui(均**惰性导入**;未安装时本模块只是优雅地不可用,
不会影响主路径或其它代码的导入)。返回契约与 ``ChiExecutor.execute_measurement`` 一致。
"""

from __future__ import annotations

import os
import glob
import time
from typing import Dict, Any, Optional

import numpy as np

DEFAULT_CHI_EXE = os.environ.get("CHI_EXE", r"D:\auto\CHI660E\chi660e\chi660e.exe")


class ChiMacroRescue:
    """通过 GUI Macro Command 对话框跑 ``tsave``,救回内存里已测好的谱(只存盘)。"""

    def __init__(self, config: Optional[dict] = None):
        self.config = {
            "chi_exe": DEFAULT_CHI_EXE,
            # Control 菜单中从顶部到 "Macro Command..." 的方向键次数(本 build 实测)
            "open_dialog_downs": 9,
            "open_dialog_retries": 3,
            "popup_poll_s": 2.0,
            "file_stable_checks": 2,
            "max_wait_s": 90.0,     # tsave 很快;给 90s 充裕兜底
            "min_points": 10,
            **(config or {}),
        }

    # ------------------------------------------------------------------
    # 主入口:救援存盘(只 tsave,不 run)
    # ------------------------------------------------------------------
    def rescue_save(
        self,
        chi_params: dict,
        output_dir: Optional[str] = None,
        current_temperature_C: Optional[float] = None,
    ) -> Dict[str, Any]:
        steps: Dict[str, Any] = {}
        for k in ["material", "highf", "lowf", "initV", "your_position"]:
            if k not in chi_params:
                return self._fail(f"Missing required CHI parameter: {k}", steps)

        save_dir = output_dir or chi_params["your_position"]
        try:
            os.makedirs(save_dir, exist_ok=True)
        except OSError as exc:
            return self._fail(f"Failed to create save directory: {exc}", steps)

        temp_str = f"{current_temperature_C:.1f}" if current_temperature_C is not None else "unknown"
        base = (f"{chi_params['material']}_T{temp_str}_f{chi_params['lowf']}"
                f"_{chi_params['highf']}_V{chi_params['initV']}")
        # CHI 的 tsave 会把文件名里第一个 '.' 之后当扩展名而截断,故去点(0.1->0p1)、去空格、去非法字符
        base = self._sanitize_macro_name(base)
        filename = base
        n = 1
        while self._existing_output(save_dir, filename) is not None:
            filename = f"{base}_rescue{n}"; n += 1

        try:
            from pywinauto.application import Application
            import pyautogui
            pyautogui.FAILSAFE = False
        except Exception as exc:  # noqa: BLE001
            return self._fail(f"pywinauto/pyautogui not available: {exc}", steps)

        # 救援必须连到正在运行、内存里已有谱图的实例(绝不启动新实例)
        try:
            app = Application(backend="win32").connect(title_re=".*CHI660E.*", timeout=5)
        except Exception as exc:  # noqa: BLE001
            return self._fail(f"CHI not running (rescue needs in-memory data): {exc}", steps)

        # 先清掉失败的图像自动化可能残留的模态框(半开的"另存为"等),回到主窗口
        self._cleanup_modal_dialogs(app, pyautogui, steps)

        if not self._open_macro_dialog(app, pyautogui, steps):
            return self._fail("failed to open Macro Command dialog (rescue)", steps)

        macro_text = "\r\n".join([f"folder: {save_dir}", "fileoverride", f"tsave: {filename}"]) + "\r\n"
        steps["render_macro"] = {"success": True, "macro": macro_text, "expected_basename": filename}
        try:
            mac_win = app.window(title="Macro Command")
            ed = mac_win.child_window(class_name="Edit")
            ed.set_edit_text(macro_text)
            time.sleep(0.3)
            self._remove_existing(save_dir, filename)
            t0 = time.time()
            mac_win.child_window(title="Run &Macro", class_name="Button").click()
            steps["run_macro"] = {"success": True, "tsave_only": True}
        except Exception as exc:  # noqa: BLE001
            return self._fail(f"failed to set/run tsave macro: {exc}", steps)

        out_file, werr = self._wait_with_popup_dismiss(app, save_dir, filename, t0)
        try:
            app.window(title="Macro Command").child_window(title="Cancel", class_name="Button").click()
        except Exception:
            pass
        if out_file is None:
            steps["wait_output"] = {"success": False, "error": werr}
            return self._fail(werr or "tsave output never appeared", steps)
        steps["wait_output"] = {"success": True, "output_file": out_file}

        freqs, zr, zi = self._parse_chi_data_file(out_file)
        if freqs is None or len(freqs) < self.config["min_points"]:
            return self._fail(f"rescue parse failed or too few points: {out_file}",
                              steps, output_file=out_file)
        return {"success": True, "frequencies": freqs, "z_real": zr, "z_imag": zi,
                "output_file": out_file, "n_points": len(freqs), "steps": steps,
                "error": None, "rescued": True}

    # ------------------------------------------------------------------
    # GUI 步骤
    # ------------------------------------------------------------------
    def _cleanup_modal_dialogs(self, app, pyautogui, steps) -> None:
        """关掉失败的图像自动化可能残留的模态框,回到主窗口。"""
        closed = []
        known = ("Save As", "另存为", "CH Instruments Electrochemical Software",
                 "Warning", "Macro Error", "Open", "打开")
        for _ in range(6):
            acted = False
            for w in app.windows():
                t = w.window_text()
                if t and t in known:
                    try:
                        w.set_focus()
                        try:
                            w.child_window(title="Cancel", class_name="Button").click()
                        except Exception:
                            try:
                                w.child_window(class_name="Button").click()
                            except Exception:
                                pyautogui.press("esc")
                        closed.append(t); acted = True
                    except Exception:
                        pass
            if not acted:
                break
            time.sleep(0.4)
        steps["cleanup_modal"] = {"closed": closed}

    def _open_macro_dialog(self, app, pyautogui, steps) -> bool:
        for attempt in range(self.config["open_dialog_retries"]):
            try:
                dlg = app.top_window(); dlg.restore(); dlg.set_focus()
                time.sleep(0.6)
                dlg.type_keys("%C")          # Alt+C 打开 Control 菜单
                time.sleep(0.6)
                for _ in range(self.config["open_dialog_downs"]):
                    pyautogui.press("down"); time.sleep(0.18)
                pyautogui.press("enter"); time.sleep(1.5)
                if app.window(title="Macro Command").exists():
                    steps["open_dialog"] = {"success": True, "attempt": attempt + 1}
                    return True
            except Exception:
                pass
            try:
                pyautogui.press("esc")
            except Exception:
                pass
            time.sleep(0.5)
        steps["open_dialog"] = {"success": False}
        return False

    def _wait_with_popup_dismiss(self, app, save_dir, filename, t0):
        stable_needed = self.config["file_stable_checks"]
        last_size = -1; stable = 0
        while time.time() - t0 < self.config["max_wait_s"]:
            for title in ("Warning", "CH Instruments Electrochemical Software", "Macro Error"):
                try:
                    w = app.window(title=title)
                    if w.exists():
                        w.set_focus()
                        try:
                            w.child_window(class_name="Button").click()
                        except Exception:
                            import pyautogui
                            pyautogui.press("enter")
                except Exception:
                    pass
            path = self._existing_output(save_dir, filename)
            if path is not None:
                try:
                    size = os.path.getsize(path)
                except OSError:
                    size = -1
                if size > 0 and size == last_size:
                    stable += 1
                    if stable >= stable_needed:
                        return path, None
                else:
                    stable = 0; last_size = size
            time.sleep(self.config["popup_poll_s"])
        return None, f"timeout after {self.config['max_wait_s']}s"

    # ------------------------------------------------------------------
    # 辅助(自包含:解析镜像 chi_executor._parse_chi_data_file)
    # ------------------------------------------------------------------
    @staticmethod
    def _existing_output(save_dir: str, basename: str) -> Optional[str]:
        cand = os.path.join(save_dir, basename + ".txt")
        if os.path.isfile(cand):
            return cand
        for p in sorted(glob.glob(os.path.join(save_dir, basename + ".*"))):
            if os.path.splitext(p)[1].lower() not in (".mcr", ".bin"):
                return p
        return None

    @staticmethod
    def _remove_existing(save_dir: str, basename: str) -> None:
        for p in glob.glob(os.path.join(save_dir, basename + ".*")):
            if os.path.splitext(p)[1].lower() not in (".mcr",):
                try:
                    os.remove(p)
                except OSError:
                    pass

    @staticmethod
    def _sanitize_macro_name(name: str) -> str:
        bad = '<>:"/\\|?*'
        name = "".join("_" if c in bad else c for c in name)
        return name.replace(".", "p").replace(" ", "_")

    @staticmethod
    def _fail(msg: str, steps: dict, output_file: Optional[str] = None) -> Dict[str, Any]:
        return {"success": False, "frequencies": None, "z_real": None, "z_imag": None,
                "output_file": output_file, "steps": steps, "error": msg}

    def _parse_chi_data_file(self, filepath: str):
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
            rows = [r for r in (self._try_parse_three_floats(l) for l in lines) if r is not None]
            if not rows:
                return None, None, None
            data = np.array(rows)
            return data[:, 0], data[:, 1], data[:, 2]
        except Exception:
            return None, None, None

    @staticmethod
    def _try_parse_three_floats(line: str):
        line = line.strip()
        if not line:
            return None
        skip = ("#", "//", "Frequency", "Date", "Init", "High", "Low",
                "Amplitude", "Quiet", "Cycles", "Instrument")
        if line.startswith(skip):
            return None
        for delim in (",", "\t", None):
            try:
                parts = line.split(delim) if delim else line.split()
                if len(parts) < 3:
                    continue
                return (float(parts[0]), float(parts[1]), float(parts[2]))
            except (ValueError, IndexError):
                continue
        return None
