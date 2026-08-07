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
  the RAW JSON confirmation preference, default Open/Export folders, and the
  Difference-cache MiB preference.
- `SettingsRepository` owns defaults, versioned schema behavior, migration,
  validation, invalid-state recovery, save, and reset.
- `QSettingsAdapter` is the only application-settings component that knows raw
  application-preference keys. QSettings is an adapter, not the domain model.
- `Edit > Settings...` uses a category/page template with **General**, **Files**,
  and **Performance** pages. The left navigation is intentionally simple at the
  current settings count; a VS Code-style settings search is not required yet.
- Application bootstrap loads `ApplicationSettings`, converts the Difference
  cache preference to an immutable byte-based `PerformanceSettings` startup
  snapshot, and passes both settings objects plus the repository to
  `MainWindow`.
- `MainWindow` injects `PerformanceSettings.difference_cache_bytes` into
  `DifferencePanel`, which passes the fixed budget to `DifferenceMapCache`.
  Neither the panel nor the cache reads persistence.
- Default Open/Export folders are live preferences. A blank value preserves the
  existing last-used-folder behavior; a configured existing folder only changes
  the starting location of the corresponding file dialog.
- Runtime edits to startup-only performance values are persisted for the next
  launch; existing runtime caches are not mutated.

Schema version 2 owns:

- `settings/schema_version`
- `settings/general/dont_show_raw_json_profiles`
- `settings/files/default_open_directory`
- `settings/files/default_export_directory`
- `settings/performance/difference_cache_mib`

Schema version 1 is migrated by preserving the existing RAW and Difference-cache
values and adding blank file-location preferences. Legacy
`raw/dont_show_json_profiles` remains migration input only. Invalid current
values normalize to validated defaults. A future schema version is not guessed
or rewritten; the current process uses safe defaults and exposes application
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

A dedicated image-load pool runs at most two workers. The shared numerical pool
runs at most four. Registered paths begin as lightweight pending documents.

Normal image-load stale-result validation primarily depends on the target
document ID, `MainWindow._load_tokens`, the load-worker registry, and rejection
of results from cancelled workers. The current implementation must not be
described as if `ImageLoadWorker` independently owns a complete document
request/generation identity contract.

Statistics and Histogram cache keys include document generation and operation
parameters. Line Profile caches by generation and line coordinates. Rapid
navigation invalidates obsolete work through current MainWindow/worker rules.

Decoded sources use a reloadable working set owned by `MainWindow`. Recency and
a protected set of visible documents and active load targets are used to keep at
most seven native source arrays resident, with dependent channel state cleared
during eviction. This is a count-based UI/application policy, not a byte-based
manager. Selected and analysis documents are not yet explicit policy inputs;
those protections are planned for P2-B.

## Current Difference lifecycle

`DifferenceMapCache` owns order-independent native absolute maps with a
startup-selected byte budget, LRU promotion/eviction, oversized-map rejection,
and `used_bytes`, `budget_bytes`, and `entry_count` diagnostics. Metric and
preview entries are invalidated when a map leaves the cache.

P2-A2 persists the user preference in MiB with a 512 MiB default and 64–8192 MiB
validation range. Startup converts MiB to bytes in frozen `PerformanceSettings`
and injects that value through `MainWindow` → `DifferencePanel` →
`DifferenceMapCache`. Saving a different value during the session does not
mutate the existing cache; the Settings dialog reports restart-required state
against the startup snapshot.

Difference-cache memory and decoded-source residency are separate policies.

## Current source-memory boundary

`ImageDocument.from_array()` retains both native source and preview. A future
source-residency budget therefore accounts only native decoded source arrays and
must not be presented as process memory. Preview arrays, Qt textures, Difference
and derived caches, and transient worker arrays are outside that accounting.

## Current RAW boundary

`RawProfile` separates storage format, sample container, effective bit depth,
endian, alignment, dimensions, stride, offset, and grayscale/Bayer layout.
MIPI RAW10/12/14 have fixed packing rules. Decoding returns native grayscale or
Bayer mosaic arrays. Demosaic, black/white-level processing, and profile
suggestion remain outside the current implementation.

The persistent RAW JSON confirmation preference is exposed through the General
Settings page rather than the File menu. The RAW open dialog may still set the
same typed preference when the user chooses its "don't show again" option.

## Planned P2 boundaries

The following are target boundaries, not implemented components:

- `ResidencyManager`: native-source byte accounting, protected LRU, soft-budget
  policy, eviction/reload, invalidation, and diagnostics. Its user-facing source
  budget belongs on the existing Performance Settings page when P2-B lands.
- `PreloadController`: one-group-ahead planning, bounded ownership, normal-load
  priority, cancellation requests, stale-result rejection, and retention. Its
  enabled/default choice belongs on Performance when P2-C lands.
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
