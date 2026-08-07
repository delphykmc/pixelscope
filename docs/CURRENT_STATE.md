# PixelScope current state

Snapshot date: 2026-08-07  
PR #13 merge commit and PR #14 branch base:
`52daa63425a286e370aa5ef36f59ba51a8acd565`  
Runtime code baseline before PR #14:
`1f13e85bccf3ef1eab7f27c87c84f798eadfcc2f`

This document records the implementation baseline that new work must use.

## Merge baseline

- P1-D merged as PR #10.
- P1-E merged as PR #11.
- P1-F merged as PR #12.
- P2-0 merged as PR #13 at
  `52daa63425a286e370aa5ef36f59ba51a8acd565`.
- PR #13 changed durable documentation only, so the runtime code baseline before
  PR #14 remains the PR #12 merge commit
  `1f13e85bccf3ef1eab7f27c87c84f798eadfcc2f`.
- P2-A is split into P2-A1 identity/resources and P2-A2 settings foundation.

## Implemented baseline

### Workspace and selection

- Folder-grouped Files tree with loading, resident, and error indicators.
- Ordered selection is the comparison model; Difference selectors own the pair.
- Fixed one-to-six-image Multi View geometry.
- Every regular two-to-six-image Multi View exposes primary behavior.
- Primary promotion changes display order without changing Files order, document
  IDs, logical badges, viewer identity, or synchronized ranges.
- A preserve-view primary promotion skips redundant viewer removal/reinsertion
  when the document count and fixed geometry are unchanged, preventing
  resize-driven range changes.
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

- PR #14 delivers the P2-A1 identity/resource foundation.
- Canonical icon assets are colocated at
  `src/pixelscope/assets/icons/pixelscope.{svg,png,ico}`.
- The approved artwork is a transparent standalone photograph-and-magnifier mark
  with enlarged pixels inside the lens and a restrained amber accent. Omitting a
  full-canvas plate lets the mark occupy more of the Windows taskbar icon area
  with higher contrast and clearer image-analysis semantics.
- The SVG is the editable vector source, the transparent 256 px PNG is the Qt
  runtime asset, and the ICO contains transparent 16, 20, 24, 32, 40, 48, 64,
  128, and 256 px frames.
- `scripts/generate_icon_assets.py` uses dev-pinned `resvg_py` and Pillow to
  reproduce the owner-validated PNG/ICO derivatives from the SVG. The previous
  Qt SVG rasterization path is no longer authoritative.
- `generate_icon_assets.py --check` generates both derivatives into a temporary
  directory, requires exact byte equality with the checked-in PNG/ICO, and
  removes the temporary output before returning.
- `tests/unit/test_icon_assets.py` verifies the same reproduction contract and
  confirms that no temporary generated files remain after the test.
- Application bootstrap reads the PNG through `importlib.resources`; lookup is
  independent of the current working directory and source-tree absolute paths.
- Windows source runs assign `PixelScope.PixelScope` before `QApplication`
  creation, then assign the canonical icon to both `QApplication` and the main
  window so the running Taskbar entry does not retain the Python process identity.
- SVG, PNG, and ICO files are declared as setuptools package data.
- Executable, shortcut, installer, and final packaged Windows shell identity
  binding remain P7 work.
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

- P2-A2 typed `ApplicationSettings`, `SettingsRepository`, QSettings adapter,
  migration, validation, reset, Settings dialog, restart-required UI, and
  Difference-cache startup injection.
- Byte-budgeted decoded-source setting and residency manager.
- One-group-ahead preload.
- Runtime diagnostics dialog/snapshot, Copy Diagnostics, or export.
- P3–P7 workflow, RAW processing, remote/authentication, and distribution work.

## Validation evidence

The repository owner recorded the full automated validation contract as passed
for P1-D, P1-E, and P1-F. P1-D and P1-E also have recorded manual Windows checks.
P1-F manual Windows evidence was not re-verified during P2-0 and is not claimed
as passed by that documentation PR.

The repository owner confirmed the P2-0 documentation checker and docs contract
test passed locally.

For PR #14, the repository owner confirmed after the runtime fixes that the
application behavior works and the Windows taskbar uses the PixelScope identity
rather than the Python icon. The owner-generated PNG/ICO are now treated as the
reference derivatives; the generator and focused unit test must reproduce them
exactly from the SVG before the draft is marked ready. Exact status remains in PR
#14.

## Active plan

- P1 history: [`exec-plans/completed/p1-d-to-p1-f-workspace-polish.md`](exec-plans/completed/p1-d-to-p1-f-workspace-polish.md)
- P2 active plan: [`exec-plans/active/next-phase.md`](exec-plans/active/next-phase.md)
- P2-A1: application identity/resource foundation, delivered by PR #14.
- Next implementation slice after PR #14: P2-A2 — settings foundation and
  Difference-cache startup injection.
