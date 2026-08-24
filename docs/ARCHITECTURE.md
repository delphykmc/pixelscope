# Architecture

## Current boundaries and data flow

`io` discovers and decodes files into source arrays. `core.ImageDocument` owns
native source arrays, metadata, canonical preview data, generation state, and
source-local caches. `core` performs Bayer handling, display conversion,
statistics/histogram, line-profile, and Difference math without Qt. `workers` runs
expensive I/O and numerics in bounded `QThreadPool` workers. `ui` renders derived
presentation and emits lightweight interaction state. `app.MainWindow` owns the
registered document catalog, ordered selection, Current Comparison Page derivation,
presentation orchestration, settings composition, load identity, source residency
integration, and window lifecycle.

`core/` and `io/` must not import PySide6 or pyqtgraph. The repository enforces this
stable numerical/presentation boundary in `tests/unit/test_architecture_boundaries.py`.

Native `ImageDocument.source` remains authoritative for analysis. Viewer preview
is derived presentation and must not redefine source, Difference, Statistics,
Histogram, Line Profile, Split Channel, or residency domains.

## P3-D input and comparison ownership model

P3-D separates five runtime layers:

```text
Registered
    ↓ user selection
Selected
    ↓ Selected ordering + page offset / size 6
Current Comparison Page
    ↓ viewer representation
Presented
    ↓ native-source lifecycle
Resident when required
```

- **Registered** is catalog membership in `MainWindow.documents` / Files tree.
- **Selected** is the ordered logical comparison set represented by Files selection
  plus `_selection_order`; it may exceed six images.
- **Current Comparison Page** is a derived bounded view of Selected, calculated from
  Selected ordering and `_page_start` with `COMPARISON_PAGE_SIZE = 6`. It is not a
  separately owned document collection.
- **Presented** is the viewer representation of that page. Multi View presents the
  current page; Single View presents one active image while retaining page context.
- **Resident** is native decoded source retained by `ResidencyManager` only while
  required by current correctness/runtime owners.

`MainWindow.current_comparison_documents()` is the semantic authority for the
bounded comparison working set. The following consume the same page:

- Multi View binding and Single View page context;
- Statistics and Histogram;
- Line Profile;
- selection-derived Difference inputs;
- ROI/Line normalization;
- foreground page-load completion;
- current-page source-residency protection;
- local viewer slot mapping.

Feature-owned explicit Difference pair/reference authority remains separate.

`Analysis Working Set = Current Comparison Page`.
Viewer slots are always `1..6` within the Current Comparison Page. A global Selected
ordinal is never used as a viewer slot.

The six-image Current Comparison Page is a working-set boundary, not a registration
or logical-selection limit. Registration and Selected may contain arbitrary
practical image counts.

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
The obsolete exactly-two-folder `pair_folders()` abstraction is not part of the
P3-D input architecture.

### Selection-oriented image input

`Open Images...` and direct image-file drag/drop use:

```text
discover inputs
    ↓
register every supported direct file
    ↓
replace current Selected with the ordered direct-file set
    ↓
derive Current Comparison Page
    ↓
present current page
```

Multi-file selection is preserved. More than six directly supplied images remain
registered and Selected. The first Current Comparison Page contains images 1–6;
later pages are reached without changing Selected membership/order.

### Registration-oriented folder input

`Open Folder...` uses the native single-directory
`QFileDialog.getExistingDirectory()` path and registers one folder per invocation.
Multiple-folder registration remains supported through folder drag/drop and the
registration API, with deterministic resolved-path deduplication where multiple
paths are supplied. No custom multi-directory picker or Windows COM dependency is
introduced.

Opened or dropped folders use:

```text
discover supported immediate contents
    ↓
register catalog documents
    ↓
no Selected change
    ↓
no Current Comparison Page change
    ↓
no presentation change
```

There is no six-folder limit and no exactly-two-folder comparison special case.
Folder registration does not call `_select_document_ids()` or `_render_selection()`.
Therefore current layout, active/primary state, ROI, Line Profile, Difference state,
Display Gain, zoom/pan preservation state, resident ownership, and Difference
cache remain untouched by the registration operation itself.

Mixed file + folder drop keeps both intents: folders register first without
selection mutation; explicit dropped files then register and become Selected.
Folder contents are never implicitly added to that explicit selection.

Folders with no supported images are skipped independently. Registration status
reports registered image/folder counts without implying presentation.

### Registered but unselected workspace

`documents > 0` with zero selected documents is a valid state. `EmptyWorkspace`
uses the same central-stack component in two modes:

- truly empty: **Drop images or folders here**, with Open Images/Open Folder;
- registered but unselected: **Select an image from Files to view**.

