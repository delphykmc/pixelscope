# Engineering decisions

## Platform and implementation constraints

- CPython 3.10 x64 is fixed.
- PySide6 6.4.2 remains the Qt binding; pyqtgraph 0.13.3 provides image and plot
  primitives.
- PyInstaller is fixed at exactly 5.7 `onedir`; 6.x is prohibited. Inno Setup is
  the planned installer layer.
- NumPy/OpenCV implementations come first. Native C/C++ optimization requires
  profiling evidence and remains behind numerical/RAW interfaces.
- Expensive I/O and analysis run in bounded workers; widgets do not own decode or
  Difference algorithms.
- Source pixels retain native dtype/channel meaning; overflow-prone arithmetic
  promotes operands first.

## Current product decisions

- Ordered selection is the comparison model; Difference may select any two
  current images.
- Multi View has one fixed layout policy. `_fixed_geometry()` is the sole
  geometry authority; P1-F removed arrangement compatibility state.
- Primary-image reference priority is primary, active, then first displayed.
- Difference caches one native absolute map and derives views/metrics from it.
- RAW storage format, sample container, effective bit depth, endian, and
  alignment remain separate concepts.
- Remote evaluation uses a versioned REST job API boundary.

## Accepted P2 program decisions

- P2 is named **Runtime Foundation, Settings & Performance**.
- P2 proceeds sequentially:
  **P2-A1 → P2-A2 → P2-B → P2-C → P2-D → P2-E → P2-F** after the P2-0
  documentation transition. Each slice starts from the latest merged prerequisite
  on `main`.
- P2-A1 is the application identity/resource foundation merged as PR #14.
  P2-A2 merged as PR #15 and owns typed settings, persistence, the Settings
  dialog, Difference display defaults, RAW size policy, and Difference Map Cache
  startup injection.
- P2-B and P2-C merged as PR #16 and PR #17. P2-D merged as PR #18 at
  `a7b4ddf62af95e86b9d9e38a4328cf9572226114` and owns observation-only runtime
  diagnostics without changing resource policy.
- P2-E **Running Preload Promotion / Foreground Reuse** is complete and merged as
  PR #19 at `7ee7aec2980baeef9d511f3db5c71f89fa319a64`. P2-F is the final P2
  Performance Characterization & Phase Hardening closure slice.
- QSettings is a persistence adapter, not the application settings domain model.
  Frozen `ApplicationSettings` is the persisted typed model;
  `SettingsRepository` owns defaults, validation, migration, save, and reset;
  `QSettingsAdapter` owns raw application-preference keys.
- Application settings schema version 5 owns:
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
- Schema v4 migrates directly to v5, preserving all v4 values and adding enabled
  preload. Schema v3 migration adds the current source-residency default. A v3
  Difference-cache value valid in the former 64–8192 MiB range is clamped to the
  new 1280 MiB maximum instead of reset to 128 MiB. Schema v2/v1 and legacy
  `raw/dont_show_json_profiles` also migrate into the current model.
- Invalid current values fall back to validated defaults and are normalized. A
  persisted schema newer than the running application is never destructively
  guessed or rewritten; application preferences remain read-only until a
  compatible version is used.
- Settings uses a restrained VS Code-inspired category/page structure:
  **General**, **Files**, and **Performance**. It uses hierarchy, spacing, and
  flat setting rows rather than nested legacy group boxes; search is deferred
  until the settings count justifies it.
- **Don't Show RAW JSON Profiles** is a persistent General setting and is removed
  from the File menu. The RAW open dialog may still persist that one field from
  its explicit don't-show-again interaction without resetting other settings.
- **Require Exact RAW File Size** is a persistent General setting. Disabled
  accepts trailing bytes while rejecting undersized inputs; enabled requires
  exact byte equality. `MainWindow` passes the policy to RAW workers and uses the
  same rule for JSON-sidecar auto-approval.
- **Difference Threshold** and **Difference Gain** are persistent General
  analysis defaults. They initialize the Difference panel at startup and apply
  to the live panel immediately after Settings saves; they do not require
  restart.
