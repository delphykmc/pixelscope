# User Guide follow-up work packages

The searchable User Guide foundation deliberately stops at documentation source, static-site build, search, self-contained offline output, validation, and screenshot strategy. Application/runtime integration remains separate.

## WP-Help-A — Application Help integration

- Add **Help > User Guide**.
- Open the installed local `help/index.html` bundle using the least invasive platform mechanism.
- Offer an Online Documentation action when a deployment URL exists.
- Evaluate F1/context-sensitive routing without coupling user documentation to Qt widget implementation details.

## WP-Help-B — Packaging integration

- Build the MkDocs offline site as a release input.
- Consume the already validated, self-contained `site/` artifact when producing the offline `help/` bundle; the installed application must not fetch documentation assets at runtime.
- Include the generated help bundle in PyInstaller/Inno Setup artifacts.
- Validate that installed relative links, search assets, screenshots, and self-hosted external assets work without network access.
- Add release-artifact checks without making documentation packages runtime dependencies.
- Define cache/bootstrap handling separately if a documentation build itself must run in an air-gapped environment.

## WP-Help-C — Documentation deployment

- Publish the same generated static site to GitHub Pages **or** an enterprise/internal static server.
- Keep hosting optional so repositories with Pages disabled still build locally.
- Define release/tag/version publication and retention policy.

## WP-Help-D — Agent interface

- Extend the static `llms.txt` entry point if agent ecosystems converge on additional conventions.
- Evaluate local documentation search and an optional Ask PixelScope experience only after the static corpus and packaging path are stable.
- Keep any future RAG/LLM service optional and separate from the canonical Markdown.

## Non-goals of the foundation PR

No PyQt Help window, QWebEngineView, QtHelp/QCH, F1 routing, Inno Setup bundle integration, online/offline switching, chatbot, RAG server, or Remote LLM API is implemented here.
