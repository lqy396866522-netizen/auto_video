"""Dump Jianying UIA tree: every element with text + rectangle.

Usage:
  python -m jianying.inspect_ui           # dump current window
  python -m jianying.inspect_ui --filter 导入,开始创作

Run once on HOME page, once on EDITOR page, to learn reliable selectors.
"""
from __future__ import annotations

import argparse
import sys

from .window import find_main_window


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--filter", default="", help="逗号分隔关键词，只打印含这些文字的元素")
    args = parser.parse_args(argv)
    keywords = [k for k in args.filter.split(",") if k]

    win = find_main_window(timeout_sec=5)
    if win is None:
        print("未找到剪映窗口", file=sys.stderr)
        return 1

    r = win.rectangle()
    print(f"窗口: '{win.window_text()}'  rect=({r.left},{r.top})-({r.right},{r.bottom})  {r.width()}x{r.height()}")
    print("-" * 100)

    try:
        descendants = win.descendants()
    except Exception as exc:
        print(f"descendants() 失败: {exc}", file=sys.stderr)
        return 1

    count = 0
    for d in descendants:
        try:
            txt = (d.window_text() or "").strip()
            ct = d.element_info.control_type
        except Exception:
            continue
        if not txt:
            continue
        if keywords and not any(k in txt for k in keywords):
            continue
        try:
            dr = d.rectangle()
            cx = (dr.left + dr.right) // 2
            cy = (dr.top + dr.bottom) // 2
            # relative to window
            rx = (cx - r.left) / r.width() if r.width() else 0
            ry = (cy - r.top) / r.height() if r.height() else 0
            print(f"[{ct:12}] '{txt[:40]}'  center=({cx},{cy})  rel=({rx:.3f},{ry:.3f})  size={dr.width()}x{dr.height()}")
            count += 1
        except Exception:
            print(f"[{ct:12}] '{txt[:40]}'  (no rect)")
            count += 1

    print("-" * 100)
    print(f"共 {count} 个带文字元素")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
