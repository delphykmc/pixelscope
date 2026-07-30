# PixelScope

PixelScope is a CPU-only Windows desktop application for quickly comparing
multiple PNG, BMP, and profile-described unpacked RAW images. It preserves
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
Images / Open Folder**. Dropping two folders (or choosing **Compare Two
Folders**) creates naturally sorted image pairs and initially loads only the
first pair. RAW files with a same-name JSON sidecar are discovered
automatically; **Open RAW with Profile** remains available for manual profiles.

The menu bar groups commands under **File**, **Edit**, **Selection**, and
**View**. Files and analysis share the resizable left sidebar. Files is a
two-level tree of parent folders and naturally sorted filenames. Use standard
Ctrl/Shift selection; that ordered selection is the comparison set.
**Compare Selection** chooses an appropriate 2/4/6 viewer grid. In the single
viewer, Space and Shift+Space toggle selected images.

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

The Comparison table uses one image per column and one statistic per row.
Histogram bins follow each image's effective bit depth automatically. RGB
curves keep fixed red/green/blue colors while six line styles distinguish
images. Histogram and line profile both provide R/G/B toggles, grid lines, and
right-side legends. The status bar uses a fixed-width `Position (X, Y)` field
and numbered values separated by vertical bars. Space toggling and image drops
preserve the current zoom and offset.

Example RAW profile:
[`raw_profiles/example_unpacked_raw16.json`](raw_profiles/example_unpacked_raw16.json).
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

Generated deterministic images are written to ignored `generated_test_data/`
unless another output directory is supplied.

## Current scope

Implemented: file/folder drag-and-drop, multi-file/folder dialogs, naturally
sorted folder pairs, lazy decoding, PNG/BMP including Unicode paths, 8/16-bit
grayscale, explicit BGR-to-RGB conversion, unpacked u8/u16 RAW with
offset/stride/endianness, selection-driven 1/2/4/6 synchronized viewing,
cached asynchronous comparison statistics/histograms, shared rectangular ROI,
Alt-drag line profiles with channel toggles, preserved comparison view state,
signed/absolute differences, metrics, common background workers, remote
evaluation contracts, and a deterministic mock client.
`PixelScope_4K_Test_Samples` is covered by integration tests for
reference/degraded metrics and the provided Bayer RAW profile.

Not yet implemented: MIPI packed RAW, demosaic, alpha overlay, live GPU
service, heatmap overlay, and standalone distribution. See
[the roadmap](docs/ROADMAP.md).

Packaging and installers are deliberately not produced in this phase. The
future production target is exactly PyInstaller 5.7 `onedir` followed by Inno
Setup; PyInstaller 6.x is prohibited by deployment policy.
