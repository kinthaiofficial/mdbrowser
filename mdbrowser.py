#!/usr/bin/env python3
"""
mdbrowser — a text-mode "browser" for the terminal.

Fetches any URL, converts it to clean Markdown, renders it with rich, and
numbers every hyperlink so you can follow links by typing a number — just like
w3m/lynx, but with Markdown formatting.

Two-tier fetching:
  1. static  — Jina AI Reader (fast, no local browser). Works for most pages.
  2. rendered — local headless Chromium (Playwright) + html2text. Falls back here
                when static returns nothing: JS-only SPAs, and pages whose TLS
                cert is expired/invalid (a real browser context can ignore that).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import ssl
import sys
import urllib.parse
import urllib.request
from datetime import datetime

import html2text
from rich.cells import cell_len
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text

console = Console()

JINA_PREFIX = "https://r.jina.ai/"
USER_AGENT = "mdbrowser/0.1 (+https://example.local)"


# --- i18n: bilingual UI (English default, Chinese via `set language Chinese`) ---
def ui_lang(language: str) -> str:
    """Map the free-form summary language to a UI code: 'zh' for Chinese, else 'en'."""
    s = (language or "").lower()
    return "zh" if ("chinese" in s or "中文" in language or "汉语" in language) else "en"


STRINGS = {
    "banner": {
        "en": "[bold]mdbrowser[/] — terminal markdown browser, Obsidian-compatible saves  ·  type [cyan]h[/] for help  ·  [dim]vault: {vault}[/]",
        "zh": "[bold]mdbrowser[/] — 终端 Markdown 浏览器，保存格式兼容 Obsidian  ·  按 [cyan]h[/] 看帮助  ·  [dim]vault: {vault}[/]",
    },
    "restored": {
        "en": "[dim]restored {n} history entries — press ↑ to browse, or paste a URL.[/]",
        "zh": "[dim]已恢复 {n} 条历史 —— 按 ↑ 浏览，或粘贴一个网址。[/]",
    },
    "bye": {"en": "[dim]bye[/]", "zh": "[dim]再见[/]"},
    "settings_header": {"en": "[bold]settings[/]", "zh": "[bold]设置[/]"},
    "settings_hint": {
        "en": "[dim]change with:  set language <name>   (e.g. set language Chinese)[/]",
        "zh": "[dim]修改：  set language <名称>   （如 set language Chinese）[/]",
    },
    "settings_usage": {"en": "[dim]usage:  set   |   set language <name>[/]",
                       "zh": "[dim]用法：  set   |   set language <名称>[/]"},
    "lang_set": {"en": "[dim]language = {value}[/]", "zh": "[dim]language = {value}[/]"},
    "nothing_to_save": {"en": "[yellow]nothing to save[/]", "zh": "[yellow]没有可保存的页面[/]"},
    "saved": {"en": "[green]✓ saved[/] {path}  [dim]({n} images)[/]",
              "zh": "[green]✓ 已保存[/] {path}  [dim]（{n} 张图片）[/]"},
    "save_failed": {"en": "[red]✗ save failed:[/] {exc}", "zh": "[red]✗ 保存失败：[/] {exc}"},
    "history_cleared": {"en": "[dim]history cleared ({n} entries removed)[/]",
                        "zh": "[dim]历史已清空（移除 {n} 条）[/]"},
    "unknown_cmd": {"en": "[dim]unknown command — type h for help[/]",
                    "zh": "[dim]未知命令 —— 按 h 看帮助[/]"},
    "no_link": {"en": "[yellow]no link {n} (have 1–{m})[/]", "zh": "[yellow]没有链接 {n}（共 1–{m}）[/]"},
    "oldest_page": {"en": "[yellow]already at oldest page[/]", "zh": "[yellow]已经是最早的页面[/]"},
    "no_forward": {"en": "[yellow]no forward page[/]", "zh": "[yellow]没有可前进的页面[/]"},
    "reader_failed": {"en": "[red]✗ reader failed:[/] {exc}", "zh": "[red]✗ 正文提取失败：[/] {exc}"},
    "render_failed": {"en": "[red]✗ render failed:[/] {exc}", "zh": "[red]✗ 渲染失败：[/] {exc}"},
    "st_reading": {"en": "[dim]reading article[/] {url}", "zh": "[dim]提取正文中[/] {url}"},
    "st_static": {"en": "[dim]fetching (static)[/] {url}", "zh": "[dim]抓取中（静态）[/] {url}"},
    "st_retry": {"en": "[dim]empty — retrying without cache[/] {url}", "zh": "[dim]为空 —— 不用缓存重试[/] {url}"},
    "st_render": {"en": "[dim]rendering with headless browser[/] {url}", "zh": "[dim]无头浏览器渲染中[/] {url}"},
    "st_summary": {"en": "[dim]generating AI summary…[/]", "zh": "[dim]正在生成 AI 摘要…[/]"},
    "ai_heading": {"en": "AI Summary", "zh": "AI 摘要"},
    "summary_failed": {"en": "_(summary failed: {exc})_", "zh": "_(摘要生成失败：{exc})_"},
    "empty_title": {"en": "[red]empty page[/] · {url}", "zh": "[red]空页面[/] · {url}"},
    "empty_got_title": {"en": "got the page title ({title!r}) but no body content.\n\n",
                        "zh": "拿到了标题（{title!r}）但没有正文内容。\n\n"},
    "empty_no_content": {"en": "no content came back.\n\n", "zh": "没有返回任何内容。\n\n"},
    "empty_both": {"en": "static fetch and headless render both came back empty.\n",
                   "zh": "静态抓取和无头渲染都返回为空。\n"},
    "empty_causes": {"en": "likely causes:\n", "zh": "可能的原因：\n"},
    "empty_list": {
        "en": "  • the host is unreachable / DNS fails\n"
              "  • content loads only after login or interaction\n"
              "  • the site actively blocks automated browsers\n\n",
        "zh": "  • 主机不可达 / DNS 解析失败\n"
              "  • 内容需登录或交互后才加载\n"
              "  • 站点主动屏蔽自动化浏览器\n\n",
    },
    "empty_try": {"en": "try: ", "zh": "建议： "},
    "empty_try_rest": {"en": "open the URL in a normal browser to check it loads at all.",
                       "zh": "用普通浏览器打开这个网址，确认它能加载。"},
    "mode_browse": {"en": "browse mode", "zh": "浏览模式"},
    "mode_reader": {"en": "reader mode on", "zh": "阅读模式"},
    "mode_summary": {"en": "summary mode on (AI summary)", "zh": "摘要模式（AI 摘要）"},
    "mode_cycle": {"en": "(shift+tab to cycle)", "zh": "（shift+tab 切换）"},
    "mode_apply": {"en": "(shift+tab to cycle · press ↵ to apply to this page)",
                   "zh": "（shift+tab 切换 · 按 ↵ 应用到当前页）"},
    "keys": {
        "en": " paste url + ↵ = open · num → link · ↑↓ history (back/fwd) + ↵ go · r reload · s save · set · h help · q quit ",
        "zh": " 粘贴网址 + ↵ 打开 · 数字 → 链接 · ↑↓ 历史(前进/后退) + ↵ 进入 · r 重载 · s 保存 · set 设置 · h 帮助 · q 退出 ",
    },
    "inline_data_image": {"en": "{tag}{label} (inline data image)", "zh": "{tag}{label}（内嵌图片数据）"},
    "hist_line": {"en": " {mark} history {i}/{m}: {url}  (↵ to go) ",
                  "zh": " {mark} 历史 {i}/{m}: {url}  （↵ 进入） "},
}


def tr(lang: str, key: str, **kw) -> str:
    template = STRINGS[key].get(lang) or STRINGS[key]["en"]
    return template.format(**kw) if kw else template

# Matches links [text](url) AND images ![alt](url) in one pass — group 1 is the
# leading "!" (empty for links), so we can number both in document order.
COMBINED_RE = re.compile(r"(!?)\[([^\]]*)\]\((<[^>]+>|[^)\s]+)(?:\s+\"[^\"]*\")?\)")


def fetch_markdown(url: str, *, no_cache: bool = False) -> str:
    """Fetch a URL and return Markdown. Uses Jina Reader for HTML→MD."""
    target = url if url.endswith(".md") else JINA_PREFIX + url
    headers = {
        "User-Agent": USER_AGENT,
        # Append a "Links/Buttons:" section listing every link on the page. Many
        # SPAs render their nav/links as JS buttons that don't survive as inline
        # markdown links — this recovers them so navigation works.
        "x-with-links-summary": "true",
    }
    if no_cache:
        # Bypass Jina's cached snapshot and force a fresh render.
        headers["x-no-cache"] = "true"
    req = urllib.request.Request(target, headers=headers)
    with urllib.request.urlopen(req, timeout=45) as resp:
        return resp.read().decode("utf-8", errors="replace")


def body_text(md: str) -> str:
    """Return just the article body Jina produced, after its metadata header."""
    marker = "Markdown Content:"
    return md.split(marker, 1)[1].strip() if marker in md else md.strip()


# Jina appends a "Links/Buttons:" footer even when the page body is empty (common
# on cached SPA snapshots). Strip it so emptiness checks see the real content.
_LINKS_FOOTER_RE = re.compile(r"\n*Links/Buttons:\s*\n.*$", re.DOTALL)


def main_content(md: str) -> str:
    """body_text minus Jina's trailing Links/Buttons summary — the real page text."""
    return _LINKS_FOOTER_RE.sub("", body_text(md)).strip()


