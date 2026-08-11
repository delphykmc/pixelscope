# Engineering decisions

## Platform and implementation constraints

- CPython 3.10 x64 is fixed.
- PySide6 6.4.2 remains the Qt binding; pyqtgraph 0.13.3 provides image and plot
  primitives.
- PyInstaller is fixed at exactly 5.7 `onedir`; 6.x is prohibited. Inno Setup is
  the planned installer layer.
- NumPy/OpenCV implementations come first. Native C/C++ optimization requires
  profiling evidence and remains behind numerical/image interfaces.
- Expensive I/O and numerical work runs in bounded workers; widgets do not own
  decode, Difference, or full-frame display algorithms.
- Source pixels retain native dtype/channel meaning. Overflow-prone arithmetic
  promotes operands before subtraction/multiplication.
- Presentation transforms do not redefine source or analysis domains.

## Current product decisions

- **Registered**, **Selected**, **Current Comparison Page**, **Presented**, and
  **Resident** are distinct runtime states.
  - Registered means Files-catalog membership.
  - Selected is the ordered logical comparison set and may exceed six.
  - Current Comparison Page is a derived maximum-six working subset of Selected.
  - Presented is the viewer representation of that page.
  - Resident is the P2 decoded-native-source memory state when required.
- `Analysis Working Set = Current Comparison Page`.
- Viewer slots are local `1..6` within Current Comparison Page; global Selected
  ordinal and viewer slot are separate concepts.
- Viewer capacity does not limit workspace registration or logical Selected size.
- Multi View has one fixed layout policy. `_fixed_geometry()` is the sole geometry
  authority; P1-F removed arrangement compatibility state. Large selections retain
  six-slot Grid 3x2 page geometry, including short final pages with empty slots.
- Ordered selection is the logical comparison model; Current Comparison Page is
  derived from that ordering plus page offset and does not duplicate ownership.
- Left/Right remains previous/next Selected Image. Ctrl+Left/Ctrl+Right moves one
  non-wrapping Comparison Page. PageUp/PageDown remains Folder Position only.
- Primary-image analysis reference priority is primary, active, then first
  displayed; for large selections primary/focus ordering is page-local and cannot
  change Selected ordering/page membership.
- Difference caches one absolute map per order-independent document-generation
  pair and derives views/metrics from it. The map explicitly records native or
  normalized domain metadata. Explicit Difference pair authority remains
  feature-owned.
- RAW storage format, sample container, effective bit depth, endian, alignment,
  Black Level, and White Level remain separate concepts.
- **Open Images...** is selection-oriented and is the one top-level file-open
  command for PNG/BMP/JPEG/RAW.
- **Open Folder...** is registration-oriented and uses the native single-folder
  picker. Multiple-folder registration remains available through folder D&D / the
  registration API without changing Selected, Current Comparison Page, or
  presentation.
- RAW-specific profile resolution is conditional logic inside the common input
  pipeline rather than a second user-facing open mode.
- Selected membership alone is not a generic source-residency protection owner for
  large selections; Current Comparison Page plus correctness dependencies own
  protection.
- Remote evaluation uses a versioned REST job API boundary.

## Accepted P2 program decisions

P2 — Runtime Foundation, Settings & Performance completed sequentially through
P2-F as PR #13–#20. The merged P2 baseline establishes these durable boundaries.

### Settings and identity

- QSettings is a persistence adapter, not the application settings domain model.
- Frozen `ApplicationSettings` is the typed persisted model;
  `SettingsRepository` owns defaults, validation, migration, save/reset, corrupt
  recovery, and future-schema compatibility; `QSettingsAdapter` owns raw keys.
- Settings schema version 5 owns RAW confirmation/exact-size policy, optional
  Open/Export folders, Difference Threshold/Gain defaults, Difference Map Cache
  MiB, Decoded Source Memory MiB, and preload enablement.
