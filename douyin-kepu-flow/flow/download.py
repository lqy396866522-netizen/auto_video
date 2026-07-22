"""Google Flow — 下载与报告。"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from playwright.sync_api import Page

from .common import click_first_matching, is_visible
from .navigate import is_video_ready


@dataclass
class SegmentResult:
    index: int
    status: str
    file: str | None = None
    error: str | None = None
    attempts: int = 1


@dataclass
class BatchReport:
    topic: str
    slug: str
    download_dir: str
    started_at: str
    finished_at: str | None = None
    segments: list[SegmentResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "topic": self.topic,
            "slug": self.slug,
            "download_dir": self.download_dir,
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


def try_download_via_video_src(page: Page, dest: Path) -> bool:
    if not is_video_ready(page):
        return False
    video = page.locator("video").first
    src = video.evaluate(
        """el => el.currentSrc || el.src || (el.querySelector('source') && el.querySelector('source').src) || ''"""
    )
    if not src or not str(src).startswith("http"):
        return False
    import urllib.request

    dest.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(src, dest)  # noqa: S310 — user-initiated Flow asset
    return dest.exists() and dest.stat().st_size > 0


def save_segment_video(page: Page, dest: Path) -> None:
    try:
        download_latest_video(page, dest)
        return
    except Exception:
        pass
    if try_download_via_video_src(page, dest):
        return
    raise RuntimeError("下载失败：既无下载按钮也无法读取 video src")


def write_batch_report(report: BatchReport, path: Path) -> None:
    path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")


def build_flow_prompt(style_prefix: str, visual: str) -> str:
    visual = visual.strip()
    prefix = style_prefix.strip()
    if visual.lower().startswith(prefix[: min(40, len(prefix))].lower()):
        return visual
    return f"{prefix}\n\n{visual}"
