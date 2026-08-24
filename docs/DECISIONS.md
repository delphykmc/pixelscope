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
- Settings UI uses General, Files, and Performance categories. General owns RAW
  confirmation/exact-size policy and Difference Threshold/Gain defaults; Files owns
  default Open/Export directories; Performance owns Difference Map Cache, Decoded
  Source Memory, and preload enablement. Workspace geometry, splitter/dock state,
  current layout, Plots state, and last-directory state remain separate workspace
  persistence.
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
- Six-source Difference results established by explicit Calculate use the same
  Diff-only Single View and workspace-restore semantics whether the generation-aware
  map came from cache or fresh asynchronous calculation.

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
- Settings schema remains v5 at the P3-D boundary.
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
- **Review curation is source-only. Difference is a derived presentation and is
  never an independent Pick or logical Selected member.** Difference tiles expose
  a neutral non-interactive `Derived` role instead of an interactive Pick control.
- Active, Primary, and Pick are separate states and visual affordances. The Pick
  text remains `Pick`; checked membership uses the depressed control plus a
  bright-yellow tile-wide border, with Active still independently visible.
- The presentation row exposes
  `Layout | Page | Display Gain | Selected N | Clear Selection | Keep Selection`.
  `Selected N` is the temporary Pick Set count, not Files logical Selected count.
