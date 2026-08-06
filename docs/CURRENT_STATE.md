# PixelScope current state

Snapshot date: 2026-08-06
Reference branch: `feature/p1-f-layout-cleanup` / current scoped PR

This document is the first source to read before planning new work. It records
what is implemented, what earlier plans incorrectly describe, and which
remaining items are verified against the current code.

## PR audit

PR #1 through PR #9 were inspected, excluding PR #7 because it is the harness
documentation branch being updated.

| PR | Delivered |
|---|---|
| #1 | Fixed 1–6 image Multi View layouts and removal of user-facing arrangement choices |
| #2 | 512 MiB Difference-map LRU, chunked native metrics, cache diagnostics |
| #3 | PixelScope-owned toolbar icons and action-state behavior |
| #4 | Split-channel loading/state, disabled menu styling, deterministic Diff ordering |
| #5 | Files residency presentation, Statistics terminology/ROI detail, responsive tile headers |
| #6 | Histogram bins/Y modes, compact plot tooltips/titles, bit-depth fixtures |
| #8 | Line Profile reference selection and compact legend refinement |
| #9 | RAW profile model, unpacked alignment/endian handling, MIPI RAW10/12/14, fixtures and tests |
| #10 | Primary-image ordering for all regular Multi Views and atomic Split transitions |
| #11 | Plots persistence/maximize, gesture/shortcut cleanup, and Statistics workspace polish |

## Implemented baseline

### Workspace and selection

- Folder-grouped `File`/`Type` tree with loading, resident, and error state
  icons.
- Ordered selection is the comparison model; Difference selectors are the only
  pair authority.
- Fixed Multi View layouts for one to six source images.
- Every regular Multi View with two through six images exposes a primary flag.
- The first displayed image is the implicit primary. Selecting another primary
  promotes it through `_multi_display_order` without changing Files selection
  order, document IDs, or logical slot badges.
- Two-, four-, and six-image layouts remain equal-sized. Three- and five-image
  layouts enlarge the first, primary tile.
- Split RGB and Bayer channels use loading placeholders and stable action state.
  Transient channel-component tiles retain fixed ordering and do not expose
  primary flags.
- Split Channels transitions apply target geometry before replacement content,
  preventing an observable old-grid intermediate frame.
- Page Up/Page Down folder-pair navigation remains owned by MainWindow
  application shortcuts and works from the Files view and visible image tiles.
- Deterministic Difference placement is preserved in Single and Multi View.

### Analysis

- Statistics for full image and active ROI with explicit pixel terminology.
- Histogram Auto/256/1024/4096 bins; Count, Normalized, and Log count modes.
- Line Profile reference selection for Difference-from-reference mode.
- Reference priority is primary image, active image, then first displayed image.
- Native absolute Difference cache with byte accounting, LRU eviction, and
  chunked metrics.
- Floating Plots geometry persists independently, title-bar double-click
  maximizes/restores, and the selected tab persists through
  `analysis/bottom_tab`.
- Esc clears ROI only; Shift+Esc clears Line Profile only. Ctrl+drag creates
  ROI, Shift+drag creates Line Profile, and Alt+drag creates neither.

### RAW

- Unpacked `uint8`/`uint16`, effective bit depth, endian, and LSB/MSB alignment.
- MIPI RAW10, RAW12, and RAW14 decoding.
- JSON profile migration and same-path reload.
- Deterministic unpacked/packed fixtures and unit, integration, and UI coverage.
- Bayer remains native mosaic analysis; no demosaic preview.

### Resource behavior

- Difference maps use the dedicated 512 MiB byte-budget cache.
- Decoded source images use a reloadable working set with a fixed seven-document
  resident limit.
- The resident-image policy is count-based, not byte-budgeted, and does not
  preload the next folder group.

## Corrected assumptions

- MIPI RAW10/12/14 is implemented; it must not remain listed as future scope.
- P1-B reference selection is complete.
- Plots selected-tab and floating-geometry persistence are complete.
- Image residency is not wholly absent: fixed-count eviction exists.
- P1-D and P1-E are merged as PR #10 and PR #11.
- P1-F removes the compatibility-only Multi View arrangement bridge; a single
  fixed policy does not require a replacement arrangement abstraction.
- Esc/Shift+Esc labels and behavior are complete.

## P1-F current scoped PR

- Removed arrangement constants, registry, runtime fields, actions, setter, and
  render calls from `MultiCompareView` and MainWindow.
- Removed arrangement from `SixImageDiffRestoreState` and its restore path.
- Startup ignores `ui/multiview_arrangement`; save never writes it; Reset
  Workspace Layout removes it when present.
- `_fixed_geometry()` remains the only Multi View geometry policy.
- Focused tests cover one-to-six geometry/stretch, primary ordering, logical
  badges, viewer reuse, synchronized ranges, legacy settings, reset, obsolete
  symbols, and exact six-source Difference restoration.

The active program plan is
[`exec-plans/active/next-phase.md`](exec-plans/active/next-phase.md). It remains
at the required active path with `Status: Complete` because no completed-plan
directory exists. The pinned full suite and manual Windows checks remain
required after local patch application.

## Later backlog

- Preferences UI and restart-applied performance settings.
- Byte-budgeted decoded-image residency and one-group-ahead preload.
- Runtime diagnostics for worker queues, cache budgets, stale-result drops, and
  load failures.
- RAW demosaic UX, algorithm/memory/cache policy, black/white-level processing,
  and profile suggestion.
- Recent files, saved ROI manager, persistent comparison sessions,
  arbitrary-angle sampling, alpha overlay, and additional export formats.
- GitHub Release update checking, PyInstaller/Inno Setup packaging, clean-PC
  validation, code signing, and update strategy.
- Live remote GPU IQA, queue/cancellation, artifact download, and heatmaps.