LOADING_RE = re.compile(r"(加载中|正在加载|加载.{0,6}数据|\bloading\b|请稍候|please wait)", re.I)


def looks_unrendered(body: str) -> bool:
    """A short body still showing a loading placeholder = JS hasn't populated it."""
    return len(body) < 600 and LOADING_RE.search(body) is not None


# A pasted URL (full http(s) link, or a bare domain like example.com/path).
URL_RE = re.compile(r"^(https?://\S+|[\w-]+(\.[\w-]+)+(/\S*)?)$")


def looks_like_url(s: str) -> bool:
    return " " not in s and URL_RE.match(s) is not None


def fetch_rendered_html(url: str) -> str:
    """Render a URL's JS in a real headless browser and return the final HTML.

    Handles SPAs (executes their JS) and pages with expired/invalid TLS certs
    (ignore_https_errors lets the browser load them anyway).
    """
    from playwright.sync_api import sync_playwright  # lazy: heavy, only when needed

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(ignore_https_errors=True, user_agent=USER_AGENT)
        page = ctx.new_page()
        try:
            page.goto(url, wait_until="networkidle", timeout=30000)
        except Exception:  # noqa: BLE001 - networkidle can time out on chatty pages
            pass  # take whatever has rendered so far
        html = page.content()
        browser.close()
    return html


def render_markdown(url: str) -> str:
    """Tier-2 backend: render JS, then convert the whole page to MD (keeps all links)."""
    h = html2text.HTML2Text()
    h.ignore_images = False  # keep ![alt](src) so each image becomes a link line
    h.body_width = 0  # don't hard-wrap; let the terminal/rich wrap
    return h.handle(fetch_rendered_html(url))


