# PixelScope current state

Snapshot date: 2026-08-07  
P2-A1 / PR #14 merge commit and P2-A2 branch base:
`c3ddb91f4644eae981d4683fe42d9b8219ad76fe`

This document records the implementation baseline that new work must use.

## Merge baseline

- P1-D merged as PR #10.
- P1-E merged as PR #11.
- P1-F merged as PR #12.
- P2-0 merged as PR #13 at
  `52daa63425a286e370aa5ef36f59ba51a8acd565`.
- P2-A1 merged as PR #14 at
  `c3ddb91f4644eae981d4683fe42d9b8219ad76fe`.
- P2-A2 is implemented on `feature/p2-a-settings-foundation`; merge and owner
  validation remain pending in the active PR.

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
- The RAW JSON confirmation preference is now an `ApplicationSettings` value.
  Legacy `raw/dont_show_json_profiles` values are migrated to the versioned
  application-settings namespace.
- Native grayscale/Bayer analysis without demosaic.

### Runtime resources and settings

- P2-A1 supplies canonical SVG/PNG/ICO resources, reproducible asset generation,
  CWD-independent package lookup, and the Windows source-run AppUserModelID
  `PixelScope.PixelScope` before `QApplication` creation.
- `DifferenceMapCache` remains a persistence-free byte-budgeted LRU.
- `ApplicationSettings` is the frozen typed model for persisted user preferences.
  P2-A2 currently owns `dont_show_raw_json_profiles` and
  `difference_cache_mib`.
- `SettingsRepository` owns defaults, schema migration, validation, save/reset,
  invalid-state recovery, and future-schema compatibility; `QSettingsAdapter`
  owns raw QSettings keys.
- Settings schema version 1 uses `settings/schema_version`,
  `settings/general/dont_show_raw_json_profiles`, and
  `settings/performance/difference_cache_mib`.
- Difference cache preference defaults to 512 MiB and accepts 64–8192 MiB.
- Application startup converts persisted MiB into an immutable
  `PerformanceSettings.difference_cache_bytes` snapshot and injects that value
  through `MainWindow` into `DifferencePanel` and `DifferenceMapCache`.
- Runtime changes to the Difference-cache preference are saved for the next
  launch; an existing cache budget is not mutated live.
- `Edit > Settings...` exposes General and Performance settings. The existing
  File-menu RAW preference remains and shares the same typed setting.
- `Reset Settings` resets only schema-owned application preferences. Workspace
  geometry, dock/splitter state, last directory, and unrelated QSettings keys
  remain owned by their existing persistence path and are not reset.
- Unknown future settings schemas are not rewritten; the current application
  uses safe defaults and treats application settings as read-only compatibility
  state.
- Decoded-source residency remains a reloadable fixed seven-document,
  count-based policy owned by `MainWindow`; P2-B replaces that policy.
- The dedicated image-load pool is bounded at two workers; the shared numeric
  pool is bounded at four.

## Not implemented

- Byte-budgeted decoded-source setting and `ResidencyManager` (P2-B).
- One-group-ahead preload (P2-C).
- Runtime diagnostics dialog/snapshot, Copy Diagnostics, or export (P2-D).
- P3–P7 workflow, RAW processing expansion, remote/authentication, and
  distribution work.

## Validation evidence

The repository owner recorded the full automated validation contract as passed
for P1-D, P1-E, P1-F, and final P2-A1. P2-A1 also has owner-confirmed application
runtime and Windows taskbar identity evidence.

For P2-A2, implementation and focused regression tests are present in the active
branch. Full repository validation and the manual Windows matrix must be recorded
in the P2-A2 PR before merge; this document does not pre-claim those checks.

## Active plan

- P1 history: [`exec-plans/completed/p1-d-to-p1-f-workspace-polish.md`](exec-plans/completed/p1-d-to-p1-f-workspace-polish.md)
- P2 active plan: [`exec-plans/active/next-phase.md`](exec-plans/active/next-phase.md)
- P2-A1: complete; merged as PR #14.
- P2-A2: active implementation on `feature/p2-a-settings-foundation`.
- Next slice after P2-A2 merge: P2-B — byte-budgeted decoded-source residency.
