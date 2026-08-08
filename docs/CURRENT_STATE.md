# PixelScope current state

Snapshot date: 2026-08-08  
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
- P2-A2 is implemented on `feature/p2-a-settings-foundation`; merge remains
  pending while the final schema-v3 runtime-integration review fixes are
  revalidated.

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
- Difference Threshold and Gain are persisted General settings. Persisted values
  initialize the Difference panel at startup and Settings saves update the live
  panel immediately without restart.

### RAW

- Unpacked uint8/uint16 with effective depth, endian, stride, offset, and
  LSB/MSB alignment.
- MIPI RAW10/12/14.
- JSON profile load/save, migration, confirmation preference, and same-path
  reload.
- The persistent RAW JSON confirmation preference is an `ApplicationSettings`
  value exposed through **Settings > General**, not the File menu. Legacy
  `raw/dont_show_json_profiles` values are migrated to the versioned namespace.
- The RAW confirmation dialog may still set the same preference through its
  explicit don't-show-again choice; that update preserves all other schema-v3
  settings.
- `Require Exact RAW File Size` is a General setting. Disabled allows trailing
  bytes while still rejecting undersized files; enabled requires exact byte
  equality. `MainWindow` passes the setting into RAW load workers and applies the
  same rule before auto-approving a JSON sidecar.
- Native grayscale/Bayer analysis without demosaic.

### Runtime resources and settings

- P2-A1 supplies canonical SVG/PNG/ICO resources, reproducible asset generation,
  CWD-independent package lookup, and the Windows source-run AppUserModelID
  `PixelScope.PixelScope` before `QApplication` creation.
- `DifferenceMapCache` remains a persistence-free byte-budgeted LRU.
- `ApplicationSettings` is the frozen typed model for persisted user preferences.
  P2-A2 owns RAW confirmation, exact RAW file-size validation, default
  Open/Export folders, Difference Threshold/Gain defaults, and Difference Map
  Cache MiB.
- `SettingsRepository` owns defaults, schema migration, validation, save/reset,
  invalid-state recovery, and future-schema compatibility; `QSettingsAdapter`
  owns raw application-setting keys.
- Settings schema version 3 uses:
  - `settings/schema_version`
  - `settings/general/dont_show_raw_json_profiles`
  - `settings/general/require_exact_raw_file_size`
  - `settings/files/default_open_directory`
  - `settings/files/default_export_directory`
  - `settings/analysis/difference_threshold`
  - `settings/analysis/difference_gain`
  - `settings/performance/difference_cache_mib`
- Schema v2 migrates to v3 by preserving its existing values and adding exact RAW
  validation plus Difference Threshold/Gain defaults. Schema v1 and the legacy
  RAW key are also migrated into the current model.
- `Edit > Settings...` uses left-side **General / Files / Performance** page
  navigation with a flat VS Code-inspired content hierarchy.
- Blank default Open/Export locations preserve the existing last-used-folder
  behavior. A configured existing location only seeds the corresponding file
  dialog and applies without restart.
- Difference Map Cache defaults to 512 MiB and accepts 64–8192 MiB.
- Application startup converts persisted MiB into immutable
  `PerformanceSettings.difference_cache_bytes` and injects it through
  `MainWindow` into `DifferencePanel` and `DifferenceMapCache`.
- Difference Map Cache edits are saved for the next launch; an existing cache
  budget is not mutated live.
- `Reset Settings` resets only schema-owned application preferences. Workspace
  geometry, dock/splitter state, remembered last directory, and unrelated
  QSettings keys remain independently owned.
- Dock geometry, splitter sizes, current layout, and Plots visibility are not
  duplicated as application settings because exact workspace persistence is
  already authoritative for those values.
- Unknown future settings schemas are not rewritten; the current application
  uses safe defaults and treats application settings as read-only compatibility
  state.
- Decoded-source residency remains a reloadable fixed seven-document,
  count-based policy owned by `MainWindow`; P2-B replaces that policy.
- The dedicated image-load pool is bounded at two workers; the shared numeric
  pool is bounded at four.

## Not implemented

- Byte-budgeted decoded-source setting and `ResidencyManager` (P2-B). Its budget
  will extend the Performance Settings page.
- One-group-ahead preload (P2-C). Its preference will extend Performance when
  that lifecycle exists.
- Runtime diagnostics dialog/snapshot, Copy Diagnostics, or export (P2-D).
- Broader export-format/naming preferences; only Statistics CSV currently exists.
- P3–P7 workflow, RAW processing expansion, remote/authentication, and
  distribution work.
- Windows startup white-frame polish. There is no intentional splash/pre-render
  path; investigation is deferred until the major phases are complete.

## Validation evidence

The repository owner recorded the full automated validation contract as passed
for P1-D, P1-E, P1-F, final P2-A1, and the P2-A2 head before the final runtime
integration review. That prior result remains useful evidence, but it predates
the final merge-blocker fixes for exact RAW propagation, Difference defaults,
partial-settings preservation, and schema-v3 documentation alignment.

A fresh full validation run is therefore required on the new P2-A2 head before
merge. No post-fix full-suite result is pre-claimed here.

## Active plan

- P1 history: [`exec-plans/completed/p1-d-to-p1-f-workspace-polish.md`](exec-plans/completed/p1-d-to-p1-f-workspace-polish.md)
- P2 active plan: [`exec-plans/active/next-phase.md`](exec-plans/active/next-phase.md)
- P2-A1: complete; merged as PR #14.
- P2-A2: final runtime-integration fixes and revalidation on
  `feature/p2-a-settings-foundation`.
- Next slice after P2-A2 merge: P2-B — byte-budgeted decoded-source residency.
