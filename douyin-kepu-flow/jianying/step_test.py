"""Step-by-step interactive test with screenshots between actions.

Usage:
  python -m jianying.step_test attach
  python -m jianying.step_test start_create
  python -m jianying.step_test import  --video-dir "E:\\path"
Each step re-attaches the window, performs ONE action, saves a screenshot
to test-data/shots/ so we can verify before the next step.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import pyautogui
from PIL import ImageGrab

pyautogui.FAILSAFE = False

from .window import find_main_window, click_coord, bring_to_front

SHOT_DIR = Path(__file__).resolve().parents[2] / "test-data" / "shots"


def _shot(name: str, win=None) -> Path:
    """Capture using all_screens=True so secondary monitors aren't black."""
    SHOT_DIR.mkdir(parents=True, exist_ok=True)
    out = SHOT_DIR / f"{name}.png"
    if win is not None:
        r = win.rectangle()
        bbox = (r.left, r.top, r.right, r.bottom)
        img = ImageGrab.grab(bbox=bbox, all_screens=True)
    else:
        img = ImageGrab.grab(all_screens=True)
    img.save(str(out))
    print(f"SHOT -> {out}  bbox={win.rectangle() if win else 'full'}")
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("step", choices=["attach", "start_create", "import", "timeline", "shot"])
    parser.add_argument("--video-dir", default="")
    args = parser.parse_args(argv)

    win = find_main_window(timeout_sec=8)
    if win is None:
        print("未找到剪映窗口", file=sys.stderr)
        return 1
    r = win.rectangle()
    print(f"窗口 rect=({r.left},{r.top})-({r.right},{r.bottom}) {r.width()}x{r.height()}")
    try:
        win.set_focus()
    except Exception:
        pass
    time.sleep(0.8)

    if args.step == "attach" or args.step == "shot":
        bring_to_front(win)
        win = find_main_window(timeout_sec=5) or win
        _shot(f"{args.step}", win)
        return 0

    if args.step == "start_create":
        _shot("before_start_create", win)
        # verify cursor actually lands where we intend
        tx = r.left + int(r.width() * 0.586)
        ty = r.top + int(r.height() * 0.155)
        pyautogui.moveTo(tx, ty)
        time.sleep(0.3)
        print(f"target=({tx},{ty}) cursor_now={pyautogui.position()}")
        click_coord(win, 0.586, 0.155, desc="开始创作", sleep=3.0)
        # window may have changed size/handle after entering editor
        win2 = find_main_window(timeout_sec=8) or win
        _shot("after_start_create", win2)
        return 0

    if args.step == "import":
        bring_to_front(win)
        win = find_main_window(timeout_sec=5) or win
        _shot("before_import", win)
        click_coord(win, 0.19, 0.15, desc="导入按钮", sleep=2.5)
        # file dialog is a separate top-level window; capture full desktop
        _shot("after_import_full")
        return 0

    if args.step == "timeline":
        from .import_clips import add_clips_to_timeline

        _shot("before_timeline", win)
        add_clips_to_timeline(win, count=10)
        win2 = find_main_window(timeout_sec=5) or win
        _shot("after_timeline", win2)
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
