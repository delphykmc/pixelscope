# PixelScope current state

Snapshot date: 2026-08-06  
Reference branch: `main` after merged PR #9

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
| #3 | PixelScope-owned toolbar/focus icons and action-state behavior |
| #4 | Split-channel loading/state, disabled menu styling, deterministic Diff ordering |
| #5 | Files residency presentation, Statistics terminology/ROI detail, responsive tile headers |
| #6 | Histogram bins/Y modes, compact plot tooltips/titles, bit-depth fixtures |
| #8 | Line Profile reference selection and compact legend refinement |
| #9 | RAW profile model, unpacked alignment/endian handling, MIPI RAW10/12/14, fixtures and tests |

PR #1–#6, #8, and #9 contain no GitHub review comments or unresolved review
threads. The remaining work below comes from explicit PR scope exclusions,
outdated plans, and direct code/document comparison.

## Implemented baseline

### Workspace and selection

- Folder-grouped `File`/`Type` tree with loading, resident, and error state
  icons.
- Ordered selection is the comparison model; Difference selectors are the only
  pair authority.
- Fixed Multi View layouts for one to six source images, including focus
  promotion for three and five images.
- Split RGB and Bayer channels with loading placeholders and stable action
  state.
- Deterministic Difference placement in Single and Multi View.

### Analysis

- Statistics for full image and active ROI with explicit pixel terminology.
- Histogram Auto/256/1024/4096 bins; Count, Normalized, and Log count modes.
- Line Profile reference selection for Difference-from-reference mode.
- Native absolute Difference cache with byte accounting, LRU eviction, and
  chunked metrics.
- Plots selected tab is already persisted through `analysis/bottom_tab`.

### RAW

- Unpacked `uint8`/`uint16`, effective bit depth, endian, and LSB/MSB alignment.
- MIPI RAW10, RAW12, and RAW14 decoding.
- JSON profile migration and same-path reload.
- Deterministic unpacked/packed fixtures and unit, integration, and UI coverage.
- Bayer remains native mosaic analysis; no demosaic preview.

### Resource behavior

- Difference maps use the dedicated 512 MiB byte-budget cache.
- Decoded source images already use a reloadable working set with a fixed
  seven-document resident limit.
- The resident-image policy is count-based, not byte-budgeted, and does not
  preload the next folder group.

## Corrected assumptions

- MIPI RAW10/12/14 is implemented; it must not remain listed as future scope.
- P1-B reference selection is complete.
- Last selected Plots tab persistence is already implemented.
- Image residency is not wholly absent: fixed-count eviction exists.
- The obsolete Multi View arrangement setting still exists only as a
  compatibility bridge and should be removed in a bounded cleanup.
- Esc already clears ROI only, but the menu text still says
  `Clear ROI / Restore Grid`.

## Verified immediate backlog

### P1-D — workspace completion and cleanup

1. Persist floating Plots geometry independently and verify restore behavior.
2. Add title-bar double-click maximize/restore for floating Plots.
3. Rename `Clear ROI / Restore Grid` to `Clear ROI`; preserve Esc and
   Shift+Esc behavior with focused tests.
4. Remove the fixed-arrangement compatibility registry, field, and QSettings
   key after migrating startup/reset/restore tests.
5. Keep existing `analysis/bottom_tab` persistence; add regression coverage
   rather than reimplementing it.

The active plan is
[`exec-plans/active/next-phase.md`](exec-plans/active/next-phase.md).

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

## Documentation debt resolved by PR #7

The previous `README.md`, `PRODUCT_SPEC.md`, `ARCHITECTURE.md`, `ROADMAP.md`,
`USER_GUIDE.md`, and UI status notes described packed RAW and P1-B/P1-C work as
future or unstarted. PR #7 updates those sources and adds a mechanical
documentation contract so the same drift is detectable.
