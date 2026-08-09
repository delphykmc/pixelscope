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

- Ordered selection is the comparison model; Difference may select any two current
  images.
- Multi View has one fixed layout policy. `_fixed_geometry()` is the sole geometry
  authority; P1-F removed arrangement compatibility state.
- Primary-image analysis reference priority is primary, active, then first
  displayed.
- Difference caches one absolute map per order-independent document-generation
  pair and derives views/metrics from it. The map explicitly records native or
  normalized domain metadata.
- RAW storage format, sample container, effective bit depth, endian, alignment,
  Black Level, and White Level remain separate concepts.
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
- Visible, selected, active/analysis, Difference-pair, and foreground-authority
  sources are protected while required.
- One required source may exceed the entire soft budget while protected.
- Preview arrays, Qt textures, Difference maps, derived presentation buffers,
  transient worker arrays, Python/Qt overhead, and process RSS are not source
  residency.
- Source eviction and Difference-cache ownership are independent. Evicting source
  does not invalidate a valid generation-keyed Difference map.

### Navigation, preload, and promotion

- PageUp/PageDown owns previous/next Folder Position; Up/Down remains Files-tree
  navigation and Left/Right remains previous/next selected image.
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

P3-B intentionally does **not** make the numerical gain implementation RAW-only.
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
  the pre-P3-B global-preview anchor `min(black_level)` while preserving the
  stored tuple.
- Bayer four-value Black uses R/Gr/Gb/B channel-specific anchors by CFA parity for
  RGGB/GRBG/GBRG/BGGR.
- Scalar Bayer Black applies one anchor to all channels.
- Split Bayer planes use their named channel anchor.
- Bayer processing operates on parity-plane views and never materializes a
  full-size Black Level map.

### P3-B UI/runtime and lifetime policy

P3-B established the runtime/lifetime boundary that P3-C retains:

- session-local gain choices are 1×/2×/4×/8×/16×;
- gain is not persisted to `RawProfile`, workspace QSettings, or
  `ApplicationSettings`; schema remains v5;
- gain 1× uses canonical `ImageDocument.preview` and schedules no gained-preview
  worker;
- gain >1 derives a viewer-local preview from resident source on the shared
  numerical worker pool;
- result acceptance checks task/request/document/source/generation/gain/visibility
  identity;
- hidden viewers release gain>1 derived buffers back to canonical 1× presentation
  and regenerate current gain when shown;
- `+` / `-` Display Gain command ownership is the image-presentation subtree
  (`MainWindow.central_stack`) with `WidgetWithChildrenShortcut`, not the whole
  window. Files-tree focus therefore retains Qt-native expand/collapse behavior;
- teardown callbacks must respect QObject lifetime and Qt sibling-destruction order.

### P3-B scope exclusions

P3-B adds no ordinary-image gain UI/runtime activation, demosaic, white balance,
CCM, tone-map feature, optical-Black estimation, processed RAW document/analysis,
new Difference mode, profile management/suggestion, persistence, Settings schema
bump, resource-policy redesign, packaging, or broad MainWindow/toolbar redesign.

## Accepted P3-C Display Gain generalization decision

P3-C implements ordinary-image activation of the P3-B generic display-gain core
while retaining RAW semantics and the P3-B command/lifecycle boundaries.

### One session state and product surface

- The user-facing term is **Display Gain** or **Gain**, never **Exposure**.
- One QApplication-session `DisplayGainState` serves all supported viewer
  presentations using 1×/2×/4×/8×/16×.
- No RAW/RGB duplicate controls are introduced.
- Generic session/control ownership lives in `ui.display_gain`; the RAW-only
  compatibility UI wrapper is removed.
- Display Gain is not persisted to Settings, workspace state, or RAW profiles;
  schema remains v5.

### Ordinary Gray/RGB/RGBA policy

- Ordinary Gray and RGB use the same core with `anchor=0`.
- All RGB channels receive the same gain; P3-C adds no color-balance transform.
- Ordinary RGB split-channel visual documents gain their native 2-D source plane
  with `anchor=0` while retaining colored presentation.
- RGBA applies gain only to RGB. Gain>1 alpha must equal canonical 1× preview
  alpha exactly.
- RGBA gain arithmetic targets the RGB source view rather than constructing a
  four-channel float32 gain working buffer.
- Difference is excluded from general Display Gain because Difference owns its
  own independent presentation Gain.

### RAW regression policy

P3-C does not alter P3-B RAW semantics:

- RAW 1× still maps effective full scale without subtracting Black or promoting
  White Level to display maximum;
- gain >1 remains `B + G * (X - B)`;
- Gray scalar/legacy tuple and Bayer R/Gr/Gb/B Black-anchor rules are unchanged;
- split Bayer channels retain their named-channel Black anchor;
- White Level remains metadata rather than display authority.

### Generic viewer runtime policy

- Gain 1× is a no-work path for every supported presentation: canonical
  `ImageDocument.preview` is reused, no full-frame gain worker is scheduled, and
  no extra gained preview is retained.
- Gain >1 uses resident source and the existing shared numerical pool; it does not
  decode/reload source.
- Result acceptance includes task/request serial, document/source/canonical-preview
  identity, generation, requested gain, and visibility.
- Hidden/replaced viewers release unnecessary gain>1 derived buffers and
  regenerate the current session gain when shown again.
- Display Gain never mutates source/generation, source residency, or Difference
  cache identity.
- No new worker pool, resource setting, scheduler redesign, or debounce policy is
  added without profiling evidence.

### Analysis and shortcut independence

- Pixel inspection, Statistics, Histogram, Line Profile numerical source, Split
  Channel source arrays, Difference, source generation, residency accounting, and
  Difference-cache identity remain independent of Display Gain.
- P3-C reuses the P3-B `central_stack` / `WidgetWithChildrenShortcut` command
  boundary. Files-tree `+` / `-` routing remains native and regression-covered for
  both ordinary and RAW content.

### P3-C scope exclusions

P3-C adds no demosaic, white balance, CCM/color conversion, tone mapping, new
gamma feature, processed RAW/document analysis, exposure simulation, automatic
Black estimation, profile management/suggestion, gain persistence, Settings
schema bump, new Difference mode, preload/residency redesign, worker-pool
expansion, broad MainWindow rewrite, packaging, signing, or installer work.

Additional clipping/highlight/shadow and Bayer observability remains optional and
must not expand the merge-critical Display Gain slice without a clear product need.

## Current resource policy

- Difference Map Cache remains byte-budgeted and persistence-free with default
  128 MiB.
- Decoded-source residency remains a protected soft-budget manager with default
  256 MiB.
- Normal load pool max remains two; preload pool max remains one; shared numerical
  pool max remains four.
- Display Gain derived previews are viewer-local presentation buffers and are not
  added to decoded-source residency or Difference cache ownership.
- The generic gain core does not become a cache, persistence, or resource-policy
  owner.

## Validation and merge state

P3-B is complete as PR #24. P3-C implementation is present on
`feature/p3-c-display-gain`. Core/UI/RAW-regression test code is added or updated,
but the Chat implementation agent has not run repository validation. Owner/local
Windows validation of the latest P3-C head is required before merge.