def reader_markdown(url: str) -> str:
    """Reader mode: render JS, then extract just the article body with trafilatura
    (strips nav/ads/sidebars). Falls back to the static fetch if extraction is thin."""
    import trafilatura  # lazy: only when reader mode is used

    html = fetch_rendered_html(url)
    md = trafilatura.extract(html, output_format="markdown",
                             include_links=True, include_images=True, url=url) or ""
    if len(md.strip()) < 200:  # extraction came up thin → fall back to Jina
        md = body_text(fetch_markdown(url))
    return md


# --- AI summary (provider-neutral: any OpenAI-compatible chat API) ----------
# Summary mode appends an AI-written summary, using the user's OWN model — set via
# env so it works with OpenAI, DeepSeek, Moonshot, a local server, etc. Not tied
# to any one provider.
LLM_BASE = os.environ.get("MDBROWSER_LLM_BASE", "https://api.openai.com/v1").rstrip("/")
LLM_KEY = os.environ.get("MDBROWSER_LLM_KEY", "")
LLM_MODEL = os.environ.get("MDBROWSER_LLM_MODEL", "")
_PROVIDER_TABLE = (
    "\n\n**Cloud · Chinese**\n\n"
    "| Provider | BASE | MODEL |\n"
    "|---|---|---|\n"
    "| DeepSeek | https://api.deepseek.com | deepseek-chat |\n"
    "| MiniMax 海螺 | https://api.minimaxi.com/v1 | MiniMax-M2.5 |\n"
    "| Moonshot/Kimi | https://api.moonshot.cn/v1 | kimi-k2 |\n"
    "| Qwen 通义千问 | https://dashscope.aliyuncs.com/compatible-mode/v1 | qwen-plus |\n"
    "| 智谱 GLM | https://open.bigmodel.cn/api/paas/v4 | glm-4.6 |\n"
    "| 豆包 火山方舟 | https://ark.cn-beijing.volces.com/api/v3 | doubao-... |\n"
    "| 百度文心 千帆 | https://qianfan.baidubce.com/v2 | ernie-4.5-... |\n"
    "| 硅基流动 SiliconFlow | https://api.siliconflow.cn/v1 | deepseek-ai/DeepSeek-V3 |\n"
    "\n**Cloud · Global**\n\n"
    "| Provider | BASE | MODEL |\n"
    "|---|---|---|\n"
    "| OpenAI | https://api.openai.com/v1 | gpt-4o-mini |\n"
    "| Google Gemini | https://generativelanguage.googleapis.com/v1beta/openai | gemini-2.5-flash |\n"
    "| xAI Grok | https://api.x.ai/v1 | grok-4 |\n"
    "| Mistral | https://api.mistral.ai/v1 | mistral-large-latest |\n"
    "| Groq | https://api.groq.com/openai/v1 | llama-3.3-70b-versatile |\n"
    "| MiniMax intl | https://api.minimax.io/v1 | MiniMax-M2.5 |\n"
    "| OpenRouter (含 Claude) | https://openrouter.ai/api/v1 | anthropic/claude-... |\n"
    "\n**Local**\n\n"
    "| Tool | BASE | MODEL |\n"
    "|---|---|---|\n"
    "| Ollama | http://localhost:11434/v1 | qwen2.5 |\n"
    "| LM Studio | http://localhost:1234/v1 | (loaded model name) |\n"
    "| vLLM | http://localhost:8000/v1 | (served model name) |\n"
)
_SETUP_BLOCK = (
    "\n```bash\n"
    "export MDBROWSER_LLM_KEY=your-api-key\n"
    "export MDBROWSER_LLM_MODEL=deepseek-chat\n"
    "export MDBROWSER_LLM_BASE=https://api.deepseek.com\n"
    "```"
)
LLM_SETUP_HELP = {
    "en": "**Summary mode is not configured.** It uses your own LLM — any OpenAI-compatible API. "
          "Pick a provider, then copy the block below into your shell (e.g. ~/.bashrc), fill in your "
          "key (model names are examples — confirm the current id in your provider's console):"
          + _PROVIDER_TABLE + _SETUP_BLOCK,
    "zh": "**摘要模式尚未配置。** 它用你自己的大模型（任意 OpenAI 兼容接口）。挑一个服务商，把下面的代码块复制到"
          "你的 shell（如 ~/.bashrc），填上 key（模型名仅为示例，以服务商控制台当前的为准）："
          + _PROVIDER_TABLE + _SETUP_BLOCK,
}


