# Architecture

## Current boundaries and data flow

`io` discovers and decodes files into source arrays. `core.ImageDocument` owns
native source arrays, metadata, canonical preview data, generation state, caches,
and evaluation results. `core` performs display conversion, Bayer handling,
statistics/histogram, line-profile, and overflow-safe Difference math without Qt.
`workers` runs expensive I/O and numerics in bounded `QThreadPool` workers. `ui`
renders previews and emits lightweight image-coordinate state. `app` owns
documents, ordered selection, application settings composition, workspace state,
load identity, source residency, and window lifecycle.

Source arrays retain decoded dtype and channel meaning. Viewer presentation is a
derived representation and may not redefine source or analysis domains. RGBA
analysis ignores alpha. Difference and squared-error paths promote operands before
subtraction/multiplication.

## Display Gain architecture

P3-B separates **generic display gain** from **RAW metadata policy**. P3-C reuses
that same numerical core and generalizes the session/UI/worker presentation
lifecycle to ordinary Gray/RGB/RGBA and supported split-channel views.

The generic numerical model lives in `core.display_transform`:

```text
display = anchor + gain * (source - anchor)
```

`DisplayTransform` describes display low/high, gain, gain anchor, and gamma as
presentation parameters. The generic layer does not know `RawProfile`, Bayer
patterns, Black Level, White Level, or application UI state.

The generic gain implementation has these ownership rules:

- `anchor` is a scalar supplied by the caller; zero is a normal supported value;
- gain and display-range normalization are algebraically fused into float32
  scale/offset when possible;
- one float32 working buffer is used for full-frame conversion rather than
  serial full-frame subtract/multiply/add/normalize temporaries;
- full-frame gain math does not promote to float64;
- affine application accepts array views, so RGBA can target `[..., :3]` and
  leave alpha untouched;
- clipping occurs only at the final display-conversion boundary;
- source arrays are never modified.

`core.raw_display` is a RAW adapter over that generic core. It selects effective
full scale and Black-derived anchor semantics, then delegates numerical gain/range
conversion to `core.display_transform`. `core.bayer` uses the same affine helpers
on CFA parity-plane views. It does not construct a full-size Black Level map.

P3-C adds `render_ordinary_display_preview()` as the ordinary-image presentation
adapter over the same generic core:

- ordinary Gray/RGB use `anchor=0` and their canonical display range;
- ordinary RGB split-channel documents apply `anchor=0` to the native 2-D source
  plane while retaining the existing colored channel presentation;
- RGBA applies gain only to `source[..., :3]`, then copies alpha exactly from the
  canonical 1× preview into the final uint8 RGBA result;
- Difference is explicitly excluded because it owns independent Difference-panel
  Gain semantics.

The RGBA path therefore avoids a four-channel float32 gain working buffer. The
product term is **Display Gain** or **Gain**, not Exposure.

Display Gain is presentation-only. `ImageDocument.source`, pixel inspection,
Statistics, Histogram, Line Profile, Split Channel source data, Difference,
source residency, and Difference-cache identity do not depend on it.

## Current application identity and resource boundary

Canonical application assets live under
`src/pixelscope/assets/icons/pixelscope.{svg,png,ico}`. The SVG is the editable
source of truth; `scripts/generate_icon_assets.py` derives the runtime PNG and
multi-frame Windows ICO.

`pixelscope.app.resources` reads package bytes through `importlib.resources`.
On Windows, bootstrap assigns stable AppUserModelID `PixelScope.PixelScope` before
`QApplication` creation, then applies the package icon to the application and
main window. Resource lookup is independent of current working directory and
source-tree absolute paths.

This boundary supplies source-run application/window/Taskbar identity. PyInstaller
executable icon binding, shortcuts, installer identity, signing, updater, and
final release naming remain P7.

## Current application settings boundary

Application preferences and workspace/session persistence are intentionally
separate even though both use Qt persistence adapters.

- Frozen `ApplicationSettings` is the typed persisted model.
- `SettingsRepository` owns defaults, versioned migration, validation, invalid-
  state recovery, save, reset, and future-schema compatibility.
