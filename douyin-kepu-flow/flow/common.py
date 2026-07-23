"""Google Flow — 公共浏览器工具。"""
from __future__ import annotations

import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright

DEFAULT_FLOW_URL = (
    "https://labs.google/fx/zh/tools/flow/project/147a46cc-6217-4b1f-a162-e5bcfcd96b9b"
)
DEFAULT_CDP_PORT = 9335
DEFAULT_BROWSER_PROFILE = Path.home() / ".hermes" / "flow-browser"
DEFAULT_PROFILE = DEFAULT_BROWSER_PROFILE  # backward compat
DEFAULT_DOWNLOAD_DIR_TEMPLATE = r"D:\douyin-videos\{topic}"
FLOW_PROMPT_PLACEHOLDER = "您希望创作什么内容？"


def resolve_browser_profile() -> Path:
    """浏览器登录态目录；未配置时使用当前用户 ~/.hermes/flow-browser。"""
    raw = os.getenv("FLOW_BROWSER_PROFILE", "").strip()
    if raw:
        return Path(expand_env(raw))
    return DEFAULT_BROWSER_PROFILE


def expand_env(value: str) -> str:
    return os.path.expandvars(os.path.expanduser(value))


def env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if not raw:
        return default
    return int(raw)


def env_str(name: str, default: str) -> str:
    return expand_env(os.getenv(name, default))


def is_port_open(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.3)
        return sock.connect_ex((host, port)) == 0


def find_chromium_executable() -> Optional[str]:
    pw_root = Path(os.getenv("LOCALAPPDATA", "")) / "ms-playwright"
    if pw_root.exists():
        for p in sorted(pw_root.glob("chromium-*/chrome-win/chrome.exe")):
            return str(p)
        for p in sorted(pw_root.glob("chromium-*/chrome-win64/chrome.exe")):
            return str(p)
    return None


def launch_persistent_chromium(profile_dir: Path, cdp_port: int) -> subprocess.Popen:
    profile_dir.mkdir(parents=True, exist_ok=True)
    exe = find_chromium_executable()
    if not exe:
        raise RuntimeError(
            "未找到 Playwright Chromium。请先运行: pip install playwright && playwright install chromium"
        )
    args = [
        exe,
        f"--remote-debugging-port={cdp_port}",
        f"--user-data-dir={profile_dir}",
        "--no-first-run",
        "--no-default-browser-check",
        "about:blank",
    ]
    return subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def ensure_browser(cdp_port: int, profile_dir: Path) -> None:
    if is_port_open(cdp_port):
        return
    proc = launch_persistent_chromium(profile_dir, cdp_port)
    for _ in range(40):
        if is_port_open(cdp_port):
            return
        if proc.poll() is not None:
            raise RuntimeError("Chromium 启动失败")
        time.sleep(0.25)
    raise RuntimeError(f"等待 CDP 端口 {cdp_port} 超时")


def connect_browser(playwright: Playwright, cdp_port: int) -> Browser:
    return playwright.chromium.connect_over_cdp(f"http://127.0.0.1:{cdp_port}")


def get_work_page(context: BrowserContext, url: str) -> Page:
    for page in context.pages:
        if "labs.google" in page.url or "google.com" in page.url:
            page.bring_to_front()
            return page
    page = context.new_page()
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    return page


def is_visible(locator, timeout_ms: int = 1500) -> bool:
    try:
        locator.wait_for(state="visible", timeout=timeout_ms)
        return True
    except Exception:
        return False


def click_first_matching(page: Page, patterns: list[str], *, timeout_ms: int = 8000) -> bool:
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        for pattern in patterns:
            loc = page.get_by_role("button", name=re.compile(pattern, re.I))
            if is_visible(loc, 800):
                loc.click()
                return True
            loc = page.get_by_text(re.compile(pattern, re.I)).first
            if is_visible(loc, 800):
                loc.click()
                return True
        time.sleep(0.3)
    return False