- Schema v4 migrates to v5 by preserving values and adding enabled preload. Older
  schemas and the legacy RAW-confirmation key remain supported. A future schema
  is never guessed or destructively rewritten.
- Settings UI uses General, Files, and Performance categories. Workspace geometry,
  splitter/dock state, current layout, Plots state, and last-directory state remain
  separate workspace persistence.
- Difference Map Cache defaults to 128 MiB. Decoded Source Memory defaults to
  256 MiB. When physical RAM is known, the Settings UI constrains the combined
  configured budgets to at most 50% of RAM; this is a configuration envelope,
  not a process-memory guarantee.
- Performance budgets and preload enablement are startup snapshots; edits persist
  for the next launch and do not mutate existing runtime owners.
- `Reset Settings` resets schema-owned application preferences only; workspace
  reset remains separate.
- Canonical source-run identity uses the package SVG/PNG/ICO triplet and stable
  Windows AppUserModelID `PixelScope.PixelScope`. Installer/signing/release-shell
  identity remains P7.

### Source residency

- Decoded Source Memory accounts exact native `ImageDocument.source.nbytes` only.
- `ResidencyManager` owns byte accounting, protected soft-budget LRU order,
  eviction planning, and bounded diagnostics; `MainWindow` owns document mutation.
- At the P2 baseline, visible, selected, active/analysis, Difference-pair, and
  foreground-authority sources were protected while required. P3-D later refines
  the generic Selected owner for arbitrarily large logical selections; see the
  accepted P3-D decisions below.
- One required source may exceed the entire soft budget while protected.
- Preview arrays, Qt textures, Difference maps, derived presentation buffers,
  transient worker arrays, Python/Qt overhead, and process RSS are not source
  residency.
- Source eviction and Difference-cache ownership are independent. Evicting source
  does not invalidate a valid generation-keyed Difference map.
- Registration alone does not imply decoded-source residency.

### Navigation, preload, and promotion

- PageUp/PageDown owns previous/next Folder Position; Up/Down remains Files-tree
  navigation and Left/Right remains previous/next selected image.
- Folder Position is derived only from the currently selected one-to-six documents
  from distinct folders. Other registered folders do not participate.
- One pure folder-navigation planner is authoritative for actual movement and
  preload prediction.
- Preload policy is `+1` only, exactly one Folder Position deep, enabled by
  default, and concurrency one in a dedicated pool. Normal image-load pool max is
  two.
- Completed speculative preload enters ordinary source residency with no
  speculative protection or separate memory budget.
- Cancellation is advisory; token/generation/request identity is the authority
  for stale-result rejection.
- P2-E promotion applies only to an exact matching physically RUNNING preload.
  Promotion is a logical authority transition, not thread migration; the worker
  stays in the preload pool.
- Promotion requires exact document/generation/path/RAW-profile/exact-size/token
  identity, running/not-cancelled state, non-resident source, and no duplicate
  normal worker.
- Promoted success/failure delegates exactly once to normal foreground behavior.
  Promotion does not promote an entire group or change pool limits.

### Diagnostics and P2 closure

- Runtime diagnostics are deterministic, bounded, sanitized, and observation-only.
- The sole user surface is **Help > Copy Diagnostics**. There is no live monitor,
  timer, modal diagnostics viewer, refresh loop, or diagnostics file export.
- Diagnostics may not touch LRUs, load/preload, calculate Difference, mutate
  selection, or scan files.
- Recent failures are bounded and sanitized for paths, credential-like values,
  bearer data, URL detail, traceback context, and excess length.
- P2-F merge gates are deterministic correctness/resource/lifecycle properties.
  Wall-clock timing is observational only.
- Windows CI remains deferred until Qt/offscreen reliability and runner cost are
  demonstrated; owner/local Windows validation is the current closure authority.

## Accepted P3-A Difference decisions

P3-A merged as PR #22 at
`769588bf869847da844cfc0b77c008023d8b048b`.

