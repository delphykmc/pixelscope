# PixelScope current state

Snapshot date: 2026-08-07  
Current `main` / P2-A branch base: `52daa63425a286e370aa5ef36f59ba51a8acd565`  
Runtime code baseline: PR #12 merge commit `1f13e85bccf3ef1eab7f27c87c84f798eadfcc2f`

This document records the implementation baseline that new work must use.

## Merge baseline

- P1-D merged as PR #10.
- P1-E merged as PR #11.
- P1-F merged as PR #12.
- P2-0 merged as PR #13 at
  `52daa63425a286e370aa5ef36f59ba51a8acd565`; that commit is the P2-A branch base.
- PR #13 changed durable documentation only, so the runtime code baseline remains
  the PR #12 merge commit `1f13e85bccf3ef1eab7f27c87c84f798eadfcc2f`.
- The current runtime phase is P2-A.

## Implemented baseline

### Workspace and selection

- Folder-grouped Files tree with loading, resident, and error indicators.
- Ordered selection is the comparison model; Difference selectors own the pair.
- Fixed one-to-six-image Multi View geometry.
- Every regular two-to-six-image Multi View exposes primary behavior.
- Primary promotion changes display order without changing Files order, document
  IDs, logical badges, viewer identity, or synchronized ranges.
- Two/four/six views remain equal; three/five enlarge the first tile.
- Split RGB/Bayer component order is fixed and transitions are applied atomically.
- Page Up/Page Down folder-pair navigation is implemented.

### Analysis

- Full-image and Active ROI Statistics.
- Histogram Auto/256/1024/4096 bins and Count/Normalized/Log count modes.
- Line Profile absolute, normalized, and Difference-from-reference modes.
- Reference priority: primary image, active image, then first displayed image.
- Floating Plots geometry and selected tab persistence; title double-click
  maximize/restore.
- Esc clears ROI; Shift+Esc clears Line Profile. Ctrl+drag creates ROI;
  Shift+drag creates Line Profile; Alt+drag creates neither.

### RAW

- Unpacked uint8/uint16 with effective depth, endian, stride, offset, and
  LSB/MSB alignment.
- MIPI RAW10/12/14.
- JSON profile load/save, migration, confirmation preference, and same-path
  reload.
- Native grayscale/Bayer analysis without demosaic.

### Runtime resources

- Canonical icon assets are colocated at
  `src/pixelscope/assets/icons/pixelscope.{svg,png,ico}`. The SVG is the editable
  source, the 256 px indexed-color PNG is the Qt runtime asset, and the ICO contains
  16–256 px Windows frames.
- Application bootstrap reads the PNG through `importlib.resources` and assigns
  it to `QApplication`; lookup is independent of the current working directory.
- SVG, PNG, and ICO files are declared as setuptools package data.
- `DifferenceMapCache` is a byte-budgeted LRU with a 512 MiB default.
- Difference diagnostics expose `used_bytes`, `budget_bytes`, and `entry_count`.
- `DifferencePanel` has a constructor injection seam for its cache budget.
- Frozen `PerformanceSettings` exists with only `difference_cache_bytes`, but
  application bootstrap does not load or inject it; `MainWindow` uses the
  `DifferencePanel` default.
- Decoded-source residency exists as a reloadable fixed seven-document,
  count-based policy owned by `MainWindow`.
- The current protected set is based on visible documents and active load
  targets; selected and analysis documents are not yet explicit policy inputs.
- The source residency policy is not byte-budgeted and is distinct from the
  Difference cache.
- Native source arrays and previews coexist in `ImageDocument`; source residency
  accounting is therefore not total process memory.
- The dedicated image-load pool is bounded at two workers; the shared numeric
  pool is bounded at four.
- Normal-load stale-result handling primarily uses target document ID,
  `_load_tokens`, the load-worker registry, and cancelled-worker rejection.

## Not implemented

- Settings dialog, typed application settings repository, migration service, and
  restart-required UI.
- Byte-budgeted decoded-source setting and residency manager.
- One-group-ahead preload.
- Runtime diagnostics dialog/snapshot, Copy Diagnostics, or export.
- P3–P7 workflow, RAW processing, remote/authentication, and distribution work.

## Validation evidence

The repository owner recorded the full automated validation contract as passed
for P1-D, P1-E, and P1-F. P1-D and P1-E also have recorded manual Windows checks.
P1-F manual Windows evidence was not re-verified during P2-0 and is not claimed
as passed by this documentation PR.

The repository owner confirmed the P2-0 documentation checker and docs contract
test passed locally.

The P2-A identity slice remains a draft until the full repository contract and
manual Windows title-bar, Alt+Tab, and taskbar checks are recorded.

## Active plan

- P1 history: [`exec-plans/completed/p1-d-to-p1-f-workspace-polish.md`](exec-plans/completed/p1-d-to-p1-f-workspace-polish.md)
- P2 active plan: [`exec-plans/active/next-phase.md`](exec-plans/active/next-phase.md)
- Current implementation phase: P2-A — Application identity and Settings foundation.
- The icon/resource slice is present; typed settings and Difference-cache startup
  injection remain to complete P2-A.
