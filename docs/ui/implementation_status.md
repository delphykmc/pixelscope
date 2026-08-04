# PixelScope UI/performance iteration status

## Baseline

- Original iteration baseline: `ea64b1d8fda331e3f85dbfa0181d772974358e74`
- P0-A correction merge: `1606503a08b24b73e77f9fb4784d22c2339d6f59`
- P0-B merge: `b0ee42a9757337947de12eaf7052cae99ee7e527`
- P0-C merge: `494cab1a49da1efeaa970fc605029e1eda80e3b8`
- P0-D merge: `90c379a554418b5a2152a47f4b495d99dd8255e2`
- Current work branch: `chatgpt/p1a-files-statistics-responsive-header`
- Current phase: **P1-A — Files, Statistics, and responsive tile header**
- Phase state: **implementation prepared; awaiting local core patch and Windows review**
- Runtime constraints retained: CPython 3.10, PySide6 6.4.2, and future
  PyInstaller 5.7 `onedir` compatibility.

## P1-A goals

1. Simplify the Files tree so selection and active state are visually clear without
   exposing obsolete A/B or slot-role text.
2. Make the Difference panel selectors the only authority for the comparison pair.
3. Stabilize the Statistics header area and use accurate `Pixels` terminology.
4. Make tile headers degrade cleanly in narrow 3-, 4-, 5-, and 6-tile layouts.

## Prepared implementation

### Files tree

- Reduced the tree to `File` and `Type` columns.
- Removed the visible state/role column and the unused compare-role signal.
- Added distinct folder, regular image, RAW, loading, and error icons.
- Kept standard row selection highlighting.
- Added a bold active filename and a narrow left accent marker without replacing
  the normal selection background.
- Loading, error, visible, active, and registered state remain available through
  the file tooltip rather than terse A/B or slot labels.

### Difference pair authority

The local core patch removes the obsolete `_compare_pair` path from MainWindow
and MultiCompareView:

- no A/B badge assignment in Single View or Multi View
- no A/B state propagation into the Files tree
- no compare-role setter or signal connection
- no pair override passed into `DifferencePanel.set_documents()`
- current Image 1 / Image 2 selector values are preserved whenever both remain
  available; otherwise DifferencePanel falls back to the first valid distinct pair

### Statistics

- Region detail is a fixed-height row, so switching Full image / Active ROI does
  not move the tables below it.
- Full image leaves the detail row blank.
- Active ROI uses explicit fields:
  `x=…, y=…, width=…, height=…`.
- The image summary header changes from `Samples` to `Pixels`.
- RGB ROI pixel totals remain width × height.
- Bayer summary totals remain mosaic pixel counts, while the per-plane R/Gr/Gb/B
  rows remain unchanged.

### Responsive tile header

- Widths at or above 480 px show folder-qualified filename, image metadata, zoom,
  and focus controls.
- Widths below 480 px hide secondary metadata and retain badge/navigation,
  filename, zoom, and focus controls.
- Compact mode uses the basename instead of the folder-qualified label.
- Filename text remains middle-elided and the full path remains available in the
  tooltip.
- Focus-pin visibility remains limited to 3- and 5-tile layouts.

## Files changed or prepared

- `src/pixelscope/ui/document_list.py`
- `src/pixelscope/ui/tile_header.py`
- `tests/ui/test_p1a_files_statistics_header.py`
- `scripts/apply_p1a_core_patch.py` — temporary local integration helper
- `docs/ui/implementation_status.md`
- Local helper targets:
  - `src/pixelscope/app/main_window.py`
  - `src/pixelscope/ui/multi_compare_view.py`
  - `src/pixelscope/ui/comparison_analysis_panel.py`
  - `tests/ui/test_ui_smoke.py`

## Required local integration

```powershell
git fetch origin
git switch --track origin/chatgpt/p1a-files-statistics-responsive-header

.\.venv\Scripts\python.exe scripts\apply_p1a_core_patch.py
```

Format the affected files:

```powershell
.\.venv\Scripts\python.exe -m ruff format `
    src\pixelscope\app\main_window.py `
    src\pixelscope\ui\multi_compare_view.py `
    src\pixelscope\ui\comparison_analysis_panel.py `
    src\pixelscope\ui\document_list.py `
    src\pixelscope\ui\tile_header.py `
    tests\ui\test_ui_smoke.py `
    tests\ui\test_p1a_files_statistics_header.py `
    scripts\apply_p1a_core_patch.py
```

Run targeted validation:

```powershell
.\.venv\Scripts\python.exe -m pytest `
    tests\ui\test_p1a_files_statistics_header.py `
    tests\ui\test_ui_smoke.py `
    -q
```

Then run the full checks:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m mypy src
.\.venv\Scripts\python.exe -m pip check
```

## Manual UI checks

1. Files tree contains only File and Type columns.
2. Selected rows use the normal selection highlight; the active row also has bold
   text and a left accent.
3. Loading and failed files use distinct icons, and no A/B or slot text appears.
4. Changing Difference Image 1 / Image 2 remains stable while layout or focus
   changes are made.
5. Full image leaves the Region detail line blank; Active ROI shows explicit x, y,
   width, and height without changing the panel geometry.
6. Statistics summary says Pixels and retains correct RGB and Bayer counts.
7. Wide tiles show metadata; narrow tiles hide metadata but retain filename, zoom,
   and pin controls.
8. Pin controls appear only in 3- and 5-tile layouts.

## Incomplete / intentionally deferred

- P1-B and P1-C are not started.
- Preferences UI and QSettings-backed performance settings remain separate.
- Image resident cache and one-group-ahead preload remain separate.
- GitHub Release update checking and installer workflow remain separate.
- P0-A's internal fixed-arrangement compatibility field/QSettings key remains for
  later cleanup.
