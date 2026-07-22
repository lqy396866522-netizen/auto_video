"""Orchestrate full Jianying compose pipeline."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from .clips import collect_segments
from .config import resolve_video_dir
from .import_clips import add_clips_to_timeline, click_start_create, import_clips
from .subtitle_tts import run_subtitle_tts
from .window import attach_or_launch
from .debug_log import dbg


@dataclass
class StepResult:
    name: str
    ok: bool
    duration_sec: float
    error: str = ""


@dataclass
class ComposeReport:
    slug: str
    video_dir: str
    prompts_file: str
    started_at: str
    finished_at: str = ""
    success: bool = False
    steps: list[dict[str, Any]] = field(default_factory=list)
    clips: list[str] = field(default_factory=list)

    def add_step(self, step: StepResult) -> None:
        self.steps.append(
            {
                "name": step.name,
                "ok": step.ok,
                "duration_sec": round(step.duration_sec, 2),
                "error": step.error,
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "slug": self.slug,
            "video_dir": self.video_dir,
            "prompts_file": self.prompts_file,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "success": self.success,
            "clips": self.clips,
            "steps": self.steps,
        }


def load_prompts(prompts_file: Path) -> dict[str, Any]:
    data = json.loads(prompts_file.read_text(encoding="utf-8"))
    if not data.get("narration_script"):
        segments = data.get("segments") or []
        parts = [s.get("narration_zh", "") for s in segments if s.get("narration_zh")]
        data["narration_script"] = "".join(parts)
    if not data.get("narration_script"):
        raise ValueError("prompts.json 缺少 narration_script 且无 segments.narration_zh")
    return data


def _run_step(name: str, fn) -> StepResult:
    t0 = time.time()
    try:
        fn()
        return StepResult(name=name, ok=True, duration_sec=time.time() - t0)
    except Exception as exc:
        return StepResult(
            name=name,
            ok=False,
            duration_sec=time.time() - t0,
            error=str(exc),
        )


def compose(
    prompts_file: Path,
    video_dir: Path,
    *,
    dry_run: bool = False,
    import_one_by_one: bool = False,
    report_path: Path | None = None,
) -> ComposeReport:
    load_dotenv()
    prompts_file = prompts_file.resolve()
    video_dir = resolve_video_dir(video_dir)
    data = load_prompts(prompts_file)
    slug = data.get("slug") or prompts_file.parent.name
    narration = data["narration_script"]

    report = ComposeReport(
        slug=slug,
        video_dir=str(video_dir),
        prompts_file=str(prompts_file),
        started_at=datetime.now(timezone.utc).isoformat(),
    )

    clips = collect_segments(video_dir)
    report.clips = [p.name for p in clips]

    if dry_run:
        print(f"视频目录: {video_dir}")
        print(f"片段 ({len(clips)}): " + ", ".join(p.name for p in clips))
        report.success = True
        report.finished_at = datetime.now(timezone.utc).isoformat()
        report.add_step(StepResult("validate_clips", True, 0))
        _write_report(report, report_path, video_dir, slug)
        return report

    print(f"视频目录: {video_dir}")
    print(f"将导入 {len(clips)} 个文件: {clips[0].name} … {clips[-1].name}")

    win = None
    steps_plan = [
        ("attach_jianying", lambda: None),  # placeholder, handled below
        ("start_create", lambda: click_start_create(win)),
        ("import_clips", lambda: import_clips(win, clips, one_by_one=import_one_by_one)),
        ("add_to_timeline", lambda: add_clips_to_timeline(win, count=len(clips))),
        ("subtitle_tts", lambda: run_subtitle_tts(win, narration)),
    ]

    for name, fn in steps_plan:
        if name == "attach_jianying":
            t0 = time.time()
            try:
                win = attach_or_launch()
                step = StepResult(name=name, ok=True, duration_sec=time.time() - t0)
            except Exception as exc:
                step = StepResult(
                    name=name,
                    ok=False,
                    duration_sec=time.time() - t0,
                    error=str(exc),
                )
        else:
            step = _run_step(name, fn)
        report.add_step(step)
        dbg("ui_compose.py:compose", f"step {name}", {"ok": step.ok, "error": step.error, "sec": step.duration_sec}, hypothesis_id="E")
        if not step.ok:
            report.success = False
            report.finished_at = datetime.now(timezone.utc).isoformat()
            _write_report(report, report_path, video_dir, slug)
            raise RuntimeError(f"步骤失败 [{name}]: {step.error}")

    report.success = True
    report.finished_at = datetime.now(timezone.utc).isoformat()
    _write_report(report, report_path, video_dir, slug)
    return report


def _write_report(
    report: ComposeReport,
    report_path: Path | None,
    video_dir: Path,
    slug: str,
) -> None:
    out = report_path or (video_dir / "jianying_compose_report.json")
    out.write_text(
        json.dumps(report.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
