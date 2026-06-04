#!/usr/bin/env python3
"""Benchmark the three main agy-mcp paths and report wall-clock per call.

Run with the homebrew python that has agy_mcp installed:
    /opt/homebrew/opt/python@3.12/bin/python3.12 scripts/bench.py

A healthy run is tens of seconds per call. Anything near the timeout means a
wedge — see core.py (DEFAULT_TIMEOUT / auto-retry).
"""
import sys
import time
import tempfile
from pathlib import Path

from agy_mcp.core import run_agy, generate_image, DEFAULT_TIMEOUT, AGY_RETRIES, AGY_IMAGE_TIMEOUT


def timed(label, fn):
    t = time.time()
    try:
        out = fn()
        dt = time.time() - t
        print(f"[OK ] {label:<12} {dt:6.1f}s  -> {str(out)[:70]!r}")
        return dt
    except Exception as e:
        dt = time.time() - t
        print(f"[ERR] {label:<12} {dt:6.1f}s  -> {type(e).__name__}: {str(e)[:120]}")
        return None


def main():
    print(f"config: DEFAULT_TIMEOUT={DEFAULT_TIMEOUT}s  retries={AGY_RETRIES}  "
          f"image_timeout={AGY_IMAGE_TIMEOUT}s\n")
    times = {}

    times["文案生成/ask"] = timed("文案生成", lambda: run_agy(
        "写一句给营销 SaaS 的开屏标语,中文,12 字以内,只输出标语本身。"))

    times["网络调研/search"] = timed("网络调研", lambda: run_agy(
        "Use web search to answer: what did OpenAI ship for Codex this week?\n\n"
        "Return a concise synthesis followed by a numbered list of source URLs."))

    img = Path(tempfile.gettempdir()) / "agy_bench.jpg"
    times["图片生成/image"] = timed("图片生成", lambda: generate_image(
        "a minimalist blue paper airplane on a clean white background, flat design",
        str(img), aspect_ratio="1:1"))

    print("\n--- summary ---")
    ok = [v for v in times.values() if v is not None]
    for k, v in times.items():
        verdict = "n/a" if v is None else ("OK" if v < 180 else "SLOW")
        print(f"  {k:<18} {('%.1fs' % v) if v is not None else 'FAILED':>8}  [{verdict}]")
    if ok:
        print(f"\n  max={max(ok):.1f}s  (10 min = 600s; healthy = tens of seconds)")
    sys.exit(0 if len(ok) == len(times) else 1)


if __name__ == "__main__":
    main()
