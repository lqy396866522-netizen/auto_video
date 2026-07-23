"""Flow 干跑测试：仅填入 N 段 prompt（不点「创建」）+ 下载页面上已有前 N 个 tile。

不会提交生成新视频，不消耗 Flow 额度。

用法（在 auto_video 根目录）:
  $env:PYTHONPATH="douyin-kepu-flow"
  python -m flow.test_fill_download --prompts-file douyin-kepu-flow/prompts/payment-pain/prompts.json
  python -m flow.test_fill_download --fill-only
  python -m flow.test_fill_download --download-only
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

from .common import (
    DEFAULT_CDP_PORT,
    DEFAULT_FLOW_URL,
    clear_prompt_editor,
    connect_browser,
    ensure_browser,
    env_int,
    env_str,
    fill_prompt_text,
    get_create_submit_button,
    get_prompt_editor,
    get_work_page,
    load_dotenv_if_present,
    resolve_browser_profile,
)
from .download import build_flow_prompt, save_tile_video
from .navigate import open_flow
from .run_batch import load_prompts, resolve_topic
from .tiles import (
    TileState,
    format_segment_filename,
    get_tile_locator,
    get_tile_state,
    ordered_tile_ids,
    sanitize_topic_dirname,
)


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _read_editor_text(page: Page) -> str:
    editor = get_prompt_editor(page)
    try:
        text = editor.evaluate(
            """el => {
                const walk = n => {
                    if (!n) return '';
                    if (n.nodeType === Node.TEXT_NODE) return n.textContent || '';
                    return Array.from(n.childNodes).map(walk).join('');
                };
                return (el.innerText || walk(el) || '').trim();
            }"""
        )
        return (text or "").strip()
    except Exception:
        return (editor.inner_text() or "").strip()


def _create_button_disabled(page: Page) -> bool | None:
    try:
        btn = get_create_submit_button(page)
        val = btn.get_attribute("aria-disabled")
        return val in ("true", "True")
    except Exception:
        return None


def _snippet(text: str, n: int = 48) -> str:
    t = " ".join(text.split())
    return t[:n] + ("…" if len(t) > n else "")


def test_fill_only(page: Page, segments: list[dict], style_prefix: str) -> bool:
    """循环 N 次：填入 → 读回验证 → 清空。绝不点击「创建」。"""
    ok_all = True
    n = len(segments)
    print(f"\n=== 阶段 1：填入测试（{n} 段，不提交）===")

    for i, seg in enumerate(segments):
        idx = int(seg.get("index", i + 1))
        visual = seg["visual_prompt_en"]
        prompt = build_flow_prompt(style_prefix, visual)
        marker = _snippet(visual, 40)

        try:
            fill_prompt_text(page, prompt)
            page.wait_for_timeout(400)
            actual = _read_editor_text(page)
            contains_marker = marker[:20].lower() in actual.lower() if marker else bool(actual)
            create_disabled = _create_button_disabled(page)

            len_ok = abs(len(actual) - len(prompt)) <= max(30, int(len(prompt) * 0.05))
            status = "OK" if contains_marker and len_ok else "FAIL"
            if status != "OK":
                ok_all = False
            print(f"  [{status}] seg-{idx:02d} len={len(actual)} marker_hit={contains_marker} create_disabled={create_disabled}")

            clear_prompt_editor(page)
            page.wait_for_timeout(300)
            after_clear = _read_editor_text(page)
            if len(after_clear) > 80:
                print(f"  [WARN] seg-{idx:02d} 清空后仍有 {len(after_clear)} 字符残留")
                ok_all = False

        except Exception as exc:
            ok_all = False
            print(f"  [FAIL] seg-{idx:02d}: {exc}", file=sys.stderr)

    print(f"\n填入测试: {'全部通过' if ok_all else '存在失败'}")
    return ok_all


def test_download_only(page: Page, segments: list[dict], download_dir: Path) -> bool:
    """下载页面上已有前 N 个 tile（按 DOM 顺序，仅 COMPLETE），不提交新 prompt。"""
    n = len(segments)
    max_index = max(int(s.get("index", i + 1)) for i, s in enumerate(segments))
    download_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n=== 阶段 2：下载测试（前 {n} 个已完成 tile，不提交）===")
    print(f"保存目录: {download_dir}")

    tile_ids = ordered_tile_ids(page)
    print(f"  页面共 {len(tile_ids)} 个 tile")

    complete_tiles: list[tuple[str, TileState]] = []
    for tid in tile_ids:
        tile = get_tile_locator(page, tid)
        state = get_tile_state(tile)
        if state == TileState.COMPLETE:
            complete_tiles.append((tid, state))
        if len(complete_tiles) >= n:
            break

    if len(complete_tiles) < n:
        print(f"  [WARN] 仅找到 {len(complete_tiles)}/{n} 个已完成 tile，仍将尝试下载已有的")

    ok_all = True
    for i, (tid, _state) in enumerate(complete_tiles[:n]):
        idx = i + 1
        dest = download_dir / format_segment_filename(idx, max_index)
        tile = get_tile_locator(page, tid)
        try:
            save_tile_video(page, tile, dest)
            size = dest.stat().st_size if dest.is_file() else 0
            if size < 1024:
                ok_all = False
                print(f"  [FAIL] {dest.name} 文件过小 ({size} bytes)", file=sys.stderr)
            else:
                print(f"  [OK] {dest.name} <- tile {tid} ({size} bytes)")
        except Exception as exc:
            ok_all = False
            print(f"  [FAIL] seg-{idx:02d} tile {tid}: {exc}", file=sys.stderr)

    if not complete_tiles:
        print("  [FAIL] 页面上没有可下载的已完成 tile")
        return False

    print(f"\n下载测试: {'全部通过' if ok_all else '存在失败'}")
    return ok_all


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Flow 干跑：仅填入 prompt + 下载已有 tile（不提交生成）")
    parser.add_argument(
        "--prompts-file",
        type=Path,
        default=Path("douyin-kepu-flow/prompts/payment-pain/prompts.json"),
        help="prompts.json 路径",
    )
    parser.add_argument("--fill-only", action="store_true", help="只测填入")
    parser.add_argument("--download-only", action="store_true", help="只测下载")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path(r"D:\douyin-videos\_flow_fill_test"),
        help="下载测试输出目录",
    )
    args = parser.parse_args(argv)

    root = project_root()
    load_dotenv_if_present(root)

    prompts_path = args.prompts_file
    if not prompts_path.is_file():
        alt = root / args.prompts_file
        if alt.is_file():
            prompts_path = alt
        else:
            print(f"找不到 prompts 文件: {args.prompts_file}", file=sys.stderr)
            return 1

    data = load_prompts(prompts_path)
    segments = data["segments"]
    style_prefix = data.get("style_prefix", "")
    topic = resolve_topic(data, prompts_path)
    n = len(segments)

    do_fill = not args.download_only
    do_download = not args.fill_only

    flow_url = env_str("FLOW_URL", DEFAULT_FLOW_URL)
    cdp_port = env_int("FLOW_CDP_PORT", DEFAULT_CDP_PORT)
    profile = resolve_browser_profile()

    print(f"prompts: {prompts_path}")
    print(f"段数 N={n}  topic={topic}")
    print("[WARN] 本脚本不会点击「创建」，不会消耗 Flow 生成额度")

    ensure_browser(cdp_port, profile)

    fill_ok = True
    dl_ok = True

    with sync_playwright() as pw:
        browser = connect_browser(pw, cdp_port)
        context = browser.contexts[0] if browser.contexts else browser.new_context()
        page = get_work_page(context, flow_url)
        open_flow(page, flow_url)
        page.wait_for_timeout(1500)

        if do_fill:
            fill_ok = test_fill_only(page, segments, style_prefix)
        if do_download:
            topic_dir = args.out_dir / sanitize_topic_dirname(topic)
            dl_ok = test_download_only(page, segments, topic_dir)

    if not fill_ok or not dl_ok:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
