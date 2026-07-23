"""Google Flow — 下载与报告。"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from playwright.sync_api import Locator, Page

from .common import click_first_matching, is_visible
from .navigate import is_video_ready


@dataclass
class SegmentResult:
    index: int
    status: str
    file: str | None = None
    error: str | None = None
    attempts: int = 1
    tile_id: str | None = None


@dataclass
class BatchReport:
    topic: str
    slug: str
    download_dir: str
    segment_count: int = 0
    started_at: str = ""
    finished_at: str | None = None
    segments: list[SegmentResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "topic": self.topic,
            "slug": self.slug,
            "download_dir": self.download_dir,
            "segment_count": self.segment_count,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "segments": [asdict(s) for s in self.segments],
            "success_count": sum(1 for s in self.segments if s.status == "success"),
            "failed_count": sum(1 for s in self.segments if s.status != "success"),
        }


def download_latest_video(page: Page, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)

    with page.expect_download(timeout=120000) as dl_info:
        clicked = click_first_matching(
            page,
            [r"下载", r"Download", r"Export"],
            timeout_ms=15000,
        )
        if not clicked:
            raise RuntimeError("未找到下载按钮")
    download = dl_info.value
    suggested = download.suggested_filename or dest.name
    if not dest.suffix and "." in suggested:
        dest = dest.with_suffix(Path(suggested).suffix or ".mp4")
    download.save_as(dest)


def download_tile_720p(page: Page, tile: Locator, dest: Path) -> None:
    """对单个 tile：hover → 三点 → 下载 → 720p。"""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tile.scroll_into_view_if_needed()
    tile.hover()
    page.wait_for_timeout(500)

    more_btn = tile.locator("button").filter(
        has=page.locator("i.google-symbols", has_text="more_vert")
    )
    if more_btn.count() == 0:
        more_btn = tile.locator("button").filter(has=page.locator("i", has_text="more_vert"))
    if not is_visible(more_btn.first, 2500):
        raise RuntimeError("未找到三点更多按钮（more_vert）")

    more_btn.first.click(force=True)
    page.wait_for_timeout(400)

    download_item = page.get_by_role("menuitem").filter(has_text=re.compile(r"下载|Download", re.I))
    if not is_visible(download_item.first, 4000):
        raise RuntimeError("未找到「下载」菜单项")
    download_item.first.hover()
    page.wait_for_timeout(500)

    item_720 = page.get_by_role("menuitem").filter(has_text=re.compile(r"720\s*p", re.I))
    if not is_visible(item_720.first, 4000):
        raise RuntimeError("未找到 720p 下载选项")

    with page.expect_download(timeout=120000) as dl_info:
        item_720.first.click(force=True)
    download = dl_info.value
    suggested = download.suggested_filename or dest.name
    if not dest.suffix and "." in suggested:
        dest = dest.with_suffix(Path(suggested).suffix or ".mp4")
    download.save_as(dest)


def _ensure_valid_video_file(dest: Path, *, min_bytes: int = 1024) -> None:
    size = dest.stat().st_size if dest.is_file() else 0
    if size < min_bytes:
        raise RuntimeError(f"下载文件过小或不存在: {dest} ({size} bytes)")


def try_download_via_video_src(page: Page, dest: Path) -> bool:
    if not is_video_ready(page):
        return False
    video = page.locator("video").first
    src = video.evaluate(
        """el => el.currentSrc || el.src || (el.querySelector('source') && el.querySelector('source').src) || ''"""
    )
    if not src or not str(src).startswith("http"):
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    response = page.request.get(str(src), timeout=120_000)
    if not response.ok:
        return False
    body = response.body()
    if len(body) < 1024:
        return False
    dest.write_bytes(body)
    return dest.exists() and dest.stat().st_size >= 1024


def try_download_tile_via_video_src(page: Page, tile: Locator, dest: Path) -> bool:
    video = tile.locator("video")
    if video.count() == 0:
        return False
    src = video.first.evaluate("el => el.currentSrc || el.getAttribute('src') || ''")
    src = str(src or "")
    if not src.startswith("http"):
        if src.startswith("/"):
            src = f"https://labs.google{src}"
        else:
            return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    response = page.request.get(src, timeout=120_000)
    if not response.ok:
        return False
    body = response.body()
    if len(body) < 1024:
        return False
    dest.write_bytes(body)
    return dest.exists() and dest.stat().st_size >= 1024


def save_segment_video(page: Page, dest: Path) -> None:
    errors: list[str] = []
    try:
        download_latest_video(page, dest)
        _ensure_valid_video_file(dest)
        return
    except Exception as exc:
        errors.append(str(exc))
    if try_download_via_video_src(page, dest):
        _ensure_valid_video_file(dest)
        return
    raise RuntimeError("下载失败：" + ("; ".join(errors) if errors else "按钮与 video src 均不可用"))


def save_tile_video(page: Page, tile: Locator, dest: Path) -> None:
    errors: list[str] = []
    try:
        download_tile_720p(page, tile, dest)
        _ensure_valid_video_file(dest)
        return
    except Exception as exc:
        errors.append(f"720p: {exc}")
    if try_download_tile_via_video_src(page, tile, dest):
        _ensure_valid_video_file(dest)
        return
    raise RuntimeError("下载失败：" + ("; ".join(errors) if errors else "720p 与 video src 均不可用"))


def write_batch_report(report: BatchReport, path: Path) -> None:
    path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")


def build_flow_prompt(style_prefix: str, visual: str) -> str:
    visual = visual.strip()
    prefix = style_prefix.strip()
    if visual.lower().startswith(prefix[: min(40, len(prefix))].lower()):
        return visual
    return f"{prefix}\n\n{visual}"
