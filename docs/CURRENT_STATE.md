# PixelScope current state

Snapshot date: 2026-08-09
P2-E / PR #19 merge commit and P2-F branch base:
`7ee7aec2980baeef9d511f3db5c71f89fa319a64`

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
- P2-D merged as PR #18 at
  `a7b4ddf62af95e86b9d9e38a4328cf9572226114`.
- P2-E merged as PR #19 at
  `7ee7aec2980baeef9d511f3db5c71f89fa319a64`.
- P2-F is active on `feature/p2-f-performance-hardening` as the final
  Performance Characterization & Phase Hardening slice.

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
  pair, and active foreground load-target registered sources. Protected bytes may
  exceed the soft budget; an oversized required source is retained without
  load/evict thrash.
- Eviction releases source and preview, clears Statistics/Histogram and
  source-dependent channel views, updates the Files residency state, and marks
  the document pending for the existing tokenized normal-load path. Difference
  maps remain independently owned and are not evicted solely for source-budget
  pressure.
- The dedicated image-load pool is bounded at two workers; the shared numeric
  pool is bounded at four. A separate preload pool is bounded at one worker.
- Pure-core `FolderNavigationPlan` is the shared PageUp/PageDown and preload
  prediction authority over registered `_folder_documents` sequences.
- Pure-core `PreloadController` owns exactly one next-position plan (zero to six
  targets), request generation, active/completed state, running/promotion state,
  and bounded counters. Preload starts only after foreground loads become idle
  and never scans or auto-registers filesystem siblings.
- The preload baseline remains `plan(+1)` only, exactly one Folder Position deep,
  with fixed preload concurrency one. No previous, bidirectional, next-next, or
  configurable worker/resource policy is introduced by P2-E or P2-F.
- A request becomes promotion-eligible only after the preload worker's existing
  `started` signal establishes that it is physically RUNNING. Queued/not-started,
  cancelled, stale, mismatched, resident, or superseded requests remain on the
  existing normal-load correctness path.
- When the exact running preload becomes foreground-required, P2-E changes its
  logical authority from speculative to foreground without migrating the worker
  between `QThreadPool` instances. The same `ImageLoadWorker` and decode continue
  in the max-one preload pool.
- Promotion is validated against document ID, document generation, source-path
  identity, RAW-profile identity, exact RAW-size policy, normal-load token,
  registered-document existence, non-resident state, running state, and absence
  of a duplicate normal worker.
- Promotion occurs before selection/navigation invalidates the previous preload
  plan. The promoted request leaves speculative cancellation ownership, becomes
  foreground Loading, is protected as foreground-required residency input, and
  prevents a second decoder from starting for the same target.
- Other members of a one-to-six-folder group are unchanged. With concurrency one,
  one matching running member can be promoted while any other required members
  use the ordinary max-two foreground pool.
- Promoted success is applied exactly once through the existing normal foreground
  success path, preserving document identity/generation, exact `source.nbytes`
  accounting, MRU touch, Files state, selected-batch render gating, eviction, and
  Ready/status behavior. It is not first applied as speculative success.
- Promoted failure is handled exactly once as a foreground load failure and enters
  P2-D Recent Failures as `foreground-load/decode`; it is not also counted as a
  preload failure.
- Navigation away from a promoted request uses ordinary foreground cancellation
  and token-stale semantics. Cancellation remains advisory; a late result cannot
  overwrite newer document/selection state because current token/generation/
  request identity remains the correctness authority.
- A promoted worker remains physically present in the preload registry/pool until
  completion, so no new speculative preload starts alongside it. Logical worker
  diagnostics classify it as foreground, not simultaneously as preload.
- Valid completed speculative preload results remain ordinary source residency,
  receive no special protection, and may be evicted immediately under source
  pressure. Already-resident next targets remain the immediate-reuse fast path.
- Frozen Qt-free `RuntimeDiagnosticsSnapshot` values aggregate exact source,
  Difference-cache, foreground/preload worker, preload counter, foreground stale
  drop, and bounded recent failure state. `MainWindow.runtime_diagnostics_snapshot()`
  remains observation-only.
- P2-E adds only `promotion_count` observability. Copy Diagnostics includes
  **Promoted to foreground: N**; a promoted running worker is counted once under
  logical foreground activity and excluded from speculative preload active counts.
- Recent failures are limited to ten entries. Accepted current foreground/preload
  failures are recorded; obsolete cancelled or replanned speculative failures
  are not. Sanitization continues to remove paths, credential-like values,
  bearer/URL detail, traceback context, and long messages.
- The only end-user diagnostics surface remains **Help > Copy Diagnostics**.
  There is no diagnostics modal, refresh loop, live monitor, timer, or diagnostics
  file export.

### P2-F characterization state

