"""Gemini backend: shell out to the official Gemini CLI (`gemini`).

Companion to `core.py` (which wraps Antigravity / `agy`). Both bill against your
Google AI subscription via OAuth login, NOT a paid API key.

Why a second backend: `agy` is the only CLI that can generate images on OAuth
subscription quota, but its print-mode OAuth path is flaky. The official Gemini
CLI is far more stable for text + web-search grounding (but cannot generate
images on subscription quota). So: text/search -> gemini, image -> agy.

`gemini -o json` prints a JSON object, but user-configured stdout hooks (e.g.
moshi-hook SessionEnd lines) get appended after it. We parse only the FIRST JSON
object via raw_decode so that noise can't corrupt the answer.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from typing import Optional

GEMINI_BIN = os.environ.get("GEMINI_BIN", "gemini")
GEMINI_TIMEOUT = int(os.environ.get("GEMINI_TIMEOUT", "240"))

# Forces the google_web_search tool and discourages the model's habit of padding
# answers with plausible-but-fake "模拟参考地址" URLs.
SEARCH_WRAP = (
    "Use the google_web_search tool to answer with current, real information. "
    "Do NOT invent or use placeholder/simulated URLs — cite only real URLs the "
    "search returned. Give a concise synthesis, then a numbered list of source URLs."
    "\n\nQuery: {q}"
)


class GeminiError(RuntimeError):
    """Raised when the gemini CLI fails or returns no usable response."""


def run_gemini(prompt: str, cwd: Optional[str] = None, timeout: Optional[int] = None) -> str:
    """Run a prompt through `gemini -o json -p` and return the model's text.

    Parses only the first JSON object so trailing stdout hook noise is ignored.
    Raises GeminiError on missing binary, timeout, or empty response.
    """
    if not shutil.which(GEMINI_BIN):
        raise GeminiError(
            f"`{GEMINI_BIN}` not found on PATH. Install the Gemini CLI: "
            "`npm i -g @google/gemini-cli`, then `gemini` once to log in (OAuth)."
        )
    try:
        proc = subprocess.run(
            [GEMINI_BIN, "-o", "json", "-p", prompt],
            cwd=cwd or os.getcwd(),
            capture_output=True,
            text=True,
            timeout=timeout or GEMINI_TIMEOUT,
        )
    except subprocess.TimeoutExpired as exc:
        raise GeminiError(
            f"gemini timed out after {timeout or GEMINI_TIMEOUT}s."
        ) from exc

    out = (proc.stdout or "").lstrip()
    try:
        obj, _ = json.JSONDecoder().raw_decode(out)
    except ValueError as exc:
        err = (proc.stderr or "").strip()
        raise GeminiError(
            f"gemini produced no parseable JSON (rc={proc.returncode}).\n"
            f"stderr:\n{err or '(empty)'}\nstdout:\n{out[:500] or '(empty)'}"
        ) from exc

    resp = (obj.get("response") or "").strip()
    if resp:
        return resp
    err = (obj.get("error") or proc.stderr or "(no response)")
    raise GeminiError(f"gemini returned no response: {str(err).strip()}")


def search_gemini(query: str, timeout: Optional[int] = None) -> str:
    """Web search with grounding: wraps the query to force google_web_search."""
    return run_gemini(SEARCH_WRAP.format(q=query), timeout=timeout)
