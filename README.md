# mdbrowser

> A text-mode web browser for the terminal. Give it a URL; it fetches the page,
> converts it to clean Markdown, and renders it with numbered, clickable links —
> like `w3m`/`lynx`, but Markdown-formatted and AI-friendly. Optional reader and
> AI-summary modes, and one-key saving to an Obsidian-compatible vault.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](requirements.txt)
[![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Linux-lightgrey)]()

---

## What it does

The command line has no browser. mdbrowser is the missing glue: it turns any URL
into readable Markdown in your terminal, with every link numbered so you can
follow it by typing a number (or clicking, in terminals that support it).

```
            ┌─ tier 1: static  ── Jina Reader (fast, no local browser)
URL ──┤            │ empty / loading? ↓ auto-fallback
            └─ tier 2: rendered ── headless Chromium (Playwright) + html2text
                                     ├ runs JS → handles SPAs
                                     └ ignores bad TLS certs
```

- **Static-first, auto-rendering** — most pages load instantly via a static
  fetch; JS-only SPAs, expired-cert sites, and "loading…" shells automatically
  fall back to a real headless browser. No manual step.
- **Numbered + clickable links** — links render as `⟦n⟧ text`: type `n` to
  follow, or click (OSC 8 hyperlinks). Images show as `🖼 ⟦n⟧` links — no slow,
  ugly pixel art.
- **Text tables** — wide tables render as aligned monospace text (never
  truncated to fit the terminal).
- **Reader mode** — extract just the article body (via trafilatura), stripping
  nav/ads/sidebars. Great for blogs and news.
- **AI summary mode** — append an AI-written summary, using *your own* model
  (any OpenAI-compatible API — not tied to any provider).
- **Save to an Obsidian vault** — press `s` to clip the page as a Markdown note
  with YAML frontmatter, local image copies, and `[[wikilinks]]` between saved
  pages.
- **Persistent history**, **bilingual UI** (English / Chinese), and both an
  **interactive** and a **command-line** mode.

## Install

Requires Python 3.10+.

```bash
git clone https://github.com/kinthaiofficial/mdbrowser.git
cd mdbrowser
./install.sh        # creates .venv, installs deps, downloads Chromium
```

Put it on your PATH (optional):

```bash
sudo ln -sf "$(pwd)/mdbrowser" /usr/local/bin/mdbrowser
```

## Usage

```bash
# Interactive mode — browse with the keyboard
mdbrowser

# Command-line mode — fetch a URL, print it, exit (scriptable / pipeable)
mdbrowser https://en.wikipedia.org/wiki/Markdown
mdbrowser --reader  https://some-blog/post     # just the article body
mdbrowser --summary https://some-blog/post     # article + AI summary
mdbrowser <url> | less                          # auto command-line mode when piped
mdbrowser --help
```

### Interactive keys

| Key | Action | Key | Action |
|-----|--------|-----|--------|
| paste a URL + `↵` | open it | `<number>` | follow link `⟦n⟧` (also clickable) |
| `↑` / `↓` | back / forward through history | `↵` | open the highlighted page |
| `r` | reload | `Shift+Tab` | cycle mode: browse → reader → summary |
| `s` | save to vault | `set` | settings (`set language Chinese`) |
| `/clear-history` | wipe history | `h` / `q` | help / quit |

The bottom toolbar always shows the current mode and the key hints. `Shift+Tab`
flips the mode instantly; press `r` (or `↵`) to apply it to the current page.

## AI summary mode

Summary mode appends an AI-written summary using **your own LLM** via any
OpenAI-compatible `/chat/completions` endpoint. Configure with three env vars:

```bash
export MDBROWSER_LLM_KEY=your-api-key
export MDBROWSER_LLM_MODEL=deepseek-chat
export MDBROWSER_LLM_BASE=https://api.deepseek.com
```

The base URL is stable per provider; model ids change — confirm the current id
in your provider's console. A few common providers:

| Provider | `MDBROWSER_LLM_BASE` | `MODEL` (example) |
|---|---|---|
| DeepSeek | `https://api.deepseek.com` | `deepseek-chat` |
| MiniMax | `https://api.minimaxi.com/v1` | `MiniMax-M2.5` |
| Moonshot / Kimi | `https://api.moonshot.cn/v1` | `kimi-k2` |
| Qwen (Aliyun) | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-plus` |
| Zhipu GLM | `https://open.bigmodel.cn/api/paas/v4` | `glm-4.6` |
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-mini` |
| Google Gemini | `https://generativelanguage.googleapis.com/v1beta/openai` | `gemini-2.5-flash` |
| xAI Grok | `https://api.x.ai/v1` | `grok-4` |
| OpenRouter (incl. Claude) | `https://openrouter.ai/api/v1` | `anthropic/claude-...` |
| Ollama (local) | `http://localhost:11434/v1` | `qwen2.5` |

If summary mode is unconfigured, it prints this table in-app so you can copy a
setup block. Reasoning models that emit `<think>…</think>` are handled (the tag
is stripped from the displayed summary).

## Saving (Obsidian vault)

Press `s` to save the current page. Files land in your vault (default
`./mdbrowser-vault`, override with `--vault <dir>` or `MDBROWSER_VAULT`):

```
<vault>/
  <Page Title>.md          # article + YAML frontmatter (title, url, fetched, tags)
  attachments/<hash>.png   # original image files
  .mdbrowser-index.json    # url ↔ note index (dedupe + wikilinks)
```

Open the vault directory in [Obsidian](https://obsidian.md) to read, search, and
graph your clippings. Links to pages you've already saved become `[[wikilinks]]`.

## Settings & language

- The UI is **English by default**; `set language Chinese` switches **both the UI
  and the AI summary** to Chinese (`set language English` to switch back).
- Settings (`language`, `mode`) persist in `~/.mdbrowser/settings.json`; history
  in `~/.mdbrowser/history`.

## Configuration reference

| Env var | Purpose | Default |
|---|---|---|
| `MDBROWSER_LLM_KEY` / `MDBROWSER_LLM_MODEL` / `MDBROWSER_LLM_BASE` | AI summary provider | — / — / `https://api.openai.com/v1` |
| `MDBROWSER_VAULT` | save directory for `s` | `./mdbrowser-vault` |
| `MDBROWSER_HISTORY` | history file | `~/.mdbrowser/history` |
| `MDBROWSER_SETTINGS` | settings file | `~/.mdbrowser/settings.json` |

## How it works

1. **Tier 1 (static):** fetches via [Jina Reader](https://jina.ai/reader) with a
   links-summary so most pages — including many SPAs — return clean Markdown with
   their links, no local browser needed.
2. **Tier 2 (rendered):** when the body is empty or still shows a loading
   placeholder, it renders the page in headless Chromium (Playwright, ignoring
   TLS errors) and converts the result with html2text.
3. **Reader / summary** render the page then extract the article with trafilatura
   (summary additionally calls your LLM).

## License

MIT © 2026 Freddy Chu. See [LICENSE](LICENSE).

Contributor: Freddy Chu <freddychu@gmail.com>