Actions that require a Selected/current-page source remain unavailable until
selection creates an applicable comparison lifecycle.

## Current Comparison Page navigation

The page size is conceptually fixed at six even when Single View presents only one
image. `_view_capacity` is therefore not the logical page-size authority.

For `Selected <= 6`, Current Comparison Page equals Selected and existing
Auto/Single/Multi semantics remain unchanged.

For `Selected > 6`:

- `_page_start` is aligned in six-image increments and page membership is derived
  from Selected ordering;
- Previous/Next Comparison Page are separate coarse actions using
  `Ctrl+Left` / `Ctrl+Right` with non-wrapping endpoints; their application-wide
  `QShortcut` is enabled only while movement in that direction is available, so unavailable
  Ctrl+Arrow input remains owned by the focused control;
- the presentation-control row above the image workspace keeps Page status and the
  current Selected range visible even for a single page; previous/next arrows remain
  present and disable at unavailable endpoints;
- `Left` / `Right` remain Previous/Next Selected Image fine navigation across the
  complete ordered Selected set;
- fine navigation crossing a page boundary updates `_page_start` so the active
  image remains inside Current Comparison Page;
- number keys `1..6` use the current page-local slot in Single View;
- page movement preserves the active local slot when possible and clamps it on a
  short final page;
- primary/focus reordering is applied only to documents already in the Current
  Comparison Page and does not change Selected ordering or page membership;
- large-selection Multi View uses six-slot `Grid 3x2` geometry even on a partial
  final page; unused slots are cleared rather than reflowing to 3/4/5-image
  geometry.

`MultiCompareView.set_documents()` accepts a fixed geometry count and local-slot
presentation mode for this bounded large-selection case. For `Selected <= 6`, the
existing fixed two/three/four/five/six geometry contract is retained.

### Split Channels presentation working set

Split Channels does not add Registered or Selected documents. When exactly one
supported RGB/RGBA or Bayer source is Selected, PixelScope derives a transient
presentation working set (`R/G/B` or `R/Gr/Gb/B`). Multi View presents those
subchannels with an explicit Primary; Single View presents one subchannel and uses
local number/header/Left/Right navigation across the same transient set. Primary
and active subchannel state survive Single/Multi presentation changes. Files still
contains and selects only the original source, while Statistics, Histogram, Line
Profile, Difference authority, source loading, and residency remain bound to the
native Current Comparison Page source. Pending/loading sources keep channel
placeholders so an unsplit stale frame is never presented while Split is active.

## P4-A temporary curation boundary

P4-A adds curation state without inserting a new source/analysis ownership layer.
The product flow is:

```text
Registered
    ↓
Selected
    ↓
Current Comparison Page
    ↓
direct temporary Pick Set
    ↓ Keep Selection
new Selected subset
```

`core.review_selection.ReviewSelectionState` is a Qt-free workflow model containing
only:

- `baseline_selected_ids`: ordered source-document IDs captured on the first direct
  checked Pick for the current logical Selected set;
- `picked_ids`: an unordered membership set of native source-document IDs;
- `active`: internal captured-baseline state, not a user-facing mode.

It does not hold `ImageDocument` objects, native/preview arrays, resident/cache
objects, workers, RAW profile copies, Current Comparison Page copies, or derived
Split/Difference documents. `kept_selected_ids()` filters baseline order by picked
membership so application order never depends on pick order.

`ui.review_selection.ReviewSelectionController` owns direct temporary-curation
orchestration. Production composition adds `Selected N / Clear Selection / Keep
Selection` after Display Gain in the presentation row; there is no Review Select
entry control and no user-facing Cancel action. `Selected N` is the temporary Pick
Set count rather than Files logical Selected count.

`TileHeader` owns the explicit stable **Pick** affordance on eligible native-source
Multi View tiles and emits ID-free UI intent. The first checked Pick captures the
baseline; checked membership keeps the text `Pick`, uses the depressed button state,
and sets the viewer `reviewPicked` property so `tile_style()` applies a bright-yellow
tile-wide border. Active and Primary are not reused as Pick state. The controller
resolves each presented tile back to a native source ID that must still exist in
`MainWindow.documents` and the captured/current Selected authority. Split and
Difference derived tiles remain non-pickable. A presented Difference uses the same
fixed header-role width but shows a neutral `QLabel` **Derived** badge with no focus,
check state, or Pick signal, so viewer reuse cannot accidentally expose source-only
curation intent on a derived document.

Pick/Unpick/Clear Selection only mutate the temporary ID set and tile/control state.
They do not call `_ensure_loaded()`, touch source LRU/protection, create
preload/foreground promotion, generate gained previews, change source generation,
issue numerical analysis, calculate/reconcile Difference, or invalidate Difference
cache. Off-page picked sources may therefore be nonresident and unprotected.
`Analysis Working Set` remains Current Comparison Page and explicit Difference-pair
ownership remains feature-local.

