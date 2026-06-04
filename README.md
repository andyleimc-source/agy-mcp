# agy-mcp

Call the **Google Antigravity CLI** (`agy`) from anything:

- **`agy-mcp`** — an MCP server, for MCP clients (Claude Code, Cursor, Continue, Zed, …)
- **`agq`** — a plain CLI, for any terminal / shell script / cron / other code

> **Why this exists:** Antigravity's official SDK only supports API keys (per-token billing). The `agy` CLI uses OAuth and is billed against your **Google AI Pro / Ultra subscription**. This package exposes `agy` programmatically so subscription users get access without paying API rates.
>
> **Bonus — works around the `agy -p` stdout bug:** in non-TTY contexts `agy -p` sometimes gets the model response but never writes it to stdout. Both `agy-mcp` and `agq` fall back to reading the answer from agy's own transcript files (`~/.gemini/antigravity-cli/brain/<conv-id>/.system_generated/logs/transcript.jsonl`), so you always get the response.

## Features (8 tools)

| Tool | What it does |
|---|---|
| `ask` | General Q&A / drafting / code gen in any cwd |
| `search` | Web search via Antigravity's built-in Google Search |
| `image` | Generate an image (Imagen / Nano Banana) and save to disk |
| `code_review` | Review a file or directory; prioritized findings |
| `explain` | Explain what code does (file path or snippet) |
| `translate` | Translate text into a target language with chosen tone |
| `summarize_url` | Fetch a URL and summarize it |
| `continue_chat` | Continue the most recent `agy` conversation |

## Prerequisites

1. **Antigravity CLI installed and logged in.** Run `agy` once interactively to complete OAuth login. Verify with:
   ```bash
   agy -p "say hi"
   ```
2. **Python ≥ 3.10**.

## Install

```bash
pip install --user agy-mcp
# or, from source:
git clone https://github.com/andyleimc-source/agy-mcp
cd agy-mcp && pip install --user .
```

This installs two executables on your PATH: `agy-mcp` (the MCP server) and `agq` (the CLI).

## `agq` — call agy from the terminal or any script

```bash
agq "summarize the latest Go release notes"      # ask (default), prints the answer
agq ask "write a bash one-liner to dedupe a file"
agq image "a red fox in snow, studio lighting" fox.jpg --ar 16:9
agq search "2026 Southeast Asia SaaS partner conferences"
```

Exit code is non-zero on failure and the error goes to stderr, so it composes in pipelines and `cron`:

```bash
desc=$(agq "one-line commit message for these changes: $(git diff --staged --stat)")
agq image "$desc" /tmp/banner.jpg --ar 16:9 || echo "image failed" >&2
```

## Configure your MCP client

### Claude Code (global, all projects)

Add to `~/.claude.json` under `mcpServers`:

```json
{
  "mcpServers": {
    "agy": {
      "command": "agy-mcp"
    }
  }
}
```

Or with the CLI:

```bash
claude mcp add agy agy-mcp --scope user
```

### Cursor / Continue / Zed

Use the same `command: agy-mcp` in their respective MCP config file.

## Usage examples

Inside any MCP-aware client, the model can now call:

```
agy.search(query="2026 Southeast Asia SaaS partner conferences")
agy.image(prompt="A red apple on white background, studio lighting", out_path="/tmp/apple.jpg")
agy.code_review(target_path="./src/auth.ts", focus="security")
agy.translate(text="Hello partner", target_lang="Bahasa Indonesia", tone="formal")
agy.summarize_url(url="https://example.com/post", max_words=150)
```

## Environment variables

| Var | Default | Purpose |
|---|---|---|
| `AGY_BIN` | `agy` | Override path to the Antigravity binary |
| `AGY_TIMEOUT` | `600` | Per-call timeout in seconds |

## Notes & gotchas

- **Image output is JPEG** regardless of the extension you pass. Prefer `.jpg`.
- **Every call cold-starts `agy`** (~6s of OAuth + bootstrap before the model even runs), so expect ~9–30s/call. This is inherent to `agy` being re-spawned per call; there is no resident-process mode.
- **Image generation takes ~30s** per call. Parallelize if you need batches.
- **`continue_chat` is global state** — Antigravity tracks the "most recent" conversation across all callers, so concurrent use can collide.
- This is an **unofficial** wrapper. Not affiliated with Google.

## License

MIT © Andy Lei
