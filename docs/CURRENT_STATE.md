# PixelScope current state

Snapshot date: 2026-08-07  
Reference runtime baseline: PR #12 merge commit  
P2-0 branch base: `1f13e85bccf3ef1eab7f27c87c84f798eadfcc2f`

This document records the implementation baseline that new work must use.

## Merge baseline

- P1-D merged as PR #10.
- P1-E merged as PR #11.
- P1-F merged as PR #12.
- PR #12 merge commit and the P2-0 branch base are both
  `1f13e85bccf3ef1eab7f27c87c84f798eadfcc2f`.
- P2-0 is the documentation-only transition PR; the next runtime phase is P2-A.

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
- Canonical PixelScope application/window/taskbar icon and packaged-resource
  foundation.
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

## Active plan

- P1 history: [`exec-plans/completed/p1-d-to-p1-f-workspace-polish.md`](exec-plans/completed/p1-d-to-p1-f-workspace-polish.md)
- P2 active plan: [`exec-plans/active/next-phase.md`](exec-plans/active/next-phase.md)
- Next implementation phase: P2-A — Application identity and Settings foundation.
