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

The generated `site/` uses local relative assets, the Material offline plugin,
and system fonts. The exact MIT-licensed iframe-worker 1.0.4 JS is checked
in under `docs/user-guide/assets/vendor/`, together with its upstream license,
provenance, and SHA-256. The privacy plugin has been removed; it is not needed
to download an asset that already exists in the repository. Mermaid diagrams
are not currently part of the supported User Guide; introducing them requires
local asset handling before use.

To prove the build does not rely on internet access, a previously populated
privacy cache, or individually permitted CDN URLs, run the cold-cache
network-blocked validation (requires the documentation packages to be installed):

```powershell
.\.venv\Scripts\python.exe scripts\check_user_guide_build_offline.py
```

The network-blocked test is also enforced by GitHub Actions on Windows and
Ubuntu. `site/404.html` is intended for static hosting and is excluded from
installed `file://` Help because MkDocs generates root-relative 404 assets.

## Release packaging

The canonical `scripts/build_release.py` rebuilds the validated User Guide
and copies `site/` alongside the frozen executable as `dist/PixelScope/help/`.
Both the portable ZIP and Inno Setup installer consume that same onedir
payload; `Help > User Guide` uses `PixelScope.exe`-relative `help/index.html`.
The release artifact validator rejects missing, incomplete, or altered Help
assets before distribution.

If building from the separate release venv, specify the docs-enabled interpreter
through `PIXELSCOPE_DOCS_PYTHON` or install the docs toolchain in the ordinary
`.venv`. The release-candidate pipeline supplies its dev interpreter
automatically. MkDocs and Material are **build-time only** and are never required
on the installed machine.

The future MkDocs 2.0 warning banner is an upstream advisory unrelated to
these offline assets: `requirements/docs.txt` pins MkDocs 1.6.1 and Material
9.7.7. Python package installation itself needs an approved internal package
index or a wheelhouse in a fully air-gapped build environment.

## Optional online publication

The same generated static documentation can be staged for an approved internal
static server or manually deployed to GitHub Pages when repository policy allows
it. Online hosting is not needed for a local build, the installed offline Help,
or the four-file PixelScope application release contract.

See [User Guide deployment](USER_GUIDE_DEPLOYMENT.md) for explicit authorization,
manual workflow steps, canonical `main`/release-tag identity, SHA-256 publication
inventory, artifact retention, and online-link activation policy. No online
documentation URL is assumed until an owner verifies the real deployed address.