**Keep Selection** is the only curation operation that mutates Selected. Production
composition installs `ui.difference_curation_lifecycle.DifferenceCurationLifecycle`
after `ReviewSelectionController` to apply the owner-final Difference lifecycle at
that commit boundary without moving Difference numerical/cache ownership out of the
existing panel/MainWindow paths.

When Keep succeeds, any active Difference is closed unconditionally before Selected
mutates. The adapter first delegates visible-result teardown to the existing PR #32
path, then clears active Difference document/provenance bindings and stale reusable
viewer references, applies the ordered kept IDs through the inherited
`_select_document_ids()` lifecycle, and leaves toolbar `Diff` unchecked and disabled.
The decision does not inspect whether old A/B survived or where they would appear in
the resulting Current Comparison Page.

Keep is a presentation/binding reset, not a cache invalidation. It never purges the
generation-aware Difference Map Cache, changes source generations, or adds
curation-owned source residency/preload authority. Current Comparison Page
derivation, stale-slot clearing, source loading/residency, Files selection,
first-result Active state, and analysis rebinding remain ordinary selection behavior.
Zero picks prevent the Selected mutation.

The same lifecycle adapter makes explicit Difference calculation the only path that
may establish a new active Difference result. During passive selection/page renders,
it suppresses MainWindow's legacy cached-display promotion and implicit calculation
hooks while still allowing DifferencePanel inputs/metrics to rebind. The
DifferencePanel remains the cache/numerical owner: explicit **Calculate** performs
normal pair validation and generation-aware cache lookup, reuses a hit or runs the
existing asynchronous calculation on a miss, and `result_ready` then establishes
the active Difference document/provenance.

Toolbar `Diff` enablement is derived from that explicit active binding, not from
mere cache availability. Once a result is established, the toolbar is
visibility-only: uncheck hides the same active result, recheck shows the same result,
and neither operation infers another A/B pair or starts numerical work.

External selection-oriented mutation is the invalidation boundary. Programmatic
`_select_document_ids()` / selected-document removal adapters and the
`DocumentListWidget` pre/post selection/removal signals ensure a captured baseline
is cleared before or with a different logical Selected membership change while
preserving MainWindow's existing mutation authority. The safe ordering is:

```text
invalidate captured curation baseline/Pick Set
    ↓
existing MainWindow Selected mutation
    ↓
curation UI resync
```

Registration-only folder input does not invalidate captured curation state because
it does not mutate Selected. Temporary curation state is not persisted; Settings
schema remains v5 at the P4-A boundary.

## P4-B Comparison Set persistence boundary

P4-B adds an external durable artifact without introducing a second runtime ownership
model. `core.comparison_set.ComparisonSet` is Qt-free and runtime-document-ID-free;
`io.comparison_set_repository.ComparisonSetRepository` owns schema validation and
atomic JSON persistence; `ui.comparison_set.ComparisonSetController` bridges the
artifact to existing MainWindow registration/selection/layout/Active/Primary paths.

The artifact contract is:

```text
.pixelscope JSON v1
    ↓ validate kind/schema/field types/path identities/RAW metadata
ordered absolute native-source paths
    ↓ normal registration path
logical Selected
    ↓ saved Active + Selected ordering
Current Comparison Page        # derived, never serialized
    ↓ applicable saved Primary + layout
Presented
    ↓ existing foreground/residency lifecycle
Resident when required
```

`schema_version = 1` and `kind = "pixelscope-comparison-set"`. Persistent source
identity is a normalized **absolute local path**. The repository rejects blank or
relative source/Active/Primary identities before normalization; v1 performs no
relocation/fuzzy resolution. This is deterministic but machine/path-layout dependent
and means a shared artifact can reveal local filesystem paths.

Durable state is intentionally narrow: ordered logical Selected native-source
references, optional selected Active, optional applicable page-local Primary, stable
layout mode, and minimum resolved RAW profile metadata needed to reconstruct a RAW
source. Runtime `document_id`, Current Comparison Page/page offset, and P4-A Pick
state are not durable identity.

Save is metadata-only with respect to runtime resources. It serializes logical
Selected rather than temporary Picks, does not call `_ensure_loaded()` for off-page
members, does not force unresolved RAW resolution, does not alter Picks, and does not
acquire source residency/protection/LRU ownership. If Keep Selection has already
changed logical Selected, the curated subset is naturally what is saved.