- `QSettingsAdapter` is the only application-settings component that knows raw
  preference keys.
- `Edit > Settings...` uses General, Files, and Performance pages.
- Bootstrap converts persisted performance preferences to an immutable
  byte-based `PerformanceSettings` runtime snapshot.
- `MainWindow` injects Difference-cache and decoded-source budgets into their
  independent runtime owners.
- Default Open/Export folders are live preferences; blank retains remembered
  last-used-folder behavior.
- Exact RAW-size policy is passed into foreground and preload RAW loading paths.

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

P3-B/P3-C add no key or schema migration. `DisplayGainState` is QApplication-
session state and resets to 1× on a new application session. The generic display-
gain core owns no persistence. Display Gain is not stored in application Settings,
workspace persistence, or RAW profiles.

Schema v4 migrates directly to v5 and adds enabled preload without changing v4
values. Schema v3 adds source-residency preference; valid legacy Difference-cache
values are clamped to the current maximum rather than replaced. v2/v1 and legacy
RAW confirmation keys remain supported. A future schema version is never guessed
or destructively rewritten.

`Reset Settings` resets only schema-owned application preferences. Workspace
layout reset remains separate.

## Current workspace structure

The central splitter contains Files/Analysis and the active workspace. Ordered
selection is the comparison set; Difference Image 1/Image 2 controls own the pair.

Workspace QSettings own main geometry, dock state, splitter state, layout mode,
Plots visibility, selected bottom tab, floating Plots geometry, and last-directory
state. They are not duplicated into `ApplicationSettings`.

Multi View has one fixed layout policy. `_focus_document_id` retains explicit
primary identity and `_multi_display_order` owns display promotion without
mutating Files order. `MultiCompareView._fixed_geometry()` is the sole one-to-six
geometry authority. Split Channels applies target geometry/visibility before
replacement content to preserve atomic Bayer/RGB-to-GRAY transitions.

## Current thread, request, and document lifecycle

A dedicated image-load pool runs at most two workers. A separate preload pool runs
at most one worker. The shared numerical pool runs at most four workers.
Registered file paths begin as lightweight pending documents.

Foreground image-load correctness depends on document ID, load token, worker
registry, generation/input identity, and stale-result rejection. Cancellation is
advisory; result acceptance is the correctness boundary.

Statistics/Histogram cache keys include document generation and operation
parameters. `ComparisonAnalysisPanel` also tracks current numerical-request
identity so rebinding an identical analysis request does not cancel/restart it.
Line Profile caches by generation/line coordinates.

### Display Gain runtime

The canonical `ImageDocument.preview` remains the 1× preview produced by load/read
paths. P3-C generalizes the P3-B viewer-local RAW lifecycle into one generic
`ImageViewer` Display Gain lifecycle:

- gain 1× directly reuses `ImageDocument.preview`; no full-frame gain worker is
  scheduled and no additional gained preview is retained;
- gain >1 derives a viewer-local preview from resident native source in the shared
  numerical pool;
- RAW dispatches to `render_raw_preview`; ordinary supported documents dispatch to
  `render_ordinary_display_preview`;
- task/request, document/source/canonical-preview identity, generation, requested
  gain, and visibility are checked before a result can replace presentation;
- gain changes never request source reload/decode or advance source generation;
- hidden viewers cancel obsolete logical work and restore the canonical 1×
  preview, releasing their gain>1 derived buffer;
- when shown again they regenerate the current session gain if needed;
- toolbar gain-control subscriptions use QObject receiver lifetime, so a deleted
  control cannot remain reachable as a Python closure from QApplication-global
  `DisplayGainState`.

The generic `ui.display_gain_shortcuts` command layer is scoped to
`MainWindow.central_stack` with `WidgetWithChildrenShortcut`. Therefore `+` / `-`
steps Display Gain only while focus is inside the image-presentation subtree;
sibling widgets such as the Files tree keep native Qt key routing. Shortcut
callbacks treat a destroyed toolbar control as inactive and do not touch shortcut
wrappers during parent teardown, avoiding Qt sibling-destruction-order hazards.

