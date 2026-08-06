# Architecture

## Current boundaries and data flow

`io` discovers and decodes files into source arrays. `core.ImageDocument` owns
native source arrays, metadata, preview data, generation state, caches, and
evaluation results. `core` performs display conversion, Bayer handling,
statistics/histogram, line-profile, and overflow-safe Difference math without
Qt. `workers` runs expensive I/O and numerics in bounded `QThreadPool` workers.
`ui` renders previews and emits lightweight image-coordinate state. `app`, and
primarily `MainWindow`, currently owns documents, ordered selection, workspace
state, QSettings persistence, load identity, source residency, and window
lifecycle.

Source arrays retain decoded dtype and channel meaning. Display conversion
creates uint8 previews without modifying native source data. RGBA analysis
ignores alpha. Difference and squared-error paths promote operands first.

## Current workspace structure

The central splitter contains Files/Analysis and the active workspace. Ordered
selection is the comparison set; Difference Image 1/Image 2 controls own the
comparison pair.

Histogram and Line Profile live in a bottom `QDockWidget`. QSettings persists
main geometry, dock state, splitter state, layout mode, Plots visibility,
selected bottom tab, and floating Plots geometry. The custom title bar shares a
maximize/restore state machine between its button and title double-click.

Multi View uses one fixed layout policy. `_focus_document_id` retains explicit
primary identity and `_multi_display_order` owns display promotion without
mutating Files order or logical IDs. `MultiCompareView._fixed_geometry()` is the
sole one-to-six geometry authority; no runtime arrangement registry, action,
field, or persisted arrangement remains.

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
protected visible/analysis documents are used to keep at most seven native
source arrays resident, with dependent channel state cleared during eviction.
This is a count-based UI/application policy, not a byte-based manager.

## Current Difference lifecycle

`DifferenceMapCache` owns order-independent native absolute maps with a 512 MiB
default byte budget, LRU promotion/eviction, oversized-map rejection, and
`used_bytes`, `budget_bytes`, and `entry_count` diagnostics. Metric and preview
entries are invalidated when a map leaves the cache.

`DifferencePanel` accepts the cache budget at construction. Frozen
`PerformanceSettings` currently contains only `difference_cache_bytes`, but the
application bootstrap creates `MainWindow` directly and does not load/inject
that startup snapshot. Current behavior therefore relies on the panel default.

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

## Planned P2 boundaries

The following are target boundaries, not implemented components:

- `SettingsRepository`: schema-aware load/save/reset and migration.
- typed `ApplicationSettings`: validated persisted choices.
- immutable `PerformanceSettings`: one startup snapshot injected into runtime
  services; later edits require restart.
- `ResidencyManager`: native-source byte accounting, protected LRU, soft-budget
  policy, eviction/reload, invalidation, and diagnostics.
- `PreloadController`: one-group-ahead planning, bounded ownership, normal-load
  priority, cancellation requests, stale-result rejection, and retention.
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
