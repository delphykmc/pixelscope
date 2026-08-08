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
  **P2-A1 → P2-A2 → P2-B → P2-C → P2-D → P2-E** after the P2-0 documentation
  transition. Each slice starts from the latest merged prerequisite on `main`.
- P2-A1 is the application identity/resource foundation merged as PR #14.
  P2-A2 merged as PR #15 and owns typed settings, persistence, the Settings
  dialog, Difference display defaults, RAW size policy, and Difference Map Cache
  startup injection.
- QSettings is a persistence adapter, not the application settings domain model.
  Frozen `ApplicationSettings` is the persisted typed model;
  `SettingsRepository` owns defaults, validation, migration, save, and reset;
  `QSettingsAdapter` owns raw application-preference keys.
- Application settings schema version 4 owns:
  - `settings/schema_version`
  - `settings/general/dont_show_raw_json_profiles`
  - `settings/general/require_exact_raw_file_size`
  - `settings/files/default_open_directory`
  - `settings/files/default_export_directory`
  - `settings/analysis/difference_threshold`
  - `settings/analysis/difference_gain`
  - `settings/performance/difference_cache_mib`
  - `settings/performance/source_residency_mib`
- Schema v3 migrates directly to v4 and adds the current source-residency
  default. A v3 Difference-cache value valid in the former 64–8192 MiB range is
  clamped to the new 1280 MiB maximum instead of reset to 128 MiB. Schema v2/v1
  and legacy `raw/dont_show_json_profiles` also migrate into the current model.
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
  P2-A2 application preferences.
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
- Restart-required UI compares both saved/editable startup-only budget values to
  the current runtime snapshot. Returning both to their runtime values clears
  the indication. File-location, RAW, Threshold, and Gain changes do not require
  restart.
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
  pair, and active load-target registered sources are protected. A required
  source larger than the budget remains resident while protected.
- Pure-core `ResidencyManager` owns byte accounting, LRU order, protected
  eviction planning, and minimal diagnostics. `MainWindow` alone mutates
  documents, invalidates source-local caches, updates Files state, and triggers
  existing-path reloads.
- Source-only eviction does not invalidate a valid Difference map. Difference
  maps remain under their own budget/generation contract.
- P2-C's preload preference extends the existing Performance Settings page when
  that runtime lifecycle is implemented.
- Preload has bounded ownership separate from normal load and may not starve
  interactive work.
- Cancellation and stale-result rejection are distinct; obsolete results must
  not apply even when a decoder cannot stop immediately.
- Diagnostics redact full paths and sanitize failures by default. They contain no
  credentials, bearer tokens, pixel content, or unbounded raw traceback and do
  not start expensive work.
- Packaging, signing, update strategy, and release engineering are P7.
- Login, SSO, token/credential lifecycle, access policy, and remote operations
  administration are P6. P2 does not introduce credentials.
- The brief Windows startup white-frame flash has no intentional splash or
  pre-render owner in the current startup path. Investigation is deferred to
  startup polish after the major phases and is not a P2-A2 merge blocker.

## Current resource policy

- The canonical SVG/PNG/ICO icon triplet, reproducible generator,
  package-resource loader, `QApplication`/main-window assignment, and source-run
  Windows AppUserModelID are P2-A1 boundaries.
- `DifferenceMapCache` is byte-budgeted and persistence-free. P2-A2 injects its
  startup budget through immutable `PerformanceSettings`; the default is 128 MiB.
- Decoded-source residency uses the P2-B byte-budgeted manager and protected-set
  policy. The former fixed seven-document limit is no longer authoritative.

## Pending owner decisions

This recommendation is not an accepted value until the owner confirms it:

- Preload default — recommendation: Enabled; pending before P2-C.
