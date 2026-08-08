# Architecture

## Current boundaries and data flow

`io` discovers and decodes files into source arrays. `core.ImageDocument` owns
native source arrays, metadata, preview data, generation state, caches, and
evaluation results. `core` performs display conversion, Bayer handling,
statistics/histogram, line-profile, and overflow-safe Difference math without
Qt. `workers` runs expensive I/O and numerics in bounded `QThreadPool` workers.
`ui` renders previews and emits lightweight image-coordinate state. `app` owns
documents, ordered selection, application settings composition, workspace state,
load identity, source residency, and window lifecycle.

Source arrays retain decoded dtype and channel meaning. Display conversion
creates uint8 previews without modifying native source data. RGBA analysis
ignores alpha. Difference and squared-error paths promote operands first.

## Current application identity and resource boundary

Canonical application assets live under
`src/pixelscope/assets/icons/pixelscope.{svg,png,ico}`. The SVG is the editable
source of truth; `scripts/generate_icon_assets.py` derives the runtime PNG and
multi-frame Windows ICO.

`pixelscope.app.resources` reads package bytes through `importlib.resources`.
On Windows, application bootstrap assigns the stable AppUserModelID
`PixelScope.PixelScope` before `QApplication` creation. Bootstrap then assigns
the decoded runtime icon to `QApplication`, and `main()` explicitly assigns the
same icon to `MainWindow` before showing it. Resource lookup is independent of
the current working directory and source-tree absolute paths. Setuptools package
data includes the complete icon triplet.

This boundary supplies source-run application, window, Alt+Tab, and running
Taskbar identity. PyInstaller executable icon binding, Windows shortcut and
installer identity, pinned-shell behavior, signing, and final release naming
remain P7.

## Current application settings boundary

Application preferences and workspace/session persistence are intentionally
separate even though both ultimately use Qt persistence.

- Frozen `ApplicationSettings` is the typed persisted domain model. P2-A2 owns
  RAW JSON confirmation, exact RAW file-size validation, default Open/Export
  folders, Difference Threshold/Gain defaults, and the Difference Map Cache MiB
  preference. P2-B adds Decoded Source Memory MiB and P2-C adds preload enablement.
- `SettingsRepository` owns defaults, versioned schema behavior, migration,
  validation, invalid-state recovery, save, and reset.
- `QSettingsAdapter` is the only application-settings component that knows raw
  application-preference keys. QSettings is an adapter, not the domain model.
- `Edit > Settings...` uses a category/page template with **General**, **Files**,
  and **Performance** pages. The left navigation is intentionally simple at the
  current settings count; a VS Code-style settings search is not required yet.
- Application bootstrap loads `ApplicationSettings`, converts the performance
  preferences to an immutable byte-based `PerformanceSettings` startup snapshot,
  and passes both settings objects plus the repository to `MainWindow`.
- `MainWindow` injects `PerformanceSettings.difference_cache_bytes` into
  `DifferencePanel`, which passes the fixed budget to `DifferenceMapCache`.
  Neither the panel nor the cache reads persistence.
- `MainWindow` also applies persisted Difference Threshold/Gain values to the
  live `DifferencePanel` at startup and after Settings saves. Those display
  defaults do not require restart.
- `MainWindow` passes `require_exact_raw_file_size` into every RAW
  `ImageLoadWorker`; JSON-sidecar auto-approval uses the same exact-versus-
  minimum-size policy before skipping the profile dialog.
- Default Open/Export folders are live preferences. A blank value preserves the
  existing last-used-folder behavior; a configured existing folder only changes
  the starting location of the corresponding file dialog.
- `MainWindow` constructs `ResidencyManager` from
  `PerformanceSettings.source_residency_bytes`. The manager never reads
  persistence and the Difference cache remains a separate owner.
- Runtime edits to startup-only performance values are persisted for the next
  launch; existing runtime caches, managers, and preload controller are not mutated.

Schema version 5 owns:

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

Schema v4 migrates directly to v5 and adds enabled preload without changing any
v4 preference. Schema v3 migration still adds the source-residency preference. A
legacy Difference-cache value valid in v3's 64–8192 MiB range is clamped to the
new 1280 MiB maximum rather than replaced by the 128 MiB default. Malformed and
genuinely invalid values normalize to validated defaults. Schema v2/v1 migration
and legacy `raw/dont_show_json_profiles` input remain supported. A future schema
version is not guessed or
rewritten; the current process uses safe defaults and exposes application
settings as read-only compatibility state.

