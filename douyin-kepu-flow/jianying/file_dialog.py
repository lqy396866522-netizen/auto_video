"""Windows file-open dialog helpers for Jianying 「请选择媒体资源」."""
from __future__ import annotations

import logging
import time
from pathlib import Path

import pyperclip
from pywinauto import Desktop

from .debug_log import dbg

log = logging.getLogger(__name__)

DIALOG_TITLES = (
    "请选择媒体资源",
    "打开",
    "Open",
)

DIALOG_TITLE_RES = (
    r".*请选择媒体资源.*",
    r".*打开.*",
    r".*Open.*",
)


def find_import_dialog(timeout_sec: float = 60):
    """Return (dialog_wrapper, backend_name). Prefer win32 for #32770 dialogs."""
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        for backend in ("win32", "uia"):
            desktop = Desktop(backend=backend)
            for title in DIALOG_TITLES:
                dlg = _try_window(desktop, title=title, class_name="#32770")
                if dlg is not None:
                    dbg("file_dialog.py:find_import_dialog", "found", {"backend": backend, "title": title}, hypothesis_id="B")
                    return dlg, backend
            for title_re in DIALOG_TITLE_RES:
                dlg = _try_window(desktop, title_re=title_re, class_name="#32770")
                if dlg is not None:
                    dbg("file_dialog.py:find_import_dialog", "found", {"backend": backend, "title_re": title_re}, hypothesis_id="B")
                    return dlg, backend
                dlg = _try_window(desktop, title_re=title_re)
                if dlg is not None:
                    dbg("file_dialog.py:find_import_dialog", "found", {"backend": backend, "title_re": title_re, "no32770": True}, hypothesis_id="B")
                    return dlg, backend
        time.sleep(0.25)
    dbg("file_dialog.py:find_import_dialog", "dialog NOT found", {"timeout_sec": timeout_sec}, hypothesis_id="B")
    raise TimeoutError(f"未找到导入对话框「请选择媒体资源」（等待 {timeout_sec}s）")


def _try_window(desktop, **kwargs):
    try:
        dlg = desktop.window(**kwargs)
        if dlg.exists(timeout=0.2):
            try:
                dlg.set_focus()
            except Exception:
                pass
            return dlg
    except Exception:
        pass
    return None


def _filename_edit(dlg, backend: str):
    if backend == "win32":
        for spec in (
            {"auto_id": 1148, "class_name": "Edit"},
            {"class_name": "ComboBox", "found_index": 0},
            {"class_name": "ComboBoxEx32"},
            {"class_name": "Edit", "found_index": 0},
        ):
            try:
                ctrl = dlg.child_window(**spec)
                if ctrl.exists(timeout=0.2):
                    if ctrl.class_name() in ("ComboBox", "ComboBoxEx32"):
                        inner = ctrl.child_window(class_name="Edit")
                        if inner.exists(timeout=0.2):
                            return inner
                    return ctrl
            except Exception:
                continue
    for spec in (
        {"title_re": r"文件名.*", "control_type": "Edit"},
        {"title_re": r"文件名.*", "control_type": "ComboBox"},
        {"control_type": "Edit", "found_index": 0},
    ):
        try:
            ctrl = dlg.child_window(**spec)
            if ctrl.exists(timeout=0.2):
                return ctrl
        except Exception:
            continue
    raise RuntimeError("找不到文件名输入框（文件名(N)）")


def _click_open(dlg, backend: str) -> None:
    if backend == "win32":
        for auto_id in (1,):
            try:
                btn = dlg.child_window(auto_id=auto_id, class_name="Button")
                if btn.exists(timeout=0.2):
                    btn.click()
                    return
            except Exception:
                pass
        for title in ("打开(&O)", "打开(O)", "打开"):
            try:
                btn = dlg.child_window(title=title, class_name="Button")
                if btn.exists(timeout=0.2):
                    btn.click()
                    return
            except Exception:
                pass
    for label in ("打开(O)", "打开", "Open", "确定"):
        try:
            btn = dlg.child_window(title_re=f".*{label}.*", control_type="Button")
            if btn.exists(timeout=0.2):
                btn.click_input()
                return
        except Exception:
            continue
    dlg.type_keys("{ENTER}", pause=0.05, with_spaces=True)