Open validates the entire artifact before logical workspace mutation. Loadable
sources use `_register_input(..., resolve_raw_profile=False)` so registration remains
lazy. Saved resolved RAW profile metadata is installed before foreground use;
unresolved RAW remains unresolved. The saved Active ID seeds the existing selection
lifecycle so Current Comparison Page is derived from Active + saved ordering; only
then is an applicable saved Primary restored. Unrelated Registered documents remain
registered. Partial missing paths are tolerated, zero-loadable input is a no-op, and
corrupt/wrong-kind/future-schema/semantic-invalid artifacts do not begin source
registration or foreground loading.

Comparison Set persistence owns none of native source arrays, source
residency/LRU/protection, Difference maps/cache, preload plans/workers, foreground
promotion, Display Gain state/previews, Statistics/Histogram/Line Profile/Difference
request state, worker/token/generation state, Split/Difference derived documents,
transient zoom/pan, ROI/Line state, or temporary curation. Settings schema remains
v5 at the P4-B boundary because `.pixelscope` is an external artifact rather than an
`ApplicationSettings` migration.

### P4-C/R3-B current Session UI authority

Current writes and production restore are Session v1. `core.comparison_set.Session`
owns the durable domain, while `ComparisonSetRepository` writes only
`kind = "pixelscope-session"` and retains the legacy P4-B kind as a read adapter.

At the UI boundary, `ui.comparison_set.SessionController` retains shared capture/menu
mechanics and the legacy restore implementation. `SessionControllerBase` names that
role explicitly. Production composition calls only `ui.session.install_session`, which
installs the transactional `ui.session.SessionController` as
`window.session_controller`. Production composition coverage locks that concrete type.
`RecentEntriesController` accepts the shared base so the retained P4-B
`install_comparison_set` compatibility composition remains valid.

`window.comparison_set_controller` remains a narrow P4-B compatibility facade over the
same production controller. It shares the repository and all operations but preserves
the legacy `open_from_path` selected-count return view. It is not a second persistence,
restore, menu, Recent, or runtime owner. No Session/Comparison Set field, byte format,
validation, transaction, or restore order changes at this boundary.

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
decode the source.

A folder-registered unresolved RAW does not prompt/decode merely because it belongs
to Selected or the temporary Pick Set. Off-page Selected/Picked RAW stays pending
and unprotected. When it enters Current Comparison Page, `_ensure_loaded()` becomes
the foreground profile/load boundary.

Comparison Set open uses the same lazy registration boundary. When saved resolved
RAW metadata exists it is restored before foreground use; when no resolved metadata
was saved, the RAW remains unresolved and follows the inherited foreground prompt
path. Saving never resolves RAW merely to populate the artifact.

`_raw_profile_prompt_suppressed` defines the cancel retry boundary: one foreground
attempt prompts an unresolved RAW at most once. Cancel leaves the document pending
and starts no worker; passive rerenders do not immediately prompt again. Explicit
foreground intents such as page/selection navigation clear suppression for the
required current-page document(s) and may retry.

Unresolved RAW is skipped by speculative preload because `_refresh_preload_plan()`
requires an existing resolved RAW profile before constructing a RAW preload
worker. P4-A adds no Comparison Page/Pick Set preloading; preload remains exclusively
Folder Position +1.

`RawProfile` JSON migration remains the durable compatibility boundary. P4-A adds
no profile-library persistence, profile schema version, last-profile reuse,
size-only/fuzzy matching, sensor inference, or automatic Black/White estimation.

## Workspace and Folder Position

Files groups documents by parent folder in natural filename order. Folder catalog
membership and active comparison membership are independent.

`_folder_navigation_selection()` derives Folder Position only from currently
Selected documents. It accepts one to six Selected documents from distinct
folders. `FolderNavigationPlan` is the single index authority for PageUp/PageDown
and next-position prediction. Other registered folders do not participate.

`Selected > 6` makes Folder Position unavailable. PageUp/PageDown remain Folder
Position shortcuts and become a no-op with compact status; the current page is not
partially moved.

A valid PageUp/PageDown plan for `Selected <= 6` atomically replaces Selected with
the corresponding previous/next members while preserving the existing Folder
Position view/overlay and preload/promotion contract. If a curation baseline has
been captured, that Selected replacement first invalidates the temporary baseline
and Pick Set. Endpoint or invalid-member plans remain no-ops.

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
residency, Difference cache identity, and Pick identity are independent of it.

The canonical 1× preview is reused directly. Gain >1 derives viewer-local preview
from already resident native source on the shared numerical pool. Request identity,
generation, source/preview identity, requested gain, and visibility gate result
acceptance. Hidden viewers release obsolete derived buffers.

## Settings boundary

Frozen `ApplicationSettings` plus `SettingsRepository` own versioned application
preferences. Workspace layout/session QSettings remain separate.