- **Default Open Folder** and **Default Export Folder** are optional Files
  preferences. Blank means use the remembered last-used folder; a configured
  existing path only seeds the corresponding dialog and applies immediately.
- Exact dock geometry, splitter sizes, current layout mode, Plots visibility, and
  floating state are not duplicated in Settings. Workspace persistence already
  owns those values; a second default source would create restore/reset
  precedence conflicts.
- Broader export format, naming, and destination policy is deferred until
  PixelScope has more than the current Statistics CSV export surface.
- Worker counts, zoom/sync state, and other transient runtime state remain outside
  application preferences.
- Performance settings are immutable startup snapshots. Difference Map Cache and
  Decoded Source Memory edits are persisted immediately but do not mutate their
  existing runtime owners.
- Difference Map Cache preference default is 128 MiB with an accepted range of
  64–1280 MiB. Runtime receives bytes through `PerformanceSettings`.
- Decoded Source Memory defaults to 256 MiB, accepts 128–2560 MiB, and uses
  128 MiB UI increments. Runtime receives bytes through
  `PerformanceSettings.source_residency_bytes`.
- When physical RAM is known, the Settings UI requires both budgets together to
  remain at or below 50% of RAM. An above-limit Save retains both entered values,
  warns, and stays open. Unknown RAM uses product bounds only. This is a
  conservative configuration envelope, not an out-of-memory guarantee.
- Restart-required UI compares both saved/editable startup-only budget values and
  preload enablement to the current runtime snapshot. Returning all three to
  their runtime values clears the indication. File-location, RAW, Threshold, and
  Gain changes do not require restart.
- `Reset Settings` resets only schema-owned application preferences. `Reset
  Workspace Layout` remains a separate action and application reset does not
  remove window/dock/splitter geometry, remembered last-directory state, or
  unrelated QSettings keys.
- The current canonical PixelScope identity is a blue-gray image/scope/pixel mark
  with a restrained amber accent. The editable SVG, runtime PNG, and Windows ICO
  are colocated under `src/pixelscope/assets/icons/`; release naming or artwork
  may replace the triplet before P7, but duplicate canonical copies are not
  allowed.
- `scripts/generate_icon_assets.py` is the canonical derivative path. It uses
  dev-pinned `resvg_py==0.3.3` plus `Pillow==12.3.0`, renders every target size
  directly from the SVG, and must reproduce the checked-in PNG/ICO exactly.
- Application icon lookup uses package-resource bytes and may not depend on the
  current working directory or a source-tree absolute path.
- Windows source runs use the stable AppUserModelID `PixelScope.PixelScope`, set
  before `QApplication` creation.
- Executable-file icons, pinned shortcuts, installer shortcuts, signing, final
  packaged-shell grouping, and release-name policy remain P7 concerns.
- Decoded-source budgeting accounts native decoded `ImageDocument.source`
  arrays only. It excludes previews, Qt textures, Difference/derived caches, and
  transient worker arrays and is not total process memory.
- The decoded-source budget is a soft limit because protected documents may
  temporarily exceed it. Visible, selected, active/analysis, current Difference
  pair, and foreground load-target registered sources are protected. A required
  source larger than the budget remains resident while protected.
- Pure-core `ResidencyManager` owns byte accounting, LRU order, protected
  eviction planning, and minimal diagnostics. `MainWindow` alone mutates
  documents, invalidates source-local caches, updates Files state, and triggers
  existing-path reloads.
- Source-only eviction does not invalidate a valid Difference map. Difference
  maps remain under their own budget/generation contract.
- Folder Position navigation operates only on registered `_folder_documents`
  sequences. One-to-six selected file-backed documents from distinct folders
  move atomically; any endpoint or invalid member makes the whole move a no-op.
- Up/Down remains native Files-tree row navigation. Left/Right remains
  Previous/Next Selected Image. PageUp/PageDown owns Previous/Next Folder Position.
- One pure folder-navigation planner is authoritative for actual PageDown targets
  and preload prediction.
