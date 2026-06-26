# Changelog

All notable changes to mdbrowser will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] - 2026-06-26

### Added
- Initial release — a text-mode web browser for the terminal.
- **Two-tier fetch**: static via Jina Reader, with automatic headless-render
  fallback (Playwright) for JS-only SPAs, expired-cert sites, and "loading…"
  shells. No manual step.
- **Numbered + clickable links** (`⟦n⟧`, OSC 8 hyperlinks); images render as
  `🖼 ⟦n⟧` link lines; wide tables render as aligned, untruncated text tables.
- **Modes** (cycle with `Shift+Tab`): browse, reader (article extraction via
  trafilatura), and summary (AI summary using your own OpenAI-compatible model).
- **Save to an Obsidian-compatible vault**: Markdown note + YAML frontmatter,
  local image copies, and `[[wikilinks]]` between saved pages.
- **Persistent history** and **bilingual UI** (English / Chinese) via `set language`.
- **Interactive and command-line modes** (`mdbrowser <url>`, `--reader`, `--summary`).
