# PixelScope UI/performance iteration status

## Baseline

- Original iteration baseline: `ea64b1d8fda331e3f85dbfa0181d772974358e74`
- Initial P0-A commit: `d66b371831b4f2fa2792f9a5f576b1d66f4ba19c`
- Current work branch: `fix/p0a-fixed-multiview-layout`
- Current phase: **P0-A correction — fixed multi-view layouts**
- Phase state: **implementation complete; awaiting Windows test and visual review**
- Runtime constraints retained: CPython 3.10, current PySide6 binding, and future
  PyInstaller 5.7 `onedir` compatibility.

## Corrected P0-A behavior

- Removed the user-visible `Top Focus · 2 Columns` and
  `Left Focus · 3 Columns` choices from the View menu.
- Replaced selectable arrangements with one deterministic layout family:
  - 1 tile: single view
  - 2 tiles: one row by two columns
  - 3 tiles: focus spans the first two rows in the left column; two images stack
    in the right column
  - 4 tiles: 2 by 2 grid
  - 5 tiles: the 3-tile structure plus an equal-height bottom row containing two
    more images
  - 6 tiles: two columns by three rows
- Uses equal row and column stretch factors. The focus tile is formed by spanning
  cells rather than by assigning a larger stretch ratio.
- Focus-pin visibility remains limited to 3- and 5-tile layouts.
- Diff remains the initial focus for 2-source/3-tile and 4-source/5-tile results.
- Six sources plus Diff remains a Diff-only Single View and restores the previous
  focus, active document, page indices, display order, and synchronized view
  range when Diff is hidden.
- The existing six `ImageViewer` objects continue to be reused.
- Legacy persisted arrangement strings are normalized to the fixed-layout value.

## Implementation note

- `MainWindow` still contains the small arrangement persistence/restore path
  introduced by the initial P0-A commit. `MultiCompareView` exposes a temporary
  compatibility registry that creates no View-menu actions and accepts only the
  fixed-layout value. This keeps the correction narrow and preserves the tested
  six-image Diff restore path.
- A later cleanup may remove the now-internal arrangement field and QSettings key,
  but no selectable arrangement remains in the UI.

## Tests updated in this branch

- Exact grid positions and stretch factors for every tile count from 1 through 6.
- Focus-pin visibility only for 3 and 5 tiles.
- Real widget geometry for the 3-tile layout:
  equal columns and a focus tile spanning two equal-height rows.
- Real widget geometry for the 5-tile layout:
  equal columns, three equal-height rows, and the focus tile spanning the first
  two left cells.
- View menu does not expose either removed arrangement choice.
- A legacy `ui/multiview_arrangement` value is normalized.
- Diff becomes focus in 3- and 5-tile result layouts.
- Focus pin reorders the focus tile without changing selection order.
- Six-source Diff hide restores the prior multi-view state.

These tests were written through the GitHub connector but have not been executed
in a Windows/PySide6 runtime yet.

## Files changed by the correction

- `src/pixelscope/ui/multi_compare_view.py`
- `tests/ui/test_multiview_arrangements.py`
- `scripts/capture_ui_review.py`
- `docs/ui/README.md`
- `docs/ui/implementation_status.md`
- Obsolete alternate-arrangement captures are scheduled for removal after local
  capture regeneration confirms the fixed layouts.

## Required local validation

Run at minimum:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\ui\test_multiview_arrangements.py -q
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m mypy src
```

Regenerate captures:

```powershell
$env:QT_QPA_PLATFORM = 'offscreen'
.\.venv\Scripts\python.exe scripts\capture_ui_review.py docs\ui
```

Visually inspect `three_image_multiview.png`, `five_image_multiview.png`, and
`six_image_multiview.png`, plus interactive focus-pin behavior in the normal
Windows platform plugin.

## Incomplete / intentionally deferred

- P0-B difference-map LRU cache and metric optimization: not started.
- Difference cache default for P0-B: 512 MiB, constructor/configuration injected,
  no direct QSettings read from the cache implementation.
- P0-C toolbar icon/state work: not started.
- P1-A through P1-C: not started.
- Preferences, image resident cache, preload, and GitHub Release update support
  remain separate future phases.
- Legacy visible A/B and `_compare_pair` behavior remains for the P1-A audit.

## Exact next starting point

1. Fetch and test `fix/p0a-fixed-multiview-layout` on Windows.
2. Report any pytest, Ruff, mypy, or visual-layout failure.
3. Apply a follow-up correction on the same branch if required.
4. Merge the validated P0-A correction.
5. Start **P0-B — absolute difference cache and metrics** from the validated
   correction commit.