- **Preload Next Folder Position** is enabled by default and is an immutable
  startup setting. It owns exactly `plan(+1)`, never previous or next-next work.
- Preload uses a dedicated max-one worker pool, has bounded ownership separate
  from normal load, and may not starve interactive work.
- Successful completed speculative preload results enter ordinary source
  residency with no speculative protection or separate memory budget. Silent
  speculative failure remains retryable through normal loading.
- Cancellation and stale-result rejection are distinct; obsolete results must
  not apply even when a decoder cannot stop immediately.
- P2-D establishes deterministic, inexpensive, sanitized runtime observability for
  automated validation, P2-F characterization, and support troubleshooting. The
  only end-user surface is an on-demand **Help > Copy Diagnostics** action.
- Runtime diagnostics are frozen Qt-free snapshots with a pure deterministic text
  formatter. They reuse the existing source, Difference-cache, and preload owners;
  foreground/preload workers use general active/max pairs. P2-F may consume
  `MainWindow.runtime_diagnostics_snapshot()` directly without any diagnostics UI.
- Diagnostics retain at most ten recent accepted failures. Obsolete cancelled or
  replanned speculative preload failures are not promoted into recent failure
  history. Failure text redacts absolute Windows/POSIX paths, complete
  credential-like assignment values including multi-word values, bearer tokens,
  URL detail, multiline traceback context, and excess message length. Diagnostics
  contain no pixel content, raw traceback, environment dump, username, hostname,
  CWD, or timestamp.
- **Help > Copy Diagnostics** obtains one current snapshot, formats it once with
  the canonical formatter, copies that exact sanitized text to the clipboard,
  and provides a short status-bar confirmation. There is no diagnostics modal,
  live monitor, Refresh/timer, or diagnostics text-file export.
- Reading or copying diagnostics may not load images, calculate Difference,
  mutate an LRU, start/cancel workers, refresh preload, scan files, or change
  selection/rendering.

## Accepted P2-E promotion decisions

- The preload policy remains `+1` only, exactly one Folder Position deep, with
  fixed preload concurrency one. P2-E does not add previous/bidirectional
  prediction, next-next preload, configurable depth, worker count, or CPU/I/O
  aggressiveness.
- Promotion applies only to the exact preload request that has physically begun
  execution. `TaskWorker.started` is the RUNNING boundary; queued/not-started
  requests are invalidated/cancelled as speculative work and the ordinary normal
  load path remains authoritative.
- Promotion is a **logical authority transition**, not QThreadPool migration. The
  `ImageLoadWorker` stays in the preload pool and completes the same decode.
- Promotion eligibility requires exact agreement on target document ID,
  registered-document existence, document generation, source-path identity, RAW
  profile identity, exact RAW-size policy, captured normal-load token,
  non-resident source state, RUNNING/not-cancelled state, non-stale request state,
  and absence of a duplicate normal worker for the target.
- Selection/navigation must attempt matching promotion before invalidating the
  old preload plan. An accepted promoted worker leaves speculative cancellation
  ownership and may not be cancelled merely because that plan is replaced.
- The promoted request receives foreground loading/token authority and
  foreground-required residency protection. `_ensure_loaded()` must not start a
  second decoder for the same target.
- Promotion does not promote an entire pair/group. With preload concurrency one,
  at most the currently RUNNING matching member is reused; other required group
  members use the ordinary normal-load path.
- Promoted success follows the normal foreground result path exactly once,
  including original document identity/generation, exact native `source.nbytes`
  accounting, MRU touch, Files state, selected-batch completion/render, ordinary
  eviction, and normal Ready/status behavior.
- Promoted failure follows the normal foreground failure path exactly once,
  including document error/status behavior and P2-D Recent Failures category
  `foreground-load/decode`. It is not also recorded as a preload failure.
- Once promoted, later navigation may make that foreground work obsolete under
  the same advisory-cancellation and token/generation stale-rejection principles
  as normal loads. A late promoted result may not overwrite newer state.
