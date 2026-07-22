"""Scan folder for 10 segment mp4 files ordered 01-10."""
from __future__ import annotations

import re
from pathlib import Path

REQUIRED_COUNT = 10

_PATTERNS = [
    re.compile(r"seg[-_]?(\d{1,2})", re.I),
    re.compile(r"(?:^|[-_.])(\d{1,2})(?:[-_.]|$)", re.I),
]


def extract_segment_index(path: Path) -> int | None:
    name = path.stem
    for pat in _PATTERNS:
        for m in pat.findall(name):
            idx = int(m)
            if 1 <= idx <= REQUIRED_COUNT:
                return idx
    return None


def collect_segments(video_dir: Path) -> list[Path]:
    if not video_dir.is_dir():
        raise FileNotFoundError(f"目录不存在: {video_dir}")

    found: dict[int, Path] = {}
    duplicates: list[str] = []

    for mp4 in sorted(video_dir.glob("*.mp4")):
        idx = extract_segment_index(mp4)
        if idx is None:
            continue
        if idx in found:
            duplicates.append(f"序号 {idx:02d}: {found[idx].name} 与 {mp4.name}")
        else:
            found[idx] = mp4.resolve()

    missing = [i for i in range(1, REQUIRED_COUNT + 1) if i not in found]
    errors: list[str] = []
    if missing:
        errors.append(f"缺少序号: {', '.join(f'{i:02d}' for i in missing)}")
    if duplicates:
        errors.extend(duplicates)
    if errors:
        hint = "\n".join(f"  - {e}" for e in errors)
        raise ValueError(
            f"在 {video_dir} 未找到完整 01-10 片段（当前 {len(found)}/{REQUIRED_COUNT}）:\n{hint}\n"
            f"提示: 文件名需含 seg-01 或 01 等序号"
        )

    return [found[i] for i in range(1, REQUIRED_COUNT + 1)]
