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

The pre-MkDocs monolithic guide remains available in repository history (`git log -- docs/USER_GUIDE.md` and `git show <commit>:docs/USER_GUIDE.md`). It is intentionally not duplicated in the current tree because a second full guide would become a stale competing corpus for users, repository search, and agents.

## Build the searchable site

Install the documentation dependencies and run:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements\docs.txt
.\.venv\Scripts\python.exe -m mkdocs build --strict
.\.venv\Scripts\python.exe scripts\check_user_guide_site.py site
```

The static output is written to `site/`. `mkdocs.yml` uses relative-file-friendly URLs, the Material offline plugin, and system fonts so the output does not depend on remote web-font assets. The generated-site checker verifies `llms.txt` routes and rejects remote resource dependencies. Hosting/deployment and installer inclusion are separate follow-up work.
