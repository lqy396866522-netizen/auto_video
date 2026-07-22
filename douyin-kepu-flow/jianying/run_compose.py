"""CLI entry for Jianying compose automation."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .ui_compose import compose


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="剪映 UI 自动合成：导入 10 段 + 字幕配音")
    parser.add_argument("--prompts-file", required=True, help="prompts.json 路径")
    parser.add_argument("--video-dir", required=True, help="10 段 mp4 所在目录")
    parser.add_argument("--dry-run", action="store_true", help="仅校验片段，不操作剪映")
    parser.add_argument(
        "--import-one-by-one",
        action="store_true",
        help="文件对话框逐个导入（目录内有多余 mp4 时用）",
    )
    parser.add_argument(
        "--report-file",
        default="",
        help="报告输出路径（默认写入 VideoDir/jianying_compose_report.json）",
    )
    args = parser.parse_args(argv)

    prompts_file = Path(args.prompts_file)
    if not prompts_file.is_file():
        print(f"找不到 prompts 文件: {prompts_file}", file=sys.stderr)
        return 1

    report_path = Path(args.report_file) if args.report_file else None

    try:
        report = compose(
            prompts_file=prompts_file,
            video_dir=Path(args.video_dir),
            dry_run=args.dry_run,
            import_one_by_one=args.import_one_by_one,
            report_path=report_path,
        )
    except Exception as exc:
        print(f"剪映合成失败: {exc}", file=sys.stderr)
        return 1

    mode = "校验" if args.dry_run else "合成"
    status = "成功" if report.success else "失败"
    print(f"[{mode}{status}] slug={report.slug} clips={len(report.clips)}")
    for step in report.steps:
        mark = "OK" if step["ok"] else "FAIL"
        print(f"  {mark} {step['name']} ({step['duration_sec']}s)")
        if step.get("error"):
            print(f"       {step['error']}")
    return 0 if report.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
