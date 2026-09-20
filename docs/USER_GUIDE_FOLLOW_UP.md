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

## WP-Help-B — Fully local documentation build and packaging — next

**Non-negotiable security contract:** the User Guide must build from checked-in files plus a
preinstalled documentation toolchain, even when individual external URLs are blocked. A
previously warmed MkDocs privacy cache, permitted CDN access, symlink privileges, or
internet access on the release machine must not be prerequisites.

- Replace the current CDN-based iframe-worker polyfill with a versioned, checked-in local
  JavaScript asset. Preserve working `file://` search; do not disable the offline plugin,
  substitute a no-op shim, or merely silence privacy-plugin warnings.
- Investigate the current build-time Mermaid CDN fetch. If no supported User Guide page
  uses Mermaid, remove its dependency without introducing an unbundled runtime URL.
  Otherwise vendor the exact required script locally.
- Record upstream version, source, license/attribution, and a reproducible content hash
  for each vendored third-party asset. Avoid downloading arbitrary mutable CDN content
  during routine documentation builds.
- Make `mkdocs build --strict` work after clearing `site/` and
  `.cache/plugin/privacy/` with outbound network access blocked. Include a deterministic
  test/CI job that prevents outbound requests during the build, not just an assertion
  that HTML is free of CDN links after a network-enabled build.
- Extend the generated-site contract to cover all runtime-loaded HTML, CSS, and JS
  references and to detect missing relative assets, especially the search shim.
- Consume the validated, self-contained `site/` as a release input for the offline
  `help/` bundle. Include it in portable ZIP and Inno Setup artifacts at the exact
  executable-relative path `help/index.html`.
- Validate offline search, navigation, screenshots, and relative links in installed
  and portable builds on Windows without network access.
- Documentation packages remain build-time dependencies, never PixelScope runtime
  dependencies. If the package installation itself must occur air-gapped, provide an
  approved internal package index or a prebuilt, pinned wheelhouse; this bootstrap is
  separate from the requirement for a network-free MkDocs build once installed.

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
