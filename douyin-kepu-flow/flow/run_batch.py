"""Google Flow 批处理主入口。"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

from .common import (
    DEFAULT_CDP_PORT,
    DEFAULT_FLOW_URL,
    DEFAULT_PROFILE,
    connect_browser,
    ensure_browser,
    env_int,
    env_str,
    get_work_page,
    load_dotenv_if_present,
)
from .download import (
    BatchReport,
    SegmentResult,
    build_flow_prompt,
    save_segment_video,
    write_batch_report,
)
from .navigate import (
    is_logged_in,
    open_flow,
    prepare_next_segment,
    submit_prompt,
    wait_for_generation_complete,
    wait_for_manual_login,
)


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_prompts(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if "segments" not in data or not data["segments"]:
        raise ValueError("prompts.json 缺少 segments")
    return data


def resolve_download_dir(template: str, slug: str) -> Path:
    path = Path(env_str("FLOW_DOWNLOAD_DIR", template).replace("{topic}", slug))
    path.mkdir(parents=True, exist_ok=True)
    return path


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
    topic = data.get("topic", slug)
    style_prefix = data.get("style_prefix", "")
    aspect_ratio = data.get("aspect_ratio", "16:9")
    segments = data["segments"]

    flow_url = env_str("FLOW_URL", DEFAULT_FLOW_URL)
    cdp_port = env_int("FLOW_CDP_PORT", DEFAULT_CDP_PORT)
    profile = Path(env_str("FLOW_BROWSER_PROFILE", str(DEFAULT_PROFILE)))
    timeout_sec = env_int("FLOW_GENERATION_TIMEOUT_SEC", 300)
    retries = env_int("FLOW_GENERATION_RETRIES", 2)

    download_dir = resolve_download_dir(
        str(Path.home() / "Desktop" / "douyin-videos" / "{topic}"), slug
    )

    report = BatchReport(
        topic=topic,
        slug=slug,
        download_dir=str(download_dir),
        started_at=datetime.now(timezone.utc).isoformat(),
    )
    report_path = download_dir / "batch_report.json"

    ensure_browser(cdp_port, profile)

    with sync_playwright() as pw:
        browser = connect_browser(pw, cdp_port)
        context = browser.contexts[0] if browser.contexts else browser.new_context()
        page = get_work_page(context, flow_url)
        open_flow(page, flow_url)

        if not skip_login_wait and not is_logged_in(page):
            wait_for_manual_login(page, flow_url)

        for seg in segments:
            idx = int(seg.get("index", 0))
            dest = download_dir / f"seg-{idx:02d}.mp4"
            prompt = build_flow_prompt(style_prefix, seg["visual_prompt_en"])
            result = SegmentResult(index=idx, status="failed")

            for attempt in range(1, retries + 2):
                result.attempts = attempt
                try:
                    if attempt > 1:
                        prepare_next_segment(page)
                    submit_prompt(page, prompt)
                    if submit_only:
                        prepare_next_segment(page)
                        result.status = "success"
                        result.file = None
                        print(f"[OK] seg-{idx:02d} 已提交")
                        break
                    wait_for_generation_complete(page, timeout_sec=timeout_sec)
                    save_segment_video(page, dest)
                    result.status = "success"
                    result.file = str(dest)
                    result.error = None
                    print(f"[OK] seg-{idx:02d} -> {dest}")
                    prepare_next_segment(page)
                    break
                except Exception as exc:
                    result.error = str(exc)
                    print(f"[RETRY {attempt}] seg-{idx:02d}: {exc}", file=sys.stderr)

            if result.status != "success":
                print(f"[FAIL] seg-{idx:02d}", file=sys.stderr)
            report.segments.append(result)
            write_batch_report(report, report_path)

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
        help="仅提交 prompt 并清空输入框，不等待生成/下载",
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
