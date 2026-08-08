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
version is not guessed or rewritten; the current process uses safe defaults and
exposes application settings as read-only compatibility state.

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
of results from obsolete authority. `ImageLoadWorker` remains a physical work
unit; `MainWindow` owns foreground authority and token acceptance.

Statistics/Histogram cache keys include document generation and operation
parameters. P2-F also gives `ComparisonAnalysisPanel` an explicit current
numerical-request identity over the loaded document/source identity, generation,
channel-layout/Bayer semantics, ROI, and histogram specification. Rebinding the
same selected analysis set during presentation-only Single View navigation is
therefore idempotent: an identical scheduled request is not rescheduled, an
identical running worker is not cancelled/recreated, and an identical completed
result is not rerendered. A changed numerical identity still cancels obsolete
work when present and follows the normal cache/recompute path. Line Profile
continues to cache by generation and line coordinates.

Decoded sources use a reloadable byte-budgeted working set. Pure-core
`ResidencyManager` owns exact native-source byte accounting, LRU order,
protected eviction planning, and minimal diagnostics without importing Qt or
mutating documents. `MainWindow` owns document lookup and mutation. Its
protected registered-ID set includes visible, selected, active/analysis,
current Difference-pair, active normal-load targets, and any promoted preload
that currently has foreground authority.

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
generation, completion/active state, explicit running state, promotion state,
and cheap bounded counters. `MainWindow` owns document/profile lookup, worker
creation, cancellation requests, promotion eligibility, stale validation,
result application, residency mutation, and Files-state updates. Only
`plan(+1)` is preloaded after foreground loading becomes idle.

Preload request identity captures plan generation, document generation, source
path, RAW profile, exact-size policy, and the authoritative normal-load token.
The existing `TaskWorker.started` signal marks an accepted preload request as
physically RUNNING. Queued/not-started work is not promotion-eligible.

### Running preload promotion

P2-E adds one narrow authority transition:

```text
speculative running preload
        ↓ exact foreground request identity matches
foreground authority promotion
        ↓ same physical ImageLoadWorker stays in preload QThreadPool
normal foreground success/failure semantics
```

Promotion is not thread migration and does not create a generic scheduler. The
physical worker remains in the dedicated max-one preload pool. Only its logical
runtime authority changes from speculative to foreground-required.

Before selection/navigation invalidates the old preload plan, `MainWindow`
checks future foreground-required document IDs for a matching RUNNING preload.
Eligibility requires all of the following to remain exact:

- target document ID and registered-document existence,
- document generation,
- source-path identity,
- RAW profile identity,
- exact RAW-size policy,
- the captured normal-load token,
- non-resident source state,
- worker present and physically RUNNING,
- no prior cancellation,
- no stale/superseded request,
- no normal foreground worker already decoding the same target.

On acceptance, `PreloadController` records the request as promoted and removes it
from speculative active/cancellation ownership. `MainWindow` advances the
normal-load token to create current foreground authority, marks the document
Loading, protects it as foreground-required residency input, and continues the
selection/navigation transition. Subsequent old-plan invalidation skips the
promoted worker. `_ensure_loaded()` therefore does not start a duplicate normal
worker for that document.

A promoted worker remains physically present in `_preload_workers` until it
finishes. Consequently no new speculative preload starts while that promoted
foreground decode is still using the max-one preload pool. Other foreground
members of a pair/group remain free to use the ordinary max-two normal pool; P2-E
does not attempt to promote a whole group.

Promoted success is validated again against current document/request/token/RAW
identity and then delegated exactly once to the existing normal
`_load_succeeded()` path. This preserves document identity/generation, exact
`source.nbytes` residency accounting, MRU touch, Files residency state,
selected-batch render gating, ordinary eviction, and Ready/status behavior. The
same result is never first applied as speculative success and then applied again
as foreground success.

Promoted failure is likewise delegated exactly once to `_load_failed()` when the
foreground authority is still current. It therefore uses the normal document
error/status path and P2-D `foreground-load/decode` Recent Failure category; it
is not also recorded as a speculative preload failure.

If foreground navigation moves away before completion, `_cancel_obsolete_loads()`
handles the promoted worker as foreground authority: cancellation is requested,
the foreground token is invalidated, and Loading may return to pending. As with
all other asynchronous loading, cancellation remains advisory. A decoder that
finishes late cannot apply its result because token/generation/request identity
is the correctness authority.

Completed speculative preload behavior is unchanged: a valid result enters
ordinary source residency with no speculative protection and may be evicted
immediately. Already-resident next targets remain the immediate-reuse fast path.
Unmatched/stale/cancelled/not-started preload requests fall back to the existing
normal-load correctness path.

The preload policy itself remains unchanged by promotion and P2-F: direction
`+1` only, depth exactly one Folder Position, preload concurrency fixed one,
normal pool max two, and preload pool max one. Previous/bidirectional/deeper
preload, worker-count settings, CPU aggressiveness, and broader resource tuning
remain post-P2 evidence-driven optimization candidates.

## Current runtime diagnostics lifecycle

P2-D established deterministic, inexpensive, sanitized runtime observability for
automated validation, P2-F characterization, and support troubleshooting. The
only end-user surface is an on-demand `Help > Copy Diagnostics` action.

`RuntimeDiagnosticsSnapshot` and its nested source, Difference-cache, worker-pool,
and failure values are frozen, Qt-free domain models. The snapshot reuses the
existing `PreloadDiagnostics` value instead of introducing duplicate preload
state. P2-E adds only one cumulative counter, `promotion_count`.

