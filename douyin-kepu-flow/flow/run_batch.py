"""Google Flow 批处理主入口。"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

from .common import (
    DEFAULT_CDP_PORT,
    DEFAULT_DOWNLOAD_DIR_TEMPLATE,
    DEFAULT_FLOW_URL,
    connect_browser,
    ensure_browser,
    env_int,
    env_str,
    get_work_page,
    load_dotenv_if_present,
    resolve_browser_profile,
)
from .download import (
    BatchReport,
    SegmentResult,
    build_flow_prompt,
    save_tile_video,
    write_batch_report,
)
from .navigate import (
    is_logged_in,
    open_flow,
    prepare_next_segment,
    submit_prompt,
    wait_for_manual_login,
)
from .tiles import (
    TileState,
    format_segment_filename,
    get_tile_locator,
    get_tile_state,
    sanitize_topic_dirname,
    segment_is_done,
    snapshot_tile_ids,
    wait_for_new_tile,
)


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_prompts(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if "segments" not in data or not data["segments"]:
        raise ValueError("prompts.json 缺少 segments")
    return data


def resolve_topic(data: dict, prompts_file: Path) -> str:
    """下载目录名：优先 topic，其次 title，最后 slug。"""
    slug = data.get("slug") or prompts_file.parent.name
    return data.get("topic") or data.get("title") or slug


def resolve_download_dir(template: str, topic: str) -> Path:
    dirname = sanitize_topic_dirname(topic)
    path = Path(env_str("FLOW_DOWNLOAD_DIR", template).replace("{topic}", dirname))
    path.mkdir(parents=True, exist_ok=True)
    return path


def _segment_indices(segments: list[dict]) -> list[int]:
    return [int(seg.get("index", i + 1)) for i, seg in enumerate(segments)]


def _max_segment_index(segments: list[dict]) -> int:
    return max(_segment_indices(segments))


def _watch_timeout_sec(segment_count: int) -> int:
    default = max(3600, segment_count * 300)
    return env_int("FLOW_BATCH_WATCH_TIMEOUT_SEC", default)


def _poll_interval_sec() -> float:
    return env_int("FLOW_TILE_POLL_INTERVAL_SEC", 3)


def _create_button_timeout_ms() -> int:
    return env_int("FLOW_CREATE_BUTTON_TIMEOUT_SEC", 120) * 1000


def _new_tile_timeout_sec() -> float:
    return float(env_int("FLOW_NEW_TILE_TIMEOUT_SEC", 90))


def submit_all_segments(
    page: Page,
    *,
    segments: list[dict],
    style_prefix: str,
    known_ids: set[str],
    results: dict[int, SegmentResult],
    index_to_tile: dict[int, str],
) -> None:
    """按 prompts.json 段数连续提交 N 段（Flow 支持并行排队，不等单段生成完）。"""
    create_timeout_ms = _create_button_timeout_ms()
    tile_timeout_sec = _new_tile_timeout_sec()
    segment_count = len(segments)

    print(f"[INFO] 批量提交 {segment_count} 段 prompt…")

    for i, seg in enumerate(segments):
        idx = int(seg.get("index", i + 1))
        prompt = build_flow_prompt(style_prefix, seg["visual_prompt_en"])
        try:
            submit_prompt(page, prompt, create_timeout_ms=create_timeout_ms)
            prepare_next_segment(page)
            tile_id = wait_for_new_tile(page, known_ids, timeout_sec=tile_timeout_sec)
            known_ids.add(tile_id)
            index_to_tile[idx] = tile_id
            print(f"[OK] seg-{idx:02d} 已提交 ({i + 1}/{segment_count}) -> tile {tile_id}")
        except Exception as exc:
            results[idx].status = "failed"
            results[idx].error = str(exc)
            print(f"[WARN] seg-{idx:02d} 提交失败: {exc}", file=sys.stderr)
            try:
                prepare_next_segment(page)
            except Exception:
                pass


def run_submit_only(
    page: Page,
    *,
    segments: list[dict],
    style_prefix: str,
    report: BatchReport,
    report_path: Path,
) -> None:
    """调试：仅提交 N 段 prompt，不监听/下载。"""
    create_timeout_ms = _create_button_timeout_ms()
    indices = _segment_indices(segments)

    for i, seg in enumerate(segments):
        idx = int(seg.get("index", i + 1))
        prompt = build_flow_prompt(style_prefix, seg["visual_prompt_en"])
        result = SegmentResult(index=idx, status="failed")
        try:
            submit_prompt(page, prompt, create_timeout_ms=create_timeout_ms)
            prepare_next_segment(page)
            result.status = "success"
            print(f"[OK] seg-{idx:02d} 已提交 ({i + 1}/{len(segments)})")
        except Exception as exc:
            result.error = str(exc)
            print(f"[WARN] seg-{idx:02d}: {exc}", file=sys.stderr)
        report.segments.append(result)
        write_batch_report(report, report_path)


def run_watch_and_download(
    page: Page,
    *,
    segments: list[dict],
    style_prefix: str,
    download_dir: Path,
    report: BatchReport,
    report_path: Path,
) -> None:
    segment_count = len(segments)
    max_index = _max_segment_index(segments)
    indices = _segment_indices(segments)

    results: dict[int, SegmentResult] = {
        idx: SegmentResult(index=idx, status="pending") for idx in indices
    }
    index_to_tile: dict[int, str] = {}
    downloaded: set[int] = set()

    known_ids = snapshot_tile_ids(page)
    print(f"[INFO] baseline tiles: {len(known_ids)}")

    submit_all_segments(
        page,
        segments=segments,
        style_prefix=style_prefix,
        known_ids=known_ids,
        results=results,
        index_to_tile=index_to_tile,
    )

    submitted = len(index_to_tile)
    print(f"[INFO] 提交完成: {submitted}/{segment_count} 段已绑定 tile，开始监听并下载…")
    report.segments = [results[i] for i in indices]
    write_batch_report(report, report_path)

    watch_deadline = time.monotonic() + _watch_timeout_sec(segment_count)
    poll_sec = _poll_interval_sec()

    while time.monotonic() < watch_deadline:
        any_active = False

        for idx in indices:
            result = results[idx]
            if segment_is_done(
                has_tile=idx in index_to_tile,
                state=TileState.FAILED if result.status == "failed" and idx not in index_to_tile else None,
                downloaded=idx in downloaded,
            ):
                if idx not in index_to_tile and result.status == "pending":
                    result.status = "failed"
                    result.error = result.error or "未绑定 tile"
                continue

            tile_id = index_to_tile.get(idx)
            if not tile_id:
                any_active = True
                continue

            tile = get_tile_locator(page, tile_id)
            state = get_tile_state(tile)

            if state == TileState.FAILED:
                result.status = "failed"
                result.error = "Flow 生成失败"
                result.tile_id = tile_id
                print(f"[FAIL] seg-{idx:02d} Flow 标记失败")
                continue

            if state in (TileState.GENERATING, TileState.UNKNOWN):
                any_active = True
                continue

            if state == TileState.COMPLETE and idx not in downloaded:
                dest = download_dir / format_segment_filename(idx, max_index)
                try:
                    save_tile_video(page, tile, dest)
                    result.status = "success"
                    result.file = str(dest)
                    result.error = None
                    result.tile_id = tile_id
                    downloaded.add(idx)
                    print(f"[OK] seg-{idx:02d} -> {dest}")
                except Exception as exc:
                    result.error = str(exc)
                    result.tile_id = tile_id
                    any_active = True
                    print(f"[RETRY download] seg-{idx:02d}: {exc}", file=sys.stderr)
                continue

        report.segments = [results[i] for i in indices]
        write_batch_report(report, report_path)

        all_done = True
        for idx in indices:
            result = results[idx]
            if result.status == "failed" or idx in downloaded:
                continue
            if idx not in index_to_tile:
                all_done = False
                continue
            state = get_tile_state(get_tile_locator(page, index_to_tile[idx]))
            if state not in (TileState.COMPLETE, TileState.FAILED):
                all_done = False
        if all_done:
            print(f"[INFO] 全部 {segment_count} 段已终态")
            break

        if any_active:
            page.wait_for_timeout(int(poll_sec * 1000))
        else:
            break
    else:
        print(f"[WARN] 监听超时（{_watch_timeout_sec(segment_count)}s）", file=sys.stderr)
        for idx in indices:
            if results[idx].status == "pending":
                results[idx].status = "failed"
                results[idx].error = results[idx].error or "监听超时"

    report.segments = [results[i] for i in indices]
    write_batch_report(report, report_path)


def run_batch(
    prompts_file: Path,
    *,
    skip_login_wait: bool = True,
    submit_only: bool = False,
) -> int:
    root = project_root()
    load_dotenv_if_present(root)

    data = load_prompts(prompts_file)
    slug = data.get("slug") or prompts_file.parent.name
    topic = resolve_topic(data, prompts_file)
    style_prefix = data.get("style_prefix", "")
    segments = data["segments"]
    segment_count = len(segments)

    flow_url = env_str("FLOW_URL", DEFAULT_FLOW_URL)
    cdp_port = env_int("FLOW_CDP_PORT", DEFAULT_CDP_PORT)
    profile = resolve_browser_profile()

    download_dir = resolve_download_dir(DEFAULT_DOWNLOAD_DIR_TEMPLATE, topic)

    report = BatchReport(
        topic=topic,
        slug=slug,
        download_dir=str(download_dir),
        segment_count=segment_count,
        started_at=datetime.now(timezone.utc).isoformat(),
    )
    report_path = download_dir / "batch_report.json"

    print(f"[INFO] slug={slug} 段数={segment_count} 下载目录={download_dir}")

    ensure_browser(cdp_port, profile)

    with sync_playwright() as pw:
        browser = connect_browser(pw, cdp_port)
        context = browser.contexts[0] if browser.contexts else browser.new_context()
        page = get_work_page(context, flow_url)
        open_flow(page, flow_url)

        if not skip_login_wait and not is_logged_in(page):
            wait_for_manual_login(page, flow_url)

        if submit_only:
            run_submit_only(
                page,
                segments=segments,
                style_prefix=style_prefix,
                report=report,
                report_path=report_path,
            )
        else:
            run_watch_and_download(
                page,
                segments=segments,
                style_prefix=style_prefix,
                download_dir=download_dir,
                report=report,
                report_path=report_path,
            )

    report.finished_at = datetime.now(timezone.utc).isoformat()
    write_batch_report(report, report_path)

    failed = sum(1 for s in report.segments if s.status != "success")
    print(f"\n完成: 成功 {len(report.segments) - failed}/{len(report.segments)}")
    print(f"下载目录: {download_dir}")
    print(f"报告: {report_path}")
    return 1 if failed else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Google Flow 批量生成抖音科普视频片段")
    parser.add_argument("--prompts-file", required=True, type=Path, help="prompts.json 路径")
    parser.add_argument(
        "--require-login",
        action="store_true",
        help="启用登录检测与等待（默认跳过，假定项目页已登录）",
    )
    parser.add_argument(
        "--submit-only",
        action="store_true",
        help="仅提交 N 段 prompt（N=len(segments)），不监听/下载",
    )
    parser.add_argument(
        "--watch-and-download",
        action="store_true",
        help="（默认行为）批量提交 N 段后监听网格并 720p 下载",
    )
    args = parser.parse_args()
    if not args.prompts_file.is_file():
        print(f"文件不存在: {args.prompts_file}", file=sys.stderr)
        return 1
    skip_login = not args.require_login
    return run_batch(
        args.prompts_file,
        skip_login_wait=skip_login,
        submit_only=args.submit_only,
    )


if __name__ == "__main__":
    raise SystemExit(main())
