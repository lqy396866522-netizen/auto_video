"""Jianying automation configuration."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path


def expand_env(value: str) -> str:
    return os.path.expandvars(os.path.expanduser(value))


def env_str(name: str, default: str) -> str:
    return expand_env(os.getenv(name, default))


def env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    return int(raw) if raw else default


def _running_jianying_exe() -> Path | None:
    try:
        out = subprocess.check_output(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "(Get-CimInstance Win32_Process -Filter \"Name='JianyingPro.exe'\" "
                "| Select-Object -First 1).ExecutablePath",
            ],
            text=True,
            errors="replace",
            timeout=10,
        ).strip()
        p = Path(out)
        if p.is_file():
            return p.resolve()
    except Exception:
        pass
    return None


def default_jianying_exe() -> Path:
    running = _running_jianying_exe()
    if running:
        return running
    candidates: list[Path] = []
    for drive in ("E:", "D:", "C:"):
        root = Path(drive + "/")
        if not root.exists():
            continue
        candidates.extend(root.glob("*/JianyingPro/JianyingPro.exe"))
        candidates.extend(root.glob("*/JianyingPro/*/JianyingPro.exe"))
    candidates.extend(
        [
            Path(os.getenv("LOCALAPPDATA", "")) / "JianyingPro" / "Apps" / "JianyingPro.exe",
            Path(os.getenv("LOCALAPPDATA", "")) / "JianyingPro" / "JianyingPro.exe",
            Path(r"C:\Program Files\JianyingPro\JianyingPro.exe"),
        ]
    )
    for p in candidates:
        if p.is_file():
            return p.resolve()
    return candidates[0] if candidates else Path("JianyingPro.exe")


def resolve_video_dir(video_dir: str | Path) -> Path:
    p = Path(expand_env(str(video_dir)))
    if p.is_dir():
        return p.resolve()
    desktop_sub = Path.home() / "Desktop" / "douyin-videos" / p.name
    if desktop_sub.is_dir():
        return desktop_sub.resolve()
    desktop_direct = Path.home() / "Desktop" / p.name
    if desktop_direct.is_dir():
        return desktop_direct.resolve()
    raise FileNotFoundError(
        f"视频目录不存在: {video_dir}\n"
        f"尝试过: {p}, {desktop_sub}, {desktop_direct}"
    )
