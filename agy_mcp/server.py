"""agy-mcp: MCP server wrapping Google Antigravity CLI (`agy`).

Exposes Antigravity capabilities (chat, search, image gen, code review, etc.)
to any MCP client. All calls go through the local `agy` CLI, which uses your
OAuth login — so usage is billed against your Google AI subscription, not the
Gemini API.

The CLI invocation and the transcript-recovery workaround for the `agy -p`
non-TTY stdout bug live in `agy_mcp.core` and are shared with the `agq` CLI.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import FastMCP

from .core import AGY_BIN, DEFAULT_TIMEOUT, AgyError, _agy_cmd, generate_image, run_agy
from .gemini import run_gemini, search_gemini

mcp = FastMCP("agy")


@mcp.tool()
def ask(prompt: str, cwd: Optional[str] = None) -> str:
    """General-purpose Antigravity (agy) query. Use for analysis, Q&A, drafting,
    code generation, anything that doesn't fit a more specific tool.

    Args:
        prompt: Full natural-language instruction.
        cwd: Optional working directory (defaults to current). The agent can
             read/write files relative to this path.
    """
    return run_agy(prompt, cwd=cwd)


@mcp.tool()
def search(query: str) -> str:
    """Web search via Antigravity's built-in Google Search tool. Returns a
    synthesized answer with citations. Best for fresh/realtime info.
    """
    p = (
        f"Use web search to answer: {query}\n\n"
        "Return a concise synthesis followed by a numbered list of source URLs."
    )
    return run_agy(p)


@mcp.tool()
def gemini_ask(prompt: str) -> str:
    """General-purpose query via the official Gemini CLI (OAuth subscription).
    More stable than `ask` for plain text; prefer this for non-image text work.
    """
    return run_gemini(prompt)


@mcp.tool()
def gemini_search(query: str) -> str:
    """Web search via the Gemini CLI's google_web_search grounding. Returns a
    synthesized answer with real source URLs. More stable than agy `search`.
    """
    return search_gemini(query)


@mcp.tool()
def image(prompt: str, out_path: str, aspect_ratio: str = "1:1") -> str:
    """Generate an image with Antigravity's image tool and save it locally.

    Note: output is JPEG regardless of extension; prefer `.jpg`.

    Args:
        prompt: Image description.
        out_path: Absolute path to save the file (e.g. /tmp/hero.jpg).
        aspect_ratio: One of "1:1", "16:9", "9:16", "4:3", "3:4".
    """
    target = generate_image(prompt, out_path, aspect_ratio=aspect_ratio)
    return f"Saved: {target} ({target.stat().st_size} bytes)"


@mcp.tool()
def code_review(target_path: str, focus: Optional[str] = None) -> str:
    """Review a file or directory for bugs, smells, and improvements.

    Args:
        target_path: Path to file or directory to review.
        focus: Optional focus area (e.g. "security", "performance", "naming").
    """
    path = Path(target_path).expanduser().resolve()
    if not path.exists():
        raise ValueError(f"path not found: {path}")
    focus_line = f"Focus particularly on: {focus}.\n" if focus else ""
    p = (
        f"Code review the file or directory at: {path}\n"
        f"{focus_line}"
        "Output: prioritized findings (Critical / Major / Minor), each with "
        "file:line reference and a concrete suggested fix. Be terse."
    )
    return run_agy(p, cwd=str(path.parent if path.is_file() else path))


@mcp.tool()
def explain(target: str, level: str = "brief") -> str:
    """Explain what code does. `target` is a file path or raw code snippet.

    Args:
        target: Path to file, OR a code snippet (auto-detected).
        level: "brief" (default, 3-5 sentences) or "detailed" (with examples).
    """
    detail = (
        "in 3-5 sentences, no fluff"
        if level == "brief"
        else "in depth, with concrete examples and edge cases"
    )
    candidate = Path(target).expanduser()
    if candidate.exists() and candidate.is_file():
        p = f"Read {candidate.resolve()} and explain what it does, {detail}."
        return run_agy(p, cwd=str(candidate.parent))
    p = f"Explain what this code does, {detail}:\n\n```\n{target}\n```"
    return run_agy(p)


@mcp.tool()
def translate(text: str, target_lang: str = "English", tone: str = "natural") -> str:
    """Translate text into the target language.

    Args:
        text: Source text.
        target_lang: e.g. "English", "Simplified Chinese", "Bahasa Indonesia".
        tone: "natural" (default), "formal", "casual", "marketing".
    """
    p = (
        f"Translate the following into {target_lang}. Tone: {tone}. "
        "Output only the translation, no commentary.\n\n"
        f"---\n{text}\n---"
    )
    return run_agy(p)


@mcp.tool()
def summarize_url(url: str, max_words: int = 200) -> str:
    """Fetch a URL and return a summary.

    Args:
        url: HTTP(S) URL.
        max_words: Word budget for the summary.
    """
    if not re.match(r"^https?://", url):
        raise ValueError(f"not an http(s) URL: {url}")
    p = (
        f"Fetch this URL and summarize it in <= {max_words} words: {url}\n"
        "Lead with the single most important takeaway, then 3-5 bullet supporting points."
    )
    return run_agy(p)


@mcp.tool()
def continue_chat(prompt: str) -> str:
    """Continue the most recent Antigravity conversation (uses `agy -c`).
    Useful for multi-turn refinement without losing context.
    """
    if not shutil.which(AGY_BIN):
        raise AgyError(f"`{AGY_BIN}` not found on PATH.")
    result = subprocess.run(
        _agy_cmd(["-c", "-p", prompt]),
        capture_output=True,
        text=True,
        timeout=DEFAULT_TIMEOUT,
    )
    if result.returncode != 0:
        raise AgyError(f"agy exited {result.returncode}: {result.stderr.strip()}")
    return (result.stdout or "").strip()


def _exit_when_orphaned(poll: float = 5.0) -> None:
    """Daemon watchdog: exit if our parent (the MCP host) dies.

    stdio servers should quit on stdin EOF when the host exits, but while a tool
    call is blocked in a long `agy` subprocess that EOF goes unread, so orphaned
    servers pile up (observed: 20 instances surviving for days). On Unix a dead
    parent reparents us to PID 1; polling getppid() lets us exit reliably no
    matter what the main thread is doing. os._exit because we may be mid-blocked.
    """
    while True:
        if os.getppid() == 1:
            os._exit(0)
        time.sleep(poll)


def main() -> None:
    threading.Thread(target=_exit_when_orphaned, daemon=True).start()
    mcp.run()


if __name__ == "__main__":
    main()
