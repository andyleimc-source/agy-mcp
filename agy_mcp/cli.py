"""agq — call Antigravity (agy) from any terminal or script.

Usage:
  agq "your prompt"                  # ask, prints the answer
  agq ask "your prompt" [--cwd DIR]
  agq image "a red fox in snow" fox.jpg [--ar 16:9]
  agq search "latest news on X"

Billed against your Google AI subscription via agy's OAuth login (not the
Gemini API). Reads agy's response from stdout, falling back to its transcript
files when stdout is empty (the known agy -p non-TTY bug).
"""

from __future__ import annotations

import argparse
import sys
from typing import Optional, Sequence

from . import core

_SUBCMDS = {"ask", "image", "search"}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agq", description="Call Antigravity (agy) from the shell."
    )
    sub = parser.add_subparsers(dest="cmd")

    p_ask = sub.add_parser("ask", help="Run a prompt and print the answer (default).")
    p_ask.add_argument("prompt")
    p_ask.add_argument("--cwd", help="Working directory agy runs in.")

    p_img = sub.add_parser("image", help="Generate an image to a file.")
    p_img.add_argument("prompt")
    p_img.add_argument("out", help="Output path (JPEG; prefer .jpg).")
    p_img.add_argument(
        "--ar", default="1:1", help="Aspect ratio: 1:1, 16:9, 9:16, 4:3, 3:4."
    )

    p_search = sub.add_parser("search", help="Web search, returns answer + sources.")
    p_search.add_argument("query")

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    # Bare `agq "prompt"` is shorthand for `agq ask "prompt"`.
    if argv and argv[0] not in _SUBCMDS and argv[0] not in {"-h", "--help"}:
        argv = ["ask", *argv]

    args = _build_parser().parse_args(argv)
    try:
        if args.cmd == "image":
            print(core.generate_image(args.prompt, args.out, aspect_ratio=args.ar))
        elif args.cmd == "search":
            print(
                core.run_agy(
                    f"Use web search to answer: {args.query}\n"
                    "Return a concise synthesis followed by a numbered list of source URLs."
                )
            )
        elif args.cmd == "ask":
            print(core.run_agy(args.prompt, cwd=args.cwd))
        else:
            _build_parser().print_help()
            return 2
    except core.AgyError as e:
        print(f"agq: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