- Supported Difference families are Gray ↔ Gray, RGB/RGBA ↔ RGB/RGBA, and
  same-CFA Bayer ↔ Bayer. RGB/RGBA ignores alpha.
- Cross-family, size-mismatch, CFA-mismatch, and unsupported layouts are rejected.
  No implicit RGB→Gray/luma conversion is permitted.
- Family compatibility is decided before effective bit depth.
- Equal effective bit depth uses native code-domain Difference and compact integer
  storage with data range `(1 << bit_depth) - 1`.
- Mixed effective depth independently normalizes each source by its own effective
  full scale, stores canonical float32 absolute maps in `[0,1]`, and uses `%FS`
  threshold semantics.
- Mixed-bit normalized work is bounded/chunked and avoids full-size float64
  normalized arrays. P95/P99 use a deterministic 65,536-level histogram.
- Difference cache entries explicitly store domain/data-range/family/layout/Bayer
  metadata while retaining order-independent generation-pair identity.
- RAW Black/White metadata, display transforms, viewer gain, preview pixels,
  demosaic output, and other presentation state never participate in P3-A domain
  selection or normalization.
- Normalized threshold is session-local; schema v5 is unchanged.

## Accepted P3-B RAW/display decisions

P3-B merged as PR #24 at
`1817490a08c61da9087efe9c3c6afd8bd85838f0` and introduced RAW viewer gain without
redefining native analysis.

### Native RAW authority

- `ImageDocument.source` remains the decoded native authority.
- Pixel inspection, Statistics, Histogram, Line Profile, Split Channels,
  Difference, and source residency consume native source rather than gained
  preview pixels.
- Gain changes do not reload/decode source, bump generation, alter source
  residency, or change Difference-cache identity.
- `white_level` remains persisted profile metadata and is not the 1× or gained
  display maximum.

### Generic display-gain core

The common core model is:

```text
display = anchor + gain * (source - anchor)
```

- `core.display_transform` owns the generic anchor-based numerical primitive.
- RAW metadata interpretation remains outside the generic primitive.
- The core supports scalar anchors including `anchor=0`.
- Gain and display-range normalization are fused into float32 scale/offset where
  possible to reduce full-frame memory-bandwidth passes.
- Full-frame display-gain arithmetic does not promote to float64.
- Generic affine application can target an array/channel view.
- Clipping is deferred to final display conversion.
- Source arrays are not modified.

### RAW anchor policy

- RAW 1× display maps effective native full scale
  `0..((1 << bit_depth) - 1)` to the preview range.
- Black is not subtracted at 1× and White is not promoted to display maximum.
- RAW Gray scalar `black_level` is the gain anchor.
- A schema-valid GRAY profile with four Black values remains compatible and uses
  the legacy global-preview anchor `min(black_level)` while preserving the tuple.
- Bayer four-value Black uses R/Gr/Gb/B channel-specific anchors by CFA parity.
- Scalar Bayer Black applies one anchor to all channels.
- Split Bayer planes use their named channel anchor.
- Bayer processing operates on parity-plane views and never materializes a
  full-size Black Level map.

### P3-B UI/runtime policy

- session-local gain choices are 1×/2×/4×/8×/16×;
- gain is not persisted to `RawProfile`, workspace QSettings, or
  `ApplicationSettings`; schema remains v5;
- gain 1× uses canonical `ImageDocument.preview` and schedules no gained-preview
  worker;
- gain >1 derives a viewer-local preview from resident source on the shared
  numerical worker pool;
- result acceptance checks task/request/document/source/generation/gain/visibility
  identity;
- hidden viewers release gain>1 derived buffers and regenerate current gain when
  shown;
- `+` / `-` Display Gain command ownership is the image-presentation subtree,
  preserving Files-tree native expand/collapse.

## Accepted P3-C Display Gain generalization decisions

P3-C merged as PR #25 at
`7f6bef73e6712f6a14a4d401820a915196e25da2`.

- The user-facing term is **Display Gain** or **Gain**, never **Exposure**.
- One QApplication-session `DisplayGainState` serves supported ordinary and RAW
  presentations using 1×/2×/4×/8×/16×.
