"""Subtitle + TTS workflow — 剪映 11.x 纯坐标（UIA 树为空，已实测验证）.

流程（截图逐步验证）:
  字幕 tab → 新建字幕 → 手动写字幕 → 智能文案对话框
  → 粘贴 narration → 配音选择 → 收藏 → 活力科普 → 添加到轨道
  → 等待「自动拆句中…」「文本朗读中…」完成（字幕轨 + 配音轨生成）
"""
from __future__ import annotations

import time

import pyautogui
import pyperclip

from .config import env_int, env_str
from .debug_log import dbg
from .window import bring_to_front

pyautogui.FAILSAFE = False

# 已实测坐标（相对窗口 rx, ry），见 references/jianying-selectors.md
COORD_SUBTITLE_TAB = (0.169, 0.05)      # 顶部工具栏「字幕」
COORD_NEW_SUBTITLE = (0.0245, 0.246)    # 左侧子标签「新建字幕」
COORD_MANUAL_WRITE = (0.082, 0.10)      # 「手动写字幕」按钮
COORD_CONTENT_BOX = (0.576, 0.33)       # 智能文案右侧文本框
COORD_VOICE_SELECT = (0.660, 0.762)     # 「配音选择」按钮
COORD_FAV_TAB = (0.592, 0.308)          # 配音面板「收藏」标签
COORD_VOICE_ITEM = (0.609, 0.44)        # 收藏夹「活力科普」（第 2 行左列）
COORD_ADD_TO_TRACK = (0.543, 0.764)     # 「添加到轨道」按钮


def _click(win, coord: tuple[float, float], *, sleep: float = 1.2, desc: str = "") -> None:
    r = win.rectangle()
    x = r.left + int(r.width() * coord[0])
    y = r.top + int(r.height() * coord[1])
    pyautogui.click(x, y)
    time.sleep(sleep)
    dbg("subtitle_tts.py:_click", desc, {"x": x, "y": y, "coord": coord}, hypothesis_id="I")


def open_manual_subtitle(win) -> None:
    bring_to_front(win)
    _click(win, COORD_SUBTITLE_TAB, sleep=1.5, desc="字幕 tab")
    _click(win, COORD_NEW_SUBTITLE, sleep=1.2, desc="新建字幕")
    _click(win, COORD_MANUAL_WRITE, sleep=2.0, desc="手动写字幕")


def paste_narration(win, narration_script: str) -> None:
    _click(win, COORD_CONTENT_BOX, sleep=0.6, desc="文案输入框")
    pyperclip.copy(narration_script)
    time.sleep(0.3)
    pyautogui.hotkey("ctrl", "v")
    time.sleep(1.2)
    dbg("subtitle_tts.py:paste_narration", "pasted", {"len": len(narration_script)}, hypothesis_id="I")


def select_voice(win) -> None:
    voice_name = env_str("JIANYING_VOICE_NAME", "活力科普")
    _click(win, COORD_VOICE_SELECT, sleep=1.8, desc="配音选择")
    _click(win, COORD_FAV_TAB, sleep=1.5, desc="收藏 tab")
    # 活力科普固定在收藏夹第 2 行左列（用户已收藏）
    _click(win, COORD_VOICE_ITEM, sleep=1.2, desc=f"音色 {voice_name}")


def add_to_track(win) -> None:
    _click(win, COORD_ADD_TO_TRACK, sleep=3.0, desc="添加到轨道")


def wait_generation(win) -> None:
    """等待「自动拆句中…」+「文本朗读中…」完成。

    UIA 无法读弹窗文字，用截图像素法检测中央弹窗是否消失。
    弹窗固定出现在预览区下方中央（约 rx=0.5, ry=0.5 的小灰框）。
    """
    from PIL import ImageGrab

    timeout = env_int("JIANYING_SPLIT_SENTENCE_TIMEOUT_SEC", 300)
    r = win.rectangle()
    # 弹窗中心区域（"自动拆句中…/文本朗读中…" 灰框）
    cx = r.left + int(r.width() * 0.5)
    cy = r.top + int(r.height() * 0.5)
    box = (cx - 60, cy - 40, cx + 60, cy + 40)

    def popup_present() -> bool:
        img = ImageGrab.grab(bbox=box, all_screens=True).convert("L")
        px = list(img.getdata())
        avg = sum(px) / len(px)
        # 弹窗是浅灰框(较亮)，无弹窗时该区是深色时间轴/预览(较暗)
        return avg > 60

    deadline = time.time() + timeout
    # 先给生成一点启动时间
    time.sleep(3)
    seen_popup = False
    stable_empty = 0
    while time.time() < deadline:
        present = popup_present()
        dbg("subtitle_tts.py:wait_generation", "poll", {"present": present}, hypothesis_id="I")
        if present:
            seen_popup = True
            stable_empty = 0
        else:
            stable_empty += 1
            # 连续 3 次(~6s)无弹窗且此前见过弹窗 → 判定完成
            if seen_popup and stable_empty >= 3:
                dbg("subtitle_tts.py:wait_generation", "done", {}, hypothesis_id="I")
                return
            # 从未见弹窗但已稳定空 5 次 → 可能瞬时完成
            if not seen_popup and stable_empty >= 5:
                dbg("subtitle_tts.py:wait_generation", "done (no popup seen)", {}, hypothesis_id="I")
                return
        time.sleep(2)
    dbg("subtitle_tts.py:wait_generation", "timeout", {"timeout": timeout}, hypothesis_id="I")


def run_subtitle_tts(win, narration_script: str) -> None:
    open_manual_subtitle(win)
    paste_narration(win, narration_script)
    select_voice(win)
    add_to_track(win)
    wait_generation(win)
