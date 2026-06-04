"""gmq — call the official Gemini CLI from any terminal or script.

Uses your personal Google OAuth login (subscription/free quota, NOT an API key).
Per call it runs a fresh `gemini` process (no daemon to wedge) and prints only
the model text, stripping any stdout hook noise.

Usage:
  gmq "your prompt"             # ask, prints the answer
  gmq ask "your prompt"
  gmq search "what's new in X"  # forces google_web_search grounding + real URLs

Image generation is NOT here — Gemini CLI can't generate images on OAuth
subscription quota. Use `agq image ...` (Antigravity) for that.
"""
from __future__ import annotations

import sys
from typing import Optional, Sequence

from . import gemini


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in {"-h", "--help"}:
        print(__doc__)
        return 0 if args else 2

    try:
        if args[0] == "search":
            if len(args) < 2:
                print("gmq: search needs a query", file=sys.stderr)
                return 2
            print(gemini.search_gemini(" ".join(args[1:])))
        else:
            if args[0] == "ask":
                args = args[1:]
            if not args:
                print("gmq: ask needs a prompt", file=sys.stderr)
                return 2
            print(gemini.run_gemini(" ".join(args)))
    except gemini.GeminiError as e:
        print(f"gmq: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