- Ordinary Gray/RGB use the P3-B core with `anchor=0`.
- Ordinary RGB split-channel views gain their native 2-D source plane with
  `anchor=0` while retaining colored presentation.
- RGBA applies gain only to RGB; gain>1 alpha equals canonical 1× alpha exactly.
- RGBA gain arithmetic targets the RGB source view rather than a four-channel
  float32 gain buffer.
- RAW P3-B semantics remain unchanged.
- Difference is excluded from general Display Gain.
- Gain 1× is a no-work canonical-preview reuse path; gain>1 uses resident source
  and the existing shared numerical worker pool.
- Stale results are rejected by explicit request/document/source/preview/
  generation/gain/visibility identity.
- Hidden/replaced viewers release unnecessary gain>1 derived buffers.
- Display Gain never mutates native source/generation, source residency, analysis,
  or Difference-cache identity.
- No new worker pool, resource setting, persistence, or schema migration was
  introduced.

## Accepted P3-D unified input and Current Comparison Page decisions

P3-D's authoritative product goal is **Unified Image Opening & RAW Profile
Resolution** with an explicit bounded Current Comparison Page between logical
selection and viewer presentation. The earlier reusable Profile Library/suggestion
concept is deferred.

### Runtime hierarchy

```text
Registered
    ↓
Selected                         # ordered logical set, may exceed 6
    ↓
Current Comparison Page          # derived working subset, max 6
    ↓
Presented
    ↓
Resident when required
```

- Current Comparison Page is derived from Selected ordering plus page offset; it is
  not a duplicated document collection.
- `Analysis Working Set = Current Comparison Page`.
- Viewer slot is local `1..6` within Current Comparison Page.
- A global Selected ordinal must not be exposed as a viewer slot.

### Input intent

- **Open Images...** is selection-oriented. It supports multi-file input, registers
  every supported direct file, and makes those files the ordered Selected set.
- **Open Folder...** is registration-oriented and uses the native single-directory
  picker. Multiple folders remain supported through folder D&D / the registration
  API with deterministic resolved-path deduplication; folder registration does not
  change Selected, Current Comparison Page, or presentation.
- Direct image-file D&D uses Open Images intent.
- Folder D&D uses Open Folder registration intent for one, two, six, fifteen, or
  any other practical count. Exactly two folders have no special comparison behavior.
- Mixed D&D preserves both intents: direct files become Selected; folder contents
  remain registration-only.
- Workspace registration and logical selection have no six-item limit.

### Registration ownership

- `io.path_discovery` owns supported-extension discovery.
- `ImageInput` remains path plus optional exact-sidecar identity.
- `_register_inputs()` is registration-only. Selection/page/presentation is owned
  by explicit callers such as Open Images/direct-file D&D or Folder Position.
- Folder registration must not invoke the selection/render lifecycle and therefore
  preserves current layout, active/primary state, ROI, Line Profile, Difference,
  Display Gain, zoom/pan preservation state, source residency, and Difference
  cache.
- A valid state with registered documents and zero Selected is supported. The
  central workspace prompts the user to select from Files.
- Unsupported files and standalone `.json` sidecars are ignored; empty folders do
  not fail other folder registrations.
- The obsolete exactly-two-folder `pair_folders()` abstraction is removed from the
  supported input model.

### Current Comparison Page and navigation

- `Selected <= 6` keeps `Current Comparison Page = Selected` and preserves existing
  Auto/Single/Multi, number-key, primary, analysis, Difference, Folder Position,
  residency, and preload semantics.
- `Selected > 6` is divided into derived six-image pages without changing Selected
  membership/order.
- `current_comparison_documents()` is the semantic page authority for Multi View,
  Single View page context, Statistics, Histogram, Line Profile,
  selection-derived Difference inputs, ROI/Line normalization, current-page load
  completion, residency protection, and local slot mapping.
