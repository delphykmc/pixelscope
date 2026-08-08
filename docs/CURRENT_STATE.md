# PixelScope current state

Snapshot date: 2026-08-09
P2-C / PR #17 merge commit and P2-D branch base:
`812982dacdecca155f7b53ab42ef2bd9fba68a77`

This document records the implementation baseline that new work must use.

## Merge baseline

- P1-D merged as PR #10.
- P1-E merged as PR #11.
- P1-F merged as PR #12.
- P2-0 merged as PR #13 at
  `52daa63425a286e370aa5ef36f59ba51a8acd565`.
- P2-A1 merged as PR #14 at
  `c3ddb91f4644eae981d4683fe42d9b8219ad76fe`.
- P2-A2 merged as PR #15 at
  `1869764a74b01cebebaf8fa915b11a2a696be6cb`.
- P2-B merged as PR #16 at
  `453b718535bdbdce2a9225c01f6144d7f2df40b0`.
- P2-C merged as PR #17 at
  `812982dacdecca155f7b53ab42ef2bd9fba68a77`.
- P2-D is active on `feature/p2-d-runtime-diagnostics`.

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
- Page Up/Page Down atomically moves a registered one-to-six-folder selection by
  one Folder Position. Left/Right moves within the selected-image set, while
  Up/Down remains native Files-tree row navigation.

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
  explicit don't-show-again choice; that update preserves all other schema-v5
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
  Cache MiB. P2-B adds Decoded Source Memory MiB and P2-C adds preload enablement.
- `SettingsRepository` owns defaults, schema migration, validation, save/reset,
  invalid-state recovery, and future-schema compatibility; `QSettingsAdapter`
  owns raw application-setting keys.
- Settings schema version 5 uses:
  - `settings/schema_version`
  - `settings/general/dont_show_raw_json_profiles`
  - `settings/general/require_exact_raw_file_size`
  - `settings/files/default_open_directory`
  - `settings/files/default_export_directory`
  - `settings/analysis/difference_threshold`
  - `settings/analysis/difference_gain`
  - `settings/performance/difference_cache_mib`
  - `settings/performance/source_residency_mib`
  - `settings/performance/preload_enabled`
- Schema v4 migrates directly to v5 by adding enabled preload while preserving
  every v4 application preference and unrelated/workspace key.
- Schema v3 migrates directly to v5. Difference-cache values valid in the v3
  64–8192 MiB range are preserved up to 1280 MiB and clamped to 1280 MiB above
  that new maximum; malformed or genuinely invalid values use the new default.
  The migration adds the 256 MiB source-residency default and preserves unrelated
  keys. Schema v2/v1 and the legacy RAW key continue to migrate forward.
- `Edit > Settings...` uses left-side **General / Files / Performance** page
  navigation with a flat VS Code-inspired content hierarchy.
- Blank default Open/Export locations preserve the existing last-used-folder
  behavior. A configured existing location only seeds the corresponding file
  dialog and applies without restart.
- Difference Map Cache defaults to 128 MiB and accepts 64–1280 MiB.
- Decoded Source Memory defaults to 256 MiB, accepts 128–2560 MiB, and uses
  128 MiB UI increments.
- When physical RAM is detected, Settings accepts a combined image-memory budget
  up to 50% of RAM. Above-limit saves are rejected without changing either input.
  Unknown RAM falls back to product bounds only. This is a conservative
  configuration guard, not an out-of-memory guarantee.
- Application startup converts persisted MiB into immutable
  `PerformanceSettings.difference_cache_bytes` and
  `PerformanceSettings.source_residency_bytes`, and snapshots preload enablement.
  `MainWindow` injects the former
  into `DifferencePanel`/`DifferenceMapCache` and the latter into
  `ResidencyManager`.
- Both budget edits and preload enablement are saved for the next launch;
  existing runtime cache/manager/controller state is not mutated live.
- `Reset Settings` resets only schema-owned application preferences. Workspace
  geometry, dock/splitter state, remembered last directory, and unrelated
  QSettings keys remain independently owned.
- Dock geometry, splitter sizes, current layout, and Plots visibility are not
  duplicated as application settings because exact workspace persistence is
  already authoritative for those values.
