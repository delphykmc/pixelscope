# PixelScope User Guide

This file remains the stable repository entry point for end-user documentation.

The canonical User Guide is now topic-oriented under [`docs/user-guide/`](user-guide/index.md) so the same Markdown source can power searchable web documentation, an offline static bundle, and agent/document search.

## Start here

- [User Guide home](user-guide/index.md)
- [5-minute Quick Start](user-guide/getting-started/quick-start.md)
- [Core concepts](user-guide/getting-started/concepts.md)
- [Keyboard shortcuts](user-guide/reference/keyboard-shortcuts.md)
- [RAW Guide](user-guide/formats/raw.md)
- [YUV Guide](user-guide/formats/yuv.md)
- [Troubleshooting](user-guide/troubleshooting/index.md)
- [Screenshot strategy](user-guide/assets/screenshots/README.md)

## Source-of-truth policy

User-visible behavior belongs in the topic page that owns that workflow or feature. Do not maintain a second prose copy here. Developer architecture, implementation phase names, regression history, and deployment plans remain in the developer documentation rather than in the end-user site.

The pre-MkDocs monolithic guide remains available in repository history (`git log -- docs/USER_GUIDE.md` and `git show 6b8773fb:docs/USER_GUIDE.md`, or any earlier relevant commit). It is intentionally not duplicated in the current tree because a second full guide would become a stale competing corpus for users, repository search, and agents.

## Build the searchable site

Install the documentation dependencies and run:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements\docs.txt
.\.venv\Scripts\python.exe -m mkdocs build --strict
.\.venv\Scripts\python.exe scripts\check_user_guide_site.py site
```

The static output is written to `site/`. `mkdocs.yml` uses relative-file-friendly URLs, the Material offline plugin, system fonts, and the Material privacy plugin. The iframe-worker shim is pinned to an explicit version and `.js` URL. Material's offline plugin recognizes the configured shim, while the privacy plugin downloads it as a regular file rather than attempting to create a Windows symlink for an extensionless CDN alias. The generated-site checker verifies `llms.txt` routes, local shim presence, and the absence of remote runtime resource dependencies. Hosting/deployment and installer inclusion are separate follow-up work.

A clean documentation build may require network access to fetch the pinned shim; the generated `site/` does not. The Material for MkDocs banner about future MkDocs 2.0 compatibility is an upstream advisory, not the cause of a failed build: `requirements/docs.txt` pins MkDocs 1.6.1 and Material 9.7.7. Do not suppress privacy-plugin warnings or enable Windows Developer Mode merely to make this build pass.
