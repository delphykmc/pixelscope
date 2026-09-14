# User Guide follow-up work packages

The searchable User Guide foundation is now merged. Follow-up work keeps application Help integration, release packaging, hosting, and agent-facing extensions as separate contracts.

## WP-Help-A — Application Help integration

Status: **implemented on the User Guide Help integration branch**.

- **Help > User Guide** is installed by the production application composition.
- Frozen/release builds resolve the local entry point relative to the executable as `help/index.html`; the application does not depend on the process working directory.
- Source runs can open an already-built `site/index.html` and may also consume a local `help/index.html` bundle.
- The local page is handed to the platform through `QDesktopServices` rather than embedding a browser engine or introducing QtHelp/QCH.
- A build without a local bundle reports that the User Guide is unavailable instead of guessing an online location.
- Focused tests cover path resolution, Help-menu placement, idempotent installation, and local-file URL handoff.

Online Documentation remains dependent on WP-Help-C establishing an authoritative deployment URL. F1/context-sensitive routing remains deferred until the static local Help path has shipped and proved stable.

## WP-Help-B — Packaging integration — next

- Build the MkDocs offline site as a release input.
- Consume the already validated, self-contained `site/` artifact when producing the offline `help/` bundle; the installed application must not fetch documentation assets at runtime.
- Include the generated help bundle in PyInstaller/Inno Setup artifacts so the WP-Help-A executable-relative `help/index.html` contract is satisfied.
- Validate that installed relative links, search assets, screenshots, and self-hosted external assets work without network access.
- Add release-artifact checks without making documentation packages runtime dependencies.
- Define cache/bootstrap handling separately if a documentation build itself must run in an air-gapped environment.

## WP-Help-C — Documentation deployment

- Publish the same generated static site to GitHub Pages **or** an enterprise/internal static server.
- Keep hosting optional so repositories with Pages disabled still build locally.
- Define release/tag/version publication and retention policy.
- Once an authoritative deployment URL exists, add an explicit **Online Documentation** action rather than silently falling back from local Help.

## WP-Help-D — Agent interface

- Extend the static `llms.txt` entry point if agent ecosystems converge on additional conventions.
- Evaluate local documentation search and an optional Ask PixelScope experience only after the static corpus and packaging path are stable.
- Keep any future RAG/LLM service optional and separate from the canonical Markdown.
- Evaluate F1/context-sensitive routing without coupling user documentation to Qt widget implementation details.

## Deferred/non-goals

No embedded PyQt Help window, QWebEngineView, QtHelp/QCH, chatbot, RAG server, Remote LLM API, implicit online fallback, or context-sensitive F1 routing is part of WP-Help-A. Installer bundle integration is owned by WP-Help-B.