- Multi View retains six-slot Grid 3x2 geometry for large selections, including a
  short final page with unused slots cleared.
- Single View presents one active page-local image while retaining full current-page
  analysis/load context.
- Number keys `1..6` always mean current-page local slots.
- Left/Right remains fine previous/next Selected Image navigation across the full
  ordered set and automatically changes page at a boundary.
- Ctrl+Left/Ctrl+Right is separate non-wrapping Previous/Next Comparison Page
  navigation. Its application-wide `QShortcut` is enabled only while movement in
  that direction is available. The presentation-control row keeps Page status and
  range visible even for one page, with endpoint arrows disabled rather than hidden.
- Coarse page movement preserves active local slot where possible and clamps it on
  a short final page.
- Primary/focus ordering is page-local and cannot change Selected ordering or page
  membership.
- PageUp/PageDown is never Comparison Page navigation.
- Split Channels is a transient presentation working set derived from one Selected
  source; it does not create Registered/Selected subchannel documents or move native
  analysis/residency authority away from Current Comparison Page.
- Six-source Difference cache hits and fresh asynchronous results have identical
  Diff-only Single View presentation and workspace-restore semantics.

### Folder Position

- Folder Position derives only from one-to-six currently Selected documents from
  distinct folders. Other registered folders do not participate.
- `Selected > 6` makes Folder Position unavailable; PageUp/PageDown is a no-op with
  status rather than partially moving the current page.
- For `Selected <= 6`, existing P1/P2 atomic movement, endpoint, preload, and
  promotion semantics remain authoritative.

### RAW profile-resolution order and lazy folder boundary

Direct RAW image input preserves this sequence:

1. Exact same-basename sidecar, if present, is parsed/validated.
2. Existing confirmation suppression and exact/minimum-size policy remain in force.
3. No sidecar opens editable RAW Profile entry.
4. Invalid sidecar warns and opens editable fallback.
5. Cancel prevents erroneous direct-open RAW registration.
6. Multiple direct RAW inputs resolve independently.

Folder registration deliberately does not prompt for unresolved RAW. It registers
the pending RAW path and any deterministic sidecar path.

Selected-but-off-page unresolved RAW is logical selection only: it must not prompt,
decode, or require residency merely because it is Selected. When it enters a
foreground Current Comparison Page and source is required, `_ensure_loaded()`
invokes the existing profile resolver before creating the RAW load worker.

One foreground attempt prompts an unresolved RAW at most once. Cancel leaves it
registered/pending, starts no worker, and passive rerenders do not immediately
re-prompt. A later explicit foreground intent may retry. Unresolved RAW is excluded
from speculative preload until a profile has been resolved. No file-size-only or
fuzzy profile inference is introduced.

Existing same-path reload, RawProfile identity, packed/unpacked validation, Bayer
pattern, Black/White metadata, legacy JSON migration, exact-size semantics, and
P2 worker/residency identity remain unchanged.

### Residency and preload refinement

- P2 exact native `source.nbytes` accounting and protected soft-budget LRU remain
  authoritative.
- P3-D supersedes the generic P2-era large-Selected interpretation: **Selected
  membership alone is not a source-protection owner**.
- Current Comparison Page plus correctness dependencies such as foreground loads,
  promoted preload, Difference dependencies, and non-reloadable sources are
  protected.
- Selected-but-off-page sources may be evicted and normally reloaded when their
  page is revisited without losing Registered/Selected identity.
- P2 preload remains exactly +1 Folder Position with one preload worker. P3-D adds
  no Comparison Page preload system.

### Multi-folder registration UI

- **Open Folder...** uses the native single-directory picker.
- Multiple folders are registered through folder D&D or the registration API, with
  deterministic resolved-path deduplication where several paths are supplied.
- There is no custom multi-directory picker, Windows COM dependency, or six-folder
  UI limit.

### Profile UI and persistence boundary

- User-facing buttons are **Load Profile...** and **Save Profile...**; JSON remains
  the compatible profile format.
