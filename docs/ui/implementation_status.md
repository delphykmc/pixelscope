# PixelScope UI/performance iteration status

## Baseline

- Baseline commit: `ea64b1d8fda331e3f85dbfa0181d772974358e74`
- Current phase: **P0-A — selectable multi-view arrangement**
- Phase state: **complete; ready for local commit**
- Runtime constraints retained: CPython 3.10, current PySide6 binding, and future
  PyInstaller 5.7 `onedir` compatibility.

## Completed in P0-A

- Added two fixed multi-view arrangements:
  - `Top Focus · 2 Columns` (default)
  - `Left Focus · 3 Columns`
- Added exclusive radio actions under the View menu.
- Persisted the selection with `ui/multiview_arrangement` and included it in
  workspace reset behavior.
- Implemented the specified 1–6 tile placements and 3/5-tile focus ratios.
- Limited focus-pin visibility to 3- and 5-tile layouts.
- Reused the existing six `ImageViewer` instances when switching arrangement;
  no document reload or viewer recreation occurs.
- Preserved focus, active tile, zoom/pan, selection order, cursor graphics,
  ROI, and line-profile overlays across arrangement changes.
- Made Diff the initial focus for 2-source/3-tile and 4-source/5-tile results.
- Kept 6-source + Diff as Diff-only Single View and restored the prior layout
  mode, arrangement, focus, active document, page indices, display order, and
  synchronized view range when Diff is hidden.

## Incomplete / intentionally deferred

- P0-B difference-map LRU cache and metric optimization: not started.
- P0-C toolbar icon/state work: not started.
- P1-A through P1-C: not started.
- Legacy visible A/B and `_compare_pair` behavior remains for the required P1-A
  audit; it was not altered during P0-A.

## Changed files

- `src/pixelscope/app/main_window.py`
- `src/pixelscope/ui/multi_compare_view.py`
- `tests/ui/test_multiview_arrangements.py`
- `tests/ui/test_ui_smoke.py`
- `scripts/capture_ui_review.py`
- `docs/ui/README.md`
- `docs/ui/implementation_status.md`
- P0-A captures listed below.

## Tests and results

- Targeted P0-A UI suite: `21 passed`
- Full pytest suite: `107 passed`
- Geometry coverage: both arrangements at every tile count from 1 through 6.
- State coverage: no-reload arrangement switch, QSettings restore, 3/5-tile
  Diff focus, and exact 6-source Diff workspace restore.
- Ruff check and format check: passed (`61 files already formatted`).
- mypy: passed (`42 source files`, no issues).
- `pip check`: passed (no broken requirements).

## Capture paths

- `docs/ui/three_image_multiview.png`
- `docs/ui/five_image_multiview.png`
- `docs/ui/six_image_multiview.png`
- `docs/ui/three_image_left_focus.png`
- `docs/ui/five_image_left_focus.png`
- `docs/ui/six_image_left_focus.png`

The captures were visually inspected for focus span, raster order, unused space,
and tile-header clipping.

## Newly discovered issues

- No new functional blocker was found in P0-A.
- Offscreen capture text rendering depends on the fonts available to the Windows
  capture environment; geometry and image content remain suitable for layout QA.

## Exact next starting point

Start **P0-B — absolute difference cache and metrics** from the P0-A commit.
First introduce one centralized default 512 MiB performance setting and a
dedicated byte-budget LRU cache class, then replace `DifferencePanel._map_cache`
without changing the existing Absolute/Mask UI or order-independent pair keys.
Do not begin P0-C until P0-B tests, captures (if affected), status update, and
independent local commit are complete.