def get_prompt_editor(page: Page):
    """通过 placeholder 文案定位 Slate 编辑器。"""
    placeholder = page.get_by_text(FLOW_PROMPT_PLACEHOLDER, exact=True)
    if is_visible(placeholder, 2000):
        editor = placeholder.locator(
            'xpath=ancestor::div[@role="textbox"][@contenteditable="true"]'
        )
        if is_visible(editor, 1500):
            return editor

    candidates = [
        page.locator('div[role="textbox"][contenteditable="true"][data-slate-editor="true"]'),
        page.locator('div[role="textbox"][contenteditable="true"]'),
        page.locator("[data-slate-editor=true]").first,
    ]
    for loc in candidates:
        if is_visible(loc, 2000):
            return loc
    raise RuntimeError(f'未找到 prompt 输入框（placeholder: "{FLOW_PROMPT_PLACEHOLDER}"）')


def get_create_submit_button(page: Page):
    """提交 prompt 的 arrow_forward「创建」按钮（非 add_2 菜单按钮）。"""
    btn = page.locator("button").filter(has=page.locator("i.google-symbols", has_text="arrow_forward"))
    if btn.count() > 0:
        return btn.last
    btn = page.locator("button.sc-26b30722-5")
    if btn.count() > 0:
        return btn.first
    return page.get_by_role("button", name="创建").last


def _read_editor_plaintext(editor) -> str:
    try:
        return (
            editor.evaluate(
                """el => {
                    const walk = n => {
                        if (!n) return '';
                        if (n.nodeType === Node.TEXT_NODE) return n.textContent || '';
                        return Array.from(n.childNodes).map(walk).join('');
                    };
                    return (el.innerText || walk(el) || '').trim();
                }"""
            )
            or ""
        ).strip()
    except Exception:
        return (editor.inner_text() or "").strip()


def clear_prompt_editor(page: Page) -> None:
    """清空 Slate 编辑器（Backspace 对 Slate 不可靠，用 Delete + execCommand 兜底）。"""
    editor = get_prompt_editor(page)
    editor.click()
    page.wait_for_timeout(150)
    for _ in range(3):
        page.keyboard.press("Control+A")
        page.wait_for_timeout(80)
        page.keyboard.press("Delete")
        page.wait_for_timeout(150)
        if len(_read_editor_plaintext(editor)) < 15:
            return
    editor.evaluate(
        """el => {
            el.focus();
            const sel = window.getSelection();
            const range = document.createRange();
            range.selectNodeContents(el);
            sel.removeAllRanges();
            sel.addRange(range);
            document.execCommand('delete');
        }"""
    )
    page.wait_for_timeout(200)
    if len(_read_editor_plaintext(editor)) >= 15:
        editor.evaluate(
            """el => {
                el.focus();
                while (el.firstChild) el.removeChild(el.firstChild);
                el.textContent = '';
                el.dispatchEvent(new InputEvent('input', { bubbles: true, inputType: 'deleteContentBackward' }));
            }"""
        )
        page.wait_for_timeout(200)


def fill_prompt_text(page: Page, text: str) -> None:
    clear_prompt_editor(page)
    if not text:
        return
    editor = get_prompt_editor(page)
    editor.click()
    page.wait_for_timeout(100)
    page.keyboard.insert_text(text)
    page.wait_for_timeout(300)


def wait_create_button_enabled(page: Page, *, timeout_ms: int | None = None) -> None:
    if timeout_ms is None:
        timeout_ms = env_int("FLOW_CREATE_BUTTON_TIMEOUT_SEC", 120) * 1000
    btn = get_create_submit_button(page)
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        disabled = btn.get_attribute("aria-disabled")
        if disabled not in ("true", "True"):
            return
        page.wait_for_timeout(200)
    raise TimeoutError("「创建」按钮未变为可点击（aria-disabled 仍为 true）")


def click_create_submit(page: Page, *, timeout_ms: int | None = None) -> None:
    wait_create_button_enabled(page, timeout_ms=timeout_ms)
    get_create_submit_button(page).click()


def load_dotenv_if_present(root: Path) -> None:
    env_file = root / ".env"
    if not env_file.exists():
        return
    try:
        from dotenv import load_dotenv

        load_dotenv(env_file)
    except ImportError:
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            os.environ.setdefault(key.strip(), expand_env(val.strip()))