- Settings schema remains v5.
- RawProfile gains no artificial version field solely for this slice.
- No global profile database/library, Settings-owned profile collection,
  favorites, rename/duplicate/delete manager, search UI, size-only/fuzzy profile
  selection, sensor inference, Bayer-pattern inference, or Black/White estimation
  is introduced.

### Scope preservation

P3-D does not redesign Difference, Display Gain, P2 preload worker limits, session
persistence, Recent Files/Folders, demosaic, white balance, CCM, tone mapping, or
packaging. The residency change above is a bounded ownership refinement required
so unlimited logical Selected membership does not defeat the existing P2 soft
budget; it does not replace ResidencyManager or its accounting model. Native source
remains authoritative and all P3-A/B/C analysis/display boundaries remain intact.

## P4-A Review Selection & Curation decisions — Complete

P4-A merged as PR #29 at
`3486146494076e9b513843b90ec44e504043729e`.

- There is **no explicit Review Select mode**. Eligible native source tiles in Multi
  View expose the curation **Pick** control directly; ordinary tile activation and
  Primary retain their inherited meanings.
- The first checked Pick captures the current ordered Selected IDs as the temporary
  baseline. `ReviewSelectionState.active` represents internal captured-baseline
  state, not a user-facing mode.
- `ReviewSelectionState` is the sole Pick Set model and contains only ordered
  baseline Selected IDs, picked native source IDs, and internal captured state.
- `ImageDocument` does not gain a persistent/workflow Pick field. Pick state is not
  stored in source, preview, residency, cache, worker, RAW profile, or derived
  presentation objects.
- Pick identity is the native Registered/Selected source document ID. Split Channel,
  Difference, and gained preview representations are not independent pick
  identities.
- Active, Primary, and Pick are separate states and visual affordances. The Pick
  text remains `Pick`; checked membership uses the depressed control plus a
  bright-yellow tile-wide border, with Active still independently visible.
- The presentation row exposes
  `Layout | Page | Display Gain | Selected N | Clear Selection | Keep Selection`.
  `Selected N` is the temporary Pick Set count, not Files logical Selected count.
