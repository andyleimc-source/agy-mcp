# agy-mcp

An MCP server that wraps the **Google Antigravity CLI** (`agy`) so you can call Antigravity from any MCP client — Claude Code, Cursor, Continue, Zed, etc.

> **Why this exists:** Antigravity's official SDK only supports API keys (per-token billing). The `agy` CLI uses OAuth and is billed against your **Google AI Pro / Ultra subscription**. This server exposes `agy` over MCP so subscription users can get programmatic access without paying API rates.

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

This installs an `agy-mcp` executable on your PATH.

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
- **Image generation takes ~30s** per call. Parallelize if you need batches.
- **`continue_chat` is global state** — Antigravity tracks the "most recent" conversation across all callers, so concurrent use can collide.
- This is an **unofficial** wrapper. Not affiliated with Google.

## License

MIT © Andy Lei