- Already-resident preloaded targets remain the immediate-reuse fast path and do
  not require promotion or a new worker.
- RAW promotion reuses the same worker only when RAW profile identity and exact
  RAW-size policy still match. P2-E does not duplicate RAW decoding logic and
  does not introduce speculative RAW dialogs.
- P2-D diagnostics are extended only by a deterministic cumulative
  `promotion_count` (`Promoted to foreground: N`). A promoted physical preload
  worker is observed once under logical foreground activity and is excluded from
  speculative preload active counts; diagnostics remain observation-only.
- P2-E adds no new setting and does not change settings schema version 5.
- Packaging, signing, update strategy, and release engineering are P7.
- Login, SSO, token/credential lifecycle, access policy, and remote operations
  administration are P6. P2 does not introduce credentials.
- The brief Windows startup white-frame flash has no intentional splash or
  pre-render owner in the current startup path. Investigation is deferred to
  startup polish after the major phases and is not a P2 merge blocker.

## Accepted P2-F characterization decisions

- P2-F is a final characterization/hardening slice, not a feature or scheduler
  redesign. Production changes are justified only by an observed correctness,
  resource, or lifecycle defect.
- Performance merge gates are deterministic. Shape, dtype, pixel/count results,
  exact native byte accounting, cache/residency state, request identity, decode
  count, worker ownership, cancellation/stale rejection, and bounded diagnostics
  may fail a test; elapsed wall-clock time may not.
- `perf_counter()` measurements may remain in performance smoke output as
  hardware-specific observational evidence. The former `threshold_mask < 0.5 s`
  assertion is not an acceptable P2 merge gate and is removed rather than
  replaced by another arbitrary threshold.
- Representative automated coverage is intentionally not a Cartesian product.
  P2-F uses FHD RGB uint8, FHD grayscale uint16, and UHD Bayer uint16
  profile-described RAW characterization, with the existing real 4K RGB/RGGB10
  integration fixture retained as complementary evidence.
- No large binary fixture is added for characterization; synthetic arrays and
  temporary RAW files are preferred when resolution/resource behavior itself is
  under test.
- P2-F preserves settings schema v5, the 128 MiB Difference default, the 256 MiB
  source-residency default, enabled preload, and the existing combined-RAM guard.
- P2-F preserves preload direction `+1`, depth exactly one Folder Position,
  preload concurrency one, normal pool max two, preload pool max one, exact
  RUNNING promotion, foreground priority, ordinary preload residency, and
  independent Difference caching.
- Process RSS, preview/Qt-texture totals, telemetry, benchmark UI, and live
  diagnostics remain outside P2 resource accounting.
- The repository currently has no GitHub Actions workflow. A new Windows Qt gate
  is not introduced without observed PySide6/pytest-qt/offscreen stability and
  runtime/resource evidence. For P2 closure, Windows CI introduction is deferred
  and owner/local Windows validation remains authoritative.
- Post-P2 optimization candidates remain evidence-driven separate work:
  preload concurrency one versus two, directional/bidirectional prediction,
  deeper preload, CPU/I/O aggressiveness, and broader resource-policy Settings
  exposure. P2-F does not implement them speculatively.

## Current resource policy

- The canonical SVG/PNG/ICO icon triplet, reproducible generator,
  package-resource loader, `QApplication`/main-window assignment, and source-run
  Windows AppUserModelID are P2-A1 boundaries.
- `DifferenceMapCache` is byte-budgeted and persistence-free. P2-A2 injects its
  startup budget through immutable `PerformanceSettings`; the default is 128 MiB.
- Decoded-source residency uses the P2-B byte-budgeted manager and protected-set
  policy. The former fixed seven-document limit is no longer authoritative.
- Normal image-load pool max remains two; preload pool max remains one. Promotion
  changes logical authority only and does not change either physical pool limit.

## Pending owner decisions

There are no pending P2-F product-design decisions. Independent review, the full
standard validation commands, and the agreed Windows characterization matrix are
closure evidence still required before merge; they do not authorize speculative
runtime-policy expansion.