- Pick/Unpick/**Clear Selection** are ID-set/UI operations only. They do not call
  decode or `_ensure_loaded()`, touch source LRU/protection, create preload or
  promotion, generate Display Gain previews, issue analysis requests, calculate
  Difference, bump source generation, or invalidate Difference cache.
- Off-page picked sources may be evicted/unprotected; Pick membership is not a
  source-residency owner.
- `Analysis Working Set = Current Comparison Page` remains unchanged. Temporary Pick
  Set is not Statistics/Histogram/Line Profile/ROI/Difference authority.
- **Keep Selection** is the only curation operation that mutates Selected. The
  result is `baseline_selected_ids` filtered by picked membership, preserving
  baseline order rather than pick order.
- Zero picks disable Keep Selection; there is no curation path that silently creates
  an empty Selected set.
- Non-picked images remain Registered and Keep Selection reuses the inherited
  Selected mutation/page/render/source lifecycle rather than creating a
  curation-specific lifecycle.
- There is no user-facing Cancel command. Clear Selection removes temporary picks;
  a different logical Selected-membership mutation invalidates the captured
  baseline/Pick Set before or with the ordinary mutation.
- Registration-only folder input does not invalidate captured curation state because
  it does not mutate Selected.
- Temporary curation state is not persisted. Settings schema remains v5.
- Comparison Page navigation creates no speculative preload for picked sources. P2
  preload remains Folder Position +1, one position, max-one worker.
- Difference, Display Gain, RAW Black/White/native-source semantics, source
  generation identity, and source residency accounting remain unchanged.

## P4-B Comparison Set Persistence decisions — implemented, merge pending

- P4-B persists an explicit **Comparison Set**, not a full application/session
  snapshot.
- File extension is `.pixelscope`; v1 JSON requires
  `kind = "pixelscope-comparison-set"` and `schema_version = 1`.
- Persistent source identity is a normalized **absolute local native-source path**.
  The external reader rejects non-string, blank, or relative source/Active/Primary
  paths before normalization. v1 performs no relocation or fuzzy path resolution.
- Absolute-path identity is intentionally deterministic but machine/path-layout
  dependent. A shared artifact may expose local filesystem paths; this is a
  documented privacy/portability constraint rather than hidden behavior.
- Durable state is limited to ordered logical Selected source references, optional
  selected Active, optional applicable page-local Primary, stable layout mode, and
  minimum resolved RAW profile metadata required to reconstruct a RAW source.
- Current Comparison Page/page index/page offset is **derived**, never serialized.
  Saved Active plus Selected ordering derives the page before applicable Primary is
  restored.
- Save serializes logical Selected, not the temporary P4-A Pick Set. Before Keep,
  Picks do not change saved membership; after Keep, the curated Selected subset is
  the logical set and is therefore saved.
- Save does not apply/clear Picks, call `_ensure_loaded()` for off-page members,
  force unresolved RAW profile resolution, or acquire Selected-wide
  residency/protection/LRU authority.
- Open validates the complete artifact before logical mutation. Semantically invalid
  artifacts begin no source registration or foreground loading.
- Valid Open reuses normal registration and Selected mutation authorities, retains
  unrelated Registered sources, restores loadable saved ordering, uses saved Active
  or deterministic fallback, derives Current Comparison Page, then restores
  applicable Primary/layout.
- Missing paths partially load with compact warning. Zero-loadable input is a no-op.
  Corrupt JSON, wrong kind, future schema, invalid identity/layout, or invalid
  embedded RAW profile is rejected without logical workspace mutation.
- Saved resolved RAW metadata is restored before foreground use. Unresolved RAW
  remains unresolved and follows the existing lazy foreground profile-resolution
  path; Save does not force resolution.
- Comparison Set persistence owns none of decoded source arrays, source
  residency/LRU/protection, preload/promotion, Difference maps/cache, Display Gain,
  analysis request/results, workers/tokens/generation, Split/Difference derived
  documents, transient view state, ROI/Line, or temporary Picks.
- Comparison Sets are external user artifacts and do not change Settings schema v5.
- P4-C should build **Comparison Set Entry UX / Recent Entries**, not revive the
  broader obsolete "persistent session" framing.

## Current resource policy

- Difference Map Cache remains byte-budgeted and persistence-free with default
  128 MiB.
- Decoded-source residency remains a protected soft-budget manager with default
  256 MiB.
- Current Comparison Page plus correctness dependencies are the generic P3-D
  protection set; Selected/Picked-but-off-page is not protected solely by logical
  membership.
- Normal load pool max remains two; preload pool max remains one; shared numerical
  pool max remains four.
- Display Gain derived previews are viewer-local presentation buffers and are not
  added to decoded-source residency or Difference cache ownership.
- Comparison Page navigation, Pick membership, and Comparison Set Save/Open introduce
  no Selected-wide speculative preload/cache/residency owner.

## Validation and merge state

P3 is Complete through P3-E / PR #27. P4-0 is Complete as PR #28. P4-A is Complete
as PR #29 at `3486146494076e9b513843b90ec44e504043729e`.

P4-B focused coverage includes schema/path validation, atomic round-trip,
logical-Selected-vs-Pick save semantics, later-page Active/Primary restore,
missing/zero-loadable/corrupt transaction behavior, resolved/unresolved RAW
semantics, large-set page-bounded foreground work, and save-side non-ownership of
load/residency/protection.

The repository owner reports the focused P4-B Windows validation PASS (`36 passed`).
Independent review reports no remaining runtime/schema/test blocker. PR #30 remains
merge-pending for durable-doc consistency and final review/validation closure. These
durable-doc edits do not alter runtime or tests; no unobserved full-suite/tooling
PASS is inferred here.