- P2-F changes no production runtime policy in its initial audit. Settings schema
  remains v5; preload remains `+1`, one Folder Position deep, normal pool max two,
  preload pool max one, and preload concurrency one.
- Existing settings tests already cover fresh/default state, current round-trip,
  v4-to-v5 and v3-to-current migration, old Difference-cache clamping,
  malformed/invalid state, legacy RAW migration, future-schema non-destructive
  behavior, reset/workspace separation, startup-only restart indication,
  enabled-by-default preload, and the combined source/Difference RAM guard at and
  above the exact limit.
- Existing source-residency and Difference-cache tests already cover exact native
  `source.nbytes`, protection, ordinary LRU, soft over-budget and oversized
  required sources, normal reload without a reload/evict loop, independent
  Difference ownership, and low-budget Difference-pair protection.
- Existing preload/promotion tests distinguish completed resident reuse, exact
  RUNNING promotion with one decoder, ordinary foreground fallback, promoted
  success/failure exactly once, pair/group completion, RAW profile/exact-size
  identity, promotion diagnostics, logical worker classification, and rapid
  navigation stale-result rejection.
- Existing diagnostics tests preserve exact source/Difference/worker/preload
  values, bounded sanitized failures, **Copy Diagnostics** as the only surface,
  and observation-only reads with no LRU touch, load/preload/cancellation/render,
  or filesystem work.
- `tests/performance/test_performance_smoke.py` supplies a representative
  synthetic/temp-file matrix for FHD RGB uint8, FHD grayscale uint16, and UHD
  Bayer uint16 profile-described RAW. The UHD case runs the production
  `read_raw_document()` Bayer preview path and `automatic_histogram_spec()` Auto
  policy, then verifies `analyze_bayer_roi()` RGGB R/Gr/Gb/B separation,
  per-plane sample counts, 4096-bin placement, preview channel structure/content,
  exact native bytes, and zero-difference invariants. Timing output remains
  observational only.
- Existing `tests/integration/test_4k_samples.py` remains the real 3840x2160 RGB
  plus RGGB10-u16 RAW fixture path; no new large binary fixture is added by P2-F.
- Process RSS remains outside P2 source-memory accounting and no benchmark/live
  diagnostics UI is introduced.

## Not implemented

- P2-F independent re-review and owner/local Windows closure validation are still
  required before merge; this branch must not describe P2-F as merged.
- Broader export-format/naming preferences; only Statistics CSV currently exists.
- P3–P7 workflow, RAW processing expansion, remote/authentication, and
  distribution work.
- Windows startup white-frame polish. There is no intentional splash/pre-render
  path; investigation is deferred until the major phases are complete.
- Evidence-driven post-P2 optimization candidates remain separate work: preload
  concurrency one versus two, directional/bidirectional prediction, deeper
  preload, CPU/I/O aggressiveness, and broader resource-policy Settings exposure.

## Validation evidence

- P2-E is merged as PR #19 at
  `7ee7aec2980baeef9d511f3db5c71f89fa319a64`.
- P2-F coverage audit found no production-code correctness/resource/lifecycle
  blocker requiring an architecture change before characterization.
- P2-F commit `35480a4e74963de9721c448b8541069748392723`
  replaces the performance-smoke wall-clock merge gate with deterministic
  representative FHD/UHD correctness/resource invariants while retaining timing
  output as observational evidence.
- P2-F review follow-up commit `3e0cb616cecc88b3962bf6f564c9fc9feddedb41`
  closes the UHD Bayer characterization gap by exercising production Bayer
  preview loading, Auto 4096-bin selection, and CFA-specific analysis instead of
  generic grayscale preview/histogram semantics.
- The GitHub connector implementation environment does not provide the repository
  Python/Qt runtime. No P2-F pytest/ruff/mypy/pip/docs command is recorded as
  passing until its output is actually observed on the owner/local environment.
- There is no GitHub Actions workflow today. Introducing an unobserved Windows Qt
  gate during P2 closure is deferred; owner/local Windows validation remains the
  authoritative P2-F closure evidence.

## Active plan

- P1 history: [`exec-plans/completed/p1-d-to-p1-f-workspace-polish.md`](exec-plans/completed/p1-d-to-p1-f-workspace-polish.md)
- P2 active plan: [`exec-plans/active/next-phase.md`](exec-plans/active/next-phase.md)
- P2-A1: complete; merged as PR #14.
- P2-A2: complete; merged as PR #15.
- P2-B: complete; merged as PR #16.
- P2-C: complete; merged as PR #17.
- P2-D: complete; merged as PR #18.
- P2-E: complete; merged as PR #19 at
  `7ee7aec2980baeef9d511f3db5c71f89fa319a64`.
- P2-F: active — Performance Characterization & Phase Hardening.
- P2 plan archive and detailed P3 execution planning follow P2-F merge in the
  next orchestration step.
