# Installation

This page explains how an end user starts PixelScope. It intentionally does not duplicate developer build instructions.

## Installed application

Use the PixelScope installer or portable package supplied by your organization or release owner. Start **PixelScope** from the installed shortcut or executable.

PixelScope provides **Help > User Guide** for the bundled offline documentation. A release built with User Guide packaging includes `help/index.html` next to `PixelScope.exe` in both portable and installed editions. The page, search index, and JavaScript/CSS assets are local: no documentation server is required. Older or incomplete builds without the `help/` directory report that the guide is unavailable instead of silently opening an online URL.

## First launch

PixelScope opens with the main Image View and workspace panels. You can immediately use **File > Open Images...** (`Ctrl+O`) or **File > Open Folder...** (`Ctrl+Shift+O`).

Settings are stored separately from your image files. Opening images does not modify the source files.

## Developer/source installation

If you are running PixelScope from source, follow the repository `README.md` rather than this end-user page. The application and this User Guide have separate dependency groups; documentation packages are not runtime dependencies.

A source run can open an already-built `site/index.html` through **Help > User Guide**. Building that site still uses the separate documentation dependency group.

## Next step

Continue with the [Quick start](quick-start.md).