`Reset Settings` resets only schema-owned application preferences. It is
separate from `Reset Workspace Layout` and does not remove window geometry,
dock/splitter state, the remembered last-used directory, or unrelated QSettings
keys.

## Current workspace structure

The central splitter contains Files/Analysis and the active workspace. Ordered
selection is the comparison set; Difference Image 1/Image 2 controls own the
comparison pair.

Workspace QSettings remain owned by `MainWindow` and related UI components.
They persist main geometry, dock state, splitter state, layout mode, Plots
visibility, selected bottom tab, floating Plots geometry, and last-directory
state. These keys are not part of `ApplicationSettings`.

Docking, splitter sizes, current layout, Plots visibility, and exact floating
geometry are deliberately not duplicated as application preferences. The saved
workspace is already the authoritative representation of those values; adding
second default-setting owners would make restore/reset precedence ambiguous.

The custom Plots title bar shares a maximize/restore state machine between its
button and title double-click.

Multi View uses one fixed layout policy. `_focus_document_id` retains explicit
primary identity and `_multi_display_order` owns display promotion without
mutating Files order or logical IDs. `MultiCompareView._fixed_geometry()` is the
sole one-to-six geometry authority; no runtime arrangement registry, action,
field, or persisted arrangement remains. When the document count and geometry
are unchanged, a preserve-view rebind does not remove and re-add viewer widgets;
this prevents resize-driven range changes during primary promotion.

Split Channels applies target geometry and visibility before replacement content
is bound, preserving atomic Bayer/RGB-to-GRAY transitions.

## Current thread, request, and document lifecycle

A dedicated image-load pool runs at most two workers. A separate preload pool
runs at most one worker, so speculative decode cannot occupy or queue behind a
normal-load slot. The shared numerical pool runs at most four. Registered paths
begin as lightweight pending documents.

Normal image-load stale-result validation primarily depends on the target
document ID, `MainWindow._load_tokens`, the load-worker registry, and rejection
of results from cancelled workers. The current implementation must not be
described as if `ImageLoadWorker` independently owns a complete document
request/generation identity contract.

Statistics and Histogram cache keys include document generation and operation
parameters. Line Profile caches by generation and line coordinates. Rapid
navigation invalidates obsolete work through current MainWindow/worker rules.

Decoded sources use a reloadable byte-budgeted working set. Pure-core
`ResidencyManager` owns exact native-source byte accounting, LRU order,
protected eviction planning, and minimal diagnostics without importing Qt or
mutating documents. `MainWindow` owns document lookup and mutation. Its
protected registered-ID set includes visible, selected, active/analysis,
current Difference-pair, and active load-target sources.

The budget is soft: protected sources may keep `used_bytes` above
`budget_bytes`, including one source larger than the entire budget. Only
unprotected resident sources are planned for oldest-first eviction. A released
document sets source and preview to `None`, clears Statistics/Histogram and
source-dependent channel-view state, becomes pending, updates its Files badge,
and reloads through the existing load-token/worker path when required again.
Successful loads refresh accounting from the new `source.nbytes`; stale or
failed loads do not add resident bytes.

Pure-core `FolderNavigationPlan` is the single index authority for PageUp,
PageDown, and next-position prediction. It accepts only one-to-six selected
registered documents from distinct folders and returns no plan when any folder
is at the requested endpoint. `MainWindow` alone applies the plan atomically.

Pure-core `PreloadController` owns the current one-position target IDs, request
generation, completion/active state, and cheap bounded counters. `MainWindow`
owns document/profile lookup, worker creation, cancellation requests, stale
validation, result application, residency mutation, and Files-state updates.
Only `plan(+1)` is preloaded after foreground loading becomes idle.

Preload request identity captures plan generation, document generation, source
path, RAW profile, exact-size policy, and the authoritative normal-load token.
Navigation or state replacement invalidates the plan and requests cooperative
cancellation. A normal load starts immediately on its own pool even when the
same source is still decoding speculatively. Late or incompatible results are
dropped; cancellation is not correctness authority. Valid results enter normal
source residency, receive no preload protection, and may be evicted immediately.
Preload failures do not mutate the document into foreground error state.
Cancellation-request de-duplication is retained only while its worker request is
active and is discarded together with that request when the worker finishes.

