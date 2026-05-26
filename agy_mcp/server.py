"""agy-mcp: MCP server wrapping Google Antigravity CLI (`agy`).

Exposes Antigravity capabilities (chat, search, image gen, code review, etc.)
to any MCP client. All calls go through the local `agy` CLI, which uses your
OAuth login — so usage is billed against your Google AI subscription, not the
Gemini API.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("agy")

AGY_BIN = os.environ.get("AGY_BIN", "agy")
DEFAULT_TIMEOUT = int(os.environ.get("AGY_TIMEOUT", "600"))


def _run_agy(prompt: str, cwd: Optional[str] = None, timeout: Optional[int] = None) -> str:
    if not shutil.which(AGY_BIN):
        raise RuntimeError(
            f"`{AGY_BIN}` not found on PATH. Install Antigravity CLI first "
            "(https://antigravity.google) and ensure `agy` is on PATH."
        )
    workdir = cwd or os.getcwd()
    if not Path(workdir).is_dir():
        raise ValueError(f"cwd does not exist: {workdir}")

    result = subprocess.run(
        [AGY_BIN, "-p", prompt],
        cwd=workdir,
        capture_output=True,
        text=True,
        timeout=timeout or DEFAULT_TIMEOUT,
    )
    out = (result.stdout or "").strip()
    err = (result.stderr or "").strip()
    if result.returncode != 0:
        raise RuntimeError(f"agy exited {result.returncode}.\nstderr:\n{err}\nstdout:\n{out}")
    return out or err


@mcp.tool()
def ask(prompt: str, cwd: Optional[str] = None) -> str:
    """General-purpose Antigravity query. Use for analysis, Q&A, drafting,
    code generation, anything that doesn't fit a more specific tool.

    Args:
        prompt: Full natural-language instruction.
        cwd: Optional working directory (defaults to current). The agent can
             read/write files relative to this path.
    """
    return _run_agy(prompt, cwd=cwd)


@mcp.tool()
def search(query: str) -> str:
    """Web search via Antigravity's built-in Google Search tool. Returns a
    synthesized answer with citations. Best for fresh/realtime info.
    """
    p = (
        f"Use web search to answer: {query}\n\n"
        "Return a concise synthesis followed by a numbered list of source URLs."
    )
    return _run_agy(p)


@mcp.tool()
def image(prompt: str, out_path: str, aspect_ratio: str = "1:1") -> str:
    """Generate an image with Antigravity's image tool and save it locally.

    Note: output is JPEG regardless of extension; prefer `.jpg`.

    Args:
        prompt: Image description.
        out_path: Absolute path to save the file (e.g. /tmp/hero.jpg).
        aspect_ratio: One of "1:1", "16:9", "9:16", "4:3", "3:4".
    """
    target = Path(out_path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    p = (
        f"Generate an image. Description: {prompt}\n"
        f"Aspect ratio: {aspect_ratio}.\n"
        f"Save the result to this ABSOLUTE path: {target}\n"
        f"After saving, verify the file exists and reply with only the path."
    )
    out = _run_agy(p)
    if not target.exists():
        raise RuntimeError(f"agy completed but no file at {target}.\nOutput:\n{out}")
    size = target.stat().st_size
    return f"Saved: {target} ({size} bytes)"


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
    return _run_agy(p, cwd=str(path.parent if path.is_file() else path))


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
        return _run_agy(p, cwd=str(candidate.parent))
    p = f"Explain what this code does, {detail}:\n\n```\n{target}\n```"
    return _run_agy(p)


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
    return _run_agy(p)


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
    return _run_agy(p)


@mcp.tool()
def continue_chat(prompt: str) -> str:
    """Continue the most recent Antigravity conversation (uses `agy -c`).
    Useful for multi-turn refinement without losing context.
    """
    if not shutil.which(AGY_BIN):
        raise RuntimeError(f"`{AGY_BIN}` not found on PATH.")
    result = subprocess.run(
        [AGY_BIN, "-c", "-p", prompt],
        capture_output=True,
        text=True,
        timeout=DEFAULT_TIMEOUT,
    )
    if result.returncode != 0:
        raise RuntimeError(f"agy exited {result.returncode}: {result.stderr.strip()}")
    return (result.stdout or "").strip()


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
