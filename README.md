# agy-mcp

Use **Google's subscription CLIs** — **Antigravity** (`agy`) and the official **Gemini CLI** (`gemini`) — from anything, billed against your **Google AI Pro / Ultra subscription** (OAuth), not a paid API key.

Three executables, installed together:

- **`agy-mcp`** — an MCP server, for MCP clients (Claude Code, Cursor, Continue, Zed, …)
- **`agq`** — Antigravity CLI wrapper: text / search / **image** / code-review / …
- **`gmq`** — Gemini CLI wrapper: text / web-search

> **Why two backends?** `agy` (Antigravity) is the **only** CLI that can generate **images** on OAuth subscription quota — but its print-mode OAuth path is flaky/slow. The **official Gemini CLI is far more stable for text + web-search grounding** (but cannot generate images on subscription quota). So the recommended split is:
>
> | Task | Use | Why |
> |---|---|---|
> | text / drafting | **`gmq`** (gemini) | more stable, better maintained |
> | web research | **`gmq search`** (gemini) | real google_web_search grounding |
> | **image** | **`agq image`** (agy) | the only subscription image path that exists |

> **Stability note:** prefer the **CLIs (`agq` / `gmq`) over a long-lived MCP server**. Each CLI call spawns a fresh process; a resident MCP server holding `agy` has been observed to wedge (Antigravity 1.0.3 print-mode OAuth bug). The MCP tools still exist for clients that want them.

## Tools (MCP server)

| Tool | Backend | What it does |
|---|---|---|
| `gemini_ask` | gemini | General Q&A / drafting — **preferred for text** |
| `gemini_search` | gemini | Web search w/ google_web_search grounding — **preferred for research** |
| `ask` | agy | General Q&A in any cwd |
| `search` | agy | Web search via Antigravity's Google Search |
| `image` | agy | Generate an image (Imagen / Nano Banana) and save to disk |
| `code_review` | agy | Review a file or directory; prioritized findings |
| `explain` | agy | Explain what code does (file path or snippet) |
| `translate` | agy | Translate text into a target language with chosen tone |
| `summarize_url` | agy | Fetch a URL and summarize it |
| `continue_chat` | agy | Continue the most recent `agy` conversation |

> **Bonus — works around the `agy -p` stdout bug:** in non-TTY contexts `agy -p` sometimes gets the model response but never writes it to stdout. The agy path falls back to reading the answer from agy's own transcript files (`~/.gemini/antigravity-cli/brain/<conv-id>/.system_generated/logs/transcript.jsonl`). The gemini path parses only the first JSON object from `gemini -o json`, so user-configured stdout hooks (e.g. moshi-hook) can't corrupt the answer.

## Prerequisites

1. **For `agq` / agy tools — Antigravity CLI installed and logged in.** Run `agy` once interactively to complete OAuth, then verify: `agy -p "say hi"`.
2. **For `gmq` / gemini tools — Gemini CLI installed and logged in.** `npm i -g @google/gemini-cli`, then run `gemini` once to complete OAuth login.
3. **Python ≥ 3.10.**

You only need the backend(s) for the commands you actually use.

## Install

```bash
pip install --user agy-mcp
# or, from source:
git clone https://github.com/andyleimc-source/agy-mcp
cd agy-mcp && pip install --user .
```

Installs three executables on your PATH: `agy-mcp` (MCP server), `agq` (Antigravity CLI), `gmq` (Gemini CLI).

## `gmq` — text & web research (Gemini, recommended)

```bash
gmq "summarize the latest Go release notes"      # ask (default), prints the answer
gmq ask "write a bash one-liner to dedupe a file"
gmq search "2026 Southeast Asia SaaS partner conferences"   # forces grounding + real URLs
```

## `agq` — text / search / image (Antigravity; use it for images)

```bash
agq image "a red fox in snow, studio lighting" fox.jpg --ar 16:9
agq "summarize these notes: $(cat notes.txt)"
agq search "2026 SaaS partner conferences"       # gmq search is usually steadier
```

Both CLIs exit non-zero on failure with the error on stderr, so they compose in pipelines / `cron`:

```bash
desc=$(gmq "one-line commit message for: $(git diff --staged --stat)")
agq image "$desc" /tmp/banner.jpg --ar 16:9 || echo "image failed" >&2
```

## Configure your MCP client

### Claude Code (global, all projects)

```bash
claude mcp add agy agy-mcp --scope user
```

Or add to `~/.claude.json` under `mcpServers`:

```json
{ "mcpServers": { "agy": { "command": "agy-mcp" } } }
```

### Cursor / Continue / Zed

Use the same `command: agy-mcp` in their respective MCP config file. Inside the client the model can call `agy.gemini_search(...)`, `agy.image(...)`, etc.

## Environment variables

| Var | Default | Purpose |
|---|---|---|
| `AGY_BIN` | `agy` | Path to the Antigravity binary |
| `AGY_TIMEOUT` | `120` | agy per-attempt timeout (s). Worst case = timeout × (AGY_RETRIES+1) |
| `AGY_RETRIES` | `1` | Retries when `agy` hard-times-out (wedge). Fresh process usually recovers |
| `AGY_IMAGE_TIMEOUT` | `120` | agy image per-attempt timeout (s) |
| `GEMINI_BIN` | `gemini` | Path to the Gemini CLI binary |
| `GEMINI_TIMEOUT` | `240` | gemini per-call timeout (s) |

## Notes & gotchas

- **Use the CLIs, not a resident MCP server**, for reliability — see the stability note above.
- **Image is agy-only and JPEG** regardless of extension; prefer `.jpg`. Image gen runs ~30–60s (occasionally slower due to the agy print-mode OAuth bug).
- **Gemini can't make images on subscription quota** — that path requires a paid API key, which defeats the purpose; use `agq image`.
- **Web-search citations** from either backend can occasionally include padded/fake URLs — trust the synthesis, verify the links.
- **`continue_chat` is global state** in Antigravity; concurrent use can collide.
- Unofficial wrapper. Not affiliated with Google.

## License

MIT © Andy Lei
