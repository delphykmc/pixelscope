# PixelScope UI/performance iteration status

Snapshot date: 2026-08-06
Current merged baseline: PR #11 on `main`

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
| P1-D / #10 | Complete | Primary ordering, atomic Split transitions, folder navigation |
| P1-E / #11 | Complete | Plots persistence, gestures, Statistics workspace |
| P1-F / current PR | Implemented | Fixed-layout compatibility cleanup |

## Current UI behavior

### Files and workspace

- Files tree exposes File and Type only.
- Residency, loading, and errors are represented by icons and tooltips.
- Ordered selection drives fixed one-to-six-image layouts.
- Difference panel selectors are the only comparison-pair authority.
- Split Channels supports RGB and Bayer placeholders during loading.
- Every regular two-to-six-image Multi View exposes a primary flag. Primary
  promotion preserves Files order, logical badges, viewer identity, and
  synchronized ranges.
- Two/four/six views remain equal-sized; three/five enlarge the first tile.
- Multi View exposes no arrangement menu or runtime arrangement state;
  `_fixed_geometry()` is the geometry contract.

### Analysis

- Statistics uses Pixels and stable ROI detail.
- Histogram has explicit bins and Count/Normalized/Log count modes.
- Line Profile has compact legends and explicit Difference reference.
- Difference uses a 512 MiB native-map LRU with expanded metrics.
- Floating Plots geometry and the selected tab persist; title-bar
  double-click maximizes/restores.
- Esc clears ROI, Shift+Esc clears Line Profile, Ctrl+drag creates ROI,
  Shift+drag creates Line Profile, and Alt+drag creates neither.

### RAW

- Compact profile dialog with storage/container/depth/endian/alignment
  separation.
- Unpacked `uint8`/`uint16` and MIPI RAW10/12/14.
- JSON load/save, legacy migration, confirmation preference, and same-path
  reload.
- Deterministic grayscale/Bayer fixtures and regression tests.
- Demosaic is intentionally excluded.

## P1-D–P1-F workspace polish status

- P1-D primary ordering, equal/enlarged geometry, atomic Split replacement, and
  folder navigation are complete in PR #10.
- P1-E Plots persistence/maximize, gestures, shortcuts, and Statistics workspace
  behavior are complete in PR #11.
- P1-F removes arrangement constants, registry, runtime fields, menu/actions,
  setter, startup/save, render, and six-source restore coupling.
- Startup ignores legacy `ui/multiview_arrangement`; save never writes it;
  workspace reset removes it when present.
- Focused P1-F coverage verifies geometry/stretch, primary promotion contracts,
  legacy settings, reset, obsolete symbol absence, and exact six-source restore.
- The pinned full validation suite and manual Windows checks remain required
  after local patch application.

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

Earlier snapshots described P1-D/P1-E as pending and the primary control as
limited to three/five views. PR #10 and PR #11 completed those items. P1-F now
removes the compatibility-only arrangement bridge without adding a replacement
layout abstraction.