`MainWindow.runtime_diagnostics_snapshot()` is the sole runtime aggregator. It
reads `ResidencyManager` byte/count properties, `DifferenceMapCache` byte/entry
properties, the foreground/preload worker registries and pool maxima, existing
preload diagnostics, the foreground stale-drop counter, and a ten-entry recent
failure deque. It does not call cache `get()`, residency `touch()`, preload plan
refresh, worker start/cancel, selection/render, or filesystem discovery.

A promoted physical preload worker is classified by logical authority: it is
counted once as foreground activity and excluded from speculative preload active
counts. `PreloadDiagnostics.active_worker_count` likewise represents only
speculative active requests. **Copy Diagnostics** includes
`Promoted to foreground: N`. The physical pool limits remain normal max two and
preload max one; promotion does not change either limit.

Foreground load token/document rejections increment the foreground stale counter.
Accepted current foreground-load and speculative-preload failures enter the
recent deque with a subsystem/category, exception type, and short message. A
promoted failure uses the foreground path only. A speculative preload failure
from an obsolete cancelled or replanned generation is rejected by
`PreloadController.record_failure()` before it can enter recent failure history.
Sanitization removes Windows/POSIX absolute paths, URL detail, complete
credential-like assignment values including unquoted multi-word values, bearer
values, multiline traceback context, and excess length; raw traceback and image
content are never stored in diagnostics.

`format_runtime_diagnostics()` is pure and emits a fixed section/field order with
no timestamp. `MainWindow.copy_diagnostics()` takes one current snapshot, formats
it once, copies that exact sanitized text to `QApplication.clipboard()`, and shows
`Diagnostics copied to clipboard` in the status bar. There is no diagnostics
modal, live monitor, timer, refresh control, or diagnostics text-file export.
Copying remains observation-only with respect to workers, navigation, render,
preload counters/policy, and both LRU owners.

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
indication/revert/reset contract without changing the two memory budgets. P2-E
and P2-F add no Performance setting.

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
single-field update preserves every other current preference.

`Require Exact RAW File Size` is also a General preference. When disabled,
trailing bytes are allowed and undersized RAW files are rejected. When enabled,
the source byte count must exactly equal the profile requirement. The same rule
controls worker decoding, JSON-sidecar auto-approval, and preload/promotion
identity matching.

## P2-F characterization boundary

P2-F does not add a new production ownership layer. It exercises the existing
`io`, `core`, `workers`, `ui`, and `app` boundaries and records evidence against
their existing contracts. A focused `ComparisonAnalysisPanel` lifecycle hardening
is permitted because Windows characterization demonstrated duplicate identical
analysis preparation/cancellation during presentation-only navigation; this does
not introduce a new scheduler or ownership boundary.

The representative performance matrix uses FHD RGB uint8, FHD grayscale uint16,
and UHD Bayer uint16 profile-described RAW synthetic/temp data; the existing real
4K RGB and RGGB10-u16 integration fixtures remain complementary coverage. The
matrix observes raw-document load/Bayer analysis/difference/metric/threshold
timings when useful, but elapsed time is never an automated PASS/FAIL condition.
Deterministic shape, dtype, values/counts, native byte accounting, Difference
results, worker ownership, decode count, request identity, and stale-result
rejection are the merge gates.

Source residency and `DifferenceMapCache` remain independent byte-budget owners.
P2-F does not add process-RSS accounting and does not reinterpret preview arrays,
Qt textures, derived caches, worker temporaries, or Python/Qt overhead as source
residency. Completed speculative preload remains ordinary unprotected residency;
a promoted running preload uses foreground-required protection through the
existing authority path.

Diagnostics remain observation-only and sanitized. Characterization may read the
snapshot API but may not introduce a live monitor, timer, export surface, LRU
touch, load/preload/cancellation, render, Difference calculation, or filesystem
scan as a side effect of observation.

There is currently no GitHub Actions workflow. A Windows Qt gate is deferred
until PySide6/pytest-qt/offscreen reliability and suite runtime/resource use can
be observed on the target runner. P2-F therefore keeps owner/local Windows
validation as authoritative closure evidence; packaging/installer CI remains P7.

## P2 boundary status

The P2 runtime boundaries for settings, source residency, bounded preload,
deterministic diagnostics, and running-preload foreground reuse are implemented
incrementally without a broad `MainWindow` rewrite. P2-F is active as the final
characterization/hardening and documentation closure slice. Its analysis-request
idempotency fix is a local lifecycle guard and does not alter settings, resource,
preload, Difference, or diagnostics ownership.

## P2 request and cancellation target

Normal load, speculative preload, promoted foreground authority, and numerical
analysis work require explicit request identity or generation/input validation
before results are applied. Cancellation means obsolete work should be requested
to stop when possible; it does not guarantee a running decoder or numerical
kernel halts immediately. For that reason, an unchanged numerical analysis
request must not be cancelled and recreated merely because presentation state is
rebound. Stale-result rejection remains mandatory after genuinely obsolete work
is cancelled.

## Extension and packaging boundaries

Remote REST DTO/client boundaries remain independent of widgets. All syntax and
APIs target CPython 3.10. Packaged resources must work with exactly PyInstaller
5.7 `onedir` and must not depend on the source tree or current working directory.
Packaging/signing is P7; credentials and access policy are P6.
