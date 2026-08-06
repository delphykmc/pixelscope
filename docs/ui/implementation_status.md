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

1. Persist floating Plots geometry independently.
2. Add title-bar double-click maximize/restore for floating Plots.
3. Rename `Clear ROI / Restore Grid` to `Clear ROI`; Esc already only clears
   ROI.
4. Preserve Shift+Esc line clearing with focused regression tests.
5. Remove the fixed-arrangement compatibility registry and QSettings key.
6. Retain existing selected-tab persistence and add explicit regression
   coverage.

## Performance/settings backlog

- The Difference cache is byte-budgeted and diagnostic-ready.
- Decoded image arrays already have fixed seven-document resident eviction.
- Preferences, restart-applied budgets, byte-budgeted source residency, and
  one-group-ahead preload remain future work.

## Historical correction

The previous version of this file described P1-A as awaiting integration,
listed a temporary patch script, and said P1-B/P1-C were unstarted. Those
statements became invalid after PR #5, #6, #8, and #9 and have been removed.