Generic session/control ownership lives in `ui.display_gain`; RAW metadata policy
remains in the RAW/Bayer layers. No permanent RAW-only UI compatibility wrapper is
retained.

## Current decoded-source residency boundary

Pure-core `ResidencyManager` owns exact native `ImageDocument.source.nbytes`
accounting, LRU order, protected eviction planning, and bounded diagnostics.
`MainWindow` owns document lookup/mutation and Files-state updates.

Protected registered sources include visible, selected, active/analysis,
Difference-pair, foreground-load, and promoted-preload authorities as required.
The budget is soft: protected sources may exceed it, including one required source
larger than the configured budget. Only unprotected resident sources are evicted.

Source eviction clears reloadable source/canonical preview/source-local analysis
state and returns the document to pending; reload uses the existing tokenized
worker path. Successful reload refreshes accounting from the new `source.nbytes`.

Preview arrays, Qt textures, Display Gain derived buffers, Difference maps,
channel-split documents, transient worker arrays, Python/Qt overhead, and process
RSS are outside decoded-source accounting. Difference maps remain under their own
independent byte budget.

## Current folder navigation, preload, and promotion boundary

Pure-core `FolderNavigationPlan` is the single index authority for PageUp,
PageDown, and next-position prediction. One-to-six selected registered documents
from distinct folders move atomically; any endpoint/invalid member makes the move
a no-op.

Pure-core `PreloadController` owns one-position `plan(+1)` target identity,
request generation, running/completion/promotion state, and bounded counters.
`MainWindow` owns lookup, worker creation, cancellation requests, promotion
eligibility, stale validation, result application, residency mutation, and Files
state.

Preload policy remains:

- direction `+1` only;
- depth exactly one Folder Position;
- preload concurrency one;
- normal-load pool max two;
- preload pool max one;
- speculative start only after foreground loading is idle.

An exact matching **RUNNING** preload can transfer logical authority to a new
foreground request without migrating the physical worker. Eligibility includes
exact document/generation/path/RAW-profile/exact-size/token identity, non-resident
state, running/not-cancelled request state, and absence of duplicate normal work.

Promoted success/failure delegates exactly once to the normal foreground paths.
Promotion preserves original document identity, exact source accounting, MRU/Files
state, render gating, error semantics, and stale-result rules. It does not promote
an entire group or change pool limits.

## Current runtime diagnostics lifecycle

`RuntimeDiagnosticsSnapshot` and nested source/Difference/preload/worker/failure
values are frozen, deterministic, bounded, sanitized, and observation-only.
`MainWindow.runtime_diagnostics_snapshot()` is the sole runtime aggregator.

Diagnostics may read counters and ownership state but may not touch LRUs, trigger
load/preload/Difference/rendering, mutate selection, or scan files. Recent failure
history is bounded to ten accepted failures and sanitized for paths, credentials,
bearer values, URL detail, multiline traceback context, and excess length.

The only end-user surface is **Help > Copy Diagnostics**. It formats one snapshot,
copies that exact text to the clipboard, and shows a short status confirmation.
There is no live monitor, timer, refresh loop, modal diagnostics viewer, or file
export.

## Current Difference lifecycle

P3-A gives pure-core `difference_compatibility()` authority over family
compatibility and native-versus-normalized domain selection.

- Equal effective bit depth uses compact native absolute Difference and effective
  full-scale data range.
- Mixed effective depth independently scales each native source by its own full
  scale and builds one canonical float32 absolute map in `[0,1]`.
- Normalized computation/metrics are chunked; P95/P99 use a deterministic 65,536-
  level histogram with error contract at most `1/65535` full scale.
- `CachedDifferenceMap` stores domain/data-range/family/layout/Bayer metadata while
  retaining order-independent generation-pair identity.
- Source residency and Difference-cache ownership remain independent.

Difference Threshold/Gain are separate Difference-panel presentation settings.
P3-A Difference never reads Display Gain, `RawProfile.black_level`,
`RawProfile.white_level`, `DisplayTransform`, or preview pixels. Difference
derived documents are excluded from generic Display Gain, preventing double gain.

