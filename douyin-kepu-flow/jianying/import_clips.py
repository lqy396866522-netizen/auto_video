"""Import mp4 clips and add them to timeline."""
from __future__ import annotations

import logging
import time
from pathlib import Path

from .config import env_int
from .debug_log import dbg
from .file_dialog import find_import_dialog, import_files_in_dialog, select_and_open_files
from .window import bring_to_front, click_by_names, click_coord, click_names_or_coord

log = logging.getLogger(__name__)

try:
    import pyautogui

    pyautogui.FAILSAFE = False
    _HAS_PYAUTOGUI = True
except ImportError:
    _HAS_PYAUTOGUI = False


def click_start_create(win) -> None:
    # 剪映 11.x QML 无 UIA 元素，坐标点击。首页顶部横幅「开始创作」中心 ~rx=0.586, ry=0.155
    bring_to_front(win)
    click_coord(win, 0.586, 0.155, desc="开始创作", sleep=3.0)
    dbg("import_clips.py:click_start_create", "done", {}, hypothesis_id="A")


def import_clips(win, clips: list[Path], one_by_one: bool = False) -> None:
    # 编辑页左侧素材面板「导入」拖拽区中心 ~rx=0.19, ry=0.15
    # 必须先置顶，避免微信等窗口遮挡（已验证）
    bring_to_front(win)
    click_coord(win, 0.19, 0.15, desc="导入按钮", sleep=2.0)
    dbg("import_clips.py:import_clips", "clicked import", {}, hypothesis_id="A")

    timeout = env_int("JIANYING_IMPORT_TIMEOUT_SEC", 60)
    time.sleep(0.8)

    try:
        import_files_in_dialog(clips, one_by_one=one_by_one, timeout_sec=timeout)
    except Exception as first_err:
        log.warning("primary import failed: %s", first_err)
        # Retry: dialog may already be open
        try:
            dlg, backend = find_import_dialog(timeout_sec=5)
            select_and_open_files(dlg, clips, backend, one_by_one=one_by_one)
        except Exception as second_err:
            raise RuntimeError(
                f"导入文件失败: {first_err}; retry: {second_err}\n"
                f"目录: {clips[0].parent}\n"
                f"文件: {', '.join(c.name for c in clips[:3])}..."
            ) from second_err

    time.sleep(2.0)


def add_clips_to_timeline(win, count: int = 10) -> None:
    """全选素材面板所有片段，拖拽到底部时间轴轨道。

    剪映 11.x QML 无 UIA 元素，坐标操作。素材缩略图 3 列网格，
    首格中心 ~rx=0.092, ry=0.171；时间轴放置区在窗口下半部。
    """
    bring_to_front(win)
    time.sleep(1.0)

    r = win.rectangle()

    def abs_xy(rx: float, ry: float) -> tuple[int, int]:
        return r.left + int(r.width() * rx), r.top + int(r.height() * ry)

    # 1) 点第一个缩略图并全选
    fx, fy = abs_xy(0.092, 0.171)
    pyautogui.click(fx, fy)
    time.sleep(0.4)
    pyautogui.hotkey("ctrl", "a")
    time.sleep(0.5)
    dbg("import_clips.py:add_clips_to_timeline", "selected all", {"first": [fx, fy]}, hypothesis_id="H")

    # 2) 拖拽到时间轴（窗口下半部空轨道区）
    tx, ty = abs_xy(0.35, 0.72)
    pyautogui.moveTo(fx, fy)
    time.sleep(0.2)
    pyautogui.mouseDown()
    # 分段移动，避免剪映丢拖拽
    pyautogui.moveTo((fx + tx) // 2, (fy + ty) // 2, duration=0.4)
    pyautogui.moveTo(tx, ty, duration=0.5)
    time.sleep(0.3)
    pyautogui.mouseUp()
    time.sleep(2.0)
    dbg("import_clips.py:add_clips_to_timeline", "dragged to timeline", {"target": [tx, ty]}, hypothesis_id="H")


def _jr(win) -> tuple[int, int, int, int]:
    r = win.rectangle()
    return r.left, r.top, r.width(), r.height()


def _click_at(win, rx: float, ry: float, *, sleep: float = 1.0) -> None:
    left, top, w, h = _jr(win)
    pyautogui.click(left + int(w * rx), top + int(h * ry))
    time.sleep(sleep)


def _hotkey(win, *keys) -> None:
    try:
        win.set_focus()
    except Exception:
        pass
    time.sleep(0.2)
    pyautogui.hotkey(*keys)