## Current Difference lifecycle

`DifferenceMapCache` owns order-independent native absolute maps with a
startup-selected byte budget, LRU promotion/eviction, oversized-map rejection,
and `used_bytes`, `budget_bytes`, and `entry_count` diagnostics. Metric and
preview entries are invalidated when a map leaves the cache.

P2-A2 persists the Difference Map Cache preference in MiB with a 128 MiB default
and 64–1280 MiB validation range. Startup converts MiB to bytes in frozen
`PerformanceSettings` and injects that value through `MainWindow` →
`DifferencePanel` → `DifferenceMapCache`. Saving a different value during the
session does not mutate the existing cache; the Settings dialog reports
restart-required state against the startup snapshot.

P2-B persists Decoded Source Memory independently with a 256 MiB default,
128–2560 MiB validation range, and 128 MiB UI increment. Saving either
startup-only budget never mutates its current runtime owner; the Settings dialog
compares both editable values with the startup snapshot for restart indication.
The dialog detects installed physical RAM without a production dependency. It
accepts the two configured budgets when their sum is at most 50% of detected RAM
and otherwise rejects Save without mutating either field. If detection fails,
only product bounds apply. This guard is deliberately conservative; it does not
model previews, Qt textures, workers, Python overhead, or protected soft-budget
overage and therefore is not an out-of-memory guarantee.

P2-C persists **Preload Next Folder Position**, enabled by default. It is the
third startup-only Performance setting and participates in the same restart
indication/revert/reset contract without changing the two memory budgets.

Difference Threshold and Gain are persisted analysis display defaults. They are
applied to `DifferencePanel` when `MainWindow` starts and immediately after a
Settings save; changing them does not require restart. Difference-map memory and
decoded-source residency remain separate policies.

## Current source-memory boundary

`ImageDocument.from_array()` retains both native source and preview. Decoded
Source Memory accounts only registered native `ImageDocument.source.nbytes`.
Registered programmatic sources without a reload path are counted and protected
rather than discarded. Preview arrays, Qt textures, Difference and
derived caches, channel-split documents, transient worker arrays, Python/Qt
object overhead, and process RSS are outside that accounting. The Files green
residency state means the registered document's native source is currently
resident; it does not describe Difference-map cache state.

## Current RAW boundary

`RawProfile` separates storage format, sample container, effective bit depth,
endian, alignment, dimensions, stride, offset, and grayscale/Bayer layout.
MIPI RAW10/12/14 have fixed packing rules. Decoding returns native grayscale or
Bayer mosaic arrays. Demosaic, black/white-level processing, and profile
suggestion remain outside the current implementation.

The persistent RAW JSON confirmation preference is exposed through the General
Settings page rather than the File menu. The RAW open dialog may still set the
same typed preference when the user chooses its "don't show again" option; that
single-field update preserves every other schema-v3 preference.

`Require Exact RAW File Size` is also a General preference. When disabled,
trailing bytes are allowed and undersized RAW files are rejected. When enabled,
the source byte count must exactly equal the profile requirement. The same rule
controls both worker decoding and whether a matching JSON sidecar may bypass the
profile-confirmation dialog.

## Planned P2 boundaries

The remaining target boundary is:

- `DiagnosticsSnapshot` or equivalent: deterministic, redacted, cheap-to-read
  cache/residency/worker/preload/failure state.

P2 introduces these boundaries incrementally; it is not a broad MainWindow
rewrite.

## P2 request and cancellation target

Normal load and preload require explicit request identity/token or generation
validation before applying results. Cancellation means obsolete work should be
requested to stop when possible; it does not guarantee a running decoder halts
immediately. Stale-result rejection remains mandatory even after cancellation.

## Extension and packaging boundaries

Remote REST DTO/client boundaries remain independent of widgets. All syntax and
APIs target CPython 3.10. Packaged resources must work with exactly PyInstaller
5.7 `onedir` and must not depend on the source tree or current working directory.
Packaging/signing is P7; credentials and access policy are P6.
