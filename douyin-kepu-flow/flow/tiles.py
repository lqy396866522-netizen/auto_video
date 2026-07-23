"""Google Flow — 项目页视频 tile 网格解析。"""
from __future__ import annotations

import re
import time
from enum import Enum

from playwright.sync_api import Locator, Page

from .common import is_visible


class TileState(str, Enum):
    GENERATING = "generating"
    COMPLETE = "complete"
    FAILED = "failed"
    UNKNOWN = "unknown"


def sanitize_topic_dirname(topic: str) -> str:
    invalid = '<>:"/\\|?*'
    result = topic.strip()
    for ch in invalid:
        result = result.replace(ch, "_")
    return result.rstrip(". ") or "untitled"


def format_segment_filename(index: int, max_index: int) -> str:
    width = 3 if max_index > 99 else 2
    return f"{index:0{width}d}.mp4"


def snapshot_tile_ids(page: Page) -> set[str]:
    ids: set[str] = set()
    for el in page.locator("[data-tile-id]").all():
        tid = el.get_attribute("data-tile-id")
        if tid:
            ids.add(tid)
    return ids


def ordered_tile_ids(page: Page) -> list[str]:
    """DOM 顺序（最新在前），去重 data-tile-id。"""
    ordered: list[str] = []
    seen: set[str] = set()
    for el in page.locator("[data-tile-id]").all():
        tid = el.get_attribute("data-tile-id")
        if tid and tid not in seen:
            seen.add(tid)
            ordered.append(tid)
    return ordered


def get_tile_locator(page: Page, tile_id: str) -> Locator:
    return page.locator(f'[data-tile-id="{tile_id}"]').first


def get_tile_state(tile: Locator) -> TileState:
    resolved = TileState.UNKNOWN
    page = tile.page
    try:
        tile.scroll_into_view_if_needed(timeout=3000)
        tile.hover(timeout=2000)
        page.wait_for_timeout(400)
    except Exception:
        pass
    try:
        has_pct = False
        pct = tile.locator(".sc-40f16b33-7")
        if pct.count() > 0:
            try:
                text = pct.first.inner_text(timeout=500)
                has_pct = bool(re.search(r"\d+\s*%", text))
            except Exception:
                has_pct = is_visible(
                    tile.locator(".sc-40f16b33-7").filter(has_text=re.compile(r"\d+\s*%")), 400
                )

        if has_pct:
            resolved = TileState.GENERATING
        elif tile.locator("video").count() > 0:
            src = tile.locator("video").first.evaluate(
                "el => el.currentSrc || el.getAttribute('src') || ''"
            )
            src = str(src or "")
            if src and ("getMediaUrlRedirect" in src or src.startswith("http")):
                resolved = TileState.COMPLETE
        elif is_visible(tile.locator(".sc-784d6f75-0.cFXNwK"), 400):
            if not is_visible(tile.locator("video[src]"), 400):
                resolved = TileState.GENERATING
        elif is_visible(tile.locator(".sc-101009f9-0.llonRc"), 400):
            if is_visible(tile.locator(".sc-101009f9-1").filter(has_text="失败"), 400):
                resolved = TileState.FAILED
        elif is_visible(tile.get_by_text("失败", exact=True), 400):
            if not has_pct and tile.locator("video[src]").count() == 0:
                resolved = TileState.FAILED
    except Exception:
        pass
    return resolved


def is_terminal_state(state: TileState) -> bool:
    return state in (TileState.COMPLETE, TileState.FAILED)


def wait_for_new_tile(page: Page, known_ids: set[str], *, timeout_sec: float = 90) -> str:
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        for tid in ordered_tile_ids(page):
            if tid not in known_ids:
                return tid
        page.wait_for_timeout(500)
    raise TimeoutError(f"等待新 tile 超时（{timeout_sec}s）")


def segment_is_done(
    *,
    has_tile: bool,
    state: TileState | None,
    downloaded: bool,
) -> bool:
    if not has_tile:
        return True
    if state == TileState.FAILED:
        return True
    if state == TileState.COMPLETE and downloaded:
        return True
    return False
