"""Shared core for agy-mcp / agq: invoke the Antigravity CLI and recover responses.

All calls shell out to `agy -p`. `agy -p` has a known bug in non-TTY contexts
where it authenticates, talks to the model, gets the answer — and then sometimes
fails to write it to stdout. The response is, however, always persisted to the
CLI's transcript files. So we read stdout first and, when it's empty, recover the
answer from:

    <gemini_dir>/brain/<conv-id>/.system_generated/logs/transcript.jsonl

where the conversation id is mapped from the working directory via
`<gemini_dir>/cache/last_conversations.json`.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Optional

AGY_BIN = os.environ.get("AGY_BIN", "agy")
# A normal ask/search completes in ~30s. agy occasionally wedges — ignoring even
# its own --print-timeout — and a hard 600s budget turned those transient hangs
# into 10-minute blocks. Fail fast instead (6x headroom over a normal call) and
# rely on the auto-retry below: a fresh agy process almost always clears the wedge.
DEFAULT_TIMEOUT = int(os.environ.get("AGY_TIMEOUT", "180"))
# How many times to retry run_agy when the subprocess hard-times-out (the wedge
# case). 1 retry = up to 2 total attempts.
AGY_RETRIES = int(os.environ.get("AGY_RETRIES", "1"))
# Image generation legitimately runs longer than a text answer; give it its own
# (larger) budget so the tighter DEFAULT_TIMEOUT doesn't kill valid gens.
AGY_IMAGE_TIMEOUT = int(os.environ.get("AGY_IMAGE_TIMEOUT", "300"))
# agy is an agentic CLI. In non-TTY print mode it stalls on tool-permission
# prompts (image generation, file writes) with nobody to confirm, burning the
# whole timeout. --dangerously-skip-permissions auto-approves so print mode
# actually completes. Opt out with AGY_SKIP_PERMISSIONS=0.
AGY_SKIP_PERMS = os.environ.get("AGY_SKIP_PERMISSIONS", "1") != "0"


def _agy_cmd(extra_args: list, timeout: Optional[int] = None) -> list:
    """Build the agy argv: skip-permissions + a print-timeout that gives up just
    before our subprocess kill, so agy reports its own timeout instead of being
    hard-killed."""
    cmd = [AGY_BIN]
    if AGY_SKIP_PERMS:
        cmd.append("--dangerously-skip-permissions")
    budget = timeout or DEFAULT_TIMEOUT
    cmd += ["--print-timeout", f"{max(budget - 10, 30)}s"]
    return cmd + extra_args
GEMINI_DIR = Path(
    os.environ.get("AGY_GEMINI_DIR", str(Path.home() / ".gemini" / "antigravity-cli"))
)


class AgyError(RuntimeError):
    """Raised when agy fails or no response can be recovered."""


# --- transcript recovery (workaround for the agy -p non-TTY stdout bug) -------


def _resolve_conv_id(workdir: str) -> Optional[str]:
    """Map a working directory to its Antigravity conversation id."""
    cache = GEMINI_DIR / "cache" / "last_conversations.json"
    try:
        data = json.loads(cache.read_text())
    except (OSError, ValueError):
        return None
    return data.get(str(Path(workdir).resolve())) or data.get(workdir)


def _transcript_path(conv_id: str) -> Path:
    return GEMINI_DIR / "brain" / conv_id / ".system_generated" / "logs" / "transcript.jsonl"


def _read_last_response(path: Path) -> Optional[str]:
    """Return the content of the last PLANNER_RESPONSE entry, if any."""
    try:
        lines = path.read_text().splitlines()
    except OSError:
        return None
    for line in reversed(lines):
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        if obj.get("type") == "PLANNER_RESPONSE":
            content = obj.get("content")
            if isinstance(content, str) and content.strip():
                return content.strip()
    return None


def _newest_transcript(since: float) -> Optional[Path]:
    """Newest transcript.jsonl modified at/after `since` (epoch seconds)."""
    brain = GEMINI_DIR / "brain"
    best: Optional[Path] = None
    best_m = since
    try:
        for d in brain.iterdir():
            t = d / ".system_generated" / "logs" / "transcript.jsonl"
            try:
                m = t.stat().st_mtime
            except OSError:
                continue
            if m >= since and m >= best_m:
                best, best_m = t, m
    except OSError:
        return None
    return best


def _recover_from_transcript(workdir: str, since: float) -> Optional[str]:
    """Recover the model response after an empty-stdout agy -p call.

    Prefer the conversation bound to this cwd (and only if its transcript was
    just touched); fall back to the newest transcript modified since the call
    started. `since` is given ~2s of slack to absorb clock/filesystem skew.
    """
    floor = since - 2
    conv = _resolve_conv_id(workdir)
    if conv:
        p = _transcript_path(conv)
        try:
            if p.stat().st_mtime >= floor:
                recovered = _read_last_response(p)
                if recovered:
                    return recovered
        except OSError:
            pass
    p = _newest_transcript(floor)
    if p:
        return _read_last_response(p)
    return None


# --- public API ---------------------------------------------------------------


def _run_agy_once(prompt: str, workdir: str, timeout: int) -> str:
    """One `agy -p` attempt. Raises subprocess.TimeoutExpired on hard timeout
    (the wedge case, handled by the retry loop in run_agy) or AgyError otherwise."""
    start = time.time()
    proc = subprocess.run(
        _agy_cmd(["-p", prompt], timeout),
        cwd=workdir,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    out = (proc.stdout or "").strip()
    err = (proc.stderr or "").strip()
    if proc.returncode != 0:
        raise AgyError(f"agy exited {proc.returncode}.\nstderr:\n{err}\nstdout:\n{out}")
    if out:
        return out

    recovered = _recover_from_transcript(workdir, start)
    if recovered:
        return recovered
    raise AgyError(
        "agy returned no stdout and no transcript response could be recovered.\n"
        f"stderr:\n{err or '(empty)'}"
    )


def run_agy(prompt: str, cwd: Optional[str] = None, timeout: Optional[int] = None) -> str:
    """Run a single prompt through `agy -p` and return the model's response.

    Reads stdout first; on empty stdout (the known non-TTY bug) recovers the
    answer from agy's transcript files. On a hard timeout (agy wedged and ignored
    its own --print-timeout) the killed process is retried with a fresh agy, which
    almost always clears the wedge. Raises AgyError on failure.
    """
    if not shutil.which(AGY_BIN):
        raise AgyError(
            f"`{AGY_BIN}` not found on PATH. Install Antigravity CLI first "
            "(https://antigravity.google) and ensure `agy` is on PATH."
        )
    workdir = cwd or os.getcwd()
    if not Path(workdir).is_dir():
        raise AgyError(f"cwd does not exist: {workdir}")

    budget = timeout or DEFAULT_TIMEOUT
    last_exc: Optional[subprocess.TimeoutExpired] = None
    for attempt in range(AGY_RETRIES + 1):
        try:
            return _run_agy_once(prompt, workdir, budget)
        except subprocess.TimeoutExpired as exc:
            last_exc = exc  # wedged: kill happened in subprocess.run; retry fresh
    raise AgyError(
        f"agy hard-timed-out after {budget}s on {AGY_RETRIES + 1} attempt(s) — "
        f"the CLI appears wedged (it ignored its own --print-timeout). "
        f"Try again, or run `agy -p '...'` directly to re-check the OAuth login state."
    ) from last_exc


def generate_image(
    prompt: str,
    out_path: str,
    aspect_ratio: str = "1:1",
    cwd: Optional[str] = None,
    timeout: Optional[int] = None,
) -> Path:
    """Generate an image with agy and save it. Returns the resolved file path.

    Note: output is JPEG regardless of extension; prefer `.jpg`.
    """
    target = Path(out_path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    p = (
        f"Generate an image. Description: {prompt}\n"
        f"Aspect ratio: {aspect_ratio}.\n"
        f"Save the result to this ABSOLUTE path: {target}\n"
        f"After saving, verify the file exists and reply with only the path."
    )
    out = run_agy(p, cwd=cwd, timeout=timeout or AGY_IMAGE_TIMEOUT)
    if not target.exists():
        raise AgyError(f"agy completed but no file at {target}.\nOutput:\n{out}")
    return target