Current schema version 6 owns the prior schema-v5 preferences—RAW JSON confirmation,
exact RAW size, default Open/Export directories, Difference Threshold/Gain,
Difference Map Cache MiB, Decoded Source Memory MiB, and preload enablement—and adds
typed machine-local Remote IQA settings:

```text
RemoteIqaSettings
    server_base_url
    storage_roots[] {
        storage_root_id
        client_path
    }
    staging_root_id
```

`storage_root_id` is portable client/server identity; `client_path` is machine-local
only. Server physical paths and credentials are not persisted in PixelScope. Session
v1 and result artifacts do not own these mappings.

P4-A/P4-B introduced no setting/schema migration; Display Gain and temporary curation
remain session-local. P5-C is the schema-v5→v6 migration owner. `Reset Settings`
resets schema-owned application preferences, including Remote IQA configuration,
while workspace-layout reset remains separate.

## Thread and request lifecycle

Foreground image loading uses a dedicated max-two pool. Preload uses a separate
max-one pool. Numerical analysis/display work uses the bounded shared numerical
pool.

Registered documents begin as lightweight pending documents. Foreground load
correctness depends on document ID, load token, generation/input identity, worker
registry, and stale-result rejection. Cancellation is advisory; result acceptance
is authoritative.

Selection/page presentation triggers `_ensure_loaded()` only for Current Comparison
Page requirements. Registration and off-page Selected/Pick membership alone do not
decode unrelated images. `_selected_load_batch_complete()` uses the Current
Comparison Page rather than an independent first-six slice.

Comparison Set Save does not schedule load/analysis work. Comparison Set Open only
re-enters normal registration/selection/page foreground authority after full artifact
validation; it does not restore workers/tokens/generations from disk.

Statistics/Histogram request identity includes generation and operation parameters
so rebinding an unchanged request does not restart work. Line Profile caches by
generation and line coordinates. Pick/Unpick/Clear Selection do not rebind those
numerical requests.

## Source residency boundary

`ResidencyManager` owns exact native `ImageDocument.source.nbytes` accounting, LRU
order, protected eviction planning, and bounded diagnostics. `MainWindow` owns
actual document mutation and Files-state updates.

P2 established protected soft-budget LRU semantics. P3-D refines the generic
selection owner for arbitrarily large logical selections: **Selected membership by
itself is not protected**. P4-A adds the same non-authority rule for Pick membership.
`MainWindow._residency_protected_document_ids()` protects Current Comparison Page
plus correctness dependencies, including foreground-load, promoted-preload,
Difference pair/result dependencies, and non-reloadable sources.
Selected/Picked-but-off-page sources may be evicted and return to normal pending /
reload state without losing Registered, Selected, or temporary Pick identity.

The budget remains soft: protected sources may exceed it, including one required
source larger than budget. Only unprotected resident sources are evicted.

Registration and Pick membership do not add residency bytes. Comparison Set Save is
also not a residency owner, and opening a large set does not protect all saved
Selected members: only the derived Current Comparison Page plus inherited correctness
dependencies own protection. Eviction clears reloadable native source and
source-local caches, returns the document to pending, and preserves its catalog
identity. Preview arrays, Qt textures, Display Gain buffers, Difference maps,
split-channel derivatives, temporary curation ID sets, Comparison Set metadata,
worker temporaries, and process RSS are outside decoded-source accounting.

## Preload and promotion boundary

Preload remains tied to the predicted `+1` Folder Position of a valid one-to-six
Selected Folder Position set:

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
registration or Pick membership alone does not create new speculative work;
unresolved RAW without a profile is not preloaded. Comparison Page navigation
starts no new speculative page preload system; sources needed for a newly foreground
page use normal foreground requirements. Comparison Set Save/Open introduces no
Selected-wide or Comparison-Page-ahead preload system.

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
- Difference cache ownership remains independent from source residency and from
  derived presentation visibility.

Difference panel inputs default to the Current Comparison Page, while the panel's
explicit Image 1/Image 2 pair remains feature-owned authority. Temporary Pick Set
is not a Difference input authority and Pick/Unpick/Clear Selection does not
calculate, reconcile, or invalidate Difference. Difference never consumes general
Display Gain, RAW Black/White metadata, `DisplayTransform`, or preview pixels.
Folder-only registration does not invalidate Difference cache or presentation
because it does not change Selected/current-page lifecycle.

The DifferencePanel remains the numerical/cache authority. An explicit Calculate
validates its current A/B pair, constructs the generation-aware cache key, reuses a
cached map on hit or dispatches the existing asynchronous numerical path on miss,
and emits the successful result through the existing MainWindow presentation path.
For a six-source page, an explicit-Calculate cache hit and a fresh asynchronous
result share the same Diff-only Single View presentation and workspace-restore
contract.

