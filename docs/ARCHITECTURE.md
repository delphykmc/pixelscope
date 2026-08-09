# Architecture

## Current boundaries and data flow

`io` discovers and decodes files into source arrays. `core.ImageDocument` owns
native source arrays, metadata, canonical preview data, generation state, and
source-local caches. `core` performs Bayer handling, display conversion,
statistics/histogram, line-profile, and Difference math without Qt. `workers` runs
expensive I/O and numerics in bounded `QThreadPool` workers. `ui` renders derived
presentation and emits lightweight interaction state. `app.MainWindow` owns the
registered document catalog, ordered selection, presentation orchestration,
settings composition, load identity, source residency integration, and window
lifecycle.

Native `ImageDocument.source` remains authoritative for analysis. Viewer preview
is derived presentation and must not redefine source, Difference, Statistics,
Histogram, Line Profile, Split Channel, or residency domains.

## P3-D input ownership model

P3-D separates four ownership layers:

```text
Registered
    ↓ user selection
Selected
    ↓ viewer capacity / layout
Presented
    ↓ source lifecycle
Resident when required
```

- **Registered** is catalog membership in `MainWindow.documents` / Files tree.
- **Selected** is the ordered user comparison set represented by Files selection
  plus `_selection_order`.
- **Presented** is the bounded subset currently bound to `ImageViewer` or
  `MultiCompareView` tiles.
- **Resident** is native decoded source retained by `ResidencyManager`.

The one-to-six viewer geometry is a presentation constraint, not a registration
constraint. Registration may contain arbitrary practical image/folder counts.

### Discovery contract

`io.path_discovery` owns the supported family and picker contract:

```text
.png  .bmp  .jpg  .jpeg  .raw
Supported Images (*.png *.bmp *.jpg *.jpeg *.raw)
```

Unsupported extensions are ignored and never interpreted as RAW. A `.json`
sidecar is attached only to an exact same-basename `.raw` `ImageInput`; JSON never
becomes a standalone image document.

`MainWindow._register_input()` creates or reuses pending catalog documents.
`_register_inputs()` is registration-only; callers own subsequent selection.
This separation prevents registration from implicitly resetting presentation.

### Selection-oriented image input

`Open Images...` and direct image-file drag/drop use:

```text
discover inputs
    ↓
register every supported direct file
    ↓
select the registered direct files
    ↓
present according to existing viewer capacity
```

Multi-file selection is preserved. More than six directly supplied images remain
registered and selected even though at most six are presented simultaneously in
Multi View.

### Registration-oriented folder input

`Open Folders...` uses a project-local, Qt-only non-native `QFileDialog` configured
for extended directory selection. Selected existing directories are resolved,
case-insensitively deduplicated, and deterministically ordered. No Windows COM
runtime dependency is introduced.

Opened or dropped folders use:

```text
discover supported immediate contents
    ↓
register catalog documents
    ↓
no selection change
    ↓
no presentation change
```

There is no six-folder limit and no exactly-two-folder comparison special case.
Folder registration does not call `_select_document_ids()` or `_render_selection()`.
Therefore current layout, active/focus state, ROI, Line Profile, Difference state,
Display Gain, zoom/pan preservation state, resident ownership, and Difference
cache remain untouched by the registration operation itself.

Mixed file + folder drop keeps both intents: folders register first without
selection mutation; explicit dropped files then register and become the selection.
Folder contents are never implicitly added to that explicit selection.

Folders with no supported images are skipped independently. Registration status
reports registered image/folder counts without implying presentation.

### Registered but unselected workspace

`documents > 0` with zero selected documents is a valid state. `EmptyWorkspace`
uses the same central-stack component in two modes:

- truly empty: **Drop images or folders here**, with Open Images/Open Folders;
- registered but unselected: **Select an image from Files to view**.

Actions that require presented/selected source remain unavailable until selection
creates an applicable presentation lifecycle.

## RAW profile-resolution boundary

RAW and ordinary images share the same user-facing image-open command but retain
format-specific decoding policy internally.

For direct RAW image input, `_register_input(..., resolve_raw_profile=True)` keeps
the existing P3-D contract before direct-file registration:

- valid same-basename sidecar → parse/validate and preserve confirmation plus
  exact/minimum-size policy;
- no sidecar → editable `RawOpenDialog`;
- invalid sidecar → warning then editable fallback;
- cancel → no new direct-open RAW document;
- multiple RAW inputs → each resolves independently;
- existing RAW path retains document identity and may be marked pending for reload
  with corrected profile metadata.

Folder registration uses `_register_input(..., resolve_raw_profile=False)`. It
records the RAW path and deterministic sidecar path but does not show a dialog or
decode the source. `_ensure_loaded()` becomes the lazy foreground boundary: when a
pending RAW without resolved profile is actually selected/presented, it invokes
the same `_confirm_raw_profile()` policy and only then starts `ImageLoadWorker`.

Unresolved RAW is skipped by speculative preload because `_refresh_preload_plan()`
requires an existing resolved RAW profile before constructing a RAW preload
worker. This avoids registration-time dialog storms without guessing profiles or
redesigning the P2 worker/residency system.

`RawProfile` JSON migration remains the durable compatibility boundary. P3-D adds
no profile-library persistence, profile schema version, last-profile reuse,
size-only/fuzzy matching, sensor inference, or automatic Black/White estimation.

## Workspace and Folder Position

Files groups documents by parent folder in natural filename order. Folder catalog
membership and active comparison membership are independent.

`_folder_navigation_selection()` derives Folder Position only from currently
selected documents. It accepts one to six selected documents from distinct
folders. `FolderNavigationPlan` is the single index authority for PageUp/PageDown
and next-position prediction. Other registered folders do not participate.

A valid PageUp/PageDown plan atomically replaces the selected documents with the
corresponding previous/next members while preserving the existing Folder Position
view/overlay policy. Endpoint or invalid-member plans remain no-ops.

Multi View geometry remains fixed by `MultiCompareView._fixed_geometry()` and
`MainWindow._effective_layout()`; one-to-six simultaneous presentation remains the
viewer contract. Larger registered/selected catalogs are not truncated at
registration time.

## Display Gain architecture

P3-B separates generic display gain from RAW metadata policy; P3-C generalizes the
same presentation lifecycle to ordinary Gray/RGB/RGBA and split-channel views.

```text
display = anchor + gain * (source - anchor)
```

`core.display_transform` owns scalar-anchor affine math and knows nothing about
`RawProfile`, Bayer patterns, or UI state. Gain/range mapping is fused in float32
where possible, avoids serial full-frame temporaries and float64 promotion, works
on channel views, clips only at final display conversion, and never mutates source.

`core.raw_display` selects RAW effective-full-scale and Black-derived anchors.
`core.bayer` applies per-CFA anchor/range operations on parity-plane views instead
of constructing a full-size Black map. Ordinary Gray/RGB use anchor 0; RGBA gains
RGB only and preserves canonical alpha. Difference is excluded because it owns an
independent presentation Gain.

Display Gain is presentation-only. `ImageDocument.source`, pixel inspection,
Statistics, Histogram, Line Profile, Split Channel data, Difference, source
residency, and Difference cache identity are independent of it.

The canonical 1× preview is reused directly. Gain >1 derives viewer-local preview
from already resident native source on the shared numerical pool. Request identity,
generation, source/preview identity, requested gain, and visibility gate result
acceptance. Hidden viewers release obsolete derived buffers.

## Settings boundary

Frozen `ApplicationSettings` plus `SettingsRepository` own versioned application
preferences. Workspace layout/session QSettings remain separate.

Schema version 5 owns RAW JSON confirmation, exact RAW size, default Open/Export
directories, Difference Threshold/Gain, Difference Map Cache MiB, Decoded Source
Memory MiB, and preload enablement.

P3-B/P3-C/P3-D add no setting/schema migration. Display Gain is QApplication-
session state. P3-D creates no Settings-owned RAW profile collection. `Reset
Settings` remains separate from workspace-layout reset.

## Thread and request lifecycle

Foreground image loading uses a dedicated max-two pool. Preload uses a separate
max-one pool. Numerical analysis/display work uses the bounded shared numerical
pool.

