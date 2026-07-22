"""Wait helpers for Jianying UI automation."""
from __future__ import annotations

import time
from typing import Any, Callable


def wait_until(
    predicate: Callable[[], bool],
    timeout_sec: float,
    interval_sec: float = 0.5,
    desc: str = "",
) -> bool:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(interval_sec)
    raise TimeoutError(f"等待超时 ({timeout_sec}s): {desc}")


def wait_gone(
    predicate: Callable[[], bool],
    timeout_sec: float,
    interval_sec: float = 0.5,
    desc: str = "",
) -> None:
    """Wait until predicate returns False (element/text disappeared)."""
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        if not predicate():
            return
        time.sleep(interval_sec)
    raise TimeoutError(f"等待消失超时 ({timeout_sec}s): {desc}")


def safe_window_text(ctrl: Any) -> str:
    try:
        return (ctrl.window_text() or "").strip()
    except Exception:
        return ""


def descendant_texts(root: Any) -> list[str]:
    texts: list[str] = []
    try:
        for d in root.descendants():
            t = safe_window_text(d)
            if t:
                texts.append(t)
    except Exception:
        pass
    return texts


def any_text_contains(root: Any, needle: str) -> bool:
    return any(needle in t for t in descendant_texts(root))
