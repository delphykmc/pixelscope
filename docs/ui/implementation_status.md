# PixelScope UI/performance iteration status

Snapshot date: 2026-08-06  
Current merged baseline: PR #9 on `main`

## Completed iterations

| Phase/PR | State | Main result |
|---|---|---|
| P0-A / #1 | Complete | Fixed Multi View layouts and focus behavior |
| P0-B / #2 | Complete | Difference LRU and chunked metrics |
| P0-C / #3 | Complete | Toolbar/focus icons and action states |
| P0-D / #4 | Complete | Split loading, disabled menus, Diff ordering |
| P1-A / #5 | Complete | Files, Statistics, responsive headers |
| P1-B1 / #6 | Complete | Histogram modes and plot text |
| P1-B2 / #8 | Complete | Line Profile reference and legends |
| P1-C / #9 | Complete | RAW profile workflow and MIPI decoding |

## Current UI behavior

### Files and workspace

- Files tree exposes File and Type only.
- Residency, loading, and errors are represented by icons and tooltips.
- Ordered selection drives fixed one-to-six-image layouts.
- Difference panel selectors are the only comparison-pair authority.
- Split Channels supports RGB and Bayer placeholders during loading.
- Pinning promotes a document to the first tile without changing selection
  order, but the control is currently visible only for three and five views.

### Analysis

- Statistics uses Pixels and stable ROI detail.
- Histogram has explicit bins and Count/Normalized/Log count modes.
- Line Profile has compact legends and explicit Difference reference.
- Difference uses a 512 MiB native-map LRU with expanded metrics.
- Plots selected tab is persisted through `analysis/bottom_tab`.

### RAW

- Compact profile dialog with storage/container/depth/endian/alignment
  separation.
- Unpacked `uint8`/`uint16` and MIPI RAW10/12/14.
- JSON load/save, legacy migration, confirmation preference, and same-path
  reload.
- Deterministic grayscale/Bayer fixtures and regression tests.
- Demosaic is intentionally excluded.

## Verified remaining UI work

### P1-D — Multi View ordering and Split transition polish

1. Show the pin/order control for two through six displayed documents.
2. Keep equal geometry in two/four/six views while allowing first-tile
   promotion.
3. Keep enlarged first-tile geometry in three/five views.
4. Update focus-only tooltip wording to describe first-tile ordering.
5. Remove the visible two-step Bayer/RGB split to GRAY transition.
6. Arrange the target viewer geometry before rebinding documents and batch the
   operation into one repaint.
7. Preserve loading placeholders, viewer reuse, Difference priority,
   synchronization, selection order, and logical IDs.

### P1-E — Plots workspace completion

1. Persist floating Plots geometry independently.
2. Add title-bar double-click maximize/restore for floating Plots.
3. Rename `Clear ROI / Restore Grid` to `Clear ROI`; Esc already only clears
   ROI.
4. Preserve Shift+Esc line clearing with focused regression tests.
5. Retain existing selected-tab persistence and add explicit regression
   coverage.

### P1-F — compatibility cleanup

1. Remove the fixed-arrangement compatibility registry and QSettings key.
2. Remove arrangement-dependent startup/reset/restore code.
3. Preserve one-to-six geometry and six-source Difference restoration.

## Split transition cause analysis

With Split Channels enabled, `_effective_layout()` deliberately keeps a
one-document result in the Multi View container with capacity four. For GRAY,
`_split_display_documents()` correctly returns `[document]` because no channel
split applies.

The visual flash occurs lower in the view layer: `MultiCompareView.set_documents()`
assigns the GRAY document while the previous 2x2 arrangement and visibility are
still active, then invokes `_arrange_viewers(1)`. Qt can paint the intermediate
state, so the first tile briefly appears at quarter size before expanding.

The intended fix is an atomic batch update, not a change to the final layout
policy:

- compute the target count and placement first;
- update layout/visibility before content binding;
- suppress intermediate painting during the batch;
- bind the final documents once;
- restore updates and request one repaint.

## Performance/settings backlog

- The Difference cache is byte-budgeted and diagnostic-ready.
- Decoded image arrays already have fixed seven-document resident eviction.
- Preferences, restart-applied budgets, byte-budgeted source residency, and
  one-group-ahead preload remain future work.

## Historical correction

The previous version of this file described P1-A as awaiting integration,
listed a temporary patch script, and said P1-B/P1-C were unstarted. Those
statements became invalid after PR #5, #6, #8, and #9 and have been removed.