- Pick/Unpick/**Clear Selection** are ID-set/UI operations only. They do not call
  decode or `_ensure_loaded()`, touch source LRU/protection, create preload or
  promotion, generate Display Gain previews, issue analysis requests, calculate
  Difference, bump source generation, invalidate Difference cache, or reconcile
  an active Difference presentation.
- Off-page picked sources may be evicted/unprotected; Pick membership is not a
  source-residency owner.
- `Analysis Working Set = Current Comparison Page` remains unchanged. Temporary Pick
  Set is not Statistics/Histogram/Line Profile/ROI/Difference authority.
- **Keep Selection** is the only curation operation that mutates Selected. The
  result is `baseline_selected_ids` filtered by picked membership, preserving
  baseline order rather than pick order.
- **Keep Selection is an unconditional active-Difference reset boundary.** If a
  Difference is active/visible, the existing PR #32 teardown path runs before
  Selected mutates; active Difference document/provenance and stale presentation
  binding are then cleared. This does not depend on whether old A/B survive in the
  resulting Selected set or Current Comparison Page.
- Immediately after Keep, toolbar `Diff` is unchecked and disabled because no active
  Difference result is bound to the new workspace. Curation does not purge or
  rewrite generation-keyed Difference Map Cache entries, bump source generations,
  or introduce source reload/residency/preload ownership.
- The next active Difference is established only by an explicit **Calculate** for
  the current Difference Image 1/Image 2 pair. Calculate performs normal validation
  and generation-aware cache lookup first, reuses a hit without numerical-map
  recomputation, or runs the existing asynchronous calculation on miss.
- After successful Calculate, toolbar `Diff` is visibility-only for that explicitly
  established result: checked shows it, unchecked hides it, and re-checking shows
  the same result without inferring another pair or recalculating.
- Passive selection/page rerenders must not promote a cached map into an active
  Difference or start implicit Difference calculation.
- Zero picks disable Keep Selection; there is no curation path that silently creates
  an empty Selected set.
- Non-picked images remain Registered and Keep Selection reuses the inherited
  Selected mutation/page/render/source lifecycle rather than creating a
  curation-specific source lifecycle.
- There is no user-facing Cancel command. Clear Selection removes temporary picks;
  a different logical Selected-membership mutation invalidates the captured
  baseline/Pick Set before or with the ordinary mutation.
- Registration-only folder input does not invalidate captured curation state because
  it does not mutate Selected.
- Temporary curation state is not persisted. Settings schema remains v5 at the P4-A
  boundary.
- Comparison Page navigation creates no speculative preload for picked sources. P2
  preload remains Folder Position +1, one position, max-one worker.
- Difference numerical semantics, Display Gain, RAW Black/White/native-source
  semantics, source generation identity, Difference cache identity, and source
  residency accounting remain unchanged.

## P4-B Comparison Set Persistence decisions — Complete

P4-B merged as PR #30 at
`3a19589e6cbad5fa8c814c522df6a553f59ee340`.

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
- Comparison Sets are external user artifacts and do not change Settings schema v5
  at the P4-B boundary.
- P4-C / PR #31 supersedes current writes/UI with Session v1 while retaining this
  legacy Comparison Set v1 read-compatibility contract.

## P4-C Session Persistence & Typed Recent decisions — Complete

P4-C merged as PR #31 at
`436033a0d99513fe8db35f08305395127e430af2`. The authoritative external-artifact
contract is `docs/SESSION_CONTRACT.md`.

- New `.pixelscope` writes use `kind = "pixelscope-session"`, schema v1. Legacy
  `pixelscope-comparison-set` v1 remains read compatible.
- Session persists durable workspace intent: Registered membership, exact ordered
  Selected, a source-path page anchor, applicable source Active/Primary/layout, ROI,
  Line, Display Gain, applicable Split, RAW reconstruction metadata, and only an
  eligible regenerable current-page Difference recipe.
- Runtime arrays, cache/residency/preload/worker state, generated Difference result,
  calculated analysis results, and temporary P4-A Picks remain non-persistent.
- Session Open validates/stages before destructive workspace replacement and
  foreground-loads only the reconstructed bounded Current Comparison Page.
- Session restore reuses existing source, Display Gain, ROI/Line, Split, and
  Difference pipelines rather than creating a persistence-owned runtime path.
- An eligible Difference recipe restores panel intent and issues one explicit
  Calculate; Session does not pre-bind active Difference provenance.
- Writer and reader share current-page Difference eligibility. Off-page hidden
  provenance is omitted at Save and never creates off-page restore ownership.
- Recent Images/Folders/Sessions are typed max-10 path-only MRUs and best-effort
  observer metadata outside Settings schema v5. Image, Folder, and Session activation
  delegate to their canonical workflows.
- Settings schema remains v5 at the P4-C boundary.

## P4-E Analysis Export Productivity decisions — Complete

P4-E merged as PR #34 at
`79ee74134f1ebef9dd13f82e49f8e34407bb78f4`.

- P4-D Saved/named/multiple ROI is deferred. Session v1 already persists the current
  active ROI/Line, while a named ROI manager still lacks owner-approved
  global/source/scene ownership and mixed-dimension coordinate semantics.
- Alpha Overlay/Flicker/Wipe is deferred. Current Multi View, synchronized
  navigation, and Difference cover the principal comparison workflow and no concrete
  need justifies additional pairing/alpha/Gain/Split/Session semantics yet.
- P4-E exports only current existing results: Difference presentation PNG, Histogram
  CSV, and Line Profile CSV. Existing Statistics CSV remains unchanged.
- Export follows `native source → existing analysis/result owner → current
  result/presentation → export consumer`; export never becomes a numerical, source,
  analysis-working-set, Difference, residency/preload, or generation authority.
- Histogram CSV preserves raw native histogram counts/bin edges and identifies the
  current plotted display edge/unit semantics, Full image/Active ROI bounds,
  source/series/channel, and deterministic ordering.
- Line Profile CSV serializes the current plotted samples and identifies the current
  line coordinates, source/series/channel, x/y modes, sample index/position, and
  current rendered value without changing sampling semantics.
- Difference PNG requires an explicitly established active Difference result and
  encodes the current Difference presentation preview, including current
  Absolute/Mask, threshold, Difference gain, and channel presentation. A cached map
  alone is not export authority.
- Difference export does not screenshot UI chrome, call Calculate, change cache
  identity, or bump source generation. PNG encoding/file I/O reuses the existing
  bounded analysis worker pool; no new pool is introduced.
- CSV artifacts are small and may be serialized synchronously from already-computed
  in-memory result series.
- File dialogs reuse the existing configured Export directory; no new export
  setting/schema is added at the P4-E boundary.
- Missing/in-flight result actions are unavailable or safe no-ops. Cancel mutates
  nothing; failed writes report compact status without workspace mutation.
- P4-D Saved ROI and Alpha Overlay remain deferred and are not P4 completion
  blockers.

## P4-F Integration & Workflow Hardening decisions — Complete

P4-F merged as PR #35; the P4-complete main baseline is
`d1d1fbe8fc7ee81855e5e037bcecc1278435e298`.

- P4-F added no new image-analysis numerical authority; it hardened the composed
  P4 workflow and inherited P2/P3 lifetime/ownership contracts.
- Session, curation, Difference, export, Display Gain, current-page loading, and
  repeated close/recreate behavior compose without creating Selected-wide source
  residency/preload authority.
- P4-D Saved/named/multiple ROI, Alpha Overlay/Flicker/Wipe, and arbitrary-angle
  Line Profile remain deferred beyond P4.

## P5 Remote IQA decisions — executable schema v2 / client complete through P5-F

P5-0 / PR #36 established the program. P5-A / PR #37 is the historical executable
schema-v1 baseline. P5-A2 Stage 1 / PR #39 established the durable schema-v2 model;
Stage 2 / PR #40 is the executable schema-v2 authority. P5-B / PR #38 is merged at
`a44978db783ebcecb0d55f8abb52b583e0fdc47c` and owns the canonical local Results
workspace. P5-C / PR #42, P5-D / PR #43, P5-E / PR #44, and P5-F / PR #45 are merged.
P5-G remains an unobserved external validation gate. R closeout is independently
reviewed on PR #55 with merge pending; no repository implementation program is active.

`docs/REMOTE_IQA_CONTRACT.md` is the product/transport ownership authority.
`docs/REMOTE_IQA_V2_SPEC.md` is the current numerical/artifact authority.
`docs/REMOTE_IQA_V1_SPEC.md` remains historical and unchanged.

### Preserved local authority

- Remote IQA remains feature-local and does not replace
  `Registered → Selected → Current Comparison Page → Presented → Resident` or
  `Analysis Working Set = Current Comparison Page`.
- Session v1 remains unchanged. Remote numeric arrays, running jobs, batch
  membership, and machine-local root mappings do not become Session/source/
  residency/preload/Difference authority.
- Passive IQA result browsing does not mutate Files/Selected/Primary/native analysis.
- Native source Inspect remains the explicit P5-D logical-root/hash/canonical-
  registration action rather than direct use of result `relative_path`.

### Executable version/result decisions

- Canonical `iqa_result_reader.load_result()` dispatches schema v2 to the native v2
  reader, schema v1 to historical read-only compatibility, and other versions to
  `UNSUPPORTED`; there is no synthesized v1→v2 measurement upgrade.
- Normal v2 open is summary-first: manifest + summary only. `load_grid_scene()` owns
  deferred grid filesystem/materialization/numerical validation.
- Optional detail references remain opaque until P5-D defines a typed consumer.
- Every published successful Scene, whether COMPLETE or PARTIAL, binds every declared
  `variant_id` once in top-level order and obeys the same exact geometry/numerical
  rules. Failed/cancelled requested Scenes are not represented by incomplete
  published Scenes.

### Identity decisions

- `variant_id` is stable comparison-slot/Reference identity.
- `source_id` is concrete image identity and may recur with identical immutable
  metadata.
- `measurement_context_id` scopes the weighted measurement to its Scene context.
- Display labels are non-identity metadata.
- Absolute presentation mode is client-local state, never a reserved `variant_id`.

### Numerical/presentation decisions

- **Server owns measurement; PixelScope owns reference-dependent comparison,
  reductions, and visualization.**
- W/S1/S2/count/valid plus normative formulas are numerical authority.
- Canonical Scene absolute mean is `ΣS1/ΣW`.
- Default absolute Dataset Overview is `pooled_weighted_mean`.
- Pair-valid support is target-valid ∩ reference-valid.
- Power Mode 1 = ratio of pair-valid aggregate weighted means.
- Power Mode 2 = unweighted mean of finite pair-valid per-grid dB ratios.
- Signed mode = pair-valid target weighted mean minus reference weighted mean.
- Central quality direction applies consistently; neutral/signed has no quality
  delta.
- Default relative Dataset Overview = arithmetic mean of valid Scene comparison
  values.
- P5-B keeps declared variants stable across Absolute/Relative presentation and uses
  the selected Reference only as a local zero anchor where applicable.

### P5-B result-workspace decisions — Complete

- P5-B is the sole local IQA result workspace/controller reused by Remote Open Result.
- Summary-first Absolute presentation is the default.
- Unprepared Reference work is off-thread, one Scene grid at a time, and retains only
  derived scalar results.
- Deferred Reference failure restores last-valid presentation/control state.
- Scene cards are metadata-only and do not open native source directly.
- IQA dock float/dock/maximize/reset follows the Plots workspace lifecycle.

### P5-C settings/storage decisions

- P5-C migrates `ApplicationSettings` schema v5→v6.
- `RemoteIqaSettings` owns `server_base_url`, logical `storage_roots[]`, and
  `staging_root_id`.
- Each storage root maps portable `storage_root_id` to a machine-local client path.
- Client paths, server physical paths, and credentials are not portable result/request
  identity.
- Portable source/result location is always `storage_root_id + relative_path`.
- Existing sources under configured roots are referenced through the most-specific
  matching root. Outside sources may be staged content-addressed by SHA-256.
- Staging uses independently named same-directory temp files, resolved containment
  before mutation, atomic final publication, and SHA-256 verified winner/reuse.
- Cross-process publication and source/result symlink or junction escape handling are
  implemented and covered by P5-C regressions; they are no longer open merge blockers.

### P5-C submission decisions

- Initial user-facing submission is exactly two variants `A/B`; result schema remains
  N-way-capable.
- Current Pair is the A/B pair of **underlying Current Comparison Page documents**,
  not Primary/Active/presented order.
- Folder Pair is immediate-files only, non-recursive, non-symlink, NFC lexical,
  equal-count, pair-by-index, and equal-dimension.
- Remote input is PNG/JPG/JPEG/BMP only; no silent RAW conversion.
- Max submitted Scenes = 512.
- Scene IDs are deterministic `scene_000000...`; each Scene serializes A then B.
- Requests send logical root/path, SHA-256, width, and height; local physical paths
  are not serialized.
- Folder Pair preparation does not imply Files registration/Selected membership or
  batch-wide source residency/preload.
- Folder Pair preview validation owns a latest-request revision; stale callbacks cannot
  publish over a newer request or permanently strand the Validate action after an
  in-flight input edit.

### P5-C PARTIAL decisions

- Durable PARTIAL is now executable schema v2, not `UNSUPPORTED`.
- `publication_state = "partial"` requires ordered `scene_outcomes[]` covering every
  requested Scene.
- Outcome status is succeeded/failed/cancelled.
- Successful outcome has no error diagnostics. Failed/cancelled requires bounded
  error code/message and may include boolean `retryable`.
- PARTIAL requires at least one success and at least one failed/cancelled Scene.
- Published `scenes[]` equals successful outcomes in the same request order and each
  published Scene satisfies normal v2 invariants.
- Zero-success terminal work is FAILED/CANCELLED with no result reference.
- All-success terminal work is SUCCEEDED/COMPLETE.

### P5-C job/retry decisions

- REST boundary is create/status/result/cancel with polling; WebSocket is not required.
- Terminal states are succeeded/partial/failed/cancelled; only succeeded/partial may
  resolve a result reference.
- Result completion never auto-opens Results; user explicitly selects Open Result.
- Create `POST /jobs` is **never automatically retried** because timeout after possible
  server acceptance is ambiguous.
- Terminal result-reference acquisition is an idempotent GET. After the existing
  initial attempt, transient failure uses bounded 1s/2s/4s/8s retry backoff.
- Retry exhaustion leaves the job terminal/visible and never causes resubmission.
- Client diagnostics are classified into configuration, connection, timeout, HTTP,
  protocol, and storage-resolution categories.
- Returned server job IDs are validated before entering the local job model.
- One in-flight local create owner prevents duplicate in-process submission. Ambiguous
  create outcomes block further submission in that process rather than inviting a
  duplicate manual/automatic POST retry. The durable decision remains **no blind
  create retry**.

### P5-C workspace/debug decisions

- One IQA dock contains Setup / Jobs / Results; Results is the P5-B workspace.
- Debug tools are gated by `PIXELSCOPE_REMOTE_IQA_DEBUG` and do not define production
  server architecture.
- Request Inspector runs production request preparation but stops before POST.
- Replay JSON carries logical terminal job/result identity only and still requires
  explicit Open Result.
- Deterministic fake result generation reuses the canonical v2 fixture writer/loader.
- The localhost `ThreadingHTTPServer` is a real-socket client-contract/fault harness
  only. It returns references to deterministic fake results and performs no IQA
  computation.

### P5-C lifecycle decisions — complete / PR #42

- Cooperative cancellation reaches running preflight/hash/staging work and checks
  again immediately before create POST.
- Once create POST is in flight, local cancellation does not pretend to revoke remote
  acceptance; explicit ambiguous-create blocking governs unknown outcomes and no
  blind POST retry is issued.
- Storage-root mapping changes use revision + pending re-resolution so stale
  old-settings result-path callbacks cannot overwrite the newest mapping.
- Latest Folder Pair preview ownership rejects stale validation callbacks and restores
  Validate after the latest worker completes even when inputs changed in flight.
- Production-composition regressions assert Current Pair A/B remains underlying page
  order across Primary/Active presentation changes and Folder Pair preparation does
  not mutate Files/Selected/current page/residency/preload.
- These implementation decisions are complete and merged in PR #42.

### P5-D/P5-E/P5-F lifetime decisions — complete

- P5-D alone owns explicit verified native Inspect/Return; P5-E historical reopen is
  passive until that explicit transition.
- P5-B Result/Reference, P5-D verification/spatial, and P5-E historical resolution use
  one application-owned fixed max-two Remote IQA file/result pool, separate from local
  analysis and the existing P5-C max-two job-operation pool.
- HTTP client reuse uses lazy physical checkout inside executing P5-C workers. Queued
  work cleared before execution owns no physical client; shutdown drains executing
  leases.
- R may clarify construction, dependency, and shutdown seams but may not change these
  pool counts, retry/polling, cancellation, or stale-callback semantics.

### R1 application composition decisions — complete / PR #47

- The production application keeps one small `_compose_remote_iqa` seam rather than a
  DI framework, service container, or new controller hierarchy.
- Application ownership of the Remote IQA result pool and reusable transport pool is
  explicit at the seam.
- Installer order remains P5-C mapping/retry and lifecycle hardening, then P5-D native
  Inspect, then P5-E history/Provenance. The nested settings/open/teardown chains are
  preserved and covered by focused composition and inherited semantic tests.
- Existing controller attributes, `MethodType` wrappers, signal reconnections,
  shutdown behavior, debug gating, and UI layout remain unchanged.

### R2 result-pool injection decisions — complete / PR #48

- Production constructs the Remote IQA result/file pool before `MainWindow` and injects
  it into P5-B at controller construction time.
- The R1 composition seam passes that same pool explicitly to the P5-D and P5-E
  installers. No result-side controller is constructed against one pool and privately
  rebound to another.
- A read-only controller `pool` property exposes the fixed dependency without granting
  rebinding authority. The existing analysis-pool fallback remains available to direct
  non-production controller construction.
- Production initializes the local analysis pool before the Remote IQA pool so Qt
  shutdown retains its existing local-background then Remote-IQA clear/wait order.
- Reinstalling P5-D or P5-E with the same explicit pool is idempotent; supplying a
  different pool fails explicitly rather than hiding split ownership.
- Fixed max-two Remote IQA result/file and P5-C job pools, local analysis separation,
  lazy HTTP checkout, cancellation, stale-callback, and shutdown semantics are
  unchanged.

### R3-A obsolete Remote scaffold decisions — complete / PR #49

- Remove the initial-release `remote/evaluation_client.py`, `mock_client.py`, and
  `schemas.py` plus their isolated `tests/unit/test_remote.py`. Repository history and
  reference inventory show no production/export/canonical-test consumer after their
  common introduction in `262cd5b`.
- This is dead-contract removal, not schema-v1 compatibility removal. Historical
  schema-v1 Result reading remains executable through `test_remote_iqa_v1.py`; canonical
  job transport remains `/v1/iqa/jobs` in `iqa_client.py` and its P5-C/P5-F tests.
- Preserve the original `/v1/jobs` sketch in `server/api_contract.md` with an explicit
  historical/unsupported status and link the server directory to the current durable
  contract. Do not silently rewrite it as a production server specification.

### R3-B Session/legacy adapter decisions — complete / PR #50

- `ui.session.SessionController` installed by `install_session` is the sole production
  transactional Session restore authority and owns `window.session_controller`.
- `ui.comparison_set.SessionController` remains the shared capture/menu and legacy
  restore base; `SessionControllerBase` makes that inheritance role explicit without
  deleting its compatibility names or installer.
- `window.comparison_set_controller` remains a facade over the same production
  controller only to preserve the P4-B selected-count `open_from_path` view. It has no
  independent repository or runtime ownership.
- Production Recent Sessions delegate to the production Session controller, while the
  shared-base predicate retains `install_comparison_set` + Recent compatibility. Session
  v1 writes, legacy Comparison Set v1 reads, repository payloads, transactional restore,
  menu order, Recent behavior, and return semantics are unchanged.

### R6 harness and durable-document decisions — complete / PR #54

- Mechanically forbid PySide6 and pyqtgraph imports from `src/pixelscope/core/` and
  `src/pixelscope/io/`. This enforces the existing numerical/presentation boundary; it
  does not introduce a broader speculative layer framework.
- Retain `REMOTE_IQA_V1_SPEC.md` and `REMOTE_IQA_V2_SPEC.md` because version identity is
  part of persisted compatibility authority.
- Retain the phase-named P5-D/P5-E/P5-F root documents. Their names preserve additive
  contract and closure-evidence scope, while moving them would churn roughly twenty
  durable links without improving current authority. `docs/index.md` now states each
  role explicitly.

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
- Comparison Page navigation, Pick membership, Session Save/Open, P4-E export, and
  Remote IQA result membership introduce no Selected-wide speculative
  preload/cache/residency owner.
- P5-B Reference-grid preparation and P5-C transport/staging workers are feature-local
  and do not alter decoded source residency ownership. P5-F added no result-grid cache
  or preload; any later tuning requires measured P5-G evidence and review.

## Validation and merge state

P3 is Complete through PR #27. P4 is Complete through PR #35. P5 repository-side
client work is complete through P5-F / PR #45. R0–R6 merged as PR #46–#54. Current
main is `7c3dbe386aaff900f0accc7ce460759df80f14e0`; R7 closeout is independently
reviewed on PR #55 with merge pending, and no repository implementation program is
active.

Observed P5-C evidence includes:

- historical full-suite checkpoint at `04f8c08...`: 809 pytest PASS plus Ruff/mypy/
  diff PASS, before later P5-C stages;
- owner full requested validation on durable-doc head `f7728b2...`: PASS;
- Setup UX + Request Inspector focused/static PASS;
- Replay JSON + deterministic COMPLETE result manual Open Result PASS;
- Stage-4 focused localhost/result-retry/submission/UI suite: 26 PASS;
- normal real-socket localhost submit/poll/result-reference manual PASS;
- transient terminal `/result` HTTP 500 followed by automatic successful retry with
  no resubmit, manually reproduced on a second newly-created job;
- staging hardening focused/static PASS and lifecycle/storage hardening PASS after
  the Windows concurrent-publication repair;
- result-remap focused tests, Ruff check, mypy, and `git diff --check` PASS on
  `86cc871...`; `177078f...` is the subsequent formatter-only repair.

Independent whole-PR review at `177078f...` confirmed the earlier architecture
blockers closed and requested only narrow preview-lifecycle, authority-regression,
and stale-status-doc closeout. That evidence is historical P5-C evidence; PR #42 later
merged. P5-D/E/F subsequently merged as PR #43/#44/#45. Their exact evidence remains in
the corresponding durable contracts/characterization and is not inferred as current R
validation.

Only validation actually observed for a named head may be recorded as PASS.
