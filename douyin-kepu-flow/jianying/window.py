"""Launch or attach to Jianying Pro main window."""
from __future__ import annotations

import subprocess
import time
from pathlib import Path

from pywinauto import Application, Desktop
from pywinauto.findwindows import ElementNotFoundError

from .config import default_jianying_exe, env_int, env_str
from .debug_log import dbg


def _desktop():
    return Desktop(backend="uia")


def find_main_window(timeout_sec: float = 5):
    desktop = _desktop()
    patterns = [
        ".*剪映.*",
        ".*JianyingPro.*",
        ".*CapCut.*",
    ]
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        for pat in patterns:
            try:
                win = desktop.window(title_re=pat, visible_only=True)
                if win.exists(timeout=0.5):
                    return win
            except ElementNotFoundError:
                continue
        time.sleep(0.5)
    return None


def launch_jianying(exe_path: Path | None = None) -> None:
    exe = exe_path or Path(env_str("JIANYING_EXE", str(default_jianying_exe())))
    if not exe.is_file():
        raise FileNotFoundError(
            f"找不到剪映可执行文件: {exe}\n"
            f"请在 .env 设置 JIANYING_EXE"
        )
    subprocess.Popen([str(exe)], shell=False)
    startup_timeout = env_int("JIANYING_STARTUP_TIMEOUT_SEC", 30)
    deadline = time.time() + startup_timeout
    while time.time() < deadline:
        if find_main_window(timeout_sec=1):
            return
        time.sleep(1)
    raise TimeoutError(f"剪映启动超时 ({startup_timeout}s)")


def attach_or_launch(exe_path: Path | None = None):
    win = find_main_window(timeout_sec=3)
    if win is None:
        launch_jianying(exe_path)
        win = find_main_window(timeout_sec=5)
    if win is None:
        raise RuntimeError("无法附着剪映主窗口")
    dbg("window.py:attach_or_launch", "attached", {"title": win.window_text()}, hypothesis_id="A")
    try:
        win.set_focus()
    except Exception:
        pass
    time.sleep(0.8)
    return win


def bring_to_front(win) -> None:
    """Robustly raise the Jianying window above others (e.g. WeChat overlay)."""
    import ctypes

    try:
        if win.is_minimized():
            win.restore()
    except Exception:
        pass
    try:
        win.set_focus()
    except Exception:
        pass
    # Fallback: Win32 SetForegroundWindow + ShowWindow(SW_SHOW)
    try:
        hwnd = win.handle
        user32 = ctypes.windll.user32
        user32.ShowWindow(hwnd, 5)  # SW_SHOW
        # AttachThreadInput trick to bypass foreground lock
        fg = user32.GetForegroundWindow()
        cur_tid = user32.GetWindowThreadProcessId(fg, None)
        tgt_tid = user32.GetWindowThreadProcessId(hwnd, None)
        kernel32 = ctypes.windll.kernel32
        this_tid = kernel32.GetCurrentThreadId()
        user32.AttachThreadInput(this_tid, cur_tid, True)
        user32.AttachThreadInput(this_tid, tgt_tid, True)
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
        user32.AttachThreadInput(this_tid, cur_tid, False)
        user32.AttachThreadInput(this_tid, tgt_tid, False)
    except Exception as exc:
        dbg("window.py:bring_to_front", "win32 fallback failed", {"err": str(exc)}, hypothesis_id="G")
    time.sleep(0.6)
    dbg("window.py:bring_to_front", "done", {"title": win.window_text()}, hypothesis_id="G")


def click_by_names(win, names: list[str], control_types: list[str] | None = None) -> bool:
    """Try clicking first matching descendant by window_text."""
    ctypes = control_types or ["Button", "Text", "Hyperlink", "MenuItem", "ListItem"]
    for name in names:
        for ct in ctypes:
            try:
                ctrl = win.child_window(title=name, control_type=ct)
                if ctrl.exists(timeout=0.3):
                    ctrl.click_input()
                    return True
            except Exception:
                continue
        # partial match
        try:
            for d in win.descendants(control_type="Button"):
                txt = (d.window_text() or "")
                if name in txt:
                    d.click_input()
                    return True
        except Exception:
            pass
    return False


def find_element_rect_by_names(win, names: list[str]):
    """Search ALL descendants (any control type) for a name match.

    Returns (cx, cy) center of the first visible match, else None.
    QML/Electron windows expose text on Text/Group/Custom/Image nodes,
    so we don't restrict by control type.
    """
    try:
        descendants = win.descendants()
    except Exception:
        return None
    for name in names:
        for d in descendants:
            try:
                txt = (d.window_text() or "").strip()
            except Exception:
                continue
            if not txt or name not in txt:
                continue
            try:
                r = d.rectangle()
                if r.width() <= 0 or r.height() <= 0:
                    continue
                cx = (r.left + r.right) // 2
                cy = (r.top + r.bottom) // 2
                return cx, cy
            except Exception:
                continue
    return None


# 剪映 11.x 是纯 QML 渲染，UIA 树为空，名称匹配无效——统一走坐标。
# 一旦检测到窗口无 UIA 子元素，缓存标记，后续跳过昂贵的 descendants() 调用。
_UIA_EMPTY: bool | None = None


def _uia_is_empty(win) -> bool:
    global _UIA_EMPTY
    if _UIA_EMPTY is not None:
        return _UIA_EMPTY
    try:
        _UIA_EMPTY = len(win.descendants()) == 0
    except Exception:
        _UIA_EMPTY = True
    return _UIA_EMPTY


def click_coord(win, rx: float, ry: float, *, desc: str = "", sleep: float = 1.0) -> None:
    """Click at a window-relative coordinate (handles multi-monitor offset)."""
    import pyautogui

    r = win.rectangle()
    x = r.left + int(r.width() * rx)
    y = r.top + int(r.height() * ry)
    try:
        win.set_focus()
    except Exception:
        pass
    time.sleep(0.15)
    pyautogui.click(x, y)
    time.sleep(sleep)
    dbg(
        "window.py:click_coord",
        f"click {desc}",
        {"x": x, "y": y, "rx": rx, "ry": ry, "win": f"{r.width()}x{r.height()}", "origin": f"{r.left},{r.top}"},
        hypothesis_id="F",
    )


def click_names_or_coord(win, names: list[str], rx: float, ry: float, *, desc: str = "", sleep: float = 1.0) -> str:
    """Click by UIA name (rect center) if available, else relative coordinate."""
    if not _uia_is_empty(win):
        hit = find_element_rect_by_names(win, names)
        if hit is not None:
            import pyautogui

            cx, cy = hit
            pyautogui.click(cx, cy)
            time.sleep(sleep)
            dbg("window.py:click_names_or_coord", f"clicked by NAME {desc}", {"x": cx, "y": cy}, hypothesis_id="F")
            return "name"

    click_coord(win, rx, ry, desc=desc, sleep=sleep)
    return "coord"