## Current RAW boundary

`RawProfile` separates storage format, sample container, effective bit depth,
endian, alignment, dimensions, stride, offset, grayscale/Bayer layout,
`black_level`, and `white_level`. MIPI RAW10/12/14 retain fixed packing rules.
Decoding returns native grayscale or Bayer mosaic arrays in
`ImageDocument.source`.

RAW presentation policy is layered on the generic gain core:

- `raw_full_scale(bit_depth)` defines `0..((1 << bit_depth) - 1)` display range;
- 1× never subtracts Black or uses White as display high;
- gain >1 remains `B + G * (X - B)`;
- RAW Gray scalar Black is the gain anchor;
- schema-compatible GRAY tuple Black uses the legacy deterministic `min(tuple)`
  global anchor;
- Bayer tuple Black uses R/Gr/Gb/B CFA parity-specific anchors;
- split Bayer planes use their named channel anchor;
- Bayer parity-plane processing creates no full-size Black map;
- gain/range mapping uses float32 fused affine processing where possible;
- clipping occurs only during final uint8 conversion;
- `white_level` remains metadata only.

The base document preview is 1× effective-full-scale presentation. Higher RAW gain
is viewer-local and on-demand. Demosaic, white balance, CCM, tone mapping,
processed-RAW analysis, optical-Black estimation, and profile suggestion remain
outside P3-C.

The persistent RAW JSON confirmation and exact-size preferences remain General
Settings concerns. The same exact-size policy governs foreground loading,
JSON-sidecar auto-approval, preload, and promotion identity.

## P3-C extension boundary

P3-C implements the P3-B generic gain-core extension with these fixed architecture
constraints:

- one QApplication-session `DisplayGainState` serves supported ordinary and RAW
  presentations using `1× / 2× / 4× / 8× / 16×`;
- Gray/RGB use `anchor=0`;
- RGBA applies gain to RGB only and copies canonical 1× alpha exactly;
- ordinary RGB split-channel views use `anchor=0`; RAW Bayer split channels retain
  their existing named-channel Black anchor;
- RAW semantics from P3-B are unchanged;
- Difference is not a generic Display Gain target;
- user-facing terminology is **Display Gain** or **Gain**, never Exposure;
- 1× is a no-work canonical-preview reuse fast path;
- clipping is deterministic and presentation-only;
- source/generation/residency and Statistics/Histogram/Line Profile/Difference
  inputs remain unchanged;
- asynchronous gain>1 work uses explicit request identity and stale-result
  rejection, and hidden viewer-local gained previews are released;
- `+` / `-` command ownership remains `central_stack` /
  `WidgetWithChildrenShortcut`; Files-tree native expand/collapse stays intact;
- tests cover Gray/RGB/RGBA, alpha preservation, clipping, 1× identity, RAW
  regression, mixed RAW+RGB behavior, analysis/Difference independence,
  lifecycle, command/control synchronization, and Files-tree key routing.

P3-C does not gain authority to create a processed-image analysis domain merely
because viewer display is transformed. Additional RAW clipping/highlight/shadow or
Bayer observability remains optional/deferred; demosaic is not part of P3-C.

## P2/P3 boundary status

P2 runtime boundaries for settings, source residency, bounded preload,
deterministic diagnostics, and running-preload foreground reuse were completed by
PR #20. P3-A preserves them for Difference. P3-B is complete as PR #24 at
`1817490a08c61da9087efe9c3c6afd8bd85838f0`. P3-C preserves the same boundaries
while generalizing viewer Display Gain: neither the generic core nor
`DisplayGainState` becomes a Settings, source-residency, preload, Difference-cache,
or processed-source owner.

## Extension and packaging boundaries

Remote REST DTO/client boundaries remain independent of widgets. All syntax/APIs
target CPython 3.10. Packaged resources must work with exactly PyInstaller 5.7
`onedir` and must not depend on the source tree or current working directory.
Packaging/signing is P7; credentials and access policy are P6.
