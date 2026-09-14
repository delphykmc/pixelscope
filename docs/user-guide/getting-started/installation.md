# Installation

This page explains how an end user starts PixelScope. It intentionally does not duplicate developer build instructions.

## Installed application

Use the PixelScope installer or portable package supplied by your organization or release owner. Start **PixelScope** from the installed shortcut or executable.

PixelScope provides **Help > User Guide** for the local documentation bundle. Release packaging is responsible for placing that bundle at `help/index.html` next to the application. Until that packaging step is included in a release, choosing **Help > User Guide** reports that the local guide is unavailable rather than requiring a network connection or guessing an online documentation address.

## First launch

PixelScope opens with the main Image View and workspace panels. You can immediately use **File > Open Images...** (`Ctrl+O`) or **File > Open Folder...** (`Ctrl+Shift+O`).

Settings are stored separately from your image files. Opening images does not modify the source files.

## Developer/source installation

If you are running PixelScope from source, follow the repository `README.md` rather than this end-user page. The application and this User Guide have separate dependency groups; documentation packages are not runtime dependencies.

A source run can open an already-built `site/index.html` through **Help > User Guide**. Building that site still uses the separate documentation dependency group.

## Next step

Continue with the [Quick start](quick-start.md).
