"""Scan folder for segment mp4 files ordered by index in filename."""
from __future__ import annotations

import re
from pathlib import Path

_PATTERNS = [
    re.compile(r"seg[-_]?(\d{1,3})", re.I),
    re.compile(r"(?:^|[-_.])(\d{1,3})(?:[-_.]|$)", re.I),
]


def extract_segment_index(path: Path, *, max_index: int = 999) -> int | None:
    name = path.stem
    for pat in _PATTERNS:
        for m in pat.findall(name):
            idx = int(m)
            if 1 <= idx <= max_index:
                return idx
    return None


def collect_segments(video_dir: Path, *, expected_count: int | None = None) -> list[Path]:
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

    if expected_count is None:
        expected_count = max(found.keys()) if found else 0
    if expected_count <= 0:
        raise ValueError(f"在 {video_dir} 未找到任何带序号的 mp4")

    missing = [i for i in range(1, expected_count + 1) if i not in found]
    errors: list[str] = []
    if missing:
        errors.append(f"缺少序号: {', '.join(f'{i:02d}' for i in missing)}")
    if duplicates:
        errors.extend(duplicates)
    if errors:
        hint = "\n".join(f"  - {e}" for e in errors)
        raise ValueError(
            f"在 {video_dir} 未找到完整 01-{expected_count:02d} 片段（当前 {len(found)}/{expected_count}）:\n{hint}\n"
            f"提示: 文件名需含 seg-01 或 01 等序号"
        )

    return [found[i] for i in range(1, expected_count + 1)]
