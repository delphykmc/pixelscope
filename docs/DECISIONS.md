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
  P2-A2 owns typed settings, persistence, the Settings dialog, and
  Difference-cache startup injection.
- QSettings is a persistence adapter, not the application settings domain model.
  Frozen `ApplicationSettings` is the persisted typed model;
  `SettingsRepository` owns defaults, validation, migration, save, and reset;
  `QSettingsAdapter` owns raw application-preference keys.
- Application settings schema version 2 owns:
  - `settings/schema_version`
  - `settings/general/dont_show_raw_json_profiles`
  - `settings/files/default_open_directory`
  - `settings/files/default_export_directory`
  - `settings/performance/difference_cache_mib`
- Schema v1 migrates to v2 by preserving the RAW and Difference-cache values and
  initializing both file-location values to blank. Legacy
  `raw/dont_show_json_profiles` remains migration input only.
- Invalid current values fall back to validated defaults and are normalized. A
  persisted schema newer than the running application is never destructively
  guessed or rewritten; application preferences remain read-only until a
  compatible version is used.
- Settings uses an Excel-style category/page structure rather than a single long
  form: **General**, **Files**, and **Performance**. This supports later additions
  without adopting VS Code's search-heavy settings UX before it is needed.
- **Don't Show RAW JSON Profiles** is a persistent General setting and is removed
  from the File menu. The RAW open dialog may still persist the same preference
  from its explicit don't-show-again interaction.
- **Default Open Folder** and **Default Export Folder** are optional Files
  preferences. Blank means use the remembered last-used folder; a configured
  existing path only seeds the corresponding dialog and applies immediately.
- Exact dock geometry, splitter sizes, current layout mode, Plots visibility, and
  floating state are not duplicated in Settings. Workspace persistence already
  owns those values; a second default source would create restore/reset
  precedence conflicts.
- Broader export format, naming, and destination policy is deferred until
  PixelScope has more than the current Statistics CSV export surface.
- Worker counts, zoom/sync state, Difference gain/threshold, and other transient
  analysis/runtime state are not general user preferences in P2-A2.
- Performance settings are immutable startup snapshots. Difference-cache edits
  are persisted immediately but do not mutate an existing runtime cache.
- Difference-cache preference default is 512 MiB with an accepted range of
  64–8192 MiB. Runtime receives bytes through `PerformanceSettings`.
- Restart-required UI is determined by comparing the saved/editable startup-only
  value to the current runtime snapshot. Returning to the runtime value clears
  the indication. File-location and RAW changes do not require restart.
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
  temporarily exceed it. P2-B extends the protected-set policy beyond the
  current visible-document and active-load-target inputs.
- P2-B's source-residency budget and P2-C's preload preference extend the existing
  Performance Settings page when those runtime lifecycles are implemented.
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

## Current resource policy

- The canonical SVG/PNG/ICO icon triplet, reproducible generator,
  package-resource loader, `QApplication`/main-window assignment, and source-run
  Windows AppUserModelID are P2-A1 boundaries.
- `DifferenceMapCache` is byte-budgeted and persistence-free. P2-A2 injects its
  startup budget through immutable `PerformanceSettings`; the default remains
  512 MiB.
- Decoded-source residency currently uses a fixed seven-document reloadable
  policy in `MainWindow`; P2-B moves policy ownership to a byte-budgeted manager.
- The current residency protection inputs are visible documents and active load
  targets. Selected and analysis protection are P2-B additions.

## Pending owner decisions

These recommendations are not accepted values until the owner confirms them:

- Decoded-source budget default — recommendation: 1024 MiB; pending before P2-B.
- Preload default — recommendation: Enabled; pending before P2-C.
