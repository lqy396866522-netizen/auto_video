"""Google Flow — 导航与生成操作。"""
from __future__ import annotations

import re
import time

from playwright.sync_api import Page

from .common import (
    clear_prompt_editor,
    click_create_submit,
    fill_prompt_text,
    get_create_submit_button,
    is_visible,
)


def is_logged_in(page: Page) -> bool:
    """固定项目页模式：默认可用；仅 Google 登录页视为未登录。"""
    if "accounts.google.com" in page.url:
        return False
    return True


def wait_for_manual_login(page: Page, flow_url: str, *, timeout_sec: int = 600) -> None:
    page.goto(flow_url, wait_until="domcontentloaded", timeout=60000)
    print("请在浏览器中完成 Google 登录…")
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        if is_logged_in(page):
            print("登录检测通过。")
            return
        time.sleep(2)
    raise TimeoutError("等待 Google Flow 登录超时")


def open_flow(page: Page, flow_url: str) -> None:
    page.goto(flow_url, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(2000)


def submit_prompt(page: Page, prompt_text: str) -> None:
    """写入 prompt → 等待「创建」可点 → 点击提交（使用页面默认模型/参数）。"""
    fill_prompt_text(page, prompt_text)
    click_create_submit(page)
    page.wait_for_timeout(800)


def prepare_next_segment(page: Page) -> None:
    """清除输入框，准备写入下一段 prompt。"""
    clear_prompt_editor(page)
    page.wait_for_timeout(500)


def is_generation_in_progress(page: Page) -> bool:
    btn = get_create_submit_button(page)
    try:
        if btn.get_attribute("aria-disabled") in ("true", "True"):
            if is_visible(page.get_by_text(re.compile(r"Generating|生成中|Creating|请稍候", re.I)), 500):
                return True
    except Exception:
        pass
    if is_visible(page.locator("[role=progressbar]"), 500):
        return True
    if is_visible(page.get_by_text(re.compile(r"Generating|生成中|Creating|请稍候", re.I)), 500):
        return True
    return False


def wait_for_generation_complete(page: Page, *, timeout_sec: int = 300) -> None:
    deadline = time.monotonic() + timeout_sec
    saw_progress = False
    while time.monotonic() < deadline:
        if is_generation_in_progress(page):
            saw_progress = True
        else:
            if saw_progress or is_download_ready(page) or is_video_ready(page):
                page.wait_for_timeout(1500)
                if not is_generation_in_progress(page):
                    return
        time.sleep(1.5)
    raise TimeoutError(f"视频生成超时（{timeout_sec}s）")


def is_download_ready(page: Page) -> bool:
    loc = page.get_by_role("button", name=re.compile(r"下载|Download", re.I))
    if is_visible(loc, 800):
        return True
    loc = page.get_by_role("link", name=re.compile(r"下载|Download", re.I))
    return is_visible(loc, 800)


def is_video_ready(page: Page) -> bool:
    video = page.locator("video").first
    if not is_visible(video, 800):
        return False
    try:
        ready = video.evaluate(
            "el => el.readyState >= 2 && (el.currentSrc || el.src || '').length > 0"
        )
        return bool(ready)
    except Exception:
        return False
