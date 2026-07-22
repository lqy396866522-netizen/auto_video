"""Prepare test video dir and run E2E compose (debug session)."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEST_DIR = ROOT / "test-data" / "buffet-profit-secret"
PROMPTS = ROOT / "douyin-kepu-flow" / "prompts" / "buffet-profit-secret" / "prompts.json"


def setup_videos() -> Path:
    TEST_DIR.mkdir(parents=True, exist_ok=True)
    # clear old
    for old in TEST_DIR.glob("*.mp4"):
        old.unlink()
    dl = Path.home() / "Downloads"
    sources = sorted(dl.glob("*.mp4"))[:10]
    if len(sources) < 10:
        raise SystemExit(f"Downloads 里 mp4 不足 10 个（当前 {len(sources)}）")
    for i, src in enumerate(sources, start=1):
        dst = TEST_DIR / f"seg-{i:02d}.mp4"
        if not dst.exists():
            shutil.copy2(src, dst)
    print(f"Prepared {TEST_DIR} with 10 clips")
    return TEST_DIR


def main() -> int:
    video_dir = setup_videos()
    env = {**dict(**__import__("os").environ), "PYTHONPATH": str(ROOT / "douyin-kepu-flow")}
    cmd = [
        sys.executable,
        "-m",
        "jianying.run_compose",
        "--prompts-file",
        str(PROMPTS),
        "--video-dir",
        str(video_dir),
    ]
    print("Running:", " ".join(cmd))
    return subprocess.call(cmd, cwd=str(ROOT), env=env)


if __name__ == "__main__":
    raise SystemExit(main())