def summarize(text: str, language: str = "English") -> str:
    """Summarize article text via an OpenAI-compatible /chat/completions endpoint."""
    payload = json.dumps({
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": f"You are a concise summarizer. Output 3–6 "
             f"bullet points capturing the article's core. Respond in {language}."},
            {"role": "user", "content": "Summarize the core content of this article:\n\n" + text[:12000]},
        ],
        "temperature": 0.3,
    }).encode("utf-8")
    req = urllib.request.Request(
        LLM_BASE + "/chat/completions", data=payload,
        headers={"Authorization": f"Bearer {LLM_KEY}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.load(resp)
    content = data["choices"][0]["message"]["content"]
    # Strip <think>…</think> reasoning some models (MiniMax M2.5, DeepSeek-R1, QwQ…)
    # inline into the content, so the displayed summary is just the answer.
    content = re.sub(r"(?is)<think>.*?</think>\s*", "", content)
    return content.strip()


def ai_summary_section(text: str, language: str = "English") -> str:
    """Return the body for the AI Summary section — setup help / summary / error."""
    lang = ui_lang(language)
    if not (LLM_KEY and LLM_MODEL):
        return LLM_SETUP_HELP.get(lang, LLM_SETUP_HELP["en"])
    try:
        with console.status(tr(lang, "st_summary")):
            return summarize(text, language)
    except Exception as exc:  # noqa: BLE001 - surface the failure inline
        return tr(lang, "summary_failed", exc=exc)


def extract_links(md: str, base_url: str):
    """Number links and images in document order; return (new_md, links).

    Links become '⟦n⟧ [text](url)': the ⟦n⟧ lets you follow by number, and the
    intact markdown link is rendered by rich as a clickable terminal hyperlink
    (URL embedded — click to open, or copy the link). Images keep their
    ![alt](src) syntax (rendered as a 🖼 link line) but their src is registered in
    the links list too, so each image gets a followable number. Deduped by URL.
    """
    links: list[str] = []
    seen: dict[str, int] = {}

    def number(href: str) -> int:
        n = seen.get(href)
        if n is None:
            links.append(href)
            n = seen[href] = len(links)
        return n

    def repl(m: re.Match) -> str:
        is_image, text = m.group(1), m.group(2)
        href = urllib.parse.urljoin(base_url, m.group(3).strip("<>"))
        n = number(href)  # stable, followable number
        if is_image:
            return m.group(0)  # leave images intact for the image-link renderer
        return f"⟦{n}⟧ [{text}]({href})"

    return COMBINED_RE.sub(repl, md), links


# --- table-aware rendering -------------------------------------------------
# rich.Markdown truncates wide-table cells with "…", which mangles data-heavy
# tables (financial dashboards, etc). We pull GFM pipe tables out of the body
# and render them ourselves: normal grid when it fits, vertical record layout
# when it's too wide to fit the terminal.

TABLE_SEP_RE = re.compile(r"^\s*\|?[\s:|-]*-{2,}[\s:|-]*\|?\s*$")


def _is_table_start(lines: list[str], i: int) -> bool:
    return (
        "|" in lines[i]
        and i + 1 < len(lines)
        and "-" in lines[i + 1]
        and TABLE_SEP_RE.match(lines[i + 1]) is not None
    )


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def iter_blocks(body: str):
    """Yield ('text', str) and ('table', list[str]) blocks in document order."""
    lines = body.split("\n")
    i, n, buf = 0, len(lines), []
    while i < n:
        if _is_table_start(lines, i):
            if buf:
                yield "text", "\n".join(buf)
                buf = []
            start = i
            i += 2
            while i < n and "|" in lines[i] and lines[i].strip():
                i += 1
            yield "table", lines[start:i]
        else:
            buf.append(lines[i])
            i += 1
    if buf:
        yield "text", "\n".join(buf)


def _pad(s: str, width: int) -> str:
    """Right-pad to a display width, counting CJK glyphs as 2 columns."""
    return s + " " * max(0, width - cell_len(s))


def render_table(table_lines: list[str]) -> None:
    """Print an aligned monospace text table — no width fitting, no truncation.

    A markdown table is just text, so we emit it as text: pad each column to its
    widest cell and let the terminal handle anything wider than the window
    (soft_wrap). Every character of data is preserved.
    """
    # Mosaics can't live inside a text cell — collapse any image to "🖼alt".
    def clean(cell: str) -> str:
        return IMAGE_RE.sub(lambda m: "🖼" + m.group(1).strip(), cell)

    header = [clean(c) for c in _cells(table_lines[0])]
    rows = [[clean(c) for c in _cells(l)] for l in table_lines[2:]]
    ncols = len(header)
    header = (header + [""] * ncols)[:ncols]
    rows = [(r + [""] * ncols)[:ncols] for r in rows]

    col_w = [cell_len(header[k]) for k in range(ncols)]
    for r in rows:
        for k in range(ncols):
            col_w[k] = max(col_w[k], cell_len(r[k]))

    def fmt(cells: list[str]) -> str:
        return " │ ".join(_pad(cells[k], col_w[k]) for k in range(ncols))

    sep = "─┼─".join("─" * col_w[k] for k in range(ncols))
    console.print(fmt(header), soft_wrap=True, markup=False, highlight=False, style="bold")
    console.print(sep, soft_wrap=True, markup=False, highlight=False, style="dim")
    for r in rows:
        console.print(fmt(r), soft_wrap=True, markup=False, highlight=False)


# --- inline images ---------------------------------------------------------
# We don't render image pixels (terminal mosaics look bad and are slow). Instead
# each image becomes a compact line: 🖼 ⟦n⟧ + a clickable link to the original,
# so you can press n or click to open the full image in a real browser.

IMAGE_RE = re.compile(r"!\[([^\]]*)\]\((<[^>]+>|[^)\s]+)(?:\s+\"[^\"]*\")?\)")
_IMG_MAX_BYTES = 16 << 20  # cap when downloading originals for vault saves
_IMG_CTX = ssl._create_unverified_context()  # tolerate bad certs like the render tier


def download_bytes(url: str) -> tuple[bytes, str]:
    """Fetch raw bytes + content-type for an image (used only when saving to a vault)."""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15, context=_IMG_CTX) as resp:
        data = resp.read(_IMG_MAX_BYTES + 1)
        ct = resp.headers.get("Content-Type", "")
    if len(data) > _IMG_MAX_BYTES:
        raise ValueError("image too large")
    return data, ct


def render_text(text: str, base_url: str, links: list[str], lang: str = "en") -> None:
    """Render a markdown text block; each image becomes a 🖼 ⟦n⟧ clickable link."""
    pos = 0
    for m in IMAGE_RE.finditer(text):
        before = text[pos:m.start()]
        if before.strip():
            console.print(Markdown(before))
        src = urllib.parse.urljoin(base_url, m.group(2).strip("<>"))
        num = links.index(src) + 1 if src in links else None
        label = m.group(1).strip() or "image"
        tag = f"⟦{num}⟧ " if num else ""
        if src.startswith("data:"):
            console.print("[dim]🖼 " + tr(lang, "inline_data_image", tag=tag, label=label) + "[/]")
        else:
            console.print(Markdown(f"🖼 {tag}[{label}]({src})"))
        pos = m.end()
    rest = text[pos:]
    if rest.strip():
        console.print(Markdown(rest))


def render_body(body: str, base_url: str = "", links: list[str] | None = None, lang: str = "en") -> None:
    """Render markdown: pipe tables as text tables, images as link lines, rest via rich."""
    links = links or []
    for kind, block in iter_blocks(body):
        if kind == "table":
            render_table(block)
        elif block.strip():
            render_text(block, base_url, links, lang)


# --- saving to a local Obsidian vault --------------------------------------
# A page → one Markdown note with YAML frontmatter (Obsidian properties). Images
# are downloaded into attachments/ and the note embeds the local copies. Links
# to pages already in the vault become [[wikilinks]] so Obsidian's graph connects
# them. An index maps url → note name for idempotent re-saves and wikilinking.

DEFAULT_VAULT = os.environ.get("MDBROWSER_VAULT", "mdbrowser-vault")
INDEX_FILE = ".mdbrowser-index.json"
_EXT_BY_CT = {
    "image/png": ".png", "image/jpeg": ".jpg", "image/gif": ".gif",
    "image/webp": ".webp", "image/svg+xml": ".svg", "image/avif": ".avif",
}


def _norm_url(url: str) -> str:
    """Canonical key for matching pages: lowercase host, no trailing slash, no fragment."""
    p = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit(
        (p.scheme.lower(), p.netloc.lower(), p.path.rstrip("/"), p.query, ""))


def slugify(text: str, fallback: str) -> str:
    """Filesystem- and Obsidian-safe note name (keeps spaces and unicode/CJK)."""
    text = re.sub(r'[\\/:*?"<>|#^\[\]]', "", text or "").strip()
    text = re.sub(r"\s+", " ", text)
    return text[:80].strip() or fallback or "page"


def _img_ext(src: str, ct: str) -> str:
    ext = os.path.splitext(urllib.parse.urlparse(src).path)[1].lower()
    if ext in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".avif"):
        return ext
    return _EXT_BY_CT.get(ct.split(";")[0].strip(), ".img")


