# Architecture

## Boundaries and data flow

`io` discovers and decodes files into source arrays. `core.ImageDocument` owns
source arrays, metadata, preview data, generation state, caches, and evaluation
results. `core` performs display conversion, Bayer plane handling,
statistics/histogram, line-profile, and overflow-safe Difference math without
Qt. `workers` executes expensive I/O and numerics in bounded `QThreadPool`
workers. `ui` renders previews and emits lightweight image-coordinate state.
`app` owns documents, ordered selection, view state, persistence, request
identity, generation checks, and window lifecycle. `remote` defines versioned
DTOs and clients independently of widgets.

Source arrays retain decoded dtype and channel meaning: grayscale, RGB/RGBA, or
Bayer. Display conversion creates uint8 previews without modifying source data.
RGBA analysis ignores alpha. Difference and squared-error paths promote
operands before arithmetic.

## Workspace structure

The central splitter contains the Files/Analysis sidebar and the active
workspace. Files is a two-level tree with non-selectable folder roots and
naturally sorted selectable files. Ordered selection is the comparison set;
Difference Image 1/Image 2 controls are the comparison-pair authority.

Histogram and Line Profile live in a bottom `QDockWidget`. It can be hidden,
floated, maximized, and restored. `QSettings` persists main geometry, dock state,
splitter state, layout mode, Plots visibility, selected bottom tab, and
independent floating Plots geometry. The custom Plots title bar uses the same
maximize/restore state machine for its button and title-bar double-click.

Multi View uses one fixed layout policy: side-by-side for two, enlarged
primary-first layouts for three and five, 2×2 for four, and 3×2 for six. The
first displayed image is the implicit primary when no valid explicit primary
exists. MainWindow retains the explicit primary identity in
`_focus_document_id` and owns display promotion through `_multi_display_order`;
Files selection order and logical document IDs are not mutated.
`MultiCompareView._fixed_geometry()` is the sole one-to-six geometry policy;
there is no runtime arrangement registry, field, menu, or persisted setting.

Split Channels uses fixed transient component order. Target viewer geometry and
visibility are applied before replacement channel content is bound, and updates
are suppressed only for the replacement batch. This keeps Bayer/RGB-to-GRAY
transitions visually atomic without changing loading-placeholder or stale-result
rules.

## Thread, request, and document lifecycle

Registered paths start as lightweight pending documents. A dedicated load pool
uses at most two workers; the shared numerical pool uses at most four. Every
task carries task/document/generation identity. Results return to the UI thread
and apply only when the complete request signature is current.

Statistics and Histogram cache keys include document generation, half-open ROI,
bit-depth/bin specification, and range. Line Profile caches by generation and
inclusive line coordinates. Rapid navigation invalidates obsolete loads and
coalesces analysis work.

Decoded source images use a reloadable working set. MainWindow tracks recency,
keeps at most seven resident source arrays, protects visible/analysis documents,
and clears dependent channel views when evicting. This is an interim
count-based policy; byte budgeting and one-group-ahead preload are not present.

## Difference lifecycle

`DifferenceMapCache` owns order-independent native absolute maps with a default
512 MiB byte budget, LRU promotion/eviction, oversized-map rejection, and
diagnostics. Metric and preview entries are invalidated when a map leaves the
cache. Channel, gain, threshold mask, display preview, and full/ROI metrics
derive from the native map.

Display-only changes update the Difference tile without re-uploading unchanged
source previews. Six sources plus Difference force Single View until Difference
is disabled.

## RAW boundary

`RawProfile` describes storage format separately from container representation.
Unpacked data supports `uint8`/`uint16`, effective bit depth, endian, and LSB/MSB
alignment. Packed MIPI RAW10/12/14 use fixed group layouts decoded in
`io.raw_reader`. Width, stride, offset, required file size, and profile
compatibility are validated before decoding.

RAW decoding returns native grayscale or Bayer mosaic arrays. Demosaic,
black/white-level processing, and profile suggestion must remain behind RAW/core
interfaces and must not be embedded in the dialog or viewer.

## Extension and packaging boundaries

The REST job state machine is create, poll, result, or cancel/failure; the
synchronous HTTP client must run in a worker. All syntax and APIs target CPython
3.10. Packaged resource access must work with exactly PyInstaller 5.7 `onedir`
and must not depend on the source tree or current working directory.
