# mdbrowser

> 终端里的纯文本网页浏览器。给它一个网址，它会抓取页面、转成干净的 Markdown，
> 并把每个链接编号、可点击地渲染出来 —— 像 `w3m`/`lynx`，但排版是 Markdown，
> 对人和 AI 都友好。可选阅读模式、AI 摘要模式，并能一键保存为 Obsidian 兼容的 vault。

[![CI](https://github.com/kinthaiofficial/mdbrowser/actions/workflows/ci.yml/badge.svg)](https://github.com/kinthaiofficial/mdbrowser/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](requirements.txt)
[![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Linux-lightgrey)]()

[English](README.md) · **中文**

---

## 使用

```bash
# 交互模式 —— 用键盘浏览
mdbrowser

# 命令行模式 —— 抓取网址、打印、退出（可脚本化 / 管道）
mdbrowser https://en.wikipedia.org/wiki/Markdown
mdbrowser --reader  https://some-blog/post     # 只看正文
mdbrowser --summary https://some-blog/post     # 正文 + AI 摘要
mdbrowser <url> | less                          # 输出非终端时自动走命令行模式
mdbrowser --help
```

### 交互按键

| 按键 | 作用 | 按键 | 作用 |
|-----|------|-----|------|
| 粘贴网址 + `↵` | 打开 | `<数字>` | 跟进链接 `⟦n⟧`（也可点击）|
| `↑` / `↓` | 在历史里后退 / 前进 | `↵` | 打开选中的页面 |
| `r` | 重新加载 | `Shift+Tab` | 切换模式：浏览 → 阅读 → 摘要 |
| `s` | 保存到 vault | `set` | 设置（`set language Chinese`）|
| `/clear-history` | 清空历史 | `h` / `q` | 帮助 / 退出 |

底部工具栏始终显示当前模式和按键提示。`Shift+Tab` 即时切换模式；按 `r`（或 `↵`）
把新模式应用到当前页。

## 安装

需要 Python 3.10+。

```bash
git clone https://github.com/kinthaiofficial/mdbrowser.git
cd mdbrowser
./install.sh        # 创建 .venv、安装依赖、下载 Chromium
```

放到 PATH 上（可选）：

```bash
sudo ln -sf "$(pwd)/mdbrowser" /usr/local/bin/mdbrowser
```

## 它解决什么

命令行里没有浏览器。mdbrowser 就是那块缺失的拼图：把任意网址变成终端里可读的
Markdown，每个链接都有编号，输入数字即可跟进（支持的终端里也能点击）。

```
            ┌─ tier 1: 静态  ── Jina Reader（快，无需本地浏览器）
URL ──┤            │ 空 / 加载中？ ↓ 自动回退
            └─ tier 2: 渲染  ── 无头 Chromium（Playwright）+ html2text
                                  ├ 执行 JS → 搞定 SPA
                                  └ 忽略过期/无效证书
```

- **静态优先、自动渲染** —— 多数页面静态抓取秒开；纯前端 SPA、证书过期的站点、
  "加载中" 空壳会自动回退到真实无头浏览器，无需手动操作。
- **链接编号 + 可点击** —— 链接渲染为 `⟦n⟧ 文字`：输数字跟进，或点击（OSC 8 超链接）。
  图片显示为 `🖼 ⟦n⟧` 链接 —— 不做又慢又糊的像素图。
- **文本表格** —— 宽表格按列对齐成等宽文本（绝不为适配终端而截断）。
- **阅读模式** —— 用 trafilatura 只提取正文，去掉导航/广告/侧栏，适合博客和新闻。
- **AI 摘要模式** —— 在末尾追加一段 AI 摘要，用**你自己的**模型（任意 OpenAI 兼容
  接口，不绑定任何厂商）。
- **保存到 Obsidian vault** —— 按 `s` 把页面剪藏成带 YAML frontmatter 的 Markdown
  笔记，图片存本地，已保存页面之间用 `[[wikilinks]]` 互链。
- **历史持久化**、**双语界面**（中 / 英），以及 **交互** 和 **命令行** 两种模式。

## AI 摘要模式

摘要模式通过任意 OpenAI 兼容的 `/chat/completions` 接口，用**你自己的大模型**生成摘要。
配置三个环境变量即可：

```bash
export MDBROWSER_LLM_KEY=your-api-key
export MDBROWSER_LLM_MODEL=deepseek-chat
export MDBROWSER_LLM_BASE=https://api.deepseek.com
```

base URL 按服务商固定；模型名会变动，以服务商控制台当前的为准。常见服务商：

| 服务商 | `MDBROWSER_LLM_BASE` | `MODEL`（示例）|
|---|---|---|
| DeepSeek | `https://api.deepseek.com` | `deepseek-chat` |
| MiniMax | `https://api.minimaxi.com/v1` | `MiniMax-M2.5` |
| Moonshot / Kimi | `https://api.moonshot.cn/v1` | `kimi-k2` |
| 通义千问（阿里）| `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-plus` |
| 智谱 GLM | `https://open.bigmodel.cn/api/paas/v4` | `glm-4.6` |
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-mini` |
| Google Gemini | `https://generativelanguage.googleapis.com/v1beta/openai` | `gemini-2.5-flash` |
| xAI Grok | `https://api.x.ai/v1` | `grok-4` |
| OpenRouter（含 Claude）| `https://openrouter.ai/api/v1` | `anthropic/claude-...` |
| Ollama（本地）| `http://localhost:11434/v1` | `qwen2.5` |

未配置时，摘要模式会在程序里直接打印这张表，方便你复制一段配置。推理模型输出的
`<think>…</think>` 会被自动剥离，只显示摘要本身。

## 保存（Obsidian vault）

按 `s` 保存当前页。文件存到你的 vault（默认 `./mdbrowser-vault`，可用 `--vault <目录>`
或 `MDBROWSER_VAULT` 指定）：

```
<vault>/
  <页面标题>.md           # 正文 + YAML frontmatter（标题、网址、时间、标签）
  attachments/<哈希>.png  # 图片原文件
  .mdbrowser-index.json   # url ↔ 笔记 索引（去重 + 双链）
```

用 [Obsidian](https://obsidian.md) 打开这个 vault 目录，即可阅读、搜索、用图谱串联你的
剪藏。指向已保存页面的链接会变成 `[[wikilinks]]`。

## 设置与语言

- 界面**默认英文**；`set language Chinese` 把**界面和 AI 摘要一起切中文**
  （`set language English` 切回）。
- 设置（`language`、`mode`）持久化在 `~/.mdbrowser/settings.json`；历史在
  `~/.mdbrowser/history`。

## 配置参考

| 环境变量 | 作用 | 默认 |
|---|---|---|
| `MDBROWSER_LLM_KEY` / `MDBROWSER_LLM_MODEL` / `MDBROWSER_LLM_BASE` | AI 摘要服务商 | — / — / `https://api.openai.com/v1` |
| `MDBROWSER_VAULT` | `s` 的保存目录 | `./mdbrowser-vault` |
| `MDBROWSER_HISTORY` | 历史文件 | `~/.mdbrowser/history` |
| `MDBROWSER_SETTINGS` | 设置文件 | `~/.mdbrowser/settings.json` |

## 工作原理

1. **Tier 1（静态）**：通过 [Jina Reader](https://jina.ai/reader) 抓取并带上链接摘要，
   多数页面（包括许多 SPA）都能直接返回带链接的干净 Markdown，无需本地浏览器。
2. **Tier 2（渲染）**：当正文为空或仍是"加载中"占位时，用无头 Chromium（Playwright，
   忽略 TLS 错误）渲染页面，再用 html2text 转换。
3. **阅读 / 摘要**：先渲染再用 trafilatura 提取正文（摘要模式额外调用你的大模型）。

## 许可证

MIT © 2026 Freddy Chu，见 [LICENSE](LICENSE)。

欢迎贡献 —— 贡献者名单见
[contributors](https://github.com/kinthaiofficial/mdbrowser/graphs/contributors)。
