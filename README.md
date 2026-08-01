# PixelScope

PixelScope is a CPU-only Windows desktop application for quickly comparing
multiple PNG, BMP, JPEG, and profile-described unpacked RAW images. It preserves
source pixel data while providing synchronized viewers, pixel readout,
full-image/ROI statistics and histograms, line profiles, and overflow-safe
signed/absolute differences.

## Requirements and installation

- Windows 10 or 11, x64
- CPython 3.10.x x64 (3.11+ is intentionally unsupported)

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements\runtime.txt
.\.venv\Scripts\python.exe -m pip install -r requirements\dev.txt
.\.venv\Scripts\python.exe -m pip install -e .
```

## Run

```powershell
.\.venv\Scripts\python.exe -m pixelscope
```

Register images by dropping one or more files/folders, or use **File > Open
Images / Open Folder**. Selecting files from different registered folders
creates a naturally sorted folder-pair session; Page Down/Up advances or
rewinds every participating folder atomically. RAW files with a same-name JSON sidecar are discovered
automatically; **Open RAW with Profile** remains available for manual profiles.

The menu bar groups commands under **File**, **Edit**, **Selection**, and
**View**. Files and analysis share the resizable left sidebar. Files is a
two-level tree of parent folders and naturally sorted filenames. Use standard
Ctrl/Shift selection; that ordered selection is the comparison set.
Auto/Single View/Multi View chooses the appropriate smart layout. In the single
viewer, Left/Right or the numbered header buttons toggle selected images.

When every selected file belongs to a different folder, Page Down/Up advances
or rewinds each folder by one position. Movement is atomic: if any folder has
no next/previous image, no folder moves. Each folder remembers its current
file. Selecting multiple files from one folder intentionally disables pair
navigation.

Mouse wheel zooms and dragging pans. Ctrl+drag sets one rectangular ROI at the
same image offset in every viewer; double-click or Esc clears it. With no ROI,
Comparison analyzes the full image. Alt+drag sets a shared horizontal line
segment; its per-image RGB profiles appear in the full-width panel below the
viewer, where R/G/B channels can be toggled independently.

Statistics uses one row per image channel with an explicit image ID. Histogram
bins follow each image's effective bit depth automatically. Histogram and line
profile provide channel toggles, grid lines, and compact legends. Difference
keeps one order-independent native absolute map per image pair; channel views,
ROI metrics, display range, gain, and threshold masks derive from that cache.
The status bar uses structured fields for file metadata, cursor, pixel values,
zoom, and background-task state.

The bottom **Plots** dock contains Histogram and Line Profile tabs. Its title
bar has explicit Float/Dock, Maximize/Restore, and Hide controls. Maximizing a
docked plot restores to its original dock position; maximizing a floating plot
restores to its previous floating state.

Example RAW profile:
[`examples/raw_profiles/example_unpacked_raw16.json`](examples/raw_profiles/example_unpacked_raw16.json).
RAW profiles can also be loaded and saved from the RAW dialog.

## Development

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m mypy src
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe scripts\generate_test_images.py
```

Generated deterministic images are written to ignored `test_data/generated/`
unless another output directory is supplied.

Manual validation assets are documented in
[`test_data/README.md`](test_data/README.md). The versioned FHD chart database
exercises JPEG folder pairing and multi-view workflows; the UHD database covers
4K PNG/RAW decoding, metrics, ROI, and Difference responsiveness.

## Current scope

Implemented: file/folder drag-and-drop, multi-file/folder dialogs, naturally
sorted folder pairs, lazy decoding, PNG/BMP/JPEG including Unicode paths, 8/16-bit
grayscale, explicit BGR-to-RGB conversion, unpacked u8/u16 RAW with
offset/stride/endianness, selection-driven 1/2/4/6 synchronized viewing,
cached asynchronous comparison statistics/histograms, shared rectangular ROI,
Alt-drag line profiles with channel toggles, preserved comparison view state,
cached native absolute differences, threshold masks, metrics, common background workers, remote
evaluation contracts, and a deterministic mock client.
The versioned FHD/UHD manual datasets are covered by integration tests for
folder pairing, reference/degraded metrics, and the provided Bayer RAW profile.

## Documentation

- [User guide](docs/USER_GUIDE.md)
- [Product scope](docs/PRODUCT_SPEC.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Engineering decisions](docs/DECISIONS.md)
- [Roadmap](docs/ROADMAP.md)
- [Current UI captures](docs/ui/README.md)

Not yet implemented: MIPI packed RAW decoding, demosaic, alpha overlay, live
GPU service, heatmap overlay, persistent sessions, and standalone distribution. See
[the roadmap](docs/ROADMAP.md).

Packaging and installers are deliberately not produced in this phase. The
future production target is exactly PyInstaller 5.7 `onedir` followed by Inno
Setup; PyInstaller 6.x is prohibited by deployment policy.