- Unknown future settings schemas are not rewritten; the current application
  uses safe defaults and treats application settings as read-only compatibility
  state.
- `ResidencyManager` owns exact native `ImageDocument.source.nbytes` accounting,
  deterministic LRU order, protected eviction planning, and
  `budget_bytes`/`used_bytes`/`resident_count`/`over_budget_bytes` diagnostics.
- `MainWindow` protects visible, selected, active/analysis, current Difference
  pair, and active load-target registered sources. Protected bytes may exceed
  the soft budget; an oversized required source is retained without load/evict
  thrash.
- Eviction releases source and preview, clears Statistics/Histogram and
  source-dependent channel views, updates the Files residency state, and marks
  the document pending for the existing tokenized normal-load path. Difference
  maps remain independently owned and are not evicted solely for source-budget
  pressure.
- The dedicated image-load pool is bounded at two workers; the shared numeric
  pool is bounded at four. A separate preload pool is bounded at one worker, so
  speculative decode cannot occupy a normal-load slot.
- Pure-core `FolderNavigationPlan` is the shared PageUp/PageDown and preload
  prediction authority over registered `_folder_documents` sequences.
- Pure-core `PreloadController` owns exactly one next-position plan (zero to six
  targets), request generation, active/completed state, and bounded counters.
  Preload starts only after foreground loads become idle and never scans or
  auto-registers filesystem siblings.
- Navigation or selection replacement invalidates the old plan and requests
  cancellation. Correctness relies on plan/document generation, path/profile,
  exact-RAW-policy, and normal-load-token validation before result application.
  A normal load never waits for speculative work; short duplicate decode is
  allowed and late preload results are dropped. Cancellation de-duplication state
  exists only for an active worker request and is discarded on worker completion.
- Valid preload results become ordinary native source residency, receive no
  special protection, and may be evicted immediately under source-budget pressure.
  Speculative failure is silent and leaves normal retry available.
- Frozen Qt-free `RuntimeDiagnosticsSnapshot` values aggregate exact source,
  Difference-cache, foreground/preload worker, preload counter, foreground stale
  drop, and bounded recent failure state. `MainWindow.runtime_diagnostics_snapshot()`
  reads existing cheap owners without touching either LRU or starting work.
- Recent failures are limited to ten entries and sanitize Windows/POSIX absolute
  paths, credential-like values, multiline traceback content, and long messages.
  The pure formatter uses a fixed section order. **Help > Diagnostics...** exposes
  read-only Refresh, Copy Diagnostics, UTF-8 text save, and Close actions; display,
  clipboard, and saved content are identical sanitized text.

## Not implemented

- P2-E performance characterization and phase hardening.
- Broader export-format/naming preferences; only Statistics CSV currently exists.
- P3–P7 workflow, RAW processing expansion, remote/authentication, and
  distribution work.
- Windows startup white-frame polish. There is no intentional splash/pre-render
  path; investigation is deferred until the major phases are complete.

## Validation evidence

Focused P2-D diagnostics validation reports 20 passed. Full pytest reports 378
passed with three reproducible offscreen
failures: floating Plots geometry restore and two pyqtgraph hover-coordinate
assertions. The same three tests fail from an isolated
`origin/main@812982dacdecca155f7b53ab42ef2bd9fba68a77` archive in
the identical environment, confirming they are baseline/environment failures,
not P2-D regressions. They were not skipped or rewritten. Manual Windows P2-D
dialog, clipboard, save, sanitization, and responsiveness validation remains.

## Active plan

- P1 history: [`exec-plans/completed/p1-d-to-p1-f-workspace-polish.md`](exec-plans/completed/p1-d-to-p1-f-workspace-polish.md)
- P2 active plan: [`exec-plans/active/next-phase.md`](exec-plans/active/next-phase.md)
- P2-A1: complete; merged as PR #14.
- P2-A2: complete; merged as PR #15.
- P2-B: complete; merged as PR #16.
- P2-C: complete; merged as PR #17.
- P2-D: active on `feature/p2-d-runtime-diagnostics`.
- Next slice after P2-D merge: P2-E — performance characterization and hardening.