Difference is a derived presentation rather than a Registered/Selected/Pick identity.
`DifferenceCurationLifecycle` defines the P4-A integration boundary: Keep always
closes any active Difference before Selected changes, clears active
`_difference_document` / `_difference_source_ids` binding, and preserves the
Difference Map Cache and source generations. Passive rerenders cannot promote a
cached map or implicitly calculate Difference. After a successful explicit
Calculate, toolbar `Diff` is enabled because an active result is bound and then
acts only as hide/show visibility for that exact result. It never guesses a new A/B
pair from Current Comparison Page state.

No curation-specific Difference numerical algorithm, cache, source generation, or
residency owner is introduced. Comparison Set persistence does not serialize or
rehydrate Difference inputs, maps, cache entries, or presentation state.

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

## Historical P5-A schema-v1 published-result boundary

The following path remains supported only as explicit historical/read-only schema-v1
compatibility:

```text
manifest.json publication marker
    → iqa_reader schema-v1 identity/publication/path/NPZ validation
    → immutable Result / Scene / Source / Attribute / Comparison domain
    → lazy compact Scene load
        → iqa_math historical W/S1/S2/count/valid recomposition/comparison
        → iqa_geometry continuous source ↔ analysis mapping
```

Its Tier-1/Tier-2 vocabulary and A/B-specific comparison behavior are not the current
schema-v2 architecture and are not silently changed by P5-A2/P5-C.

## Current schema-v2 result architecture

The Qt-free result path under `src/pixelscope/remote/` is:

```text
manifest.json
    → iqa_result_reader.load_result() canonical version dispatch
        ├─ schema_version 1 → iqa_reader historical read-only Result
        └─ schema_version 2 → iqa_v2_reader.load_result_v2()
                                 ↓
                         COMPLETE or PARTIAL manifest
                                 ↓
                         manifest structure + summary.npz
                                 ↓
                              ResultV2
                       / PartialResultV2
                                 ↓ explicit Scene demand
                         load_grid_scene(scene_id)
                                 ↓
                         bounded Scene grid NPZ
                                 ↓
                         iqa_v2_math local
                         target/reference comparison
```

Schema-v2 ordinary open is summary-first: filesystem I/O is limited to
`manifest.json` and `summary.npz`. Deferred Scene-grid/detail references receive path
syntax validation; `load_grid_scene()` owns resolved containment, existence,
archive/member/dtype/shape materialization, and grid numerical consistency. Optional
detail references remain opaque until a later typed P5-D consumer contract.

Identity remains explicit:

- `variant_id` = ordered comparison/Reference slot;
- `source_id` = concrete source identity, reusable only with identical immutable
  path/hash/dimension metadata;
- `scene_id` = Scene identity;
- `measurement_context_id` = deterministic Scene measurement-context fingerprint.

Every published successful Scene—COMPLETE or PARTIAL—binds every declared variant
exactly once and obeys the same exact cross-variant SceneGeometry/GridGeometry and
numerical invariants. A failed/cancelled requested Scene is represented by the
PARTIAL outcome list and is absent from published `scenes[]`; PixelScope never
publishes an incomplete successful Scene.

Server-authored W/S1/S2/count/valid remain numerical authority. Scene absolute mean
is `ΣS1/ΣW`; pooled/equal-Scene Dataset summaries are distinct projections. Local
comparison owns pair-valid support, both power modes, signed target-minus-reference,
and centralized quality orientation.

### Executable PARTIAL extension

P5-C keeps `schema_version = 2` and adds ordered `scene_outcomes[]` for
`publication_state = "partial"`:

- one outcome for every requested Scene in request order;
- status `succeeded`, `failed`, or `cancelled`;
- bounded error diagnostics required for failed/cancelled outcomes;
- at least one success and one failed/cancelled outcome;
- `scenes[]` equals the ordered successful outcomes only;
- zero-success terminal jobs publish no PARTIAL result;
- all-success jobs publish COMPLETE.

The existing schema-v2 reader/math remains the only numerical authority.

## P5-B Results workspace boundary

P5-B / PR #38 is merged and owns the canonical local IQA Results path.

```text
Open IQA Result
    ↓ canonical versioned loader
summary-first ResultV2 / PartialResultV2
    ↓
Absolute Dataset/Scene presentation
    ↓ optional Reference selection
background one-Scene-at-a-time grid preparation
    ↓
canonical relative scalar results
    ↓
Dataset Overview / Scene Trend / source metadata cards
```