def _paste_into_edit(edit, text: str) -> None:
    edit.set_focus()
    time.sleep(0.15)
    pyperclip.copy(text)
    try:
        edit.set_edit_text("")
    except Exception:
        pass
    try:
        edit.type_keys("^a", pause=0.03, with_spaces=True)
        edit.type_keys("^v", pause=0.03, with_spaces=True)
    except Exception:
        # Some ComboBoxEx32 wrappers only accept set_edit_text
        edit.set_edit_text(text)


def navigate_to_folder(dlg, folder: Path, backend: str) -> None:
    folder_str = str(folder.resolve())
    dbg("file_dialog.py:navigate_to_folder", "start", {"folder": folder_str, "backend": backend}, hypothesis_id="C")
    dlg.set_focus()
    time.sleep(0.2)

    # Alt+D → 地址栏（从「下载」等默认位置跳转到用户 VideoDir）
    try:
        dlg.type_keys("%d", pause=0.05, with_spaces=True)
        time.sleep(0.4)
        pyperclip.copy(folder_str)
        dlg.type_keys("^a", pause=0.03, with_spaces=True)
        dlg.type_keys("^v", pause=0.05, with_spaces=True)
        dlg.type_keys("{ENTER}", pause=0.05, with_spaces=True)
        time.sleep(1.2)
        dbg("file_dialog.py:navigate_to_folder", "done via Alt+D", {"folder": folder_str}, hypothesis_id="C")
        return
    except Exception as exc:
        log.debug("Alt+D navigate failed: %s", exc)

    # 文件名框输入目录路径 + Enter
    edit = _filename_edit(dlg, backend)
    _paste_into_edit(edit, folder_str)
    edit.type_keys("{ENTER}", pause=0.05, with_spaces=True)
    time.sleep(1.2)
    dbg("file_dialog.py:navigate_to_folder", "done via filename edit", {"folder": folder_str}, hypothesis_id="C")


def select_and_open_files(
    dlg,
    clips: list[Path],
    backend: str,
    *,
    one_by_one: bool = False,
) -> None:
    resolved = [c.resolve() for c in clips]
    folder = resolved[0].parent

    if one_by_one:
        for clip in resolved:
            dlg.set_focus()
            time.sleep(0.3)
            # 每次从用户指定目录导入，用完整路径（不依赖对话框当前所在位置）
            edit = _filename_edit(dlg, backend)
            _paste_into_edit(edit, str(clip))
            time.sleep(0.2)
            _click_open(dlg, backend)
            time.sleep(1.2)
        return

    # 1) 先跳转到用户指定的 VideoDir（对话框默认在「下载」不影响）
    navigate_to_folder(dlg, folder, backend)
    dlg.set_focus()
    time.sleep(0.4)

    # 2) 在该目录下按文件名多选
    quoted_names = " ".join(f'"{p.name}"' for p in resolved)
    dbg("file_dialog.py:select_and_open_files", "try basenames", {"folder": str(folder), "names": quoted_names[:200]}, hypothesis_id="D")
    try:
        edit = _filename_edit(dlg, backend)
        _paste_into_edit(edit, quoted_names)
        time.sleep(0.25)
        _click_open(dlg, backend)
        time.sleep(1.5)
        dbg("file_dialog.py:select_and_open_files", "success basenames", {"count": len(resolved)}, hypothesis_id="D")
        return
    except Exception as exc:
        log.debug("basename import failed: %s", exc)

    # 3) 若目录里只有这 10 个 mp4，Ctrl+A 全选
    mp4_count = len(list(folder.glob("*.mp4")))
    if mp4_count == len(resolved):
        dlg.set_focus()
        dlg.type_keys("^a", pause=0.05, with_spaces=True)
        time.sleep(0.3)
        _click_open(dlg, backend)
        time.sleep(1.5)
        dbg("file_dialog.py:select_and_open_files", "success basenames", {"count": len(resolved)}, hypothesis_id="D")
        return

    # 4) 兜底：文件名框粘贴带引号的完整路径（无需先导航）
    quoted_full = " ".join(f'"{p}"' for p in resolved)
    edit = _filename_edit(dlg, backend)
    _paste_into_edit(edit, quoted_full)
    time.sleep(0.25)
    _click_open(dlg, backend)
    time.sleep(1.5)


def import_files_in_dialog(clips: list[Path], *, one_by_one: bool = False, timeout_sec: float = 60) -> None:
    dlg, backend = find_import_dialog(timeout_sec)
    select_and_open_files(dlg, clips, backend, one_by_one=one_by_one)