Registered documents begin as lightweight pending documents. Foreground load
correctness depends on document ID, load token, generation/input identity, worker
registry, and stale-result rejection. Cancellation is advisory; result acceptance
is authoritative.

Selection/presentation triggers `_ensure_loaded()` only for the current applicable
presentation/analysis subset. Registration alone does not decode unrelated images.

Statistics/Histogram request identity includes generation and operation parameters
so rebinding an unchanged request does not restart work. Line Profile caches by
generation and line coordinates.

## Source residency boundary

`ResidencyManager` owns exact native `ImageDocument.source.nbytes` accounting, LRU
order, protected eviction planning, and bounded diagnostics. `MainWindow` owns
actual document mutation and Files-state updates.

Visible, selected, active/analysis, Difference-pair, foreground-load, and promoted-
preload authorities are protected as applicable. The budget is soft: protected
sources may exceed it, including one required source larger than budget. Only
unprotected resident sources are evicted.

Registration does not add residency bytes. Eviction clears reloadable native source
and source-local caches, returns the document to pending, and preserves its catalog
identity. Preview arrays, Qt textures, Display Gain buffers, Difference maps,
split-channel derivatives, worker temporaries, and process RSS are outside decoded-
source accounting.

## Preload and promotion boundary

Preload remains tied to the predicted `+1` Folder Position of the current selected
comparison set:

- direction +1 only;
- depth exactly one Folder Position;
- max-one preload worker;
- max-two normal-load workers;
- speculative start only when foreground loading is idle.

An exact matching physically RUNNING preload may transfer logical authority to
foreground without duplicate decode. Eligibility includes exact document,
generation, source-path, RAW-profile, exact-size-policy, and token identity plus
non-resident/running/not-cancelled state.

Promoted success/failure delegates once to normal foreground paths. Folder
registration alone does not create new speculative work; unresolved RAW without a
profile is not preloaded.

## Difference boundary

`difference_compatibility()` owns family compatibility and native-versus-normalized
domain selection.

- Equal effective bit depth keeps compact native Difference and effective full
  scale.
- Mixed depth independently normalizes each native source and stores one canonical
  float32 absolute map in `[0,1]`.
- Normalized metrics are bounded/chunked; P95/P99 use the deterministic 65,536-
  level histogram contract.
- `CachedDifferenceMap` stores domain/data-range/family/layout/Bayer metadata while
  retaining order-independent generation-pair identity.
- Difference cache ownership remains independent from source residency.

Difference never consumes general Display Gain, RAW Black/White metadata,
`DisplayTransform`, or preview pixels. Folder-only registration does not invalidate
Difference cache or presentation because it does not change the current selected
pair/presentation lifecycle.

## RAW decode/display boundary

`RawProfile` separates storage format, unpacked container, effective bit depth,
endian/alignment, dimensions, stride/offset, Gray/Bayer layout, Bayer pattern,
Black Level, and White Level. MIPI RAW10/12/14 retain fixed packing rules. Decoding
returns native grayscale/Bayer mosaic arrays in `ImageDocument.source`.

RAW display policy remains:

- native effective full scale at 1×;
- 1× does not subtract Black or use White as display maximum;
- gain >1 uses `B + G * (X - B)`;
- Gray scalar Black is the scalar anchor;
- schema-compatible Gray tuple Black keeps deterministic legacy global anchor;
- Bayer tuple Black uses R/Gr/Gb/B parity-specific anchors;
- split Bayer planes use the corresponding named anchor;
- no full-frame Black map;
- float32 fused affine processing where possible;
- clipping only at final uint8 conversion;
- White Level remains metadata only.

Demosaic, white balance, CCM, tone mapping, processed-RAW analysis, optical-Black
estimation, and profile suggestion remain outside the current boundary.

## Runtime diagnostics and release boundaries

`RuntimeDiagnosticsSnapshot` is frozen, deterministic, bounded, sanitized, and
observation-only. The sole product surface is **Help > Copy Diagnostics**; no live
monitor/timer is introduced.

Canonical application icon assets are package resources and source-run Windows
identity is established before QApplication creation. PyInstaller executable icon
binding, shortcuts, installer identity, signing, updater, and final distribution
remain P7. Remote REST/client boundaries remain independent of widgets. All APIs
target CPython 3.10.
