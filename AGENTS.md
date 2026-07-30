# PixelScope Agent Rules

- Write and review all code for CPython 3.10 x64. Do not use Python 3.11+ syntax or APIs.
- Inspect related source and tests before changing public behavior; minimize public interface changes.
- Handle dtype promotion, overflow, channel order, strides, endianness, and image bounds explicitly.
- Keep numerical algorithms out of Qt widgets and keep expensive work off the UI thread.
- Add or update tests with every functional change.
- Before completion, run pytest, Ruff check/format check, and, when possible, mypy and pip check.
- If a validation command cannot run, report the exact reason.
- Verify Python 3.10 support before adding a production dependency; do not upgrade blindly.
- The packaging target is exactly PyInstaller 5.7 `onedir`. Never upgrade it to 6.x.
- Do not install or run packaging tools unless explicitly requested.
- Do not preserve temporary workarounds as permanent architecture.
- Never log credentials, image content, or unnecessary sensitive paths.
- Do not modify files outside this project.
- Do not push, force-push, destructively reset, or delete user files.
- Final reports must list changed files, commands, test results, and known constraints.
