"""Validate and render prompts.json / editing_guide.md."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

DEFAULT_STYLE_PREFIX = """Modern flat vector illustration,
corporate explainer animation style,
educational motion graphics.

Storyset style,
ManyPixels style,
Google Material illustration style.

2D flat design,
clean vector artwork,
bold black outlines,
consistent line thickness.

Friendly professional characters,
simple geometric shapes.

Low saturation pastel colors.

Smooth motion graphics animation,
gentle easing,
subtle character movement.

Minimal modern environment.

---

Chinese language requirement:

All visible text in the video must use simplified Chinese characters.

Use Chinese only for:
labels,
charts,
documents,
blackboards,
UI interfaces,
educational annotations.

Do not generate English text.
Do not generate random symbols.
Do not create fake unreadable text.

Chinese text must be clear and correctly written.

If text generation is unreliable,
keep the area blank or replace with simple icons.

---

No:
3D rendering,
anime,
Pixar style,
realistic characters,
cinematic lighting,
complex shadows,
random text,
English words."""

DEFAULT_ASPECT_RATIO = "16:9"
REQUIRED_SEGMENT_COUNT = 10


def slugify(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    text = re.sub(r"[\s_]+", "-", text)
    return text.strip("-") or "untitled"


def validate_payload(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for key in ("topic", "slug", "style_prefix", "segments"):
        if key not in data:
            errors.append(f"缺少字段: {key}")
    segments = data.get("segments")
    if not isinstance(segments, list):
        errors.append("segments 必须是数组")
        return errors
    if len(segments) != REQUIRED_SEGMENT_COUNT:
        errors.append(f"segments 数量应为 {REQUIRED_SEGMENT_COUNT}，当前为 {len(segments)}")
    for i, seg in enumerate(segments, start=1):
        for field in ("index", "duration_sec", "narration_zh", "visual_prompt_en"):
            if field not in seg:
                errors.append(f"第 {i} 段缺少字段: {field}")
        if seg.get("index") != i:
            errors.append(f"第 {i} 段 index 应为 {i}")
    return errors


def flow_prompt(style_prefix: str, visual: str) -> str:
    visual = visual.strip()
    prefix = style_prefix.strip()
    if visual.lower().startswith(prefix[:40].lower()):
        return visual
    return f"{prefix}\n\n{visual}"


def _ensure_sentence_end(text: str) -> str:
    text = text.strip()
    if not text:
        return text
    if text[-1] in "。！？；…":
        return text
    if text[-1] in "？」\"":
        return text
    return text + "。"


def build_narration_script(segments: list[dict[str, Any]]) -> str:
    """合并各段旁白为带段落换行的口播文案（每段一行/一段，便于剪映断句）。"""
    parts: list[str] = []
    for seg in segments:
        chunk = str(seg.get("narration_zh", "")).strip()
        if chunk:
            parts.append(_ensure_sentence_end(chunk))
    return "\n\n".join(parts)


def render_narration_script(data: dict[str, Any]) -> str:
    script = data.get("narration_script") or build_narration_script(data.get("segments", []))
    return script.strip() + "\n"


def render_editing_guide(data: dict[str, Any]) -> str:
    count = len(data["segments"])
    aspect = data.get("aspect_ratio", DEFAULT_ASPECT_RATIO)
    lines = [
        f"# 剪辑清单：{data['topic']}",
        "",
        f"- Slug: `{data['slug']}`",
        f"- 总段数: {count}",
        f"- 画幅: {aspect}",
        "",
        "| 段号 | 时间轴 | 旁白（中文） | 文件名 |",
        "|------|--------|--------------|--------|",
    ]
    cursor = 0
    for seg in data["segments"]:
        start = cursor
        end = cursor + int(seg.get("duration_sec", 6))
        ts = f"{start // 60:02d}:{start % 60:02d}–{end // 60:02d}:{end % 60:02d}"
        idx = int(seg["index"])
        fname = f"seg-{idx:02d}.mp4"
        narration = seg["narration_zh"].replace("|", "\\|")
        lines.append(f"| {idx} | {ts} | {narration} | {fname} |")
        cursor = end
    last_seg = f"seg-{count:02d}"
    lines.extend(
        [
            "",
            "## 剪映操作建议",
            "",
            f"1. 新建 {aspect} 项目，按上表顺序导入 seg-01 … {last_seg}",
            "2. 每段 clip 对齐 6 秒，段间可加 0.2s 交叉淡化",
            "3. 按旁白列录制或导入 TTS 配音",
            "",
        ]
    )
    return "\n".join(lines)


def cmd_validate(path: Path) -> int:
    data = json.loads(path.read_text(encoding="utf-8"))
    errors = validate_payload(data)
    if errors:
        for err in errors:
            print(f"ERROR: {err}", file=sys.stderr)
        return 1
    print(f"OK: {path}")
    return 0


def cmd_render_guide(path: Path, out: Path | None) -> int:
    data = json.loads(path.read_text(encoding="utf-8"))
    errors = validate_payload(data)
    if errors:
        for err in errors:
            print(f"ERROR: {err}", file=sys.stderr)
        return 1
    target = out or path.parent / "editing_guide.md"
    target.write_text(render_editing_guide(data), encoding="utf-8")
    print(f"Wrote {target}")
    narr_path = path.parent / "narration_script.txt"
    narr_path.write_text(render_narration_script(data), encoding="utf-8")
    print(f"Wrote {narr_path}")
    return 0


def cmd_render_narration(path: Path, out: Path | None) -> int:
    data = json.loads(path.read_text(encoding="utf-8"))
    if "segments" not in data:
        print("ERROR: 缺少 segments", file=sys.stderr)
        return 1
    target = out or path.parent / "narration_script.txt"
    target.write_text(render_narration_script(data), encoding="utf-8")
    print(f"Wrote {target}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Prompt JSON utilities")
    sub = parser.add_subparsers(dest="command", required=True)

    p_val = sub.add_parser("validate", help="Validate prompts.json")
    p_val.add_argument("--file", type=Path, required=True)

    p_guide = sub.add_parser("render-guide", help="Write editing_guide.md + narration_script.txt")
    p_guide.add_argument("--file", type=Path, required=True)
    p_guide.add_argument("--out", type=Path, default=None)

    p_narr = sub.add_parser("render-narration", help="Write narration_script.txt only")
    p_narr.add_argument("--file", type=Path, required=True)
    p_narr.add_argument("--out", type=Path, default=None)

    args = parser.parse_args()
    if args.command == "validate":
        return cmd_validate(args.file)
    if args.command == "render-guide":
        return cmd_render_guide(args.file, args.out)
    if args.command == "render-narration":
        return cmd_render_narration(args.file, args.out)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
