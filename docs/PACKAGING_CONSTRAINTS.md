# Packaging constraints

Release packaging is outside P3-D Unified Image Opening & RAW Profile Resolution.

## Fixed platform and package constraints

- CPython 3.10 x64.
- PyInstaller exactly 5.7.
- `onedir` distribution; do not switch to onefile without a separate owner decision.
- Inno Setup remains the planned Windows installer layer.
- Do not introduce a different Qt binding or runtime solely for packaging.
- Application signing, installer signing, updater strategy, and final shell identity
  belong to P7 Release Engineering & Distribution.

## P3-D boundary

P3-D may change file/folder registration UX, RAW profile-resolution timing, and
related documentation/tests. It must not run or redesign packaging/signing as part
of that work. No Windows COM or native dependency should be added solely to support
multi-folder selection when a maintainable Qt/PySide implementation is available.