def page_title(raw: str, url: str) -> str:
    for line in raw.splitlines():
        if line.startswith("Title:") and line[6:].strip():
            return line[6:].strip()
    m = re.search(r"^#\s+(.+)$", body_text(raw), re.MULTILINE)
    if m:
        return m.group(1).strip()
    return urllib.parse.urlparse(url).netloc or url


def _load_index(vault: str) -> dict:
    try:
        with open(os.path.join(vault, INDEX_FILE), encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_to_vault(url: str, raw: str, backend: str, vault: str) -> tuple[str, int]:
    """Write one page as an Obsidian note + attachments. Returns (note_name, images_saved)."""
    attach = os.path.join(vault, "attachments")
    os.makedirs(attach, exist_ok=True)
    index = _load_index(vault)
    title = page_title(raw, url)
    key = _norm_url(url)

    # Stable note name: reuse prior slug for this url, else slugify title (+hash on clash).
    slug = index.get(key, {}).get("slug")
    if not slug:
        base = slugify(title, urllib.parse.urlparse(url).netloc)
        slug = base
        taken = {v["slug"] for k, v in index.items() if k != key}
        if slug in taken:
            slug = f"{base} {hashlib.sha1(url.encode()).hexdigest()[:6]}"

    body = body_text(raw)
    saved = 0

    def img_repl(m: re.Match) -> str:
        nonlocal saved
        alt = m.group(1)
        src = urllib.parse.urljoin(url, m.group(2).strip("<>"))
        if src.startswith("data:"):
            return m.group(0)
        try:
            data, ct = download_bytes(src)
            name = hashlib.sha1(src.encode()).hexdigest()[:16] + _img_ext(src, ct)
            with open(os.path.join(attach, name), "wb") as f:
                f.write(data)
            saved += 1
            return f"![{alt}](attachments/{name})"
        except Exception:  # noqa: BLE001 - keep the remote URL if the download fails
            return f"![{alt}]({src})"

    body = IMAGE_RE.sub(img_repl, body)

    def link_repl(m: re.Match) -> str:
        if m.group(1):  # image — already handled above
            return m.group(0)
        text = m.group(2)
        href = urllib.parse.urljoin(url, m.group(3).strip("<>"))
        tgt = index.get(_norm_url(href))
        if tgt:  # link to an already-saved page → Obsidian wikilink (builds the graph)
            return f"[[{tgt['slug']}|{text}]]"
        return f"[{text}]({href})"

    body = COMBINED_RE.sub(link_repl, body)

    fetched = datetime.now().isoformat(timespec="seconds")
    domain = urllib.parse.urlparse(url).netloc
    tag = re.sub(r"[^\w/-]", "-", domain)
    fm = (
        "---\n"
        f'title: "{title.replace(chr(34), chr(39))}"\n'
        f"url: {url}\n"
        f"fetched: {fetched}\n"
        f"backend: {backend}\n"
        f"domain: {domain}\n"
        "tags:\n  - mdbrowser\n"
        f"  - {tag}\n"
        "---\n\n"
    )
    with open(os.path.join(vault, slug + ".md"), "w", encoding="utf-8") as f:
        f.write(fm + body.strip() + "\n")

    index[key] = {"slug": slug, "title": title, "url": url, "fetched": fetched, "backend": backend}
    with open(os.path.join(vault, INDEX_FILE), "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    return slug, saved


# --- persistent browsing history -------------------------------------------
HISTORY_FILE = os.environ.get("MDBROWSER_HISTORY", os.path.expanduser("~/.mdbrowser/history"))
HISTORY_MAX = 1000  # keep the most recent N visited URLs


def load_history() -> list[str]:
    try:
        with open(HISTORY_FILE, encoding="utf-8") as f:
            return [ln.strip() for ln in f if ln.strip()]
    except (FileNotFoundError, OSError):
        return []


def save_history(history: list[str]) -> None:
    try:
        os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(history[-HISTORY_MAX:]) + "\n")
    except OSError:
        pass  # never let history persistence break browsing


# --- settings (persisted) --------------------------------------------------
SETTINGS_FILE = os.environ.get("MDBROWSER_SETTINGS", os.path.expanduser("~/.mdbrowser/settings.json"))
DEFAULT_SETTINGS = {"language": "English", "mode": "browse"}  # persisted across sessions


def load_settings() -> dict:
    try:
        with open(SETTINGS_FILE, encoding="utf-8") as f:
            return {**DEFAULT_SETTINGS, **json.load(f)}
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return dict(DEFAULT_SETTINGS)


def save_settings(settings: dict) -> None:
    try:
        os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


MODES = ("browse", "reader", "summary")  # cycled with Shift+Tab


class Browser:
    def __init__(self) -> None:
        self.history: list[str] = load_history()  # persisted across sessions
        self.pos: int = len(self.history) - 1     # start at the most recent page
        self.links: list[str] = []     # current page's numbered links
        self.sel: int | None = None    # history-browsing cursor (↑/↓), None = idle
        self.vault: str = DEFAULT_VAULT  # local Obsidian vault for saved pages
        self.page: dict | None = None  # last loaded page {url, raw, backend} for saving
        self.settings: dict = load_settings()  # persisted: language + mode
        m = self.settings.get("mode", "browse")
        self.mode: str = m if m in MODES else "browse"  # restored across sessions
        self.rendered_mode: str = self.mode  # mode the current page was rendered in

    def cycle_mode(self) -> None:
        # Flip the mode flag only — instant, no fetch. Applied on next open / reload.
        self.mode = MODES[(MODES.index(self.mode) + 1) % len(MODES)]
        self.settings["mode"] = self.mode  # persist so it survives a restart
        save_settings(self.settings)

    @property
    def lang(self) -> str:
        return ui_lang(self.settings.get("language", "English"))

    def t(self, key: str, **kw) -> str:
        return tr(self.lang, key, **kw)

    @property
    def current(self) -> str | None:
        return self.history[self.pos] if 0 <= self.pos < len(self.history) else None

    def open(self, url: str, *, push: bool = True) -> None:
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        raw, backend = "", "static"

        if self.mode in ("reader", "summary"):
            # Render then extract just the article body (shared by reader + summary).
            try:
                with console.status(self.t("st_reading", url=url)):
                    raw = reader_markdown(url)
                backend = self.mode
            except Exception as exc:  # noqa: BLE001 - surface reader failure to user
                console.print(self.t("reader_failed", exc=exc))
        else:
            # Tier 1 — static fetch via Jina.
            try:
                with console.status(self.t("st_static", url=url)):
                    raw = fetch_markdown(url)
                if not main_content(raw):  # empty (often a cached snapshot) → retry fresh
                    with console.status(self.t("st_retry", url=url)):
                        raw = fetch_markdown(url, no_cache=True)
            except Exception:  # noqa: BLE001 - static failed; the render tier may still work
                raw = ""

            # Tier 2 — headless render (SPAs, expired certs, anti-bot static fetchers,
            # and pages still showing a "loading…" placeholder over JS-injected data).
            if not main_content(raw) or looks_unrendered(main_content(raw)):
                try:
                    with console.status(self.t("st_render", url=url)):
                        raw = render_markdown(url)
                    backend = "rendered"
                except Exception as exc:  # noqa: BLE001 - surface render failure to user
                    console.print(self.t("render_failed", exc=exc))

        if not main_content(raw):
            self.warn_empty(url, raw)
            return

        # Summary mode — append an AI-written summary section using the user's own LLM.
        if self.mode == "summary":
            summary = ai_summary_section(body_text(raw), self.settings.get("language", "English"))
            raw += f"\n\n---\n\n## 🤖 {self.t('ai_heading')}\n\n" + summary

        body, self.links = extract_links(raw, url)
        if push:
            # Truncate any forward history when navigating to a new page.
            del self.history[self.pos + 1:]
            if not self.history or self.history[-1] != url:  # skip consecutive dupes
                self.history.append(url)
            self.pos = len(self.history) - 1
            save_history(self.history)  # persist across sessions
        self.sel = None  # reset the ↑/↓ history cursor to the current page
        self.page = {"url": url, "raw": raw, "backend": backend}
        self.rendered_mode = self.mode  # this page now reflects the current mode
        self.render(body, url, backend)

    def render(self, body: str, url: str, backend: str = "static") -> None:
        console.rule(f"[bold cyan]{url}")
        render_body(body, base_url=url, links=self.links, lang=self.lang)
        tags = {"rendered": "[green]rendered[/]", "reader": "[magenta]reader[/]",
                "summary": "[blue]summary[/]"}
        tag = tags.get(backend, "[dim]static[/]")
        bar = f"{tag} · [dim]{len(self.links)} links · {self.pos + 1}/{len(self.history)} in history[/]"
        console.print(Panel(bar, expand=False, border_style="dim"))

    def warn_empty(self, url: str, raw: str) -> None:
        """The page rendered no body — explain the likely causes instead of a blank screen."""
        title = ""
        for line in raw.splitlines():
            if line.startswith("Title:"):
                title = line[len("Title:"):].strip()
                break
        msg = Text()
        if title:
            msg.append(self.t("empty_got_title", title=title), style="yellow")
        else:
            msg.append(self.t("empty_no_content"), style="yellow")
        msg.append(self.t("empty_both"), style="dim")
        msg.append(self.t("empty_causes"), style="bold")
        msg.append(self.t("empty_list"))
        msg.append(self.t("empty_try"), style="bold")
        msg.append(self.t("empty_try_rest"))
        console.print(Panel(msg, title=self.t("empty_title", url=url), border_style="red", expand=False))

    def back(self) -> None:
        if self.pos > 0:
            self.pos -= 1
            self.open(self.history[self.pos], push=False)
        else:
            console.print(self.t("oldest_page"))

    def forward(self) -> None:
        if self.pos < len(self.history) - 1:
            self.pos += 1
            self.open(self.history[self.pos], push=False)
        else:
            console.print(self.t("no_forward"))

    def follow(self, n: int) -> None:
        if 1 <= n <= len(self.links):
            self.open(self.links[n - 1])
        else:
            console.print(self.t("no_link", n=n, m=len(self.links)))

    def do_setting(self, arg: str) -> None:
        """`set` shows settings; `set language <name>` changes one and persists it."""
        parts = arg.split()
        if not parts:
            console.print(self.t("settings_header"))
            for k, v in self.settings.items():
                console.print(f"  [cyan]{k}[/] = {v}")
            console.print(self.t("settings_hint"))
            return
        key = "language" if parts[0] in ("language", "lang") else parts[0]
        if key == "language" and len(parts) >= 2:
            self.settings["language"] = " ".join(parts[1:])
            save_settings(self.settings)
            console.print(self.t("lang_set", value=self.settings["language"]))
            if self.current and self.mode == "summary":
                self.open(self.current, push=False)  # re-summarize in the new language
        else:
            console.print(self.t("settings_usage"))

    # --- command dispatch (shared by typed input and synthetic keys) -------
    def dispatch(self, raw: str) -> bool:
        """Run one command. Returns False to quit the browser."""
        raw = raw.strip()
        if not raw:
            return True
        cmd, _, arg = raw.partition(" ")
        self.sel = None  # any command ends history-browsing

        if cmd in ("q", "quit", "exit"):
            return False
        elif cmd in ("h", "help", "?"):
            console.print(help_text(self.lang))
        elif cmd == "__hist":  # synthetic: open a history index (↵ on cursor)
            i = int(arg)
            if 0 <= i < len(self.history):  # current page included → reloads it
                self.pos = i
                self.open(self.history[i], push=False)
        elif cmd.isdigit():
            self.follow(int(cmd))
        elif cmd in ("b", "back"):       # reached via Ctrl+Left key binding
            self.back()
        elif cmd in ("f", "forward"):    # reached via Ctrl+Right key binding
            self.forward()
        elif cmd in ("r", "reload"):
            if self.current:
                self.open(self.current, push=False)
        elif cmd in ("s", "save"):
            if not self.page:
                console.print(self.t("nothing_to_save"))
            else:
                try:
                    slug, imgs = save_to_vault(
                        self.page["url"], self.page["raw"], self.page["backend"], self.vault)
                    console.print(self.t("saved", path=f"{self.vault}/{slug}.md", n=imgs))
                except Exception as exc:  # noqa: BLE001 - surface save errors
                    console.print(self.t("save_failed", exc=exc))
        elif cmd in ("/clear-history", "clear-history"):
            n = len(self.history)
            self.history.clear()
            self.pos = -1
            save_history(self.history)
            console.print(self.t("history_cleared", n=n))
        elif cmd in ("set", "settings"):
            self.do_setting(arg.strip())
        elif looks_like_url(raw):  # bare URL pasted → just open it (no need for `o`)
            self.open(raw)
        else:
            console.print(self.t("unknown_cmd"))
        return True


HELP_EN = """\
[bold]commands[/]
  [cyan]paste a URL + ↵[/]   open it (no command needed)
  [cyan]num → link[/]        type a link's number ⟦n⟧ to open it (links are also clickable)
  [cyan]↑ / ↓[/]             step back / forward through visited pages; [cyan]↵[/] opens the highlighted one
  [cyan]r[/]                 reload this page
  [cyan]Shift+Tab[/]         cycle mode: browse → reader → summary (instant; press [cyan]r[/] to apply to this page)
                       [dim]reader = just the article body; summary = article + AI summary[/]
  [cyan]s[/]                 save this page to your local Obsidian vault (.md + images)
  [cyan]set[/]               show settings; [cyan]set language <name>[/] sets the language (UI + summary)
  [cyan]/clear-history[/]    wipe saved browsing history
  [cyan]h / q[/]             this help / quit

[dim]summary mode uses your own LLM (any OpenAI-compatible API) — set
MDBROWSER_LLM_KEY / MDBROWSER_LLM_MODEL / MDBROWSER_LLM_BASE.[/]\
"""

HELP_ZH = """\
[bold]命令[/]
  [cyan]粘贴网址 + ↵[/]    打开（无需命令）
  [cyan]数字 → 链接[/]     输入链接编号 ⟦n⟧ 打开它（链接也可直接点击）
  [cyan]↑ / ↓[/]          在访问过的页面间后退 / 前进；[cyan]↵[/] 打开选中的那页
  [cyan]r[/]              重新加载当前页
  [cyan]Shift+Tab[/]      切换模式：浏览 → 阅读 → 摘要（即时；按 [cyan]r[/] 应用到当前页）
                     [dim]阅读 = 只看正文；摘要 = 正文 + AI 摘要[/]
  [cyan]s[/]              保存当前页到本地 Obsidian vault（.md + 图片）
  [cyan]set[/]            查看设置；[cyan]set language <名称>[/] 切换语言（界面 + 摘要）
  [cyan]/clear-history[/] 清空浏览历史
  [cyan]h / q[/]          帮助 / 退出

[dim]摘要模式用你自己的大模型（任意 OpenAI 兼容接口）——设置
MDBROWSER_LLM_KEY / MDBROWSER_LLM_MODEL / MDBROWSER_LLM_BASE。[/]\
"""


def help_text(lang: str) -> str:
    return HELP_ZH if lang == "zh" else HELP_EN


USAGE = """\
mdbrowser — terminal markdown browser (Obsidian-compatible saves)

  mdbrowser                     interactive mode
  mdbrowser <url>               fetch <url>, print it, and exit (command-line mode)
  mdbrowser --reader  <url>     command-line: print just the article body
  mdbrowser --summary <url>     command-line: print article + AI summary
  mdbrowser --vault <dir> ...   set the save directory for `s`

In interactive mode: type h for help. URL also works piped: `mdbrowser <url> | less`."""


def main() -> None:
    argv = sys.argv[1:]
    url, vault, mode_override = None, None, None
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("-h", "--help"):
            print(USAGE)
            return
        elif a == "--vault" and i + 1 < len(argv):
            vault, i = argv[i + 1], i + 2
            continue
        elif a in ("--browse", "--reader", "--summary"):
            mode_override = a[2:]
        elif not a.startswith("-"):
            url = a
        i += 1

    browser = Browser()
    if vault:
        browser.vault = vault
    if mode_override:
        browser.mode = browser.rendered_mode = mode_override

    # Command-line mode: a URL argument → fetch, render to stdout, exit.
    if url:
        browser.open(url)
        return

    # No URL → interactive mode.
    from prompt_toolkit import PromptSession
    from prompt_toolkit.formatted_text import HTML
    from prompt_toolkit.key_binding import KeyBindings

    console.print(Panel.fit(browser.t("banner", vault=browser.vault), border_style="cyan"))
    if browser.history:
        console.print(browser.t("restored", n=len(browser.history)))

    kb = KeyBindings()

    @kb.add("up")
    def _(event) -> None:
        buf = event.app.current_buffer
        if buf.text:                       # typing → normal command-history recall
            buf.auto_up()
            return
        if not browser.history:
            return
        if browser.sel is None:
            browser.sel = browser.pos
        browser.sel = max(0, browser.sel - 1)

    @kb.add("down")
    def _(event) -> None:
        buf = event.app.current_buffer
        if buf.text:
            buf.auto_down()
            return
        if not browser.history:
            return
        if browser.sel is None:
            browser.sel = browser.pos
        browser.sel = min(len(browser.history) - 1, browser.sel + 1)

    @kb.add("enter")
    def _(event) -> None:
        buf = event.app.current_buffer
        if not buf.text.strip():
            if browser.sel is not None:
                # browsing history → open the selected page (current included = reload)
                buf.text = f"__hist {browser.sel}"
            elif browser.current and browser.mode != browser.rendered_mode:
                # Shift+Tab changed the mode → apply it to the current page
                buf.text = "r"
        buf.validate_and_handle()

    @kb.add("s-tab")  # Shift+Tab → cycle mode (instant: flip flag + redraw toolbar)
    def _(event) -> None:
        if not event.app.current_buffer.text.strip():
            browser.cycle_mode()
            event.app.invalidate()  # redraw the bottom toolbar immediately, no fetch

    def toolbar() -> HTML:
        # Line 1: Claude-Code-style mode indicator. Line 2: the key hints.
        lang = browser.lang
        label = tr(lang, {"browse": "mode_browse", "reader": "mode_reader",
                          "summary": "mode_summary"}[browser.mode])
        # When the mode was just changed but the page hasn't been re-rendered, prompt to apply.
        pending = browser.current and browser.mode != browser.rendered_mode
        hint = tr(lang, "mode_apply") if pending else tr(lang, "mode_cycle")
        mode = f" ⏵ {label}  {hint} "
        lines = [f"<b>{_esc(mode)}</b>", _esc(tr(lang, "keys"))]
        if browser.sel is not None and browser.history:
            mark = "●" if browser.sel == browser.pos else "○"
            hist = tr(lang, "hist_line", mark=mark, i=browser.sel + 1,
                      m=len(browser.history), url=browser.history[browser.sel])
            lines.insert(0, f"<b>{_esc(hist)}</b>")
        return HTML("\n".join(lines))

    session: PromptSession = PromptSession(key_bindings=kb, bottom_toolbar=toolbar)

    while True:
        try:
            raw = session.prompt(HTML("<ansigreen><b>» </b></ansigreen>"))
        except KeyboardInterrupt:
            continue
        except EOFError:
            break
        if not browser.dispatch(raw):
            break

    console.print(browser.t("bye"))


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


if __name__ == "__main__":
    main()
