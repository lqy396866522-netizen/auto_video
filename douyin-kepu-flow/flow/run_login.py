"""Google Flow 首次登录 — 打开持久化浏览器供用户手动登录。"""
from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

from .common import (
    DEFAULT_CDP_PORT,
    DEFAULT_FLOW_URL,
    connect_browser,
    ensure_browser,
    env_int,
    env_str,
    get_work_page,
    load_dotenv_if_present,
    resolve_browser_profile,
)
from .navigate import is_logged_in, open_flow, wait_for_manual_login


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def main() -> int:
    root = project_root()
    load_dotenv_if_present(root)

    flow_url = env_str("FLOW_URL", DEFAULT_FLOW_URL)
    cdp_port = env_int("FLOW_CDP_PORT", DEFAULT_CDP_PORT)
    profile = resolve_browser_profile()

    print(f"Profile: {profile}")
    print(f"CDP 端口: {cdp_port}")
    ensure_browser(cdp_port, profile)

    with sync_playwright() as pw:
        browser = connect_browser(pw, cdp_port)
        context = browser.contexts[0] if browser.contexts else browser.new_context()
        page = get_work_page(context, flow_url)
        open_flow(page, flow_url)

        if is_logged_in(page):
            print("已检测到登录状态。浏览器保持打开，可直接运行 run_batch.ps1。")
        else:
            wait_for_manual_login(page, flow_url)
            print("登录完成。浏览器保持打开。")

        print("按 Ctrl+C 退出（浏览器进程可继续复用）。")
        try:
            page.wait_for_timeout(86400000)
        except KeyboardInterrupt:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