P5-B retains only derived scalar Reference-preparation results rather than the raw
grid corpus. Passive browsing does not mutate Files, Selected, Primary, native
analysis, Difference, source residency/preload, Session, or Picks. Scene cards are
metadata-only; native source Inspect remains P5-D.

## P5-C storage and submission architecture

### Portable shared-storage identity

Machine-local root configuration belongs to schema-v6 `ApplicationSettings`, while
portable request/result identity is always:

```text
storage_root_id + relative_path
```

Existing sources under configured roots resolve using the most-specific matching
root. Sources outside configured roots may be staged using SHA-256 content identity.
Machine-local Windows/UNC roots are never request/result identity and server physical
paths are never persisted by PixelScope.

Staging uses independently named same-directory temporary files, resolves containment
before child mutation, rejects source/result symlink or junction escapes outside the
configured logical root, and atomically publishes/reuses the final file only after
SHA-256 verification. Concurrent publishers, including the Windows `os.replace()`
loser case, converge on the verified final identity rather than sharing one temp name.

### Deterministic request builder

Initial P5-C submit cardinality is exactly two variants A/B.

- Current Pair consumes the A/B pair of **underlying Current Comparison Page
  documents**, not Primary/Active/presented tile order.
- Folder Pair is an independent Remote-IQA batch-preparation path over immediate
  eligible files; it does not register/select/decode the whole batch locally.
- PNG/JPG/JPEG/BMP only; RAW is rejected.
- Folder pairing is deterministic NFC lexical sort + pair-by-index with equal count
  and equal pair dimensions.
- Scene IDs are deterministic `scene_000000...`.
- request source records contain logical root, relative path, SHA-256, width, height.

The request builder is Qt-free and performs preflight/hash/staging before creating an
`IqaJobRequest`. Viewer transforms and local Difference state do not participate.

### HTTP client and Jobs ownership

`HttpIqaJobClient` is synchronous/Qt-free and is always called from feature-local
workers. It owns only REST protocol validation:

```text
POST /v1/iqa/jobs
GET  /v1/iqa/jobs/{job_id}
GET  /v1/iqa/jobs/{job_id}/result
POST /v1/iqa/jobs/{job_id}/cancel
```

The UI/controller owns worker scheduling, local tracked-job records, polling cadence,
and stale callback rejection. The remote durable job remains server-owned.

Create POST is deliberately never auto-retried. One local preparation/create owner
prevents duplicate in-process submissions; ambiguous create outcomes block further
submission in that process rather than inviting a blind retry. Cooperative
cancellation reaches preflight/hash/staging and checks again immediately before the
create POST. Terminal succeeded/partial result-reference acquisition is an idempotent
GET with bounded 1s/2s/4s/8s recovery after the initial attempt. Completion never
auto-opens Results; explicit `Open Result` resolves the logical result reference
through current settings and delegates to the P5-B controller.

Client errors are classified as configuration, connection, timeout, HTTP, protocol,
or storage-resolution failures. Result-path resolution is a separate machine-local
storage operation after the server has returned portable result identity. Live
storage-root changes use revision + pending re-resolution so stale old-mapping
callbacks cannot overwrite the newest mapping.

### Folder Pair preview lifecycle

Folder Pair validation has feature-local latest-request ownership. Editing Folder A/B
while an older validation is running invalidates the old preview; stale callbacks do
not publish results, and completion of the latest in-flight validation restores the
`Validate / Preview` action. A stale older worker cannot re-enable controls over a
newer validation. This preview lifecycle does not acquire Files/Selected/current-page,
source-residency, or preload authority.

### Single IQA workspace composition

Production composition installs one IQA dock:

```text
RemoteIqaWorkspace
├─ Setup
│   ├─ Current Pair
│   └─ Folder Pair
├─ Jobs
│   ├─ Cancel
│   └─ Open Result
└─ Results
    └─ existing P5-B IqaWorkspaceWidget/controller
```

This composition does not create a second result parser, source catalog, or analysis
working set.

### Debug harness separation

`PIXELSCOPE_REMOTE_IQA_DEBUG` gates contract-validation tools that are not production
server architecture:

- Request Inspector runs the production request preparation path and stops before
  POST;
- Replay JSON injects bounded logical terminal-job/result records without HTTP;
- deterministic fake result generation reuses the canonical v2 fixture writer and
  validates through the canonical loader;
- the localhost `ThreadingHTTPServer` uses real socket HTTP to exercise the production
  client and fault/retry paths but performs no IQA computation.

A future real GPU server plugs into the same REST/logical-storage contract rather than
requiring a separate PixelScope transport architecture.

## P5-C lifetime boundaries — complete / PR #42

PR #42 now implements the lifecycle/resource hardening that was previously tracked as
merge-blocking:

- concurrent staging and resolved containment before filesystem mutation;
- cooperative preflight/hash/staging cancellation plus a final pre-create checkpoint;
- one in-flight local create owner and explicit ambiguous-create/no-blind-retry policy;
- settings mapping revision + pending re-resolution so newest result-path mapping wins;
- latest Folder Pair preview ownership so input edits cannot permanently disable
  validation;
- production-composition regressions for Current Pair A/B page-order authority and
  Folder Pair isolation from Files/Selected/current page/residency/preload.

These guards remain feature-local and do not redesign P2 source residency/preload or
P5-A2/P5-B numerical/result ownership. P5-C merged as PR #42.

## P5-D/P5-E/P5-F composed lifetime boundaries — implemented

P5-D is the only explicit verified native Inspect/Return bridge. P5-E wraps the same
canonical P5-B open path with bounded historical locator/identity/Provenance state and
does not acquire Files/Selected authority. P5-F preserves those boundaries while
separating three resource domains:

- local Statistics/Difference analysis uses the established analysis pool;
- P5-B Result/Reference, P5-D verification/spatial, and P5-E historical resolution use
  one application-owned fixed max-two Remote IQA file/result pool;
- P5-C job operations retain their separate fixed max-two pool.

Production HTTP operations use lazy per-worker physical client checkout. Queued work
cleared before execution owns no physical client; executing leases drain during
shutdown. No raw-grid cache, speculative preload, adaptive polling, generalized retry,
or concurrency-policy change was introduced. R may make injection/composition explicit
but must not change these lifetime policies.

## R1 application composition seam

`src/pixelscope/app/application.py` remains the production composition root. Its local
presentation/workflow installation stays in `_compose_main_window_presentation`, while
the Remote IQA feature chain is isolated in `_compose_remote_iqa` with its existing
application-owned result pool and transport pool passed explicitly.

The Remote IQA installation order is a behavior contract, not incidental formatting:

```text
P5-C submission/jobs + transport lifetime
    ↓
result mapping/retry/setup/debug hardening
    ↓
P5-D explicit native Inspect + settings observer
    ↓
P5-E historical open + Provenance observer
```

This seam does not replace `MethodType` wrappers, reconnect signals, change any
controller method, or alter settings/open/shutdown order.

## R2 explicit Remote IQA result-pool ownership

Production creates the fixed max-two Remote IQA result/file pool before `MainWindow`.
`MainWindow` passes that pool into the P5-B Result controller constructor, and the R1
composition seam forwards the same dependency into the P5-D Inspect and P5-E history
installers. Each controller therefore has its final pool from construction; application
composition no longer mutates private `_pool` state after installation.

The controllers retain a read-only `pool` ownership view for composition and contract
tests. Direct non-production construction may still omit the dependency and use the
established analysis-pool fallback. Idempotent P5-D/P5-E installation returns the
existing controller only when an explicitly supplied pool has the same identity; a
conflicting pool fails instead of silently splitting result-side ownership.

Production initializes the already-existing analysis pool before the Remote IQA pool,
then constructs `MainWindow`. This retains the pre-R2 `aboutToQuit` clear/wait order
(local background pools, then Remote IQA) while still injecting the final P5-B pool at
construction. R2 does not change pool sizes, the separate P5-C job-operation pool,
worker start/cancel behavior, stale-result guards, HTTP checkout, or installer/wrapper
order.

## R3-A pre-P5 Remote scaffold boundary

The initial-release `evaluation_client.py`, `mock_client.py`, and `schemas.py` formed an
isolated `/v1/jobs` sketch. They were never exported by `pixelscope.remote`, imported by
production, or connected to the canonical P5 result/job architecture. R3-A removes that
dead implementation and its self-only test so `remote` exposes one supported IQA stack.

This removal does not affect P5-A historical schema-v1 Result compatibility, whose
authority remains `iqa_domain.py`/`iqa_reader.py` plus
`tests/unit/test_remote_iqa_v1.py`. It also does not change the P5-C `/v1/iqa/jobs`
transport or P5-F compatibility probe. The original endpoint sketch remains clearly
marked historical/unsupported in `server/api_contract.md`; current server/transport
authority stays in `REMOTE_IQA_CONTRACT.md`.

## Runtime diagnostics and release boundaries

`RuntimeDiagnosticsSnapshot` is frozen, deterministic, bounded, sanitized, and
observation-only. The sole product surface is **Help > Copy Diagnostics**; no live
monitor/timer is introduced.

Canonical application icon assets are package resources and source-run Windows
identity is established before QApplication creation. PyInstaller executable icon
binding, shortcuts, installer identity, signing, updater, and final distribution
remain P7. Remote REST/client boundaries remain independent of widgets. All APIs
target CPython 3.10.
